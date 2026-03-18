import { useRef, useEffect } from 'react';
import { useAppStore } from '../store/appStore';

export default function TerminalPanel() {
  const terminalOutput = useAppStore((s) => s.terminalOutput);
  const clearTerminal = useAppStore((s) => s.clearTerminal);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [terminalOutput]);

  if (terminalOutput.length === 0) return null;

  const getLineColor = (line: string) => {
    if (line.startsWith('[stderr]')) return 'text-red-400';
    if (line.startsWith('[exit]')) return 'text-yellow-400';
    if (line.startsWith('[system]')) return 'text-blue-400';
    return 'text-green-400';
  };

  return (
    <div className="flex flex-col border-t border-gray-700 bg-gray-900 max-h-48">
      <div className="flex items-center justify-between px-3 py-1.5 bg-gray-800 border-b border-gray-700">
        <span className="text-xs text-gray-400 font-medium">Terminal Output</span>
        <button
          onClick={clearTerminal}
          className="px-2 py-0.5 text-xs text-gray-500 hover:text-gray-300 transition-colors"
        >
          Clear
        </button>
      </div>
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-2 font-mono text-xs leading-5"
      >
        {terminalOutput.map((line, i) => (
          <div key={i} className={getLineColor(line)}>
            {line}
          </div>
        ))}
      </div>
    </div>
  );
}
