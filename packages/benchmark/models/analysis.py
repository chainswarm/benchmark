from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any


class AnalysisStatus(str, Enum):
    PENDING = 'pending'
    RUNNING = 'running'
    PASSED = 'passed'
    FAILED = 'failed'
    ERROR = 'error'


class AnalysisFailureReason(str, Enum):
    BLACKLISTED_FILE = 'blacklisted_file'
    OBFUSCATED_CODE = 'obfuscated_code'
    CRYPTO_ADDRESS_DETECTED = 'crypto_address_detected'
    TRANSACTION_HASH_DETECTED = 'transaction_hash_detected'
    MALWARE_DETECTED = 'malware_detected'
    LLM_REJECTION = 'llm_rejection'
    BINARY_FILE_DETECTED = 'binary_file_detected'
    DATA_FILE_DETECTED = 'data_file_detected'
    DOCKERFILE_MISSING = 'dockerfile_missing'
    VALIDATION_ERROR = 'validation_error'


@dataclass
class FileAnalysisResult:
    file_path: Path
    is_allowed: bool
    issues: List[str] = field(default_factory=list)
    detected_addresses: List[str] = field(default_factory=list)
    detected_hashes: List[str] = field(default_factory=list)
    is_obfuscated: bool = False
    is_binary: bool = False


@dataclass
class AddressScanResult:
    file_path: Path
    bitcoin_addresses: List[str] = field(default_factory=list)
    evm_addresses: List[str] = field(default_factory=list)
    substrate_addresses: List[str] = field(default_factory=list)
    transaction_hashes: List[str] = field(default_factory=list)
    
    @property
    def has_addresses(self) -> bool:
        return bool(
            self.bitcoin_addresses or 
            self.evm_addresses or 
            self.substrate_addresses
        )
    
    @property
    def has_hashes(self) -> bool:
        return bool(self.transaction_hashes)
    
    @property
    def total_findings(self) -> int:
        return (
            len(self.bitcoin_addresses) +
            len(self.evm_addresses) +
            len(self.substrate_addresses) +
            len(self.transaction_hashes)
        )


@dataclass
class LLMAnalysisResult:
    file_path: Path
    is_safe: bool
    confidence: float
    issues: List[str] = field(default_factory=list)
    raw_response: Optional[str] = None
    model_used: str = "anthropic/claude-3-haiku"
    analysis_time_seconds: float = 0.0


@dataclass
class RepositoryAnalysisResult:
    repository_path: Path
    hotkey: str
    image_type: str
    status: AnalysisStatus
    failure_reason: Optional[AnalysisFailureReason] = None
    total_files_scanned: int = 0
    allowed_files: int = 0
    blacklisted_files: List[str] = field(default_factory=list)
    obfuscated_files: List[str] = field(default_factory=list)
    files_with_addresses: List[str] = field(default_factory=list)
    files_with_hashes: List[str] = field(default_factory=list)
    malware_issues: List[str] = field(default_factory=list)
    address_scan_results: List[AddressScanResult] = field(default_factory=list)
    llm_analysis_enabled: bool = True
    llm_files_analyzed: int = 0
    llm_issues: List[str] = field(default_factory=list)
    llm_results: List[LLMAnalysisResult] = field(default_factory=list)
    analysis_started_at: Optional[datetime] = None
    analysis_completed_at: Optional[datetime] = None
    
    @property
    def is_valid(self) -> bool:
        return self.status == AnalysisStatus.PASSED
    
    @property
    def all_issues(self) -> List[str]:
        issues = []
        issues.extend([f"Blacklisted file: {f}" for f in self.blacklisted_files])
        issues.extend([f"Obfuscated file: {f}" for f in self.obfuscated_files])
        issues.extend([f"Addresses in: {f}" for f in self.files_with_addresses])
        issues.extend([f"Hashes in: {f}" for f in self.files_with_hashes])
        issues.extend(self.malware_issues)
        issues.extend(self.llm_issues)
        return issues
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "repository_path": str(self.repository_path),
            "hotkey": self.hotkey,
            "image_type": self.image_type,
            "status": self.status.value,
            "failure_reason": self.failure_reason.value if self.failure_reason else None,
            "total_files_scanned": self.total_files_scanned,
            "allowed_files": self.allowed_files,
            "blacklisted_files": self.blacklisted_files,
            "obfuscated_files": self.obfuscated_files,
            "files_with_addresses": self.files_with_addresses,
            "files_with_hashes": self.files_with_hashes,
            "malware_issues": self.malware_issues,
            "llm_analysis_enabled": self.llm_analysis_enabled,
            "llm_files_analyzed": self.llm_files_analyzed,
            "llm_issues": self.llm_issues,
            "is_valid": self.is_valid,
            "all_issues": self.all_issues
        }


@dataclass
class CloneResult:
    success: bool
    repository_path: Optional[Path] = None
    error_message: Optional[str] = None
    hotkey: str = ""
    image_type: str = ""
    repository_url: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "repository_path": str(self.repository_path) if self.repository_path else None,
            "error_message": self.error_message,
            "hotkey": self.hotkey,
            "image_type": self.image_type,
            "repository_url": self.repository_url
        }


@dataclass
class BuildResult:
    success: bool
    image_tag: Optional[str] = None
    error_message: Optional[str] = None
    build_time_seconds: float = 0.0
    hotkey: str = ""
    image_type: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "image_tag": self.image_tag,
            "error_message": self.error_message,
            "build_time_seconds": self.build_time_seconds,
            "hotkey": self.hotkey,
            "image_type": self.image_type
        }