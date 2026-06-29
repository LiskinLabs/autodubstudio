with open("engine.py", "r", encoding="utf-8") as f:
    code = f.read()

# 1. Demucs filename fix
code = code.replace(
    "--two-stems vocals", '--two-stems vocals --filename "{base_name}/{stem}.{ext}"'
)

# 2. Reference 4-8s fix
old_ref = """                        # Ideal reference length for F5/XTTS is ~7 seconds
                        dur_penalty = abs(dur - 7.0)
                        
                        # Reward high word density (active speech), max out at ~3 words per sec
                        wps = word_count / max(dur, 0.1)
                        density_score = min(wps, 3.0) * 2.0  # Up to +6 points for dense speech
                        
                        score = density_score - dur_penalty"""  # noqa: W293

new_ref = """                        # Ideal reference length for F5/XTTS is 4 to 8 seconds
                        if dur < 4.0:
                            dur_penalty = (4.0 - dur) * 2.0
                        elif dur > 8.5:
                            dur_penalty = (dur - 8.5) * 2.0
                        else:
                            dur_penalty = 0.0
                        
                        # Reward high word density (active speech), max out at ~3 words per sec
                        wps = word_count / max(dur, 0.1)
                        density_score = min(wps, 3.0) * 2.0  # Up to +6 points for dense speech
                        
                        score = density_score - dur_penalty"""  # noqa: W293

code = code.replace(old_ref, new_ref)

# 3. manual_subs gender
old_subs = """                "skip_dub": s.get("skip_dub", False),
            })"""
new_subs = """                "skip_dub": s.get("skip_dub", False),
                "gender": s.get("gender", "unknown")
            })"""
code = code.replace(old_subs, new_subs)

old_man = """                            "speaker": s.get('speaker', 'SPEAKER_00')
                        })"""
new_man = """                            "speaker": s.get('speaker', 'SPEAKER_00'),
                            "gender": s.get('gender', 'unknown'),
                            "skip_dub": s.get('skip_dub', False)
                        })"""
code = code.replace(old_man, new_man)

with open("engine.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Patched successfully!")
