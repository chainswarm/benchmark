#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
from loguru import logger
from chainswarm_core.observability import setup_logger

load_dotenv()


def main():
    parser = argparse.ArgumentParser(description='Run complete miner submission pipeline')
    parser.add_argument('--github-url', required=True, help='GitHub repository URL (HTTPS)')
    parser.add_argument('--hotkey', required=True, help='Miner hotkey')
    parser.add_argument('--image-type', required=True, choices=['analytics', 'ml'], help='Image type')
    
    args = parser.parse_args()
    
    setup_logger('miner-submission')
    
    logger.info("Starting miner submission pipeline", extra={
        "github_url": args.github_url,
        "hotkey": args.hotkey,
        "image_type": args.image_type
    })
    
    run_synchronous_pipeline(args)


def run_synchronous_pipeline(args):
    from packages.jobs.tasks.repository_clone_task import repository_clone_task
    from packages.jobs.tasks.code_analysis_task import code_analysis_task
    from packages.jobs.tasks.docker_build_task import docker_build_task
    from packages.jobs.tasks.container_run_task import container_run_task
    
    logger.info("Phase 1: Cloning repository")
    clone_result = repository_clone_task.apply(args=[
        args.github_url,
        args.hotkey,
        args.image_type
    ])
    
    clone_data = clone_result.get()
    
    if not clone_data.get('success'):
        logger.error("Repository clone failed", extra={"error": clone_data.get('error_message')})
        sys.exit(1)
    
    repository_path = clone_data.get('repository_path')
    logger.info("Repository cloned successfully", extra={"path": repository_path})
    
    logger.info("Phase 2: Running code analysis")
    analysis_result = code_analysis_task.apply(args=[
        repository_path,
        args.hotkey,
        args.image_type
    ])
    
    analysis_data = analysis_result.get()
    
    if analysis_data.get('status') != 'passed':
        logger.error("Code analysis failed", extra={
            "status": analysis_data.get('status'),
            "failure_reason": analysis_data.get('failure_reason'),
            "issues": analysis_data.get('all_issues', [])[:5]
        })
        sys.exit(1)
    
    logger.info("Code analysis passed", extra={
        "files_scanned": analysis_data.get('total_files_scanned'),
        "llm_files_analyzed": analysis_data.get('llm_files_analyzed')
    })
    
    logger.info("Phase 3: Building Docker image")
    build_result = docker_build_task.apply(args=[
        repository_path,
        args.hotkey,
        args.image_type
    ])
    
    build_data = build_result.get()
    
    if not build_data.get('success'):
        logger.error("Docker build failed", extra={"error": build_data.get('error_message')})
        sys.exit(1)
    
    image_tag = build_data.get('image_tag')
    logger.info("Docker image built successfully", extra={
        "image_tag": image_tag,
        "build_time": build_data.get('build_time_seconds')
    })
    
    logger.info("Phase 4: Running container")
    run_result = container_run_task.apply(args=[
        image_tag,
        args.hotkey,
        args.image_type
    ])
    
    run_data = run_result.get()
    
    if not run_data.get('success'):
        logger.error("Container run failed", extra={"error": run_data.get('error_message')})
        sys.exit(1)
    
    logger.info("Container run completed", extra={
        "execution_time": run_data.get('execution_time_seconds'),
        "exit_code": run_data.get('exit_code')
    })
    
    logger.info("Miner submission pipeline completed successfully", extra={
        "hotkey": args.hotkey,
        "image_type": args.image_type
    })


if __name__ == '__main__':
    main()