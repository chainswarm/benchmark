import os
from typing import Dict, List, Tuple

import pandas as pd
from clickhouse_connect import get_client
from clickhouse_connect.driver import Client
from loguru import logger

from packages.benchmark.models.results import NoveltyResult, RecallMetrics


class ValidationManager:
    def __init__(self):
        self.pipeline_clients: Dict[str, Client] = {}

    def validate_addresses_exist(self, addresses: List[str], network: str) -> bool:
        client = self._get_pipeline_client(network)
        
        if not addresses:
            return True
        
        query = """
        SELECT address
        FROM core_transfers
        WHERE from_address IN %(addresses)s OR to_address IN %(addresses)s
        GROUP BY address
        """
        
        result = client.query(query, parameters={'addresses': addresses})
        found_addresses = set()
        for row in result.result_rows:
            found_addresses.add(row[0])
        
        all_addresses = set(addresses)
        missing = all_addresses - found_addresses
        
        if missing:
            logger.warning("Missing addresses in pipeline", extra={
                "network": network,
                "missing_count": len(missing),
                "sample": list(missing)[:5]
            })
            return False
        
        return True

    def validate_connections_exist(self, connections: List[Tuple[str, str]], network: str) -> bool:
        client = self._get_pipeline_client(network)
        
        if not connections:
            return True
        
        from_addresses = [c[0] for c in connections]
        to_addresses = [c[1] for c in connections]
        
        query = """
        SELECT from_address, to_address
        FROM core_transfers
        WHERE (from_address, to_address) IN (
            SELECT from_address, to_address
            FROM (
                SELECT arrayJoin(%(from_addresses)s) as from_address,
                       arrayJoin(%(to_addresses)s) as to_address
            )
        )
        GROUP BY from_address, to_address
        """
        
        result = client.query(query, parameters={
            'from_addresses': from_addresses,
            'to_addresses': to_addresses
        })
        
        found_connections = set()
        for row in result.result_rows:
            found_connections.add((row[0], row[1]))
        
        all_connections = set(connections)
        missing = all_connections - found_connections
        
        if missing:
            logger.warning("Missing connections in pipeline", extra={
                "network": network,
                "missing_count": len(missing),
                "sample": list(missing)[:5]
            })
            return False
        
        return True

    def compare_synthetic_patterns(
        self,
        miner_patterns: List[dict],
        ground_truth: pd.DataFrame
    ) -> RecallMetrics:
        expected_pattern_ids = set(ground_truth['pattern_id'].unique())
        expected_count = len(expected_pattern_ids)
        
        found_pattern_ids = set()
        
        for pattern in miner_patterns:
            pattern_addresses = set(pattern.get('addresses', []))
            
            for _, gt_row in ground_truth.iterrows():
                gt_pattern_id = gt_row['pattern_id']
                gt_addresses = set(ground_truth[ground_truth['pattern_id'] == gt_pattern_id]['address'].tolist())
                
                overlap = len(pattern_addresses & gt_addresses)
                if overlap >= len(gt_addresses) * 0.8:
                    found_pattern_ids.add(gt_pattern_id)
        
        found_count = len(found_pattern_ids)
        recall = found_count / expected_count if expected_count > 0 else 0.0
        
        matched = list(found_pattern_ids)
        missed = list(expected_pattern_ids - found_pattern_ids)
        
        logger.info("Synthetic pattern comparison complete", extra={
            "expected": expected_count,
            "found": found_count,
            "recall": recall
        })
        
        return RecallMetrics(
            patterns_expected=expected_count,
            patterns_found=found_count,
            recall=recall,
            matched_pattern_ids=matched,
            missed_pattern_ids=missed
        )

    def validate_novelty_patterns(
        self,
        patterns: List[dict],
        network: str
    ) -> NoveltyResult:
        if not patterns:
            return NoveltyResult(
                patterns_reported=0,
                patterns_validated=0,
                addresses_valid=True,
                connections_valid=True,
                invalid_addresses=[],
                invalid_connections=[]
            )
        
        all_addresses = set()
        all_connections = []
        
        for pattern in patterns:
            addresses = pattern.get('addresses', [])
            all_addresses.update(addresses)
            
            transactions = pattern.get('transactions', [])
            for tx in transactions:
                if 'from_address' in tx and 'to_address' in tx:
                    all_connections.append((tx['from_address'], tx['to_address']))
        
        addresses_valid = self.validate_addresses_exist(list(all_addresses), network)
        connections_valid = self.validate_connections_exist(all_connections, network)
        
        invalid_addresses = []
        invalid_connections = []
        
        if not addresses_valid:
            invalid_addresses = self._find_invalid_addresses(list(all_addresses), network)
        
        if not connections_valid:
            invalid_connections = self._find_invalid_connections(all_connections, network)
        
        validated_count = 0
        for pattern in patterns:
            pattern_addresses = set(pattern.get('addresses', []))
            if pattern_addresses.issubset(all_addresses - set(invalid_addresses)):
                validated_count += 1
        
        logger.info("Novelty pattern validation complete", extra={
            "reported": len(patterns),
            "validated": validated_count,
            "addresses_valid": addresses_valid,
            "connections_valid": connections_valid
        })
        
        return NoveltyResult(
            patterns_reported=len(patterns),
            patterns_validated=validated_count,
            addresses_valid=addresses_valid,
            connections_valid=connections_valid,
            invalid_addresses=invalid_addresses,
            invalid_connections=invalid_connections
        )

    def _get_pipeline_client(self, network: str) -> Client:
        if network not in self.pipeline_clients:
            network_upper = network.upper()
            
            host = os.environ[f'{network_upper}_DATA_PIPELINE_CH_HOST']
            port = int(os.environ[f'{network_upper}_DATA_PIPELINE_CH_PORT'])
            database = os.environ[f'{network_upper}_DATA_PIPELINE_CH_DATABASE']
            
            self.pipeline_clients[network] = get_client(
                host=host,
                port=port,
                database=database
            )
        
        return self.pipeline_clients[network]

    def _find_invalid_addresses(self, addresses: List[str], network: str) -> List[str]:
        client = self._get_pipeline_client(network)
        
        query = """
        SELECT DISTINCT address
        FROM (
            SELECT from_address as address FROM core_transfers WHERE from_address IN %(addresses)s
            UNION ALL
            SELECT to_address as address FROM core_transfers WHERE to_address IN %(addresses)s
        )
        """
        
        result = client.query(query, parameters={'addresses': addresses})
        found = set(row[0] for row in result.result_rows)
        
        return [addr for addr in addresses if addr not in found]

    def _find_invalid_connections(
        self,
        connections: List[Tuple[str, str]],
        network: str
    ) -> List[Tuple[str, str]]:
        client = self._get_pipeline_client(network)
        
        if not connections:
            return []
        
        from_addresses = [c[0] for c in connections]
        to_addresses = [c[1] for c in connections]
        
        query = """
        SELECT from_address, to_address
        FROM core_transfers
        WHERE from_address IN %(from_addresses)s AND to_address IN %(to_addresses)s
        GROUP BY from_address, to_address
        """
        
        result = client.query(query, parameters={
            'from_addresses': from_addresses,
            'to_addresses': to_addresses
        })
        
        found = set((row[0], row[1]) for row in result.result_rows)
        
        return [conn for conn in connections if conn not in found]