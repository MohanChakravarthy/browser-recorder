export type RecordingState = 'idle' | 'recording' | 'stopped' | 'generating' | 'ready';
export type ConnectionState = 'connecting' | 'connected' | 'disconnected';
export type ScriptTab = 'playwright_python' | 'robot_framework' | 'robot_selenium';

export interface ElementContext {
  tag: string;
  text?: string;
  attributes: Record<string, string>;
  xpath?: string;
  css_selector?: string;
}

export interface RawAction {
  type: string;
  x?: number;
  y?: number;
  key?: string;
  text?: string;
  url?: string;
  timestamp: number;
  element?: ElementContext;
}

export interface ProcessedAction {
  type: string;
  selector?: string;
  value?: string;
  url?: string;
  description: string;
}

export interface InputMessage {
  type: 'mouse' | 'keyboard' | 'scroll' | 'navigate' | 'control';
  event?: string;
  x?: number;
  y?: number;
  button?: string;
  key?: string;
  code?: string;
  shift?: boolean;
  ctrl?: boolean;
  alt?: boolean;
  meta?: boolean;
  deltaX?: number;
  deltaY?: number;
  url?: string;
  command?: string;
}

export interface OutputMessage {
  type: 'nav_update' | 'recording_state' | 'action_recorded' | 'error';
  url?: string;
  state?: RecordingState;
  action?: ProcessedAction;
  message?: string;
}

export interface ScriptOutput {
  playwright_python: string;
  robot_framework: string;
  robot_selenium: string;
}

export interface GenerateResponse {
  scripts: ScriptOutput;
  action_count: number;
}

export interface ExecuteRequest {
  script_type: ScriptTab;
  script_content: string;
}

export interface AppState {
  connectionState: ConnectionState;
  recordingState: RecordingState;
  currentUrl: string;
  scripts: ScriptOutput | null;
  activeTab: ScriptTab;
  actionCount: number;
  terminalOutput: string[];
  isExecuting: boolean;

  setConnectionState: (state: ConnectionState) => void;
  setRecordingState: (state: RecordingState) => void;
  setCurrentUrl: (url: string) => void;
  setScripts: (scripts: ScriptOutput | null) => void;
  setActiveTab: (tab: ScriptTab) => void;
  addTerminalLine: (line: string) => void;
  clearTerminal: () => void;
  setIsExecuting: (executing: boolean) => void;
  reset: () => void;
  incrementActionCount: () => void;
}
