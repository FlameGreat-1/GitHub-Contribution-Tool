import logging
import os
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import json
from datetime import datetime
import traceback
import sys

class AdvancedLogger:
    def __init__(self, name, log_file, level=logging.INFO, max_bytes=10485760, backup_count=5):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        self.log_file = log_file
        self.max_bytes = max_bytes
        self.backup_count = backup_count

        self.setup_file_handler()
        self.setup_console_handler()
        self.setup_error_handler()

    def setup_file_handler(self):
        file_handler = RotatingFileHandler(
            self.log_file, maxBytes=self.max_bytes, backupCount=self.backup_count
        )
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)

    def setup_console_handler(self):
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

    def setup_error_handler(self):
        error_file = f"{os.path.splitext(self.log_file)[0]}_error.log"
        error_handler = TimedRotatingFileHandler(
            error_file, when="midnight", interval=1, backupCount=30
        )
        error_handler.setLevel(logging.ERROR)
        error_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        error_handler.setFormatter(error_formatter)
        self.logger.addHandler(error_handler)

    def info(self, message):
        self.logger.info(message)

    def warning(self, message):
        self.logger.warning(message)

    def error(self, message, exc_info=True):
        self.logger.error(message, exc_info=exc_info)

    def critical(self, message, exc_info=True):
        self.logger.critical(message, exc_info=exc_info)

    def exception(self, message):
        self.logger.exception(message)

    def log_dict(self, data, level=logging.INFO):
        self.logger.log(level, json.dumps(data, indent=2))

    def set_level(self, level):
        self.logger.setLevel(level)

    def add_file_handler(self, log_file, level=logging.INFO):
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)

    def remove_handler(self, handler):
        self.logger.removeHandler(handler)

    def log_exception(self, exc_type, exc_value, exc_traceback):
        self.logger.error(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_traceback)
        )

    def start_timer(self, task_name):
        setattr(self, f"timer_{task_name}", datetime.now())

    def end_timer(self, task_name):
        start_time = getattr(self, f"timer_{task_name}", None)
        if start_time:
            duration = datetime.now() - start_time
            self.logger.info(f"Task '{task_name}' completed in {duration}")
            delattr(self, f"timer_{task_name}")
        else:
            self.logger.warning(f"No start time found for task '{task_name}'")

    def log_memory_usage(self):
        import psutil
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        self.logger.info(f"Memory usage: {mem_info.rss / 1024 / 1024:.2f} MB")

    def log_system_info(self):
        import platform
        system_info = {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
        }
        self.log_dict(system_info, level=logging.INFO)

    def setup_syslog_handler(self, address=('localhost', 514), facility=logging.handlers.SysLogHandler.LOG_USER):
        syslog_handler = logging.handlers.SysLogHandler(address=address, facility=facility)
        syslog_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        syslog_handler.setFormatter(syslog_formatter)
        self.logger.addHandler(syslog_handler)

    def setup_email_handler(self, mailhost, fromaddr, toaddrs, subject, credentials):
        email_handler = logging.handlers.SMTPHandler(
            mailhost, fromaddr, toaddrs, subject, credentials=credentials, secure=()
        )
        email_handler.setLevel(logging.ERROR)
        email_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        email_handler.setFormatter(email_formatter)
        self.logger.addHandler(email_handler)

    def log_git_info(self, repo_path):
        try:
            from git import Repo
            repo = Repo(repo_path)
            git_info = {
                "branch": repo.active_branch.name,
                "commit": repo.head.commit.hexsha,
                "author": repo.head.commit.author.name,
                "authored_date": repo.head.commit.authored_datetime.isoformat(),
                "committer": repo.head.commit.committer.name,
                "committed_date": repo.head.commit.committed_datetime.isoformat(),
            }
            self.log_dict(git_info, level=logging.INFO)
        except Exception as e:
            self.logger.error(f"Failed to log git info: {str(e)}")

    def log_environment_variables(self, include=None, exclude=None):
        env_vars = dict(os.environ)
        if include:
            env_vars = {k: v for k, v in env_vars.items() if k in include}
        if exclude:
            env_vars = {k: v for k, v in env_vars.items() if k not in exclude}
        self.log_dict(env_vars, level=logging.INFO)

    def create_custom_logger(self, name, log_file, level=logging.INFO):
        custom_logger = AdvancedLogger(name, log_file, level)
        return custom_logger

