import React from "react";
import { TokenMeter } from "./TokenMeter";
import { TurnStream } from "./TurnStream";
import { Badge } from "./Badges";

interface DualPaneProps {
  baselineRun: any;
  harnessedRun: any;
  isStreaming?: boolean;
}

export const DualPaneComparator: React.FC<DualPaneProps> = ({
  baselineRun,
  harnessedRun,
  isStreaming = false,
}) => {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {/* ---------------- Left Pane: Baseline Agent ---------------- */}
      <div className="bg-white rounded-xl border border-zinc-200 shadow-sm overflow-hidden flex flex-col">
        {/* Header */}
        <div className="p-3.5 bg-zinc-50 border-b border-zinc-200 flex justify-between items-center">
          <div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-rose-500" />
              <h3 className="font-semibold text-sm text-zinc-900">Baseline Agent</h3>
              <span className="text-[11px] px-2 py-0.5 rounded bg-zinc-200 text-zinc-700 font-mono">
                Tier 0 (Unmanaged) • No Guards
              </span>
            </div>
            <p className="text-[11px] text-zinc-500 mt-0.5">
              Budget Cap: {baselineRun.budgetCap?.toLocaleString() || "32,768"} tokens
            </p>
          </div>
          <div>
            <Badge type={baselineRun.status || "RUNNING"} />
          </div>
        </div>

        {/* Token Meter */}
        <div className="p-3 border-b border-zinc-100 bg-white">
          <TokenMeter
            currentTokens={baselineRun.tokensIn || 1400}
            budgetCap={baselineRun.budgetCap || 32768}
            label="Baseline Context Meter"
          />
        </div>

        {/* Turn Events Stream */}
        <div className="p-3.5 overflow-y-auto max-h-[560px] flex-1 bg-zinc-50/50">
          <TurnStream events={baselineRun.events || []} isStreaming={isStreaming && baselineRun.status === "RUNNING"} />
        </div>

        {/* Footer Metrics */}
        <div className="p-3 bg-zinc-100/70 border-t border-zinc-200 flex justify-between items-center text-xs font-mono text-zinc-600">
          <span>Cost: <strong>${baselineRun.costUsd?.toFixed(5) || "0.00000"}</strong></span>
          <span>Tokens In: <strong>{baselineRun.tokensIn?.toLocaleString() || "0"}</strong></span>
          <span className="text-zinc-500">Stop: {baselineRun.status || "N/A"}</span>
        </div>
      </div>

      {/* ---------------- Right Pane: Harness Kit Agent ---------------- */}
      <div className="bg-white rounded-xl border border-zinc-200 shadow-sm overflow-hidden flex flex-col">
        {/* Header */}
        <div className="p-3.5 bg-emerald-50/50 border-b border-zinc-200 flex justify-between items-center">
          <div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-600" />
              <h3 className="font-semibold text-sm text-zinc-900">Harness Kit Agent</h3>
              <span className="text-[11px] px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 font-mono font-medium">
                ContextT4 • AgentGuard Enabled
              </span>
            </div>
            <p className="text-[11px] text-zinc-500 mt-0.5">
              Staged Compaction (M1 Elide @ 60%, M3 Summary @ 85%)
            </p>
          </div>
          <div>
            <Badge type={harnessedRun.status || "RUNNING"} />
          </div>
        </div>

        {/* Token Meter */}
        <div className="p-3 border-b border-zinc-100 bg-white">
          <TokenMeter
            currentTokens={harnessedRun.tokensIn || 1400}
            budgetCap={harnessedRun.budgetCap || 32768}
            label="Harness Kit Context Meter"
          />
        </div>

        {/* Turn Events Stream */}
        <div className="p-3.5 overflow-y-auto max-h-[560px] flex-1 bg-zinc-50/50">
          <TurnStream events={harnessedRun.events || []} isStreaming={isStreaming && harnessedRun.status === "RUNNING"} />
        </div>

        {/* Footer Metrics */}
        <div className="p-3 bg-emerald-50/40 border-t border-zinc-200 flex justify-between items-center text-xs font-mono text-zinc-700">
          <span>Cost: <strong className="text-emerald-700">${harnessedRun.costUsd?.toFixed(5) || "0.00000"}</strong></span>
          <span>Tokens In: <strong className="text-emerald-700">{harnessedRun.tokensIn?.toLocaleString() || "0"}</strong></span>
          <span className="text-emerald-800 font-semibold">Resolved: {harnessedRun.status === "RESOLVED" ? "YES (Passed)" : "NO"}</span>
        </div>
      </div>
    </div>
  );
};
