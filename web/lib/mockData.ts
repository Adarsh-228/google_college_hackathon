export interface TaskFile {
  name: string;
  language: string;
  content: string;
  fixedContent?: string;
}

export interface TaskMeta {
  id: string;
  title: string;
  category: string;
  description: string;
  prompt: string;
  expected_behavior: string;
  eval_command: string;
  files: TaskFile[];
  diff: string;
}

export const MOCK_TASKS: TaskMeta[] = [
  {
    id: "task_01_off_by_one",
    title: "Task 1: Pagination Off-By-One Slice",
    category: "SWE-Bench Style",
    description: "The paginate function in app.py returns 9 items instead of 10 due to an incorrect slice upper bound.",
    prompt: "Fix the off-by-one pagination bug in app.py so that test_app.py passes with pytest.",
    expected_behavior: "Return exactly 'size' items for full pages.",
    eval_command: "pytest test_app.py",
    files: [
      {
        name: "app.py",
        language: "python",
        content: `from typing import List, Any

def paginate(items: List[Any], page: int, size: int) -> List[Any]:
    """
    Returns items for a 1-indexed page number.
    Bug: slice upper bound subtracts 1 unnecessarily.
    """
    if page < 1 or size < 1:
        return []
    start = (page - 1) * size
    # BUG: off-by-one slice upper bound
    return items[start : start + size - 1]
`,
        fixedContent: `from typing import List, Any

def paginate(items: List[Any], page: int, size: int) -> List[Any]:
    """
    Returns items for a 1-indexed page number.
    Bug: slice upper bound subtracts 1 unnecessarily.
    """
    if page < 1 or size < 1:
        return []
    start = (page - 1) * size
    # FIXED: proper slice upper bound
    return items[start : start + size]
`,
      },
      {
        name: "test_app.py",
        language: "python",
        content: `from app import paginate

def test_paginate_first_page():
    data = list(range(100))
    page = paginate(data, page=1, size=10)
    assert len(page) == 10
    assert page == list(range(10))

def test_paginate_empty():
    assert paginate([], 1, 10) == []
`,
      },
    ],
    diff: `--- a/app.py
+++ b/app.py
@@ -11,2 +11,2 @@
-    # BUG: off-by-one slice upper bound
-    return items[start : start + size - 1]
+    # FIXED: proper slice upper bound
+    return items[start : start + size]`,
  },
  {
    id: "task_02_auth_token_leak",
    title: "Task 2: Credential Masking in Logs",
    category: "Security & Sanitization",
    description: "auth.py emits raw Authorization Bearer tokens in stdout logs instead of masking all but the first 4 characters.",
    prompt: "Mask Bearer authentication tokens in auth.py so that sensitive secrets are not logged in plain text and test_auth.py passes.",
    expected_behavior: "Log 'Bearer abcd***' instead of 'Bearer abcd1234efgh5678'.",
    eval_command: "pytest test_auth.py",
    files: [
      {
        name: "auth.py",
        language: "python",
        content: `import re

def format_auth_log(header_value: str) -> str:
    """
    Formats authorization header for operational logs.
    Bug: logs entire raw secret token instead of masking it.
    """
    if not header_value.startswith("Bearer "):
        return f"Auth: {header_value}"

    raw_token = header_value.split("Bearer ", 1)[1]
    # BUG: plain-text token leak
    return f"Auth: Bearer {raw_token}"
`,
        fixedContent: `import re

def format_auth_log(header_value: str) -> str:
    """
    Formats authorization header for operational logs.
    Masks token secrets, preserving first 4 characters.
    """
    if not header_value.startswith("Bearer "):
        return f"Auth: {header_value}"

    raw_token = header_value.split("Bearer ", 1)[1]
    masked = raw_token[:4] + "***" if len(raw_token) > 4 else "***"
    return f"Auth: Bearer {masked}"
`,
      },
      {
        name: "test_auth.py",
        language: "python",
        content: `from auth import format_auth_log

def test_mask_bearer_token():
    header = "Bearer secrettoken123456"
    log = format_auth_log(header)
    assert "secrettoken123456" not in log
    assert log == "Auth: Bearer secr***"
`,
      },
    ],
    diff: `--- a/auth.py
+++ b/auth.py
@@ -11,2 +11,3 @@
-    # BUG: plain-text token leak
-    return f"Auth: Bearer {raw_token}"
+    masked = raw_token[:4] + "***" if len(raw_token) > 4 else "***"
+    return f"Auth: Bearer {masked}"`,
  },
  {
    id: "task_03_stuck_loop_api",
    title: "Task 3: Unbounded Flaky Retry Loop",
    category: "Reliability & Circuit Breaking",
    description: "client.py retries HTTP 429 rate limit responses forever in an unbounded while loop. Triggers AgentGuard circuit breaker if unhandled.",
    prompt: "Fix client.py by adding a max_retries limit (default 3) and exponential backoff to prevent infinite retry loops.",
    expected_behavior: "Raise MaxRetriesExceeded after 3 attempts.",
    eval_command: "pytest test_client.py",
    files: [
      {
        name: "client.py",
        language: "python",
        content: `class MaxRetriesExceeded(Exception):
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
            if attempts > 50:
                raise RuntimeError("Stuck loop runaway detected")
`,
        fixedContent: `class MaxRetriesExceeded(Exception):
    pass

class APIClient:
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries

    def fetch_with_retry(self, status_code_fn):
        """
        Calls status_code_fn() until 200 or raises MaxRetriesExceeded.
        """
        attempts = 0
        while True:
            attempts += 1
            code = status_code_fn()
            if code == 200:
                return "SUCCESS"
            if attempts >= self.max_retries:
                raise MaxRetriesExceeded("Exceeded retry limit")
`,
      },
      {
        name: "test_client.py",
        language: "python",
        content: `import pytest
from client import APIClient, MaxRetriesExceeded

def test_retry_raises_after_max():
    client = APIClient(max_retries=3)
    with pytest.raises(MaxRetriesExceeded):
        client.fetch_with_retry(lambda: 429)
`,
      },
    ],
    diff: `--- a/client.py
+++ b/client.py
@@ -19,2 +19,2 @@
-            # BUG: missing attempts >= self.max_retries check!
-            if attempts > 50:
+            if attempts >= self.max_retries:
+                raise MaxRetriesExceeded("Exceeded retry limit")`,
  },
  {
    id: "task_04_verbose_log_overflow",
    title: "Task 4: Verbose Log Parsing & Context Overflow",
    category: "Context Management & Compaction",
    description: "Running tests prints thousands of log lines that overflow unmanaged 32k context windows (T0). Under ContextT4, staged elision (M1) compacts the log, allowing Gemini to successfully fix the parser.",
    prompt: "Fix the regex in parser.py to extract IPv4 addresses correctly and ensure test_parser.py passes.",
    expected_behavior: "Extract valid IPv4 without trailing punctuation.",
    eval_command: "pytest test_parser.py",
    files: [
      {
        name: "parser.py",
        language: "python",
        content: `import re
from typing import List

def extract_ip_addresses(log_text: str) -> List[str]:
    """
    Extracts IPv4 addresses from log entries.
    BUG: regex misses matching proper boundary or octet limits.
    """
    # BUG: captures digits without proper boundary check
    pattern = r"\\d+\\.\\d+\\.\\d+\\.\\d+"
    return re.findall(pattern, log_text)
`,
        fixedContent: `import re
from typing import List

def extract_ip_addresses(log_text: str) -> List[str]:
    """
    Extracts IPv4 addresses from log entries.
    Uses strict boundary and 0-255 octet bounds.
    """
    pattern = r"\\b(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\b"
    return re.findall(pattern, log_text)
`,
      },
      {
        name: "test_parser.py",
        language: "python",
        content: `from parser import extract_ip_addresses

def test_parse_ip_standard():
    sample = "Host 192.168.1.1 connected to 10.0.0.254 on port 80."
    res = extract_ip_addresses(sample)
    assert res == ["192.168.1.1", "10.0.0.254"]

def test_parse_ip_invalid_octets():
    sample = "Invalid address 999.999.999.999 should not match."
    res = extract_ip_addresses(sample)
    assert res == []
`,
      },
    ],
    diff: `--- a/parser.py
+++ b/parser.py
@@ -8,3 +8,3 @@
-    # BUG: captures digits without proper boundary check
-    pattern = r"\\d+\\.\\d+\\.\\d+\\.\\d+"
+    pattern = r"\\b(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\b"
     return re.findall(pattern, log_text)`,
  },
  {
    id: "task_05_circular_dependency",
    title: "Task 5: Broken Import & Undefined Name",
    category: "Diagnostics & Linting",
    description: "service.py references an undefined identifier calculate_discount_v2 that causes NameError. AgentGuard's zero-turn linter alerts Gemini immediately upon file save.",
    prompt: "Fix service.py by defining calculate_discount and fixing test_service.py.",
    expected_behavior: "Return 10% discount without NameError.",
    eval_command: "pytest test_service.py",
    files: [
      {
        name: "service.py",
        language: "python",
        content: `def get_checkout_price(price: float, is_vip: bool) -> float:
    """Calculates checkout price for a customer."""
    if not is_vip:
        return price
    # BUG: references undefined calculate_discount_v2
    discount = calculate_discount_v2(price)
    return price - discount
`,
        fixedContent: `def calculate_discount(price: float) -> float:
    return price * 0.10

def get_checkout_price(price: float, is_vip: bool) -> float:
    """Calculates checkout price for a customer."""
    if not is_vip:
        return price
    discount = calculate_discount(price)
    return price - discount
`,
      },
      {
        name: "test_service.py",
        language: "python",
        content: `from service import get_checkout_price

def test_vip_discount():
    assert get_checkout_price(100.0, True) == 90.0

def test_standard_price():
    assert get_checkout_price(100.0, False) == 100.0
`,
      },
    ],
    diff: `--- a/service.py
+++ b/service.py
@@ -1,0 +1,3 @@
+def calculate_discount(price: float) -> float:
    return price * 0.10
+
@@ -6,2 +9,2 @@
-    discount = calculate_discount_v2(price)
+    discount = calculate_discount(price)
     return price - discount`,
  },
];

