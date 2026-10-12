import React, { useState } from "react";
import { TaskMeta } from "../lib/mockData";

interface LaunchModalProps {
  tasks: TaskMeta[];
  isOpen: boolean;
  onClose: () => void;
  onLaunch: (config: any) => void;
}

export const LaunchModal: React.FC<LaunchModalProps> = ({
  tasks,
  isOpen,
  onClose,
  onLaunch,
}) => {
  const [selectedTask, setSelectedTask] = useState<string>(tasks[3]?.id || tasks[0]?.id || "task_04_verbose_log_overflow");
  const [modelId, setModelId] = useState<string>("gemini-2.5-flash");
  const [budgetCap, setBudgetCap] = useState<number>(32768);
  const [contextTier, setContextTier] = useState<string>("T4");
  const [enableRbw, setEnableRbw] = useState<boolean>(true);
  const [enableLint, setEnableLint] = useState<boolean>(true);
  const [enableStreak, setEnableStreak] = useState<boolean>(true);
  const [toolMode, setToolMode] = useState<string>("predefined");
  const [enablePlanning, setEnablePlanning] = useState<boolean>(true);

  if (!isOpen) return null;

  const currentTaskMeta = tasks.find((t) => t.id === selectedTask);

  const handleSubmit = (isComparison: boolean) => {
    onLaunch({
      taskId: selectedTask,
      modelId,
      isComparison,
      harnessConfig: {
        budget_cap: budgetCap,
        context_tier: contextTier,
        enable_rbw: enableRbw,
        enable_lint: enableLint,
        enable_streak_breaker: enableStreak,
        tool_mode: toolMode,
        enable_planning: enablePlanning,
      },
    });
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-white w-full max-w-xl rounded-2xl border border-zinc-200 shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="p-4 bg-zinc-50 border-b border-zinc-200 flex justify-between items-center">
          <div>
            <h3 className="font-bold text-zinc-900 text-sm">Launch Evaluation Task</h3>
            <p className="text-xs text-zinc-500">Configure ablation parameters & baseline comparison</p>
          </div>
          <button
            onClick={onClose}
            className="text-zinc-400 hover:text-zinc-700 text-lg font-bold px-2"
          >
            ×
          </button>
        </div>

        <div className="p-5 space-y-4 text-xs">
          {/* Task Picker */}
          <div>
            <label className="block font-semibold text-zinc-700 mb-1">Select Benchmark Task</label>
            <select
              value={selectedTask}
              onChange={(e) => setSelectedTask(e.target.value)}
              className="w-full p-2 bg-zinc-50 border border-zinc-300 rounded-lg text-zinc-900 font-medium focus:ring-1 focus:ring-zinc-500"
            >
              {tasks.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.title} ({t.category})
                </option>
              ))}
            </select>
            {currentTaskMeta && (
              <p className="text-[11px] text-zinc-500 mt-1 italic">
                {currentTaskMeta.description}
              </p>
            )}
          </div>

          {/* Model & Budget Grid */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-zinc-700 mb-1">Model Selection</label>
              <select
                value={modelId}
                onChange={(e) => setModelId(e.target.value)}
                className="w-full p-2 bg-zinc-50 border border-zinc-300 rounded-lg font-mono text-zinc-900"
              >
                <option value="gemini-2.5-flash">Gemini 2.5 Flash (Default)</option>
                <option value="gemini-2.5-pro">Gemini 2.5 Pro</option>
              </select>
            </div>

            <div>
              <label className="block font-semibold text-zinc-700 mb-1">Token Budget Cap</label>
              <select
                value={budgetCap}
                onChange={(e) => setBudgetCap(Number(e.target.value))}
                className="w-full p-2 bg-zinc-50 border border-zinc-300 rounded-lg font-mono text-zinc-900"
              >
                <option value={32768}>32k Cap (Paper binding sweep)</option>
                <option value={65536}>64k Cap</option>
                <option value={131072}>128k Cap</option>
              </select>
            </div>
          </div>

          {/* Context Tier & Tool Mode */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-zinc-700 mb-1">Context Management Tier</label>
              <select
                value={contextTier}
                onChange={(e) => setContextTier(e.target.value)}
                className="w-full p-2 bg-zinc-50 border border-zinc-300 rounded-lg font-mono text-zinc-900"
              >
                <option value="T4">Tier 4 (Staged Elision + Summary)</option>
                <option value="T1">Tier 1 (Elision alone @ B2)</option>
                <option value="T3">Tier 3 (Summarization alone @ B2)</option>
                <option value="T0">Tier 0 (Unmanaged Baseline)</option>
              </select>
            </div>

            <div>
              <label className="block font-semibold text-zinc-700 mb-1">Action Space</label>
              <select
                value={toolMode}
                onChange={(e) => setToolMode(e.target.value)}
                className="w-full p-2 bg-zinc-50 border border-zinc-300 rounded-lg font-mono text-zinc-900"
              >
                <option value="predefined">Predefined Tools (read/edit/bash)</option>
                <option value="bash_only">Bash-Only + Linter</option>
              </select>
            </div>
          </div>

          {/* Substrate Guard Toggles */}
          <div className="p-3 bg-zinc-50 border border-zinc-200 rounded-xl space-y-2">
            <span className="font-semibold text-zinc-700 block text-[11px] uppercase tracking-wider">
              AgentGuard Substrate Gates
            </span>
            <div className="grid grid-cols-3 gap-2">
              <label className="flex items-center gap-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={enableRbw}
                  onChange={(e) => setEnableRbw(e.target.checked)}
                  className="rounded border-zinc-300 text-zinc-900 focus:ring-0"
                />
                <span className="text-zinc-700">Read-Before-Write</span>
              </label>

              <label className="flex items-center gap-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={enableLint}
                  onChange={(e) => setEnableLint(e.target.checked)}
                  className="rounded border-zinc-300 text-zinc-900 focus:ring-0"
                />
                <span className="text-zinc-700">Zero-Turn Linter</span>
              </label>

              <label className="flex items-center gap-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={enableStreak}
                  onChange={(e) => setEnableStreak(e.target.checked)}
                  className="rounded border-zinc-300 text-zinc-900 focus:ring-0"
                />
                <span className="text-zinc-700">Streak Breaker</span>
              </label>
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="p-4 bg-zinc-50 border-t border-zinc-200 flex justify-end gap-2 text-xs">
          <button
            onClick={onClose}
            className="px-3 py-2 rounded-lg border border-zinc-300 text-zinc-700 font-medium hover:bg-zinc-100"
          >
            Cancel
          </button>
          <button
            onClick={() => handleSubmit(false)}
            className="px-3.5 py-2 rounded-lg bg-zinc-200 text-zinc-800 font-medium hover:bg-zinc-300"
          >
            Run Single Task
          </button>
          <button
            onClick={() => handleSubmit(true)}
            className="px-4 py-2 rounded-lg bg-zinc-900 text-white font-medium hover:bg-zinc-800 shadow-sm"
          >
            ⚔️ Run A/B Comparison
          </button>
        </div>
      </div>
    </div>
  );
};
