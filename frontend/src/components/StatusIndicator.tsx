import { useAppStore } from '../store/appStore';

export default function StatusIndicator() {
  const connectionState = useAppStore((s) => s.connectionState);
  const recordingState = useAppStore((s) => s.recordingState);

  const getDotColor = () => {
    if (recordingState === 'recording') return 'bg-red-500 animate-pulse';
    switch (connectionState) {
      case 'connected':
        return 'bg-green-500';
      case 'connecting':
        return 'bg-yellow-500';
      case 'disconnected':
        return 'bg-red-500';
    }
  };

  const getLabel = () => {
    if (recordingState === 'recording') return 'Recording';
    switch (connectionState) {
      case 'connected':
        return 'Connected';
      case 'connecting':
        return 'Connecting';
      case 'disconnected':
        return 'Disconnected';
    }
  };

  return (
    <div className="flex items-center gap-2 px-3 py-1">
      <span className={`w-2.5 h-2.5 rounded-full ${getDotColor()}`} />
      <span className="text-xs text-gray-400">{getLabel()}</span>
    </div>
  );
}
