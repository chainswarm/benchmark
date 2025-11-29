import os
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from loguru import logger

from packages.benchmark.models.analysis import CloneResult
from packages.benchmark.models.miner import ImageType
from packages.benchmark.models.results import ValidationResult


class RepositoryManager:
    def __init__(self, repositories_base_path: str = None):
        self.repositories_base_path = Path(repositories_base_path or os.environ['BENCHMARK_REPOS_PATH'])
        self.repositories_base_path.mkdir(parents=True, exist_ok=True)
        
        for image_type in ImageType:
            type_directory = self.repositories_base_path / image_type.value
            type_directory.mkdir(exist_ok=True)

    def clone_with_type(self, hotkey: str, repository_url: str, image_type: ImageType) -> CloneResult:
        try:
            self._validate_github_url(repository_url)
        except ValueError as e:
            return CloneResult(
                success=False,
                error_message=str(e),
                hotkey=hotkey,
                image_type=image_type.value,
                repository_url=repository_url
            )
        
        repository_path = self.get_repository_path(hotkey, image_type)
        
        try:
            if repository_path.exists():
                logger.info("Pulling existing repository", extra={
                    "hotkey": hotkey,
                    "image_type": image_type.value,
                    "path": str(repository_path)
                })
                self._git_pull(repository_path)
            else:
                logger.info("Cloning repository", extra={
                    "hotkey": hotkey,
                    "image_type": image_type.value,
                    "url": repository_url
                })
                self._git_clone(repository_url, repository_path)
            
            return CloneResult(
                success=True,
                repository_path=repository_path,
                hotkey=hotkey,
                image_type=image_type.value,
                repository_url=repository_url
            )
            
        except RuntimeError as e:
            logger.error("Git operation failed", extra={
                "hotkey": hotkey,
                "error": str(e)
            })
            return CloneResult(
                success=False,
                error_message=str(e),
                hotkey=hotkey,
                image_type=image_type.value,
                repository_url=repository_url
            )

    def get_repository_path(self, hotkey: str, image_type: ImageType) -> Path:
        return self.repositories_base_path / image_type.value / hotkey

    def clone_or_pull(self, hotkey: str, repository_url: str) -> Path:
        self._validate_github_url(repository_url)
        repository_path = self.repositories_base_path / hotkey
        
        if repository_path.exists():
            logger.info("Pulling existing repository", extra={"hotkey": hotkey, "path": str(repository_path)})
            self._git_pull(repository_path)
        else:
            logger.info("Cloning repository", extra={"hotkey": hotkey, "url": repository_url})
            self._git_clone(repository_url, repository_path)
        
        return repository_path

    def validate_repository(self, repository_path: Path) -> ValidationResult:
        has_dockerfile = self._check_dockerfile_exists(repository_path)
        if not has_dockerfile:
            return ValidationResult(
                is_valid=False,
                repo_path=repository_path,
                error_message="Dockerfile not found in repository root",
                has_dockerfile=False,
                is_obfuscated=False,
                has_malware=False
            )
        
        is_obfuscated = self.check_obfuscation(repository_path)
        if is_obfuscated:
            return ValidationResult(
                is_valid=False,
                repo_path=repository_path,
                error_message="Repository contains obfuscated code",
                has_dockerfile=True,
                is_obfuscated=True,
                has_malware=False
            )
        
        scan_result = self.scan_malware(repository_path)
        if scan_result:
            return ValidationResult(
                is_valid=False,
                repo_path=repository_path,
                error_message=f"Malware detected: {scan_result}",
                has_dockerfile=True,
                is_obfuscated=False,
                has_malware=True
            )
        
        return ValidationResult(
            is_valid=True,
            repo_path=repository_path,
            error_message=None,
            has_dockerfile=True,
            is_obfuscated=False,
            has_malware=False
        )

    def check_obfuscation(self, repository_path: Path) -> bool:
        python_files = list(repository_path.rglob("*.py"))
        
        for python_file in python_files:
            if self._is_in_venv(python_file):
                continue
            
            content = python_file.read_text(errors='ignore')
            
            if self._has_base64_code_blocks(content):
                logger.warning("Base64 encoded code detected", extra={"file": str(python_file)})
                return True
            
            if self._is_minified_python(content):
                logger.warning("Minified Python detected", extra={"file": str(python_file)})
                return True
        
        return False

    def scan_malware(self, repository_path: Path) -> str:
        all_files = list(repository_path.rglob("*"))
        
        for file_path in all_files:
            if not file_path.is_file():
                continue
            
            if self._is_in_venv(file_path):
                continue
            
            if self._is_suspicious_binary(file_path):
                return f"Suspicious binary: {file_path.name}"
            
            if file_path.suffix in ['.sh', '.bash']:
                content = file_path.read_text(errors='ignore')
                if self._has_curl_bash_pattern(content):
                    return f"Dangerous shell pattern in: {file_path.name}"
        
        dockerfile_path = repository_path / "Dockerfile"
        if dockerfile_path.exists():
            dockerfile_content = dockerfile_path.read_text()
            malware_check = self._check_dockerfile_security(dockerfile_content)
            if malware_check:
                return malware_check
        
        return ""

    def cleanup_repository_with_type(self, hotkey: str, image_type: ImageType) -> None:
        repository_path = self.get_repository_path(hotkey, image_type)
        if repository_path.exists():
            logger.info("Cleaning up repository", extra={
                "hotkey": hotkey,
                "image_type": image_type.value,
                "path": str(repository_path)
            })
            shutil.rmtree(repository_path)

    def cleanup_repository(self, hotkey: str) -> None:
        repository_path = self.repositories_base_path / hotkey
        if repository_path.exists():
            logger.info("Cleaning up repository", extra={"hotkey": hotkey})
            shutil.rmtree(repository_path)

    def _validate_github_url(self, repository_url: str) -> None:
        parsed = urlparse(repository_url)
        if parsed.netloc not in ['github.com', 'www.github.com']:
            raise ValueError(f"Repository must be from github.com, got: {parsed.netloc}")

    def _git_clone(self, repository_url: str, repository_path: Path) -> None:
        result = subprocess.run(
            ['git', 'clone', '--depth', '1', repository_url, str(repository_path)],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            raise RuntimeError(f"Git clone failed: {result.stderr}")

    def _git_pull(self, repository_path: Path) -> None:
        result = subprocess.run(
            ['git', '-C', str(repository_path), 'pull', '--ff-only'],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            raise RuntimeError(f"Git pull failed: {result.stderr}")

    def get_commit_hash(self, repository_path: Path, short: bool = True) -> str:
        """Get the current commit hash of a repository.
        
        Args:
            repository_path: Path to the git repository
            short: If True, returns 7-character short hash. Otherwise full hash.
            
        Returns:
            The commit hash as a lowercase string
        """
        format_arg = '--short=7' if short else ''
        cmd = ['git', '-C', str(repository_path), 'rev-parse']
        if format_arg:
            cmd.append(format_arg)
        cmd.append('HEAD')
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to get commit hash: {result.stderr}")
        
        return result.stdout.strip().lower()

    def _check_dockerfile_exists(self, repository_path: Path) -> bool:
        return (repository_path / "Dockerfile").exists()

    def _is_in_venv(self, file_path: Path) -> bool:
        parts = file_path.parts
        venv_indicators = ['venv', '.venv', 'env', '.env', 'site-packages', '__pycache__']
        return any(indicator in parts for indicator in venv_indicators)

    def _has_base64_code_blocks(self, content: str) -> bool:
        base64_pattern = r'exec\s*\(\s*__import__\s*\(\s*["\']base64["\']\s*\)'
        if re.search(base64_pattern, content):
            return True
        
        eval_base64_pattern = r'eval\s*\(\s*.*base64.*decode'
        if re.search(eval_base64_pattern, content):
            return True
        
        long_base64_pattern = r'[A-Za-z0-9+/=]{200,}'
        matches = re.findall(long_base64_pattern, content)
        for match in matches:
            if len(match) > 500:
                return True
        
        return False

    def _is_minified_python(self, content: str) -> bool:
        lines = content.split('\n')
        if len(lines) < 5:
            return False
        
        total_length = sum(len(line) for line in lines)
        average_line_length = total_length / len(lines) if lines else 0
        
        if average_line_length > 500:
            return True
        
        exec_compile_pattern = r'exec\s*\(\s*compile\s*\('
        if re.search(exec_compile_pattern, content):
            return True
        
        return False

    def _is_suspicious_binary(self, file_path: Path) -> bool:
        suspicious_extensions = {'.exe', '.bat', '.cmd', '.com', '.scr', '.msi'}
        
        if file_path.suffix.lower() in suspicious_extensions:
            return True
        
        return False

    def _has_curl_bash_pattern(self, content: str) -> bool:
        patterns = [
            r'curl\s+.*\|\s*bash',
            r'curl\s+.*\|\s*sh',
            r'wget\s+.*\|\s*bash',
            r'wget\s+.*\|\s*sh',
        ]
        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        return False

    def _check_dockerfile_security(self, content: str) -> str:
        dangerous_patterns = [
            (r'curl\s+.*\|\s*bash', "Curl piped to bash in Dockerfile"),
            (r'wget\s+.*\|\s*bash', "Wget piped to bash in Dockerfile"),
            (r'curl\s+.*\|\s*sh', "Curl piped to sh in Dockerfile"),
        ]
        
        for pattern, message in dangerous_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return message
        
        return ""