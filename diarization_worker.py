import os
import sys
import json
import torch
import traceback

def main():
    if len(sys.argv) < 4:
        print("Usage: python diarization_worker.py <input_audio.wav> <output.json> <hf_token>")
        sys.exit(1)

    audio_path = sys.argv[1]
    output_json = sys.argv[2]
    hf_token = sys.argv[3]

    if not os.path.exists(audio_path):
        print(f"File not found: {audio_path}")
        sys.exit(1)

    print("Запуск Pyannote Diarization 3.1...")
    print(f"Аудио: {audio_path}")
    
    try:
        from pyannote.audio import Pipeline
    except ImportError:
        print("Ошибка: pyannote.audio не установлена в текущем окружении!")
        print("Запустите: pip install pyannote.audio")
        sys.exit(2)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    try:
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=hf_token
        )
        if torch.cuda.is_available():
            pipeline.to(device)
    except Exception as e:
        print(f"Ошибка загрузки модели Pyannote (проверьте HF Token и доступ): {e}")
        sys.exit(3)

    print("Анализ аудио (это может занять время)...")
    try:
        diarization = pipeline(audio_path)
    except Exception as e:
        print(f"Ошибка при обработке аудио: {e}")
        sys.exit(4)

    results = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        results.append({
            "start": round(turn.start, 2),
            "end": round(turn.end, 2),
            "speaker": speaker
        })

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=4)

    unique_speakers = set(r["speaker"] for r in results)
    print(f"✅ Диаризация завершена. Найдено уникальных спикеров: {len(unique_speakers)}")
    print(f"Результат сохранен в {output_json}")
    sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(traceback.format_exc())
        sys.exit(5)
