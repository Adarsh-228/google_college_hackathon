import React from "react";

interface TokenMeterProps {
  currentTokens: number;
  budgetCap: number;
}

export const TokenMeter: React.FC<TokenMeterProps> = ({
  currentTokens,
  budgetCap,
}) => {
  const percentage = Math.min(100, Math.round((currentTokens / budgetCap) * 100));
  const isOverflow = currentTokens >= budgetCap;

  return (
    <div className="w-full flex items-center gap-3 text-xs font-mono">
      {/* Progress Bar */}
      <div className="flex-1 h-1.5 bg-zinc-200 rounded-full overflow-hidden relative">
        <div
          className={`h-full transition-all duration-300 rounded-full ${
            isOverflow ? "bg-rose-500" : percentage > 70 ? "bg-amber-500" : "bg-emerald-600"
          }`}
          style={{ width: `${percentage}%` }}
        />
      </div>

      {/* Numerical metric */}
      <span className="text-[11px] text-zinc-600 shrink-0">
        <strong className={isOverflow ? "text-rose-600 font-bold" : "text-zinc-800"}>
          {currentTokens.toLocaleString()}
        </strong>{" "}
        / {budgetCap.toLocaleString()}{" "}
        <span className={isOverflow ? "text-rose-600 font-semibold" : "text-zinc-500"}>
          ({percentage}%)
        </span>
      </span>
    </div>
  );
};
