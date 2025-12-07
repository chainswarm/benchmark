import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

from loguru import logger

from packages.benchmark.models.baseline import Baseline, BaselineStatus
from packages.benchmark.models.miner import ImageType


class BaselineManager:
    """Manages baseline images - forking winning code and building baseline Docker images."""
    
    def __init__(self):
        self.github_org = os.environ.get('BASELINE_GITHUB_ORG', 'chainswarm')
        self.github_token = os.environ.get('GITHUB_TOKEN', '')
        self.repos_base_path = Path(os.environ.get('BENCHMARK_REPOS_PATH', '/var/benchmark/repos'))
    
    def get_baseline_repo_name(self, image_type: ImageType) -> str:
        """Get the baseline repository name for an image type."""
        if image_type == ImageType.ANALYTICS:
            return os.environ.get('BASELINE_ANALYTICS_REPO', 'baseline-analytics')
        else:
            return os.environ.get('BASELINE_ML_REPO', 'baseline-ml')
    
    def get_next_version(self, current_version: Optional[str]) -> str:
        """Generate next version string (e.g., v1.0.0 -> v1.1.0)."""
        if current_version is None:
            return 'v1.0.0'
        
        # Parse version v1.0.0 -> increment minor
        parts = current_version.lstrip('v').split('.')
        if len(parts) >= 2:
            major = int(parts[0])
            minor = int(parts[1]) + 1
            return f'v{major}.{minor}.0'
        return 'v1.0.0'
    
    def fork_winner_as_baseline(
        self,
        winner_hotkey: str,
        winner_repo_url: str,
        winner_commit_hash: str,
        image_type: ImageType,
        tournament_id: UUID,
        current_version: Optional[str] = None
    ) -> Baseline:
        """
        Fork the winning repository to become the new baseline.
        
        1. Clone the winner's repository
        2. Get the specific commit
        3. Push to baseline org repository
        4. Create new baseline record
        """
        new_version = self.get_next_version(current_version)
        baseline_repo_name = self.get_baseline_repo_name(image_type)
        baseline_repo_url = f"https://github.com/{self.github_org}/{baseline_repo_name}"
        
        logger.info("Forking winner as new baseline", extra={
            "winner_hotkey": winner_hotkey,
            "winner_repo": winner_repo_url,
            "winner_commit": winner_commit_hash,
            "new_version": new_version,
            "baseline_repo": baseline_repo_url
        })
        
        # Clone winner's repo
        clone_path = self.repos_base_path / f"baseline_fork_{image_type.value}"
        if clone_path.exists():
            import shutil
            shutil.rmtree(clone_path)
        
        self._run_git_command(['clone', winner_repo_url, str(clone_path)])
        
        # Checkout specific commit
        self._run_git_command(['checkout', winner_commit_hash], cwd=clone_path)
        
        # Configure remote for baseline org
        self._run_git_command(['remote', 'remove', 'origin'], cwd=clone_path, check=False)
        auth_url = f"https://{self.github_token}@github.com/{self.github_org}/{baseline_repo_name}.git"
        self._run_git_command(['remote', 'add', 'origin', auth_url], cwd=clone_path)
        
        # Create version tag
        self._run_git_command(['tag', new_version], cwd=clone_path)
        
        # Force push to baseline repo
        self._run_git_command(['push', '-f', 'origin', 'HEAD:main'], cwd=clone_path)
        self._run_git_command(['push', 'origin', new_version], cwd=clone_path)
        
        docker_image_tag = f"baseline_{image_type.value}_{new_version}"
        
        baseline = Baseline(
            baseline_id=uuid4(),
            image_type=image_type,
            version=new_version,
            github_repository=baseline_repo_url,
            commit_hash=winner_commit_hash,
            docker_image_tag=docker_image_tag,
            status=BaselineStatus.BUILDING,
            created_at=datetime.now(),
            originated_from_tournament_id=tournament_id,
            originated_from_hotkey=winner_hotkey,
            activated_at=None,
            deprecated_at=None
        )
        
        logger.info("Created new baseline from winner", extra={
            "baseline_id": str(baseline.baseline_id),
            "version": new_version,
            "docker_tag": docker_image_tag
        })
        
        return baseline
    
    def build_baseline_image(self, baseline: Baseline) -> str:
        """Build Docker image for the baseline."""
        from packages.benchmark.managers.docker_manager import DockerManager
        
        docker_manager = DockerManager()
        
        # Clone baseline repo
        clone_path = self.repos_base_path / f"baseline_{baseline.image_type.value}"
        if clone_path.exists():
            import shutil
            shutil.rmtree(clone_path)
        
        self._run_git_command(['clone', baseline.github_repository, str(clone_path)])
        self._run_git_command(['checkout', baseline.commit_hash], cwd=clone_path)
        
        # Build image
        image_tag = docker_manager.build_image(
            repo_path=clone_path,
            image_type=baseline.image_type.value,
            hotkey=f"baseline_{baseline.version}"
        )
        
        logger.info("Built baseline Docker image", extra={
            "baseline_id": str(baseline.baseline_id),
            "image_tag": image_tag
        })
        
        return image_tag
    
    def create_initial_baseline(self, image_type: ImageType, repo_url: str, commit_hash: str) -> Baseline:
        """Create the initial baseline (v1.0.0) when no baseline exists."""
        version = 'v1.0.0'
        docker_image_tag = f"baseline_{image_type.value}_{version}"
        
        baseline = Baseline(
            baseline_id=uuid4(),
            image_type=image_type,
            version=version,
            github_repository=repo_url,
            commit_hash=commit_hash,
            docker_image_tag=docker_image_tag,
            status=BaselineStatus.BUILDING,
            created_at=datetime.now(),
            originated_from_tournament_id=None,
            originated_from_hotkey=None,
            activated_at=None,
            deprecated_at=None
        )
        
        return baseline
    
    def _run_git_command(self, args: list, cwd: Path = None, check: bool = True) -> subprocess.CompletedProcess:
        """Run a git command."""
        cmd = ['git'] + args
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False
        )
        
        if check and result.returncode != 0:
            logger.error("Git command failed", extra={
                "command": ' '.join(cmd),
                "stderr": result.stderr
            })
            raise RuntimeError(f"Git command failed: {result.stderr}")
        
        return result