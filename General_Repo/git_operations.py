import asyncio
import os
from git import Repo
from git.exc import GitCommandError

class GitOperations:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.repo = None

    async def clone_repo(self, repo_url, local_path):
        try:
            self.logger.info(f"Cloning repository from {repo_url} to {local_path}")
            self.repo = await asyncio.to_thread(Repo.clone_from, repo_url, local_path)
            self.logger.info("Repository cloned successfully")
        except GitCommandError as e:
            self.logger.error(f"Failed to clone repository: {str(e)}")
            raise

    async def create_branch(self, branch_name):
        try:
            self.logger.info(f"Creating new branch: {branch_name}")
            await asyncio.to_thread(self.repo.git.checkout, '-b', branch_name)
            self.logger.info(f"Branch '{branch_name}' created successfully")
        except GitCommandError as e:
            self.logger.error(f"Failed to create branch: {str(e)}")
            raise

    async def commit_changes(self, commit_message):
        try:
            self.logger.info("Committing changes")
            await asyncio.to_thread(self.repo.git.add, A=True)
            await asyncio.to_thread(self.repo.index.commit, commit_message)
            self.logger.info("Changes committed successfully")
        except GitCommandError as e:
            self.logger.error(f"Failed to commit changes: {str(e)}")
            raise

    async def push_changes(self, branch_name):
        try:
            self.logger.info(f"Pushing changes to remote branch: {branch_name}")
            await asyncio.to_thread(self.repo.git.push, 'origin', branch_name)
            self.logger.info("Changes pushed successfully")
        except GitCommandError as e:
            self.logger.error(f"Failed to push changes: {str(e)}")
            raise

    async def pull_changes(self, branch_name):
        try:
            self.logger.info(f"Pulling changes from remote branch: {branch_name}")
            await asyncio.to_thread(self.repo.git.pull, 'origin', branch_name)
            self.logger.info("Changes pulled successfully")
        except GitCommandError as e:
            self.logger.error(f"Failed to pull changes: {str(e)}")
            raise

    async def resolve_conflicts(self):
        try:
            self.logger.info("Attempting to resolve conflicts")
            conflicted_files = [item.a_path for item in self.repo.index.diff(None) if item.a_path]
            for file_path in conflicted_files:
                await asyncio.to_thread(self.repo.git.checkout, '--ours', file_path)
                await asyncio.to_thread(self.repo.git.add, file_path)
            self.logger.info("Conflicts resolved")
        except GitCommandError as e:
            self.logger.error(f"Failed to resolve conflicts: {str(e)}")
            raise

    async def undo_last_commit(self):
        try:
            self.logger.info("Undoing last commit")
            await asyncio.to_thread(self.repo.git.reset, '--soft', 'HEAD~1')
            self.logger.info("Last commit undone successfully")
        except GitCommandError as e:
            self.logger.error(f"Failed to undo last commit: {str(e)}")
            raise
