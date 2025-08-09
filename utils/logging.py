import json
import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


class StructuredFormatter(logging.Formatter):

    def __init__(self):
        super().__init__()
        self.hostname = os.uname().nodename

    def format(self, record: logging.LogRecord) -> str:
        # Base log data
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'message': record.getMessage(),
            'hostname': self.hostname,
        }

        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': self.formatException(record.exc_info),
            }

        # Add extra fields if present
        if hasattr(record, 'extra_fields'):
            log_data.update(record.extra_fields)

        return json.dumps(log_data)


def setup_logging(
    log_dir: str | None = None,
    level: int = logging.INFO,
    max_size: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    console: bool = True,
) -> None:
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear any existing handlers
    root_logger.handlers.clear()

    # Create structured formatter
    formatter = StructuredFormatter()

    # Add file handler with rotation if log_dir is specified
    if log_dir:
        log_dir_path = Path(log_dir)
        log_dir_path.mkdir(parents=True, exist_ok=True)

        # Ensure log directory permissions are restricted
        os.chmod(log_dir_path, 0o700)

        log_file = log_dir_path / 'app.log'
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_file, maxBytes=max_size, backupCount=backup_count, mode='a'
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        # Ensure log file permissions are restricted
        os.chmod(log_file, 0o600)

    # Add console handler if requested
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)


def log_with_context(
    logger: logging.Logger, level: int, msg: str, context: dict[str, Any] | None = None, **kwargs
) -> None:
    extra = kwargs.get('extra', {})
    if context:
        extra['extra_fields'] = context
    kwargs['extra'] = extra
    logger.log(level, msg, **kwargs)


# Example usage:
# setup_logging(log_dir='/var/log/myapp', level=logging.INFO)
# log_with_context(logger, logging.INFO, "User logged in",
