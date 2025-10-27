import pytest
import requests

import services.garmin.client as garmin_client_module
from services.garmin.client import GarminConnectClient


def make_http_error(status_code: int, body: str = "") -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status_code
    response._content = body.encode()
    return requests.HTTPError(response=response)


def test_connect_reuses_existing_tokens_without_login(monkeypatch, tmp_path):
    resume_calls = []
    monkeypatch.setattr(
        garmin_client_module.garth, "resume", lambda path: resume_calls.append(path)
    )
    garth_login_calls = []
    monkeypatch.setattr(
        garmin_client_module.garth,
        "login",
        lambda *args, **kwargs: garth_login_calls.append((args, kwargs)),
    )
    garth_save_calls = []
    monkeypatch.setattr(
        garmin_client_module.garth, "save", lambda path: garth_save_calls.append(path)
    )

    class StubGarmin:
        def __init__(self):
            self.login_attempts = 0

        def login(self, tokenstore: str) -> None:
            self.login_attempts += 1

        def get_full_name(self) -> str:
            return "Test User"

    monkeypatch.setattr(garmin_client_module, "Garmin", StubGarmin)

    client = GarminConnectClient(token_dir=tmp_path)
    client.connect("user@example.com", "secret")

    assert resume_calls == [str(tmp_path)]
    assert garth_login_calls == []
    assert garth_save_calls == []
    assert client.client.login_attempts == 1


def test_connect_performs_fresh_login_when_resume_fails(monkeypatch, tmp_path):
    def failing_resume(path: str) -> None:
        raise RuntimeError("missing tokens")

    monkeypatch.setattr(garmin_client_module.garth, "resume", failing_resume)

    garth_login_calls = []

    def garth_login(email: str, password: str, **kwargs) -> None:
        garth_login_calls.append((email, password, kwargs))

    monkeypatch.setattr(garmin_client_module.garth, "login", garth_login)

    garth_save_calls = []
    monkeypatch.setattr(
        garmin_client_module.garth, "save", lambda path: garth_save_calls.append(path)
    )

    class StubGarmin:
        def __init__(self):
            self.login_attempts = 0

        def login(self, tokenstore: str) -> None:
            self.login_attempts += 1

        def get_full_name(self) -> str:
            return "Test User"

    monkeypatch.setattr(garmin_client_module, "Garmin", StubGarmin)

    client = GarminConnectClient(token_dir=tmp_path)
    client.connect("user@example.com", "secret", mfa_callback=lambda: next(iter(["123456"])))

    assert len(garth_login_calls) == 1
    email, password, kwargs = garth_login_calls[0]
    assert email == "user@example.com"
    assert password == "secret"
    assert kwargs == {"otp": "123456"}
    assert garth_save_calls == [str(tmp_path)]
    assert client.client.login_attempts == 1


def test_connect_reauths_after_garmin_login_rejection(monkeypatch, tmp_path):
    monkeypatch.setattr(garmin_client_module.garth, "resume", lambda path: None)

    garth_login_kwargs = []

    def garth_login(_: str, __: str, **kwargs) -> None:
        garth_login_kwargs.append(kwargs)

    monkeypatch.setattr(garmin_client_module.garth, "login", garth_login)

    garth_save_calls = []
    monkeypatch.setattr(
        garmin_client_module.garth, "save", lambda path: garth_save_calls.append(path)
    )

    class RejectingOnceGarmin:
        def __init__(self):
            self.login_attempts = 0

        def login(self, tokenstore: str) -> None:
            self.login_attempts += 1
            if self.login_attempts == 1:
                raise make_http_error(401, "Unauthorized")

        def get_full_name(self) -> str:
            return "Test User"

    monkeypatch.setattr(garmin_client_module, "Garmin", RejectingOnceGarmin)

    codes = iter(["654321"])
    client = GarminConnectClient(token_dir=tmp_path)
    client.connect("user@example.com", "secret", mfa_callback=lambda: next(codes))

    assert len(garth_login_kwargs) == 1
    assert garth_login_kwargs[0] == {"otp": "654321"}
    assert garth_save_calls == [str(tmp_path)]
    assert client.client is not None
    assert client.client.login_attempts == 2


def test_connect_reauths_after_session_ping_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(garmin_client_module.garth, "resume", lambda path: None)

    garth_login_kwargs = []

    def garth_login(_: str, __: str, **kwargs) -> None:
        garth_login_kwargs.append(kwargs)

    monkeypatch.setattr(garmin_client_module.garth, "login", garth_login)

    garth_save_calls = []
    monkeypatch.setattr(
        garmin_client_module.garth, "save", lambda path: garth_save_calls.append(path)
    )

    class PingFailGarmin:
        def __init__(self):
            self.login_attempts = 0
            self.ping_attempts = 0

        def login(self, tokenstore: str) -> None:
            self.login_attempts += 1

        def get_full_name(self) -> str:
            self.ping_attempts += 1
            if self.ping_attempts == 1:
                raise make_http_error(403, "Forbidden")
            return "Test User"

    monkeypatch.setattr(garmin_client_module, "Garmin", PingFailGarmin)

    client = GarminConnectClient(token_dir=tmp_path)
    client.connect("user@example.com", "secret", mfa_callback=lambda: next(iter(["777777"])))

    assert len(garth_login_kwargs) == 1
    assert garth_login_kwargs[0] == {"otp": "777777"}
    assert garth_save_calls == [str(tmp_path)]
    assert client.client is not None
    assert client.client.login_attempts == 2
    assert client.client.ping_attempts == 1


