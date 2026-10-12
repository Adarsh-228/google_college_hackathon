const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function fetchTasks() {
  try {
    const res = await fetch(`${API_BASE}/api/tasks`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return data.tasks || [];
  } catch (err) {
    console.warn("Failed to fetch tasks from API, using fallback:", err);
    throw err;
  }
}

export async function fetchMetricsSummary() {
  try {
    const res = await fetch(`${API_BASE}/api/metrics/summary`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn("Failed to fetch metrics from API:", err);
    throw err;
  }
}

export async function startRun(
  taskId: string,
  modelId: string = "gemini-2.5-flash",
  harnessConfig?: any
) {
  try {
    const res = await fetch(`${API_BASE}/api/runs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        task_id: taskId,
        model_id: modelId,
        harness_config: harnessConfig,
      }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn("Failed to start run via API:", err);
    return null;
  }
}

export async function startCompare(
  taskId: string,
  modelId: string = "gemini-2.5-flash",
  harnessConfig?: any
) {
  try {
    const res = await fetch(`${API_BASE}/api/compare`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        task_id: taskId,
        model_id: modelId,
        harness_config: harnessConfig,
      }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn("Failed to start comparison via API:", err);
    return null;
  }
}

export async function fetchComparisonMetrics(
  harnessRunId: string,
  baselineRunId: string
) {
  try {
    const res = await fetch(
      `${API_BASE}/api/metrics/compare/${harnessRunId}/${baselineRunId}`
    );
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.warn("Failed to fetch comparison metrics:", err);
    return null;
  }
}
