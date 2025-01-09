import asyncio
from github import GithubException

class RepoHealth:
    def __init__(self, github_api, logger):
        self.github_api = github_api
        self.logger = logger
        self.required_files = ['README.md', 'LICENSE', 'CONTRIBUTING.md', '.gitignore']
        self.recommended_files = ['.github/CODEOWNERS', '.github/ISSUE_TEMPLATE.md', '.github/PULL_REQUEST_TEMPLATE.md']

    async def check_health(self, repo):
        try:
            self.logger.info(f"Checking health of repository: {repo.full_name}")
            health_report = {
                'required_files': await self.check_required_files(repo),
                'recommended_files': await self.check_recommended_files(repo),
                'branch_protection': await self.check_branch_protection(repo),
                'open_issues': await self.check_open_issues(repo),
                'recent_commits': await self.check_recent_commits(repo),
                'ci_status': await self.check_ci_status(repo),
            }
            self.logger.info(f"Health check completed for {repo.full_name}")
            return health_report
        except GithubException as e:
            self.logger.error(f"Failed to check repository health: {str(e)}")
            raise

    async def check_required_files(self, repo):
        missing_files = []
        for file in self.required_files:
            try:
                await asyncio.to_thread(repo.get_contents, file)
            except GithubException:
                missing_files.append(file)
        return {'present': len(missing_files) == 0, 'missing': missing_files}

    async def check_recommended_files(self, repo):
        missing_files = []
        for file in self.recommended_files:
            try:
                await asyncio.to_thread(repo.get_contents, file)
            except GithubException:
                missing_files.append(file)
        return {'present': len(missing_files) == 0, 'missing': missing_files}

    async def check_branch_protection(self, repo):
        try:
            branch = await asyncio.to_thread(repo.get_branch, repo.default_branch)
            protection = await asyncio.to_thread(branch.get_protection)
            return {
                'enabled': True,
                'require_pull_request_reviews': protection.required_pull_request_reviews is not None,
                'require_status_checks': protection.required_status_checks is not None,
                'enforce_admins': protection.enforce_admins,
            }
        except GithubException:
            return {'enabled': False}

    async def check_open_issues(self, repo):
        open_issues = await asyncio.to_thread(repo.get_issues, state='open')
        return {'count': open_issues.totalCount}

    async def check_recent_commits(self, repo):
        commits = await asyncio.to_thread(repo.get_commits)
        recent_commits = [commit for commit in commits[:10]]  # Get the 10 most recent commits
        return {'count': len(recent_commits), 'commits': recent_commits}

    async def check_ci_status(self, repo):
        try:
            branch = await asyncio.to_thread(repo.get_branch, repo.default_branch)
            status = await asyncio.to_thread(branch.commit.get_combined_status)
            return {'state': status.state, 'total_count': status.total_count}
        except GithubException:
            return {'state': 'unknown', 'total_count': 0}

    async def suggest_improvements(self, health_report):
        suggestions = []
        if not health_report['required_files']['present']:
            suggestions.append(f"Add missing required files: {', '.join(health_report['required_files']['missing'])}")
        if not health_report['recommended_files']['present']:
            suggestions.append(f"Consider adding recommended files: {', '.join(health_report['recommended_files']['missing'])}")
        if not health_report['branch_protection']['enabled']:
            suggestions.append("Enable branch protection for the default branch")
        if health_report['open_issues']['count'] > 10:
            suggestions.append("Consider addressing some open issues")
        if health_report['ci_status']['state'] != 'success':
            suggestions.append("Investigate and fix CI issues")
        return suggestions

    async def generate_health_report(self, repo):
        health_report = await self.check_health(repo)
        suggestions = await self.suggest_improvements(health_report)
        report = f"Health Report for {repo.full_name}:\n\n"
        report += f"Required Files: {'All present' if health_report['required_files']['present'] else 'Missing some'}\n"
        report += f"Recommended Files: {'All present' if health_report['recommended_files']['present'] else 'Missing some'}\n"
        report += f"Branch Protection: {'Enabled' if health_report['branch_protection']['enabled'] else 'Disabled'}\n"
        report += f"Open Issues: {health_report['open_issues']['count']}\n"
        report += f"Recent Commits: {health_report['recent_commits']['count']} in the last 10\n"
        report += f"CI Status: {health_report['ci_status']['state']}\n\n"
        if suggestions:
            report += "Suggestions for improvement:\n"
            for suggestion in suggestions:
                report += f"- {suggestion}\n"
        return report
