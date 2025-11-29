import os
from pathlib import Path
from typing import List, Dict, Any, Optional

import httpx
from loguru import logger

from packages.benchmark.models.analysis import LLMAnalysisResult


class LLMCodeAnalyzer:
    DEFAULT_MODEL = "anthropic/claude-3-haiku"
    DEFAULT_MAX_TOKENS = 4096
    DEFAULT_TIMEOUT = 60.0
    
    ANALYSIS_PROMPT = """You are a security code analyst. Analyze the following code for security issues.

CRITICAL ISSUES TO DETECT:
1. Obfuscated code (base64 encoding, hex encoding, eval/exec with encoded strings)
2. Hidden cryptocurrency addresses (encoded, split, or obscured wallet addresses)
3. Encrypted or manipulated data that could hide malicious content
4. Network exfiltration attempts (hidden URLs, data sending mechanisms)
5. File system manipulation (unauthorized file access, hidden file operations)
6. Process injection or execution (subprocess calls with encoded commands)
7. Backdoors or reverse shells
8. Credential harvesting or keylogging
9. Mining or unauthorized resource usage
10. Anti-analysis techniques (debugger detection, VM detection)

For each file, analyze and report:
- OBFUSCATION: Any encoded/encrypted code sections
- HIDDEN_ADDRESSES: Any cryptocurrency addresses (Bitcoin, Ethereum, Polkadot)
- MALICIOUS_INTENT: Any code that appears designed to harm or steal
- SECURITY_RISK: General security concerns

Respond in JSON format:
{
    "overall_safe": true/false,
    "confidence": 0.0-1.0,
    "files": [
        {
            "file": "filename",
            "safe": true/false,
            "issues": ["list of issues found"],
            "severity": "HIGH|MEDIUM|LOW|NONE"
        }
    ],
    "summary": "brief summary of findings"
}

CODE TO ANALYZE:
"""
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None,
                 max_tokens: Optional[int] = None, timeout: Optional[float] = None):
        self.api_key = api_key or os.environ.get('OPENROUTER_API_KEY')
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY is required for LLM analysis")
        
        self.model = model or os.environ.get('LLM_MODEL', self.DEFAULT_MODEL)
        self.max_tokens = max_tokens or int(os.environ.get('LLM_MAX_TOKENS', str(self.DEFAULT_MAX_TOKENS)))
        self.timeout = timeout or float(os.environ.get('LLM_TIMEOUT', str(self.DEFAULT_TIMEOUT)))
        
        self.base_url = "https://openrouter.ai/api/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://chainswarm.io",
            "X-Title": "ChainSwarm Benchmark Security"
        }
    
    @property
    def is_enabled(self) -> bool:
        return True
    
    def analyze_repository(self, repository_path: Path, file_extensions: List[str] = None) -> List[LLMAnalysisResult]:
        
        if file_extensions is None:
            file_extensions = ['.py', '.sh', '.js', '.ts']
        
        code_files = []
        for extension in file_extensions:
            code_files.extend(repository_path.rglob(f"*{extension}"))
        
        code_files = [f for f in code_files if not self._is_excluded_path(f)]
        
        combined_content = ""
        file_map = {}
        
        for file_path in code_files[:20]:
            try:
                content = file_path.read_text(errors='ignore')
                if len(content) > 50000:
                    content = content[:50000] + "\n... [truncated]"
                
                relative_path = file_path.relative_to(repository_path)
                file_map[str(relative_path)] = file_path
                combined_content += f"\n\n=== FILE: {relative_path} ===\n{content}"
            except Exception as error:
                logger.warning("Failed to read file for LLM analysis", extra={
                    "file": str(file_path),
                    "error": str(error)
                })
        
        if len(combined_content) > 100000:
            combined_content = combined_content[:100000] + "\n... [truncated due to size]"
        
        if not combined_content:
            return []
        
        import time
        start_time = time.time()
        
        try:
            analysis_result = self._analyze_code(combined_content, f"repository:{repository_path.name}")
            elapsed_time = time.time() - start_time
            return self._convert_to_llm_results(analysis_result, file_map, repository_path, elapsed_time)
        except Exception as error:
            logger.error("LLM repository analysis failed", extra={"error": str(error)})
            return []
    
    def _analyze_code(self, code_content: str, filename: str = "unknown") -> Dict[str, Any]:
        prompt = f"{self.ANALYSIS_PROMPT}\n\nFile: {filename}\n```\n{code_content}\n```"
        
        try:
            response = self._make_request(prompt)
            return self._parse_response(response)
        except Exception as error:
            logger.error("LLM analysis failed", extra={"error": str(error), "filename": filename})
            return {
                "overall_safe": True,
                "confidence": 0.0,
                "files": [],
                "summary": f"Analysis failed: {str(error)}",
                "error": True
            }
    
    def _convert_to_llm_results(self, analysis_result: Dict[str, Any], file_map: Dict[str, Path], 
                                 repository_path: Path, elapsed_time: float) -> List[LLMAnalysisResult]:
        results = []
        
        file_analyses = analysis_result.get('files', [])
        overall_safe = analysis_result.get('overall_safe', True)
        overall_confidence = analysis_result.get('confidence', 0.0)
        
        for file_analysis in file_analyses:
            file_name = file_analysis.get('file', '')
            file_path = file_map.get(file_name)
            
            if not file_path:
                for key, path in file_map.items():
                    if path.name == file_name or key.endswith(file_name):
                        file_path = path
                        break
            
            if not file_path:
                file_path = repository_path / file_name
            
            result = LLMAnalysisResult(
                file_path=file_path,
                is_safe=file_analysis.get('safe', True),
                confidence=overall_confidence,
                issues=file_analysis.get('issues', []),
                raw_response=analysis_result.get('summary', ''),
                model_used=self.model,
                analysis_time_seconds=elapsed_time
            )
            results.append(result)
        
        if not file_analyses and not overall_safe:
            for file_path in file_map.values():
                result = LLMAnalysisResult(
                    file_path=file_path,
                    is_safe=False,
                    confidence=overall_confidence,
                    issues=[analysis_result.get('summary', 'Security issues detected')],
                    raw_response=analysis_result.get('summary', ''),
                    model_used=self.model,
                    analysis_time_seconds=elapsed_time
                )
                results.append(result)
        
        return results
    
    def analyze_suspicious_patterns(self, patterns: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not patterns:
            return {"verdict": "LEGITIMATE", "confidence": 1.0, "reasoning": "No patterns to analyze"}
        
        prompt = f"""Analyze these suspicious code patterns found during static analysis:

{self._format_patterns(patterns)}

Determine if these patterns indicate:
1. Intentional obfuscation to hide malicious code
2. Legitimate use (e.g., encoding for data transfer)
3. Security vulnerabilities that could be exploited

Respond in JSON:
{{
    "verdict": "MALICIOUS|SUSPICIOUS|LEGITIMATE",
    "confidence": 0.0-1.0,
    "reasoning": "explanation",
    "recommendations": ["list of actions"]
}}
"""
        
        try:
            response = self._make_request(prompt)
            return self._parse_response(response)
        except Exception as error:
            logger.error("Pattern analysis failed", extra={"error": str(error)})
            return {
                "verdict": "UNKNOWN",
                "confidence": 0.0,
                "reasoning": f"Analysis failed: {str(error)}",
                "error": True
            }
    
    def _make_request(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a security expert analyzing code for malicious content. Respond only in valid JSON."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": self.max_tokens,
            "temperature": 0.1
        }
        
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            
            data = response.json()
            return data['choices'][0]['message']['content']
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        import json
        
        response = response.strip()
        if response.startswith('```json'):
            response = response[7:]
        if response.startswith('```'):
            response = response[3:]
        if response.endswith('```'):
            response = response[:-3]
        
        try:
            return json.loads(response.strip())
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM response as JSON", extra={"response": response[:500]})
            return {
                "overall_safe": True,
                "confidence": 0.0,
                "files": [],
                "summary": "Failed to parse analysis response",
                "raw_response": response[:1000]
            }
    
    def _is_excluded_path(self, file_path: Path) -> bool:
        excluded_directories = {'venv', '.venv', 'env', '.env', 'node_modules', '__pycache__', 
                                '.git', '.pytest_cache', '.mypy_cache', 'dist', 'build', 'egg-info'}
        return any(part in excluded_directories for part in file_path.parts)
    
    def _format_patterns(self, patterns: List[Dict[str, Any]]) -> str:
        formatted = []
        for i, pattern in enumerate(patterns, 1):
            formatted.append(f"""
Pattern {i}:
- Type: {pattern.get('type', 'unknown')}
- File: {pattern.get('file', 'unknown')}
- Line: {pattern.get('line', 'unknown')}
- Content: {pattern.get('content', 'N/A')[:500]}
""")
        return "\n".join(formatted)


LLMAnalyzer = LLMCodeAnalyzer