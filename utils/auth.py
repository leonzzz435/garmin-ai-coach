import os
import json
import datetime
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

class SecureStorageBase:
    def __init__(self, user_id: str, storage_type: str):
        """Initialize the secure storage manager for a specific user."""
        self.user_id = str(user_id)
        self.storage_type = storage_type
        self._setup_storage()
        
    def _setup_storage(self):
        """Set up the secure storage directory structure."""
        # Create secure storage directory in user's home
        storage_dir = Path.home() / '.garmin_bot' / self.storage_type
        storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Ensure directory permissions are restricted
        os.chmod(storage_dir.parent, 0o700)
        os.chmod(storage_dir, 0o700)
        
        self.user_file = storage_dir / f'{self.user_id}.enc'
        
        # Generate or load encryption key
        key_file = storage_dir / '.key'
        if not key_file.exists():
            key = Fernet.generate_key()
            key_file.write_bytes(key)
            os.chmod(key_file, 0o600)
        else:
            key = key_file.read_bytes()
            
        self.cipher_suite = Fernet(key)

class SecureCredentialManager(SecureStorageBase):
    def __init__(self, user_id: str):
        """Initialize the credential manager for a specific user."""
        super().__init__(user_id, 'credentials')

    def store_credentials(self, email: str, password: str) -> bool:
        """
        Securely store user credentials.
        Returns True if successful, False otherwise.
        """
        try:
            data = {
                'email': email,
                'password': password,
                'user_id': self.user_id
            }
            encrypted_data = self.cipher_suite.encrypt(json.dumps(data).encode())
            self.user_file.write_bytes(encrypted_data)
            os.chmod(self.user_file, 0o600)
            return True
        except Exception as e:
            print(f"Error storing credentials: {e}")
            return False

    def get_credentials(self) -> tuple[str, str] | None:
        """
        Retrieve stored credentials.
        Returns (email, password) tuple if found, None otherwise.
        """
        try:
            if not self.user_file.exists():
                return None
            
            encrypted_data = self.user_file.read_bytes()
            data = json.loads(self.cipher_suite.decrypt(encrypted_data))
            
            if data['user_id'] != self.user_id:
                return None
                
            return data['email'], data['password']
        except Exception as e:
            print(f"Error retrieving credentials: {e}")
            return None

    def clear_credentials(self) -> bool:
        """
        Remove stored credentials.
        Returns True if successful, False otherwise.
        """
        try:
            if self.user_file.exists():
                self.user_file.unlink()
            return True
        except Exception as e:
            print(f"Error clearing credentials: {e}")
            return False

    def has_stored_credentials(self) -> bool:
        """Check if user has stored credentials."""
        return self.user_file.exists()

class SecureReportManager(SecureStorageBase):
    def __init__(self, user_id: str):
        """Initialize the report manager for a specific user."""
        super().__init__(user_id, 'reports')

    def store_report(self, report: str) -> bool:
        """
        Securely store user's latest report with timestamp.
        Returns True if successful, False otherwise.
        """
        try:
            data = {
                'report': report,
                'timestamp': datetime.datetime.now().isoformat(),
                'user_id': self.user_id
            }
            encrypted_data = self.cipher_suite.encrypt(json.dumps(data).encode())
            self.user_file.write_bytes(encrypted_data)
            os.chmod(self.user_file, 0o600)
            return True
        except Exception as e:
            print(f"Error storing report: {e}")
            return False

    def get_report(self) -> tuple[str, datetime.datetime] | None:
        """
        Retrieve stored report and its timestamp.
        Returns (report, timestamp) tuple if found and not expired, None otherwise.
        """
        try:
            if not self.user_file.exists():
                return None
            
            encrypted_data = self.user_file.read_bytes()
            data = json.loads(self.cipher_suite.decrypt(encrypted_data))
            
            if data['user_id'] != self.user_id:
                return None

            timestamp = datetime.datetime.fromisoformat(data['timestamp'])
            current_time = datetime.datetime.now()
            
            # Check if report is less than 12 hours old
            if (current_time - timestamp).total_seconds() < 43200:  # 12 hours
                return data['report'], timestamp
            
            return None
        except Exception as e:
            print(f"Error retrieving report: {e}")
            return None

    def clear_report(self) -> bool:
        """
        Remove stored report.
        Returns True if successful, False otherwise.
        """
        try:
            if self.user_file.exists():
                self.user_file.unlink()
            return True
        except Exception as e:
            print(f"Error clearing report: {e}")
            return False
