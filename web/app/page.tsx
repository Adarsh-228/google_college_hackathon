"use client";

import React, { useState, useEffect } from "react";
import { DualPaneComparator } from "../components/DualPaneComparator";
import { MetricsScorecard } from "../components/MetricsScorecard";
import { LaunchModal } from "../components/LaunchModal";
import {
  MOCK_TASKS,
  MOCK_BASELINE_RUN,
  MOCK_HARNESSED_RUN,
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

  // Active run state
  const [baselineRun, setBaselineRun] = useState<any>(MOCK_BASELINE_RUN);
  const [harnessedRun, setHarnessedRun] = useState<any>(MOCK_HARNESSED_RUN);
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [isLiveConnected, setIsLiveConnected] = useState<boolean>(false);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);

  useEffect(() => {
    // Attempt connecting to local API
    async function init() {
      try {
        const loadedTasks = await fetchTasks();
        setTasks(loadedTasks);
        const loadedMetrics = await fetchMetricsSummary();
        setMetrics(loadedMetrics);
        setIsLiveConnected(true);
      } catch {
        setIsLiveConnected(false);
      }
    }
    init();
  }, []);

  const triggerLiveDemo = () => {
    setActiveTab("comparator");
    setIsStreaming(true);

    // Initial empty state
    setBaselineRun({
      ...MOCK_BASELINE_RUN,
      status: "RUNNING",
      tokensIn: 1400,
      events: [MOCK_BASELINE_RUN.events[0]],
    });

    setHarnessedRun({
      ...MOCK_HARNESSED_RUN,
      status: "RUNNING",
      tokensIn: 1400,
      events: [MOCK_HARNESSED_RUN.events[0]],
    });

    // Step 1: Turn 1 (Tool Call pytest)
    setTimeout(() => {
      setBaselineRun((prev: any) => ({
        ...prev,
        events: [...prev.events, MOCK_BASELINE_RUN.events[1]],
      }));
      setHarnessedRun((prev: any) => ({
        ...prev,
        events: [...prev.events, MOCK_HARNESSED_RUN.events[1]],
      }));
    }, 1000);

    // Step 2: Turn 2 (Context threshold & Compaction)
    setTimeout(() => {
      // Baseline overflows!
      setBaselineRun((prev: any) => ({
        ...prev,
        status: "CONTEXT_OVERFLOW",
        tokensIn: 34100,
        events: [...prev.events, MOCK_BASELINE_RUN.events[2], MOCK_BASELINE_RUN.events[3]],
      }));

      // Harnessed applies M1 Elision at 60%!
      setHarnessedRun((prev: any) => ({
        ...prev,
        tokensIn: 2150,
        events: [...prev.events, MOCK_HARNESSED_RUN.events[2], MOCK_HARNESSED_RUN.events[3]],
      }));
    }, 2200);

    // Step 3: Turn 3-4 (Harness edits and passes)
    setTimeout(() => {
      setHarnessedRun((prev: any) => ({
        ...prev,
        tokensIn: 3200,
        events: [
          ...prev.events,
          MOCK_HARNESSED_RUN.events[4],
          MOCK_HARNESSED_RUN.events[5],
          MOCK_HARNESSED_RUN.events[6],
          MOCK_HARNESSED_RUN.events[7],
        ],
      }));
    }, 3200);

    // Step 4: Verification passed
    setTimeout(() => {
      setHarnessedRun((prev: any) => ({
        ...prev,
        status: "RESOLVED",
        tokensIn: 4120,
        events: [
          ...prev.events,
          MOCK_HARNESSED_RUN.events[8],
          MOCK_HARNESSED_RUN.events[9],
          MOCK_HARNESSED_RUN.events[10],
        ],
      }));
      setIsStreaming(false);
    }, 4200);
  };

  const handleCustomLaunch = async (config: any) => {
    setActiveTab("comparator");
    if (config.isComparison) {
      triggerLiveDemo();
    } else {
      setIsStreaming(true);
      const res = await startRun(config.taskId, config.modelId, config.harnessConfig);
      if (res && res.run_id && !res.run_id.startsWith("mock_")) {
        setActiveRunId(res.run_id);
        // Connect live Firestore real-time subscriptions
        const unsubEvents = subscribeToRunEvents(res.run_id, (events) => {
          if (events && events.length > 0) {
            setHarnessedRun((prev: any) => ({
              ...prev,
              events: events,
            }));
          }
        });

        const unsubDoc = subscribeToRun(res.run_id, (docData) => {
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

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      {/* ---------------- Navigation / Header ---------------- */}
      <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-zinc-200">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-zinc-900 flex items-center justify-center text-white font-mono font-bold text-sm shadow-sm">
              HK
            </div>
            <h1 className="text-xl font-bold tracking-tight text-zinc-900">
              HARNESS KIT
            </h1>
            <span className="text-[11px] px-2 py-0.5 rounded-full bg-zinc-200 text-zinc-700 font-mono font-medium">
              Google Cloud Edition
            </span>
          </div>
          <p className="text-xs text-zinc-500 mt-1">
            Don&apos;t guess your agent&apos;s harness. Measure it. Based on <em>arXiv:2609.20804</em>.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2 text-xs">
          <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white border border-zinc-200 text-zinc-600 font-mono text-[11px]">
            <span className="w-2 h-2 rounded-full bg-amber-500" />
            <span>Firebase: <strong>rbux-37584</strong> (Live Firestore)</span>
          </div>

          <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white border border-zinc-200 text-zinc-600 font-mono text-[11px]">
            <span className={`w-2 h-2 rounded-full ${isLiveConnected ? "bg-emerald-500" : "bg-zinc-400"}`} />
            {isLiveConnected ? "Cloud Run API" : "Local Runner"}
          </div>

          <button
            onClick={triggerLiveDemo}
            disabled={isStreaming}
            className="px-3.5 py-2 rounded-lg bg-zinc-200 text-zinc-800 font-medium hover:bg-zinc-300 transition-colors shadow-sm disabled:opacity-50"
          >
            ⚡ Run Demo (Task 04 Overflow)
          </button>

          <button
            onClick={() => setIsModalOpen(true)}
            className="px-4 py-2 rounded-lg bg-zinc-900 text-white font-medium hover:bg-zinc-800 transition-colors shadow-sm flex items-center gap-1.5"
          >
            <span>⚔️</span>
            <span>New Evaluation</span>
          </button>
        </div>
      </header>

      {/* ---------------- Navigation Tabs ---------------- */}
      <div className="flex items-center gap-2 border-b border-zinc-200 pb-2 text-xs font-medium">
        <button
          onClick={() => setActiveTab("comparator")}
          className={`px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5 ${
            activeTab === "comparator"
              ? "bg-zinc-900 text-white shadow-sm font-semibold"
              : "text-zinc-600 hover:text-zinc-900 hover:bg-zinc-100"
          }`}
        >
          <span>Dual-Pane Live Comparator</span>
          <span className="text-[10px] px-1.5 py-0.2 bg-white/20 rounded font-mono">A/B</span>
        </button>

        <button
          onClick={() => setActiveTab("metrics")}
          className={`px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5 ${
            activeTab === "metrics"
              ? "bg-zinc-900 text-white shadow-sm font-semibold"
              : "text-zinc-600 hover:text-zinc-900 hover:bg-zinc-100"
          }`}
        >
          <span>AgentTrace BigQuery Analytics</span>
          <span className="text-[10px] px-1.5 py-0.2 bg-white/20 rounded font-mono">SQL</span>
        </button>

        <button
          onClick={() => setActiveTab("testbeds")}
          className={`px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5 ${
            activeTab === "testbeds"
              ? "bg-zinc-900 text-white shadow-sm font-semibold"
              : "text-zinc-600 hover:text-zinc-900 hover:bg-zinc-100"
          }`}
        >
          <span>Benchmark Testbeds (5)</span>
        </button>
      </div>

      {/* ---------------- Screen 1: Dual-Pane Comparator ---------------- */}
      {activeTab === "comparator" && (
        <main className="space-y-4">
          <DualPaneComparator
            baselineRun={baselineRun}
            harnessedRun={harnessedRun}
            isStreaming={isStreaming}
          />
        </main>
      )}

      {/* ---------------- Screen 2: AgentTrace Scorecard ---------------- */}
      {activeTab === "metrics" && (
        <main>
          <MetricsScorecard metrics={metrics} />
        </main>
      )}

      {/* ---------------- Screen 3: Testbeds Directory ---------------- */}
      {activeTab === "testbeds" && (
        <main className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {tasks.map((task) => (
            <div
              key={task.id}
              className="bg-white p-4 rounded-xl border border-zinc-200 shadow-sm flex flex-col justify-between"
            >
              <div>
                <div className="flex justify-between items-start mb-2">
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-100 text-zinc-600">
                    {task.category}
                  </span>
                  <span className="text-[10px] font-mono text-zinc-400">pytest</span>
                </div>
                <h4 className="font-semibold text-sm text-zinc-900 mb-1">{task.title}</h4>
                <p className="text-xs text-zinc-500 mb-3">{task.description}</p>
              </div>

              <button
                onClick={() => {
                  setSelectedTaskInModal(task.id);
                  setIsModalOpen(true);
                }}
                className="w-full py-1.5 rounded-lg border border-zinc-300 text-zinc-700 font-medium text-xs hover:bg-zinc-50"
              >
                Launch on this Testbed
              </button>
            </div>
          ))}
        </main>
      )}

      {/* Launch Configuration Modal */}
      <LaunchModal
        tasks={tasks}
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onLaunch={handleCustomLaunch}
      />
    </div>
  );
}

function setSelectedTaskInModal(id: string) {
  // Auxiliary helper
}
