import React from "react";
import { Button } from "@fluentui/react-components";
import {
  WarningRegular as AlertTriangle,
  CheckmarkRegular as Check,
  SendRegular as Send,
  ArrowSyncRegular as RefreshCw,
} from "@fluentui/react-icons";
import { reportErrorToGitHub } from "../lib/errorReporter";
import { settingsStore } from "../store";

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
    console.error("[ErrorBoundary] Caught:", error.message);
    reportErrorToGitHub(error, info.componentStack || undefined).then((url) => {
      this.setState({ reported: true });
      if (url) console.log("[ErrorBoundary] Report URL:", url);
    });
  }

  handleReload = () => {
    this.setState({ hasError: false, error: null, reported: false });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center h-full gap-5 p-8 text-center">
          <div style={{
            padding: 20, borderRadius: 16,
            background: "var(--colorPaletteRedBackground1)",
            border: "1px solid var(--colorPaletteRedBorder1)",
          }}>
            <AlertTriangle style={{ fontSize: 48, color: "var(--colorPaletteRedForeground1)" }} />
          </div>
          <h2 className="text-xl font-semibold">{settingsStore.t("error.title")}</h2>
          <p className="text-sm max-w-md leading-relaxed" style={{ color: "var(--colorNeutralForeground2)" }}>
            {this.state.error?.message || settingsStore.t("error.default_message")}
          </p>

          {this.state.reported ? (
            <div className="flex gap-3 p-4 rounded-xl shadow-sm max-w-md text-left" style={{
              background: "var(--colorPaletteGreenBackground2)",
              border: "1px solid var(--colorPaletteGreenBorder1)",
            }}>
              <Check style={{ fontSize: 18, color: "var(--colorPaletteGreenForeground1)" }} />
              <span className="text-sm">{settingsStore.t("error.reported")}</span>
            </div>
          ) : (
            <div className="flex gap-3 p-4 rounded-xl shadow-sm max-w-md text-left" style={{
              background: "var(--colorPaletteBlueBackground2)",
              border: "1px solid var(--colorPaletteBlueBorder1)",
            }}>
              <Send style={{ fontSize: 18, color: "var(--colorPaletteBlueForeground1)" }} />
              <span className="text-sm">{settingsStore.t("error.sending")}</span>
            </div>
          )}

          <Button appearance="primary" icon={<RefreshCw style={{ fontSize: 16 }} />} onClick={this.handleReload}>
            {settingsStore.t("error.reload")}
          </Button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