// Per-task realistic runs matching each testbed's actual failure and resolution behavior
export const TASK_BENCHMARK_RUNS: Record<string, { baseline: any; harnessed: any }> = {
  task_01_off_by_one: {
    baseline: {
      runId: "run_b_t1",
      taskId: "task_01_off_by_one",
      model: "gemini-2.5-flash",
      tier: "T0 (Unmanaged)",
      status: "ASSERTION_FAILED",
      budgetCap: 32768,
      tokensIn: 2420,
      costUsd: 0.00021,
      events: [
        { turn_idx: 1, type: "TOOL_CALL", data: { tool: "bash", args: { command: "pytest test_app.py -v" } } },
        { turn_idx: 1, type: "TOOL_RESULT", data: { tool: "bash", is_error: true, output: "FAILED test_app.py::test_paginate_first_page - AssertionError: assert 9 == 10" } },
        { turn_idx: 2, type: "ERROR", data: { reason: "ASSERTION_FAILED", message: "Failed verification. Slice returned 9 items instead of 10." } },
      ],
    },
    harnessed: {
      runId: "run_h_t1",
      taskId: "task_01_off_by_one",
      model: "gemini-2.5-flash",
      tier: "T4 (ContextT4)",
      status: "RESOLVED",
      budgetCap: 32768,
      tokensIn: 1840,
      costUsd: 0.00015,
      events: [
        { turn_idx: 1, type: "TOOL_CALL", data: { tool: "bash", args: { command: "pytest test_app.py -v" } } },
        { turn_idx: 1, type: "TOOL_RESULT", data: { tool: "bash", is_error: true, output: "FAILED test_app.py::test_paginate_first_page - AssertionError: assert 9 == 10" } },
        { turn_idx: 2, type: "GUARD_EVENT", data: { badge: "RBW_PASSED", output: "AgentGuard: Read-Before-Write verified on app.py." } },
        { turn_idx: 2, type: "TOOL_CALL", data: { tool: "edit_file", args: { path: "app.py", old_text: "start + size - 1", new_text: "start + size" } } },
        { turn_idx: 2, type: "TOOL_RESULT", data: { tool: "edit_file", is_error: false, output: "Replaced 1 occurrence in app.py." } },
        { turn_idx: 3, type: "TOOL_CALL", data: { tool: "bash", args: { command: "pytest test_app.py -v" } } },
        { turn_idx: 3, type: "TOOL_RESULT", data: { tool: "bash", is_error: false, output: "test_app.py::test_paginate_first_page PASSED\ntest_app.py::test_paginate_empty PASSED [100%]\n2 passed in 0.02s" } },
        { turn_idx: 3, type: "RUN_FINISH", data: { final_message: "All 2 tests passed. Off-by-one fixed." } },
      ],
    },
  },

  task_02_auth_token_leak: {
    baseline: {
      runId: "run_b_t2",
      taskId: "task_02_auth_token_leak",
      model: "gemini-2.5-flash",
      tier: "T0 (Unmanaged)",
      status: "SECURITY_FAILED",
      budgetCap: 32768,
      tokensIn: 2650,
      costUsd: 0.00024,
      events: [
        { turn_idx: 1, type: "TOOL_CALL", data: { tool: "bash", args: { command: "pytest test_auth.py -v" } } },
        { turn_idx: 1, type: "TOOL_RESULT", data: { tool: "bash", is_error: true, output: "FAILED test_auth.py::test_mask_bearer_token - AssertionError: 'secrettoken123456' found in log output" } },
        { turn_idx: 2, type: "ERROR", data: { reason: "SECURITY_FAILED", message: "Sensitive secret token leaked in operational logs." } },
      ],
    },
    harnessed: {
      runId: "run_h_t2",
      taskId: "task_02_auth_token_leak",
      model: "gemini-2.5-flash",
      tier: "T4 (ContextT4)",
      status: "RESOLVED",
      budgetCap: 32768,
      tokensIn: 2120,
      costUsd: 0.00018,
      events: [
        { turn_idx: 1, type: "TOOL_CALL", data: { tool: "bash", args: { command: "pytest test_auth.py -v" } } },
        { turn_idx: 1, type: "TOOL_RESULT", data: { tool: "bash", is_error: true, output: "FAILED test_auth.py::test_mask_bearer_token - AssertionError: 'secrettoken123456' found in log output" } },
        { turn_idx: 2, type: "GUARD_EVENT", data: { badge: "RBW_PASSED", output: "AgentGuard: Read-Before-Write verified on auth.py." } },
        { turn_idx: 2, type: "TOOL_CALL", data: { tool: "edit_file", args: { path: "auth.py", old_text: 'return f"Auth: Bearer {raw_token}"', new_text: 'masked = raw_token[:4] + "***"\n    return f"Auth: Bearer {masked}"' } } },
        { turn_idx: 2, type: "TOOL_RESULT", data: { tool: "edit_file", is_error: false, output: "Replaced 1 occurrence in auth.py." } },
        { turn_idx: 3, type: "TOOL_CALL", data: { tool: "bash", args: { command: "pytest test_auth.py -v" } } },
        { turn_idx: 3, type: "TOOL_RESULT", data: { tool: "bash", is_error: false, output: "test_auth.py::test_mask_bearer_token PASSED [100%]\n1 passed in 0.02s" } },
        { turn_idx: 3, type: "RUN_FINISH", data: { final_message: "Token masked properly with 'Bearer secr***'." } },
      ],
    },
  },

  task_03_stuck_loop_api: {
    baseline: {
      runId: "run_b_t3",
      taskId: "task_03_stuck_loop_api",
      model: "gemini-2.5-flash",
      tier: "T0 (Unmanaged)",
      status: "CIRCUIT_BREAKER_HALT",
      budgetCap: 32768,
      tokensIn: 8450,
      costUsd: 0.00078,
      events: [
        { turn_idx: 1, type: "TOOL_CALL", data: { tool: "bash", args: { command: "pytest test_client.py -v" } } },
        { turn_idx: 1, type: "TOOL_RESULT", data: { tool: "bash", is_error: true, output: "FAILED test_client.py::test_retry_raises_after_max - Failed: DID NOT RAISE MaxRetriesExceeded\nRuntimeError: Stuck loop runaway detected (attempts > 50)" } },
        { turn_idx: 2, type: "GUARD_EVENT", data: { badge: "CIRCUIT_BREAKER", output: "Circuit breaker triggered: 8 repeated identical attempts without progress." } },
        { turn_idx: 2, type: "ERROR", data: { reason: "CIRCUIT_BREAKER_HALT", message: "Run halted by Circuit Breaker after 8 infinite retry loop iterations." } },
      ],
    },
    harnessed: {
      runId: "run_h_t3",
      taskId: "task_03_stuck_loop_api",
      model: "gemini-2.5-flash",
      tier: "T4 (ContextT4 + AgentGuard)",
      status: "RESOLVED",
      budgetCap: 32768,
      tokensIn: 3180,
      costUsd: 0.00028,
      events: [
        { turn_idx: 1, type: "TOOL_CALL", data: { tool: "bash", args: { command: "pytest test_client.py -v" } } },
        { turn_idx: 1, type: "TOOL_RESULT", data: { tool: "bash", is_error: true, output: "FAILED test_client.py::test_retry_raises_after_max - Failed: DID NOT RAISE MaxRetriesExceeded" } },
        { turn_idx: 2, type: "GUARD_EVENT", data: { badge: "STREAK_WARNING", output: "AgentGuard warning: Flaky retry pattern detected. Enforcing max_retries guard." } },
        { turn_idx: 2, type: "TOOL_CALL", data: { tool: "edit_file", args: { path: "client.py", old_text: "if attempts > 50:", new_text: "if attempts >= self.max_retries:\n                raise MaxRetriesExceeded('Limit exceeded')" } } },
        { turn_idx: 2, type: "TOOL_RESULT", data: { tool: "edit_file", is_error: false, output: "Replaced 1 occurrence in client.py." } },
        { turn_idx: 3, type: "TOOL_CALL", data: { tool: "bash", args: { command: "pytest test_client.py -v" } } },
        { turn_idx: 3, type: "TOOL_RESULT", data: { tool: "bash", is_error: false, output: "test_client.py::test_retry_raises_after_max PASSED [100%]\n1 passed in 0.02s" } },
        { turn_idx: 3, type: "RUN_FINISH", data: { final_message: "MaxRetriesExceeded properly raised after 3 attempts." } },
      ],
    },
  },

  task_04_verbose_log_overflow: {
    baseline: {
      runId: "run_b_t4",
      taskId: "task_04_verbose_log_overflow",
      model: "gemini-2.5-flash",
      tier: "T0 (Unmanaged)",
      status: "CONTEXT_OVERFLOW",
      budgetCap: 32768,
      tokensIn: 34100,
      costUsd: 0.00285,
      events: [
        { turn_idx: 1, type: "TOOL_CALL", data: { tool: "bash", args: { command: "pytest test_parser.py -v" } } },
        { turn_idx: 1, type: "TOOL_RESULT", data: { tool: "bash", is_error: true, output: "[Exit Code: 1]\npytest output: 14,200 lines of uncompressed test dump traces...\nFAILED test_parser.py::test_parse_ip_invalid_octets - AssertionError: ['999.999.999.999'] != []" } },
        { turn_idx: 2, type: "ERROR", data: { reason: "CONTEXT_OVERFLOW", message: "Context window exceeded budget ceiling (34,100 tokens > 32,768 cap). Baseline T0 has no staged compaction." } },
      ],
    },
    harnessed: {
      runId: "run_h_t4",
      taskId: "task_04_verbose_log_overflow",
      model: "gemini-2.5-flash",
      tier: "T4 (ContextT4)",
      status: "RESOLVED",
      budgetCap: 32768,
      tokensIn: 4120,
      costUsd: 0.00072,
      events: [
        { turn_idx: 1, type: "TOOL_CALL", data: { tool: "bash", args: { command: "pytest test_parser.py -v" } } },
        { turn_idx: 1, type: "TOOL_RESULT", data: { tool: "bash", is_error: true, output: "FAILED test_parser.py::test_parse_ip_invalid_octets - AssertionError: ['999.999.999.999'] != []" } },
        { turn_idx: 2, type: "COMPACTION", data: { badge: "M1_ELISION", tokens_saved: 29850, tokens_after: 2150 } },
        { turn_idx: 2, type: "GUARD_EVENT", data: { badge: "RBW_PASSED", output: "Read-Before-Write check verified on parser.py." } },
        { turn_idx: 3, type: "TOOL_CALL", data: { tool: "edit_file", args: { path: "parser.py", old_text: 'pattern = r"\\d+\\.\\d+\\.\\d+\\.\\d+"', new_text: 'pattern = r"\\b(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\b"' } } },
        { turn_idx: 3, type: "TOOL_RESULT", data: { tool: "edit_file", is_error: false, output: "parser.py updated cleanly." } },
        { turn_idx: 4, type: "TOOL_CALL", data: { tool: "bash", args: { command: "pytest test_parser.py -v" } } },
        { turn_idx: 4, type: "TOOL_RESULT", data: { tool: "bash", is_error: false, output: "test_parser.py::test_parse_ip_standard PASSED\ntest_parser.py::test_parse_ip_invalid_octets PASSED [100%]\n2 passed in 0.03s" } },
        { turn_idx: 4, type: "RUN_FINISH", data: { final_message: "All tests passed with pytest verification." } },
      ],
    },
  },

  task_05_circular_dependency: {
    baseline: {
      runId: "run_b_t5",
      taskId: "task_05_circular_dependency",
      model: "gemini-2.5-flash",
      tier: "T0 (Unmanaged)",
      status: "NAME_ERROR_HALT",
      budgetCap: 32768,
      tokensIn: 2890,
      costUsd: 0.00026,
      events: [
        { turn_idx: 1, type: "TOOL_CALL", data: { tool: "bash", args: { command: "pytest test_service.py -v" } } },
        { turn_idx: 1, type: "TOOL_RESULT", data: { tool: "bash", is_error: true, output: "FAILED test_service.py::test_vip_discount - NameError: name 'calculate_discount_v2' is not defined" } },
        { turn_idx: 2, type: "ERROR", data: { reason: "NAME_ERROR_HALT", message: "Runtime NameError: undefined identifier calculate_discount_v2." } },
      ],
    },
    harnessed: {
      runId: "run_h_t5",
      taskId: "task_05_circular_dependency",
      model: "gemini-2.5-flash",
      tier: "T4 (ContextT4 + AgentGuard)",
      status: "RESOLVED",
      budgetCap: 32768,
      tokensIn: 2210,
      costUsd: 0.00020,
      events: [
        { turn_idx: 1, type: "TOOL_CALL", data: { tool: "bash", args: { command: "pytest test_service.py -v" } } },
        { turn_idx: 1, type: "TOOL_RESULT", data: { tool: "bash", is_error: true, output: "FAILED test_service.py::test_vip_discount - NameError: name 'calculate_discount_v2' is not defined" } },
        { turn_idx: 2, type: "GUARD_EVENT", data: { badge: "LINT", output: "Zero-Turn Linter: undefined symbol calculate_discount_v2 detected on save." } },
        { turn_idx: 2, type: "TOOL_CALL", data: { tool: "edit_file", args: { path: "service.py", old_text: "discount = calculate_discount_v2(price)", new_text: "def calculate_discount(price):\n    return price * 0.10\n\ndiscount = calculate_discount(price)" } } },
        { turn_idx: 2, type: "TOOL_RESULT", data: { tool: "edit_file", is_error: false, output: "Fixed undefined function definition in service.py." } },
        { turn_idx: 3, type: "TOOL_CALL", data: { tool: "bash", args: { command: "pytest test_service.py -v" } } },
        { turn_idx: 3, type: "TOOL_RESULT", data: { tool: "bash", is_error: false, output: "test_service.py::test_vip_discount PASSED\ntest_service.py::test_standard_price PASSED [100%]\n2 passed in 0.02s" } },
        { turn_idx: 3, type: "RUN_FINISH", data: { final_message: "All tests passed cleanly." } },
      ],
    },
  },
};

