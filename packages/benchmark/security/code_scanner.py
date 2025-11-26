import ast
import re
from pathlib import Path
from typing import List, Set

from loguru import logger


class CodeScanner:
    VENV_INDICATORS = {'venv', '.venv', 'env', '.env', 'site-packages', '__pycache__', 'node_modules'}
    
    BASE64_PATTERNS = [
        r'exec\s*\(\s*__import__\s*\(\s*["\']base64["\']\s*\)',
        r'eval\s*\(\s*.*base64.*decode',
        r'exec\s*\(\s*.*base64.*decode',
        r'compile\s*\(\s*.*base64.*decode',
    ]
    
    OBFUSCATION_PATTERNS = [
        r'exec\s*\(\s*compile\s*\(',
        r'__import__\s*\(\s*["\']marshal["\']\s*\)',
        r'__import__\s*\(\s*["\']codecs["\']\s*\)\s*\.decode',
    ]

    def scan_repository(self, repo_path: Path) -> List[str]:
        issues = []
        
        python_files = self._get_python_files(repo_path)
        
        for py_file in python_files:
            file_issues = self._scan_python_file(py_file)
            issues.extend(file_issues)
        
        return issues

    def is_obfuscated(self, repo_path: Path) -> bool:
        python_files = self._get_python_files(repo_path)
        
        for py_file in python_files:
            content = py_file.read_text(errors='ignore')
            
            if self._has_base64_code_blocks(content):
                logger.warning("Base64 encoded code detected", extra={"file": str(py_file)})
                return True
            
            if self._has_obfuscation_patterns(content):
                logger.warning("Obfuscation pattern detected", extra={"file": str(py_file)})
                return True
            
            if self._is_minified(content):
                logger.warning("Minified code detected", extra={"file": str(py_file)})
                return True
            
            if self._has_suspicious_ast(py_file):
                logger.warning("Suspicious AST structure detected", extra={"file": str(py_file)})
                return True
        
        return False

    def _get_python_files(self, repo_path: Path) -> List[Path]:
        python_files = []
        
        for py_file in repo_path.rglob("*.py"):
            if not self._is_in_venv(py_file):
                python_files.append(py_file)
        
        return python_files

    def _is_in_venv(self, file_path: Path) -> bool:
        parts = file_path.parts
        return any(indicator in parts for indicator in self.VENV_INDICATORS)

    def _scan_python_file(self, file_path: Path) -> List[str]:
        issues = []
        
        try:
            content = file_path.read_text(errors='ignore')
        except Exception as e:
            issues.append(f"{file_path}: Failed to read file: {e}")
            return issues
        
        for pattern in self.BASE64_PATTERNS:
            if re.search(pattern, content):
                issues.append(f"{file_path}: Base64 execution pattern detected")
                break
        
        for pattern in self.OBFUSCATION_PATTERNS:
            if re.search(pattern, content):
                issues.append(f"{file_path}: Obfuscation pattern detected")
                break
        
        if self._is_minified(content):
            issues.append(f"{file_path}: Code appears to be minified")
        
        long_strings = re.findall(r'["\'][A-Za-z0-9+/=]{500,}["\']', content)
        if long_strings:
            issues.append(f"{file_path}: Long base64-like string detected")
        
        return issues

    def _has_base64_code_blocks(self, content: str) -> bool:
        for pattern in self.BASE64_PATTERNS:
            if re.search(pattern, content):
                return True
        
        long_base64_pattern = r'[A-Za-z0-9+/=]{500,}'
        matches = re.findall(long_base64_pattern, content)
        
        for match in matches:
            if len(match) > 1000:
                return True
        
        return False

    def _has_obfuscation_patterns(self, content: str) -> bool:
        for pattern in self.OBFUSCATION_PATTERNS:
            if re.search(pattern, content):
                return True
        return False

    def _is_minified(self, content: str) -> bool:
        lines = content.split('\n')
        
        if len(lines) < 3:
            return False
        
        non_empty_lines = [line for line in lines if line.strip()]
        
        if not non_empty_lines:
            return False
        
        avg_line_length = sum(len(line) for line in non_empty_lines) / len(non_empty_lines)
        
        if avg_line_length > 400:
            return True
        
        semicolon_count = content.count(';')
        if semicolon_count > len(non_empty_lines) * 3:
            return True
        
        return False

    def _has_suspicious_ast(self, file_path: Path) -> bool:
        try:
            content = file_path.read_text(errors='ignore')
            tree = ast.parse(content)
        except SyntaxError:
            return False
        except Exception:
            return False
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in ('exec', 'eval', 'compile'):
                        for arg in node.args:
                            if isinstance(arg, ast.Call):
                                if isinstance(arg.func, ast.Attribute):
                                    if arg.func.attr == 'decode':
                                        return True
        
        return False