import os
import sys
import ssl
import logging
from datetime import datetime
import configparser
import argparse
import git
import shutil
import time
import smtplib
from email.mime.text import MIMEText
from filelock import FileLock
import schedule

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
        "NOTIFICATION_EMAIL": config.get("Notification", "NOTIFICATION_EMAIL"),
        "SMTP_USE_SSL": config.getboolean("Notification", "SMTP_USE_SSL", fallback=True) 
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

def update_file(file_path, dry_run=False):
    """Update the file content based on its type and existing content."""
    lock = FileLock(f"{file_path}.lock")
    
    with lock:
        if not os.path.exists(file_path):
            if not dry_run:
                with open(file_path, "w") as file:
                    file.write("0")
                logging.info(f"Initialized '{file_path}' with value 0.")
            else:
                logging.info(f"[DRY RUN] Would initialize '{file_path}' with value 0.")
            return "0"

        backup_path = create_backup(file_path)

        try:
            with open(file_path, "r") as file:
                content = file.read().strip()

            file_name = os.path.basename(file_path).lower()
            
            if "requirements.txt" in file_name:
                # For requirements.txt, add a timestamp
                new_content = content + f"\n# Updated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                update_description = "timestamp added"
            elif content.isdigit():
                # If content is a number, increment it
                new_content = str(int(content) + 1)
                update_description = f"incremented to {new_content}"
            elif content.replace('.', '', 1).isdigit():
                # If content is a float, increment it
                new_content = str(float(content) + 1)
                update_description = f"incremented to {new_content}"
            else:
                # For other content, append a line
                new_content = content + f"\n# Updated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                update_description = "new line added"

            if not dry_run:
                with open(file_path, "w") as file:
                    file.write(new_content)
                logging.info(f"Updated '{file_path}': {update_description}")
            else:
                logging.info(f"[DRY RUN] Would update '{file_path}': {update_description}")
            
            return update_description

        except Exception as e:
            logging.error(f"Error updating {file_path}: {str(e)}. Restoring from backup.")
            shutil.copy2(backup_path, file_path)
            return None

def commit_and_push(repo, file_paths, branch_name, remote_name, commit_message_prefix, new_values, dry_run=False):
    """Commit and push changes to the remote repository."""
    for attempt in range(MAX_RETRIES):
        try:
            if not dry_run:
                repo.git.add(file_paths)
                commit_message = f"{commit_message_prefix}Updated counters: " + ", ".join(f"{path}: {value}" for path, value in zip(file_paths, new_values))
                repo.index.commit(commit_message)
                origin = repo.remote(name=remote_name)
                origin.push(refspec=f"{branch_name}:{branch_name}")
                logging.info("Successfully committed and pushed changes to remote repository.")
            else:
                logging.info(f"[DRY RUN] Would commit and push changes: {commit_message_prefix}Updated counters: " + ", ".join(f"{path}: {value}" for path, value in zip(file_paths, new_values)))
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

    context = ssl.create_default_context()

    try:
        if smtp_config.get('SMTP_USE_SSL', True):
            with smtplib.SMTP_SSL(smtp_config['SMTP_SERVER'], smtp_config['SMTP_PORT'], context=context) as server:
                server.login(smtp_config['SMTP_USER'], smtp_config['SMTP_PASSWORD'])
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_config['SMTP_SERVER'], smtp_config['SMTP_PORT']) as server:
                server.starttls(context=context)
                server.login(smtp_config['SMTP_USER'], smtp_config['SMTP_PASSWORD'])
                server.send_message(msg)
        logging.info(f"Notification email sent to {recipient}")
    except Exception as e:
        logging.error(f"Failed to send notification email: {str(e)}")

def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Automated Git commit script")
    parser.add_argument("--config", help="Path to custom config file", default=CONFIG_FILE)
    parser.add_argument("--dry-run", action="store_true", help="Perform a dry run without making actual changes")
    return parser.parse_args()

def main(dry_run=False):
    """Main function to automate the file update and Git commit."""
    config = None
    repo = None
    try:
        config = load_config()
        repo = ensure_repo_path(config["REPO_PATH"])
        with repo:  # Use context manager for the repository
            setup_git_config(repo, config["GIT_USER_NAME"], config["GIT_USER_EMAIL"])
            
            new_values = [update_file(file_path, dry_run=dry_run) for file_path in config["FILE_PATHS"]]
            commit_and_push(
                repo,
                config["FILE_PATHS"],
                config["BRANCH_NAME"],
                config["REMOTE_NAME"],
                config["COMMIT_MESSAGE_PREFIX"],
                new_values,
                dry_run=dry_run
            )
            
            notification_body = "Script executed successfully. " + (
                "Changes were simulated (dry run)." if dry_run else 
                f"Updated files: {', '.join(config['FILE_PATHS'])}"
            )
            send_notification(
                {k: config[k] for k in ['SMTP_SERVER', 'SMTP_PORT', 'SMTP_USER', 'SMTP_PASSWORD']},
                config['NOTIFICATION_EMAIL'],
                "Auto-commit script execution report",
                notification_body
            )
            
        logging.info("Script executed successfully.")
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        
        if config and 'NOTIFICATION_EMAIL' in config:
            send_notification(
                {k: config[k] for k in ['SMTP_SERVER', 'SMTP_PORT', 'SMTP_USER', 'SMTP_PASSWORD']},
                config['NOTIFICATION_EMAIL'],
                "Auto-commit script execution failed",
                f"An error occurred: {str(e)}"
            )
    finally:
        if repo and not isinstance(repo, git.Repo):
            repo.close()

def run_scheduled_task():
    """Run the main task with scheduling."""
    args = parse_arguments()
    global CONFIG_FILE
    CONFIG_FILE = args.config
    main(dry_run=args.dry_run)
    
    print("Scheduler started. Press Ctrl+C to exit.")
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("Scheduler stopped.")
    except Exception as e:
        logging.error(f"An unexpected error occurred in the scheduler: {str(e)}")
        print(f"An error occurred. Check the log file '{LOG_FILE}' for details.")
    finally:
        print("Exiting the script.")

if __name__ == "__main__":
    run_scheduled_task()
