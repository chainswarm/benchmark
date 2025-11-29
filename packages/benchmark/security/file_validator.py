import os
from pathlib import Path
from typing import List, Set, Tuple

from loguru import logger

from packages.benchmark.models.analysis import FileAnalysisResult


class FileValidator:
    VENV_INDICATORS = {'venv', '.venv', 'env', '.env', 'site-packages', '__pycache__', 'node_modules', '.git'}
    
    ALLOWED_EXTENSIONS = {
        '.py', '.pyi', '.pyw',
        '.json', '.yaml', '.yml', '.toml', '.cfg', '.ini', '.conf',
        '.md', '.rst', '.txt',
        '.sh', '.bash',
        '.sql',
        '.html', '.css', '.js', '.ts', '.jsx', '.tsx',
        '.lock',
        '.gitignore', '.gitattributes',
        '.dockerignore',
        '.env.example', '.env.sample',
    }
    
    ALLOWED_NO_EXTENSION = {
        'Dockerfile',
        'Makefile',
        'LICENSE',
        'LICENCE',
        'README',
        'CHANGELOG',
        'CONTRIBUTING',
        'AUTHORS',
        'MANIFEST',
        'requirements',
        'Pipfile',
        'setup',
        'pyproject',
    }
    
    BLACKLISTED_EXTENSIONS = {
        '.pkl', '.pickle', '.joblib',
        '.npy', '.npz',
        '.exe', '.bat', '.cmd', '.com', '.scr', '.msi',
        '.app', '.dmg', '.pkg',
        '.dll', '.so', '.dylib', '.pyd',
        '.csv', '.tsv', '.parquet', '.feather', '.arrow',
        '.h5', '.hdf5', '.hdf',
        '.sqlite', '.sqlite3', '.db',
        '.json.gz', '.jsonl', '.ndjson',
        '.zip', '.tar', '.gz', '.bz2', '.xz', '.rar', '.7z',
        '.tar.gz', '.tgz', '.tar.bz2', '.tar.xz',
        '.pt', '.pth', '.onnx', '.pb', '.ckpt',
        '.keras', '.model',
        '.bin', '.safetensors',
        '.jar', '.class', '.war',
        '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.svg',
        '.webp', '.tiff', '.tif',
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        '.odt', '.ods', '.odp',
    }
    
    MAX_FILE_SIZE_MB = 10
    MAX_TOTAL_SIZE_MB = 100
    
    def __init__(self, max_file_size_mb: int = None, max_total_size_mb: int = None,
                 additional_allowed: Set[str] = None, additional_blacklisted: Set[str] = None):
        self.max_file_size_mb = max_file_size_mb or self.MAX_FILE_SIZE_MB
        self.max_total_size_mb = max_total_size_mb or self.MAX_TOTAL_SIZE_MB
        
        self.allowed_extensions = self.ALLOWED_EXTENSIONS.copy()
        self.blacklisted_extensions = self.BLACKLISTED_EXTENSIONS.copy()
        
        if additional_allowed:
            self.allowed_extensions.update(additional_allowed)
        if additional_blacklisted:
            self.blacklisted_extensions.update(additional_blacklisted)
    
    def validate_repository(self, repository_path: Path) -> Tuple[bool, List[FileAnalysisResult]]:
        all_valid = True
        results = []
        total_size = 0
        
        for file_path in repository_path.rglob("*"):
            if not file_path.is_file():
                continue
            if self._is_in_venv(file_path):
                continue
            
            result = self.validate_file(file_path)
            
            if not result.is_allowed:
                all_valid = False
                results.append(result)
                logger.warning("File validation failed", extra={
                    "file": str(file_path),
                    "issues": result.issues
                })
            
            try:
                file_size = file_path.stat().st_size
                total_size += file_size
                
                if file_size > self.max_file_size_mb * 1024 * 1024:
                    all_valid = False
                    result.is_allowed = False
                    result.issues.append(f"File too large: {file_size / (1024*1024):.2f}MB > {self.max_file_size_mb}MB")
                    if result not in results:
                        results.append(result)
            except OSError:
                pass
        
        return all_valid, results
    
    def validate_file(self, file_path: Path) -> FileAnalysisResult:
        result = FileAnalysisResult(file_path=file_path, is_allowed=True)
        
        extension = file_path.suffix.lower()
        filename = file_path.name
        
        if extension in self.blacklisted_extensions:
            result.is_allowed = False
            result.issues.append(f"Blacklisted file type: {extension}")
            result.is_binary = self._is_binary_extension(extension)
            return result
        
        if self._has_compound_blacklisted_extension(filename):
            result.is_allowed = False
            result.issues.append(f"Blacklisted compound extension: {filename}")
            result.is_binary = True
            return result
        
        if extension == '':
            if not self._is_allowed_no_extension(filename):
                if self._is_binary_content(file_path):
                    result.is_allowed = False
                    result.is_binary = True
                    result.issues.append(f"Binary file without extension: {filename}")
                    return result
            return result
        
        if extension not in self.allowed_extensions:
            if self._is_binary_content(file_path):
                result.is_allowed = False
                result.is_binary = True
                result.issues.append(f"Binary file with unknown extension: {extension}")
        
        return result
    
    def _is_in_venv(self, file_path: Path) -> bool:
        parts = file_path.parts
        return any(indicator in parts for indicator in self.VENV_INDICATORS)
    
    def _is_binary_extension(self, extension: str) -> bool:
        binary_extensions = {
            '.exe', '.dll', '.so', '.dylib', '.pyd',
            '.pkl', '.pickle', '.joblib', '.npy', '.npz',
            '.pt', '.pth', '.onnx', '.pb', '.h5', '.bin',
            '.zip', '.tar', '.gz', '.rar', '.7z',
            '.png', '.jpg', '.jpeg', '.gif', '.pdf',
            '.parquet', '.feather', '.sqlite', '.db',
        }
        return extension in binary_extensions
    
    def _has_compound_blacklisted_extension(self, filename: str) -> bool:
        compound_extensions = ['.tar.gz', '.tar.bz2', '.tar.xz', '.json.gz']
        filename_lower = filename.lower()
        return any(filename_lower.endswith(ext) for ext in compound_extensions)
    
    def _is_allowed_no_extension(self, filename: str) -> bool:
        return filename in self.ALLOWED_NO_EXTENSION
    
    def _is_binary_content(self, file_path: Path) -> bool:
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(8192)
            
            if b'\x00' in chunk:
                return True
            
            text_characters = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7f})
            non_text = len(chunk.translate(None, text_characters))
            
            if len(chunk) > 0 and (non_text / len(chunk)) > 0.30:
                return True
            
            return False
        except Exception:
            return True
    
    def get_blacklisted_files(self, repository_path: Path) -> List[str]:
        blacklisted = []
        
        for file_path in repository_path.rglob("*"):
            if not file_path.is_file():
                continue
            if self._is_in_venv(file_path):
                continue
            
            result = self.validate_file(file_path)
            if not result.is_allowed:
                try:
                    relative_path = file_path.relative_to(repository_path)
                    blacklisted.append(str(relative_path))
                except ValueError:
                    blacklisted.append(str(file_path))
        
        return blacklisted
    
    def get_binary_files(self, repository_path: Path) -> List[str]:
        binaries = []
        
        for file_path in repository_path.rglob("*"):
            if not file_path.is_file():
                continue
            if self._is_in_venv(file_path):
                continue
            
            if self._is_binary_content(file_path):
                try:
                    relative_path = file_path.relative_to(repository_path)
                    binaries.append(str(relative_path))
                except ValueError:
                    binaries.append(str(file_path))
        
        return binaries