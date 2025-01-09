import asyncio
import time
from typing import Callable, Any
from github import GithubException

class RateLimiter:
    def __init__(self, github_api, logger):
        self.github_api = github_api
        self.logger = logger
        self.rate_limit = None
        self.rate_limit_reset = None

    async def check_rate_limit(self):
        try:
            self.rate_limit = await self.github_api.get_rate_limit()
            self.rate_limit_reset = self.rate_limit.core.reset.timestamp()
            self.logger.info(f"Rate limit: {self.rate_limit.core.remaining}/{self.rate_limit.core.limit}")
            if self.rate_limit.core.remaining == 0:
                wait_time = self.rate_limit_reset - time.time()
                self.logger.warning(f"Rate limit exceeded. Waiting for {wait_time:.2f} seconds.")
                await asyncio.sleep(wait_time)
        except GithubException as e:
            self.logger.error(f"Failed to check rate limit: {str(e)}")
            raise

    async def execute_with_rate_limit(self, func: Callable[..., Any], *args, **kwargs) -> Any:
        await self.check_rate_limit()
        try:
            result = await func(*args, **kwargs)
            return result
        except GithubException as e:
            if e.status == 403 and 'rate limit' in str(e).lower():
                self.logger.warning("Rate limit exceeded during execution. Retrying after reset.")
                await self.wait_for_reset()
                return await self.execute_with_rate_limit(func, *args, **kwargs)
            else:
                raise

    async def wait_for_reset(self):
        if self.rate_limit_reset:
            wait_time = max(self.rate_limit_reset - time.time(), 0)
            self.logger.info(f"Waiting for rate limit reset: {wait_time:.2f} seconds")
            await asyncio.sleep(wait_time)
        else:
            self.logger.warning("Rate limit reset time unknown. Waiting for 1 hour.")
            await asyncio.sleep(3600)

    async def execute_with_backoff(self, func: Callable[..., Any], *args, max_retries=5, base_delay=1, **kwargs) -> Any:
        for attempt in range(max_retries):
            try:
                return await self.execute_with_rate_limit(func, *args, **kwargs)
            except GithubException as e:
                if e.status == 403 and 'abuse' in str(e).lower():
                    delay = base_delay * (2 ** attempt)
                    self.logger.warning(f"Abuse detection mechanism triggered. Retrying in {delay} seconds.")
                    await asyncio.sleep(delay)
                else:
                    raise
        self.logger.error(f"Max retries ({max_retries}) exceeded.")
        raise GithubException(403, "Max retries exceeded due to abuse detection mechanism")

    async def bulk_operation_with_rate_limit(self, operations: list, chunk_size=10, delay=1):
        results = []
        for i in range(0, len(operations), chunk_size):
            chunk = operations[i:i+chunk_size]
            chunk_results = await asyncio.gather(*[self.execute_with_rate_limit(op) for op in chunk])
            results.extend(chunk_results)
            if i + chunk_size < len(operations):
                self.logger.info(f"Completed {i+chunk_size}/{len(operations)} operations. Waiting for {delay} seconds.")
                await asyncio.sleep(delay)
        return results

    async def monitor_rate_limit(self, interval=60):
        while True:
            await self.check_rate_limit()
            await asyncio.sleep(interval)

    async def get_rate_limit_status(self):
        await self.check_rate_limit()
        return {
            "remaining": self.rate_limit.core.remaining,
            "limit": self.rate_limit.core.limit,
            "reset_time": self.rate_limit_reset
        }

    async def execute_with_conditional_request(self, func: Callable[..., Any], etag=None, *args, **kwargs) -> Any:
        headers = {"If-None-Match": etag} if etag else {}
        try:
            result = await self.execute_with_rate_limit(func, *args, headers=headers, **kwargs)
            new_etag = result.headers.get('ETag')
            return result, new_etag
        except GithubException as e:
            if e.status == 304:  # Not Modified
                self.logger.info("Resource not modified since last request.")
                return None, etag
            else:
                raise

    async def parallel_rate_limited_execution(self, funcs: list, max_concurrent=5):
        semaphore = asyncio.Semaphore(max_concurrent)
        async def rate_limited_func(func):
            async with semaphore:
                return await self.execute_with_rate_limit(func)
        return await asyncio.gather(*[rate_limited_func(func) for func in funcs])

