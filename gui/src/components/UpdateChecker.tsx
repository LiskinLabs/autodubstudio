import { useEffect, useState, useCallback } from 'react';
import { check } from '@tauri-apps/plugin-updater';
import { relaunch } from '@tauri-apps/plugin-process';
import { notifyToast } from '../lib/toast';
import { useSettings } from '../store';

type UpdateStatus = 'idle' | 'checking' | 'available' | 'downloading' | 'ready' | 'error';

interface UpdateInfo {
  version: string;
  body?: string;
}

export default function UpdateChecker() {
  const { t } = useSettings();
  const [status, setStatus] = useState<UpdateStatus>('idle');
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(null);
  const [downloadProgress, setDownloadProgress] = useState(0);

  const checkForUpdates = useCallback(async () => {
    if (status !== 'idle') return;
    setStatus('checking');

    try {
      const update = await check();
      if (update) {
        setUpdateInfo({
          version: update.version,
          body: update.body,
        });
        setStatus('available');

        // Show toast notification
        notifyToast.info(`🔥 Update v${update.version} available!`, {
          description: 'A new version is ready. Starting background download...',
          duration: 5000,
          id: 'update-available',
        });

        // Auto-start download after short delay
        setTimeout(() => downloadUpdate(update), 2000);
      } else {
        setStatus('idle');
      }
    } catch (err) {
      console.error('[Updater] Check failed:', err);
      setStatus('error');
    }
  }, [status]);

  const downloadUpdate = useCallback(async (update: any) => {
    setStatus('downloading');
    let contentLength = 0;
    let downloaded = 0;

    try {
      await update.download((event: any) => {
        switch (event.event) {
          case 'Started':
            contentLength = event.data.contentLength || 0;
            notifyToast.loading(`Downloading update (${Math.round(contentLength / 1024 / 1024)}MB)...`, {
              id: 'update-download',
              description: 'This may take a few minutes. We\'ll notify you when it\'s ready.',
            });
            break;
          case 'Progress':
            downloaded += event.data.chunkLength;
            if (contentLength > 0) {
              setDownloadProgress(Math.round((downloaded / contentLength) * 100));
            }
            break;
          case 'Finished':
            setStatus('ready');
            notifyToast.success('✅ Update downloaded!', {
              description: 'Restart now to apply the update?',
              duration: 0, // Stays until dismissed
              id: 'update-ready',
            });
            break;
        }
      });
    } catch (err) {
      console.error('[Updater] Download failed:', err);
      setStatus('error');
      notifyToast.error('Update download failed', {
        description: 'Will retry on next launch.',
        id: 'update-error',
      });
    }
  }, []);

  const installUpdate = useCallback(async () => {
    try {
      notifyToast.loading('Installing update...', {
        description: 'App will restart automatically.',
        id: 'update-install',
      });
      await relaunch();
    } catch (err) {
      console.error('[Updater] Install failed:', err);
      notifyToast.error('Failed to install update', {
        description: 'Please restart manually.',
      });
    }
  }, []);

  // Check on mount
  useEffect(() => {
    const timer = setTimeout(checkForUpdates, 3000); // Delay to let UI load
    return () => clearTimeout(timer);
  }, []);

  // Render nothing — everything is toast-based
  // But render a statusbar indicator when update is available
  if (status === 'available' || status === 'downloading' || status === 'ready') {
    const label = status === 'ready'
      ? `⬆️ v${updateInfo?.version} ready`
      : status === 'downloading'
        ? `⬇️ ${downloadProgress}%`
        : `⬆️ v${updateInfo?.version}`;

    return (
      <div
        className="status-item"
        style={{ cursor: 'pointer', color: 'var(--accent)' }}
        onClick={() => {
          if (status === 'ready') installUpdate();
        }}
        title={
          status === 'ready'
            ? 'Click to install and restart'
            : status === 'downloading'
              ? 'Downloading update...'
              : 'Update available'
        }
      >
        <span>{label}</span>
      </div>
    );
  }

  if (status === 'checking') {
    return (
      <div className="status-item" style={{ color: 'var(--text-muted)' }}>
        <span>🔄 Checking updates...</span>
      </div>
    );
  }

  return null;
}
