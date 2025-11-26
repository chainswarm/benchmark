import traceback
from functools import wraps
from loguru import logger

def log_errors(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(
                f"Error in {func.__qualname__}",
                error=e,
                traceback=traceback.format_exc(),
                exc_info=True,
                extra={
                    "function": func.__qualname__,
                    "args_count": len(args),
                    "kwargs_keys": list(kwargs.keys()) if kwargs else [],
                }
            )
            exit(1)
    return wrapper