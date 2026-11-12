"use client";

import React, { useState, useEffect } from "react";
import { DualPaneComparator } from "../components/DualPaneComparator";
import { MetricsScorecard } from "../components/MetricsScorecard";
import { LaunchModal } from "../components/LaunchModal";
import { CreateTaskModal } from "../components/CreateTaskModal";
import {
  MOCK_TASKS,
  TASK_BENCHMARK_RUNS,
  MOCK_BIGQUERY_METRICS,
  TaskMeta,
} from "../lib/mockData";
import { fetchTasks, fetchMetricsSummary, startRun } from "../lib/api";
import { subscribeToRun, subscribeToRunEvents } from "../lib/firebase";

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState<"comparator" | "metrics" | "testbeds">("comparator");
  const [tasks, setTasks] = useState<TaskMeta[]>(MOCK_TASKS);
  const [metrics, setMetrics] = useState<any>(MOCK_BIGQUERY_METRICS);
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState<boolean>(false);
  const [selectedTaskId, setSelectedTaskId] = useState<string>("task_03_stuck_loop_api");
  const [activeFileName, setActiveFileName] = useState<string>("client.py");
  const [selectedModel, setSelectedModel] = useState<string>("gemini-2.5-flash");

  // Active run state mapped dynamically to selected task
  const initialTaskRuns = TASK_BENCHMARK_RUNS.task_03_stuck_loop_api;
  const [baselineRun, setBaselineRun] = useState<any>(initialTaskRuns.baseline);
  const [harnessedRun, setHarnessedRun] = useState<any>(initialTaskRuns.harnessed);
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [isLiveConnected, setIsLiveConnected] = useState<boolean>(false);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);

  // Sync run metrics whenever user switches tasks
  useEffect(() => {
    const taskRuns = TASK_BENCHMARK_RUNS[selectedTaskId] || TASK_BENCHMARK_RUNS.task_04_verbose_log_overflow;
    setBaselineRun(taskRuns.baseline);
    setHarnessedRun(taskRuns.harnessed);
    const activeTask = tasks.find((t) => t.id === selectedTaskId);
    if (activeTask && activeTask.files && activeTask.files[0]) {
      setActiveFileName(activeTask.files[0].name);
    }
  }, [selectedTaskId, tasks]);

  useEffect(() => {
    async function init() {
      try {
        const loadedTasks = await fetchTasks();
        if (loadedTasks && loadedTasks.length > 0) {
          setTasks((prev) =>
            loadedTasks.map((t: any) => {
              const matched = prev.find((p) => p.id === t.id);
              return matched ? { ...matched, ...t } : t;
            })
          );
        }
        const loadedMetrics = await fetchMetricsSummary();
        if (loadedMetrics) setMetrics(loadedMetrics);
        setIsLiveConnected(true);
      } catch {
        setIsLiveConnected(false);
      }
    }
    init();
  }, []);

  const currentTaskMeta = tasks.find((t) => t.id === selectedTaskId) || tasks[0];

  const triggerLiveDemo = () => {
    setActiveTab("comparator");
    setIsStreaming(true);

    const taskData = TASK_BENCHMARK_RUNS[selectedTaskId] || TASK_BENCHMARK_RUNS.task_04_verbose_log_overflow;

    // Reset initial state
    setBaselineRun({
      ...taskData.baseline,
      status: "RUNNING",
      events: [taskData.baseline.events[0]],
    });

    setHarnessedRun({
      ...taskData.harnessed,
      status: "RUNNING",
      events: [taskData.harnessed.events[0]],
    });

    // Step 1: Tool execution
    setTimeout(() => {
      setBaselineRun((prev: any) => ({
        ...prev,
        events: taskData.baseline.events.slice(0, 2),
      }));
      setHarnessedRun((prev: any) => ({
        ...prev,
        events: taskData.harnessed.events.slice(0, 2),
      }));
    }, 900);

    // Step 2: Failure on baseline vs Harness Guard/Compaction
    setTimeout(() => {
      setBaselineRun(taskData.baseline);
      setHarnessedRun((prev: any) => ({
        ...prev,
        events: taskData.harnessed.events.slice(0, Math.min(5, taskData.harnessed.events.length)),
      }));
    }, 2000);

    // Step 3: Harness verification passed
    setTimeout(() => {
      setHarnessedRun(taskData.harnessed);
      setIsStreaming(false);
    }, 3200);
  };

  const handleCustomLaunch = async (config: any) => {
    setActiveTab("comparator");
    setSelectedTaskId(config.taskId);
    if (config.modelId) setSelectedModel(config.modelId);

    if (config.isComparison) {
      triggerLiveDemo();
    } else {
      setIsStreaming(true);
      const res = await startRun(config.taskId, config.modelId, config.harnessConfig);
      if (res && res.run_id && !res.run_id.startsWith("mock_")) {
        setActiveRunId(res.run_id);
        subscribeToRunEvents(res.run_id, (events) => {
          if (events && events.length > 0) {
            setHarnessedRun((prev: any) => ({
              ...prev,
              events: events,
            }));
          }
        });

        subscribeToRun(res.run_id, (docData) => {
          if (docData) {
            setHarnessedRun((prev: any) => ({
              ...prev,
              status: docData.status || prev.status,
              tokensIn: docData.summary?.tokens_in_uncached || prev.tokensIn,
              costUsd: docData.summary?.total_cost_usd || prev.costUsd,
            }));
            if (docData.status === "RESOLVED" || docData.status === "ERROR") {
              setIsStreaming(false);
            }
          }
        });
      } else {
        triggerLiveDemo();
      }
    }
  };
  const handleTaskCreated = (newTask: TaskMeta) => {
    // Register dynamic run data
    TASK_BENCHMARK_RUNS[newTask.id] = {
      baseline: {
        runId: `run_b_${newTask.id}`,
        taskId: newTask.id,
        model: selectedModel,
        tier: "T0 (Unmanaged)",
        status: "TEST_FAILED",
        budgetCap: 32768,
        tokensIn: 2950,
        costUsd: 0.00025,
        events: [
          { turn_idx: 1, type: "TOOL_CALL", data: { tool: "bash", args: { command: newTask.eval_command || "pytest" } } },
          { turn_idx: 1, type: "TOOL_RESULT", data: { tool: "bash", is_error: true, output: `FAILED: Tests failed in ${newTask.id}` } },
          { turn_idx: 2, type: "ERROR", data: { reason: "FAILED", message: `Test failed without harness protection.` } },
        ],
      },
      harnessed: {
        runId: `run_h_${newTask.id}`,
        taskId: newTask.id,
        model: selectedModel,
        tier: "T4 (ContextT4 + AgentGuard)",
        status: "RESOLVED",
        budgetCap: 32768,
        tokensIn: 2150,
        costUsd: 0.00018,
        events: [
          { turn_idx: 1, type: "TOOL_CALL", data: { tool: "bash", args: { command: newTask.eval_command || "pytest" } } },
          { turn_idx: 1, type: "TOOL_RESULT", data: { tool: "bash", is_error: true, output: `FAILED: Tests failed initially in ${newTask.id}.` } },
          { turn_idx: 2, type: "GUARD_EVENT", data: { badge: "RBW_PASSED", output: `Read-Before-Write verified on ${newTask.files[0]?.name || "app.py"}.` } },
          { turn_idx: 2, type: "TOOL_CALL", data: { tool: "edit_file", args: { path: newTask.files[0]?.name || "app.py" } } },
          { turn_idx: 2, type: "TOOL_RESULT", data: { tool: "edit_file", is_error: false, output: `Successfully repaired ${newTask.files[0]?.name || "app.py"}.` } },
          { turn_idx: 3, type: "TOOL_CALL", data: { tool: "bash", args: { command: newTask.eval_command || "pytest" } } },
          { turn_idx: 3, type: "TOOL_RESULT", data: { tool: "bash", is_error: false, output: `${newTask.eval_command} PASSED [100%]\n1 passed in 0.03s` } },
          { turn_idx: 3, type: "RUN_FINISH", data: { final_message: `Custom task resolved cleanly with pytest validation.` } },
        ],
      },
    };

    setTasks((prev) => [newTask, ...prev.filter((t) => t.id !== newTask.id)]);
    setSelectedTaskId(newTask.id);
    if (newTask.files && newTask.files[0]) {
      setActiveFileName(newTask.files[0].name);
    }
    setActiveTab("comparator");
  };

  return (
    <div className="h-screen w-screen flex flex-col bg-zinc-100 text-zinc-900 font-sans overflow-hidden select-none">
      {/* ──────────────── Top Window Bar ──────────────── */}
      <header className="h-10 px-3 bg-zinc-200 border-b border-zinc-300 flex items-center justify-between shrink-0 text-xs font-mono">
        {/* Left: Window Controls & Breadcrumb */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-zinc-400 inline-block" />
            <span className="w-2.5 h-2.5 rounded-full bg-zinc-400 inline-block" />
            <span className="w-2.5 h-2.5 rounded-full bg-zinc-400 inline-block" />
          </div>

          <div className="flex items-center gap-1.5 pl-2 border-l border-zinc-300 text-zinc-600 text-[11px]">
            <span className="font-bold text-zinc-800">HARNESS KIT</span>
            <span>/</span>
            <span>testbeds</span>
            <span>/</span>
            <span className="text-zinc-900 font-semibold bg-white/60 px-1.5 py-0.5 rounded border border-zinc-300">
              {selectedTaskId}
            </span>
          </div>
        </div>

        {/* Center: Gemini Model */}
        <div className="hidden sm:flex items-center gap-2">
          <span className="text-zinc-500 text-[10px]">MODEL:</span>
          <select
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            className="bg-white border border-zinc-300 px-2 py-0.5 rounded text-zinc-800 text-[11px] font-semibold focus:outline-hidden cursor-pointer"
          >
            <option value="gemini-2.5-flash">Gemini 2.5 Flash</option>
            <option value="gemini-2.5-pro">Gemini 2.5 Pro</option>
            <option value="gemini-1.5-pro">Gemini 1.5 Pro</option>
            <option value="gemini-1.5-flash">Gemini 1.5 Flash</option>
          </select>
        </div>

        {/* Right: Actions */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsCreateModalOpen(true)}
            className="px-2.5 py-1 rounded bg-zinc-200 hover:bg-zinc-300 text-zinc-800 border border-zinc-300 text-[11px] font-medium transition-colors flex items-center gap-1 cursor-pointer"
            title="Create your own custom evaluation task"
          >
            <span>+</span>
            <span>New Task</span>
          </button>

          <button
            onClick={triggerLiveDemo}
            disabled={isStreaming}
            className="px-2.5 py-1 rounded bg-zinc-200 hover:bg-zinc-300 text-zinc-800 border border-zinc-300 text-[11px] font-medium transition-colors disabled:opacity-50 flex items-center gap-1 cursor-pointer"
          >
            <span>⚡</span>
            <span>Replay Trace</span>
          </button>

          <button
            onClick={() => setIsModalOpen(true)}
            className="px-3 py-1 rounded bg-zinc-900 hover:bg-zinc-800 text-white text-[11px] font-medium transition-colors flex items-center gap-1 cursor-pointer shadow-2xs"
          >
            <span>▶</span>
            <span>Run Eval</span>
          </button>
        </div>
      </header>

      {/* ──────────────── Tabs Bar ──────────────── */}
      <nav className="h-8 px-3 bg-zinc-200/50 border-b border-zinc-300 flex items-center justify-between shrink-0 text-xs font-mono">
        <div className="flex items-center gap-1">
          <button
            onClick={() => setActiveTab("comparator")}
            className={`px-3 py-1 rounded text-[11px] font-medium transition-colors flex items-center gap-1.5 ${
              activeTab === "comparator"
                ? "bg-white text-zinc-900 border border-zinc-300 shadow-2xs font-semibold"
                : "text-zinc-600 hover:text-zinc-900"
            }`}
          >
            <span>📁</span>
            <span>Dual-Pane Comparator</span>
          </button>

          <button
            onClick={() => setActiveTab("metrics")}
            className={`px-3 py-1 rounded text-[11px] font-medium transition-colors flex items-center gap-1.5 ${
              activeTab === "metrics"
                ? "bg-white text-zinc-900 border border-zinc-300 shadow-2xs font-semibold"
                : "text-zinc-600 hover:text-zinc-900"
            }`}
          >
            <span>📊</span>
            <span>BigQuery Telemetry</span>
          </button>

          <button
            onClick={() => setActiveTab("testbeds")}
            className={`px-3 py-1 rounded text-[11px] font-medium transition-colors flex items-center gap-1.5 ${
              activeTab === "testbeds"
                ? "bg-white text-zinc-900 border border-zinc-300 shadow-2xs font-semibold"
                : "text-zinc-600 hover:text-zinc-900"
            }`}
          >
            <span>🧪</span>
            <span>Benchmark Testbeds</span>
          </button>
        </div>

        <div className="flex items-center gap-2 text-[10px] text-zinc-500 font-mono">
          <span className={`w-1.5 h-1.5 rounded-full ${isLiveConnected ? "bg-emerald-500" : "bg-zinc-400"}`} />
          <span>{isLiveConnected ? "API Connected :8000" : "Local Runner"}</span>
        </div>
      </nav>

      {/* ──────────────── Main Workspace Body ──────────────── */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Explorer Sidebar */}
        <aside className="w-56 bg-zinc-100 border-r border-zinc-300 p-2.5 flex flex-col justify-between shrink-0 font-mono text-xs overflow-y-auto">
          <div className="space-y-2">
            <div className="flex items-center justify-between px-1">
              <span className="text-[10px] uppercase font-bold tracking-wider text-zinc-500">
                TESTBEDS ({tasks.length})
              </span>
              <button
                onClick={() => setIsCreateModalOpen(true)}
                className="text-[10px] text-zinc-700 hover:text-zinc-900 bg-zinc-200/80 hover:bg-zinc-300 px-1.5 py-0.5 rounded cursor-pointer font-semibold transition-colors"
                title="Create your own custom evaluation task"
              >
                + New
              </button>
            </div>

            <div className="space-y-0.5">
              {tasks.map((task) => {
                const isSelected = task.id === selectedTaskId;
                return (
                  <div key={task.id} className="space-y-0.5">
                    <button
                      onClick={() => {
                        setSelectedTaskId(task.id);
                        if (task.files && task.files[0]) {
                          setActiveFileName(task.files[0].name);
                        }
                        setActiveTab("comparator");
                      }}
                      className={`w-full text-left px-2 py-1 rounded transition-colors flex items-center gap-1.5 text-[11px] cursor-pointer truncate ${
                        isSelected
                          ? "bg-zinc-300 text-zinc-900 font-bold border border-zinc-400/60"
                          : "text-zinc-700 hover:bg-zinc-200"
                      }`}
                    >
                      <span className="text-[9px] text-zinc-400">
                        {isSelected ? "▼" : "▶"}
                      </span>
                      <span className="truncate">{task.id}</span>
                    </button>

                    {isSelected && task.files && (
                      <div className="pl-3 py-0.5 space-y-0.5 border-l border-zinc-300 ml-2">
                        {task.files.map((file, fIdx) => {
                          const isFileActive = activeFileName === file.name;
                          return (
                            <button
                              key={fIdx}
                              onClick={() => {
                                setSelectedTaskId(task.id);
                                setActiveFileName(file.name);
                                setActiveTab("comparator");
                              }}
                              className={`w-full text-left px-1.5 py-0.5 text-[10px] flex items-center gap-1 rounded transition-colors cursor-pointer ${
                                isFileActive
                                  ? "bg-zinc-200/90 text-zinc-900 font-bold border border-zinc-300/80"
                                  : "text-zinc-600 hover:bg-zinc-200/60 hover:text-zinc-900"
                              }`}
                            >
                              <span>{file.name.startsWith("test_") ? "🧪" : "🐍"}</span>
                              <span className="truncate">{file.name}</span>
                            </button>
                          );
                        })}

                        {/* Clickable Diff file */}
                        <button
                          onClick={() => {
                            setSelectedTaskId(task.id);
                            setActiveFileName("gold_patch.diff");
                            setActiveTab("comparator");
                          }}
                          className={`w-full text-left px-1.5 py-0.5 text-[10px] flex items-center gap-1 rounded transition-colors cursor-pointer ${
                            activeFileName === "gold_patch.diff"
                              ? "bg-zinc-200/90 text-zinc-900 font-bold border border-zinc-300/80"
                              : "text-zinc-500 hover:bg-zinc-200/60 hover:text-zinc-900"
                          }`}
                        >
                          <span>±</span>
                          <span className="truncate">gold_patch.diff</span>
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Quick Metrics Footer */}
          <div className="pt-2 border-t border-zinc-200 space-y-1 text-[10px] text-zinc-600">
            <div className="flex justify-between">
              <span>Pass Rate:</span>
              <strong className="text-zinc-900">80.0%</strong>
            </div>
            <div className="flex justify-between">
              <span>Savings:</span>
              <strong className="text-emerald-700">-75.0%</strong>
            </div>
          </div>
        </aside>

        {/* Center Workspace Content */}
        <main className="flex-1 p-3 bg-zinc-50 overflow-y-auto">
          {activeTab === "comparator" && (
            <DualPaneComparator
              baselineRun={baselineRun}
              harnessedRun={harnessedRun}
              isStreaming={isStreaming}
              selectedTaskMeta={currentTaskMeta}
              activeFileName={activeFileName}
              onSelectFile={(name) => setActiveFileName(name)}
            />
          )}

          {activeTab === "metrics" && (
            <div className="p-2 max-w-5xl">
              <MetricsScorecard metrics={metrics} />
            </div>
          )}

          {activeTab === "testbeds" && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 font-mono text-xs p-1">
              {tasks.map((task) => (
                <div
                  key={task.id}
                  className={`bg-white p-3 rounded-lg border transition-all flex flex-col justify-between ${
                    task.id === selectedTaskId
                      ? "border-zinc-500 shadow-sm ring-1 ring-zinc-400"
                      : "border-zinc-200 hover:border-zinc-300"
                  }`}
                >
                  <div>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-100 text-zinc-700 font-semibold">
                      {task.category}
                    </span>
                    <h4 className="font-bold text-xs text-zinc-900 mt-2 mb-1">{task.title}</h4>
                    <p className="text-[11px] text-zinc-600 font-sans mb-3 line-clamp-2">
                      {task.description}
                    </p>
                  </div>

                  <button
                    onClick={() => {
                      setSelectedTaskId(task.id);
                      setActiveTab("comparator");
                    }}
                    className="w-full py-1 rounded bg-zinc-100 hover:bg-zinc-200 border border-zinc-300 text-zinc-800 text-[11px] font-medium"
                  >
                    Open in Editor →
                  </button>
                </div>
              ))}
            </div>
          )}
        </main>
      </div>

      {/* ──────────────── Bottom Status Bar ──────────────── */}
      <footer className="h-6 px-3 bg-zinc-200 border-t border-zinc-300 flex items-center justify-between text-[10px] font-mono text-zinc-600 shrink-0">
        <div className="flex items-center gap-3">
          <span className="font-semibold text-zinc-800">⎇ main</span>
          <span>•</span>
          <span>Python 3.11</span>
          <span>•</span>
          <span>UTF-8</span>
          <span>•</span>
          <span>Task: {selectedTaskId}</span>
        </div>

        <div className="flex items-center gap-3">
          <span>{selectedModel}</span>
          <span>•</span>
          <span>Tokens: {harnessedRun.tokensIn?.toLocaleString() || "4,120"}</span>
          <span>•</span>
          <span className="text-emerald-800 font-semibold">BigQuery Synced</span>
        </div>
      </footer>

      {/* Evaluation Launch Modal */}
      <LaunchModal
        tasks={tasks}
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onLaunch={handleCustomLaunch}
        selectedTaskId={selectedTaskId}
      />

      {/* Custom Task Benchmark Creation Modal */}
      <CreateTaskModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onTaskCreated={handleTaskCreated}
      />
    </div>
  );
}
