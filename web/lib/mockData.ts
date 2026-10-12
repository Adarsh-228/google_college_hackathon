export interface TaskMeta {
  id: string;
  title: string;
  category: string;
  description: string;
  prompt: string;
  expected_behavior: string;
  eval_command: string;
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
  },
  {
    id: "task_02_auth_token_leak",
    title: "Task 2: Credential Masking in Logs",
    category: "Security & Sanitization",
    description: "auth.py emits raw Authorization Bearer tokens in stdout logs instead of masking all but the first 4 characters.",
    prompt: "Mask Bearer authentication tokens in auth.py so that sensitive secrets are not logged in plain text and test_auth.py passes.",
    expected_behavior: "Log 'Bearer abcd***' instead of 'Bearer abcd1234efgh5678'.",
    eval_command: "pytest test_auth.py",
  },
  {
    id: "task_03_stuck_loop_api",
    title: "Task 3: Unbounded Flaky Retry Loop",
    category: "Reliability & Circuit Breaking",
    description: "client.py retries HTTP 429 rate limit responses forever in an unbounded while loop with 0 backoff. Triggers AgentGuard 5-streak warning and 8-streak termination if unhandled.",
    prompt: "Fix client.py by adding a max_retries limit (default 3) and exponential backoff to prevent infinite retry loops.",
    expected_behavior: "Raise MaxRetriesExceeded after 3 attempts.",
    eval_command: "pytest test_client.py",
  },
  {
    id: "task_04_verbose_log_overflow",
    title: "Task 4: Verbose Log Parsing & Context Overflow",
    category: "Context Management & Compaction",
    description: "Running tests prints thousands of log lines that will overflow unmanaged 32k context windows (T0). Under ContextT4, staged elision (M1) compacts the log, allowing the agent to successfully fix the parser.",
    prompt: "Fix the regex in parser.py to extract IPv4 addresses correctly and ensure test_parser.py passes.",
    expected_behavior: "Extract valid IPv4 without trailing punctuation.",
    eval_command: "pytest test_parser.py",
  },
  {
    id: "task_05_circular_dependency",
    title: "Task 5: Broken Import & Undefined Name",
    category: "Diagnostics & Linting",
    description: "service.py references an undefined identifier calculate_discount_v2 that causes NameError. AgentGuard's zero-turn linter alerts the agent immediately upon file save.",
    prompt: "Fix service.py by importing or defining calculate_discount and fixing test_service.py.",
    expected_behavior: "Return 10% discount without NameError.",
    eval_command: "pytest test_service.py",
  },
];

export const MOCK_BASELINE_RUN = {
  runId: "run_baseline_t0_overflow",
  taskId: "task_04_verbose_log_overflow",
  model: "gemini-2.5-flash",
  tier: "T0",
  status: "CONTEXT_OVERFLOW",
  budgetCap: 32768,
  tokensIn: 34100,
  costUsd: 0.00285,
  events: [
    {
      turn_idx: 1,
      type: "TURN_START",
      data: { turn: 1, estimated_tokens: 1400, budget_cap: 32768 },
    },
    {
      turn_idx: 1,
      type: "TOOL_CALL",
      data: { tool: "bash", args: { command: "pytest test_parser.py -v" } },
    },
    {
      turn_idx: 1,
      type: "TOOL_RESULT",
      data: {
        tool: "bash",
        output: "[Exit Code: 1]\npytest output: 14,200 lines of uncompressed test dump traces...\nFAILED test_parser.py::test_parse_ip - AssertionError: Expected 192.168.1.1 got 192.168.1.1,",
        is_error: true,
      },
    },
    {
      turn_idx: 2,
      type: "ERROR",
      data: {
        reason: "CONTEXT_OVERFLOW",
        message: "Context window exceeded budget ceiling (34,100 tokens > 32,768 cap). Baseline T0 has no staged compaction.",
      },
    },
  ],
};

export const MOCK_HARNESSED_RUN = {
  runId: "run_harness_t4_resolved",
  taskId: "task_04_verbose_log_overflow",
  model: "gemini-2.5-flash",
  tier: "T4",
  status: "RESOLVED",
  budgetCap: 32768,
  tokensIn: 4120,
  costUsd: 0.00072,
  events: [
    {
      turn_idx: 1,
      type: "PLAN_UPDATE",
      data: {
        current_plan: [
          { content: "Run pytest to capture failure", status: "in_progress" },
          { content: "Read parser.py and locate regex bug", status: "pending" },
          { content: "Edit parser.py and verify fix", status: "pending" },
        ],
      },
    },
    {
      turn_idx: 1,
      type: "TOOL_CALL",
      data: { tool: "bash", args: { command: "pytest test_parser.py -v" } },
    },
    {
      turn_idx: 1,
      type: "TOOL_RESULT",
      data: {
        tool: "bash",
        output: "FAILED test_parser.py::test_parse_ip - AssertionError: Expected 192.168.1.1 got 192.168.1.1,",
        is_error: true,
      },
    },
    {
      turn_idx: 2,
      type: "COMPACTION",
      data: {
        badge: "M1_ELISION",
        m1_count: 1,
        m3_count: 0,
        tokens_after: 2150,
      },
    },
    {
      turn_idx: 2,
      type: "TOOL_CALL",
      data: { tool: "read_file", args: { path: "parser.py", offset: 1, limit: 100 } },
    },
    {
      turn_idx: 2,
      type: "TOOL_RESULT",
      data: {
        tool: "read_file",
        output: "1: import re\n2: def parse_ip(text):\n3:     return re.findall(r'\\d+\\.\\d+\\.\\d+\\.\\d+[,.]?', text)",
        is_error: false,
      },
    },
    {
      turn_idx: 3,
      type: "GUARD_EVENT",
      data: {
        badge: "RBW_PASSED",
        output: "File parser.py inspected before modification.",
      },
    },
    {
      turn_idx: 3,
      type: "TOOL_CALL",
      data: {
        tool: "edit_file",
        args: {
          path: "parser.py",
          old_text: "r'\\d+\\.\\d+\\.\\d+\\.\\d+[,.]?'",
          new_text: "r'\\b(?:\\d{1,3}\\.){3}\\d{1,3}\\b'",
        },
      },
    },
    {
      turn_idx: 3,
      type: "TOOL_RESULT",
      data: {
        tool: "edit_file",
        output: "Successfully replaced 1 occurrence in parser.py.",
        is_error: false,
      },
    },
    {
      turn_idx: 4,
      type: "TOOL_CALL",
      data: { tool: "bash", args: { command: "pytest test_parser.py -v" } },
    },
    {
      turn_idx: 4,
      type: "TOOL_RESULT",
      data: {
        tool: "bash",
        output: "test_parser.py::test_parse_ip PASSED [100%]\n1 passed in 0.04s",
        is_error: false,
      },
    },
  ],
};

export const MOCK_BIGQUERY_METRICS = {
  total_runs: 50,
  pass_rate: 0.80,
  avg_cost_usd: 0.00145,
  data_source: "bigquery",
  comparisons: [
    {
      context_tier: "T4",
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
      context_tier: "T0",
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
