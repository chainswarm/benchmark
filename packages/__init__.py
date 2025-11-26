import signal
import sys
import time
import uuid
import os
import threading
from typing import  Optional
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

_correlation_context = threading.local()

def generate_correlation_id() -> str:
    """Generate a unique correlation ID for request tracing."""
    return f"req_{uuid.uuid4().hex[:12]}"


def get_correlation_id() -> Optional[str]:
    """Get the current correlation ID from thread-local storage."""
    return getattr(_correlation_context, 'correlation_id', None)


def set_correlation_id(correlation_id: str):
    """Set the correlation ID in thread-local storage."""
    _correlation_context.correlation_id = correlation_id


def setup_logger(service_name: str):
    """
    Setup simple logger with auto-detection of service name.

    Args:
        service_name: Optional service name. If not provided, auto-detects from file path.
    """

    def patch_record(record):
        record["extra"]["service"] = service_name
        correlation_id = get_correlation_id()
        if correlation_id:
            record["extra"]["correlation_id"] = correlation_id
        record["extra"]["timestamp"] = time.time()
        return True

    # Try to get logs directory from environment variable first
    logs_dir = os.environ.get('LOGS_DIR')

    if not logs_dir:
        # Get the absolute path to the project root directory
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        logs_dir = os.path.join(project_root, "logs")

    # Ensure the directory exists and is writable
    try:
        os.makedirs(logs_dir, exist_ok=True)

        # Test write access by creating and removing a temporary file
        import tempfile
        test_file = os.path.join(logs_dir, f'.write_test_{service_name}_{int(time.time())}')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)

    except (OSError, PermissionError) as e:
        # Fallback to a temp directory if the intended logs directory isn't accessible
        import tempfile
        fallback_logs_dir = os.path.join(tempfile.gettempdir(), 'benchmark-logs')

        try:
            os.makedirs(fallback_logs_dir, exist_ok=True)
            # Test the fallback directory too
            test_file = os.path.join(fallback_logs_dir, f'.write_test_{service_name}_{int(time.time())}')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)

            logs_dir = fallback_logs_dir
            print(f"Warning: Using fallback logs directory {logs_dir} due to permission error: {e}")

        except (OSError, PermissionError):
            # Last resort: use current directory
            logs_dir = os.getcwd()
            print(f"Warning: Using current directory for logs due to permission errors. Original error: {e}")

    log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()

    logger.remove()

    # File logger with JSON serialization for Loki ingestion
    try:
        logger.add(
            os.path.join(logs_dir, f"{service_name}.log"),
            rotation="500 MB",
            level=log_level,
            filter=patch_record,
            serialize=True,
            format="{time} | {level} | {extra[service]} | {message} | {extra}"
        )
    except Exception as e:
        # If file logging fails completely, just proceed with console logging
        print(f"Warning: Could not set up file logging: {e}. Proceeding with console-only logging.")

    # Console logger with human-readable format
    console_format = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | <cyan>{extra[service]}</cyan> | {message} | <white>{extra}</white>"
    if get_correlation_id():
        console_format += " | <yellow>{extra[correlation_id]}</yellow>"

    logger.add(
        sys.stdout,
        format=console_format,
        level=log_level,
        filter=patch_record,
        enqueue=True,
        backtrace=False,
        diagnose=False,
    )

    logger.info(f"Logger configured with level: {log_level}")

    return service_name

terminate_event = threading.Event()

def signal_handler(sig, frame):
    logger.info(
        "Shutdown signal received",
        extra={
            "signal": sig,
        }
    )
    terminate_event.set()
    time.sleep(2)

def shutdown_handler(signum, frame):
    logger.info("Shutdown signal received. Waiting for current processing to complete...")
    terminate_event.set()

signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)