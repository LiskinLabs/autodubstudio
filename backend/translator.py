import os
import re
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
            url = "http://localhost:11434/api/chat"  # Use chat API — proper template formatting for Gemma4

            # Dynamically scale num_predict + num_gpu based on available VRAM
            try:
                vram_free_mb = torch.cuda.mem_get_info()[0] // (1024 * 1024) if torch.cuda.is_available() else 0
            except Exception:
                vram_free_mb = 0
            num_predict = 2048 if vram_free_mb > 6000 else (1024 if vram_free_mb > 4000 else 512)
            # Limit GPU layers for low-VRAM cards (leaves room for KV cache + PyTorch residue)
            num_gpu = 99 if vram_free_mb > 6000 else (30 if vram_free_mb > 4000 else 18)

            # Build system prompt for JSON output (no "format": "json" — breaks Cyrillic)
            system_msg = "You are a professional subtitle translator. Always output valid JSON exactly as requested. Never add explanations outside the JSON."
            messages = [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt},
            ]

            models_to_try = ["gemma4:e4b"]
            for model_name in models_to_try:
                payload = json.dumps({
                    "model": model_name,
                    "messages": messages,
                    "stream": False,
                    "keep_alive": 300,
                    "options": {"temperature": 0.1, "num_predict": num_predict, "num_gpu": num_gpu}
                }).encode('utf-8')
                headers = {'Content-Type': 'application/json'}
                req = urllib.request.Request(url, data=payload, headers=headers)
                try:
                    with urllib.request.urlopen(req, timeout=300) as resp:
                        if resp.status == 200:
                            result = json.loads(resp.read().decode())
                            text = result.get("message", {}).get("content", "")
                            json_text = self._extract_json(text)
                            if json_text:
                                return json_text
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
            # Fallback to Ollama via /api/chat (proper template formatting for Gemma4)
            import urllib.request
            import urllib.error
            import json
            url = "http://localhost:11434/api/chat"
            for model_name in ["gemma4:e4b"]:
                payload = json.dumps({
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "keep_alive": 300,
                    "options": {"temperature": 0.1, "num_predict": 2048}
                }).encode('utf-8')
                headers = {'Content-Type': 'application/json'}
                req = urllib.request.Request(url, data=payload, headers=headers)
                try:
                    with urllib.request.urlopen(req, timeout=60) as response:
                        if response.status == 200:
                            result = json.loads(response.read().decode())
                            return result.get("message", {}).get("content", "")
                except Exception as e:
                    continue
            raise RuntimeError("All LLM fallbacks failed for smart JSON translation.")

    def _gemma4_refine(self, segments, target_lang, log_callback=None, check_cancelled=None):
        """Refine base translations (from DeepL or Google) using Gemma4 via Ollama."""
        import gc as _gc
        lang_names = {"ru": "Russian", "en": "English", "tr": "Turkish", "ar": "Arabic"}
        lang_name = lang_names.get(target_lang, target_lang)
        batch_size = 4
        total = len(segments)
        if log_callback: log_callback(f"🧠 Gemma4 улучшает перевод (батчи по {batch_size}, {total} сегментов)...")

        # VRAM cleanup
        try:
            import torch as _t
            _gc.collect()
            if _t.cuda.is_available():
                _t.cuda.empty_cache()
                _t.cuda.synchronize()
        except Exception: pass

        # Stop any existing Ollama models
        try:
            import subprocess as _sp
            _sp.run(["ollama", "stop", "gemma4:e4b"], capture_output=True, timeout=10)
        except Exception: pass
        import time as _time; _time.sleep(1.5)

        # Warmup
        if log_callback: log_callback("  ⏳ Прогрев Gemma4...")
        warmup_ok = False
        try:
            warmup_prompt = f"Say 'ready' in {lang_name}. One word only."
            warmup_response = self._call_llm(warmup_prompt, is_json=False)
            if warmup_response and len(warmup_response.strip()) > 0:
                warmup_ok = True
                if log_callback: log_callback("  ✅ Gemma4 загружен и готов")
        except Exception:
            if log_callback: log_callback("  ⚠ Gemma4 не отвечает — оставляю базовый перевод")
            for seg in segments:
                seg["text"] = seg.get("translated_base", seg["text"])
            self.release_models()
            return segments

        gemma4_failures = 0
        for batch_start in range(0, total, batch_size):
            batch_end = min(batch_start + batch_size, total)
            batch = segments[batch_start:batch_end]
            if gemma4_failures >= 3:
                for seg in batch: seg["text"] = seg.get("translated_base", seg["text"])
                continue

            dialogue = []
            for j, seg in enumerate(batch):
                idx = batch_start + j
                spk = seg.get("speaker", "SPEAKER_00")
                orig = seg["text"].strip()
                base = seg.get("translated_base", orig)
                dialogue.append(f"[{j}] {spk}\n    Original: {orig}\n    Draft: {base}")
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
            try:
                response = self._call_llm(prompt, is_json=True)
                import json as _json
                data = _json.loads(response)
                parsed = data.get("segments", [])
                gemma4_failures = 0
                if parsed and len(parsed) == len(batch):
                    for j, p_seg in enumerate(parsed):
                        new_text = p_seg.get("text", "").strip()
                        if new_text: batch[j]["text"] = new_text
                elif parsed:
                    for j in range(min(len(parsed), len(batch))):
                        new_text = parsed[j].get("text", "").strip()
                        if new_text: batch[j]["text"] = new_text
            except Exception as e:
                gemma4_failures += 1
                if log_callback: log_callback(f"  ⚠ Gemma4 batch failed ({gemma4_failures}/3): {str(e)[:80]}.")
                for seg in batch: seg["text"] = seg.get("translated_base", seg["text"])

        if log_callback: log_callback("✅ Перевод завершен (DeepL + Gemma4)!")
        self.release_models()
        return segments

    def release_models(self):
        import gc
        if "ollama" in self.engine_name.lower():
            import urllib.request
            import json
            url = "http://localhost:11434/api/generate"
            # Release the actual models used: gemma4:e4b (primary) + gemma2 fallbacks
            for model_name in ["gemma4:e4b", "gemma2:2b", "gemma2"]:
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

    def smart_translate_segments(self, segments, target_lang, log_callback=None, check_cancelled=None):
        is_ollama = "ollama" in self.engine_name.lower()
        is_deepl = "deepl" in self.engine_name.lower() and self.deepl_key
        is_ai_refine = is_ollama or (("gemini" in self.engine_name.lower() and self.gemini_key) or
                                      ("deepseek" in self.engine_name.lower() and self.deepseek_key))
        # Hybrid: DeepL base + Gemma4 refinement (if Ollama is running)
        gemma4_available = False
        if is_deepl:
            import urllib.request as _ur
            try:
                _ur.urlopen("http://localhost:11434/api/tags", timeout=2)
                gemma4_available = True
            except Exception:
                pass

        # ── Step 1: Fast base translation ──
        # DeepL: high-quality, paid API. Google Translate: free fallback for AI refinement engines.
        if is_deepl:
            if log_callback: log_callback(f"🌐 DeepL API - профессиональный перевод...")
            import urllib.request
            import urllib.error
            import json as _json
            deepl_errors = 0
            import urllib.error
            import json as _json

            is_free = self.deepl_key.endswith(':fx')
            url = "https://api-free.deepl.com/v2/translate" if is_free else "https://api.deepl.com/v2/translate"

            for seg in segments:
                if check_cancelled: check_cancelled()
                orig_text = seg["text"].strip()
                if not orig_text:
                    seg["translated_base"] = ""
                    continue
                try:
                    payload = _json.dumps({
                        "text": [orig_text],
                        "target_lang": target_lang.upper()
                    }).encode('utf-8')
                    headers = {
                        'Authorization': f'DeepL-Auth-Key {self.deepl_key}',
                        'Content-Type': 'application/json'
                    }
                    req = urllib.request.Request(url, data=payload, headers=headers)
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        if resp.status == 200:
                            result = _json.loads(resp.read().decode())
                            seg["translated_base"] = result["translations"][0]["text"].strip()
                        else:
                            raise Exception(f"HTTP {resp.status}")
                except Exception as e:
                    if log_callback: log_callback(f"  ⚠ DeepL failed for segment: {str(e)[:80]}. Falling back to Google.")
                    try:
                        seg["translated_base"] = GoogleTranslator(source='auto', target=target_lang).translate(orig_text)
                    except Exception:
                        seg["translated_base"] = orig_text
        else:
            if log_callback: log_callback(f"🌍 Google Translate - быстрый базовый перевод...")
            google_errors = 0
            for seg in segments:
                if check_cancelled: check_cancelled()
                orig_text = seg["text"].strip()
                if not orig_text:
                    seg["translated_base"] = ""
                    continue
                try:
                    seg["translated_base"] = GoogleTranslator(source='auto', target=target_lang).translate(orig_text)
                except Exception as e:
                    google_errors += 1
                    if log_callback and google_errors <= 2:
                        log_callback(f"  ⚠ Google Translate error: {str(e)[:100]}. Using original.")
                    seg["translated_base"] = orig_text  # fallback to original
            if google_errors > 0 and log_callback:
                log_callback(f"  ⚠ Google Translate failed for {google_errors}/{len(segments)} segments")

        # ── Step 2: AI refinement (Gemma4/Gemini/DeepSeek) ──
        if is_ollama:
            # Gemma4: refine Google Translate in small batches
            batch_size = 4  # Smaller batches = faster, less failure-prone
            total = len(segments)
            lang_names = {"ru": "Russian", "en": "English", "tr": "Turkish", "ar": "Arabic"}
            lang_name = lang_names.get(target_lang, target_lang)

            if log_callback:
                log_callback(f"🧠 Gemma4 улучшает перевод (батчи по {batch_size}, {total} сегментов)...")

            # ── VRAM cleanup: aggressively free GPU memory before loading Gemma4 ──
            try:
                import gc, torch
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    torch.cuda.synchronize()
                    torch.cuda.reset_peak_memory_stats()
                    free_mb = torch.cuda.mem_get_info()[0] / 1024**2
                    if log_callback:
                        log_callback(f"  🧹 VRAM очищена, свободно: {free_mb:.0f} MB")
            except Exception:
                pass

            # ── Force-stop ALL running Ollama models to free CUDA memory ──
            try:
                import subprocess as _sp
                _sp.run(["ollama", "stop", "gemma4:e4b"],
                    capture_output=True, timeout=10,
                    env=os.environ.copy())
            except Exception:
                pass
            import time as _time
            _time.sleep(1.5)  # Let CUDA fully release

            # ── Warmup: load Gemma4 into GPU once (60-120s), then stay via keep_alive ──
            if log_callback:
                log_callback("  ⏳ Прогрев Gemma4 (загрузка в GPU, до 5 мин)...")
            warmup_ok = False
            try:
                warmup_prompt = f"Say 'ready' in {lang_name}. One word only."
                warmup_response = self._call_llm(warmup_prompt, is_json=False)
                if warmup_response and len(warmup_response.strip()) > 0:
                    warmup_ok = True
                    if log_callback:
                        log_callback(f"  ✅ Gemma4 загружен и готов")
            except Exception:
                if log_callback:
                    log_callback(f"  ⚠ Gemma4 не отвечает — использую Google Translate для этого прогона")
                # Gemma4 is down; fall back to Google Translate base translation
                for seg in segments:
                    seg["text"] = seg.get("translated_base", seg["text"])
                self.release_models()
                return segments

            gemma4_failures = 0  # Circuit breaker (only for post-warmup batches)
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
                    # Fall back to Google Translate base for this batch
                    for seg in batch:
                        seg["text"] = seg.get("translated_base", seg["text"])
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

        # ── DeepL + Gemma4 hybrid refinement ──
        if is_deepl and gemma4_available:
            if log_callback: log_callback("🧠 DeepL + Gemma4 — улучшаю перевод...")
            return self._gemma4_refine(segments, target_lang, log_callback, check_cancelled)

        # ── Non-AI engines: just use base translation ──
        if not is_ai_refine:
            for seg in segments:
                seg["text"] = seg.get("translated_base", seg["text"])
            if log_callback: log_callback("✅ Перевод завершен!")
            self.release_models()
            return segments

        # ── Gemini/DeepSeek: batch refinement of Google Translate base ──
        if is_ai_refine and not is_ollama:
            lang_names = {"ru": "Russian", "en": "English", "tr": "Turkish", "ar": "Arabic",
                          "es": "Spanish", "fr": "French", "de": "German", "zh": "Chinese",
                          "ja": "Japanese", "ko": "Korean", "it": "Italian", "pt": "Portuguese",
                          "pl": "Polish", "hi": "Hindi"}
            lang_name = lang_names.get(target_lang, target_lang)

            batch_size = 5
            total_segments = len(segments)
            if log_callback: log_callback(f"🧠 {self.engine_name} улучшает перевод (батчи по {batch_size}, {total_segments} сегментов)...")

            for batch_start in range(0, total_segments, batch_size):
                batch_end = min(batch_start + batch_size, total_segments)
                batch = segments[batch_start:batch_end]

                if log_callback: log_callback(f"  -> Батч {batch_start + 1}-{batch_end} из {total_segments}...")

                # Build dialogue with original + draft translation
                dialogue = []
                for i, seg in enumerate(batch):
                    spk = seg.get("speaker", "SPEAKER_00")
                    orig = seg["text"].strip()
                    draft = seg.get("translated_base", orig)
                    dialogue.append(f"[{i}] {spk}\n    Original: {orig}\n    Draft: {draft}")

                full_text = "\n\n".join(dialogue)

                prompt = f"""You are an expert {lang_name} translator and localization editor.
Improve these subtitle draft translations to sound completely natural in {lang_name}.
Fix grammar, word choice, and conversational flow. Keep names/brands/tech terms unchanged.

CRITICAL RULES:
- Output a JSON object with a "segments" array
- Each segment: {{"text": "improved translation", "skip_dub": false}}
- If original is already in {lang_name}, copy it unchanged and set "skip_dub": true
- If the Draft is already perfect, copy it as-is

Dialogue:
{full_text}

JSON:"""

                try:
                    response_text = self._call_llm(prompt, is_json=True)
                    response_text = re.sub(r'```[a-z]*\n|```', '', response_text).strip()
                    data = json.loads(response_text)
                    parsed = data.get("segments", [])

                    if parsed and len(parsed) == len(batch):
                        for i, p_seg in enumerate(parsed):
                            new_text = p_seg.get("text", "").strip()
                            if new_text:
                                batch[i]["text"] = new_text
                            batch[i]["skip_dub"] = p_seg.get("skip_dub", False)
                    elif parsed:
                        if log_callback:
                            log_callback(f"  ⚠ Размер не совпал ({len(parsed)}/{len(batch)}), частичное слияние")
                        for i in range(min(len(parsed), len(batch))):
                            new_text = parsed[i].get("text", "").strip()
                            if new_text:
                                batch[i]["text"] = new_text

                except Exception as e:
                    if log_callback: log_callback(f"  ⚠ Батч не удался: {str(e)[:100]}. Оставляю базовый перевод.")
                    for seg in batch:
                        seg["text"] = seg.get("translated_base", seg["text"])

            if log_callback: log_callback("✅ Перевод завершен!")
            self.release_models()
            return segments
