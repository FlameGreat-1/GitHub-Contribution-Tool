import asyncio
from typing import Callable, Any, List, Dict
from concurrent.futures import ThreadPoolExecutor
import time

class AsyncOperations:
    def __init__(self, logger):
        self.logger = logger
        self.executor = ThreadPoolExecutor(max_workers=10)

    async def run_in_parallel(self, tasks: List[Callable[..., Any]], *args) -> List[Any]:
        """
        Run multiple tasks in parallel.
        
        :param tasks: List of callable tasks to run in parallel
        :param args: Arguments to pass to each task
        :return: List of results from all tasks
        """
        self.logger.info(f"Running {len(tasks)} tasks in parallel")
        results = await asyncio.gather(*[self.run_task(task, *args) for task in tasks])
        self.logger.info("Parallel execution completed")
        return results

    async def run_task(self, task: Callable[..., Any], *args) -> Any:
        """
        Run a single task asynchronously.
        
        :param task: Callable task to run
        :param args: Arguments to pass to the task
        :return: Result of the task
        """
        try:
            result = await asyncio.to_thread(task, *args)
            return result
        except Exception as e:
            self.logger.error(f"Error in task {task.__name__}: {str(e)}")
            raise

    async def run_with_timeout(self, task: Callable[..., Any], timeout: float, *args) -> Any:
        """
        Run a task with a timeout.
        
        :param task: Callable task to run
        :param timeout: Timeout in seconds
        :param args: Arguments to pass to the task
        :return: Result of the task if completed within timeout, else None
        """
        try:
            return await asyncio.wait_for(self.run_task(task, *args), timeout=timeout)
        except asyncio.TimeoutError:
            self.logger.warning(f"Task {task.__name__} timed out after {timeout} seconds")
            return None

    async def run_with_retry(self, task: Callable[..., Any], max_retries: int, retry_delay: float, *args) -> Any:
        """
        Run a task with retry logic.
        
        :param task: Callable task to run
        :param max_retries: Maximum number of retries
        :param retry_delay: Delay between retries in seconds
        :param args: Arguments to pass to the task
        :return: Result of the task if successful, else raises last exception
        """
        for attempt in range(max_retries):
            try:
                return await self.run_task(task, *args)
            except Exception as e:
                if attempt == max_retries - 1:
                    self.logger.error(f"Task {task.__name__} failed after {max_retries} attempts: {str(e)}")
                    raise
                self.logger.warning(f"Task {task.__name__} failed (attempt {attempt + 1}/{max_retries}). Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)

    async def run_with_progress(self, tasks: List[Callable[..., Any]], *args) -> List[Any]:
        """
        Run tasks with a progress bar.
        
        :param tasks: List of callable tasks to run
        :param args: Arguments to pass to each task
        :return: List of results from all tasks
        """
        total_tasks = len(tasks)
        completed_tasks = 0
        results = []

        for task in tasks:
            result = await self.run_task(task, *args)
            results.append(result)
            completed_tasks += 1
            self.update_progress_bar(completed_tasks, total_tasks)

        print()  # New line after progress bar
        return results

    def update_progress_bar(self, completed: int, total: int):
        """
        Update and display a progress bar.
        
        :param completed: Number of completed tasks
        :param total: Total number of tasks
        """
        percent = (completed / total) * 100
        bar_length = 50
        filled_length = int(bar_length * completed // total)
        bar = '█' * filled_length + '-' * (bar_length - filled_length)
        print(f'\rProgress: |{bar}| {percent:.1f}% Complete', end='', flush=True)

    async def run_with_rate_limit(self, tasks: List[Callable[..., Any]], rate_limit: int, time_period: float, *args) -> List[Any]:
        """
        Run tasks with a rate limit.
        
        :param tasks: List of callable tasks to run
        :param rate_limit: Maximum number of tasks to run in the given time period
        :param time_period: Time period for the rate limit in seconds
        :param args: Arguments to pass to each task
        :return: List of results from all tasks
        """
        results = []
        for i in range(0, len(tasks), rate_limit):
            batch = tasks[i:i+rate_limit]
            batch_results = await self.run_in_parallel(batch, *args)
            results.extend(batch_results)
            if i + rate_limit < len(tasks):
                self.logger.info(f"Rate limit reached. Waiting for {time_period} seconds before next batch.")
                await asyncio.sleep(time_period)
        return results

    async def run_with_dependency_graph(self, tasks: Dict[str, Callable[..., Any]], dependencies: Dict[str, List[str]], *args) -> Dict[str, Any]:
        """
        Run tasks based on a dependency graph.
        
        :param tasks: Dictionary of tasks with task names as keys and callable tasks as values
        :param dependencies: Dictionary representing the dependency graph (task name -> list of dependent task names)
        :param args: Arguments to pass to each task
        :return: Dictionary of results with task names as keys
        """
        results = {}
        in_progress = set()

        async def run_task_with_deps(task_name):
            if task_name in results:
                return results[task_name]
            if task_name in in_progress:
                raise ValueError(f"Circular dependency detected for task {task_name}")
            
            in_progress.add(task_name)
            deps = dependencies.get(task_name, [])
            for dep in deps:
                await run_task_with_deps(dep)
            
            task = tasks[task_name]
            result = await self.run_task(task, *args)
            results[task_name] = result
            in_progress.remove(task_name)
            return result

        for task_name in tasks:
            await run_task_with_deps(task_name)

        return results

    async def run_with_priority(self, tasks: List[Dict[str, Any]], *args) -> List[Any]:
        """
        Run tasks based on priority.
        
        :param tasks: List of dictionaries, each containing 'task' (callable) and 'priority' (int) keys
        :param args: Arguments to pass to each task
        :return: List of results from all tasks
        """
        sorted_tasks = sorted(tasks, key=lambda x: x['priority'], reverse=True)
        results = []
        for task_info in sorted_tasks:
            result = await self.run_task(task_info['task'], *args)
            results.append(result)
        return results

    async def run_with_resource_management(self, tasks: List[Callable[..., Any]], max_concurrent: int, *args) -> List[Any]:
        """
        Run tasks with a limit on concurrent executions.
        
        :param tasks: List of callable tasks to run
        :param max_concurrent: Maximum number of tasks to run concurrently
        :param args: Arguments to pass to each task
        :return: List of results from all tasks
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        async def run_with_semaphore(task):
            async with semaphore:
                return await self.run_task(task, *args)
        return await asyncio.gather(*[run_with_semaphore(task) for task in tasks])
