import re
from pathlib import Path
from typing import List, Tuple

from loguru import logger

from packages.benchmark.models.analysis import AddressScanResult


class AddressScanner:
    VENV_INDICATORS = {'venv', '.venv', 'env', '.env', 'site-packages', '__pycache__', 'node_modules', '.git'}
    
    BITCOIN_P2PKH_PATTERN = r'\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b'
    BITCOIN_P2SH_PATTERN = r'\b3[a-km-zA-HJ-NP-Z1-9]{25,34}\b'
    BITCOIN_BECH32_PATTERN = r'\bbc1[a-z0-9]{39,59}\b'
    EVM_ADDRESS_PATTERN = r'\b0x[a-fA-F0-9]{40}\b'
    SUBSTRATE_ADDRESS_PATTERN = r'\b[1-9A-HJ-NP-Za-km-z]{47,48}\b'
    TX_HASH_EVM_PATTERN = r'\b0x[a-fA-F0-9]{64}\b'
    TX_HASH_GENERIC_PATTERN = r'\b[a-fA-F0-9]{64}\b'
    
    FALSE_POSITIVE_PATTERNS = [
        r'#[a-fA-F0-9]{6}\b',
        r'0x0{40}',
        r'0x[fF]{40}',
        r'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    ]
    
    SCANNABLE_EXTENSIONS = {
        '.py', '.pyi', '.json', '.yaml', '.yml', '.toml',
        '.md', '.rst', '.txt', '.sh', '.bash', '.sql',
        '.html', '.css', '.js', '.ts', '.jsx', '.tsx',
        '.cfg', '.ini', '.conf', '.env.example'
    }
    
    def __init__(self):
        self._compile_patterns()
    
    def _compile_patterns(self):
        self.bitcoin_p2pkh_regex = re.compile(self.BITCOIN_P2PKH_PATTERN)
        self.bitcoin_p2sh_regex = re.compile(self.BITCOIN_P2SH_PATTERN)
        self.bitcoin_bech32_regex = re.compile(self.BITCOIN_BECH32_PATTERN, re.IGNORECASE)
        self.evm_address_regex = re.compile(self.EVM_ADDRESS_PATTERN, re.IGNORECASE)
        self.substrate_address_regex = re.compile(self.SUBSTRATE_ADDRESS_PATTERN)
        self.tx_hash_evm_regex = re.compile(self.TX_HASH_EVM_PATTERN, re.IGNORECASE)
        self.tx_hash_generic_regex = re.compile(self.TX_HASH_GENERIC_PATTERN, re.IGNORECASE)
        self.false_positive_regexes = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.FALSE_POSITIVE_PATTERNS
        ]
    
    def scan_repository(self, repository_path: Path) -> List[AddressScanResult]:
        results = []
        
        for file_path in repository_path.rglob("*"):
            if not file_path.is_file():
                continue
            if self._is_in_venv(file_path):
                continue
            if file_path.suffix.lower() not in self.SCANNABLE_EXTENSIONS:
                if file_path.suffix != '':
                    continue
            
            result = self.scan_file(file_path)
            
            if result.has_addresses or result.has_hashes:
                results.append(result)
                logger.warning("Crypto addresses/hashes detected", extra={
                    "file": str(file_path),
                    "bitcoin_count": len(result.bitcoin_addresses),
                    "evm_count": len(result.evm_addresses),
                    "substrate_count": len(result.substrate_addresses),
                    "hash_count": len(result.transaction_hashes)
                })
        
        return results
    
    def scan_file(self, file_path: Path) -> AddressScanResult:
        result = AddressScanResult(file_path=file_path)
        
        try:
            content = file_path.read_text(errors='ignore')
        except Exception:
            return result
        
        bitcoin_addresses = self._find_bitcoin_addresses(content)
        result.bitcoin_addresses = self._filter_false_positives(bitcoin_addresses, content)
        
        evm_addresses = self._find_evm_addresses(content)
        result.evm_addresses = self._filter_false_positives(evm_addresses, content)
        
        substrate_addresses = self._find_substrate_addresses(content)
        result.substrate_addresses = self._filter_false_positives(substrate_addresses, content)
        
        tx_hashes = self._find_transaction_hashes(content)
        result.transaction_hashes = self._filter_false_positives(tx_hashes, content)
        
        return result
    
    def _find_bitcoin_addresses(self, content: str) -> List[str]:
        addresses = set()
        addresses.update(self.bitcoin_p2pkh_regex.findall(content))
        addresses.update(self.bitcoin_p2sh_regex.findall(content))
        addresses.update(self.bitcoin_bech32_regex.findall(content))
        
        validated = []
        for addr in addresses:
            if self._is_valid_bitcoin_address(addr):
                validated.append(addr)
        
        return validated
    
    def _find_evm_addresses(self, content: str) -> List[str]:
        addresses = set(self.evm_address_regex.findall(content))
        
        filtered = []
        for addr in addresses:
            addr_lower = addr.lower()
            if addr_lower == '0x' + '0' * 40:
                continue
            if addr_lower == '0x' + 'f' * 40:
                continue
            if addr_lower == '0x' + 'd' * 40:
                continue
            filtered.append(addr)
        
        return filtered
    
    def _find_substrate_addresses(self, content: str) -> List[str]:
        potential_addresses = self.substrate_address_regex.findall(content)
        
        validated = []
        for addr in potential_addresses:
            if self._is_likely_substrate_address(addr):
                validated.append(addr)
        
        return validated
    
    def _find_transaction_hashes(self, content: str) -> List[str]:
        hashes = set()
        hashes.update(self.tx_hash_evm_regex.findall(content))
        
        generic_matches = self.tx_hash_generic_regex.findall(content)
        for match in generic_matches:
            if f'0x{match}'.lower() in [h.lower() for h in hashes]:
                continue
            if self._looks_like_tx_hash(match, content):
                hashes.add(match)
        
        return list(hashes)
    
    def _is_valid_bitcoin_address(self, address: str) -> bool:
        if address.startswith('bc1'):
            return 42 <= len(address) <= 62
        elif address.startswith('1') or address.startswith('3'):
            return 26 <= len(address) <= 35
        return False
    
    def _is_likely_substrate_address(self, address: str) -> bool:
        if len(address) < 47 or len(address) > 48:
            return False
        first_char = address[0]
        if first_char in '15EGHJCF':
            return True
        return False
    
    def _looks_like_tx_hash(self, hash_str: str, content: str) -> bool:
        patterns = [
            f'tx.*{hash_str}',
            f'transaction.*{hash_str}',
            f'hash.*{hash_str}',
            f'{hash_str}.*tx',
            f'{hash_str}.*transaction',
        ]
        
        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        
        hash_assignment_pattern = rf'["\']?{hash_str}["\']?\s*[,\]}})]'
        if re.search(hash_assignment_pattern, content):
            return True
        
        return False
    
    def _filter_false_positives(self, items: List[str], content: str) -> List[str]:
        filtered = []
        
        for item in items:
            is_false_positive = False
            
            for regex in self.false_positive_regexes:
                if regex.search(item):
                    is_false_positive = True
                    break
            
            if not is_false_positive:
                filtered.append(item)
        
        return filtered
    
    def _is_in_venv(self, file_path: Path) -> bool:
        parts = file_path.parts
        return any(indicator in parts for indicator in self.VENV_INDICATORS)
    
    def has_crypto_data(self, repository_path: Path) -> Tuple[bool, List[str]]:
        results = self.scan_repository(repository_path)
        files_with_findings = [str(r.file_path) for r in results]
        return bool(results), files_with_findings