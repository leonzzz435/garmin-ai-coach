import logging
import os
from pathlib import Path
from typing import Callable, Optional

import garth
from garminconnect import Garmin
import requests

logger = logging.getLogger(__name__)


class GarminConnectClient:
    """
    Thin wrapper around python-garminconnect that adds MFA support via `garth`
    and persists tokens so you don't need to re-authenticate every run.
    """

    def __init__(self, token_dir: Optional[str] = None):
        """
        :param token_dir: Directory to store Garmin OAuth tokens (used by 'garth').
                         Defaults to $GARMINCONNECT_TOKENS or $GARTH_HOME or ~/.garminconnect.
        """
        self._client: Garmin | None = None
        # Where garth will load/save tokens (OAuth1 + OAuth2)
        self._token_dir = Path(
            token_dir
            or os.getenv("GARMINCONNECT_TOKENS")
            or os.getenv("GARTH_HOME")
            or os.path.expanduser("~/.garminconnect")
        )

    def _try_resume_tokens(self, email: str, password: str, mfa_callback: Optional[Callable[[], str]]) -> bool:
        """
        Try to resume tokens from disk. Do not introspect garth internals; simply
        resume and let downstream login detect if tokens are actually usable.
        """
        try:
            garth.resume(str(self._token_dir))
            logger.info("Resumed existing Garmin OAuth tokens from %s", self._token_dir)
            return True
        except Exception as e:
            logger.info("No valid tokens found; need fresh login (%s)", e)
            return False

    def _fresh_login(self, email: str, password: str, mfa_callback: Optional[Callable[[], str]]) -> None:
        try:
            if mfa_callback is not None:
                code = mfa_callback()
                # Try common signatures across garth versions
                try:
                    garth.login(email, password, otp=code)  # most versions
                except TypeError:
                    garth.login(email, password, otp_callback=lambda: code)  # fallback
            else:
                garth.login(email, password)
            garth.save(str(self._token_dir))
            logger.info("Saved Garmin OAuth tokens to %s after fresh login", self._token_dir)
        except requests.HTTPError as http_err:
            body = getattr(http_err.response, "text", "")
            logger.error("Garmin login HTTP error: %s; body=%s", http_err, body[:500])
            raise
        except Exception as e:
            logger.error("Garmin login failed: %s", e)
            raise

    def connect(
        self,
        email: str,
        password: str,
        mfa_callback: Optional[Callable[[], str]] = None,
    ) -> None:
        """
        Establish an authenticated Garmin Connect session with MFA support.

        Flow:
          1) Try to resume existing tokens (avoids MFA/password if still valid).
          2) If none/invalid or refresh fails, perform a fresh login; garth will prompt for MFA or
             call `mfa_callback` if provided.
          3) Save tokens for future runs.
          4) Initialize Garmin client, which reuses garth's session.

        :param email: Garmin account email
        :param password: Garmin account password
        :param mfa_callback: Optional callable returning an MFA code string.
        """
        try:
            logger.info("Initializing Garmin Connect client (with MFA support)")
            # Ensure token directory exists
            self._token_dir.mkdir(parents=True, exist_ok=True)

            # 1) Try to resume existing tokens (valid ~1 year), refresh if expired
            resumed = self._try_resume_tokens(email, password, mfa_callback)
            if not resumed:
                # 2) Fresh login; garth will handle MFA (OTP)
                logger.info("Performing fresh login due to missing or expired tokens")
                self._fresh_login(email, password, mfa_callback)

            # 4) Initialize python-garminconnect client (reuses garth's session under the hood)
            # IMPORTANT: Do NOT pass email/password once garth has authenticated; let it reuse tokens.
            self._client = Garmin()
            try:
                # Always point garminconnect to the same token directory used by garth
                self._client.login(tokenstore=str(self._token_dir))
            except requests.HTTPError as http_err:
                status = getattr(getattr(http_err, "response", None), "status_code", None)
                body = getattr(http_err.response, "text", "")
                if status in (401, 403):
                    logger.info("Token resume rejected by server (%s). Performing fresh login and retry…", status)
                    self._fresh_login(email, password, mfa_callback)
                    # Retry once with newly saved tokens
                    self._client.login(tokenstore=str(self._token_dir))
                else:
                    logger.error("Garmin client login HTTP error: %s; body=%s", http_err, body[:500])
                    raise
            # Optional lightweight ping to confirm session; if unauthorized, re-login once.
            try:
                if hasattr(self._client, "get_full_name"):
                    _ = self._client.get_full_name()
            except requests.HTTPError as http_err:
                status = getattr(getattr(http_err, "response", None), "status_code", None)
                if status in (401, 403):
                    logger.info("Session ping unauthorized (%s). Performing fresh login and retry…", status)
                    self._fresh_login(email, password, mfa_callback)
                    self._client.login(tokenstore=str(self._token_dir))
            logger.info("Successfully connected to Garmin Connect")
        except Exception as e:
            logger.error("Failed to connect to Garmin Connect: %s", e)
            raise

    @property
    def client(self) -> Garmin | None:
        return self._client

    def disconnect(self) -> None:
        """
        Clear the in-memory client reference. Garth tokens remain on disk, so
        future sessions won't require MFA again unless tokens expire or are revoked.
        """
        if self._client:
            self._client = None
            logger.info("Disconnected from Garmin Connect")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, _exc_val, _exc_tb):
        self.disconnect()
