import asyncio
import os
import subprocess
import json
import ast
import astor
import asyncio
from packaging import version

class SetupPyTransformer(ast.NodeTransformer):
    def __init__(self, dependency_manager):
        self.dependency_manager = dependency_manager

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id == 'setup':
            for keyword in node.keywords:
                if keyword.arg == 'install_requires':
                    if isinstance(keyword.value, ast.List):
                        new_deps = []
                        for dep in keyword.value.elts:
                            if isinstance(dep, ast.Str):
                                name, version = self.parse_requirement(dep.s)
                                new_version = asyncio.run(self.dependency_manager.update_setup_py_dependencies(name, version))
                                new_deps.append(ast.Str(s=f"{name}=={new_version}"))
                            else:
                                new_deps.append(dep)
                        keyword.value.elts = new_deps
        return node

    def parse_requirement(self, req):
        parts = req.split('==')
        if len(parts) == 2:
            return parts[0], parts[1]
        return req, ''

class DependencyManager:
    def __init__(self, logger):
        self.logger = logger

    async def update_dependencies(self, repo_path):
        try:
            self.logger.info(f"Updating dependencies for repository at {repo_path}")
            if await self.is_python_project(repo_path):
                await self.update_python_dependencies(repo_path)
            elif await self.is_node_project(repo_path):
                await self.update_node_dependencies(repo_path)
            else:
                self.logger.warning(f"Unsupported project type in {repo_path}")
            self.logger.info("Dependencies updated successfully")
        except Exception as e:
            self.logger.error(f"Failed to update dependencies: {str(e)}")
            raise

    async def is_python_project(self, repo_path):
        return os.path.exists(os.path.join(repo_path, 'requirements.txt')) or \
               os.path.exists(os.path.join(repo_path, 'setup.py'))

    async def is_node_project(self, repo_path):
        return os.path.exists(os.path.join(repo_path, 'package.json'))

    async def update_python_dependencies(self, repo_path):
        try:
            self.logger.info("Updating Python dependencies")
            requirements_file = os.path.join(repo_path, 'requirements.txt')
            if os.path.exists(requirements_file):
                await self.update_requirements_txt(requirements_file)
            else:
                await self.update_setup_py(repo_path)
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to update Python dependencies: {str(e)}")
            raise

    async def update_requirements_txt(self, requirements_file):
        with open(requirements_file, 'r') as f:
            requirements = f.readlines()
        
        updated_requirements = []
        for req in requirements:
            package = req.split('==')[0]
            latest_version = await self.get_latest_package_version(package)
            updated_requirements.append(f"{package}=={latest_version}\n")
        
        with open(requirements_file, 'w') as f:
            f.writelines(updated_requirements)

    async def update_setup_py(self, repo_path):
        setup_py = os.path.join(repo_path, 'setup.py')
        try:
            with open(setup_py, 'r') as f:
                content = f.read()
            
            tree = ast.parse(content)
            transformer = SetupPyTransformer(self)
            modified_tree = transformer.visit(tree)
            
            updated_content = astor.to_source(modified_tree)
            
            with open(setup_py, 'w') as f:
                f.write(updated_content)
            
            self.logger.info(f"Updated dependencies in {setup_py}")
        except Exception as e:
            self.logger.error(f"Failed to update {setup_py}: {str(e)}")
            raise

    async def update_setup_py_dependencies(self, name, current_version):
        try:
            latest_version = await self.get_latest_package_version(name)
            if version.parse(latest_version) > version.parse(current_version):
                return latest_version
            return current_version
        except Exception as e:
            self.logger.warning(f"Failed to update {name}, keeping current version: {str(e)}")
            return current_version

    async def update_node_dependencies(self, repo_path):
        try:
            self.logger.info("Updating Node.js dependencies")
            package_json = os.path.join(repo_path, 'package.json')
            with open(package_json, 'r') as f:
                data = json.load(f)
            
            if 'dependencies' in data:
                data['dependencies'] = await self.update_node_package_versions(data['dependencies'])
            if 'devDependencies' in data:
                data['devDependencies'] = await self.update_node_package_versions(data['devDependencies'])
            
            with open(package_json, 'w') as f:
                json.dump(data, f, indent=2)
            
            await asyncio.to_thread(subprocess.run, ['npm', 'install'], cwd=repo_path, check=True)
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to update Node.js dependencies: {str(e)}")
            raise

    async def update_node_package_versions(self, dependencies):
        updated = {}
        for package, current_version in dependencies.items():
            latest_version = await self.get_latest_npm_package_version(package)
            updated[package] = latest_version
        return updated

    async def get_latest_package_version(self, package):
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ['pip', 'install', f'{package}==', '--dry-run'],
                capture_output=True,
                text=True,
                check=True
            )
            for line in result.stdout.split('\n'):
                if f"Would install {package}" in line:
                    return line.split()[-1]
            raise ValueError(f"Could not determine latest version for {package}")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to get latest version for {package}: {str(e)}")
            raise

    async def get_latest_npm_package_version(self, package):
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ['npm', 'view', package, 'version'],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to get latest npm version for {package}: {str(e)}")
            raise

    async def check_for_vulnerabilities(self, repo_path):
        try:
            self.logger.info(f"Checking for vulnerabilities in {repo_path}")
            if await self.is_python_project(repo_path):
                await self.check_python_vulnerabilities(repo_path)
            elif await self.is_node_project(repo_path):
                await self.check_node_vulnerabilities(repo_path)
            else:
                self.logger.warning(f"Unsupported project type for vulnerability check in {repo_path}")
        except Exception as e:
            self.logger.error(f"Failed to check for vulnerabilities: {str(e)}")
            raise

        async def check_python_vulnerabilities(self, repo_path):
            try:
                result = await asyncio.to_thread(
                    subprocess.run,
                    ['safety', 'check', '--json', '-r', os.path.join(repo_path, 'requirements.txt')],
                    capture_output=True,
                    text=True,
                    check=True
                )
                vulnerabilities = json.loads(result.stdout)
                if vulnerabilities:
                    self.logger.warning(f"Found {len(vulnerabilities)} vulnerabilities in Python dependencies")
                    for vuln in vulnerabilities:
                        self.logger.warning(f"Vulnerability in {vuln['package_name']}: {vuln['vulnerability_id']}")
                    else:
                        self.logger.info("No vulnerabilities found in Python dependencies")
            except subprocess.CalledProcessError as e:
                self.logger.error(f"Failed to check Python vulnerabilities: {str(e)}")
                raise

    async def check_node_vulnerabilities(self, repo_path):
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ['npm', 'audit', '--json'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            audit_result = json.loads(result.stdout)
            if audit_result['vulnerabilities']:
                self.logger.warning(f"Found vulnerabilities in Node.js dependencies")
                for severity, count in audit_result['vulnerabilities'].items():
                    if count > 0:
                        self.logger.warning(f"{count} {severity} severity vulnerabilities")
            else:
                self.logger.info("No vulnerabilities found in Node.js dependencies")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to check Node.js vulnerabilities: {str(e)}")
            raise

    async def generate_dependency_report(self, repo_path):
        report = "Dependency Report\n==================\n\n"
        if await self.is_python_project(repo_path):
            report += await self.generate_python_dependency_report(repo_path)
        elif await self.is_node_project(repo_path):
            report += await self.generate_node_dependency_report(repo_path)
        else:
            report += "Unsupported project type"
        return report

    async def generate_python_dependency_report(self, repo_path):
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ['pip', 'list', '--format=json'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            dependencies = json.loads(result.stdout)
            report = "Python Dependencies:\n"
            for dep in dependencies:
                report += f"{dep['name']} ({dep['version']})\n"
            return report
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to generate Python dependency report: {str(e)}")
            raise

    async def generate_node_dependency_report(self, repo_path):
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ['npm', 'list', '--json'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            dependencies = json.loads(result.stdout)
            report = "Node.js Dependencies:\n"
            for dep, info in dependencies.get('dependencies', {}).items():
                report += f"{dep} ({info['version']})\n"
            return report
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to generate Node.js dependency report: {str(e)}")
            raise


