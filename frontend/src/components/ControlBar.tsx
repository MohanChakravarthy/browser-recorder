import { useRecorder } from '../hooks/useRecorder';
import { useScriptGeneration } from '../hooks/useScriptGeneration';
import { useAppStore } from '../store/appStore';
import type { InputMessage } from '../types';

interface ControlBarProps {
  sendMessage: (msg: InputMessage) => void;
}

export default function ControlBar({ sendMessage }: ControlBarProps) {
  const { startRecording, stopRecording, recordingState } = useRecorder(sendMessage);
  const { generate, isGenerating } = useScriptGeneration();
  const actionCount = useAppStore((s) => s.actionCount);
  const reset = useAppStore((s) => s.reset);

  return (
    <div className="p-4 bg-gray-800 border-b border-gray-700">
      <div className="flex items-center gap-3">
        {recordingState === 'idle' && (
          <button
            onClick={startRecording}
            className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium transition-colors"
          >
            <span className="w-3 h-3 rounded-full bg-white" />
            Record
          </button>
        )}

        {recordingState === 'recording' && (
          <>
            <button
              onClick={stopRecording}
              className="flex items-center gap-2 px-4 py-2 bg-yellow-600 hover:bg-yellow-700 text-white rounded-lg font-medium transition-colors"
            >
              <span className="w-3 h-3 bg-white" />
              Stop
            </button>
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-900 text-red-200">
              {actionCount} action{actionCount !== 1 ? 's' : ''}
            </span>
            <span className="flex items-center gap-1.5 text-red-400 text-sm">
              <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
              Recording
            </span>
          </>
        )}

        {recordingState === 'stopped' && !isGenerating && (
          <button
            onClick={generate}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
            </svg>
            Generate Scripts
          </button>
        )}

        {(recordingState === 'generating' || isGenerating) && (
          <div className="flex items-center gap-2 px-4 py-2 bg-gray-700 text-gray-300 rounded-lg font-medium">
            <div className="animate-spin w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full" />
            Generating...
          </div>
        )}

        {recordingState === 'ready' && (
          <button
            onClick={reset}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            New Recording
          </button>
        )}

        {actionCount > 0 && recordingState !== 'recording' && recordingState !== 'idle' && (
          <span className="text-xs text-gray-500">
            {actionCount} action{actionCount !== 1 ? 's' : ''} recorded
          </span>
        )}
      </div>
    </div>
  );
}
