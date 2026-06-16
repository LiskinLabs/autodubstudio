import os
import re
import ast
import json
import torch
from deep_translator import GoogleTranslator

# LLM imports
try:
    from google import genai
    from openai import OpenAI
except ImportError:
    pass

class Translator:
    def __init__(self, engine_name, gemini_key="", deepseek_key="", deepl_key="", device="cpu", gguf_model_path=None):
        self.engine_name = engine_name
        self.gemini_key = gemini_key
        self.deepseek_key = deepseek_key
        self.deepl_key = deepl_key
        self.device = device
        self.gguf_model_path = gguf_model_path
        self.qwen_model = None
        self.qwen_tokenizer = None
        self.llama_cpp_model = None

    def translate_text(self, text, target_lang):
        if not text.strip(): return ""
        try:
            lang_names = {"ru": "Russian", "en": "English", "tr": "Turkish", "ar": "Arabic",
                          "es": "Spanish", "fr": "French", "de": "German", "zh": "Chinese",
                          "ja": "Japanese", "ko": "Korean", "it": "Italian", "pt": "Portuguese"}
            lang_name = lang_names.get(target_lang, target_lang)
            prompt = f"Translate this subtitle to {lang_name}. Output only the translation.\n{text}"

            if "gemini" in self.engine_name.lower() and self.gemini_key:
                client = genai.Client(api_key=self.gemini_key)
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt
                )
                return response.text.strip()

            elif "deepseek" in self.engine_name.lower() and self.deepseek_key:
                client = OpenAI(api_key=self.deepseek_key, base_url="https://api.deepseek.com")
                response = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=1024
                )
                return response.choices[0].message.content.strip()

            elif "deepl" in self.engine_name.lower() and self.deepl_key:
                import urllib.request
                import urllib.error
                import json
                is_free = self.deepl_key.endswith(':fx')
                url = "https://api-free.deepl.com/v2/translate" if is_free else "https://api.deepl.com/v2/translate"
                
                payload = json.dumps({
                    "text": [text],
                    "target_lang": target_lang.upper()
                }).encode('utf-8')
                
                headers = {
                    'Authorization': f'DeepL-Auth-Key {self.deepl_key}',
                    'Content-Type': 'application/json'
                }
                
                req = urllib.request.Request(url, data=payload, headers=headers)
                try:
                    with urllib.request.urlopen(req, timeout=30) as response:
                        if response.status == 200:
                            result = json.loads(response.read().decode())
                            return result["translations"][0]["text"].strip()
                except Exception as e:
                    print(f"DeepL translation failed: {e}")
                    return text

            elif "ollama" in self.engine_name.lower():
                # Base translation: always use Google Translate (fast, reliable).
                # Gemma4 refinement happens in smart_translate_segments batches.
                return GoogleTranslator(source='auto', target=target_lang).translate(text)

            elif "llamacpp" in self.engine_name.lower() and self.gguf_model_path:
                from llama_cpp import Llama
                if not self.llama_cpp_model:
                    n_gpu_layers = -1 if self.device == "cuda" else 0
                    self.llama_cpp_model = Llama(
                        model_path=self.gguf_model_path,
                        n_gpu_layers=n_gpu_layers,
                        n_ctx=2048,
                        verbose=False
                    )
                response = self.llama_cpp_model.create_chat_completion(
                    messages=[{"role": "user", "content": prompt}]
                )
                return response["choices"][0]["message"]["content"].strip()

            else:
                return GoogleTranslator(source='auto', target=target_lang).translate(text)
        except Exception as e:
            print(f"Translation error: {e}")
            return text

    def _extract_json(self, text: str) -> str:
        """Extract JSON object/array from LLM response, stripping markdown fences and noise."""
        if not text:
            return ""
        text = text.strip()
        # Remove markdown code fences
        text = re.sub(r'```(?:json)?\s*\n?', '', text)
        text = re.sub(r'\n?```', '', text)
        text = text.strip()
        # Find the outermost JSON object or array
        # Try object first
        depth = 0
        start = -1
        for i, ch in enumerate(text):
            if ch == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0 and start >= 0:
                    return text[start:i+1]
        # Try array
        depth = 0
        start = -1
        for i, ch in enumerate(text):
            if ch == '[':
                if depth == 0:
                    start = i
                depth += 1
            elif ch == ']':
                depth -= 1
                if depth == 0 and start >= 0:
                    return text[start:i+1]
        # No JSON found — return original
        return text

    def _call_llm(self, prompt, is_json=True):
        if "gemini" in self.engine_name.lower() and self.gemini_key:
            client = genai.Client(api_key=self.gemini_key)
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            return response.text

        elif "deepseek" in self.engine_name.lower() and self.deepseek_key:
            client = OpenAI(api_key=self.deepseek_key, base_url="https://api.deepseek.com")
            kwargs = {}
            if is_json: kwargs["response_format"] = {"type": "json_object"}
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                **kwargs
            )
            return response.choices[0].message.content

        elif "ollama" in self.engine_name.lower():
            import urllib.request
            import urllib.error
            import json
            url = "http://localhost:11434/api/generate"
            # NOTE: Do NOT use "format": "json" — it breaks Cyrillic in Ollama.
            # Instead we extract JSON from the free-text response below.

            # Try larger model first for better translation, fall back to smaller
            models_to_try = ["gemma4:e4b"]
            for model_name in models_to_try:
                payload = json.dumps({
                    "model": model_name,
                    "prompt": prompt,
                    "stream": False,
                    "keep_alive": 300,  # Keep model in GPU for 5 min between requests
                    "options": {"temperature": 0.1, "num_predict": 2048}
                }).encode('utf-8')
                headers = {'Content-Type': 'application/json'}
                req = urllib.request.Request(url, data=payload, headers=headers)
                try:
                    with urllib.request.urlopen(req, timeout=60) as resp:
                        if resp.status == 200:
                            result = json.loads(resp.read().decode())
                            text = result.get("response", "")
                            # Extract JSON from response (strip markdown fences if any)
                            json_text = self._extract_json(text)
                            if json_text:
                                return json_text
                            # If no JSON found, return raw text for non-JSON calls
                            if not is_json:
                                return text.strip()
                except Exception as e:
                    print(f"Ollama _call_llm {model_name} error: {e}. Trying next...")
                    continue

            raise RuntimeError("All Ollama models failed for smart JSON translation.")

        elif "qwen" in self.engine_name.lower():
            from transformers import AutoModelForCausalLM, AutoTokenizer

            if not self.qwen_model:
                if self.device == "cuda":
                    torch.cuda.empty_cache()

                model_id = "Qwen/Qwen2.5-1.5B-Instruct"
                self.qwen_tokenizer = AutoTokenizer.from_pretrained(model_id)

                if self.device == "cuda":
                    self.qwen_model = AutoModelForCausalLM.from_pretrained(
                        model_id, torch_dtype=torch.float16
                    ).to("cuda")
                else:
                    self.qwen_model = AutoModelForCausalLM.from_pretrained(
                        model_id, torch_dtype=torch.float32
                    )

            chat = [{"role": "user", "content": prompt}]
            formatted_prompt = self.qwen_tokenizer.apply_chat_template(chat, tokenize=False, add_generation_prompt=True)
            inputs = self.qwen_tokenizer(formatted_prompt, return_tensors="pt")
            if self.device == "cuda":
                inputs = {k: v.to("cuda") for k, v in inputs.items()}

            outputs = self.qwen_model.generate(**inputs, max_new_tokens=4096)
            response_text = self.qwen_tokenizer.decode(outputs[0][inputs['input_ids'].shape[-1]:], skip_special_tokens=True)

            return response_text
            
        elif "llamacpp" in self.engine_name.lower() and self.gguf_model_path:
            from llama_cpp import Llama
            if not self.llama_cpp_model:
                n_gpu_layers = -1 if self.device == "cuda" else 0
                self.llama_cpp_model = Llama(
                    model_path=self.gguf_model_path,
                    n_gpu_layers=n_gpu_layers,
                    n_ctx=2048,
                    verbose=False
                )
            
            kwargs = {}
            if is_json:
                kwargs["response_format"] = {"type": "json_object"}
                
            response = self.llama_cpp_model.create_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                **kwargs
            )
            return response["choices"][0]["message"]["content"].strip()
            
        # Fallback logic if we are doing smart translation over Google/DeepL
        if self.gemini_key:
            client = genai.Client(api_key=self.gemini_key)
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            return response.text
        elif self.deepseek_key:
            client = OpenAI(api_key=self.deepseek_key, base_url="https://api.deepseek.com")
            kwargs = {}
            if is_json: kwargs["response_format"] = {"type": "json_object"}
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                **kwargs
            )
            return response.choices[0].message.content
        else:
            # Fallback to Ollama
            import urllib.request
            import urllib.error
            import json
            url = "http://localhost:11434/api/generate"
            # No "format": "json" — it breaks Cyrillic (use _extract_json instead)
            for model_name in ["qwen2.5:14b", "qwen2.5:7b", "gemma2:2b"]:
                payload = json.dumps({
                    "model": model_name,
                    "prompt": prompt,
                    "stream": False,
                    "keep_alive": 300,  # Keep model in GPU for 5 min between requests
                    "options": {"temperature": 0.1, "num_predict": 2048}
                }).encode('utf-8')
                headers = {'Content-Type': 'application/json'}
                req = urllib.request.Request(url, data=payload, headers=headers)
                try:
                    with urllib.request.urlopen(req, timeout=60) as response:
                        if response.status == 200:
                            result = json.loads(response.read().decode())
                            return result.get("response", "")
                except Exception as e:
                    continue
            raise RuntimeError("All LLM fallbacks failed for smart JSON translation.")

    def release_models(self):
        import gc
        if "ollama" in self.engine_name.lower():
            import urllib.request
            import json
            url = "http://localhost:11434/api/generate"
            for model_name in ["gemma2:2b", "gemma2"]:
                try:
                    payload = json.dumps({"model": model_name, "prompt": "", "keep_alive": 0}).encode('utf-8')
                    urllib.request.urlopen(urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'}), timeout=2)
                except Exception:
                    pass
        if self.qwen_model:
            del self.qwen_model
            del self.qwen_tokenizer
            self.qwen_model = None
            self.qwen_tokenizer = None
        if self.llama_cpp_model:
            del self.llama_cpp_model
            self.llama_cpp_model = None
        gc.collect()
        if self.device == "cuda":
            torch.cuda.empty_cache()

    def smart_translate_segments(self, segments, target_lang, log_callback=None):
        is_ollama = "ollama" in self.engine_name.lower()
        is_ai_refine = is_ollama or (("gemini" in self.engine_name.lower() and self.gemini_key) or
                                      ("deepseek" in self.engine_name.lower() and self.deepseek_key))

        # ── Step 1: ALWAYS get a base translation (Google Translate) for fallback ──
        if log_callback: log_callback("⚡ Google Translate — базовый перевод...")
        for seg in segments:
            orig_text = seg["text"].strip()
            if orig_text:
                seg["translated_base"] = self.translate_text(orig_text, target_lang)
            else:
                seg["translated_base"] = ""

        # ── Step 2: AI refinement (Gemma4/Gemini/DeepSeek) ──
        if is_ollama:
            # Gemma4: refine Google Translate in small batches
            batch_size = 4  # Smaller batches = faster, less failure-prone
            total = len(segments)
            lang_names = {"ru": "Russian", "en": "English", "tr": "Turkish", "ar": "Arabic"}
            lang_name = lang_names.get(target_lang, target_lang)

            if log_callback:
                log_callback(f"🧠 Gemma4 улучшает перевод (батчи по {batch_size}, {total} сегментов)...")

            gemma4_failures = 0  # Circuit breaker
            for batch_start in range(0, total, batch_size):
                batch_end = min(batch_start + batch_size, total)
                batch = segments[batch_start:batch_end]

                # Build dialogue for refinement
                dialogue = []
                for i, seg in enumerate(batch):
                    idx = batch_start + i
                    spk = seg.get("speaker", "SPEAKER_00")
                    orig = seg["text"].strip()
                    base = seg.get("translated_base", orig)
                    dialogue.append(f"[{i}] {spk}\n    Original: {orig}\n    Draft: {base}")

                full_text = "\n\n".join(dialogue)

                prompt = f"""Improve these subtitle translations to sound natural in {lang_name}. Fix grammar, flow, and make them conversational.

Rules:
- Output a JSON object with "segments" array
- Each segment: {{"text": "improved translation", "skip_dub": false}}
- Keep names/brands/tech terms unchanged
- If the Draft is already perfect, copy it as-is

Dialogue:
{full_text}

JSON:"""

                # Circuit breaker: skip Gemma4 if it failed 3 times in a row
                if gemma4_failures >= 3:
                    if log_callback and gemma4_failures == 3:
                        log_callback("  ⚡ Gemma4 недоступен — использую Google Translate для оставшихся батчей")
                    gemma4_failures += 1  # Keep incrementing to avoid re-logging
                    continue

                try:
                    response = self._call_llm(prompt, is_json=True)
                    data = json.loads(response)
                    parsed = data.get("segments", [])
                    gemma4_failures = 0  # Reset on success

                    if parsed and len(parsed) == len(batch):
                        for i, p_seg in enumerate(parsed):
                            new_text = p_seg.get("text", "").strip()
                            if new_text:
                                batch[i]["text"] = new_text
                    elif parsed:
                        if log_callback:
                            log_callback(f"  ⚠ Gemma4 mismatch ({len(parsed)}/{len(batch)}), partial merge")
                        for i in range(min(len(parsed), len(batch))):
                            new_text = parsed[i].get("text", "").strip()
                            if new_text:
                                batch[i]["text"] = new_text

                except Exception as e:
                    gemma4_failures += 1
                    if log_callback:
                        log_callback(f"  ⚠ Gemma4 batch failed ({gemma4_failures}/3): {str(e)[:80]}. Using Google Translate.")

            if log_callback: log_callback("✅ Перевод завершен!")
            self.release_models()
            return segments

        # ── Non-AI engines: just use base translation ──
        if not is_ai_refine:
            for seg in segments:
                seg["text"] = seg.get("translated_base", seg["text"])
            if log_callback: log_callback("✅ Перевод завершен!")
            self.release_models()
            return segments

        # ── Gemini/DeepSeek: smart batch translation ──
        if is_ai_refine and not is_ollama:

            if log_callback: log_callback("✅ Перевод завершен!")
            self.release_models()
            return segments

        # Gemini/DeepSeek/Qwen: batch JSON translation (reliable for these engines)
        if log_callback: log_callback("🧠 Умный ИИ-перевод / Корректировка (батчами по 5)...")

        batch_size = 5
        total_segments = len(segments)

        for batch_start in range(0, total_segments, batch_size):
            batch_end = min(batch_start + batch_size, total_segments)
            batch = segments[batch_start:batch_end]

            if log_callback: log_callback(f"  -> Перевод фрагментов {batch_start + 1}-{batch_end} из {total_segments}...")

            dialogue = []
            for i, seg in enumerate(batch):
                spk = seg.get("speaker", "SPEAKER_00")
                txt = seg["text"].strip()
                base_trans = seg.get("translated_base", "")
                if base_trans:
                    dialogue.append(f"[{i}] {spk} (Original): {txt}\n    (Draft Translation): {base_trans}")
                else:
                    dialogue.append(f"[{i}] {spk}: {txt}")

            full_text = "\n".join(dialogue)
            prompt_1 = f"""You are an expert localization editor. Translate to {target_lang} or correct the Draft Translation.
CRITICAL RULES:
1. Fix typos and hallucinations. If a Draft Translation is provided, improve it to sound natural in {target_lang}.
2. If a segment's original text is ALREADY in {target_lang} (or mostly in {target_lang}), do NOT translate it. Keep the translated text EXACTLY identical to the original text, and set a boolean field 'skip_dub': true for that segment.
3. Otherwise, set 'skip_dub': false.

Input:
{full_text}

Return ONLY a JSON object with a 'segments' array containing dicts with keys 'speaker', 'text' (the final translation), and 'skip_dub'."""

            try:
                response_text_1 = self._call_llm(prompt_1, is_json=True)
                response_text_1 = re.sub(r'```[a-z]*\n|```', '', response_text_1).strip()

                data = json.loads(response_text_1)
                parsed = data.get("segments", [])

                if parsed and len(parsed) == len(batch):
                    # Perfect match
                    for i, p_seg in enumerate(parsed):
                        trans = p_seg.get("text", batch[i]["text"])
                        original_text = batch[i]["text"]
                        if original_text.lower().strip() == trans.lower().strip():
                            batch[i]["skip_dub"] = True
                        batch[i]["text"] = trans
                        batch[i]["speaker"] = p_seg.get("speaker", batch[i]["speaker"])
                elif parsed:
                    # Tolerance: use what we have, fallback for rest
                    if log_callback: log_callback(f"  ⚠ JSON mismatch: got {len(parsed)} segments, expected {len(batch)}. Partial merge...")
                    for i in range(min(len(parsed), len(batch))):
                        trans = parsed[i].get("text", batch[i]["text"])
                        if batch[i]["text"].lower().strip() == trans.lower().strip():
                            batch[i]["skip_dub"] = True
                        batch[i]["text"] = trans
                    # Per-line fallback for remaining
                    for i in range(len(parsed), len(batch)):
                        orig = batch[i]["text"].strip()
                        batch[i]["text"] = batch[i].get("translated_base", orig)
                else:
                    raise ValueError("Empty JSON response")
            except Exception as e:
                if log_callback: log_callback(f"⚠ Ошибка ИИ-перевода батча {batch_start + 1}-{batch_end}: {e}. Построчный откат...")
                for seg in batch:
                    orig_text = seg["text"].strip()
                    if "translated_base" in seg:
                        seg["text"] = seg["translated_base"]
                    else:
                        seg["text"] = self.translate_text(orig_text, target_lang)
                    if orig_text.lower() == seg["text"].lower():
                        seg["skip_dub"] = True

        if log_callback: log_callback("✅ Перевод завершен!")
        self.release_models()
        return segments
