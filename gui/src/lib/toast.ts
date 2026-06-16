import { toast } from 'sonner';

type ToastType = 'success' | 'error' | 'info' | 'warning' | 'loading';

interface ToastOptions {
  description?: string;
  duration?: number;
  id?: string;
}

const DEFAULT_DURATION = 4000;

function notify(type: ToastType, title: string, opts?: ToastOptions) {
  const id = opts?.id || title;
  const duration = opts?.duration ?? DEFAULT_DURATION;

  switch (type) {
    case 'success':
      return toast.success(title, { id, description: opts?.description, duration });
    case 'error':
      return toast.error(title, { id, description: opts?.description, duration: duration * 2 });
    case 'info':
      return toast(title, { id, description: opts?.description, duration });
    case 'warning':
      return toast(title, { id, description: opts?.description, duration, style: { borderColor: '#f59e0b' } });
    case 'loading':
      return toast.loading(title, { id, description: opts?.description });
    default:
      return toast(title, { id, description: opts?.description, duration });
  }
}

export const notifyToast = {
  success: (title: string, opts?: ToastOptions) => notify('success', title, opts),
  error: (title: string, opts?: ToastOptions) => notify('error', title, opts),
  info: (title: string, opts?: ToastOptions) => notify('info', title, opts),
  warning: (title: string, opts?: ToastOptions) => notify('warning', title, opts),
  loading: (title: string, opts?: ToastOptions) => notify('loading', title, opts),
  dismiss: (id?: string) => toast.dismiss(id),
  promise: toast.promise,
};
