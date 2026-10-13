import React, { useState } from "react";
import { Badge } from "./Badges";

interface TerminalConsoleProps {
  events: any[];
  isStreaming?: boolean;
  baselineRun?: any;
  harnessedRun?: any;
}

export const TerminalConsole: React.FC<TerminalConsoleProps> = ({
  events,
  isStreaming = false,
  baselineRun,
  harnessedRun,
}) => {
  const [activeTab, setActiveTab] = useState<"terminal" | "agent" | "guard">("terminal");
  const [isOpen, setIsOpen] = useState<boolean>(true);

  return (
    <div className="flex flex-col rounded-lg border border-zinc-700 bg-zinc-900 text-zinc-200 font-mono text-xs shadow-lg overflow-hidden shrink-0">
      {/* Terminal Header Bar */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-zinc-800/90 border-b border-zinc-700 select-none">
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => {
              setActiveTab("terminal");
              setIsOpen(true);
            }}
            className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors flex items-center gap-1.5 ${
              activeTab === "terminal" && isOpen
                ? "bg-zinc-900 text-zinc-100 border border-zinc-700"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <span>▶</span>
            <span>TERMINAL (pytest)</span>
          </button>

          <button
            onClick={() => {
              setActiveTab("agent");
              setIsOpen(true);
            }}
            className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors flex items-center gap-1.5 ${
              activeTab === "agent" && isOpen
                ? "bg-zinc-900 text-zinc-100 border border-zinc-700"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <span>🤖</span>
            <span>GEMINI STREAM</span>
            {isStreaming && (
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            )}
          </button>

          <button
            onClick={() => {
              setActiveTab("guard");
              setIsOpen(true);
            }}
            className={`px-2 py-0.5 rounded text-[11px] font-medium transition-colors flex items-center gap-1.5 ${
              activeTab === "guard" && isOpen
                ? "bg-zinc-900 text-zinc-100 border border-zinc-700"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <span>🛡️</span>
            <span>AGENTGUARD</span>
          </button>
        </div>

        <div className="flex items-center gap-3 text-[10px] text-zinc-400">
          <span className="hidden sm:inline">bash 5.2</span>
          <button
            onClick={() => setIsOpen(!isOpen)}
            className="px-2 py-0.5 rounded bg-zinc-700/60 hover:bg-zinc-700 text-zinc-300 text-[10px] font-sans font-medium transition-colors cursor-pointer"
          >
            {isOpen ? "▲ Collapse" : "▼ Expand Console"}
          </button>
        </div>
      </div>

      {/* Terminal Output Area (Collapsible) */}
      {isOpen && (
        <div className="p-3 overflow-y-auto max-h-[220px] min-h-[140px] space-y-2 bg-zinc-950/90 leading-relaxed">
          {activeTab === "terminal" && (
            <div className="space-y-2">
              <div className="text-zinc-400 text-[11px]">
                <span className="text-emerald-400 font-semibold">gemini@cloud-sandbox</span>:
                <span className="text-sky-400">~/workspace</span>$ pytest -v
              </div>

              {events.length === 0 ? (
                <div className="text-zinc-500 italic py-1">
                  Ready. Click &apos;Replay Trace&apos; to run step-by-step verification.
                </div>
              ) : (
                events.map((evt, idx) => {
                  const { type, data } = evt;
                  if (type === "TOOL_CALL" && data.tool === "bash") {
                    return (
                      <div key={idx} className="space-y-1">
                        <div className="text-zinc-400 text-[11px]">
                          <span className="text-emerald-400 font-semibold">gemini@cloud-sandbox</span>:
                          <span className="text-sky-400">~/workspace</span>$ {data.args?.command || "pytest"}
                        </div>
                      </div>
                    );
                  }
                  if (type === "TOOL_RESULT" && data.tool === "bash") {
                    return (
                      <pre
                        key={idx}
                        className={`p-2 rounded text-[11px] whitespace-pre-wrap ${
                          data.is_error
                            ? "bg-rose-950/40 border border-rose-900/60 text-rose-300"
                            : "bg-zinc-900 border border-zinc-800 text-zinc-300"
                        }`}
                      >
                        {data.output}
                      </pre>
                    );
                  }
                  if (type === "COMPACTION") {
                    return (
                      <div
                        key={idx}
                        className="p-1.5 px-2 bg-emerald-950/40 border border-emerald-800/60 rounded text-[11px] text-emerald-300 flex items-center justify-between"
                      >
                        <span>⚡ [M1_ELISION] Compacted: -{data.tokens_saved?.toLocaleString() || "29,850"} tokens (0 cost)</span>
                        <span className="text-emerald-400 font-bold">Remaining: {data.tokens_after?.toLocaleString()}</span>
                      </div>
                    );
                  }
                  if (type === "RUN_FINISH") {
                    return (
                      <div
                        key={idx}
                        className="p-2 bg-emerald-950/60 border border-emerald-700 rounded text-emerald-200 text-[11px] font-semibold"
                      >
                        ✓ {data.final_message}
                      </div>
                    );
                  }
                  if (type === "ERROR") {
                    return (
                      <div
                        key={idx}
                        className="p-2 bg-rose-950/60 border border-rose-700 rounded text-rose-200 text-[11px] font-semibold"
                      >
                        ✗ [HALT]: {data.message}
                      </div>
                    );
                  }
                  return null;
                })
              )}

              {isStreaming && (
                <div className="flex items-center gap-2 text-zinc-400 text-[11px] pt-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  <span>Streaming output...</span>
                </div>
              )}
            </div>
          )}

          {activeTab === "agent" && (
            <div className="space-y-1.5">
              <div className="text-[11px] text-zinc-400">
                Google Gemini 2.5 Flash • Context: <strong className="text-emerald-400">T4 Active</strong>
              </div>

              {events.map((evt, idx) => {
                const { type, data, turn_idx } = evt;
                if (type === "PLAN_UPDATE") {
                  return (
                    <div key={idx} className="p-2 bg-zinc-900 border border-zinc-700 rounded text-[11px] space-y-1">
                      <div className="text-zinc-400 font-semibold">Turn {turn_idx}: Hierarchical Plan Injected</div>
                      <ul className="space-y-0.5">
                        {data.current_plan?.map((step: any, sIdx: number) => (
                          <li key={sIdx} className="flex items-center gap-2">
                            <span className={step.status === "completed" ? "text-emerald-400" : step.status === "in_progress" ? "text-amber-400" : "text-zinc-500"}>
                              {step.status === "completed" ? "✓" : step.status === "in_progress" ? "▶" : "·"}
                            </span>
                            <span className={step.status === "completed" ? "line-through text-zinc-500" : "text-zinc-300"}>
                              {step.content}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  );
                }
                if (type === "TOOL_CALL") {
                  return (
                    <div key={idx} className="p-2 bg-zinc-900 border border-zinc-800 rounded text-[11px]">
                      <div className="text-sky-400 font-semibold">
                        Tool Call [T{turn_idx}]: {data.tool}
                      </div>
                      <pre className="text-zinc-400 overflow-x-auto text-[10px] mt-1 bg-zinc-950 p-1 rounded">
                        {JSON.stringify(data.args, null, 2)}
                      </pre>
                    </div>
                  );
                }
                return null;
              })}
            </div>
          )}

          {activeTab === "guard" && (
            <div className="space-y-1.5">
              <div className="text-[11px] text-zinc-400">
                AgentGuard Substrate Protection (Zero-Turn Linter, Circuit Breaker, Read-Before-Write)
              </div>

              {events.filter((e) => e.type === "GUARD_EVENT" || e.type === "COMPACTION").map((evt, idx) => (
                <div key={idx} className="p-2 bg-zinc-900 border border-zinc-700 rounded text-[11px]">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge type={evt.data?.badge || evt.type} />
                    <span className="text-zinc-300">{evt.data?.output || evt.data?.message}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
