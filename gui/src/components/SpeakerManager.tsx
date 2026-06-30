import { useMemo, useState } from "react";
import { Avatar, Card, Input, Button, Tooltip, makeStyles, typographyStyles, tokens } from "@fluentui/react-components";
import { EditRegular, CheckmarkRegular } from "@fluentui/react-icons";
import { useSettings } from "../store";
import { SPEAKER_COLORS } from "../lib/utils";
import { SegmentData } from "./TimelineEditor";

interface SpeakerManagerProps {
  segments: SegmentData[];
  onRenameSpeaker: (oldSpeakerId: string, newSpeakerId: string) => void;
}

const useStyles = makeStyles({
  card: {
    minWidth: "220px",
    padding: "16px 12px",
  },
  title: {
    ...typographyStyles.subtitle2,
    marginBottom: "16px",
  },
  list: {
    display: "flex",
    flexDirection: "column",
    gap: "16px",
  },
  empty: {
    ...typographyStyles.caption1,
    opacity: 0.6,
  },
  speakerRow: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
  },
  speakerInfo: {
    flexGrow: 1,
    display: "flex",
    flexDirection: "column",
  },
  editRow: {
    display: "flex",
    gap: "4px",
  },
  displayRow: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
  },
  speakerName: {
    ...typographyStyles.body1,
    fontWeight: tokens.fontWeightMedium,
    display: "flex",
    alignItems: "center",
  },
  colorDot: {
    display: "inline-block",
    width: "10px",
    height: "10px",
    borderRadius: "50%",
    marginRight: "8px",
    border: `1px solid ${tokens.colorNeutralStroke2}`,
  }
});

export default function SpeakerManager({ segments, onRenameSpeaker }: SpeakerManagerProps) {
  const { t } = useSettings();
  const styles = useStyles();
  
  const uniqueSpeakers = useMemo(() => {
    const speakers = new Set<string>();
    segments.forEach(s => speakers.add(s.speaker));
    return Array.from(speakers).sort();
  }, [segments]);

  const [editingSpeaker, setEditingSpeaker] = useState<string | null>(null);
  const [tempName, setTempName] = useState("");

  const startEditing = (spk: string) => {
    setEditingSpeaker(spk);
    setTempName(spk);
  };

  const commitEdit = () => {
    if (editingSpeaker && tempName.trim() && tempName !== editingSpeaker) {
      onRenameSpeaker(editingSpeaker, tempName.trim());
    }
    setEditingSpeaker(null);
  };

  return (
    <Card appearance="filled" className={styles.card}>
      <div className={styles.title}>
        {t("dubbing.speakers.title") || "Speakers"}
      </div>
      
      <div className={styles.list}>
        {uniqueSpeakers.length === 0 && (
          <div className={styles.empty}>No speakers found.</div>
        )}
        {uniqueSpeakers.map(spk => {
          const colorStr = SPEAKER_COLORS[spk] || SPEAKER_COLORS.default;
          
          return (
            <div key={spk} className={styles.speakerRow}>
              <Avatar 
                name={spk} 
                color="colorful" 
              />
              <div className={styles.speakerInfo}>
                {editingSpeaker === spk ? (
                  <div className={styles.editRow}>
                    <Input 
                      size="small" 
                      value={tempName} 
                      onChange={(e, d) => setTempName(d.value)} 
                      onKeyDown={e => e.key === "Enter" && commitEdit()}
                      autoFocus
                    />
                    <Button size="small" icon={<CheckmarkRegular />} appearance="subtle" onClick={commitEdit} />
                  </div>
                ) : (
                  <div className={styles.displayRow}>
                    <span className={styles.speakerName}>
                      <span className={styles.colorDot} style={{ backgroundColor: colorStr }} />
                      {spk}
                    </span>
                    <Tooltip content="Rename Speaker" relationship="label">
                      <Button size="small" appearance="transparent" icon={<EditRegular />} onClick={() => startEditing(spk)} />
                    </Tooltip>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
