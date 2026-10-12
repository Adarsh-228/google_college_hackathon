-- Harness Kit: BigQuery Schema & AgentTrace Views
-- Dataset: harness_analytics
-- Target Project: ${PROJECT_ID} (default or replace with your GCP project)

-- 1. Create Dataset (Run via 'bq mk' or BQ Console)
-- CREATE SCHEMA IF NOT EXISTS `harness_analytics` OPTIONS(location="US");

-- ── 1. runs Table ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS `harness_analytics.runs` (
    run_id STRING NOT NULL,
    task_id STRING,
    model STRING,
    tool_mode STRING,
    planning BOOLEAN,
    context_tier STRING,
    budget_cap INT64,
    resolved BOOLEAN,
    tokens_in_uncached INT64,
    tokens_in_cached INT64,
    tokens_out INT64,
    total_cost_usd FLOAT64,
    stop_reason STRING,
    total_turns INT64,
    re_patch_count INT64,
    m1_count INT64,
    m3_count INT64,
    is_error BOOLEAN,
    created_at TIMESTAMP
);

-- ── 2. turns Table ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS `harness_analytics.turns` (
    run_id STRING NOT NULL,
    turn_idx INT64,
    phase STRING,
    tool STRING,
    tokens_in INT64,
    tokens_out INT64,
    duration_ms FLOAT64,
    compaction_event STRING,
    created_at TIMESTAMP
);

-- ── 3. tool_calls Table ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS `harness_analytics.tool_calls` (
    run_id STRING NOT NULL,
    turn_idx INT64,
    tool STRING,
    args_hash STRING,
    target_path STRING,
    is_error BOOLEAN,
    guard_event STRING,
    created_at TIMESTAMP
);

-- ── 4. judgments Table (AgentTrace Failure Classification) ───────────────
CREATE TABLE IF NOT EXISTS `harness_analytics.judgments` (
    run_id STRING NOT NULL,
    failure_stage STRING,
    reason STRING,
    created_at TIMESTAMP
);

-- ── 5. AgentTrace Analytical Views ───────────────────────────────────────

-- View 1: Harness Configuration Comparison (Main Dashboard Comparator)
CREATE OR REPLACE VIEW `harness_analytics.v_harness_comparison_summary` AS
SELECT 
    context_tier,
    tool_mode,
    planning,
    budget_cap,
    model,
    COUNT(*) as total_runs,
    SUM(CAST(resolved AS INT64)) * 1.0 / COUNT(*) as pass_rate,
    AVG(tokens_in_uncached + tokens_in_cached + tokens_out) as avg_tokens,
    AVG(total_cost_usd) as avg_cost,
    AVG(total_turns) as avg_turns,
    AVG(re_patch_count) as avg_re_patches,
    AVG(m1_count) as avg_m1_compactions,
    AVG(m3_count) as avg_m3_compactions
FROM `harness_analytics.runs`
GROUP BY context_tier, tool_mode, planning, budget_cap, model;

-- View 2: Failure Stage Attribution (Empirical Paper Alignment)
CREATE OR REPLACE VIEW `harness_analytics.v_failure_stage_attribution` AS
SELECT 
    r.context_tier,
    r.model,
    j.failure_stage,
    j.reason,
    COUNT(*) as count
FROM `harness_analytics.runs` r
JOIN `harness_analytics.judgments` j ON r.run_id = j.run_id
WHERE r.resolved = FALSE
GROUP BY r.context_tier, r.model, j.failure_stage, j.reason;

-- View 3: Phase Breakdown (Turns & Latency per Reasoning Phase)
CREATE OR REPLACE VIEW `harness_analytics.v_phase_breakdown` AS
SELECT
    t.run_id,
    r.context_tier,
    r.model,
    t.phase,
    COUNT(*) as turn_count,
    SUM(t.tokens_in + t.tokens_out) as phase_tokens,
    SUM(t.duration_ms) as phase_duration_ms
FROM `harness_analytics.turns` t
JOIN `harness_analytics.runs` r ON t.run_id = r.run_id
GROUP BY t.run_id, r.context_tier, r.model, t.phase;

-- View 4: Tool Usage & Guard Interceptions
CREATE OR REPLACE VIEW `harness_analytics.v_tool_usage` AS
SELECT
    r.context_tier,
    r.model,
    tc.tool,
    COUNT(*) as call_count,
    SUM(CAST(tc.is_error AS INT64)) as error_count,
    SUM(CASE WHEN tc.guard_event IS NOT NULL THEN 1 ELSE 0 END) as guarded_count
FROM `harness_analytics.tool_calls` tc
JOIN `harness_analytics.runs` r ON tc.run_id = r.run_id
GROUP BY r.context_tier, r.model, tc.tool;

-- View 5: Cost & Token Breakdown by Model
CREATE OR REPLACE VIEW `harness_analytics.v_cost_by_model` AS
SELECT
    model,
    context_tier,
    COUNT(*) as runs,
    AVG(total_cost_usd) as avg_cost,
    MIN(total_cost_usd) as min_cost,
    MAX(total_cost_usd) as max_cost,
    SUM(total_cost_usd) as total_cost,
    AVG(tokens_in_uncached + tokens_in_cached) as avg_input_tokens,
    AVG(tokens_out) as avg_output_tokens
FROM `harness_analytics.runs`
GROUP BY model, context_tier;
