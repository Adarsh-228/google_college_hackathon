import React, { useState } from "react";
import { TaskMeta } from "../lib/mockData";
import { createCustomTask } from "../lib/api";

interface CreateTaskModalProps {
  isOpen: boolean;
  onClose: () => void;
  onTaskCreated: (task: TaskMeta) => void;
}

export const CreateTaskModal: React.FC<CreateTaskModalProps> = ({
  isOpen,
  onClose,
  onTaskCreated,
}) => {
  const [taskId, setTaskId] = useState<string>("task_06_cache_leak");
  const [title, setTitle] = useState<string>("Task 6: Unbounded Cache Memory Leak");
  const [category, setCategory] = useState<string>("Resource Governance");
  const [prompt, setPrompt] = useState<string>(
    "Fix cache.py to evict the oldest item when cache size exceeds max_size (default 3) so that test_cache.py passes with pytest."
  );
  const [evalCommand, setEvalCommand] = useState<string>("pytest test_cache.py");

  const [sourceFilename, setSourceFilename] = useState<string>("cache.py");
  const [sourceCode, setSourceCode] = useState<string>(`class LRUCache:
    def __init__(self, max_size: int = 3):
        self.max_size = max_size
        self.items = {}

    def put(self, key, val):
        # BUG: unbounded growth, never evicts old items!
        self.items[key] = val

    def get(self, key):
        return self.items.get(key)

    def size(self):
        return len(self.items)
`);

  const [fixedCode, setFixedCode] = useState<string>(`class LRUCache:
    def __init__(self, max_size: int = 3):
        self.max_size = max_size
        self.items = {}

    def put(self, key, val):
        if len(self.items) >= self.max_size and key not in self.items:
            oldest = next(iter(self.items))
            del self.items[oldest]
        self.items[key] = val

    def get(self, key):
        return self.items.get(key)

    def size(self):
        return len(self.items)
`);

  const [testFilename, setTestFilename] = useState<string>("test_cache.py");
  const [testCode, setTestCode] = useState<string>(`from cache import LRUCache

def test_cache_eviction():
    c = LRUCache(max_size=3)
    c.put("a", 1)
    c.put("b", 2)
    c.put("c", 3)
    c.put("d", 4)
    assert c.size() == 3
    assert c.get("a") is None
    assert c.get("d") == 4
`);

  const [activeTab, setActiveTab] = useState<"meta" | "source" | "test" | "fixed">("meta");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  if (!isOpen) return null;

  const handlePreFill = () => {
    setTaskId("task_06_cache_leak");
    setTitle("Task 6: Unbounded Cache Memory Leak");
    setCategory("Resource Governance");
    setPrompt(
      "Fix cache.py to evict the oldest item when cache size exceeds max_size (default 3) so that test_cache.py passes with pytest."
    );
    setSourceFilename("cache.py");
    setTestFilename("test_cache.py");
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);

    const safeId = taskId.trim().toLowerCase().replace(/[^a-z0-9_\-]/g, "_") || "custom_task_01";

    const newTaskPayload = {
      id: safeId,
      title: title.trim() || safeId,
      category: category.trim() || "Custom Benchmark",
      description: prompt.trim(),
      prompt: prompt.trim(),
      expected_behavior: "Passes pytest evaluation with zero regression.",
      eval_command: evalCommand.trim() || `pytest ${testFilename}`,
      source_filename: sourceFilename.trim() || "app.py",
      source_code: sourceCode,
      fixed_code: fixedCode,
      test_filename: testFilename.trim() || "test_app.py",
      test_code: testCode,
      diff: `--- a/${sourceFilename}\n+++ b/${sourceFilename}\n@@ -7,2 +7,5 @@\n-        # BUG: unbounded growth\n-        self.items[key] = val\n+        if len(self.items) >= self.max_size and key not in self.items:\n+            del self.items[next(iter(self.items))]\n+        self.items[key] = val`,
    };

    // Save to backend testbeds/ directory
    try {
      await createCustomTask(newTaskPayload);
    } catch {
      // Local UI fallback
    }

    const newTaskMeta: TaskMeta = {
      id: safeId,
      title: title.trim() || safeId,
      category: category.trim() || "Custom Benchmark",
      description: prompt.trim(),
      prompt: prompt.trim(),
      expected_behavior: "Passes pytest evaluation with zero regression.",
      eval_command: evalCommand.trim() || `pytest ${testFilename}`,
      files: [
        {
          name: sourceFilename.trim() || "app.py",
          language: "python",
          content: sourceCode,
          fixedContent: fixedCode,
        },
        {
          name: testFilename.trim() || "test_app.py",
          language: "python",
          content: testCode,
        },
      ],
      diff: newTaskPayload.diff,
    };

    onTaskCreated(newTaskMeta);
    setIsSubmitting(false);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-900/40 backdrop-blur-xs p-4 animate-in fade-in duration-100">
      <div className="bg-white w-full max-w-2xl rounded-xl border border-zinc-300 shadow-2xl overflow-hidden font-mono text-xs flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-4 py-2.5 bg-zinc-100 border-b border-zinc-200 flex items-center justify-between select-none">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-zinc-400" />
            <span className="font-bold text-zinc-800 text-xs">
              CREATE BENCHMARK TESTBED
            </span>
            <span className="text-[10px] text-zinc-500 bg-zinc-200 px-1.5 py-0.2 rounded">
              testbeds/
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handlePreFill}
              className="text-[10px] text-zinc-600 hover:text-zinc-900 bg-zinc-200 hover:bg-zinc-300 px-2 py-0.5 rounded cursor-pointer transition-colors"
            >
              ⚡ Sample LRU Cache
            </button>
            <button
              onClick={onClose}
              className="text-zinc-400 hover:text-zinc-700 text-sm font-bold px-1.5"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center gap-1 px-4 py-1.5 bg-zinc-100/60 border-b border-zinc-200 text-[11px]">
          <button
            type="button"
            onClick={() => setActiveTab("meta")}
            className={`px-2.5 py-1 rounded transition-colors cursor-pointer ${
              activeTab === "meta"
                ? "bg-white text-zinc-900 font-bold border border-zinc-300 shadow-2xs"
                : "text-zinc-600 hover:bg-zinc-200"
            }`}
          >
            📋 Task Details
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("source")}
            className={`px-2.5 py-1 rounded transition-colors cursor-pointer ${
              activeTab === "source"
                ? "bg-white text-zinc-900 font-bold border border-zinc-300 shadow-2xs"
                : "text-zinc-600 hover:bg-zinc-200"
            }`}
          >
            🐍 Buggy Code ({sourceFilename})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("test")}
            className={`px-2.5 py-1 rounded transition-colors cursor-pointer ${
              activeTab === "test"
                ? "bg-white text-zinc-900 font-bold border border-zinc-300 shadow-2xs"
                : "text-zinc-600 hover:bg-zinc-200"
            }`}
          >
            🧪 Test Code ({testFilename})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("fixed")}
            className={`px-2.5 py-1 rounded transition-colors cursor-pointer ${
              activeTab === "fixed"
                ? "bg-white text-zinc-900 font-bold border border-zinc-300 shadow-2xs"
                : "text-zinc-600 hover:bg-zinc-200"
            }`}
          >
            ✨ Reference Fix
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-4 space-y-3">
          {activeTab === "meta" && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[10px] uppercase font-bold text-zinc-600 mb-1">
                    Task Directory ID
                  </label>
                  <input
                    type="text"
                    value={taskId}
                    onChange={(e) => setTaskId(e.target.value)}
                    placeholder="task_06_cache_leak"
                    required
                    className="w-full p-2 bg-zinc-50 border border-zinc-300 rounded text-zinc-900 font-mono text-xs focus:outline-hidden"
                  />
                  <p className="text-[10px] text-zinc-400 mt-0.5">
                    Creates folder: <code className="bg-zinc-100 px-1">testbeds/{taskId}/</code>
                  </p>
                </div>

                <div>
                  <label className="block text-[10px] uppercase font-bold text-zinc-600 mb-1">
                    Category
                  </label>
                  <input
                    type="text"
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    placeholder="Performance / Algorithmic"
                    className="w-full p-2 bg-zinc-50 border border-zinc-300 rounded text-zinc-900 font-mono text-xs focus:outline-hidden"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[10px] uppercase font-bold text-zinc-600 mb-1">
                  Task Display Title
                </label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Task 6: Unbounded Cache Memory Leak"
                  required
                  className="w-full p-2 bg-zinc-50 border border-zinc-300 rounded text-zinc-900 font-mono text-xs focus:outline-hidden"
                />
              </div>

              <div>
                <label className="block text-[10px] uppercase font-bold text-zinc-600 mb-1">
                  Prompt Given to Agent
                </label>
                <textarea
                  rows={3}
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="Describe the bug and instruction for the agent to fix..."
                  required
                  className="w-full p-2 bg-zinc-50 border border-zinc-300 rounded text-zinc-900 font-sans text-xs focus:outline-hidden leading-relaxed"
                />
              </div>

              <div>
                <label className="block text-[10px] uppercase font-bold text-zinc-600 mb-1">
                  Pytest Eval Command
                </label>
                <input
                  type="text"
                  value={evalCommand}
                  onChange={(e) => setEvalCommand(e.target.value)}
                  placeholder="pytest test_cache.py"
                  className="w-full p-2 bg-zinc-50 border border-zinc-300 rounded text-zinc-900 font-mono text-xs focus:outline-hidden"
                />
              </div>
            </div>
          )}

          {activeTab === "source" && (
            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <label className="text-[10px] uppercase font-bold text-zinc-600">
                  Buggy File Name
                </label>
                <input
                  type="text"
                  value={sourceFilename}
                  onChange={(e) => setSourceFilename(e.target.value)}
                  className="w-40 p-1 bg-zinc-50 border border-zinc-300 rounded text-zinc-900 text-xs"
                />
              </div>
              <textarea
                rows={12}
                value={sourceCode}
                onChange={(e) => setSourceCode(e.target.value)}
                required
                className="w-full p-2.5 bg-zinc-950 text-zinc-100 border border-zinc-800 rounded font-mono text-xs leading-5 focus:outline-hidden"
              />
            </div>
          )}

          {activeTab === "test" && (
            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <label className="text-[10px] uppercase font-bold text-zinc-600">
                  Test File Name
                </label>
                <input
                  type="text"
                  value={testFilename}
                  onChange={(e) => setTestFilename(e.target.value)}
                  className="w-40 p-1 bg-zinc-50 border border-zinc-300 rounded text-zinc-900 text-xs"
                />
              </div>
              <textarea
                rows={12}
                value={testCode}
                onChange={(e) => setTestCode(e.target.value)}
                required
                className="w-full p-2.5 bg-zinc-950 text-zinc-100 border border-zinc-800 rounded font-mono text-xs leading-5 focus:outline-hidden"
              />
            </div>
          )}

          {activeTab === "fixed" && (
            <div className="space-y-2">
              <label className="text-[10px] uppercase font-bold text-zinc-600">
                Patched / Repaired Code (Reference for Harness View)
              </label>
              <textarea
                rows={12}
                value={fixedCode}
                onChange={(e) => setFixedCode(e.target.value)}
                className="w-full p-2.5 bg-zinc-950 text-emerald-300 border border-zinc-800 rounded font-mono text-xs leading-5 focus:outline-hidden"
              />
            </div>
          )}

          {/* Footer Submit */}
          <div className="pt-3 border-t border-zinc-200 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1.5 rounded bg-zinc-100 hover:bg-zinc-200 text-zinc-700 text-xs font-sans font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-4 py-1.5 rounded bg-zinc-900 hover:bg-zinc-800 text-white text-xs font-sans font-medium transition-colors shadow-2xs disabled:opacity-50"
            >
              {isSubmitting ? "Saving to testbeds/..." : "Save & Open in Benchmark →"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
