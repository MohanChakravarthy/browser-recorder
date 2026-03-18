import { useCallback } from 'react';
import { useAppStore } from '../store/appStore';
import type { InputMessage } from '../types';

export function useRecorder(sendMessage: (msg: InputMessage) => void) {
  const recordingState = useAppStore((s) => s.recordingState);
  const setRecordingState = useAppStore((s) => s.setRecordingState);

  const startRecording = useCallback(() => {
    setRecordingState('recording');
    sendMessage({ type: 'control', command: 'start_recording' });
  }, [sendMessage, setRecordingState]);

  const stopRecording = useCallback(() => {
    setRecordingState('stopped');
    sendMessage({ type: 'control', command: 'stop_recording' });
  }, [sendMessage, setRecordingState]);

  return { startRecording, stopRecording, recordingState };
}
