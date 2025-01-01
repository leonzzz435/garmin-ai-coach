"""Base classes for secure storage functionality."""

import os
import json
import logging
from pathlib import Path
from typing import Any, Optional
from cryptography.fernet import Fernet, InvalidToken

# Configure logging
logger = logging.getLogger(__name__)

class SecurityError(Exception):
    """Base exception for security-related errors."""
    pass

class StorageError(SecurityError):
    """Exception for storage-related errors."""
    pass

class SecureStorageBase:
    """Base class for secure storage implementations."""
    
    def __init__(self, user_id: str, storage_type: str):
        """
        Initialize secure storage for a specific user and type.
        
        Args:
            user_id: Unique identifier for the user
            storage_type: Type of storage (e.g., 'credentials', 'reports')
            
        Raises:
            StorageError: If storage setup fails
        """
        self.user_id = str(user_id)
        self.storage_type = storage_type
        self._setup_storage()
    
    def _setup_storage(self) -> None:
        """
        Set up the secure storage directory structure.
        
        Raises:
            StorageError: If directory creation or permissions setup fails
        """
        try:
            # Create secure storage directory in user's home
            storage_dir = Path.home() / '.garmin_bot' / self.storage_type
            logger.debug(f"Setting up storage in directory: {storage_dir}")
            
            # Create directory if it doesn't exist
            if not storage_dir.exists():
                logger.info(f"Creating storage directory: {storage_dir}")
                storage_dir.mkdir(parents=True, exist_ok=True)
            
            # Verify/fix parent directory permissions
            parent_mode = os.stat(storage_dir.parent).st_mode & 0o777
            if parent_mode != 0o700:
                logger.warning(f"Fixing parent directory permissions: {oct(parent_mode)} -> 0o700")
                os.chmod(storage_dir.parent, 0o700)
            
            # Verify/fix storage directory permissions
            storage_mode = os.stat(storage_dir).st_mode & 0o777
            if storage_mode != 0o700:
                logger.warning(f"Fixing storage directory permissions: {oct(storage_mode)} -> 0o700")
                os.chmod(storage_dir, 0o700)
            
            # Set up user-specific encrypted file
            self.user_file = storage_dir / f'{self.user_id}.enc'
            logger.debug(f"User file path: {self.user_file}")
            
            # Set up encryption
            key_file = storage_dir / '.key'
            if not key_file.exists():
                logger.info("Generating new encryption key")
                key = Fernet.generate_key()
                key_file.write_bytes(key)
                os.chmod(key_file, 0o600)
            else:
                logger.debug("Loading existing encryption key")
                key = key_file.read_bytes()
                
                # Verify key file permissions
                key_mode = os.stat(key_file).st_mode & 0o777
                if key_mode != 0o600:
                    logger.warning(f"Fixing key file permissions: {oct(key_mode)} -> 0o600")
                    os.chmod(key_file, 0o600)
            
            self.cipher_suite = Fernet(key)
            logger.info("Storage setup completed successfully")
            
        except Exception as e:
            error_msg = f"Failed to setup secure storage: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise StorageError(error_msg) from e
    
    def _encrypt(self, data: Any) -> bytes:
        """
        Encrypt data using Fernet encryption.
        
        Args:
            data: Data to encrypt (must be JSON serializable)
            
        Returns:
            bytes: Encrypted data
            
        Raises:
            StorageError: If encryption fails
        """
        try:
            logger.debug("Encrypting data")
            logger.debug(f"Data before serialization: {data}")
            
            # Serialize to JSON
            json_data = json.dumps(data)
            logger.debug(f"Serialized JSON: {json_data}")
            
            # Encrypt
            encoded_data = json_data.encode()
            encrypted_data = self.cipher_suite.encrypt(encoded_data)
            logger.debug(f"Data encrypted successfully ({len(encrypted_data)} bytes)")
            
            return encrypted_data
            
        except json.JSONEncodeError as e:
            error_msg = f"Failed to serialize data to JSON: {str(e)}"
            logger.error(error_msg)
            logger.debug(f"Problematic data: {data}")
            raise StorageError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to encrypt data: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise StorageError(error_msg) from e
    
    def _decrypt(self, encrypted_data: bytes) -> Any:
        """
        Decrypt data using Fernet encryption.
        
        Args:
            encrypted_data: Data to decrypt
            
        Returns:
            Any: Decrypted data
            
        Raises:
            StorageError: If decryption fails
        """
        try:
            logger.debug(f"Decrypting data ({len(encrypted_data)} bytes)")
            
            # Decrypt
            decrypted_bytes = self.cipher_suite.decrypt(encrypted_data)
            decrypted_str = decrypted_bytes.decode()
            logger.debug(f"Decrypted string: {decrypted_str}")
            
            # Parse JSON
            parsed_data = json.loads(decrypted_str)
            logger.debug(f"Successfully parsed JSON: {parsed_data}")
            
            return parsed_data
            
        except InvalidToken as e:
            error_msg = "Invalid encryption token or corrupted data"
            logger.error(error_msg)
            raise StorageError(error_msg) from e
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse decrypted data as JSON: {str(e)}"
            logger.error(error_msg)
            logger.debug(f"Problematic decrypted string: {decrypted_str}")
            raise StorageError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to decrypt data: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise StorageError(error_msg) from e
    
    def _write(self, data: Any) -> None:
        """
        Write encrypted data to storage.
        
        Args:
            data: Data to store (must be JSON serializable)
            
        Raises:
            StorageError: If write operation fails
        """
        try:
            logger.debug(f"Writing data to {self.user_file}")
            logger.debug(f"Data to write: {json.dumps(data, indent=2)}")
            
            # First ensure the directory exists and has correct permissions
            storage_dir = self.user_file.parent
            if not storage_dir.exists():
                logger.info(f"Creating storage directory: {storage_dir}")
                storage_dir.mkdir(parents=True, exist_ok=True)
                os.chmod(storage_dir, 0o700)
            
            # Encrypt and write the data
            encrypted_data = self._encrypt(data)
            self.user_file.write_bytes(encrypted_data)
            os.chmod(self.user_file, 0o600)
            
            # Force sync to disk
            logger.debug("Forcing file sync to disk")
            with open(self.user_file, 'rb') as f:
                os.fsync(f.fileno())
            
            # Verify the write by reading back
            logger.debug("Verifying write operation")
            verification = self._read()
            if verification != data:
                logger.error("Write verification failed - data mismatch")
                logger.debug(f"Original data: {json.dumps(data, indent=2)}")
                logger.debug(f"Read back data: {json.dumps(verification, indent=2)}")
                raise StorageError("Write verification failed - data mismatch")
            
            logger.debug("Write operation successful and verified")
            
        except Exception as e:
            error_msg = f"Failed to write data: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise StorageError(error_msg) from e
    
    def _read(self) -> Optional[Any]:
        """
        Read and decrypt data from storage.
        
        Returns:
            Optional[Any]: Decrypted data if file exists, None otherwise
            
        Raises:
            StorageError: If read operation fails
        """
        try:
            if not self.user_file.exists():
                logger.debug(f"Storage file does not exist: {self.user_file}")
                return None
                
            logger.debug(f"Reading data from {self.user_file}")
            
            # Verify file permissions
            mode = os.stat(self.user_file).st_mode & 0o777
            if mode != 0o600:
                logger.warning(f"Incorrect file permissions: {oct(mode)}, fixing...")
                os.chmod(self.user_file, 0o600)
            
            encrypted_data = self.user_file.read_bytes()
            decrypted_data = self._decrypt(encrypted_data)
            logger.debug(f"Successfully read data: {json.dumps(decrypted_data, indent=2)}")
            return decrypted_data
            
        except Exception as e:
            error_msg = f"Failed to read data: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise StorageError(error_msg) from e
    
    def clear(self) -> bool:
        """
        Remove stored data.
        
        Returns:
            bool: True if successful or file didn't exist, False otherwise
            
        Raises:
            StorageError: If deletion fails
        """
        try:
            logger.info(f"Attempting to clear data file: {self.user_file}")
            
            if not self.user_file.exists():
                logger.debug("File does not exist, nothing to clear")
                return True
            
            # Read data before deletion for logging
            try:
                current_data = self._read()
                logger.debug(f"Current data before deletion: {json.dumps(current_data, indent=2)}")
            except Exception as e:
                logger.warning(f"Could not read current data before deletion: {e}")
            
            # Delete the file
            self.user_file.unlink()
            logger.info("File deletion initiated")
            
            # Force sync the parent directory to ensure deletion is persisted
            logger.debug("Forcing directory sync to ensure deletion is persisted")
            dir_fd = os.open(str(self.user_file.parent), os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
            
            # Verify deletion
            if self.user_file.exists():
                error_msg = "File still exists after deletion"
                logger.error(error_msg)
                raise StorageError(error_msg)
                
            logger.info("File successfully deleted and verified")
            
            # Try to read to verify it's gone
            verification = self._read()
            if verification is not None:
                error_msg = "Data still readable after deletion"
                logger.error(f"Verification data: {json.dumps(verification, indent=2)}")
                raise StorageError(error_msg)
            
            logger.info("Data successfully cleared and verified")
            return True
            
        except Exception as e:
            error_msg = f"Failed to clear data: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise StorageError(error_msg) from e
