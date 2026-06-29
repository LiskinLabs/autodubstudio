import sys

sys.stdout.reconfigure(encoding="utf-8")
import os
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine import AutoDubWorker


class MockSignal:
    def __init__(self, name):
        self.name = name

    def emit(self, *args, **kwargs):
        print(
            f"[{self.name}]",
            str(args).encode("utf-8", "replace").decode("utf-8"),
            kwargs,
        )

    def connect(self, cb):
        pass


def main():
    videos = [
        r"C:\Users\silvestr.liskin\Downloads\recordings\ACP training-20251008_100238-Meeting Recording 1.mp4",
        r"C:\Users\silvestr.liskin\Downloads\recordings\ACP training-20251008_100238-Meeting Recording.mp4",
        r"C:\Users\silvestr.liskin\Downloads\recordings\ACP training-20251008_130639-Meeting Recording.mp4",
    ]

    for video in videos:
        print(
            f"\n=======================\nStarting processing for: {video}\n=======================\n"
        )
        try:
            cfg = {
                "video_path": video,
                "target_lang": "tr",
                "translate_engine": "google",
                "tts_engine": "edge-tts",
                "vocals_volume": 1.0,
                "bg_volume": 1.0,
                "diarize": True,
                "create_subtitles": True,
                "manual_mode": False,
            }
            engine = AutoDubWorker(cfg)

            # Monkeypatch signals so they don't throw errors if undefined
            engine.progress_signal = MockSignal("progress")
            engine.log_signal = MockSignal("log")
            engine.finished_signal = MockSignal("finished")
            engine.manual_edit_signal = MockSignal("manual_edit")
            engine.vram_warning_signal = MockSignal("vram_warning")
            engine.translation_ready_signal = MockSignal("translation_ready")
            engine.extras_signal = MockSignal("extras")

            engine.run()
            print(f"Successfully finished: {video}")
        except Exception as e:
            print(f"FAILED on {video}: {e}")
            traceback.print_exc()


if __name__ == "__main__":
    main()
