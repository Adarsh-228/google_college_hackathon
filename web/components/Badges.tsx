import React from "react";

interface BadgeProps {
  type: string;
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({ type, className = "" }) => {
  const t = type.toUpperCase();

  if (t.includes("M1_ELISION") || t.includes("ELISION")) {
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-zinc-200 text-zinc-900 border border-zinc-400/80 ${className}`}>
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-600" />
        M1 ELISION (0-Cost)
      </span>
    );
  }

  if (t.includes("M3_SUMMARY") || t.includes("SUMMARY")) {
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-zinc-200 text-zinc-900 border border-zinc-400/80 ${className}`}>
        <span className="w-1.5 h-1.5 rounded-full bg-indigo-600" />
        M3 SUMMARY (Compacted)
      </span>
    );
  }

  if (t.includes("LINT")) {
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-zinc-200 text-zinc-800 border border-zinc-300 ${className}`}>
        <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
        LINT GATE PASSED
      </span>
    );
  }

  if (t.includes("RBW") || t.includes("READ_BEFORE_WRITE")) {
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-zinc-200 text-zinc-800 border border-zinc-300 ${className}`}>
        <span className="w-1.5 h-1.5 rounded-full bg-zinc-600" />
        RBW VERIFIED
      </span>
    );
  }

  if (t.includes("STREAK_WARNING")) {
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-zinc-200 text-zinc-900 border border-amber-400 ${className}`}>
        <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
        STREAK WARNING (5 calls)
      </span>
    );
  }

  if (t.includes("CIRCUIT_BREAKER") || t.includes("STUCK")) {
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-zinc-200 text-zinc-900 border border-rose-400 ${className}`}>
        <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />
        CIRCUIT BREAKER HALT
      </span>
    );
  }

  if (t.includes("CONTEXT_OVERFLOW") || t.includes("OVERFLOW")) {
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-semibold bg-rose-100 text-rose-900 border border-rose-300 ${className}`}>
        <span className="w-1.5 h-1.5 rounded-full bg-rose-600 animate-pulse" />
        CONTEXT OVERFLOW (T0 Fail)
      </span>
    );
  }

  if (t.includes("RESOLVED")) {
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-semibold bg-emerald-100 text-emerald-900 border border-emerald-300 ${className}`}>
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-600" />
        RESOLVED (Passed)
      </span>
    );
  }

  if (t.includes("RUNNING")) {
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-zinc-200 text-zinc-800 border border-zinc-300 ${className}`}>
        <span className="w-1.5 h-1.5 rounded-full bg-zinc-600 animate-ping" />
        RUNNING
      </span>
    );
  }

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono font-medium bg-zinc-200 text-zinc-800 border border-zinc-300 ${className}`}>
      {type}
    </span>
  );
};
