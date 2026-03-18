import { useCallback, useRef } from 'react';
import Editor, { type Monaco } from '@monaco-editor/react';
import { useAppStore } from '../store/appStore';
import { useScriptExecution } from '../hooks/useScriptExecution';
import {
  ROBOT_LANGUAGE_ID,
  robotLanguageConfig,
  robotTokensProvider,
} from '../lib/robotLanguage';

export default function ScriptEditor() {
  const scripts = useAppStore((s) => s.scripts);
  const activeTab = useAppStore((s) => s.activeTab);
  const recordingState = useAppStore((s) => s.recordingState);
  const { execute, isExecuting } = useScriptExecution();
  const robotRegistered = useRef(false);

  const scriptContent = scripts ? scripts[activeTab] : '';

  const language = activeTab === 'playwright_python' ? 'python' : ROBOT_LANGUAGE_ID;

  const handleEditorMount = useCallback((_editor: unknown, monaco: Monaco) => {
    if (robotRegistered.current) return;
    robotRegistered.current = true;

    monaco.languages.register({ id: ROBOT_LANGUAGE_ID });
    monaco.languages.setLanguageConfiguration(ROBOT_LANGUAGE_ID, robotLanguageConfig);
    monaco.languages.setMonarchTokensProvider(ROBOT_LANGUAGE_ID, robotTokensProvider);

    // Custom theme tokens for Robot Framework
    monaco.editor.defineTheme('robot-dark', {
      base: 'vs-dark',
      inherit: true,
      rules: [
        { token: 'keyword.section', foreground: 'C586C0', fontStyle: 'bold' },
        { token: 'keyword', foreground: 'C586C0' },
        { token: 'keyword.tag', foreground: '569CD6', fontStyle: 'bold' },
        { token: 'support.function', foreground: 'DCDCAA' },
        { token: 'variable', foreground: '9CDCFE' },
        { token: 'string', foreground: 'CE9178' },
        { token: 'string.link', foreground: '3794FF', fontStyle: 'underline' },
        { token: 'comment', foreground: '6A9955' },
        { token: 'number', foreground: 'B5CEA8' },
        { token: 'constant', foreground: '569CD6' },
        { token: 'type', foreground: '4EC9B0' },
        { token: 'attribute.name', foreground: '9CDCFE' },
        { token: 'entity.name', foreground: '4FC1FF', fontStyle: 'bold' },
      ],
      colors: {},
    });
  }, []);

  const handleCopy = useCallback(async () => {
    if (scriptContent) {
      await navigator.clipboard.writeText(scriptContent);
    }
  }, [scriptContent]);

  const handleRun = useCallback(() => {
    if (scriptContent && !isExecuting) {
      execute(activeTab, scriptContent);
    }
  }, [scriptContent, isExecuting, activeTab, execute]);

  if (recordingState !== 'ready' || !scripts) return null;

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <div className="flex items-center justify-between px-3 py-2 bg-gray-800 border-b border-gray-700">
        <span className="text-sm text-gray-400">Generated Script</span>
        <div className="flex items-center gap-2">
          <button
            onClick={handleCopy}
            className="px-3 py-1 text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 rounded transition-colors"
            title="Copy to clipboard"
          >
            Copy
          </button>
          <button
            onClick={handleRun}
            disabled={isExecuting}
            className={`px-3 py-1 text-xs rounded transition-colors ${
              isExecuting
                ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
                : 'bg-green-700 hover:bg-green-600 text-white'
            }`}
            title="Run script"
          >
            {isExecuting ? 'Running...' : 'Run'}
          </button>
        </div>
      </div>
      <div className="flex-1 min-h-0 monaco-container">
        <Editor
          height="100%"
          language={language}
          value={scriptContent}
          theme={language === ROBOT_LANGUAGE_ID ? 'robot-dark' : 'vs-dark'}
          onMount={handleEditorMount}
          options={{
            readOnly: true,
            minimap: { enabled: false },
            fontSize: 13,
            lineNumbers: 'on',
            scrollBeyondLastLine: false,
            wordWrap: 'on',
            automaticLayout: true,
            padding: { top: 8 },
          }}
        />
      </div>
    </div>
  );
}
