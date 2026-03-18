import { useCallback } from 'react';
import { useAppStore } from '../store/appStore';
import type { InputMessage } from '../types';

export function useAddressBar(sendMessage: (msg: InputMessage) => void) {
  const currentUrl = useAppStore((s) => s.currentUrl);

  const navigate = useCallback(
    (url: string) => {
      sendMessage({ type: 'navigate', url });
    },
    [sendMessage]
  );

  return { currentUrl, navigate };
}
