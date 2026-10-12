class MaxRetriesExceeded(Exception):
    pass

class APIClient:
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries

    def fetch_with_retry(self, status_code_fn):
        """
        Calls status_code_fn() until 200 or raises MaxRetriesExceeded.
        BUG: Unbounded while True loop without retry counter check!
        """
        attempts = 0
        while True:
            attempts += 1
            code = status_code_fn()
            if code == 200:
                return "SUCCESS"
            # BUG: missing attempts >= self.max_retries check!
            if attempts > 50:  # Safety guard for local test runners
                raise RuntimeError("Stuck loop runaway detected")
