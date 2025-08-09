
from typing import Optional, Tuple
from .base import SecureStorageBase, StorageError

class SecureCredentialManager(SecureStorageBase):
    
    def __init__(self, user_id: str):
        super().__init__(user_id, 'credentials')

    def store_credentials(self, email: str, password: str) -> bool:
        try:
            data = {
                'email': email,
                'password': password,
                'user_id': self.user_id
            }
            self._write(data)
            return True
        except StorageError:
            raise
        except Exception as e:
            raise StorageError(f"Failed to store credentials: {str(e)}") from e

    def get_credentials(self) -> Optional[Tuple[str, str]]:
        try:
            data = self._read()
            if not data:
                return None
            
            if data['user_id'] != self.user_id:
                return None
                
            return data['email'], data['password']
        except StorageError:
            raise
        except Exception as e:
            raise StorageError(f"Failed to retrieve credentials: {str(e)}") from e

    def has_stored_credentials(self) -> bool:
        return self.user_file.exists()
