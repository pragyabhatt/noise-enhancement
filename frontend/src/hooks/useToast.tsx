// src/hooks/useToast.tsx
import { useToast as internalUseToast } from '../components/Toast';

export const useToast = () => {
  const { ToastContainer, trigger } = internalUseToast();
  return { ToastContainer, trigger };
};
