import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from config import Settings


def test_application_configuration_fails_without_secret_key():
    environment = os.environ.copy()
    environment.pop("SECRET_KEY", None)
    result = subprocess.run(
        [sys.executable, "-c", "import config"],
        cwd=Path(__file__).parents[1],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Field required" in result.stderr


@pytest.mark.parametrize("secret_key", ["", "a" * 32, "short-secret"])
def test_secret_key_must_be_robust(monkeypatch, secret_key):
    monkeypatch.setenv("SECRET_KEY", secret_key)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
