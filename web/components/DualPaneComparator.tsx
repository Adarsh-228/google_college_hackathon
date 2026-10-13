import React from "react";
import { TokenMeter } from "./TokenMeter";
import { CodeEditor } from "./CodeEditor";
import { TerminalConsole } from "./TerminalConsole";
import { TaskMeta } from "../lib/mockData";

interface DualPaneProps {
  baselineRun: any;
  harnessedRun: any;
  isStreaming?: boolean;
  selectedTaskMeta?: TaskMeta;
  activeFileName?: string;
  onSelectFile?: (filename: string) => void;
}

export const DualPaneComparator: React.FC<DualPaneProps> = ({
  baselineRun,
  harnessedRun,
  isStreaming = false,
  selectedTaskMeta,
  activeFileName,
  onSelectFile,
}) => {
  const files = selectedTaskMeta?.files || [];
  const primaryFile = files[0] || {
    name: "client.py",
    language: "python",
    content: "# empty",
    fixedContent: "# empty",
  };
  const testFile = files[1] || {
    name: "test_client.py",
    language: "python",
    content: "# test",
  };

  // Determine currently active file
  const currentFileName = activeFileName || primaryFile.name;
  const isDiff = currentFileName.endsWith(".diff");
  const isTest = currentFileName.startsWith("test_");

  let leftCode = primaryFile.content;
  let rightCode = primaryFile.fixedContent || primaryFile.content;

  if (isDiff) {
    leftCode = selectedTaskMeta?.diff || "--- a/file.py\n+++ b/file.py";
    rightCode = selectedTaskMeta?.diff || "--- a/file.py\n+++ b/file.py";
  } else if (isTest) {
    leftCode = testFile.content;
    rightCode = testFile.content;
  }

  // Available file tabs for this task
  const fileTabs = [
    { name: primaryFile.name, icon: "🐍" },
    ...(testFile ? [{ name: testFile.name, icon: "🧪" }] : []),
    { name: "gold_patch.diff", icon: "±" },
  ];

  return (
    <div className="flex flex-col gap-3">
      {/* ── File Tabs Header Bar ── */}
      <div className="flex items-center justify-between px-2 py-1 bg-zinc-200/60 rounded-md border border-zinc-300/80 text-xs font-mono">
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-zinc-500 uppercase tracking-wider font-semibold mr-1">
            FILES:
          </span>
          {fileTabs.map((tab) => {
            const isTabActive = currentFileName === tab.name;
            return (
              <button
                key={tab.name}
                onClick={() => onSelectFile?.(tab.name)}
                className={`px-2.5 py-1 rounded text-[11px] font-medium transition-colors flex items-center gap-1.5 cursor-pointer ${
                  isTabActive
                    ? "bg-white text-zinc-900 border border-zinc-300 shadow-2xs font-bold"
                    : "text-zinc-600 hover:bg-zinc-200/80 hover:text-zinc-900"
                }`}
              >
                <span>{tab.icon}</span>
                <span>{tab.name}</span>
              </button>
            );
          })}
        </div>

        <div className="hidden sm:flex items-center gap-2 text-[10px] text-zinc-500">
          <span>Task: <strong>{selectedTaskMeta?.id}</strong></span>
          <span>•</span>
          <span className="text-zinc-700">Click tabs to inspect tests, patch, or source</span>
        </div>
      </div>

      {/* ── Side-by-side Comparator Grid ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {/* ── Left: Baseline Agent ── */}
        <div className="flex flex-col rounded-lg border border-zinc-200 bg-white overflow-hidden shadow-2xs">
          {/* Header */}
          <div className="p-2.5 bg-zinc-50 border-b border-zinc-200 flex items-center justify-between shrink-0">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-rose-500" />
              <span className="font-semibold text-xs text-zinc-900 font-mono">
                Baseline (T0 Unmanaged)
              </span>
            </div>
            <span
              className={`text-[10px] font-mono px-1.5 py-0.5 rounded font-semibold ${
                baselineRun.status === "CONTEXT_OVERFLOW"
                  ? "bg-rose-100 text-rose-800 border border-rose-200"
                  : baselineRun.status === "RESOLVED"
                  ? "bg-emerald-100 text-emerald-800 border border-emerald-200"
                  : "bg-zinc-100 text-zinc-700"
              }`}
            >
              {baselineRun.status}
            </span>
          </div>

          {/* Context Meter */}
          <div className="px-3 py-2 border-b border-zinc-100 bg-white shrink-0">
            <TokenMeter
              currentTokens={baselineRun.tokensIn || 1400}
              budgetCap={baselineRun.budgetCap || 32768}
            />
          </div>

          {/* Source Code */}
          <div className="p-2.5 bg-zinc-50/40">
            <CodeEditor
              filename={currentFileName}
              code={leftCode}
              diffMode={isDiff}
            />
          </div>
        </div>

        {/* ── Right: Harness Kit Agent ── */}
        <div className="flex flex-col rounded-lg border border-zinc-200 bg-white overflow-hidden shadow-2xs">
          {/* Header */}
          <div className="p-2.5 bg-zinc-50 border-b border-zinc-200 flex items-center justify-between shrink-0">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-600" />
              <span className="font-semibold text-xs text-zinc-900 font-mono">
                Harness Kit (T4 + Gemini)
              </span>
            </div>
            <span
              className={`text-[10px] font-mono px-1.5 py-0.5 rounded font-semibold ${
                harnessedRun.status === "RESOLVED"
                  ? "bg-emerald-100 text-emerald-800 border border-emerald-200"
                  : "bg-zinc-100 text-zinc-700"
              }`}
            >
              {harnessedRun.status === "RESOLVED" ? "PASSED (100%)" : harnessedRun.status}
            </span>
          </div>

          {/* Context Meter */}
          <div className="px-3 py-2 border-b border-zinc-100 bg-white shrink-0">
            <TokenMeter
              currentTokens={harnessedRun.tokensIn || 1400}
              budgetCap={harnessedRun.budgetCap || 32768}
            />
          </div>

          {/* Source Code (Repaired) */}
          <div className="p-2.5 bg-zinc-50/40">
            <CodeEditor
              filename={currentFileName}
              code={rightCode}
              diffMode={isDiff}
            />
          </div>
        </div>
      </div>

      {/* Terminal Console (Collapsible) */}
      <div className="shrink-0 mt-1">
        <TerminalConsole
          events={harnessedRun.events || []}
          isStreaming={isStreaming}
          baselineRun={baselineRun}
          harnessedRun={harnessedRun}
        />
      </div>
    </div>
  );
};