export const MOCK_BASELINE_RUN = TASK_BENCHMARK_RUNS.task_04_verbose_log_overflow.baseline;
export const MOCK_HARNESSED_RUN = TASK_BENCHMARK_RUNS.task_04_verbose_log_overflow.harnessed;

export const MOCK_BIGQUERY_METRICS = {
  total_runs: 50,
  pass_rate: 0.80,
  avg_cost_usd: 0.00145,
  data_source: "bigquery",
  comparisons: [
    {
      context_tier: "T4 (ContextT4)",
      tool_mode: "predefined",
      planning: 1,
      budget_cap: 32768,
      model: "gemini-2.5-flash",
      total_runs: 25,
      pass_rate: 0.84,
      avg_tokens: 4320,
      avg_cost: 0.00085,
      avg_turns: 4.8,
      avg_re_patches: 0.2,
      avg_m1_compactions: 1.4,
      avg_m3_compactions: 0.1,
    },
    {
      context_tier: "T0 (Unmanaged)",
      tool_mode: "bash_only",
      planning: 0,
      budget_cap: 32768,
      model: "gemini-2.5-flash",
      total_runs: 25,
      pass_rate: 0.12,
      avg_tokens: 31800,
      avg_cost: 0.00390,
      avg_turns: 2.1,
      avg_re_patches: 1.6,
      avg_m1_compactions: 0.0,
      avg_m3_compactions: 0.0,
    },
  ],
  failures: [
    {
      context_tier: "T0",
      model: "gemini-2.5-flash",
      failure_stage: "verification",
      reason: "CONTEXT_OVERFLOW",
      count: 18,
    },
    {
      context_tier: "T0",
      model: "gemini-2.5-flash",
      failure_stage: "line_localization",
      reason: "CIRCUIT_BREAKER_STUCK",
      count: 4,
    },
  ],
  phase_breakdown: [
    { phase: "exploration", turn_count: 25, phase_tokens: 18400, phase_duration_ms: 3200 },
    { phase: "localization", turn_count: 32, phase_tokens: 22100, phase_duration_ms: 4100 },
    { phase: "patch_implementation", turn_count: 28, phase_tokens: 16900, phase_duration_ms: 2800 },
    { phase: "verification", turn_count: 24, phase_tokens: 14500, phase_duration_ms: 1900 },
  ],
  tool_usage: [
    { tool: "read_file", call_count: 42, error_count: 1, guarded_count: 0 },
    { tool: "edit_file", call_count: 29, error_count: 2, guarded_count: 5 },
    { tool: "bash", call_count: 38, error_count: 8, guarded_count: 2 },
  ],
};
