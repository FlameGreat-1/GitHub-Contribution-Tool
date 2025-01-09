import asyncio
from github import GithubException
from datetime import datetime, timedelta

class ChangelogGenerator:
    def __init__(self, github_api, logger):
        self.github_api = github_api
        self.logger = logger

    async def generate_changelog(self, repo, since=None, until=None):
        try:
            self.logger.info(f"Generating changelog for {repo.full_name}")
            if not since:
                since = datetime.now() - timedelta(days=30)  # Default to last 30 days
            if not until:
                until = datetime.now()

            commits = await self.get_commits(repo, since, until)
            prs = await self.get_merged_prs(repo, since, until)
            issues = await self.get_closed_issues(repo, since, until)

            changelog = self.format_changelog(commits, prs, issues, since, until)
            
            await self.update_changelog_file(repo, changelog)
            self.logger.info("Changelog generated and updated successfully")
            return changelog
        except GithubException as e:
            self.logger.error(f"Failed to generate changelog: {str(e)}")
            raise

    async def get_commits(self, repo, since, until):
        commits = await asyncio.to_thread(repo.get_commits, since=since, until=until)
        return [commit for commit in commits]

    async def get_merged_prs(self, repo, since, until):
        prs = await asyncio.to_thread(
            repo.get_pulls,
            state='closed',
            sort='updated',
            direction='desc'
        )
        return [pr for pr in prs if pr.merged and since <= pr.merged_at <= until]

    async def get_closed_issues(self, repo, since, until):
        issues = await asyncio.to_thread(
            repo.get_issues,
            state='closed',
            sort='updated',
            direction='desc'
        )
        return [issue for issue in issues if not issue.pull_request and since <= issue.closed_at <= until]

    def format_changelog(self, commits, prs, issues, since, until):
        changelog = f"# Changelog\n\n"
        changelog += f"## {since.date()} - {until.date()}\n\n"

        if prs:
            changelog += "### Merged Pull Requests\n\n"
            for pr in prs:
                changelog += f"- #{pr.number} {pr.title}\n"
            changelog += "\n"

        if issues:
            changelog += "### Closed Issues\n\n"
            for issue in issues:
                changelog += f"- #{issue.number} {issue.title}\n"
            changelog += "\n"

        if commits:
            changelog += "### Commits\n\n"
            for commit in commits:
                changelog += f"- {commit.sha[:7]} {commit.commit.message.split('\n')[0]}\n"

        return changelog

    async def update_changelog_file(self, repo, new_content):
        try:
            path = 'CHANGELOG.md'
            try:
                contents = await asyncio.to_thread(repo.get_contents, path)
                current_content = contents.decoded_content.decode()
                updated_content = new_content + "\n\n" + current_content
                await asyncio.to_thread(
                    repo.update_file,
                    path,
                    "Update CHANGELOG.md",
                    updated_content,
                    contents.sha
                )
            except GithubException:
                await asyncio.to_thread(
                    repo.create_file,
                    path,
                    "Create CHANGELOG.md",
                    new_content
                )
            self.logger.info(f"CHANGELOG.md updated in {repo.full_name}")
        except GithubException as e:
            self.logger.error(f"Failed to update CHANGELOG.md: {str(e)}")
            raise

    async def categorize_changes(self, prs):
        categories = {
            'feature': [],
            'bugfix': [],
            'documentation': [],
            'refactor': [],
            'other': []
        }
        for pr in prs:
            category = self.determine_pr_category(pr)
            categories[category].append(pr)
        return categories

    def determine_pr_category(self, pr):
        title_lower = pr.title.lower()
        if 'feat' in title_lower or 'feature' in title_lower:
            return 'feature'
        elif 'fix' in title_lower or 'bug' in title_lower:
            return 'bugfix'
        elif 'doc' in title_lower:
            return 'documentation'
        elif 'refactor' in title_lower:
            return 'refactor'
        else:
            return 'other'

    async def generate_release_notes(self, repo, tag_name, previous_tag_name=None):
        try:
            self.logger.info(f"Generating release notes for {repo.full_name} tag {tag_name}")
            if previous_tag_name:
                comparison = await asyncio.to_thread(repo.compare, previous_tag_name, tag_name)
                commits = comparison.commits
            else:
                commits = await asyncio.to_thread(repo.get_commits, sha=tag_name)

            prs = await self.get_prs_for_commits(repo, commits)
            categorized_prs = await self.categorize_changes(prs)

            notes = f"# Release {tag_name}\n\n"
            for category, category_prs in categorized_prs.items():
                if category_prs:
                    notes += f"## {category.capitalize()}\n\n"
                    for pr in category_prs:
                        notes += f"- #{pr.number} {pr.title}\n"
                    notes += "\n"

            self.logger.info("Release notes generated successfully")
            return notes
        except GithubException as e:
            self.logger.error(f"Failed to generate release notes: {str(e)}")
            raise

    async def get_prs_for_commits(self, repo, commits):
        prs = []
        for commit in commits:
            commit_prs = await asyncio.to_thread(commit.get_pulls)
            prs.extend([pr for pr in commit_prs])
        return list(set(prs))  # Remove duplicates
