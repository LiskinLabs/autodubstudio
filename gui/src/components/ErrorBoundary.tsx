import React from 'react';
import { reportErrorToGitHub } from '../lib/errorReporter';

interface Props {
  children: React.ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  reported: boolean;
}

export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null, reported: false };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('[ErrorBoundary] Caught:', error.message);
    // Auto-send to backend → GitHub. Zero user interaction.
    reportErrorToGitHub(error, info.componentStack || undefined).then((url) => {
      this.setState({ reported: true });
      if (url) console.log('[ErrorBoundary] Report URL:', url);
    });
  }

  handleReload = () => {
    this.setState({ hasError: false, error: null, reported: false });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            gap: 'var(--space-4)',
            padding: 'var(--space-8)',
            textAlign: 'center',
          }}
        >
          <div style={{ fontSize: '48px', marginBottom: 'var(--space-2)' }}>💥</div>
          <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: 600, color: 'var(--text-primary)' }}>
            Something went wrong
          </h2>
          <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', maxWidth: 400, lineHeight: 1.6 }}>
            {this.state.error?.message || 'An unexpected error occurred.'}
          </p>

          {this.state.reported && (
            <div className="callout callout-success" style={{ maxWidth: 380, textAlign: 'left' }}>
              <span>✅</span>
              <span style={{ fontSize: 'var(--text-xs)' }}>
                Error report sent automatically. Our team will investigate.
              </span>
            </div>
          )}

          {!this.state.reported && (
            <div className="callout callout-info" style={{ maxWidth: 380, textAlign: 'left' }}>
              <span>📤</span>
              <span style={{ fontSize: 'var(--text-xs)' }}>
                Sending error report automatically...
              </span>
            </div>
          )}

          <button className="btn btn-primary" onClick={this.handleReload} style={{ marginTop: 'var(--space-4)' }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="23 4 23 10 17 10" />
              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
            </svg>
            Reload Component
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
