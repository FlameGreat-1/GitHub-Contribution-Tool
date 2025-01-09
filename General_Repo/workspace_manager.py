import os
import shutil
import tempfile
import asyncio
import aiofiles
import hashlib
from datetime import datetime
from typing import List, Dict, Optional

class WorkspaceError(Exception):
    """Custom exception for workspace-related errors."""
    pass

class WorkspaceManager:
    def __init__(self, base_path: str, logger, config):
        self.base_path = os.path.abspath(base_path)
        self.logger = logger
        self.config = config
        self.active_workspaces: Dict[str, str] = {}
        self.temp_dirs: List[str] = []

    async def initialize(self):
        """Initialize the workspace manager."""
        if not os.path.exists(self.base_path):
            try:
                os.makedirs(self.base_path)
                self.logger.info(f"Created base workspace directory: {self.base_path}")
            except OSError as e:
                raise WorkspaceError(f"Failed to create base workspace directory: {e}")

    async def create_workspace(self, repo_name: str) -> str:
        """Create a new workspace for a repository."""
        workspace_path = os.path.join(self.base_path, self._sanitize_name(repo_name))
        try:
            os.makedirs(workspace_path, exist_ok=True)
            self.active_workspaces[repo_name] = workspace_path
            self.logger.info(f"Created workspace for {repo_name} at {workspace_path}")
            return workspace_path
        except OSError as e:
            raise WorkspaceError(f"Failed to create workspace for {repo_name}: {e}")

    async def get_workspace(self, repo_name: str) -> str:
        """Get the path of an existing workspace."""
        if repo_name not in self.active_workspaces:
            raise WorkspaceError(f"No active workspace found for {repo_name}")
        return self.active_workspaces[repo_name]

    async def clean_workspace(self, repo_name: str):
        """Clean up a workspace, removing all files and directories."""
        if repo_name not in self.active_workspaces:
            raise WorkspaceError(f"No active workspace found for {repo_name}")
        
        workspace_path = self.active_workspaces[repo_name]
        try:
            for root, dirs, files in os.walk(workspace_path, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))
            self.logger.info(f"Cleaned workspace for {repo_name}")
        except OSError as e:
            raise WorkspaceError(f"Failed to clean workspace for {repo_name}: {e}")

    async def delete_workspace(self, repo_name: str):
        """Delete a workspace entirely."""
        if repo_name not in self.active_workspaces:
            raise WorkspaceError(f"No active workspace found for {repo_name}")
        
        workspace_path = self.active_workspaces[repo_name]
        try:
            shutil.rmtree(workspace_path)
            del self.active_workspaces[repo_name]
            self.logger.info(f"Deleted workspace for {repo_name}")
        except OSError as e:
            raise WorkspaceError(f"Failed to delete workspace for {repo_name}: {e}")

    async def create_temp_directory(self) -> str:
        """Create a temporary directory within the workspace."""
        try:
            temp_dir = tempfile.mkdtemp(dir=self.base_path)
            self.temp_dirs.append(temp_dir)
            self.logger.info(f"Created temporary directory: {temp_dir}")
            return temp_dir
        except OSError as e:
            raise WorkspaceError(f"Failed to create temporary directory: {e}")

    async def cleanup_temp_directories(self):
        """Clean up all temporary directories."""
        for temp_dir in self.temp_dirs:
            try:
                shutil.rmtree(temp_dir)
                self.logger.info(f"Cleaned up temporary directory: {temp_dir}")
            except OSError as e:
                self.logger.error(f"Failed to clean up temporary directory {temp_dir}: {e}")
        self.temp_dirs.clear()

    async def list_workspaces(self) -> List[str]:
        """List all active workspaces."""
        return list(self.active_workspaces.keys())

    async def workspace_exists(self, repo_name: str) -> bool:
        """Check if a workspace exists for a given repository."""
        return repo_name in self.active_workspaces

    async def get_workspace_size(self, repo_name: str) -> int:
        """Get the size of a workspace in bytes."""
        if repo_name not in self.active_workspaces:
            raise WorkspaceError(f"No active workspace found for {repo_name}")
        
        workspace_path = self.active_workspaces[repo_name]
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(workspace_path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                total_size += os.path.getsize(fp)
        return total_size

    async def backup_workspace(self, repo_name: str) -> str:
        """Create a backup of a workspace."""
        if repo_name not in self.active_workspaces:
            raise WorkspaceError(f"No active workspace found for {repo_name}")
        
        workspace_path = self.active_workspaces[repo_name]
        backup_name = f"{repo_name}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup_path = os.path.join(self.base_path, backup_name)
        
        try:
            shutil.copytree(workspace_path, backup_path)
            self.logger.info(f"Created backup of {repo_name} workspace at {backup_path}")
            return backup_path
        except OSError as e:
            raise WorkspaceError(f"Failed to create backup of {repo_name} workspace: {e}")

    async def restore_workspace(self, repo_name: str, backup_path: str):
        """Restore a workspace from a backup."""
        if not os.path.exists(backup_path):
            raise WorkspaceError(f"Backup path does not exist: {backup_path}")
        
        workspace_path = os.path.join(self.base_path, self._sanitize_name(repo_name))
        try:
            if os.path.exists(workspace_path):
                shutil.rmtree(workspace_path)
            shutil.copytree(backup_path, workspace_path)
            self.active_workspaces[repo_name] = workspace_path
            self.logger.info(f"Restored {repo_name} workspace from backup at {backup_path}")
        except OSError as e:
            raise WorkspaceError(f"Failed to restore {repo_name} workspace from backup: {e}")

    async def get_file_hash(self, repo_name: str, file_path: str) -> str:
        """Get the SHA-256 hash of a file in the workspace."""
        if repo_name not in self.active_workspaces:
            raise WorkspaceError(f"No active workspace found for {repo_name}")
        
        full_path = os.path.join(self.active_workspaces[repo_name], file_path)
        if not os.path.exists(full_path):
            raise WorkspaceError(f"File not found: {full_path}")
        
        try:
            async with aiofiles.open(full_path, 'rb') as file:
                contents = await file.read()
                return hashlib.sha256(contents).hexdigest()
        except IOError as e:
            raise WorkspaceError(f"Failed to read file {full_path}: {e}")

    async def find_files(self, repo_name: str, pattern: str) -> List[str]:
        """Find files in the workspace matching a given pattern."""
        if repo_name not in self.active_workspaces:
            raise WorkspaceError(f"No active workspace found for {repo_name}")
        
        workspace_path = self.active_workspaces[repo_name]
        matching_files = []
        for root, dirs, files in os.walk(workspace_path):
            for filename in files:
                if filename.endswith(pattern):
                    matching_files.append(os.path.join(root, filename))
        return matching_files

    def _sanitize_name(self, name: str) -> str:
        """Sanitize a name for use as a directory name."""
        return "".join(c for c in name if c.isalnum() or c in ['-', '_']).rstrip()

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup_temp_directories()
        for repo_name in list(self.active_workspaces.keys()):
            await self.clean_workspace(repo_name)
        self.logger.info("WorkspaceManager cleaned up all workspaces and temporary directories")

