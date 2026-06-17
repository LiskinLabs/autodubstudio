import { motion } from 'motion/react';

interface EmptyStateProps {
  icon: 'video' | 'chat' | 'audio' | 'settings' | 'search';
  title: string;
  subtitle: string;
  action?: { label: string; onClick: () => void };
}

function IconVideo() {
  return (
    <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" opacity={0.3}>
      <rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18" />
      <line x1="7" y1="2" x2="7" y2="22" />
      <line x1="17" y1="2" x2="17" y2="22" />
      <line x1="2" y1="12" x2="22" y2="12" />
      <line x1="2" y1="7" x2="7" y2="7" />
      <line x1="2" y1="17" x2="7" y2="17" />
      <line x1="17" y1="7" x2="22" y2="7" />
      <line x1="17" y1="17" x2="22" y2="17" />
    </svg>
  );
}

function IconChat() {
  return (
    <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" opacity={0.3}>
      <circle cx="12" cy="12" r="10" />
      <path d="M12 8v4l3 3" />
      <rect x="4" y="4" width="6" height="6" rx="1" />
      <rect x="14" y="14" width="6" height="6" rx="1" />
    </svg>
  );
}

function IconAudio() {
  return (
    <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" opacity={0.3}>
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="23" />
      <line x1="8" y1="23" x2="16" y2="23" />
    </svg>
  );
}

const iconMap = { video: IconVideo, chat: IconChat, audio: IconAudio, settings: IconChat, search: IconChat };

export default function EmptyState({ icon, title, subtitle, action }: EmptyStateProps) {
  const Icon = iconMap[icon];

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="flex flex-col items-center justify-center py-12 px-6 text-center gap-4 flex-1"
    >
      <div className="text-base-content/40 mb-2">
        <Icon />
      </div>
      <h3 className="text-lg font-semibold text-base-content m-0">
        {title}
      </h3>
      <p className="text-sm text-base-content/70 max-w-[360px] leading-relaxed m-0">
        {subtitle}
      </p>
      {action && (
        <button
          className="btn btn-primary mt-2"
          onClick={action.onClick}
        >
          {action.label}
        </button>
      )}
    </motion.div>
  );
}
