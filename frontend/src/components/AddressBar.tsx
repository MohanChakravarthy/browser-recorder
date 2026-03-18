import { useState, useEffect, useCallback } from 'react';
import { useAddressBar } from '../hooks/useAddressBar';
import type { InputMessage } from '../types';

interface AddressBarProps {
  sendMessage: (msg: InputMessage) => void;
}

export default function AddressBar({ sendMessage }: AddressBarProps) {
  const { currentUrl, navigate } = useAddressBar(sendMessage);
  const [inputValue, setInputValue] = useState(currentUrl);
  const [isNavigating, setIsNavigating] = useState(false);

  useEffect(() => {
    setInputValue(currentUrl);
    setIsNavigating(false);
  }, [currentUrl]);

  const handleNavigate = useCallback(() => {
    let url = inputValue.trim();
    if (!url) return;
    if (!/^https?:\/\//i.test(url)) {
      url = 'https://' + url;
    }
    setIsNavigating(true);
    navigate(url);
  }, [inputValue, navigate]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        handleNavigate();
      }
    },
    [handleNavigate]
  );

  return (
    <div className="flex items-center gap-2 px-3 py-2 bg-gray-800 border-b border-gray-700">
      <button
        onClick={handleNavigate}
        disabled={isNavigating}
        className="flex items-center justify-center px-3 h-8 rounded bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white text-xs font-medium transition-colors"
        title="Go to URL"
      >
        {isNavigating ? (
          <div className="animate-spin w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full" />
        ) : (
          'Go'
        )}
      </button>
      <input
        type="text"
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        onKeyDown={handleKeyDown}
        className="flex-1 px-3 py-1.5 bg-gray-700 border border-gray-600 rounded-full text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
        placeholder="Enter URL and press Enter or click Go..."
      />
    </div>
  );
}
