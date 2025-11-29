from datetime import datetime
from pathlib import Path

from celery_singleton import Singleton
from loguru import logger

from chainswarm_core.jobs import BaseTask

from packages.benchmark.models.analysis import (
    AnalysisFailureReason,
    AnalysisStatus,
    RepositoryAnalysisResult,
)
from packages.benchmark.models.miner import ImageType
from packages.benchmark.security.address_scanner import AddressScanner
from packages.benchmark.security.code_scanner import CodeScanner
from packages.benchmark.security.file_validator import FileValidator
from packages.benchmark.security.llm_analyzer import LLMCodeAnalyzer
from packages.benchmark.security.malware_scanner import MalwareScanner
from packages.jobs.celery_app import celery_app


class CodeAnalysisTask(BaseTask, Singleton):

    def execute_task(self, context: dict) -> dict:
        image_type = context['image_type']
        repository_path = Path(context['repository_path'])
        hotkey = context['hotkey']

        
        logger.info("Starting code analysis", extra={
            "repository_path": str(repository_path),
            "hotkey": hotkey,
            "image_type": image_type
        })
        
        result = RepositoryAnalysisResult(
            repository_path=repository_path,
            hotkey=hotkey,
            image_type=image_type,
            status=AnalysisStatus.RUNNING,
            analysis_started_at=datetime.now()
        )
        
        file_validator = FileValidator()
        files_valid, file_issues = file_validator.validate_repository(repository_path)
        
        result.total_files_scanned = len(list(repository_path.rglob("*")))
        result.blacklisted_files = [str(f.file_path) for f in file_issues if not f.is_allowed]
        
        if not files_valid:
            binary_files = [str(f.file_path) for f in file_issues if f.is_binary]
            if binary_files:
                result.status = AnalysisStatus.FAILED
                result.failure_reason = AnalysisFailureReason.BINARY_FILE_DETECTED
                result.analysis_completed_at = datetime.now()
                logger.warning("Analysis failed: binary files detected", extra={
                    "hotkey": hotkey,
                    "binary_files": binary_files[:5]
                })
                return result.to_dict()
            
            data_extensions = {'.csv', '.parquet', '.pkl', '.pickle', '.h5'}
            data_files = [
                str(f.file_path) for f in file_issues 
                if Path(str(f.file_path)).suffix.lower() in data_extensions
            ]
            if data_files:
                result.status = AnalysisStatus.FAILED
                result.failure_reason = AnalysisFailureReason.DATA_FILE_DETECTED
                result.analysis_completed_at = datetime.now()
                logger.warning("Analysis failed: data files detected", extra={
                    "hotkey": hotkey,
                    "data_files": data_files[:5]
                })
                return result.to_dict()
        
        dockerfile_path = repository_path / "ops/Dockerfile"
        if not dockerfile_path.exists():
            result.status = AnalysisStatus.FAILED
            result.failure_reason = AnalysisFailureReason.DOCKERFILE_MISSING
            result.analysis_completed_at = datetime.now()
            logger.warning("Analysis failed: Dockerfile missing", extra={"hotkey": hotkey})
            return result.to_dict()
        
        code_scanner = CodeScanner()
        
        if code_scanner.is_obfuscated(repository_path):
            code_issues = code_scanner.scan_repository(repository_path)
            result.obfuscated_files = [str(issue) for issue in code_issues]
            result.status = AnalysisStatus.FAILED
            result.failure_reason = AnalysisFailureReason.OBFUSCATED_CODE
            result.analysis_completed_at = datetime.now()
            logger.warning("Analysis failed: obfuscated code detected", extra={
                "hotkey": hotkey,
                "issues": result.obfuscated_files[:5]
            })
            return result.to_dict()
        
        address_scanner = AddressScanner()
        address_results = address_scanner.scan_repository(repository_path)
        
        result.address_scan_results = address_results
        
        files_with_addresses = [str(r.file_path) for r in address_results if r.has_addresses]
        files_with_hashes = [str(r.file_path) for r in address_results if r.has_hashes]
        
        result.files_with_addresses = files_with_addresses
        result.files_with_hashes = files_with_hashes
        
        if files_with_addresses:
            result.status = AnalysisStatus.FAILED
            result.failure_reason = AnalysisFailureReason.CRYPTO_ADDRESS_DETECTED
            result.analysis_completed_at = datetime.now()
            logger.warning("Analysis failed: crypto addresses detected", extra={
                "hotkey": hotkey,
                "files": files_with_addresses[:5]
            })
            return result.to_dict()
        
        if files_with_hashes:
            result.status = AnalysisStatus.FAILED
            result.failure_reason = AnalysisFailureReason.TRANSACTION_HASH_DETECTED
            result.analysis_completed_at = datetime.now()
            logger.warning("Analysis failed: transaction hashes detected", extra={
                "hotkey": hotkey,
                "files": files_with_hashes[:5]
            })
            return result.to_dict()
        
        malware_scanner = MalwareScanner()
        malware_result = malware_scanner.has_malware(repository_path)
        
        if malware_result:
            result.malware_issues = [malware_result]
            result.status = AnalysisStatus.FAILED
            result.failure_reason = AnalysisFailureReason.MALWARE_DETECTED
            result.analysis_completed_at = datetime.now()
            logger.warning("Analysis failed: malware detected", extra={
                "hotkey": hotkey,
                "malware": malware_result
            })
            return result.to_dict()
        
        llm_analyzer = LLMCodeAnalyzer()
        result.llm_analysis_enabled = True
        llm_results = llm_analyzer.analyze_repository(repository_path)
        result.llm_results = llm_results
        result.llm_files_analyzed = len(llm_results)
        
        unsafe_files = [r for r in llm_results if not r.is_safe and r.confidence > 0.7]
        
        if unsafe_files:
            result.llm_issues = []
            for uf in unsafe_files:
                result.llm_issues.extend([f"{uf.file_path.name}: {issue}" for issue in uf.issues])
            
            result.status = AnalysisStatus.FAILED
            result.failure_reason = AnalysisFailureReason.LLM_REJECTION
            result.analysis_completed_at = datetime.now()
            logger.warning("Analysis failed: LLM flagged security issues", extra={
                "hotkey": hotkey,
                "unsafe_files": [str(uf.file_path) for uf in unsafe_files]
            })
            return result.to_dict()
        
        result.status = AnalysisStatus.PASSED
        result.analysis_completed_at = datetime.now()
        result.allowed_files = len([f for f in repository_path.rglob("*") if f.is_file()]) - len(result.blacklisted_files)
        
        logger.info("Code analysis passed", extra={
            "hotkey": hotkey,
            "image_type": image_type,
            "files_analyzed": result.total_files_scanned,
            "llm_files_analyzed": result.llm_files_analyzed
        })
        
        return result.to_dict()


@celery_app.task(
    bind=True,
    base=CodeAnalysisTask,
    autoretry_for=(Exception,),
    retry_kwargs={
        'max_retries': 2,
        'countdown': 60
    },
    time_limit=1800,
    soft_time_limit=1700
)
def code_analysis_task(
    self,
    repository_path: str,
    hotkey: str,
    image_type: str,
):
    context = {
        'repository_path': repository_path,
        'hotkey': hotkey,
        'image_type': image_type
    }
    
    return self.run(context)