import pytest
from auth import format_auth_log

def test_bearer_token_masked():
    raw_header = "Bearer secret_api_token_12345"
    log_line = format_auth_log(raw_header)
    assert "secret_api_token_12345" not in log_line, "Raw token must not be leaked in logs!"
    assert "Bearer secr***" in log_line or "Bearer secr..." in log_line
