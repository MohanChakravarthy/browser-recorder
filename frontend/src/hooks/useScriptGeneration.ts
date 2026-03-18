import { useCallback } from 'react';
import { useAppStore } from '../store/appStore';
import { API_BASE } from '../lib/constants';
import type { GenerateResponse } from '../types';

export function useScriptGeneration() {
  const setRecordingState = useAppStore((s) => s.setRecordingState);
  const setScripts = useAppStore((s) => s.setScripts);
  const addTerminalLine = useAppStore((s) => s.addTerminalLine);
  const recordingState = useAppStore((s) => s.recordingState);
  const isGenerating = recordingState === 'generating';

  const generate = useCallback(async () => {
    setRecordingState('generating');
    try {
      const response = await fetch(`${API_BASE}/generate`, {
        method: 'POST',
      });
      if (!response.ok) {
        let errorMsg = `Generate failed: ${response.statusText}`;
        try {
          const errorData = await response.json();
          errorMsg = errorData.detail || errorMsg;
        } catch {
          // ignore parse error
        }
        addTerminalLine(`[stderr] ${errorMsg}`);
        setRecordingState('stopped');
        return;
      }
      const data: GenerateResponse = await response.json();
      setScripts(data.scripts);
      setRecordingState('ready');
      addTerminalLine(`[system] Generated scripts from ${data.action_count} actions`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      addTerminalLine(`[stderr] Script generation failed: ${msg}`);
      setRecordingState('stopped');
    }
  }, [setRecordingState, setScripts, addTerminalLine]);

  return { generate, isGenerating };
}
