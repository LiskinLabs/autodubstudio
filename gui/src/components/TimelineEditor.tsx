import { useEffect, useRef, useState } from "react";
import WaveSurfer from "wavesurfer.js";
import RegionsPlugin from "wavesurfer.js/dist/plugins/regions.esm.js";
import HoverPlugin from "wavesurfer.js/dist/plugins/hover.esm.js";
import TimelinePlugin from "wavesurfer.js/dist/plugins/timeline.esm.js";
import { convertFileSrc } from "@tauri-apps/api/core";
import { Button, Tooltip, Spinner, makeStyles, typographyStyles, tokens } from "@fluentui/react-components";
import { PlayRegular, PauseRegular, ZoomInRegular, ZoomOutRegular } from "@fluentui/react-icons";
import { useSettings } from "../store";

import { SPEAKER_COLORS } from "../lib/utils";

export interface SegmentData {
  start: number;
  end: number;
  speaker: string;
  trans: string;
  orig: string;
  speed?: number;
  pitch?: number;
  time?: string;
  gender?: string;
  skip_dub?: boolean;
}

interface TimelineEditorProps {
  mediaPath: string;
  segments: SegmentData[];
  onSegmentsChange: (updatedSegments: SegmentData[]) => void;
  playingSegmentIndex?: number | null;
}

const useStyles = makeStyles({
  container: {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
    backgroundColor: tokens.colorNeutralBackground1,
    padding: "16px",
    borderRadius: "8px",
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    marginBottom: "24px",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  title: {
    ...typographyStyles.subtitle2,
  },
  controls: {
    display: "flex",
    gap: "8px",
  },
  loadingContainer: {
    height: "120px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    color: tokens.colorNeutralForeground3,
  },
  waveContainer: {
    width: "100%",
    transitionProperty: "opacity",
    transitionDuration: "0.3s",
  },
  waveHidden: {
    opacity: 0,
  },
  waveVisible: {
    opacity: 1,
  },
  hint: {
    ...typographyStyles.caption1,
    color: tokens.colorNeutralForeground3,
    marginTop: "4px",
  }
});

export default function TimelineEditor({ mediaPath, segments, onSegmentsChange, playingSegmentIndex }: TimelineEditorProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const wavesurfer = useRef<WaveSurfer | null>(null);
  const regionsPlugin = useRef<RegionsPlugin | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isReady, setIsReady] = useState(false);
  const [zoom, setZoom] = useState(50);
  const { t } = useSettings();
  const styles = useStyles();

  useEffect(() => {
    if (!containerRef.current) return;

    let mediaUrl = mediaPath;
    if (mediaPath && !mediaPath.startsWith("http") && !mediaPath.startsWith("blob")) {
      mediaUrl = convertFileSrc(mediaPath);
    }

    const ws = WaveSurfer.create({
      container: containerRef.current,
      waveColor: "var(--colorBrandBackground2)",
      progressColor: "var(--colorBrandBackground)",
      cursorColor: "var(--colorPaletteRedBackground1)",
      barWidth: 2,
      barGap: 1,
      barRadius: 2,
      height: 120,
      normalize: true,
      minPxPerSec: zoom,
      plugins: [
        TimelinePlugin.create({ height: 20, style: { fontSize: "10px", color: "var(--colorNeutralForeground3)" } }),
        HoverPlugin.create({ lineColor: "var(--colorNeutralForeground4)", lineWidth: 1, labelBackground: "var(--colorNeutralBackgroundInverted)", labelColor: "var(--colorNeutralForegroundInverted)" }),
      ],
    });

    const regions = ws.registerPlugin(RegionsPlugin.create());
    regionsPlugin.current = regions;
    wavesurfer.current = ws;

    ws.on("ready", () => {
      setIsReady(true);
      segments.forEach((seg, i) => {
        regions.addRegion({
          start: seg.start,
          end: seg.end,
          color: SPEAKER_COLORS[seg.speaker] || SPEAKER_COLORS.default,
          content: (() => {
            const el = document.createElement("div");
            el.style.cssText = "font-size:10px;font-weight:bold;padding:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;";
            el.textContent = seg.speaker;
            return el;
          })(),
          id: `seg_${i}`,
          drag: true,
          resize: true,
        });
      });
    });

    ws.on("play", () => setIsPlaying(true));
    ws.on("pause", () => setIsPlaying(false));

    regions.on("region-updated", (region) => {
      const index = parseInt(region.id.replace("seg_", ""), 10);
      if (!isNaN(index)) {
        const updated = [...segments];
        updated[index] = { ...updated[index], start: region.start, end: region.end };
        onSegmentsChange(updated);
      }
    });

    ws.load(mediaUrl).catch((e) => {
      if (e.name !== "AbortError") {
        console.error("WaveSurfer load error:", e);
      }
    });

    return () => {
      try {
        ws.destroy();
      } catch (e) {
        console.warn("WaveSurfer destroy error:", e);
      }
    };
  }, [mediaPath]);

  useEffect(() => {
    if (wavesurfer.current && isReady) {
      wavesurfer.current.zoom(zoom);
    }
  }, [zoom, isReady]);

  useEffect(() => {
    if (wavesurfer.current && isReady && playingSegmentIndex !== undefined && playingSegmentIndex !== null) {
      const seg = segments[playingSegmentIndex];
      if (seg) {
        wavesurfer.current.setTime(seg.start);
      }
    }
  }, [playingSegmentIndex, isReady]);

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div className={styles.title}>{t("dubbing.timeline.title") || "Interactive Timeline"}</div>
        <div className={styles.controls}>
          <Button 
            appearance="subtle" 
            icon={isPlaying ? <PauseRegular /> : <PlayRegular />} 
            onClick={() => wavesurfer.current?.playPause()}
            disabled={!isReady}
          />
          <Tooltip content="Zoom Out" relationship="label">
            <Button appearance="subtle" icon={<ZoomOutRegular />} onClick={() => setZoom(z => Math.max(10, z - 20))} disabled={!isReady} />
          </Tooltip>
          <Tooltip content="Zoom In" relationship="label">
            <Button appearance="subtle" icon={<ZoomInRegular />} onClick={() => setZoom(z => Math.min(500, z + 20))} disabled={!isReady} />
          </Tooltip>
        </div>
      </div>
      
      {!isReady && (
        <div className={styles.loadingContainer}>
          <Spinner size="medium" label={t("loading.waveform") || "Loading Waveform..."} />
        </div>
      )}
      
      <div ref={containerRef} className={`${styles.waveContainer} ${isReady ? styles.waveVisible : styles.waveHidden}`} />
      <div className={styles.hint}>
        {t("dubbing.timeline.hint") || "Drag edges to resize segments, or drag the center to move them."}
      </div>
    </div>
  );
}