def test_connect_handles_legacy_garth_signature(monkeypatch, tmp_path):
    def failing_resume(path: str) -> None:
        raise RuntimeError("missing tokens")

    monkeypatch.setattr(garmin_client_module.garth, "resume", failing_resume)

    garth_login_kwargs = []

    def garth_login(email: str, password: str, **kwargs) -> None:
        garth_login_kwargs.append(kwargs)
        if "otp" in kwargs:
            raise TypeError("legacy signature")

    monkeypatch.setattr(garmin_client_module.garth, "login", garth_login)

    garth_save_calls = []
    monkeypatch.setattr(
        garmin_client_module.garth, "save", lambda path: garth_save_calls.append(path)
    )

    class StubGarmin:
        def __init__(self):
            self.login_attempts = 0

        def login(self, tokenstore: str) -> None:
            self.login_attempts += 1

        def get_full_name(self) -> str:
            return "Test User"

    monkeypatch.setattr(garmin_client_module, "Garmin", StubGarmin)

    client = GarminConnectClient(token_dir=tmp_path)
    client.connect("user@example.com", "secret", mfa_callback=lambda: next(iter(["888888"])))

    assert len(garth_login_kwargs) == 2
    assert garth_login_kwargs[0] == {"otp": "888888"}
    assert "otp_callback" in garth_login_kwargs[1]
    assert callable(garth_login_kwargs[1]["otp_callback"])
    assert garth_save_calls == [str(tmp_path)]


def test_connect_handles_non_auth_http_errors(monkeypatch, tmp_path):
    monkeypatch.setattr(garmin_client_module.garth, "resume", lambda path: None)
    monkeypatch.setattr(garmin_client_module.garth, "login", lambda *args, **kwargs: None)
    monkeypatch.setattr(garmin_client_module.garth, "save", lambda path: None)

    class ErrorGarmin:
        def login(self, tokenstore: str) -> None:
            raise make_http_error(500, "Internal Server Error")

        def get_full_name(self) -> str:
            return "Test User"

    monkeypatch.setattr(garmin_client_module, "Garmin", ErrorGarmin)

    client = GarminConnectClient(token_dir=tmp_path)
    
    with pytest.raises(requests.HTTPError):
        client.connect("user@example.com", "secret")


def test_connect_handles_garmin_login_exception(monkeypatch, tmp_path):
    monkeypatch.setattr(garmin_client_module.garth, "resume", lambda path: None)
    monkeypatch.setattr(garmin_client_module.garth, "login", lambda *args, **kwargs: None)
    monkeypatch.setattr(garmin_client_module.garth, "save", lambda path: None)

    class ExceptionGarmin:
        def login(self, tokenstore: str) -> None:
            raise RuntimeError("Connection failed")

    monkeypatch.setattr(garmin_client_module, "Garmin", ExceptionGarmin)

    client = GarminConnectClient(token_dir=tmp_path)
    
    with pytest.raises(RuntimeError):
        client.connect("user@example.com", "secret")


def test_connect_handles_fresh_login_exception(monkeypatch, tmp_path):
    def failing_resume(path: str) -> None:
        raise RuntimeError("missing tokens")

    monkeypatch.setattr(garmin_client_module.garth, "resume", failing_resume)
    monkeypatch.setattr(
        garmin_client_module.garth, "login", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("Login failed"))
    )

    client = GarminConnectClient(token_dir=tmp_path)
    
    with pytest.raises(RuntimeError):
        client.connect("user@example.com", "secret")


def test_connect_without_mfa_callback(monkeypatch, tmp_path):
    def failing_resume(path: str) -> None:
        raise RuntimeError("missing tokens")

    monkeypatch.setattr(garmin_client_module.garth, "resume", failing_resume)

    garth_login_calls = []
    monkeypatch.setattr(
        garmin_client_module.garth, "login", lambda *args, **kwargs: garth_login_calls.append((args, kwargs))
    )
    monkeypatch.setattr(garmin_client_module.garth, "save", lambda path: None)

    class StubGarmin:
        def __init__(self):
            self.login_attempts = 0

        def login(self, tokenstore: str) -> None:
            self.login_attempts += 1

        def get_full_name(self) -> str:
            return "Test User"

    monkeypatch.setattr(garmin_client_module, "Garmin", StubGarmin)

    client = GarminConnectClient(token_dir=tmp_path)
    client.connect("user@example.com", "secret")

    assert len(garth_login_calls) == 1
    args, kwargs = garth_login_calls[0]
    assert len(args) == 2
    email, password = args
    assert email == "user@example.com"
    assert password == "secret"
    assert kwargs == {}


def test_disconnect_clears_client():
    client = GarminConnectClient()
    client._client = "mock_client"
    client.disconnect()
    assert client._client is None


def test_context_manager():
    client = GarminConnectClient()
    client._client = "mock_client"
    
    with client as context_client:
        assert context_client is client
        assert context_client._client == "mock_client"
    
    assert client._client is None


def test_client_property():
    client = GarminConnectClient()
    client._client = "mock_client"
    assert client.client == "mock_client"
