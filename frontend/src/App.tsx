import { useRef, useCallback } from 'react';
import BrowserCanvas from './components/BrowserCanvas';
import AddressBar from './components/AddressBar';
import ControlBar from './components/ControlBar';
import ScriptTabs from './components/ScriptTabs';
import ScriptEditor from './components/ScriptEditor';
import TerminalPanel from './components/TerminalPanel';
import StatusIndicator from './components/StatusIndicator';
import type { InputMessage } from './types';

export default function App() {
  const sendMessageRef = useRef<((msg: InputMessage) => void) | null>(null);

  const sendMessage = useCallback((msg: InputMessage) => {
    sendMessageRef.current?.(msg);
  }, []);

  return (
    <div className="flex flex-col h-screen bg-gray-900 text-gray-100">
      {/* Top: Address Bar */}
      <div className="flex items-center">
        <div className="flex-1">
          <AddressBar sendMessage={sendMessage} />
        </div>
        <StatusIndicator />
      </div>

      {/* Middle: Browser + Side Panel */}
      <div className="flex flex-1 min-h-0">
        {/* Left: Browser Canvas */}
        <BrowserCanvas sendMessageRef={sendMessageRef} />

        {/* Right: Controls + Script Panel */}
        <div className="w-[500px] flex flex-col border-l border-gray-700 bg-gray-850">
          <ControlBar sendMessage={sendMessage} />
          <ScriptTabs />
          <ScriptEditor />
          <TerminalPanel />
        </div>
      </div>
    </div>
  );
}
