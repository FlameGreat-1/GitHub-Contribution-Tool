
import asyncio
from github import GithubException
import re
from collections import Counter
from datetime import datetime, timedelta


class PRManager:
    def __init__(self, github_api, logger):
        self.github_api = github_api
        self.logger = logger

    async def create_pull_request(self, repo, branch, title, body):
        try:
            self.logger.info(f"Creating pull request for branch: {branch}")
            pr = await self.github_api.create_pull_request(repo, branch, title, body)
            await self.request_reviewers(pr)
            await self.add_labels(pr)
            self.logger.info(f"Pull request created successfully: {pr.html_url}")
            return pr
        except GithubException as e:
            self.logger.error(f"Failed to create pull request: {str(e)}")
            raise

    async def request_reviewers(self, pr):
        try:
            self.logger.info(f"Requesting reviewers for PR #{pr.number}")
            reviewers = await self.get_suggested_reviewers(pr)
            await asyncio.to_thread(pr.create_review_request, reviewers=reviewers)
            self.logger.info(f"Reviewers requested successfully")
        except GithubException as e:
            self.logger.error(f"Failed to request reviewers: {str(e)}")

    async def get_suggested_reviewers(self, pr):
        try:
            self.logger.info(f"Suggesting reviewers for PR #{pr.number}")
            files_changed = await asyncio.to_thread(pr.get_files)
            commit_authors = await self.get_commit_authors(pr)
            
            # Get contributors who have worked on the changed files
            file_experts = await self.get_file_experts(pr.base.repo, [f.filename for f in files_changed])
            
            # Combine and weight the potential reviewers
            potential_reviewers = Counter(commit_authors + file_experts)
            
            # Remove the PR author from potential reviewers
            potential_reviewers.pop(pr.user.login, None)
            
            # Get the top 3 potential reviewers
            suggested_reviewers = [reviewer for reviewer, _ in potential_reviewers.most_common(3)]
            
            self.logger.info(f"Suggested reviewers: {', '.join(suggested_reviewers)}")
            return suggested_reviewers
        except GithubException as e:
            self.logger.error(f"Failed to suggest reviewers: {str(e)}")
            return []

    async def get_commit_authors(self, pr):
        commits = await asyncio.to_thread(pr.get_commits)
        return [commit.author.login for commit in commits if commit.author]

    async def get_file_experts(self, repo, filenames):
        experts = []
        for filename in filenames:
            try:
                commits = await asyncio.to_thread(repo.get_commits, path=filename)
                authors = [commit.author.login for commit in commits if commit.author]
                experts.extend(authors[:5])  # Consider the last 5 authors of each file
            except GithubException:
                continue
        return experts

    async def get_suggested_labels(self, pr):
        try:
            self.logger.info(f"Suggesting labels for PR #{pr.number}")
            labels = set()
            
            # Check the files changed
            files_changed = await asyncio.to_thread(pr.get_files)
            for file in files_changed:
                if file.filename.endswith('.py'):
                    labels.add('python')
                elif file.filename.endswith('.js'):
                    labels.add('javascript')
                elif file.filename.endswith('.html'):
                    labels.add('html')
                elif file.filename.endswith('.css'):
                    labels.add('css')
            
            # Check the PR title and body for keywords
            title_body = pr.title + ' ' + pr.body
            if re.search(r'\bfix(es|ed)?\b', title_body, re.IGNORECASE):
                labels.add('bug')
            if re.search(r'\bfeature\b', title_body, re.IGNORECASE):
                labels.add('enhancement')
            if re.search(r'\bdocumentation\b', title_body, re.IGNORECASE):
                labels.add('documentation')
            
            # Check the size of the PR
            if sum(f.changes for f in files_changed) > 500:
                labels.add('large-pr')
            
            # Always add 'needs-review' label
            labels.add('needs-review')
            
            self.logger.info(f"Suggested labels: {', '.join(labels)}")
            return list(labels)
        except GithubException as e:
            self.logger.error(f"Failed to suggest labels: {str(e)}")
            return ['needs-review']


    async def add_labels(self, pr):
        try:
            self.logger.info(f"Adding labels to PR #{pr.number}")
            labels = await self.get_suggested_labels(pr)
            await asyncio.to_thread(pr.add_to_labels, *labels)
            self.logger.info(f"Labels added successfully")
        except GithubException as e:
            self.logger.error(f"Failed to add labels: {str(e)}")

    async def list_pull_requests(self, repo, state='open'):
        try:
            self.logger.info(f"Listing {state} pull requests")
            prs = await self.github_api.get_pull_requests(repo, state)
            self.logger.info(f"Pull requests listed successfully")
            return prs
        except GithubException as e:
            self.logger.error(f"Failed to list pull requests: {str(e)}")
            raise

    async def update_pull_request(self, pr, title=None, body=None, state=None):
        try:
            self.logger.info(f"Updating PR #{pr.number}")
            await self.github_api.update_pull_request(pr, title, body, state)
            self.logger.info(f"Pull request updated successfully")
        except GithubException as e:
            self.logger.error(f"Failed to update pull request: {str(e)}")
            raise

    async def merge_pull_request(self, pr, commit_message=None):
        try:
            self.logger.info(f"Merging PR #{pr.number}")
            await asyncio.to_thread(pr.merge, commit_message=commit_message)
            self.logger.info(f"Pull request merged successfully")
        except GithubException as e:
            self.logger.error(f"Failed to merge pull request: {str(e)}")
            raise

    async def handle_review_comments(self, pr):
        try:
            self.logger.info(f"Handling review comments for PR #{pr.number}")
            comments = await asyncio.to_thread(pr.get_review_comments)
            for comment in comments:
                await self.process_review_comment(pr, comment)
            self.logger.info(f"Review comments handled successfully")
        except GithubException as e:
            self.logger.error(f"Failed to handle review comments: {str(e)}")
            raise

    async def process_review_comment(self, pr, comment):
        try:
            self.logger.info(f"Processing review comment {comment.id} for PR #{pr.number}")
            
            # Check if the comment is asking for changes
            if re.search(r'please\s+change', comment.body, re.IGNORECASE):
                await self.request_changes(pr, comment)
            
            # Check if the comment is approving
            elif re.search(r'lgtm|looks\s+good\s+to\s+me', comment.body, re.IGNORECASE):
                await self.approve_pr(pr, comment)
            
            # Check if the comment is asking a question
            elif '?' in comment.body:
                await self.notify_author_of_question(pr, comment)
            
            # Check if the comment is mentioning someone
            mentions = re.findall(r'@(\w+)', comment.body)
            if mentions:
                await self.notify_mentioned_users(pr, comment, mentions)
            
            self.logger.info(f"Processed review comment {comment.id}")
        except GithubException as e:
            self.logger.error(f"Failed to process review comment: {str(e)}")

    async def request_changes(self, pr, comment):
        await asyncio.to_thread(pr.create_review, body="Changes requested based on review comments.", event="REQUEST_CHANGES")
        self.logger.info(f"Requested changes for PR #{pr.number} based on comment {comment.id}")

    async def approve_pr(self, pr, comment):
        await asyncio.to_thread(pr.create_review, body="Approving based on review comments.", event="APPROVE")
        self.logger.info(f"Approved PR #{pr.number} based on comment {comment.id}")

    async def notify_author_of_question(self, pr, comment):
        issue_comment = f"@{pr.user.login} A question has been asked in a review comment: {comment.html_url}"
        await asyncio.to_thread(pr.create_issue_comment, issue_comment)
        self.logger.info(f"Notified author of question in PR #{pr.number}, comment {comment.id}")

    async def notify_mentioned_users(self, pr, comment, mentions):
        for user in mentions:
            issue_comment = f"@{user} You were mentioned in a review comment: {comment.html_url}"
            await asyncio.to_thread(pr.create_issue_comment, issue_comment)
        self.logger.info(f"Notified mentioned users in PR #{pr.number}, comment {comment.id}")

    async def check_pr_status(self, pr):
        try:
            self.logger.info(f"Checking status of PR #{pr.number}")
            status = await asyncio.to_thread(pr.get_commits().reversed[0].get_combined_status)
            self.logger.info(f"PR status checked successfully")
            return status.state
        except GithubException as e:
            self.logger.error(f"Failed to check PR status: {str(e)}")
            raise
