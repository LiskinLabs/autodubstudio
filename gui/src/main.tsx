import React from "react";
import ReactDOM from "react-dom/client";
import { FluentProvider } from "@fluentui/react-components";
import App from "./App";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { initGlobalErrorHandler } from "./lib/errorReporter";
import { Toaster } from "sonner";
import { useSettings } from "./store";
import { getFluentTheme } from "./theme";
import "./index.css";

initGlobalErrorHandler();

const Root = () => {
  const { theme } = useSettings();
  const fluentTheme = getFluentTheme(theme);

  return (
    <FluentProvider theme={fluentTheme} style={{ height: "100%" }}>
      <ErrorBoundary>
        <App />
        <Toaster
          position="bottom-right"
          toastOptions={{
            style: {
              background: "var(--colorNeutralBackground1)",
              color: "var(--colorNeutralForeground1)",
              border: "1px solid var(--colorNeutralStroke2)",
              borderRadius: "12px",
              fontFamily: "'Inter', 'Segoe UI', sans-serif",
              fontSize: "14px",
            },
          }}
          theme="system"
          richColors
          closeButton
        />
      </ErrorBoundary>
    </FluentProvider>
  );
};

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
);
