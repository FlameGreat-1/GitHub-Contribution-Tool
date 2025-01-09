import asyncio
import argparse
import json
from config import Config
from git_operations import GitOperations
from github_api import GitHubAPI
from file_manager import FileManager
from pr_manager import PRManager
from ci_cd import CICD
from repo_health import RepoHealth
from dependency_manager import DependencyManager
from changelog_generator import ChangelogGenerator
from code_formatter import CodeFormatter
from documentation_updater import DocumentationUpdater
from async_operations import AsyncOperations
from undo_manager import UndoManager
from logger import AdvancedLogger
from rate_limiter import RateLimiter
from workspace_manager import WorkspaceManager
from security_manager import SecurityManager
from error_handler import ErrorHandler
from performance_monitor import PerformanceMonitor

class GitHubContributionTool:
    def __init__(self):
        self.config = Config()
        self.logger = AdvancedLogger("github_contribution_tool", "github_tool.log")
        self.error_handler = ErrorHandler(self.logger)
        self.performance_monitor = PerformanceMonitor(self.logger)
        self.security_manager = SecurityManager(self.logger)
        self.workspace_manager = WorkspaceManager(self.config.get("WORKSPACE_BASE_PATH"), self.logger, self.config)
        self.github_api = GitHubAPI(self.config, self.logger)
        self.git_ops = GitOperations(self.config, self.logger)
        self.file_manager = FileManager(self.config, self.logger)
        self.pr_manager = PRManager(self.github_api, self.logger)
        self.ci_cd = CICD(self.github_api, self.logger)
        self.repo_health = RepoHealth(self.github_api, self.logger)
        self.dep_manager = DependencyManager(self.logger)
        self.changelog_gen = ChangelogGenerator(self.logger)
        self.code_formatter = CodeFormatter(self.config, self.logger)
        self.doc_updater = DocumentationUpdater(self.logger)
        self.async_ops = AsyncOperations(self.logger)
        self.undo_manager = UndoManager(self.logger)
        self.rate_limiter = RateLimiter(self.github_api, self.logger)

    @performance_monitor.time_function
    async def run(self, args):
        try:
            async with self.workspace_manager:
                await self.rate_limiter.check_rate_limit()
                repo = await self.github_api.get_repo(args.repo)
                
                workspace_path = await self.workspace_manager.create_workspace(args.repo)
                self.logger.info(f"Created workspace at {workspace_path}")

                if args.fork:
                    forked_repo = await self.github_api.fork_repo(repo)
                    repo = forked_repo

                await self.git_ops.clone_repo(repo.clone_url, workspace_path)
                
                if args.branch:
                    await self.git_ops.create_branch(args.branch)

                if args.files:
                    for file_path, content in args.files.items():
                        full_path = os.path.join(workspace_path, file_path)
                        await self.file_manager.update_file(full_path, content)

                if args.format_code:
                    await self.code_formatter.format_code(workspace_path)

                if args.update_deps:
                    await self.dep_manager.update_dependencies(workspace_path)

                if args.update_docs:
                    await self.doc_updater.update_documentation(workspace_path)

                await self.git_ops.commit_changes(args.commit_message)
                await self.git_ops.push_changes(args.branch)

                if args.create_pr:
                    pr = await self.pr_manager.create_pull_request(
                        repo, args.branch, args.pr_title, args.pr_body
                    )
                    await self.ci_cd.wait_for_ci(pr)

                if args.generate_changelog:
                    await self.changelog_gen.generate_changelog(repo)

                await self.repo_health.check_health(repo)

                # Cleanup workspace
                await self.workspace_manager.clean_workspace(args.repo)

        except Exception as e:
            await self.error_handler.handle_error(e)
            await self.undo_manager.undo_last_operation()

    @error_handler.error_decorator
    def parse_args(self):
        parser = argparse.ArgumentParser(description="GitHub Contribution Tool")
        parser.add_argument("--repo", required=True, help="Repository name (owner/repo)")
        parser.add_argument("--fork", action="store_true", help="Fork the repository")
        parser.add_argument("--branch", help="Branch name to create")
        parser.add_argument("--files", type=json.loads, help="JSON string of file paths and contents to update")
        parser.add_argument("--format-code", action="store_true", help="Format the code")
        parser.add_argument("--update-deps", action="store_true", help="Update dependencies")
        parser.add_argument("--update-docs", action="store_true", help="Update documentation")
        parser.add_argument("--commit-message", required=True, help="Commit message")
        parser.add_argument("--create-pr", action="store_true", help="Create a pull request")
        parser.add_argument("--pr-title", help="Pull request title")
        parser.add_argument("--pr-body", help="Pull request body")
        parser.add_argument("--generate-changelog", action="store_true", help="Generate changelog")
        return parser.parse_args()

async def main():
    tool = GitHubContributionTool()
    args = tool.parse_args()
    await tool.run(args)

if __name__ == "__main__":
    asyncio.run(main())
