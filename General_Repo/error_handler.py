import sys
import traceback
from functools import wraps

class ErrorHandler:
    def __init__(self, logger):
        self.logger = logger

    def handle_exception(self, exc_type, exc_value, exc_traceback):
        self.logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    def setup_global_error_handling(self):
        sys.excepthook = self.handle_exception

    def log_error(self, error_message, exc_info=True):
        self.logger.error(error_message, exc_info=exc_info)

    def error_decorator(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                self.log_error(f"Error in {func.__name__}: {str(e)}")
                raise
        return wrapper

    def async_error_decorator(self, func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                self.log_error(f"Error in async {func.__name__}: {str(e)}")
                raise
        return wrapper

    def custom_exception(self, exception_type, error_code, error_message):
        class CustomException(Exception):
            def __init__(self):
                self.error_code = error_code
                self.error_message = error_message

        CustomException.__name__ = exception_type
        return CustomException

    def handle_error_response(self, error):
        error_info = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "error_details": traceback.format_exc()
        }
        self.log_error(f"Error occurred: {error_info}")
        return error_info

    def retry_on_exception(self, max_retries=3, exceptions=(Exception,)):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                for attempt in range(max_retries):
                    try:
                        return func(*args, **kwargs)
                    except exceptions as e:
                        self.log_error(f"Attempt {attempt + 1} failed: {str(e)}")
                        if attempt == max_retries - 1:
                            raise
            return wrapper
        return decorator

    def async_retry_on_exception(self, max_retries=3, exceptions=(Exception,)):
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                for attempt in range(max_retries):
                    try:
                        return await func(*args, **kwargs)
                    except exceptions as e:
                        self.log_error(f"Attempt {attempt + 1} failed: {str(e)}")
                        if attempt == max_retries - 1:
                            raise
            return wrapper
        return decorator

    def error_boundary(self, fallback_function):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    self.log_error(f"Error in {func.__name__}: {str(e)}")
                    return fallback_function(*args, **kwargs)
            return wrapper
        return decorator

    def validate_input(self, validation_func):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                if not validation_func(*args, **kwargs):
                    raise ValueError("Invalid input")
                return func(*args, **kwargs)
            return wrapper
        return decorator

    def log_and_suppress(self, log_message):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    self.log_error(f"{log_message}: {str(e)}")
            return wrapper
        return decorator

    def error_notification(self, notification_func):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    self.log_error(f"Error in {func.__name__}: {str(e)}")
                    notification_func(str(e))
                    raise
            return wrapper
        return decorator

    def graceful_shutdown(self, cleanup_func):
        import atexit
        atexit.register(cleanup_func)
        self.logger.info("Registered graceful shutdown handler")

