import { useState, useEffect } from "react";
import { useSettings } from "../store";
import { useOllama } from "../hooks/useOllama";
import UpdateChecker from "./UpdateChecker";
import pkg from "../../package.json";

type GpuStatus = "gpu" | "cpu";

interface SystemStatus {
  gpu: GpuStatus;
  vramUsed: number;
  vramTotal: number;
}

const StatusBar: React.FC = () => {
  const { t } = useSettings();
  const { isConnected, checkConnection } = useOllama();

  useEffect(() => {
    checkConnection();
    const interval = setInterval(checkConnection, 5000);
    return () => clearInterval(interval);
  }, [checkConnection]);

  const [status] = useState<SystemStatus>({
    gpu: "gpu",
    vramUsed: 3.2,
    vramTotal: 4.0,
  });

  return (
    <div className="statusbar">
      {/* GPU Status */}
      <div className="status-item">
        <span
          className={`status-dot ${status.gpu === "gpu" ? "green" : "yellow"}`}
        />
        <span>{status.gpu === "gpu" ? t('status.gpu') : t('status.cpu')}</span>
      </div>

      <div className="status-separator" />

      {/* VRAM */}
      <div className="status-item">
        <span>
          {t('status.vram')}
        </span>
      </div>

      <div className="status-separator" />

      {/* Ollama */}
      <div className="status-item">
        <span
          className={`status-dot ${isConnected ? "green" : "red"}`}
        />
        <span>
          {isConnected
            ? t('status.ollama')
            : t('status.ollama_off')}
        </span>
      </div>

      <div className="status-separator" />

      {/* Update Checker — shows progress/status when active */}
      <UpdateChecker />

      {/* Version — pushed to right */}
      <div className="status-item" style={{ marginLeft: "auto" }}>
        <span>v{pkg.version}</span>
      </div>
    </div>
  );
};

export default StatusBar;
