import logging
import os
from collections.abc import Callable
from pathlib import Path

import garth
import requests
from garminconnect import Garmin

logger = logging.getLogger(__name__)


class GarminConnectClient:
    def __init__(self, token_dir: str | None = None):
        self._client: Garmin | None = None
        self._token_dir = Path(
            token_dir
            or os.getenv("GARMINCONNECT_TOKENS")
            or os.getenv("GARTH_HOME")
            or os.path.expanduser("~/.garminconnect")
        )

    def _try_resume_tokens(self) -> bool:
        try:
            garth.resume(str(self._token_dir))
            logger.info("Resumed existing Garmin OAuth tokens from %s", self._token_dir)
            return True
        except Exception as exc:
            logger.info("No valid tokens found; need fresh login (%s)", exc)
            return False

    def _fresh_login(
        self,
        email: str,
        password: str,
        mfa_callback: Callable[[], str] | None,
    ) -> None:
        try:
            if mfa_callback is not None:
                code = mfa_callback()
                try:
                    garth.login(email, password, otp=code)
                except TypeError:
                    garth.login(email, password, otp_callback=lambda: code)
            else:
                garth.login(email, password)
            garth.save(str(self._token_dir))
            logger.info("Saved Garmin OAuth tokens to %s after fresh login", self._token_dir)
        except requests.HTTPError as http_err:
            body = getattr(http_err.response, "text", "")
            logger.error("Garmin login HTTP error: %s; body=%s", http_err, body[:500])
            raise
        except Exception as exc:
            logger.error("Garmin login failed: %s", exc)
            raise

    def connect(
        self,
        email: str,
        password: str,
        mfa_callback: Callable[[], str] | None = None,
    ) -> None:
        try:
            logger.info("Initializing Garmin Connect client")
            self._token_dir.mkdir(parents=True, exist_ok=True)

            resumed = self._try_resume_tokens()
            if not resumed:
                logger.info("Performing fresh login due to missing or expired tokens")
                self._fresh_login(email, password, mfa_callback)

            self._client = Garmin()
            try:
                self._client.login(tokenstore=str(self._token_dir))
            except requests.HTTPError as http_err:
                status = getattr(getattr(http_err, "response", None), "status_code", None)
                body = getattr(http_err.response, "text", "")
                if status in (401, 403):
                    logger.info("Token resume rejected by server (%s). Performing fresh login", status)
                    self._fresh_login(email, password, mfa_callback)
                    self._client.login(tokenstore=str(self._token_dir))
                else:
                    logger.error("Garmin client login HTTP error: %s; body=%s", http_err, body[:500])
                    raise
            try:
                if hasattr(self._client, "get_full_name"):
                    _ = self._client.get_full_name()
            except requests.HTTPError as http_err:
                status = getattr(getattr(http_err, "response", None), "status_code", None)
                if status in (401, 403):
                    logger.info("Session ping unauthorized (%s). Performing fresh login", status)
                    self._fresh_login(email, password, mfa_callback)
                    self._client.login(tokenstore=str(self._token_dir))
            logger.info("Successfully connected to Garmin Connect")
        except Exception as exc:
            logger.error("Failed to connect to Garmin Connect: %s", exc)
            raise

    @property
    def client(self) -> Garmin | None:
        return self._client

    def disconnect(self) -> None:
        if self._client:
            self._client = None
            logger.info("Disconnected from Garmin Connect")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, _exc_val, _exc_tb):
        self.disconnect()
