import React from "react";

interface CodeEditorProps {
  filename: string;
  code: string;
  diffMode?: boolean;
}

export const CodeEditor: React.FC<CodeEditorProps> = ({
  filename,
  code,
  diffMode = false,
}) => {
  const lines = code.trim().split("\n");

  const getLineClass = (line: string) => {
    if (diffMode) {
      if (line.startsWith("+")) return "bg-emerald-500/10 text-emerald-800 font-medium";
      if (line.startsWith("-")) return "bg-rose-500/10 text-rose-800 font-medium";
      if (line.startsWith("@@")) return "bg-zinc-200 text-zinc-600 font-bold";
    }
    if (line.includes("BUG:")) {
      return "bg-rose-50 text-rose-900 font-semibold";
    }
    if (line.includes("FIXED:")) {
      return "bg-emerald-50 text-emerald-900 font-semibold";
    }
    return "hover:bg-zinc-50";
  };

  const renderSyntax = (line: string) => {
    if (diffMode) return <span>{line}</span>;

    if (line.trim().startsWith("#") || line.trim().startsWith('"""') || line.trim().startsWith("'''")) {
      return <span className="text-zinc-500 italic">{line}</span>;
    }

    const keywordRegex = /\b(def|class|return|import|from|if|else|elif|while|for|in|try|except|raise|pass|assert|lambda|True|False|None)\b/g;
    const parts = line.split(keywordRegex);

    return (
      <span>
        {parts.map((part, i) => {
          if (part.match(keywordRegex)) {
            return (
              <span key={i} className="text-zinc-900 font-bold">
                {part}
              </span>
            );
          }
          if (part.includes('"') || part.includes("'")) {
            return (
              <span key={i} className="text-zinc-700">
                {part}
              </span>
            );
          }
          return <span key={i}>{part}</span>;
        })}
      </span>
    );
  };

  return (
    <div className="flex flex-col h-full bg-white rounded-md border border-zinc-200 overflow-hidden font-mono text-xs">
      {/* Tab Header */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-zinc-100 border-b border-zinc-200 select-none shrink-0">
        <div className="flex items-center gap-1.5 text-zinc-700 font-medium text-[11px]">
          <span className="text-zinc-500">{filename.endsWith(".py") ? "🐍" : "±"}</span>
          <span>{filename}</span>
        </div>
        <span className="text-[10px] text-zinc-400">{lines.length} lines</span>
      </div>

      {/* Editor Body - generous height, scrollable, full code visible */}
      <div className="h-[340px] overflow-y-auto bg-white p-1">
        <div className="table w-full">
          {lines.map((line, idx) => (
            <div
              key={idx}
              className={`table-row leading-6 text-[12px] ${getLineClass(line)}`}
            >
              <div className="table-cell select-none text-right pr-3 pl-2.5 py-0.5 text-zinc-400 font-mono w-9 border-r border-zinc-200/60 bg-zinc-50 text-[11px]">
                {idx + 1}
              </div>
              <div className="table-cell pl-3 pr-3 py-0.5 whitespace-pre font-mono text-zinc-800">
                {renderSyntax(line)}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
