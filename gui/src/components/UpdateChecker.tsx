import { useEffect, useState, useCallback } from "react";
import { check } from "@tauri-apps/plugin-updater";
import { relaunch } from "@tauri-apps/plugin-process";
import {
  ArrowDownloadRegular as Download,
  ArrowSyncRegular as RefreshCw,
  RocketRegular as Rocket,
} from "@fluentui/react-icons";
import { notifyToast } from "../lib/toast";
import { useSettings } from "../store";

type UpdateStatus = "idle" | "checking" | "available" | "downloading" | "ready" | "error";

interface UpdateInfo {
  version: string;
  body?: string;
}

export default function UpdateChecker() {
  const { t } = useSettings();
  const [status, setStatus] = useState<UpdateStatus>("idle");
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null);
  const [downloadProgress, setDownloadProgress] = useState(0);

  const checkForUpdates = useCallback(async () => {
    if (status !== "idle") return;
    setStatus("checking");

    try {
      const update = await check();
      if (update) {
        setUpdateInfo({ version: update.version, body: update.body });
        setStatus("available");

        notifyToast.info(t("update.available_title").replace("{version}", update.version), {
          description: t("update.available_desc"),
          duration: 5000,
          id: "update-available",
        });

        setTimeout(() => downloadUpdate(update), 2000);
      } else {
        setStatus("idle");
      }
    } catch (err) {
      console.error("[Updater] Check failed:", err);
      setStatus("error");
    }
  }, [status, t]);

  const downloadUpdate = useCallback(async (update: any) => {
    setStatus("downloading");
    let contentLength = 0;
    let downloaded = 0;

    try {
      await update.download((event: any) => {
        switch (event.event) {
          case "Started":
            contentLength = event.data.contentLength || 0;
            notifyToast.loading(
              t("update.downloading").replace("{size}", String(Math.round(contentLength / 1024 / 1024))),
              { id: "update-download", description: t("update.notify_ready") }
            );
            break;
          case "Progress":
            if (contentLength > 0) {
              downloaded += event.data.chunkLength || 0;
              setDownloadProgress(Math.round((downloaded / contentLength) * 100));
            }
            break;
          case "Finished":
            setStatus("ready");
            notifyToast.success(t("update.downloaded"), {
              description: t("update.restart_prompt"),
              duration: 0,
              id: "update-ready",
            });
            break;
        }
      });
    } catch (err) {
      console.error("[Updater] Download failed:", err);
      setStatus("error");
      notifyToast.error(t("update.failed"), {
        description: t("update.retry_later"),
        id: "update-error",
      });
    }
  }, [t]);

  const installUpdate = useCallback(async () => {
    try {
      notifyToast.loading(t("update.installing"), {
        description: t("update.restart_auto"),
        id: "update-install",
      });
      await relaunch();
    } catch (err) {
      console.error("[Updater] Install failed:", err);
      notifyToast.error(t("update.install_failed"), {
        description: t("update.restart_manual"),
      });
    }
  }, [t]);

  useEffect(() => {
    const timer = setTimeout(checkForUpdates, 3000);
    return () => clearTimeout(timer);
  }, []);

  if (status === "available" || status === "downloading" || status === "ready") {
    const label = status === "ready"
      ? t("update.ready_label").replace("{version}", updateInfo?.version || "")
      : status === "downloading"
        ? `${downloadProgress}%`
        : t("update.available_label");

    const icons = { ready: <Rocket style={{ fontSize: 13 }} />, downloading: <Download style={{ fontSize: 13 }} />, available: <RefreshCw style={{ fontSize: 13 }} /> };
    const statusIcon = (status === "ready" ? icons.ready : status === "downloading" ? icons.downloading : icons.available) as React.ReactNode;

    const tooltip = status === "ready" ? t("update.click_to_install") : status === "downloading" ? t("update.downloading_label") : t("update.available_label");

    return (
      <div className="flex items-center gap-1.5 cursor-pointer font-medium"
        style={{ height: "100%", padding: "0 8px", color: "var(--colorBrandForeground1)", fontSize: 11 }}
        onClick={() => { if (status === "ready") installUpdate(); }}
        title={tooltip}>
        {statusIcon}
        <span>{label}</span>
      </div>
    );
  }

  if (status === "checking") {
    return (
      <div className="flex items-center gap-1.5 opacity-50" style={{ height: "100%", padding: "0 8px", fontSize: 11 }}>
        <RefreshCw style={{ fontSize: 12, animation: "spin 1s linear infinite" }} className="animate-spin" />
        <span>{t("update.checking")}</span>
      </div>
    );
  }

  return null;
}
