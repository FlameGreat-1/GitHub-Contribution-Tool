import time
import psutil
import asyncio
from functools import wraps
from concurrent.futures import ThreadPoolExecutor

class PerformanceMonitor:
    def __init__(self, logger):
        self.logger = logger
        self.executor = ThreadPoolExecutor(max_workers=5)

    def time_function(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()
            execution_time = end_time - start_time
            self.logger.info(f"Function {func.__name__} took {execution_time:.4f} seconds to execute")
            return result
        return wrapper

    async def async_time_function(self, func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            result = await func(*args, **kwargs)
            end_time = time.time()
            execution_time = end_time - start_time
            self.logger.info(f"Async function {func.__name__} took {execution_time:.4f} seconds to execute")
            return result
        return wrapper

    def log_memory_usage(self):
        process = psutil.Process()
        memory_info = process.memory_info()
        self.logger.info(f"Memory usage: {memory_info.rss / 1024 / 1024:.2f} MB")

    def log_cpu_usage(self):
        cpu_percent = psutil.cpu_percent(interval=1)
        self.logger.info(f"CPU usage: {cpu_percent}%")

    async def monitor_resources(self, interval=60):
        while True:
            self.log_memory_usage()
            self.log_cpu_usage()
            await asyncio.sleep(interval)

    def profile_function(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            import cProfile
            import pstats
            import io
            pr = cProfile.Profile()
            pr.enable()
            result = func(*args, **kwargs)
            pr.disable()
            s = io.StringIO()
            ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
            ps.print_stats()
            self.logger.info(f"Profile for {func.__name__}:\n{s.getvalue()}")
            return result
        return wrapper

    async def async_profile_function(self, func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            import cProfile
            import pstats
            import io
            pr = cProfile.Profile()
            pr.enable()
            result = await func(*args, **kwargs)
            pr.disable()
            s = io.StringIO()
            ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
            ps.print_stats()
            self.logger.info(f"Profile for async {func.__name__}:\n{s.getvalue()}")
            return result
        return wrapper

    def measure_database_performance(self, query_func):
        @wraps(query_func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = query_func(*args, **kwargs)
            end_time = time.time()
            execution_time = end_time - start_time
            self.logger.info(f"Database query took {execution_time:.4f} seconds to execute")
            return result
        return wrapper

    async def async_measure_database_performance(self, query_func):
        @wraps(query_func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            result = await query_func(*args, **kwargs)
            end_time = time.time()
            execution_time = end_time - start_time
            self.logger.info(f"Async database query took {execution_time:.4f} seconds to execute")
            return result
        return wrapper

    def log_slow_operations(self, threshold):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                result = func(*args, **kwargs)
                end_time = time.time()
                execution_time = end_time - start_time
                if execution_time > threshold:
                    self.logger.warning(f"Slow operation detected: {func.__name__} took {execution_time:.4f} seconds")
                return result
            return wrapper
        return decorator

    async def async_log_slow_operations(self, threshold):
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                start_time = time.time()
                result = await func(*args, **kwargs)
                end_time = time.time()
                execution_time = end_time - start_time
                if execution_time > threshold:
                    self.logger.warning(f"Slow async operation detected: {func.__name__} took {execution_time:.4f} seconds")
                return result
            return wrapper
        return decorator

    def track_function_calls(self):
        call_count = {}
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                call_count[func.__name__] = call_count.get(func.__name__, 0) + 1
                self.logger.info(f"Function {func.__name__} has been called {call_count[func.__name__]} times")
                return func(*args, **kwargs)
            return wrapper
        return decorator

    def monitor_thread_count(self):
        thread_count = len(threading.enumerate())
        self.logger.info(f"Current thread count: {thread_count}")

    def log_system_load(self):
        load1, load5, load15 = psutil.getloadavg()
        self.logger.info(f"System load averages: 1 min: {load1}, 5 min: {load5}, 15 min: {load15}")

    async def performance_report(self, interval=3600):
        while True:
            self.log_memory_usage()
            self.log_cpu_usage()
            self.monitor_thread_count()
            self.log_system_load()
            await asyncio.sleep(interval)

    def optimize_function(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            loop = asyncio.get_event_loop()
            return loop.run_in_executor(self.executor, func, *args, **kwargs)
        return wrapper

