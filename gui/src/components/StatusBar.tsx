import { useState, useEffect } from "react";
import { useSettings } from "../store";
import { useOllama } from "../hooks/useOllama";
import UpdateChecker from "./UpdateChecker";
import ModelDownloader from "./ModelDownloader";
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
    <div className="h-8 bg-base-200 border-t border-base-content/10 flex items-center px-3 text-[11px] font-medium text-base-content/60 shrink-0 select-none z-50">
      {/* GPU Status */}
      <div className="flex items-center gap-1.5 h-full px-2 hover:bg-base-content/5 transition-colors cursor-default">
        <span
          className={`w-2 h-2 rounded-full ${status.gpu === "gpu" ? "bg-success" : "bg-warning"}`}
        />
        <span>{status.gpu === "gpu" ? t('status.gpu') : t('status.cpu')}</span>
      </div>

      <div className="w-px h-3 bg-base-content/10 mx-1" />

      {/* VRAM */}
      <div className="flex items-center gap-1.5 h-full px-2 hover:bg-base-content/5 transition-colors cursor-default">
        <span>
          {t('status.vram')}
        </span>
      </div>

      <div className="w-px h-3 bg-base-content/10 mx-1" />

      {/* Ollama */}
      <div className="flex items-center gap-1.5 h-full px-2 hover:bg-base-content/5 transition-colors cursor-default">
        <span
          className={`w-2 h-2 rounded-full ${isConnected ? "bg-success" : "bg-error"}`}
        />
        <span>
          {isConnected
            ? t('status.ollama')
            : t('status.ollama_off')}
        </span>
      </div>

      <div className="w-px h-3 bg-base-content/10 mx-1" />

      {/* Update Checker — shows progress/status when active */}
      <UpdateChecker />

      {/* Model Downloader — shows download progress */}
      <ModelDownloader />

      {/* Version — pushed to right */}
      <div className="flex items-center gap-1.5 h-full px-2 hover:bg-base-content/5 transition-colors cursor-default ml-auto opacity-50">
        <span>v{pkg.version}</span>
      </div>
    </div>
  );
};

export default StatusBar;
