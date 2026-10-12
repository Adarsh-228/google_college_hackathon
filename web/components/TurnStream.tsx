import React from "react";
import { Badge } from "./Badges";

interface TurnEvent {
  turn_idx: number;
  type: string;
  data: any;
  timestamp?: number;
}

interface TurnStreamProps {
  events: TurnEvent[];
  isStreaming?: boolean;
}

export const TurnStream: React.FC<TurnStreamProps> = ({ events, isStreaming = false }) => {
  if (!events || events.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-8 text-zinc-400 font-mono text-xs">
        <div className="w-6 h-6 border-2 border-zinc-300 border-t-zinc-600 rounded-full animate-spin mb-2" />
        Waiting for initial agent turn...
      </div>
    );
  }

  return (
    <div className="space-y-3 font-mono text-xs">
      {events.map((evt, idx) => {
        const { turn_idx, type, data } = evt;

        if (type === "PLAN_UPDATE") {
          return (
            <div key={idx} className="p-2.5 bg-zinc-50 border border-zinc-200 rounded-md">
              <div className="text-[11px] font-semibold text-zinc-600 mb-1 flex items-center gap-1.5">
                <span>📋 Plan Injected (Turn {turn_idx})</span>
              </div>
              <ul className="space-y-1 text-zinc-700">
                {data.current_plan?.map((step: any, sIdx: number) => (
                  <li key={sIdx} className="flex items-center gap-2">
                    <span className={`w-3.5 h-3.5 flex items-center justify-center rounded text-[9px] ${
                      step.status === "completed" ? "bg-emerald-600 text-white" :
                      step.status === "in_progress" ? "bg-amber-500 text-white animate-pulse" : "bg-zinc-200 text-zinc-600"
                    }`}>
                      {step.status === "completed" ? "✓" : step.status === "in_progress" ? "▶" : "·"}
                    </span>
                    <span className={step.status === "completed" ? "line-through text-zinc-400" : ""}>
                      {step.content}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          );
        }

        if (type === "COMPACTION") {
          return (
            <div key={idx} className="p-2 bg-emerald-50 border border-emerald-200 rounded-md flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Badge type={data.badge || "M1_ELISION"} />
                <span className="text-emerald-900 font-semibold text-[11px]">
                  Staged Compaction Applied
                </span>
              </div>
              <span className="text-[10px] text-emerald-700 font-mono">
                Tokens after: {data.tokens_after?.toLocaleString()}
              </span>
            </div>
          );
        }

        if (type === "GUARD_EVENT") {
          return (
            <div key={idx} className="p-2 bg-amber-50 border border-amber-200 rounded-md">
              <div className="flex items-center gap-2 mb-1">
                <Badge type={data.badge} />
                <span className="text-amber-900 font-semibold text-[11px]">
                  AgentGuard Substrate Gate Triggered
                </span>
              </div>
              {data.output && (
                <pre className="text-[11px] text-zinc-700 overflow-x-auto whitespace-pre-wrap bg-white/70 p-1.5 rounded border border-amber-100">
                  {data.output}
                </pre>
              )}
            </div>
          );
        }

        if (type === "TOOL_CALL") {
          return (
            <div key={idx} className="p-2 bg-white border border-zinc-200 rounded-md shadow-sm">
              <div className="flex justify-between items-center mb-1">
                <span className="font-semibold text-zinc-900 flex items-center gap-1.5">
                  <span className="text-zinc-400">T{turn_idx}</span>
                  <span className="px-1.5 py-0.5 bg-zinc-100 border border-zinc-300 rounded text-zinc-800">
                    {data.tool}
                  </span>
                </span>
              </div>
              <pre className="text-[11px] text-zinc-600 bg-zinc-50 p-1.5 rounded overflow-x-auto">
                {JSON.stringify(data.args, null, 2)}
              </pre>
            </div>
          );
        }

        if (type === "TOOL_RESULT") {
          return (
            <div key={idx} className={`p-2 rounded-md border text-[11px] ${
              data.is_error ? "bg-rose-50 border-rose-200 text-rose-900" : "bg-zinc-50 border-zinc-200 text-zinc-800"
            }`}>
              <div className="font-semibold text-[10px] uppercase tracking-wider text-zinc-500 mb-0.5">
                Observation ({data.tool}) {data.is_error ? "— Error" : "— Ok"}
              </div>
              <pre className="overflow-x-auto whitespace-pre-wrap max-h-40 overflow-y-auto">
                {data.output}
              </pre>
            </div>
          );
        }

        if (type === "RUN_FINISH") {
          return (
            <div key={idx} className="p-3 bg-emerald-50 border border-emerald-300 rounded-lg text-emerald-950">
              <div className="flex items-center gap-2 mb-1">
                <Badge type="RESOLVED" />
                <span className="font-bold">Task Resolution Verified</span>
              </div>
              <p className="text-xs">{data.final_message}</p>
            </div>
          );
        }

        if (type === "ERROR") {
          return (
            <div key={idx} className="p-3 bg-rose-50 border border-rose-300 rounded-lg text-rose-950">
              <div className="flex items-center gap-2 mb-1">
                <Badge type={data.reason || "ERROR"} />
                <span className="font-bold">Run Halted</span>
              </div>
              <p className="text-xs">{data.message}</p>
            </div>
          );
        }

        return null;
      })}

      {isStreaming && (
        <div className="flex items-center gap-2 text-zinc-400 text-[11px] py-1 animate-pulse">
          <span className="w-1.5 h-1.5 rounded-full bg-zinc-500" />
          Agent reasoning in progress...
        </div>
      )}
    </div>
  );
};
