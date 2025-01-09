import os
import aiofiles
import json

class FileManager:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger

    async def update_file(self, file_path, content):
        try:
            self.logger.info(f"Updating file: {file_path}")
            async with aiofiles.open(file_path, mode='w') as file:
                await file.write(content)
            self.logger.info(f"File updated successfully")
        except IOError as e:
            self.logger.error(f"Failed to update file: {str(e)}")
            raise

    async def read_file(self, file_path):
        try:
            self.logger.info(f"Reading file: {file_path}")
            async with aiofiles.open(file_path, mode='r') as file:
                content = await file.read()
            self.logger.info(f"File read successfully")
            return content
        except IOError as e:
            self.logger.error(f"Failed to read file: {str(e)}")
            raise

    async def delete_file(self, file_path):
        try:
            self.logger.info(f"Deleting file: {file_path}")
            os.remove(file_path)
            self.logger.info(f"File deleted successfully")
        except IOError as e:
            self.logger.error(f"Failed to delete file: {str(e)}")
            raise

    async def list_files(self, directory):
        try:
            self.logger.info(f"Listing files in directory: {directory}")
            files = os.listdir(directory)
            self.logger.info(f"Files listed successfully")
            return files
        except IOError as e:
            self.logger.error(f"Failed to list files: {str(e)}")
            raise

    async def update_gitignore(self, repo_path, patterns):
        gitignore_path = os.path.join(repo_path, '.gitignore')
        try:
            self.logger.info(f"Updating .gitignore file")
            async with aiofiles.open(gitignore_path, mode='a') as file:
                for pattern in patterns:
                    await file.write(f"\n{pattern}")
            self.logger.info(f".gitignore file updated successfully")
        except IOError as e:
            self.logger.error(f"Failed to update .gitignore file: {str(e)}")
            raise

    async def load_json_file(self, file_path):
        try:
            self.logger.info(f"Loading JSON file: {file_path}")
            async with aiofiles.open(file_path, mode='r') as file:
                content = await file.read()
                data = json.loads(content)
            self.logger.info(f"JSON file loaded successfully")
            return data
        except (IOError, json.JSONDecodeError) as e:
            self.logger.error(f"Failed to load JSON file: {str(e)}")
            raise

    async def save_json_file(self, file_path, data):
        try:
            self.logger.info(f"Saving JSON file: {file_path}")
            async with aiofiles.open(file_path, mode='w') as file:
                await file.write(json.dumps(data, indent=2))
            self.logger.info(f"JSON file saved successfully")
        except IOError as e:
            self.logger.error(f"Failed to save JSON file: {str(e)}")
            raise
