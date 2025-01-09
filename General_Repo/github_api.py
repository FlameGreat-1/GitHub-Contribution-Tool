import aiohttp
from github import Github
from github.GithubException import GithubException

class GitHubAPI:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.github = Github(self.config['github_token'])

    async def get_repo(self, repo_name):
        try:
            self.logger.info(f"Fetching repository: {repo_name}")
            repo = await asyncio.to_thread(self.github.get_repo, repo_name)
            self.logger.info(f"Repository fetched successfully")
            return repo
        except GithubException as e:
            self.logger.error(f"Failed to fetch repository: {str(e)}")
            raise

    async def fork_repo(self, repo):
        try:
            self.logger.info(f"Forking repository: {repo.full_name}")
            forked_repo = await asyncio.to_thread(self.github.get_user().create_fork, repo)
            self.logger.info(f"Repository forked successfully")
            return forked_repo
        except GithubException as e:
            self.logger.error(f"Failed to fork repository: {str(e)}")
            raise

    async def create_pull_request(self, repo, branch, title, body):
        try:
            self.logger.info(f"Creating pull request for branch: {branch}")
            pr = await asyncio.to_thread(
                repo.create_pull,
                title=title,
                body=body,
                head=branch,
                base=self.config['default_branch']
            )
            self.logger.info(f"Pull request created successfully: {pr.html_url}")
            return pr
        except GithubException as e:
            self.logger.error(f"Failed to create pull request: {str(e)}")
            raise

    async def get_pull_requests(self, repo, state='open'):
        try:
            self.logger.info(f"Fetching {state} pull requests")
            prs = await asyncio.to_thread(repo.get_pulls, state=state)
            self.logger.info(f"Pull requests fetched successfully")
            return list(prs)
        except GithubException as e:
            self.logger.error(f"Failed to fetch pull requests: {str(e)}")
            raise

    async def update_pull_request(self, pr, title=None, body=None, state=None):
        try:
            self.logger.info(f"Updating pull request: {pr.number}")
            if title:
                await asyncio.to_thread(pr.edit, title=title)
            if body:
                await asyncio.to_thread(pr.edit, body=body)
            if state:
                await asyncio.to_thread(pr.edit, state=state)
            self.logger.info(f"Pull request updated successfully")
        except GithubException as e:
            self.logger.error(f"Failed to update pull request: {str(e)}")
            raise

    async def get_rate_limit(self):
        try:
            self.logger.info("Fetching rate limit information")
            rate_limit = await asyncio.to_thread(self.github.get_rate_limit)
            self.logger.info("Rate limit information fetched successfully")
            return rate_limit
        except GithubException as e:
            self.logger.error(f"Failed to fetch rate limit information: {str(e)}")
            raise
