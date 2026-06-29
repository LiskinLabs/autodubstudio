import re

with open(r"C:\Users\silvestr.liskin\Desktop\AutoDubStudio\backend\translator.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add context pre-analysis to smart_translate_segments
# We'll inject it before "Step 2: AI refinement"
step2_marker = "        # ── Step 2: AI refinement (Gemma4/Gemini/DeepSeek) ──"

context_logic = """
        context_summary = ""
        if is_ai_refine:
            if log_callback:
                log_callback("Analyzing script context for Netflix-style translation...")
            full_script_sample = "\\n".join([f"{s.get('speaker', 'Unknown')}: {s['text'].strip()}" for s in segments])[:4000]
            context_prompt = f"Analyze this video script and provide a brief summary of the context, plot, and speaker genders/roles. Keep it under 3 sentences.\\n\\n{full_script_sample}"
            try:
                context_summary = self._call_llm(context_prompt, is_json=False).strip()
                if log_callback:
                    log_callback(f"Context: {context_summary}")
            except Exception as e:
                context_summary = ""
"""
content = content.replace(step2_marker, context_logic + "\n" + step2_marker)

# 2. Add CPS constraints to the batch loops
def patch_batch_loop(text):
    # This applies to both the is_ollama loop and the is_ai_refine loop
    # Find the dialogue builder
    text = re.sub(
        r'orig = seg\["text"\]\.strip\(\)\n\s+base = seg\.get\("translated_base", orig\)\n\s+dialogue\.append\(\n\s+f"\[{i}\] \{spk\}\\n    Original: \{orig\}\\n    Draft: \{base\}"\n\s+\)',
        '''orig = seg["text"].strip()
                    base = seg.get("translated_base", orig)
                    duration = seg["end"] - seg["start"]
                    max_chars = max(15, int(duration * 17))  # 17 CPS is Netflix max readable limit
                    dialogue.append(
                        f"[{i}] {spk} (Duration: {duration:.1f}s, Max length: {max_chars} chars)\\n    Original: {orig}\\n    Draft: {base}"
                    )''',
        text
    )
    # Find the prompt rules
    text = text.replace(
        '- Keep names/brands/tech terms unchanged{glossary_text}',
        '- Keep names/brands/tech terms unchanged{glossary_text}\\n- CRITICAL: "text" MUST NOT exceed the "Max length" character limit! Shorten the translation if needed.'
    )
    # Inject context_summary into prompt
    text = text.replace(
        'Dialogue:\n{full_text}',
        'Video Context:\\n{context_summary}\\n\\nDialogue:\\n{full_text}'
    )
    return text

content = patch_batch_loop(content)

# We also need to patch _gemma4_refine
def patch_gemma4_refine(text):
    text = re.sub(
        r'base = seg\.get\("translated_base", orig\)\n\s+dialogue\.append\(f"\[\{j\}\] \{spk\}\\n    Original: \{orig\}\\n    Draft: \{base\}"\)',
        '''base = seg.get("translated_base", orig)
                duration = seg["end"] - seg["start"]
                max_chars = max(15, int(duration * 17))
                dialogue.append(f"[{j}] {spk} (Duration: {duration:.1f}s, Max length: {max_chars} chars)\\n    Original: {orig}\\n    Draft: {base}")''',
        text
    )
    # _gemma4_refine uses {full_text}
    text = text.replace(
        'Dialogue:\n{full_text}',
        'Video Context:\\n{context_summary}\\n\\nDialogue:\\n{full_text}'
    )
    return text

content = patch_gemma4_refine(content)

# Fix _gemma4_refine to accept context_summary
content = content.replace(
    'def _gemma4_refine(\n        self, segments, target_lang, log_callback=None, check_cancelled=None, _l=None\n    ):',
    'def _gemma4_refine(\n        self, segments, target_lang, log_callback=None, check_cancelled=None, _l=None, context_summary=""\n    ):'
)
# And pass it where called
content = content.replace(
    'return self._gemma4_refine(\n                segments, target_lang, log_callback, check_cancelled, _l=_l\n            )',
    'return self._gemma4_refine(\n                segments, target_lang, log_callback, check_cancelled, _l=_l, context_summary=context_summary\n            )'
)

with open(r"C:\Users\silvestr.liskin\Desktop\AutoDubStudio\backend\translator.py", "w", encoding="utf-8") as f:
    f.write(content)

print("translator.py patched successfully.")
