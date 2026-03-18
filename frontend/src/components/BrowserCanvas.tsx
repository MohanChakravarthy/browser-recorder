import { useRef, useCallback, useEffect } from 'react';
import { useBrowserSocket } from '../hooks/useBrowserSocket';
import { useAppStore } from '../store/appStore';
import { VIEWPORT_WIDTH, VIEWPORT_HEIGHT } from '../lib/constants';
import type { InputMessage } from '../types';

interface BrowserCanvasProps {
  sendMessageRef: React.MutableRefObject<((msg: InputMessage) => void) | null>;
}

export default function BrowserCanvas({ sendMessageRef }: BrowserCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const connectionState = useAppStore((s) => s.connectionState);

  const onFrame = useCallback((blob: Blob) => {
    const url = URL.createObjectURL(blob);
    const img = new Image();
    img.onload = () => {
      const ctx = canvasRef.current?.getContext('2d');
      if (ctx) {
        ctx.drawImage(img, 0, 0);
      }
      URL.revokeObjectURL(url);
    };
    img.src = url;
  }, []);

  const { sendMessage, isConnected } = useBrowserSocket(onFrame);

  useEffect(() => {
    sendMessageRef.current = sendMessage;
  }, [sendMessage, sendMessageRef]);

  const getScaledCoords = useCallback(
    (e: React.MouseEvent) => {
      const canvas = canvasRef.current;
      if (!canvas) return { x: 0, y: 0 };
      const rect = canvas.getBoundingClientRect();
      const scaleX = VIEWPORT_WIDTH / rect.width;
      const scaleY = VIEWPORT_HEIGHT / rect.height;
      return {
        x: Math.round((e.clientX - rect.left) * scaleX),
        y: Math.round((e.clientY - rect.top) * scaleY),
      };
    },
    []
  );

  const getButtonName = (button: number): string => {
    switch (button) {
      case 0: return 'left';
      case 1: return 'middle';
      case 2: return 'right';
      default: return 'left';
    }
  };

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      // Explicitly focus the canvas so it receives keyboard events
      canvasRef.current?.focus();
      const { x, y } = getScaledCoords(e);
      sendMessage({
        type: 'mouse',
        event: 'mousedown',
        x,
        y,
        button: getButtonName(e.button),
      });
    },
    [sendMessage, getScaledCoords]
  );

  const handleMouseUp = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      const { x, y } = getScaledCoords(e);
      sendMessage({
        type: 'mouse',
        event: 'mouseup',
        x,
        y,
        button: getButtonName(e.button),
      });
    },
    [sendMessage, getScaledCoords]
  );

  const lastMoveRef = useRef(0);
  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      // Throttle mousemove to every 32ms (~30fps) to avoid flooding
      const now = Date.now();
      if (now - lastMoveRef.current < 32) return;
      lastMoveRef.current = now;
      const { x, y } = getScaledCoords(e);
      sendMessage({
        type: 'mouse',
        event: 'mousemove',
        x,
        y,
      });
    },
    [sendMessage, getScaledCoords]
  );

  const handleContextMenu = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
    },
    []
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      e.preventDefault();
      sendMessage({
        type: 'keyboard',
        event: 'keydown',
        key: e.key,
        code: e.code,
        shift: e.shiftKey,
        ctrl: e.ctrlKey,
        alt: e.altKey,
        meta: e.metaKey,
      });
    },
    [sendMessage]
  );

  const handleKeyUp = useCallback(
    (e: React.KeyboardEvent) => {
      e.preventDefault();
      sendMessage({
        type: 'keyboard',
        event: 'keyup',
        key: e.key,
        code: e.code,
        shift: e.shiftKey,
        ctrl: e.ctrlKey,
        alt: e.altKey,
        meta: e.metaKey,
      });
    },
    [sendMessage]
  );

  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
      e.preventDefault();
      const { x, y } = getScaledCoords(e);
      sendMessage({
        type: 'scroll',
        x,
        y,
        deltaX: Math.round(e.deltaX),
        deltaY: Math.round(e.deltaY),
      });
    },
    [sendMessage, getScaledCoords]
  );

  // Prevent default wheel at DOM level to avoid passive listener issues
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const handler = (e: WheelEvent) => e.preventDefault();
    canvas.addEventListener('wheel', handler, { passive: false });
    return () => canvas.removeEventListener('wheel', handler);
  }, []);

  return (
    <div
      ref={containerRef}
      className="relative flex-1 flex items-center justify-center bg-black overflow-hidden"
    >
      <canvas
        ref={canvasRef}
        width={VIEWPORT_WIDTH}
        height={VIEWPORT_HEIGHT}
        tabIndex={0}
        className="max-w-full max-h-full cursor-default outline-none"
        style={{ objectFit: 'contain' }}
        onMouseDown={handleMouseDown}
        onMouseUp={handleMouseUp}
        onMouseMove={handleMouseMove}
        onContextMenu={handleContextMenu}
        onKeyDown={handleKeyDown}
        onKeyUp={handleKeyUp}
        onWheel={handleWheel}
      />
      {!isConnected && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/70">
          <div className="text-center">
            <div className="animate-spin w-8 h-8 border-2 border-blue-400 border-t-transparent rounded-full mx-auto mb-3" />
            <p className="text-gray-300 text-lg">
              {connectionState === 'connecting' ? 'Connecting...' : 'Disconnected'}
            </p>
            {connectionState === 'disconnected' && (
              <p className="text-gray-500 text-sm mt-1">Reconnecting in 2s...</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
