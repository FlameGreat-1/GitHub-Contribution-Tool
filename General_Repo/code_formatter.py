import asyncio
import subprocess
import os
from typing import List, Dict

class CodeFormatter:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.formatters = {
            'python': self.format_python,
            'javascript': self.format_javascript,
            'typescript': self.format_typescript,
            'java': self.format_java,
            'go': self.format_go,
            'rust': self.format_rust,
            'c': self.format_c,
            'cpp': self.format_cpp,
        }

    async def format_code(self, repo_path: str) -> Dict[str, List[str]]:
        self.logger.info(f"Formatting code in {repo_path}")
        formatted_files = {}
        for root, _, files in os.walk(repo_path):
            for file in files:
                file_path = os.path.join(root, file)
                extension = os.path.splitext(file)[1].lower()
                formatter = self.get_formatter(extension)
                if formatter:
                    try:
                        await formatter(file_path)
                        rel_path = os.path.relpath(file_path, repo_path)
                        formatted_files.setdefault(extension, []).append(rel_path)
                    except Exception as e:
                        self.logger.error(f"Error formatting {file_path}: {str(e)}")
        self.logger.info("Code formatting completed")
        return formatted_files

    def get_formatter(self, extension: str):
        extension_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.java': 'java',
            '.go': 'go',
            '.rs': 'rust',
            '.c': 'c',
            '.cpp': 'cpp',
            '.h': 'c',
            '.hpp': 'cpp'
        }
        language = extension_map.get(extension)
        return self.formatters.get(language)

    async def format_python(self, file_path: str):
        await self._run_command(['black', file_path])
        await self._run_command(['isort', file_path])

    async def format_javascript(self, file_path: str):
        await self._run_command(['prettier', '--write', file_path])

    async def format_typescript(self, file_path: str):
        await self._run_command(['prettier', '--write', file_path])
        await self._run_command(['tslint', '--fix', file_path])

    async def format_java(self, file_path: str):
        await self._run_command(['google-java-format', '-i', file_path])

    async def format_go(self, file_path: str):
        await self._run_command(['gofmt', '-w', file_path])

    async def format_rust(self, file_path: str):
        await self._run_command(['rustfmt', file_path])

    async def format_c(self, file_path: str):
        await self._run_command(['clang-format', '-i', file_path])

    async def format_cpp(self, file_path: str):
        await self._run_command(['clang-format', '-i', file_path])

    async def _run_command(self, command: List[str]):
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, command, stdout, stderr)
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Command failed: {e.cmd}. Error: {e.stderr.decode()}")
            raise
        except Exception as e:
            self.logger.error(f"Error running command {command}: {str(e)}")
            raise

    async def install_formatters(self):
        formatters = [
            ['pip', 'install', 'black', 'isort'],
            ['npm', 'install', '-g', 'prettier', 'tslint'],
            ['go', 'get', '-u', 'golang.org/x/tools/cmd/gofmt'],
            ['cargo', 'install', 'rustfmt'],
            ['apt-get', 'install', 'clang-format'],
        ]
        for formatter in formatters:
            try:
                await self._run_command(formatter)
            except Exception as e:
                self.logger.error(f"Failed to install formatter {formatter[0]}: {str(e)}")

    async def generate_formatting_report(self, formatted_files: Dict[str, List[str]]) -> str:
        report = "Code Formatting Report\n"
        report += "======================\n\n"
        for extension, files in formatted_files.items():
            report += f"{extension} files formatted:\n"
            for file in files:
                report += f"  - {file}\n"
            report += "\n"
        return report

    async def apply_custom_rules(self, repo_path: str):
        custom_rules = self.config.get('custom_formatting_rules', {})
        for language, rules in custom_rules.items():
            files = await self.get_files_by_language(repo_path, language)
            for file in files:
                await self.apply_rules_to_file(file, rules)

    async def get_files_by_language(self, repo_path: str, language: str) -> List[str]:
        extension = self.get_extension_for_language(language)
        files = []
        for root, _, filenames in os.walk(repo_path):
            for filename in filenames:
                if filename.endswith(extension):
                    files.append(os.path.join(root, filename))
        return files

    def get_extension_for_language(self, language: str) -> str:
        extension_map = {
            'python': '.py',
            'javascript': '.js',
            'typescript': '.ts',
            'java': '.java',
            'go': '.go',
            'rust': '.rs',
            'c': '.c',
            'cpp': '.cpp'
        }
        return extension_map.get(language, '')

    async def apply_rules_to_file(self, file_path: str, rules: List[Dict]):
        with open(file_path, 'r') as f:
            content = f.read()
        
        for rule in rules:
            content = await self.apply_rule(content, rule)
        
        with open(file_path, 'w') as f:
            f.write(content)

    async def apply_rule(self, content: str, rule: Dict) -> str:
        import re
        pattern = rule['pattern']
        replacement = rule['replacement']
        return re.sub(pattern, replacement, content)
