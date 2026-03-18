import { create } from 'zustand';
import type { AppState } from '../types';

export const useAppStore = create<AppState>((set) => ({
  connectionState: 'disconnected',
  recordingState: 'idle',
  currentUrl: '',
  scripts: null,
  activeTab: 'playwright_python',
  actionCount: 0,
  terminalOutput: [],
  isExecuting: false,

  setConnectionState: (connectionState) => set({ connectionState }),
  setRecordingState: (recordingState) => set({ recordingState }),
  setCurrentUrl: (currentUrl) => set({ currentUrl }),
  setScripts: (scripts) => set({ scripts }),
  setActiveTab: (activeTab) => set({ activeTab }),
  addTerminalLine: (line) =>
    set((state) => ({ terminalOutput: [...state.terminalOutput, line] })),
  clearTerminal: () => set({ terminalOutput: [] }),
  setIsExecuting: (isExecuting) => set({ isExecuting }),
  reset: () =>
    set({
      recordingState: 'idle',
      scripts: null,
      actionCount: 0,
      terminalOutput: [],
      isExecuting: false,
    }),
  incrementActionCount: () =>
    set((state) => ({ actionCount: state.actionCount + 1 })),
}));
