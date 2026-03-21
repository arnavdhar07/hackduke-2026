'use client';

import { useEffect } from 'react';

interface ToastProps {
  message: string;
  onDismiss: () => void;
}

export default function Toast({ message, onDismiss }: ToastProps) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, 4000);
    return () => clearTimeout(timer);
  }, [onDismiss]);

  return (
    <div className="bg-red-600 text-white px-4 py-3 rounded-lg shadow-lg max-w-sm flex items-start gap-3">
      <span className="mt-0.5 text-lg">⚠</span>
      <div className="flex-1">
        <p className="text-sm font-semibold mb-0.5">Critical Alert</p>
        <p className="text-sm opacity-90">{message}</p>
      </div>
      <button onClick={onDismiss} className="text-white/70 hover:text-white text-lg leading-none">
        ×
      </button>
    </div>
  );
}
