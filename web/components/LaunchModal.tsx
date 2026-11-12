import React, { useState } from "react";
import { TaskMeta } from "../lib/mockData";

interface LaunchModalProps {
  tasks: TaskMeta[];
  isOpen: boolean;
  onClose: () => void;
  onLaunch: (config: any) => void;
  selectedTaskId?: string;
}

export const LaunchModal: React.FC<LaunchModalProps> = ({
  tasks,
  isOpen,
  onClose,
  onLaunch,
  selectedTaskId,
}) => {
  const [selectedTask, setSelectedTask] = useState<string>(
    selectedTaskId || tasks[3]?.id || tasks[0]?.id || "task_04_verbose_log_overflow"
  );
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-900/40 backdrop-blur-xs p-4 animate-in fade-in duration-100">
      <div className="bg-white w-full max-w-lg rounded-xl border border-zinc-300 shadow-xl overflow-hidden font-sans">
        {/* Modal Window Header */}
        <div className="px-4 py-3 bg-zinc-100 border-b border-zinc-200 flex justify-between items-center">
          <div className="flex items-center gap-2">
            <div className="flex gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-zinc-300 border border-zinc-400" />
              <span className="w-2.5 h-2.5 rounded-full bg-zinc-300 border border-zinc-400" />
              <span className="w-2.5 h-2.5 rounded-full bg-zinc-300 border border-zinc-400" />
            </div>
            <h3 className="font-semibold text-zinc-900 text-xs font-mono ml-1">
              Launch Evaluation Run • Gemini Configuration
            </h3>
          </div>
          <button
            onClick={onClose}
            className="text-zinc-400 hover:text-zinc-700 text-sm font-bold px-2 py-0.5 rounded hover:bg-zinc-200"
          >
            ✕
          </button>
        </div>

        <div className="p-5 space-y-4 text-xs">
          {/* Benchmark Task Picker */}
          <div>
            <label className="block font-semibold text-zinc-700 mb-1">
              Benchmark Task
            </label>
            <select
              value={selectedTask}
              onChange={(e) => setSelectedTask(e.target.value)}
              className="w-full p-2 bg-zinc-50 border border-zinc-300 rounded-lg text-zinc-900 font-mono text-xs focus:ring-1 focus:ring-zinc-500 focus:outline-hidden"
            >
              {tasks.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.title} ({t.category})
                </option>
              ))}
            </select>
            {currentTaskMeta && (
              <p className="text-[11px] text-zinc-500 mt-1 italic leading-relaxed">
                {currentTaskMeta.description}
              </p>
            )}
          </div>

          {/* Model and Budget Cap */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-zinc-700 mb-1">
                Gemini Model
              </label>
              <select
                value={modelId}
                onChange={(e) => setModelId(e.target.value)}
                className="w-full p-2 bg-zinc-50 border border-zinc-300 rounded-lg font-mono text-xs text-zinc-900 focus:outline-hidden"
              >
                <option value="gemini-2.5-flash">Gemini 2.5 Flash (Recommended)</option>
                <option value="gemini-2.5-pro">Gemini 2.5 Pro</option>
                <option value="gemini-1.5-pro">Gemini 1.5 Pro</option>
                <option value="gemini-1.5-flash">Gemini 1.5 Flash</option>
              </select>
            </div>

            <div>
              <label className="block font-semibold text-zinc-700 mb-1">
                Budget Ceiling
              </label>
              <select
                value={budgetCap}
                onChange={(e) => setBudgetCap(Number(e.target.value))}
                className="w-full p-2 bg-zinc-50 border border-zinc-300 rounded-lg font-mono text-xs text-zinc-900 focus:outline-hidden"
              >
                <option value={32768}>32,768 tokens (Standard Cap)</option>
                <option value={65536}>65,536 tokens</option>
                <option value={131072}>131,072 tokens</option>
              </select>
            </div>
          </div>

          {/* Context Tier & Tools */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-semibold text-zinc-700 mb-1">
                Context Management
              </label>
              <select
                value={contextTier}
                onChange={(e) => setContextTier(e.target.value)}
                className="w-full p-2 bg-zinc-50 border border-zinc-300 rounded-lg font-mono text-xs text-zinc-900 focus:outline-hidden"
              >
                <option value="T4">ContextT4 (M1 Elide @ 60% + M3 Summary)</option>
                <option value="T0">T0 (Unmanaged Baseline)</option>
              </select>
            </div>

            <div>
              <label className="block font-semibold text-zinc-700 mb-1">
                Tool Protocol
              </label>
              <select
                value={toolMode}
                onChange={(e) => setToolMode(e.target.value)}
                className="w-full p-2 bg-zinc-50 border border-zinc-300 rounded-lg font-mono text-xs text-zinc-900 focus:outline-hidden"
              >
                <option value="predefined">Predefined (read, edit, bash)</option>
                <option value="bash_only">Bash Only (Terminal fallback)</option>
              </select>
            </div>
          </div>

          {/* AgentGuard Substrate Switches */}
          <div className="p-3 bg-zinc-50 rounded-lg border border-zinc-200 space-y-2">
            <span className="font-semibold text-zinc-800 block text-[11px] uppercase tracking-wider">
              AgentGuard Substrate Protection
            </span>

            <div className="grid grid-cols-3 gap-2 text-[11px]">
              <label className="flex items-center gap-1.5 cursor-pointer text-zinc-700">
                <input
                  type="checkbox"
                  checked={enableRbw}
                  onChange={(e) => setEnableRbw(e.target.checked)}
                  className="rounded border-zinc-300 text-zinc-800 focus:ring-0"
                />
                <span>Read-Before-Write</span>
              </label>

              <label className="flex items-center gap-1.5 cursor-pointer text-zinc-700">
                <input
                  type="checkbox"
                  checked={enableLint}
                  onChange={(e) => setEnableLint(e.target.checked)}
                  className="rounded border-zinc-300 text-zinc-800 focus:ring-0"
                />
                <span>Zero-Turn Lint</span>
              </label>

              <label className="flex items-center gap-1.5 cursor-pointer text-zinc-700">
                <input
                  type="checkbox"
                  checked={enableStreak}
                  onChange={(e) => setEnableStreak(e.target.checked)}
                  className="rounded border-zinc-300 text-zinc-800 focus:ring-0"
                />
                <span>Streak Breaker</span>
              </label>
            </div>
          </div>

          {/* Launch Buttons */}
          <div className="flex gap-2 pt-2 border-t border-zinc-200">
            <button
              onClick={() => handleSubmit(true)}
              className="flex-1 py-2 rounded-lg bg-zinc-900 text-white font-medium hover:bg-zinc-800 transition-colors text-xs flex items-center justify-center gap-1.5"
            >
              <span>⚔️</span>
              <span>Launch A/B Comparator Run</span>
            </button>

            <button
              onClick={() => handleSubmit(false)}
              className="py-2 px-4 rounded-lg bg-zinc-200 text-zinc-800 font-medium hover:bg-zinc-300 transition-colors text-xs"
            >
              Single Run
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
