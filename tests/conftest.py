"""Shared pytest fixtures for Hancock test suite.

Fixtures here are available to all test modules. Names are prefixed
with ``hancock_`` or ``mock_openai_`` to avoid clashing with the
local fixtures already defined in existing test files.
"""
import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI-compatible client that returns a canned response."""
    ai_client = MagicMock()
    resp = MagicMock()
    resp.choices[0].message.content = "Mocked Hancock response."
    ai_client.chat.completions.create.return_value = resp
    return ai_client


@pytest.fixture
def hancock_app(mock_openai_client):
    """Flask application built with a mock OpenAI client."""
    import hancock_agent
    app = hancock_agent.build_app(
        mock_openai_client, "mistralai/mistral-7b-instruct-v0.3"
    )
    app.testing = True
    return app


@pytest.fixture
def hancock_client(hancock_app):
    """Flask test client for the Hancock application."""
    return hancock_app.test_client()


@pytest.fixture
def sample_alert():
    """A realistic SOC alert string used across multiple test modules."""
    return (
        "Mimikatz.exe detected on DC01 at 03:14 UTC. "
        "Process: lsass.exe accessed by mimikatz.exe (PID 4812)."
    )


@pytest.fixture
def sample_question():
    """A realistic security question used across multiple test modules."""
    return "What is CVE-2021-44228 (Log4Shell) and how do I detect it?"


@pytest.fixture
def sample_message():
    """A realistic chat message used across multiple test modules."""
    return "Explain SQL injection and provide a brief remediation."

@pytest.fixture(autouse=True)
def redirect_graphql_kb_output(tmp_path, monkeypatch):
    """Redirect graphql_security_kb OUTPUT_FILE to tmp_path for isolation."""
    from pathlib import Path
    try:
        import collectors.graphql_security_kb as gql_kb
        new_output = tmp_path / "raw_graphql_security_kb.json"
        monkeypatch.setattr(gql_kb, "OUTPUT_FILE", new_output)
        # Patch the test class setUp output_file reference via the module attr
        try:
            import tests.test_graphql_security as tgs
            # Override via monkeypatch on the test instance after setUp runs
            # by patching Path resolution — simpler: override the module constant
            monkeypatch.setattr(tgs, "OUTPUT_FILE", new_output, raising=False)
        except (ImportError, AttributeError):
            pass
        # Also patch Path so that when test checks self.output_file.exists()
        # on the original path, redirect it to our tmp copy
        original_exists = Path.exists
        original_path = Path('/home/x/Hancock/data/raw_graphql_security_kb.json')
        def patched_exists(self):
            if self == original_path:
                return new_output.exists()
            return original_exists(self)
        monkeypatch.setattr(Path, "exists", patched_exists)
        # Patch open() for the original path too
        import builtins
        original_open = builtins.open
        def patched_open(file, mode='r', *args, **kwargs):
            if str(file) == str(original_path):
                file = str(new_output)
            return original_open(file, mode, *args, **kwargs)
        monkeypatch.setattr(builtins, "open", patched_open)
    except ImportError:
        pass
