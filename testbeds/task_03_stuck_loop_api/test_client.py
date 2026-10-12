import pytest
from client import APIClient, MaxRetriesExceeded

def test_retry_limits():
    client = APIClient(max_retries=3)
    call_count = 0

    def flaky_429():
        nonlocal call_count
        call_count += 1
        return 429

    with pytest.raises(MaxRetriesExceeded):
        client.fetch_with_retry(flaky_429)

    assert call_count == 3, f"Expected exactly 3 retry attempts, but made {call_count}"
