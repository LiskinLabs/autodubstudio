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
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 'var(--space-12) var(--space-6)',
        textAlign: 'center',
        gap: 'var(--space-4)',
        flex: 1,
      }}
    >
      <div style={{ color: 'var(--text-muted)', marginBottom: 'var(--space-2)' }}>
        <Icon />
      </div>
      <h3 style={{ fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
        {title}
      </h3>
      <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', maxWidth: 360, lineHeight: 1.6, margin: 0 }}>
        {subtitle}
      </p>
      {action && (
        <button
          className="btn btn-primary"
          onClick={action.onClick}
          style={{ marginTop: 'var(--space-2)' }}
        >
          {action.label}
        </button>
      )}
    </motion.div>
  );
}
