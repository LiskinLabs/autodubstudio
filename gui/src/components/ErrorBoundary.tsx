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
        <div className="flex flex-col items-center justify-center h-full gap-4 p-8 text-center">
          <div className="text-5xl mb-2">💥</div>
          <h2 className="text-xl font-semibold text-base-content">
            Something went wrong
          </h2>
          <p className="text-sm text-base-content/70 max-w-[400px] leading-relaxed">
            {this.state.error?.message || 'An unexpected error occurred.'}
          </p>

          {this.state.reported && (
            <div className="alert alert-success shadow-sm max-w-[380px] text-left text-xs">
              <span>✅</span>
              <span>Error report sent automatically. Our team will investigate.</span>
            </div>
          )}

          {!this.state.reported && (
            <div className="alert alert-info shadow-sm max-w-[380px] text-left text-xs">
              <span>📤</span>
              <span>Sending error report automatically...</span>
            </div>
          )}

          <button className="btn btn-primary mt-4" onClick={this.handleReload}>
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
