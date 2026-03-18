import { useEffect, useRef, useCallback } from 'react';
import { useAppStore } from '../store/appStore';
import { WS_URL } from '../lib/constants';
import type { InputMessage, OutputMessage } from '../types';

export function useBrowserSocket(onFrame: (blob: Blob) => void) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onFrameRef = useRef(onFrame);
  onFrameRef.current = onFrame;

  const setConnectionState = useAppStore((s) => s.setConnectionState);
  const setRecordingState = useAppStore((s) => s.setRecordingState);
  const setCurrentUrl = useAppStore((s) => s.setCurrentUrl);
  const incrementActionCount = useAppStore((s) => s.incrementActionCount);

  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;

    setConnectionState('connecting');
    const ws = new WebSocket(WS_URL);
    ws.binaryType = 'blob';

    ws.onopen = () => {
      setConnectionState('connected');
      // Request current state from backend on connect/reconnect
      ws.send(JSON.stringify({ type: 'control', command: 'get_status' }));
      // Nudge the browser with a tiny mousemove so CDP emits a first frame
      // (screencast only sends frames when the page visually changes)
      setTimeout(() => {
        ws.send(JSON.stringify({ type: 'mouse', event: 'mousemove', x: 0, y: 0 }));
      }, 300);
    };

    ws.onmessage = (event: MessageEvent) => {
      if (event.data instanceof Blob) {
        onFrameRef.current(event.data);
      } else {
        try {
          const msg: OutputMessage = JSON.parse(event.data as string);
          switch (msg.type) {
            case 'nav_update':
              if (msg.url) setCurrentUrl(msg.url);
              break;
            case 'recording_state':
              if (msg.state) setRecordingState(msg.state);
              break;
            case 'action_recorded':
              incrementActionCount();
              break;
            case 'error':
              console.error('[WS Error]', msg.message);
              break;
          }
        } catch (e) {
          console.error('Failed to parse WS message:', e);
        }
      }
    };

    ws.onclose = () => {
      setConnectionState('disconnected');
      wsRef.current = null;
      reconnectTimerRef.current = setTimeout(() => {
        connect();
      }, 2000);
    };

    ws.onerror = () => {
      ws.close();
    };

    wsRef.current = ws;
  }, [setConnectionState, setRecordingState, setCurrentUrl, incrementActionCount]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
      }
    };
  }, [connect]);

  const sendMessage = useCallback((msg: InputMessage) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  const isConnected = useAppStore((s) => s.connectionState === 'connected');

  return { sendMessage, isConnected };
}
