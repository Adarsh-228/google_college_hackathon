import React from "react";

interface BadgeProps {
  type: string;
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({ type, className = "" }) => {
  const t = type.toUpperCase();

  if (t.includes("M1_ELISION") || t.includes("ELISION")) {
    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium bg-emerald-100 text-emerald-800 border border-emerald-300 ${className}`}>
        ⚡ M1 ELISION (0 Cost)
      </span>
    );
  }

  if (t.includes("M3_SUMMARY") || t.includes("SUMMARY")) {
    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium bg-indigo-100 text-indigo-800 border border-indigo-300 ${className}`}>
        📝 M3 SUMMARY (7 Headings)
      </span>
    );
  }

  if (t.includes("LINT")) {
    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium bg-amber-100 text-amber-800 border border-amber-300 ${className}`}>
        🔍 LINT DETECTED (Zero Turn)
      </span>
    );
  }

  if (t.includes("RBW") || t.includes("READ_BEFORE_WRITE")) {
    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium bg-rose-100 text-rose-800 border border-rose-300 ${className}`}>
        🛡️ RBW BLOCKED
      </span>
    );
  }

  if (t.includes("STREAK_WARNING")) {
    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium bg-amber-100 text-amber-900 border border-amber-400 ${className}`}>
        ⚠️ STREAK WARNING (5 calls)
      </span>
    );
  }

  if (t.includes("CIRCUIT_BREAKER") || t.includes("STUCK")) {
    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium bg-red-100 text-red-900 border border-red-400 ${className}`}>
        🛑 CIRCUIT BREAKER HALT (8 calls)
      </span>
    );
  }

  if (t.includes("CONTEXT_OVERFLOW") || t.includes("OVERFLOW")) {
    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium bg-rose-200 text-rose-900 border border-rose-400 font-bold ${className}`}>
        💥 CONTEXT OVERFLOW (T0 Fail)
      </span>
    );
  }

  if (t.includes("RESOLVED")) {
    return (
      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium bg-emerald-200 text-emerald-900 border border-emerald-400 font-bold ${className}`}>
        ✅ RESOLVED
      </span>
    );
  }

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium bg-zinc-100 text-zinc-800 border border-zinc-300 ${className}`}>
      {type}
    </span>
  );
};
