import { useCallback } from 'react';
import { useAppStore } from '../store/appStore';
import { API_BASE } from '../lib/constants';
import type { ScriptTab } from '../types';

export function useScriptExecution() {
  const addTerminalLine = useAppStore((s) => s.addTerminalLine);
  const setIsExecuting = useAppStore((s) => s.setIsExecuting);
  const isExecuting = useAppStore((s) => s.isExecuting);

  const execute = useCallback(
    async (scriptType: ScriptTab, scriptContent: string) => {
      setIsExecuting(true);
      addTerminalLine(`[system] Executing ${scriptType} script...`);

      try {
        const response = await fetch(`${API_BASE}/execute`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            script_type: scriptType,
            script_content: scriptContent,
          }),
        });

        if (!response.ok) {
          addTerminalLine(`[stderr] Execute failed: ${response.statusText}`);
          setIsExecuting(false);
          return;
        }

        const reader = response.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6);
              try {
                const parsed = JSON.parse(data);
                if (parsed.type === 'stdout') {
                  addTerminalLine(`[stdout] ${parsed.data}`);
                } else if (parsed.type === 'stderr') {
                  addTerminalLine(`[stderr] ${parsed.data}`);
                } else if (parsed.type === 'exit') {
                  addTerminalLine(`[exit] Process exited with code ${parsed.data}`);
                }
              } catch {
                addTerminalLine(`[stdout] ${data}`);
              }
            }
          }
        }

        // Process remaining buffer
        if (buffer.startsWith('data: ')) {
          const data = buffer.slice(6);
          try {
            const parsed = JSON.parse(data);
            if (parsed.type === 'exit') {
              addTerminalLine(`[exit] Process exited with code ${parsed.data}`);
            } else {
              addTerminalLine(`[stdout] ${parsed.data || data}`);
            }
          } catch {
            addTerminalLine(`[stdout] ${data}`);
          }
        }
      } catch (err) {
        addTerminalLine(`[stderr] Execution error: ${err}`);
      } finally {
        setIsExecuting(false);
      }
    },
    [addTerminalLine, setIsExecuting]
  );

  return { execute, isExecuting };
}
