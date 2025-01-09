import os
import sys
import logging
from datetime import datetime
import configparser
import git
import shutil
import time
import smtplib
from email.mime.text import MIMEText
from filelock import FileLock

# Configuration
CONFIG_FILE = "config.ini"
LOG_FILE = "auto_commit.log"
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# Setup Logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

class ConfigurationError(Exception):
    """Custom exception for configuration errors."""
    pass

def load_config():
    """Load and validate configuration from config file."""
    if not os.path.exists(CONFIG_FILE):
        raise FileNotFoundError(f"Configuration file '{CONFIG_FILE}' not found.")
    
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    
    required_sections = ["General", "Git", "Notification"]
    required_keys = {
        "General": ["REPO_PATH", "FILE_PATHS", "BRANCH_NAME", "REMOTE_NAME", "COMMIT_MESSAGE_PREFIX"],
        "Git": ["GIT_USER_NAME", "GIT_USER_EMAIL"],
        "Notification": ["SMTP_SERVER", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "NOTIFICATION_EMAIL"]
    }

    for section in required_sections:
        if not config.has_section(section):
            raise ConfigurationError(f"Missing required section: {section}")
        for key in required_keys[section]:
            if not config.has_option(section, key):
                raise ConfigurationError(f"Missing required configuration: {section}.{key}")

    return {
        "REPO_PATH": config.get("General", "REPO_PATH"),
        "FILE_PATHS": [path.strip() for path in config.get("General", "FILE_PATHS").split(",")],
        "BRANCH_NAME": config.get("General", "BRANCH_NAME"),
        "REMOTE_NAME": config.get("General", "REMOTE_NAME"),
        "COMMIT_MESSAGE_PREFIX": config.get("General", "COMMIT_MESSAGE_PREFIX"),
        "GIT_USER_NAME": config.get("Git", "GIT_USER_NAME"),
        "GIT_USER_EMAIL": config.get("Git", "GIT_USER_EMAIL"),
        "SMTP_SERVER": config.get("Notification", "SMTP_SERVER"),
        "SMTP_PORT": config.getint("Notification", "SMTP_PORT"),
        "SMTP_USER": config.get("Notification", "SMTP_USER"),
        "SMTP_PASSWORD": config.get("Notification", "SMTP_PASSWORD"),
        "NOTIFICATION_EMAIL": config.get("Notification", "NOTIFICATION_EMAIL")
    }

def setup_git_config(repo, git_user_name, git_user_email):
    """Setup Git configuration for the repository."""
    with repo.config_writer() as git_config:
        git_config.set_value("user", "name", git_user_name)
        git_config.set_value("user", "email", git_user_email)

def ensure_repo_path(repo_path):
    """Ensure the repository path exists and is a valid Git repository."""
    if not os.path.exists(repo_path):
        raise FileNotFoundError(f"Repository path '{repo_path}' does not exist.")
    
    try:
        repo = git.Repo(repo_path)
        logging.info(f"Successfully opened Git repository at '{repo_path}'")
        return repo
    except git.InvalidGitRepositoryError:
        raise EnvironmentError(f"'{repo_path}' is not a valid Git repository.")

def create_backup(file_path):
    """Create a backup of the file."""
    backup_path = f"{file_path}.bak"
    shutil.copy2(file_path, backup_path)
    logging.info(f"Created backup of '{file_path}' at '{backup_path}'")
    return backup_path

def update_file(file_path):
    """Increment the counter in the file."""
    lock = FileLock(f"{file_path}.lock")
    
    with lock:
        if not os.path.exists(file_path):
            with open(file_path, "w") as file:
                file.write("0")
            logging.info(f"Initialized '{file_path}' with value 0.")
            return 0

        backup_path = create_backup(file_path)

        try:
            with open(file_path, "r+") as file:
                current_value = int(file.read().strip())
                new_value = current_value + 1
                file.seek(0)
                file.write(str(new_value))
                file.truncate()
                logging.info(f"Updated '{file_path}' to value {new_value}.")
            return new_value
        except ValueError:
            logging.error(f"Invalid data in {file_path}. Restoring from backup.")
            shutil.copy2(backup_path, file_path)
            return update_file(file_path)  # Retry with restored file

def commit_and_push(repo, file_paths, branch_name, remote_name, commit_message_prefix, new_values):
    """Commit and push changes to the remote repository."""
    for attempt in range(MAX_RETRIES):
        try:
            repo.git.add(file_paths)
            commit_message = f"{commit_message_prefix}Updated counters: " + ", ".join(f"{path}: {value}" for path, value in zip(file_paths, new_values))
            repo.index.commit(commit_message)
            origin = repo.remote(name=remote_name)
            origin.push(refspec=f"{branch_name}:{branch_name}")
            logging.info("Successfully committed and pushed changes to remote repository.")
            return
        except git.GitCommandError as e:
            if attempt < MAX_RETRIES - 1:
                logging.warning(f"Git operation failed (attempt {attempt + 1}/{MAX_RETRIES}): {str(e)}. Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                logging.error(f"Git operation failed after {MAX_RETRIES} attempts: {str(e)}")
                raise

def send_notification(smtp_config, recipient, subject, body):
    """Send an email notification."""
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = smtp_config['SMTP_USER']
    msg['To'] = recipient

    try:
        with smtplib.SMTP(smtp_config['SMTP_SERVER'], smtp_config['SMTP_PORT']) as server:
            server.starttls()
            server.login(smtp_config['SMTP_USER'], smtp_config['SMTP_PASSWORD'])
            server.send_message(msg)
        logging.info(f"Notification email sent to {recipient}")
    except Exception as e:
        logging.error(f"Failed to send notification email: {str(e)}")

def main():
    """Main function to automate the file update and Git commit."""
    try:
        config = load_config()
        repo = ensure_repo_path(config["REPO_PATH"])
        setup_git_config(repo, config["GIT_USER_NAME"], config["GIT_USER_EMAIL"])
        
        new_values = [update_file(file_path) for file_path in config["FILE_PATHS"]]
        commit_and_push(
            repo,
            config["FILE_PATHS"],
            config["BRANCH_NAME"],
            config["REMOTE_NAME"],
            config["COMMIT_MESSAGE_PREFIX"],
            new_values
        )
        
        notification_body = f"Script executed successfully. Updated files: {', '.join(config['FILE_PATHS'])}"
        send_notification(
            {k: config[k] for k in ['SMTP_SERVER', 'SMTP_PORT', 'SMTP_USER', 'SMTP_PASSWORD']},
            config['NOTIFICATION_EMAIL'],
            "Auto-commit script execution report",
            notification_body
        )
        
        print("Script executed successfully.")
        logging.info("Script executed successfully.")
    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        print(error_message)
        logging.error(error_message)
        
        if 'NOTIFICATION_EMAIL' in config:
            send_notification(
                {k: config[k] for k in ['SMTP_SERVER', 'SMTP_PORT', 'SMTP_USER', 'SMTP_PASSWORD']},
                config['NOTIFICATION_EMAIL'],
                "Auto-commit script execution failed",
                error_message
            )

if __name__ == "__main__":
    main()
