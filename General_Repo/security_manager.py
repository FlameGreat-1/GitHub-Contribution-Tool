import os
import hashlib
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import jwt
import secrets
import re
from datetime import datetime, timedelta
import redis
import time
import magic
import tempfile
import subprocess
from PIL import Image
from pdf2image import convert_from_bytes
import zipfile
import xml.etree.ElementTree as ET
import csv
import json

class SecurityManager:
    def __init__(self, logger, redis_host='localhost', redis_port=6379, redis_db=0):
        self.logger = logger
        self.key = self.load_or_generate_key()
        self.fernet = Fernet(self.key)
        self.redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db)

    def load_or_generate_key(self):
        key_file = '.encryption_key'
        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(key)
            os.chmod(key_file, 0o600)  # Restrict file permissions
            return key

    def encrypt_data(self, data):
        try:
            encrypted_data = self.fernet.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted_data).decode()
        except Exception as e:
            self.logger.error(f"Encryption failed: {str(e)}")
            raise

    def decrypt_data(self, encrypted_data):
        try:
            decrypted_data = self.fernet.decrypt(base64.urlsafe_b64decode(encrypted_data))
            return decrypted_data.decode()
        except Exception as e:
            self.logger.error(f"Decryption failed: {str(e)}")
            raise

    def hash_password(self, password):
        salt = os.urandom(32)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return f"{salt.hex()}:{key.decode()}"

    def verify_password(self, stored_password, provided_password):
        salt, key = stored_password.split(':')
        salt = bytes.fromhex(salt)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        key_to_check = base64.urlsafe_b64encode(kdf.derive(provided_password.encode())).decode()
        return secrets.compare_digest(key, key_to_check)

    def generate_token(self, user_id, expiration_hours=24):
        payload = {
            'user_id': user_id,
            'exp': datetime.utcnow() + timedelta(hours=expiration_hours)
        }
        return jwt.encode(payload, self.key, algorithm='HS256')

    def validate_token(self, token):
        try:
            payload = jwt.decode(token, self.key, algorithms=['HS256'])
            return payload['user_id']
        except jwt.ExpiredSignatureError:
            self.logger.warning("Token has expired")
            return None
        except jwt.InvalidTokenError:
            self.logger.warning("Invalid token")
            return None

    def sanitize_input(self, input_string):
        # Remove any potentially dangerous characters or patterns
        sanitized = re.sub(r'[<>&;]', '', input_string)
        return sanitized

    def validate_email(self, email):
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(email_regex, email) is not None

    def generate_secure_filename(self, filename):
        # Remove any potentially dangerous characters and limit length
        safe_filename = re.sub(r'[^a-zA-Z0-9._-]', '', filename)
        return safe_filename[:255]  # Limit to 255 characters

    def secure_headers(self):
        return {
            'X-Frame-Options': 'SAMEORIGIN',
            'X-XSS-Protection': '1; mode=block',
            'X-Content-Type-Options': 'nosniff',
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
            'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline';"
        }

    def generate_csrf_token(self):
        return secrets.token_hex(32)

    def validate_csrf_token(self, session_token, form_token):
        return secrets.compare_digest(session_token, form_token)

    def rate_limit(self, key, limit=100, period=3600):
        """
        Implement rate limiting using a sliding window algorithm with Redis.
        
        :param key: Unique identifier for the client (e.g., IP address, API key)
        :param limit: Maximum number of requests allowed in the period
        :param period: Time period in seconds
        :return: Tuple (bool, dict) - (True if request is allowed, rate limit info)
        """
        try:
            current_time = int(time.time())
            redis_key = f"rate_limit:{key}"

            # Remove old entries outside the current period
            self.redis_client.zremrangebyscore(redis_key, 0, current_time - period)

            # Count the number of requests in the current period
            request_count = self.redis_client.zcard(redis_key)

            if request_count < limit:
                # Add the current request to the sorted set
                self.redis_client.zadd(redis_key, {str(current_time): current_time})
                # Set the expiration for the key to ensure cleanup
                self.redis_client.expire(redis_key, period)
                allowed = True
            else:
                allowed = False

            # Get the oldest request timestamp in the current window
            oldest_request = self.redis_client.zrange(redis_key, 0, 0, withscores=True)
            if oldest_request:
                reset_time = int(oldest_request[0][1]) + period
            else:
                reset_time = current_time + period

            rate_limit_info = {
                "limit": limit,
                "remaining": max(0, limit - request_count),
                "reset": datetime.fromtimestamp(reset_time).isoformat(),
                "request_count": request_count
            }

            self.logger.info(f"Rate limit check for {key}: allowed={allowed}, info={rate_limit_info}")
            return allowed, rate_limit_info

        except redis.RedisError as e:
            self.logger.error(f"Redis error in rate limiting: {str(e)}")
            # Fail open: allow the request if Redis is unavailable
            return True, {"error": "Rate limiting unavailable"}

    def reset_rate_limit(self, key):
        """
        Reset the rate limit for a given key.
        
        :param key: Unique identifier for the client
        """
        try:
            redis_key = f"rate_limit:{key}"
            self.redis_client.delete(redis_key)
            self.logger.info(f"Rate limit reset for {key}")
        except redis.RedisError as e:
            self.logger.error(f"Redis error in resetting rate limit: {str(e)}")

    def log_security_event(self, event_type, details):
        self.logger.warning(f"Security Event: {event_type} - {details}")

    def check_password_strength(self, password):
        if len(password) < 12:
            return False
        if not re.search(r'[A-Z]', password):
            return False
        if not re.search(r'[a-z]', password):
            return False
        if not re.search(r'\d', password):
            return False
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            return False
        return True

    def generate_secure_password(self):
        alphabet = string.ascii_letters + string.digits + string.punctuation
        while True:
            password = ''.join(secrets.choice(alphabet) for i in range(16))
            if self.check_password_strength(password):
                return password

    def secure_file_upload(self, file, allowed_extensions, max_size_bytes, upload_dir):
        """
        Securely handle file uploads with extensive validation and scanning.

        :param file: File object to be uploaded
        :param allowed_extensions: List of allowed file extensions
        :param max_size_bytes: Maximum allowed file size in bytes
        :param upload_dir: Directory where the file will be saved
        :return: Tuple (secure_filename, file_path)
        """
        try:
            # Generate a secure filename
            original_filename = file.filename
            filename = self.generate_secure_filename(original_filename)
            
            # Check file extension
            ext = os.path.splitext(filename)[1][1:].lower()
            if ext not in allowed_extensions:
                raise ValueError(f"File type '{ext}' is not allowed")

            # Check file size
            file_content = file.read()
            if len(file_content) > max_size_bytes:
                raise ValueError(f"File size exceeds the maximum allowed size of {max_size_bytes} bytes")

            # Create a temporary file
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(file_content)
                temp_file_path = temp_file.name

            # Verify file type using magic numbers
            mime_type = magic.from_file(temp_file_path, mime=True)
            if not self.is_mime_type_allowed(mime_type, allowed_extensions):
                os.unlink(temp_file_path)
                raise ValueError(f"File type '{mime_type}' does not match the expected type")

            # Scan for viruses
            if not self.scan_file_for_viruses(temp_file_path):
                os.unlink(temp_file_path)
                raise ValueError("File failed virus scan")

            # Validate file content based on type
            if not self.validate_file_content(temp_file_path, mime_type):
                os.unlink(temp_file_path)
                raise ValueError("File content validation failed")

            # Calculate file hash
            file_hash = self.calculate_file_hash(temp_file_path)

            # Generate a unique filename using the hash
            secure_filename = f"{file_hash[:10]}_{filename}"
            file_path = os.path.join(upload_dir, secure_filename)

            # Move the file to the upload directory
            os.rename(temp_file_path, file_path)

            # Set appropriate permissions
            os.chmod(file_path, 0o644)

            self.logger.info(f"File '{original_filename}' securely uploaded as '{secure_filename}'")
            return secure_filename, file_path

        except Exception as e:
            self.logger.error(f"Secure file upload failed: {str(e)}")
            raise

    def is_mime_type_allowed(self, mime_type, allowed_extensions):
        mime_to_ext = {
            # Images
            'image/jpeg': ['jpg', 'jpeg', 'jpe'],
            'image/png': ['png'],
            'image/gif': ['gif'],
            'image/bmp': ['bmp'],
            'image/webp': ['webp'],
            'image/tiff': ['tif', 'tiff'],
            'image/svg+xml': ['svg', 'svgz'],

              # Documents
            'application/pdf': ['pdf'],
            'application/msword': ['doc'],
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['docx'],
            'application/vnd.ms-excel': ['xls'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['xlsx'],
            'application/vnd.ms-powerpoint': ['ppt'],
            'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['pptx'],
            'text/plain': ['txt', 'text'],
            'application/rtf': ['rtf'],

              # Audio
            'audio/mpeg': ['mp3'],
            'audio/x-wav': ['wav'],
            'audio/ogg': ['ogg'],
            'audio/aac': ['aac'],
            'audio/midi': ['mid', 'midi'],

             # Video
            'video/mp4': ['mp4'],
            'video/mpeg': ['mpeg', 'mpg'],
            'video/quicktime': ['mov'],
            'video/x-msvideo': ['avi'],
            'video/x-ms-wmv': ['wmv'],
            'video/webm': ['webm'],

             # Archives
            'application/zip': ['zip'],
            'application/x-rar-compressed': ['rar'],
            'application/x-tar': ['tar'],
            'application/gzip': ['gz'],
            'application/x-7z-compressed': ['7z'],

             # Programming
            'text/html': ['html', 'htm'],
            'text/css': ['css'],
            'application/javascript': ['js'],
            'application/json': ['json'],
            'application/xml': ['xml'],
            'text/x-python': ['py'],
            'text/x-java-source': ['java'],
            'text/x-c': ['c', 'cpp', 'h'],

             # Fonts
            'font/ttf': ['ttf'],
            'font/otf': ['otf'],
            'font/woff': ['woff'],
            'font/woff2': ['woff2'],

             # Others
            'application/octet-stream': ['bin'],
            'text/csv': ['csv'],
            'application/vnd.android.package-archive': ['apk'],
        }

        for allowed_ext in allowed_extensions:
            if allowed_ext in mime_to_ext.get(mime_type, []):
                return True
        return False


    def scan_file_for_viruses(self, file_path):
        try:
            # This assumes you have ClamAV installed and clamscan available
            result = subprocess.run(['clamscan', file_path], capture_output=True, text=True)
            return result.returncode == 0
        except subprocess.CalledProcessError:
            self.logger.error("Virus scan failed")
            return False

    def validate_file_content(self, file_path, mime_type):
        try:
            if mime_type.startswith('image/'):
                return self._validate_image(file_path)
            elif mime_type == 'application/pdf':
                return self._validate_pdf(file_path)
            elif mime_type in ['application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
                return self._validate_office_document(file_path)
            elif mime_type in ['application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']:
                return self._validate_office_document(file_path)
            elif mime_type in ['application/vnd.ms-powerpoint', 'application/vnd.openxmlformats-officedocument.presentationml.presentation']:
                return self._validate_office_document(file_path)
            elif mime_type == 'text/plain':
                return self._validate_text_file(file_path)
            elif mime_type in ['audio/mpeg', 'audio/x-wav', 'audio/ogg', 'audio/aac']:
                return self._validate_audio_file(file_path)
            elif mime_type in ['video/mp4', 'video/mpeg', 'video/quicktime', 'video/x-msvideo']:
                return self._validate_video_file(file_path)
            elif mime_type in ['application/zip', 'application/x-rar-compressed', 'application/x-tar', 'application/gzip']:
                return self._validate_archive(file_path)
            elif mime_type == 'text/html':
                return self._validate_html(file_path)
            elif mime_type == 'application/json':
                return self._validate_json(file_path)
            elif mime_type == 'text/csv':
                return self._validate_csv(file_path)
            else:
                self.logger.warning(f"No specific validation for MIME type: {mime_type}")
                return True  # Allow file types without specific validation
        except Exception as e:
            self.logger.error(f"File content validation failed: {str(e)}")
            return False

    def _validate_image(self, file_path):
        try:
            with Image.open(file_path) as img:
                img.verify()
                img.load()  # Try to load the image data
                if img.format.lower() not in ['jpeg', 'png', 'gif', 'bmp', 'tiff']:
                    raise ValueError("Unsupported image format")
                
            return True
        except Exception as e:
            self.logger.error(f"Image validation failed: {str(e)}")
            return False

    def _validate_pdf(self, file_path):
        try:
            # Attempt to read the first page of the PDF
            convert_from_bytes(open(file_path, 'rb').read(), first_page=1, last_page=1)

            return True
        except Exception as e:
            self.logger.error(f"PDF validation failed: {str(e)}")
            return False

    def _validate_office_document(self, file_path):
        try:
            # Check if it's a valid zip file (Office documents are zip archives)
            if not zipfile.is_zipfile(file_path):
                raise ValueError("Not a valid Office document")
            
            with zipfile.ZipFile(file_path) as zf:
                # Check for specific files that should be present in Office documents
                if '[Content_Types].xml' not in zf.namelist():
                    raise ValueError("Missing required Office document structure")
                
            return True
        except Exception as e:
            self.logger.error(f"Office document validation failed: {str(e)}")
            return False

    def _validate_text_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                f.read()  # Attempt to read the entire file
            return True
        except Exception as e:
            self.logger.error(f"Text file validation failed: {str(e)}")
            return False

    def _validate_audio_file(self, file_path):
        try:
            # Use ffprobe to get information about the audio file
            result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', file_path], capture_output=True, text=True)
            if result.returncode != 0:
                raise ValueError("Not a valid audio file")
            
            return True
        except Exception as e:
            self.logger.error(f"Audio file validation failed: {str(e)}")
            return False

    def _validate_video_file(self, file_path):
        try:
            # Use ffprobe to get information about the video file
            result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', file_path], capture_output=True, text=True)
            if result.returncode != 0:
                raise ValueError("Not a valid video file")
            
            return True
        except Exception as e:
            self.logger.error(f"Video file validation failed: {str(e)}")
            return False

    def _validate_archive(self, file_path):
        try:
            if zipfile.is_zipfile(file_path):
                with zipfile.ZipFile(file_path) as zf:
                    # Check for suspicious file names or excessive size
                    for info in zf.infolist():
                        if '..' in info.filename or info.file_size > 100_000_000:  # 100MB limit per file
                            raise ValueError("Suspicious archive content")
            elif tarfile.is_tarfile(file_path):
                with tarfile.open(file_path) as tf:
                    for member in tf.getmembers():
                        if '..' in member.name or member.size > 100_000_000:  # 100MB limit per file
                            raise ValueError("Suspicious archive content")
            else:
                raise ValueError("Unsupported archive format")
            return True
        except Exception as e:
            self.logger.error(f"Archive validation failed: {str(e)}")
            return False

    def _validate_html(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            # Basic check for HTML structure
            if not content.strip().startswith('<!DOCTYPE html>') and not content.strip().startswith('<html'):
                raise ValueError("Not a valid HTML file")

            return True
        except Exception as e:
            self.logger.error(f"HTML validation failed: {str(e)}")
            return False

    def _validate_json(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                json.load(f)  # Attempt to parse JSON
            return True
        except Exception as e:
            self.logger.error(f"JSON validation failed: {str(e)}")
            return False

    def _validate_csv(self, file_path):
        try:
            with open(file_path, 'r', newline='', encoding='utf-8') as f:
                csv.reader(f)  # Attempt to read CSV

            return True
        except Exception as e:
            self.logger.error(f"CSV validation failed: {str(e)}")
            return False

    def calculate_file_hash(self, file_path):
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def audit_log(self, user, action, resource):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'user': user,
            'action': action,
            'resource': resource,
            'ip_address': request.remote_addr  # for a web context
        }
        self.logger.info(f"Audit Log: {json.dumps(log_entry)}")

