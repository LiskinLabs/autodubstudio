import { notifyToast } from './toast';

interface ErrorReport {
  timestamp: string;
  version: string;
  platform: string;
  language: string;
  theme: string;
  error_message: string;
  error_stack: string;
  error_component_stack?: string;
  logs: string[];
  route: string;
}

const ERROR_LOG_KEY = 'autodub_error_log';
const MAX_LOG_ENTRIES = 200;
const BACKEND_URL = 'http://127.0.0.1:8000';

// Token cache — fetched once from backend /api/token
let _authToken: string | null = null;
async function getAuthToken(): Promise<string | null> {
  if (_authToken) return _authToken;
  try {
    const resp = await fetch(`${BACKEND_URL}/api/token`);
    if (resp.ok) {
      const data = await resp.json();
      _authToken = data.token;
      return _authToken;
    }
  } catch { /* backend offline */ }
  return null;
}

// ─── Runtime log buffer ───
const logBuffer: string[] = [];

export function captureLog(message: string) {
  const entry = `[${new Date().toISOString()}] ${message}`;
  logBuffer.push(entry);
  if (logBuffer.length > MAX_LOG_ENTRIES) logBuffer.shift();

  try {
    const stored: string[] = JSON.parse(localStorage.getItem(ERROR_LOG_KEY) || '[]');
    stored.push(entry);
    if (stored.length > MAX_LOG_ENTRIES) stored.splice(0, stored.length - MAX_LOG_ENTRIES);
    localStorage.setItem(ERROR_LOG_KEY, JSON.stringify(stored));
  } catch { /* ignore */ }
}

export function getRecentLogs(): string[] {
  try {
    const stored = JSON.parse(localStorage.getItem(ERROR_LOG_KEY) || '[]');
    return [...stored.slice(-50), ...logBuffer.slice(-50)];
  } catch {
    return logBuffer.slice(-50);
  }
}

export function clearLogs() {
  logBuffer.length = 0;
  localStorage.removeItem(ERROR_LOG_KEY);
}

// ─── Build error report ───
function buildReport(error: Error, componentStack?: string): ErrorReport {
  return {
    timestamp: new Date().toISOString(),
    version: '1.0.0',
    platform: navigator.platform || 'unknown',
    language: navigator.language,
    theme: document.documentElement.getAttribute('data-theme') || 'dark',
    error_message: error.message || 'Unknown error',
    error_stack: error.stack?.slice(0, 3000) || '',
    error_component_stack: componentStack?.slice(0, 2000) || '',
    logs: getRecentLogs(),
    route: window.location.hash || '/',
  };
}

// ─── Send error to backend (which creates GitHub issue) ───
export async function sendErrorReport(error: Error, componentStack?: string): Promise<string | null> {
  const report = buildReport(error, componentStack);

  try {
    const token = await getAuthToken();
    const resp = await fetch(`${BACKEND_URL}/api/report-error`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(report),
    });

    if (resp.ok) {
      const data = await resp.json();
      console.log('[ErrorReporter] Sent successfully:', data.url);
      return data.url || null;
    } else {
      console.error('[ErrorReporter] Backend returned:', resp.status);
      return null;
    }
  } catch (err) {
    console.error('[ErrorReporter] Failed to reach backend:', err);
    return null;
  }
}

// ─── Public API: auto-send + show toast ───
export async function reportErrorToGitHub(error: Error, componentStack?: string): Promise<string | null> {
  notifyToast.loading('📤 Sending error report...', {
    id: 'error-report',
    description: 'Submitting to GitHub automatically',
  });

  const url = await sendErrorReport(error, componentStack);

  if (url) {
    notifyToast.success('✅ Error reported!', {
      id: 'error-report',
      description: 'Thanks! We\'ll look into it.',
      duration: 4000,
    });
    captureLog('[REPORT] Error sent to GitHub successfully');
  } else {
    notifyToast.error('⚠️ Could not send report', {
      id: 'error-report',
      description: 'Backend may be offline. Error saved locally.',
      duration: 5000,
    });
    captureLog('[REPORT] Failed to send — backend unreachable');
  }

  return url;
}

// ─── Global error handler ───
export function initGlobalErrorHandler() {
  window.addEventListener('unhandledrejection', (event) => {
    const error = event.reason instanceof Error ? event.reason : new Error(String(event.reason));
    captureLog(`[UNHANDLED] ${error.message}`);
    reportErrorToGitHub(error);
  });

  window.addEventListener('error', (event) => {
    const error = event.error instanceof Error ? event.error : new Error(event.message);
    captureLog(`[GLOBAL] ${error.message} @ ${event.filename}:${event.lineno}`);
    reportErrorToGitHub(error);
  });

  const originalError = console.error.bind(console);
  console.error = (...args: any[]) => {
    originalError(...args);
    const msg = args.map(a => (a instanceof Error ? a.message : String(a))).join(' ');
    captureLog(`[ERROR] ${msg.slice(0, 500)}`);
  };

  const originalWarn = console.warn.bind(console);
  console.warn = (...args: any[]) => {
    originalWarn(...args);
    const msg = args.map(a => String(a)).join(' ');
    captureLog(`[WARN] ${msg.slice(0, 300)}`);
  };

  captureLog('[SYSTEM] Error reporter initialized');
}
