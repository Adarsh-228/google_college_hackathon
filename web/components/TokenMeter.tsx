import React from "react";

interface TokenMeterProps {
  currentTokens: number;
  budgetCap: number;
  label?: string;
}

export const TokenMeter: React.FC<TokenMeterProps> = ({
  currentTokens,
  budgetCap,
  label = "Context Window Usage",
}) => {
  const percentage = Math.min(100, Math.round((currentTokens / budgetCap) * 100));
  const isB1Reached = percentage >= 60;
  const isB2Reached = percentage >= 85;
  const isOverflow = currentTokens >= budgetCap;

  let barColor = "bg-zinc-700";
  if (isOverflow) {
    barColor = "bg-red-600";
  } else if (isB2Reached) {
    barColor = "bg-rose-500";
  } else if (isB1Reached) {
    barColor = "bg-amber-500";
  }

  return (
    <div className="w-full bg-white p-3 rounded-lg border border-zinc-200 shadow-sm text-xs">
      <div className="flex justify-between items-center mb-1.5 font-medium text-zinc-700">
        <span className="flex items-center gap-1.5 font-semibold text-zinc-900">
          <span className="w-2 h-2 rounded-full bg-zinc-800"></span>
          {label}
        </span>
        <span className="font-mono text-zinc-600">
          <strong className="text-zinc-900">{currentTokens.toLocaleString()}</strong> / {budgetCap.toLocaleString()} tokens ({percentage}%)
        </span>
      </div>

      {/* Progress Track */}
      <div className="relative w-full h-3 bg-zinc-100 rounded-full overflow-hidden border border-zinc-200">
        <div
          className={`h-full transition-all duration-500 rounded-full ${barColor}`}
          style={{ width: `${percentage}%` }}
        />
        
        {/* B1 (60%) Threshold Marker */}
        <div
          className="absolute top-0 bottom-0 w-0.5 bg-amber-400 z-10"
          style={{ left: "60%" }}
          title="B1 Soft Threshold: 60% (Triggers M1 Elision)"
        />

        {/* B2 (85%) Threshold Marker */}
        <div
          className="absolute top-0 bottom-0 w-0.5 bg-rose-400 z-10"
          style={{ left: "85%" }}
          title="B2 Hard Threshold: 85% (Triggers M3 Summarization)"
        />
      </div>

      {/* Threshold Labels */}
      <div className="flex justify-between text-[10px] text-zinc-400 mt-1 font-mono">
        <span>0%</span>
        <span className="text-amber-600 font-semibold">B1: 60% (M1 Elide)</span>
        <span className="text-rose-600 font-semibold">B2: 85% (M3 Summary)</span>
        <span>100% Cap</span>
      </div>
    </div>
  );
};
