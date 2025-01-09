import asyncio
import os
import re
from typing import List, Dict
import aiofiles
import markdown2
import pdoc
from bs4 import BeautifulSoup

class DocumentationUpdater:
    def __init__(self, logger):
        self.logger = logger

    async def update_documentation(self, repo_path: str) -> Dict[str, List[str]]:
        self.logger.info(f"Updating documentation in {repo_path}")
        updated_files = {}
        for root, _, files in os.walk(repo_path):
            for file in files:
                if file.endswith('.md'):
                    file_path = os.path.join(root, file)
                    try:
                        await self.update_markdown(file_path)
                        rel_path = os.path.relpath(file_path, repo_path)
                        updated_files.setdefault('markdown', []).append(rel_path)
                    except Exception as e:
                        self.logger.error(f"Error updating markdown in {file_path}: {str(e)}")
                elif file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    try:
                        await self.update_python_docstrings(file_path)
                        rel_path = os.path.relpath(file_path, repo_path)
                        updated_files.setdefault('python', []).append(rel_path)
                    except Exception as e:
                        self.logger.error(f"Error updating Python docstrings in {file_path}: {str(e)}")
        self.logger.info("Documentation update completed")
        return updated_files

    async def update_markdown(self, file_path: str):
        async with aiofiles.open(file_path, mode='r') as f:
            content = await f.read()
        
        # Update links
        content = await self.update_markdown_links(content)
        
        # Update headers
        content = await self.update_markdown_headers(content)
        
        # Add table of contents if not present
        if '## Table of Contents' not in content:
            content = await self.add_table_of_contents(content)
        
        async with aiofiles.open(file_path, mode='w') as f:
            await f.write(content)

    async def update_markdown_links(self, content: str) -> str:
        # Update relative links to absolute
        content = re.sub(r'\[([^\]]+)\]\((?!http)([^\)]+)\)', r'[\1](https://github.com/user/repo/blob/main/\2)', content)
        return content

    async def update_markdown_headers(self, content: str) -> str:
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if line.startswith('#'):
                level = len(line.split()[0])
                text = ' '.join(line.split()[1:])
                lines[i] = f"{'#' * level} {text.title()}"
        return '\n'.join(lines)

    async def add_table_of_contents(self, content: str) -> str:
        headers = re.findall(r'^(#{1,6})\s+(.+)$', content, re.MULTILINE)
        if headers:
            toc = "## Table of Contents\n\n"
            for header in headers:
                level = len(header[0]) - 1
                text = header[1]
                link = text.lower().replace(' ', '-')
                toc += f"{'  ' * level}- [{text}](#{link})\n"
            return f"{toc}\n{content}"
        return content

    async def update_python_docstrings(self, file_path: str):
        async with aiofiles.open(file_path, mode='r') as f:
            content = await f.read()
        
        # Parse the Python file
        module = pdoc.Module(pdoc.import_module(file_path))
        
        # Update docstrings
        for obj in module.walk():
            if obj.docstring:
                new_docstring = await self.improve_docstring(obj.docstring)
                content = content.replace(obj.docstring, new_docstring)
        
        async with aiofiles.open(file_path, mode='w') as f:
            await f.write(content)

    async def improve_docstring(self, docstring: str) -> str:
        # Add parameter descriptions if missing
        if 'Parameters:' not in docstring:
            docstring += "\n\nParameters:\n"
            params = re.findall(r':param (\w+):', docstring)
            for param in params:
                docstring += f"    {param}: Description of {param}\n"
        
        # Add return description if missing
        if 'Returns:' not in docstring and ':return:' in docstring:
            docstring += "\nReturns:\n    Description of return value\n"
        
        return docstring

    async def generate_api_documentation(self, repo_path: str) -> str:
        self.logger.info(f"Generating API documentation for {repo_path}")
        modules = []
        for root, _, files in os.walk(repo_path):
            for file in files:
                if file.endswith('.py'):
                    module_path = os.path.relpath(os.path.join(root, file), repo_path)
                    module_name = module_path.replace('/', '.').replace('.py', '')
                    modules.append(module_name)
        
        html = pdoc.pdoc(*modules, output_directory=repo_path)
        
        # Convert HTML to Markdown
        soup = BeautifulSoup(html, 'html.parser')
        markdown = markdown2.markdown(soup.get_text())
        
        api_doc_path = os.path.join(repo_path, 'API_DOCUMENTATION.md')
        async with aiofiles.open(api_doc_path, mode='w') as f:
            await f.write(markdown)
        
        self.logger.info(f"API documentation generated at {api_doc_path}")
        return api_doc_path

    async def update_readme(self, repo_path: str):
        readme_path = os.path.join(repo_path, 'README.md')
        if not os.path.exists(readme_path):
            self.logger.warning(f"README.md not found in {repo_path}")
            return
        
        async with aiofiles.open(readme_path, mode='r') as f:
            content = await f.read()
        
        # Update project description
        content = await self.update_project_description(content, repo_path)
        
        # Update installation instructions
        content = await self.update_installation_instructions(content, repo_path)
        
        # Update usage examples
        content = await self.update_usage_examples(content, repo_path)
        
        # Update contributing guidelines
        content = await self.update_contributing_guidelines(content, repo_path)
        
        async with aiofiles.open(readme_path, mode='w') as f:
            await f.write(content)
        
        self.logger.info(f"README.md updated in {repo_path}")

    async def update_project_description(self, content: str, repo_path: str) -> str:
        project_name = os.path.basename(repo_path)
        description = await self.generate_project_description(repo_path)
        
        # Update or add project description in README
        description_pattern = r'# (.+?)\n\n(.+?)\n\n'
        if re.search(description_pattern, content):
            content = re.sub(description_pattern, f'# {project_name}\n\n{description}\n\n', content, count=1)
        else:
            content = f'# {project_name}\n\n{description}\n\n' + content
        
        return content

    async def generate_project_description(self, repo_path: str) -> str:
        description = "This project "
        
        # Analyze project structure
        structure = await self.analyze_project_structure(repo_path)
        
        # Determine project type
        if 'setup.py' in structure['files']:
            description += "is a Python package. "
        elif 'package.json' in structure['files']:
            description += "is a Node.js application. "
        elif 'pom.xml' in structure['files']:
            description += "is a Java Maven project. "
        elif 'build.gradle' in structure['files']:
            description += "is a Java Gradle project. "
        
        # Add information about main components
        if structure['directories']:
            main_dirs = ', '.join(structure['directories'][:3])
            description += f"It contains the following main components: {main_dirs}. "
        
        # Add information about key files
        key_files = [f for f in structure['files'] if f in ['README.md', 'LICENSE', 'CONTRIBUTING.md', '.gitignore']]
        if key_files:
            description += f"The project includes {', '.join(key_files)}. "
        
        # Add information about dependencies
        dependencies = await self.extract_dependencies(repo_path)
        if dependencies:
            dep_list = ', '.join(dependencies[:5])  # List up to 5 dependencies
            description += f"It uses the following key dependencies: {dep_list}. "
        
        # Add information about main functionality
        main_functionality = await self.extract_main_functionality(repo_path)
        if main_functionality:
            description += f"The main functionality includes {main_functionality}. "
        
        return description.strip()

    async def analyze_project_structure(self, repo_path: str) -> Dict[str, List[str]]:
        structure = {'directories': [], 'files': []}
        for root, dirs, files in os.walk(repo_path):
            rel_path = os.path.relpath(root, repo_path)
            if rel_path != '.':
                structure['directories'].append(rel_path)
            for file in files:
                structure['files'].append(os.path.join(rel_path, file))
        return structure

    async def extract_dependencies(self, repo_path: str) -> List[str]:
        dependencies = []
        
        # Check for Python dependencies
        requirements_file = os.path.join(repo_path, 'requirements.txt')
        if os.path.exists(requirements_file):
            async with aiofiles.open(requirements_file, mode='r') as f:
                content = await f.read()
                dependencies = re.findall(r'^([a-zA-Z0-9-_.]+)', content, re.MULTILINE)
        
        # Check for Node.js dependencies
        package_json = os.path.join(repo_path, 'package.json')
        if os.path.exists(package_json):
            async with aiofiles.open(package_json, mode='r') as f:
                content = await f.read()
                data = json.loads(content)
                dependencies = list(data.get('dependencies', {}).keys())
        
        return dependencies

    async def extract_main_functionality(self, repo_path: str) -> str:
        main_file = await self.find_main_file(repo_path)
        if not main_file:
            return ""
        
        async with aiofiles.open(main_file, mode='r') as f:
            content = await f.read()
        
        tree = ast.parse(content)
        function_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        
        if function_names:
            return f"functions such as {', '.join(function_names[:3])}"
        return ""

    async def find_main_file(self, repo_path: str) -> str:
        potential_mains = ['main.py', 'app.py', 'index.py', 'server.py']
        for file in potential_mains:
            full_path = os.path.join(repo_path, file)
            if os.path.exists(full_path):
                return full_path
        return ""

    async def update_installation_instructions(self, content: str, repo_path: str) -> str:
        if 'pip install' not in content:
            content += "\n\n## Installation\n\n```\npip install .\n```\n"
        return content

    async def update_usage_examples(self, content: str, repo_path: str) -> str:
        if '## Usage' not in content:
            content += "\n\n## Usage\n\n```python\n# Add usage examples here\n```\n"
        return content

    async def update_contributing_guidelines(self, content: str, repo_path: str) -> str:
        if '## Contributing' not in content:
            content += "\n\n## Contributing\n\nPlease read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct, and the process for submitting pull requests to us.\n"
        return content

    async def generate_documentation_report(self, updated_files: Dict[str, List[str]]) -> str:
        report = "Documentation Update Report\n"
        report += "============================\n\n"
        for doc_type, files in updated_files.items():
            report += f"{doc_type.capitalize()} files updated:\n"
            for file in files:
                report += f"  - {file}\n"
            report += "\n"
        return report
