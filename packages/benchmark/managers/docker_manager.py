import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import docker
from docker.errors import BuildError, ContainerError, ImageNotFound
from loguru import logger

from packages.benchmark.models.results import ContainerResult


class DockerManager:
    def __init__(self):
        self.client = docker.from_env()
        self.max_execution_time = int(os.environ.get('BENCHMARK_MAX_EXECUTION_TIME', 3600))
        self.memory_limit = os.environ.get('BENCHMARK_MEMORY_LIMIT', '32g')

    def build_image(self, repo_path: Path, image_type: str, hotkey: str, commit_hash: str) -> str:
        """Build a Docker image with versioned tagging.
        
        Args:
            repo_path: Path to the repository containing the Dockerfile
            image_type: Type of image (e.g., 'analytics', 'ml')
            hotkey: Miner's hotkey identifier
            commit_hash: Short git commit hash (7 chars)
            
        Returns:
            The primary versioned image tag
        """
        build_date = datetime.utcnow().strftime('%Y%m%d')
        
        # All components lowercase for Docker compatibility
        image_name = f"{image_type.lower()}-pipeline/{hotkey.lower()}"
        version_tag = f"{commit_hash.lower()}-{build_date}"
        
        primary_tag = f"{image_name}:{version_tag}"
        latest_tag = f"{image_name}:latest"
        
        logger.info("Building Docker image", extra={
            "primary_tag": primary_tag,
            "latest_tag": latest_tag,
            "repo_path": str(repo_path)
        })
        
        try:
            image, build_logs = self.client.images.build(
                path=str(repo_path),
                dockerfile="ops/Dockerfile",
                tag=primary_tag,
                rm=True,
                forcerm=True,
                pull=True
            )
            
            for log in build_logs:
                if 'stream' in log:
                    logger.debug(log['stream'].strip())
            
            # Also tag as latest
            image.tag(image_name, tag='latest')
            
            logger.info("Docker image built successfully", extra={
                "primary_tag": primary_tag,
                "latest_tag": latest_tag
            })
            return primary_tag
            
        except BuildError as e:
            logger.error("Docker build failed", extra={"error": str(e)})
            raise RuntimeError(f"Docker build failed: {e}")

    def run_container(
        self,
        image_tag: str,
        data_mount: Path,
        miner_database: str,
        timeout: Optional[int] = None,
        network_mode: str = "none"
    ) -> ContainerResult:
        timeout = timeout or self.max_execution_time
        
        validator_host = os.environ['VALIDATOR_CH_HOST']
        validator_port = os.environ['VALIDATOR_CH_PORT']
        
        environment = {
            'CLICKHOUSE_HOST': validator_host,
            'CLICKHOUSE_PORT': validator_port,
            'CLICKHOUSE_DATABASE': miner_database,
        }
        
        volumes = {
            str(data_mount): {'bind': '/data', 'mode': 'ro'}
        }
        
        logger.info("Starting container", extra={
            "image_tag": image_tag,
            "database": miner_database,
            "timeout": timeout,
            "network_mode": network_mode
        })
        
        start_time = time.time()
        timed_out = False
        exit_code = -1
        logs = ""
        gpu_memory_peak = 0.0
        
        try:
            container = self.client.containers.run(
                image_tag,
                detach=True,
                network_mode=network_mode,
                mem_limit=self.memory_limit,
                read_only=True,
                tmpfs={'/tmp': 'rw,size=1g'},
                volumes=volumes,
                environment=environment,
                device_requests=[
                    docker.types.DeviceRequest(count=-1, capabilities=[['gpu']])
                ]
            )
            
            try:
                result = container.wait(timeout=timeout)
                exit_code = result['StatusCode']
            except Exception as wait_error:
                logger.warning("Container timeout", extra={"error": str(wait_error)})
                timed_out = True
                container.stop(timeout=10)
                exit_code = -1
            
            logs = container.logs().decode('utf-8', errors='ignore')
            
            stats = container.stats(stream=False)
            if 'memory_stats' in stats and 'max_usage' in stats['memory_stats']:
                gpu_memory_peak = stats['memory_stats']['max_usage'] / (1024 * 1024)
            
            container.remove(force=True)
            
        except ContainerError as e:
            logger.error("Container execution failed", extra={"error": str(e)})
            logs = str(e)
            exit_code = e.exit_status
        except ImageNotFound:
            raise RuntimeError(f"Image not found: {image_tag}")
        
        execution_time = time.time() - start_time
        
        logger.info("Container finished", extra={
            "image_tag": image_tag,
            "exit_code": exit_code,
            "execution_time": execution_time,
            "timed_out": timed_out
        })
        
        return ContainerResult(
            exit_code=exit_code,
            execution_time_seconds=execution_time,
            gpu_memory_peak_mb=gpu_memory_peak,
            logs=logs,
            timed_out=timed_out
        )

    def remove_image(self, image_tag: str) -> None:
        logger.info("Removing Docker image", extra={"image_tag": image_tag})
        try:
            self.client.images.remove(image_tag, force=True)
        except ImageNotFound:
            logger.warning("Image not found for removal", extra={"image_tag": image_tag})

    def list_benchmark_images(self, image_type: Optional[str] = None) -> List[str]:
        """List all benchmark images, optionally filtered by type.
        
        Args:
            image_type: Filter by image type ('analytics' or 'ml'). None for all.
            
        Returns:
            List of image tags matching the criteria
        """
        images = self.client.images.list()
        benchmark_images = []
        
        for image in images:
            for tag in image.tags:
                # Match new format: {type}-pipeline/{hotkey}:{version}
                if '-pipeline/' in tag:
                    if image_type is None:
                        benchmark_images.append(tag)
                    elif tag.startswith(f"{image_type.lower()}-pipeline/"):
                        benchmark_images.append(tag)
        
        return benchmark_images

    def image_exists(self, image_tag: str) -> bool:
        try:
            self.client.images.get(image_tag)
            return True
        except ImageNotFound:
            return False