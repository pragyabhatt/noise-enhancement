import React, { useEffect, useState } from 'react';

interface ToastProps {
  message: string;
  type?: 'error' | 'info' | 'success';
  duration?: number; // ms
  onClose: () => void;
}

export const Toast: React.FC<ToastProps> = ({ message, type = 'info', duration = 4000, onClose }) => {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => setVisible(false), duration);
    return () => clearTimeout(timer);
  }, [duration]);

  useEffect(() => {
    if (!visible) {
      const timeout = setTimeout(onClose, 300);
      return () => clearTimeout(timeout);
    }
  }, [visible, onClose]);

  const bgColor = {
    error: 'bg-red-600',
    info: 'bg-gray-800',
    success: 'bg-green-600',
  }[type];

  return (
    <div className={`fixed top-4 right-4 max-w-xs w-full transition-opacity duration-300 ${visible ? 'opacity-100' : 'opacity-0'} ${bgColor} text-white p-3 rounded shadow-lg`}>
      {message}
    </div>
  );
};

// Global toast hook
export let addToastGlobal: ((msg: string, type?: string) => void) | null = null;

export const useToast = () => {
  const [toast, setToast] = useState<{ msg: string; type?: string } | null>(null);

  useEffect(() => {
    addToastGlobal = (msg: string, type: string = 'info') => setToast({ msg, type });
    return () => { addToastGlobal = null; };
  }, []);

  const ToastContainer = () =>
    toast ? (
      <Toast message={toast.msg} type={toast.type as any} onClose={() => setToast(null)} />
    ) : null;

  const trigger = (msg: string, type: string = 'info') => {
    if (addToastGlobal) addToastGlobal(msg, type);
    else setToast({ msg, type });
  };

  return { ToastContainer, trigger };
};
