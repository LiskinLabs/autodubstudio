import os

with open("engine.py", "r", encoding="utf-8") as f:
    text = f.read()

# Find the last 'except Exception as e:' which is in the run() method
split_marker = "        except Exception as e:\n            import traceback\n            err = traceback.format_exc()\n            self.finished_signal.emit(False, str(err))"

parts = text.split(split_marker)
if len(parts) >= 2:
    good_text = split_marker.join(parts[:-1]) + split_marker
    
    append_text = """
        finally:
            self.log_signal.emit("🧹 Очистка временных файлов...")
            import shutil
            import glob
            # Очистка по списку
            for cp in all_created_files:
                try:
                    if os.path.exists(cp): os.remove(cp)
                except: pass
            
            # Тотальная очистка всех мусорных файлов по маскам в папке загрузок
            try:
                for pattern in ["temp_*.*", "ref_*.wav", "f5_tasks_*.json", "xtts_tasks_*.json", "qwen_tasks_*.json"]:
                    for fpath in glob.glob(os.path.join(self.out_dir, pattern)):
                        try: os.remove(fpath)
                        except: pass
            except: pass

            if 'demucs_out_dir' in locals() and os.path.exists(demucs_out_dir):
                try:
                    shutil.rmtree(demucs_out_dir)
                except: pass

    def format_timestamp(self, seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds % 60
        ms = int((s - int(s)) * 1000)
        return f"{h:02d}:{m:02d}:{int(s):02d},{ms:03d}"
"""
    with open("engine.py", "w", encoding="utf-8") as f:
        f.write(good_text + append_text)
    print("engine.py fixed!")
else:
    print("Marker not found.")
