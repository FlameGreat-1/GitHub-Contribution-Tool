import asyncio
import time
from github import GithubException

class CICD:
    def __init__(self, github_api, logger):
        self.github_api = github_api
        self.logger = logger
        self.max_wait_time = 3600  # 1 hour
        self.check_interval = 60  # 1 minute

    async def wait_for_ci(self, pr):
        try:
            self.logger.info(f"Waiting for CI checks on PR #{pr.number}")
            start_time = time.time()
            while time.time() - start_time < self.max_wait_time:
                status = await self.check_pr_status(pr)
                if status == 'success':
                    self.logger.info(f"CI checks passed for PR #{pr.number}")
                    return True
                elif status == 'failure':
                    self.logger.warning(f"CI checks failed for PR #{pr.number}")
                    return False
                await asyncio.sleep(self.check_interval)
            self.logger.warning(f"CI checks timed out for PR #{pr.number}")
            return False
        except GithubException as e:
            self.logger.error(f"Error waiting for CI: {str(e)}")
            raise

    async def check_pr_status(self, pr):
        try:
            self.logger.info(f"Checking status of PR #{pr.number}")
            status = await asyncio.to_thread(pr.get_commits().reversed[0].get_combined_status)
            self.logger.info(f"PR status checked successfully")
            return status.state
        except GithubException as e:
            self.logger.error(f"Failed to check PR status: {str(e)}")
            raise

    async def trigger_ci_job(self, repo, job_name):
        try:
            self.logger.info(f"Triggering CI job: {job_name}")
            workflow = await asyncio.to_thread(repo.get_workflow, job_name)
            await asyncio.to_thread(workflow.create_dispatch, repo.default_branch)
            self.logger.info(f"CI job triggered successfully")
        except GithubException as e:
            self.logger.error(f"Failed to trigger CI job: {str(e)}")
            raise

    async def get_ci_logs(self, repo, run_id):
        try:
            self.logger.info(f"Fetching CI logs for run ID: {run_id}")
            run = await asyncio.to_thread(repo.get_workflow_run, run_id)
            logs_url = await asyncio.to_thread(run.get_logs_url)
            self.logger.info(f"CI logs fetched successfully")
            return logs_url
        except GithubException as e:
            self.logger.error(f"Failed to fetch CI logs: {str(e)}")
            raise

    async def cancel_ci_job(self, repo, run_id):
        try:
            self.logger.info(f"Cancelling CI job with run ID: {run_id}")
            run = await asyncio.to_thread(repo.get_workflow_run, run_id)
            await asyncio.to_thread(run.cancel)
            self.logger.info(f"CI job cancelled successfully")
        except GithubException as e:
            self.logger.error(f"Failed to cancel CI job: {str(e)}")
            raise

    async def retry_failed_ci(self, pr):
        try:
            self.logger.info(f"Retrying failed CI for PR #{pr.number}")
            status = await self.check_pr_status(pr)
            if status == 'failure':
                await self.trigger_ci_job(pr.base.repo, 'CI')
                self.logger.info(f"CI job retriggered for PR #{pr.number}")
            else:
                self.logger.info(f"No need to retry CI for PR #{pr.number}")
        except GithubException as e:
            self.logger.error(f"Failed to retry CI: {str(e)}")
            raise
