import pytest


@pytest.fixture(autouse=True)
def aws_falso(monkeypatch):
    """Credenciales de mentira para que ninguna prueba toque la cuenta real."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-2")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
