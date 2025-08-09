
import datetime
from typing import Optional, Tuple
from .base import SecureStorageBase, StorageError

class SecureReportManager(SecureStorageBase):
    
    def __init__(self, user_id: str):
        super().__init__(user_id, 'reports')

    def store_report(self, report: str) -> bool:
        try:
            data = {
                'report': report,
                'timestamp': datetime.datetime.now().isoformat(),
                'user_id': self.user_id
            }
            self._write(data)
            return True
        except StorageError:
            raise
        except Exception as e:
            raise StorageError(f"Failed to store report: {str(e)}") from e

    def clear_report(self) -> bool:
        try:
            if self.user_file.exists():
                self.user_file.unlink()
            return True
        except Exception as e:
            raise StorageError(f"Failed to clear report: {str(e)}") from e

    def get_report(self) -> Optional[Tuple[str, datetime.datetime]]:
        try:
            data = self._read()
            if not data:
                return None
            
            if data['user_id'] != self.user_id:
                return None

            timestamp = datetime.datetime.fromisoformat(data['timestamp'])
            return data['report'], timestamp
        except StorageError:
            raise
        except Exception as e:
            raise StorageError(f"Failed to retrieve report: {str(e)}") from e
