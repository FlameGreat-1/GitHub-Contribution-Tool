import os
import json
from cryptography.fernet import Fernet

class Config:
    def __init__(self):
        self.config_file = os.path.expanduser("~/.github_tool_config.json")
        self.load_config()

    def load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
            self.decrypt_sensitive_data()
        else:
            self.config = {}
            self.create_default_config()

    def create_default_config(self):
        self.config = {
            "github_token": "",
            "user_name": "",
            "user_email": "",
            "default_branch": "main",
            "code_style": "black",
            "log_level": "INFO",
            "smtp_server": "",
            "smtp_port": 587,
            "smtp_user": "",
            "smtp_password": "",
            "notification_email": ""
        }
        self.save_config()

    def save_config(self):
        self.encrypt_sensitive_data()
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
        self.decrypt_sensitive_data()

    def encrypt_sensitive_data(self):
        key = self.get_encryption_key()
        f = Fernet(key)
        for sensitive_key in ['github_token', 'smtp_password']:
            if self.config.get(sensitive_key):
                self.config[sensitive_key] = f.encrypt(self.config[sensitive_key].encode()).decode()

    def decrypt_sensitive_data(self):
        key = self.get_encryption_key()
        f = Fernet(key)
        for sensitive_key in ['github_token', 'smtp_password']:
            if self.config.get(sensitive_key):
                self.config[sensitive_key] = f.decrypt(self.config[sensitive_key].encode()).decode()

    def get_encryption_key(self):
        key_file = os.path.expanduser("~/.github_tool_key")
        if not os.path.exists(key_file):
            key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(key)
        else:
            with open(key_file, 'rb') as f:
                key = f.read()
        return key

    def __getitem__(self, key):
        return self.config.get(key)

    def __setitem__(self, key, value):
        self.config[key] = value
        self.save_config()
