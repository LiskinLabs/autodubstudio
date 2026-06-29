with open("engine.py", "r", encoding="utf-8") as f:
    code = f.read()

old_edge_init = """                    import edge_tts
                    EDGE_VOICES = {
                        "ru": "ru-RU-DmitryNeural", "en": "en-US-ChristopherNeural",
                        "tr": "tr-TR-AhmetNeural",  "ar": "ar-SA-HamedNeural",
                        "es": "es-ES-AlvaroNeural",  "fr": "fr-FR-HenriNeural",
                        "de": "de-DE-ConradNeural",  "zh": "zh-CN-YunxiNeural",
                        "ja": "ja-JP-KeitaNeural",   "ko": "ko-KR-InJoonNeural",
                        "it": "it-IT-DiegoNeural",   "pt": "pt-PT-DuarteNeural",
                        "pl": "pl-PL-MarekNeural",   "hi": "hi-IN-MadhurNeural",
                    }
                    voice = EDGE_VOICES.get(lang, "en-US-ChristopherNeural")"""

new_edge_init = """                    import edge_tts
                    EDGE_VOICES_MALE = {
                        "ru": "ru-RU-DmitryNeural", "en": "en-US-ChristopherNeural",
                        "tr": "tr-TR-AhmetNeural",  "ar": "ar-SA-HamedNeural",
                        "es": "es-ES-AlvaroNeural",  "fr": "fr-FR-HenriNeural",
                        "de": "de-DE-ConradNeural",  "zh": "zh-CN-YunxiNeural",
                        "ja": "ja-JP-KeitaNeural",   "ko": "ko-KR-InJoonNeural",
                        "it": "it-IT-DiegoNeural",   "pt": "pt-PT-DuarteNeural",
                        "pl": "pl-PL-MarekNeural",   "hi": "hi-IN-MadhurNeural",
                    }
                    EDGE_VOICES_FEMALE = {
                        "ru": "ru-RU-SvetlanaNeural", "en": "en-US-AriaNeural",
                        "tr": "tr-TR-EmelNeural",  "ar": "ar-SA-ZariyahNeural",
                        "es": "es-ES-ElviraNeural",  "fr": "fr-FR-DeniseNeural",
                        "de": "de-DE-AmalaNeural",  "zh": "zh-CN-XiaoxiaoNeural",
                        "ja": "ja-JP-NanamiNeural",   "ko": "ko-KR-SunHiNeural",
                        "it": "it-IT-ElsaNeural",   "pt": "pt-PT-RaquelNeural",
                        "pl": "pl-PL-AgnieszkaNeural",   "hi": "hi-IN-SwaraNeural",
                    }"""

old_group_logic = """                        groups = []  # [(group_segments, combined_text)]
                        cur_group = []
                        cur_chars = 0
                        MAX_SEGMENTS = 6     # Max segments per TTS group
                        MAX_CHARS = 400       # Max total characters per group (~30 sec of speech)

                        for _, tseg, clip_path in tts_segments:
                            seg_chars = len(tseg["text"].strip())
                            # Force break if adding this segment would exceed limits
                            if cur_group and (
                                len(cur_group) >= MAX_SEGMENTS or
                                cur_chars + seg_chars > MAX_CHARS
                            ):
                                groups.append(cur_group)
                                cur_group = []
                                cur_chars = 0
                            cur_group.append((tseg, clip_path))
                            cur_chars += seg_chars
                            # Natural break at sentence end
                            if _ends_sentence(tseg["text"]):
                                groups.append(cur_group)
                                cur_group = []
                                cur_chars = 0
                        if cur_group:
                            if groups:
                                groups[-1].extend(cur_group)
                            else:
                                groups.append(cur_group)

                        async def gen_all_groups():
                            for gi, group in enumerate(groups):
                                parts = []
                                for tseg, _ in group:
                                    t = tseg["text"].strip()
                                    if t and not _ends_sentence(t) and t[-1] not in {'.', '!', '?', ' ', '?'}:
                                        t += '. '  # Force sentence break for TTS naturalness
                                    parts.append(t)
                                group_text = ' '.join(parts)
                                group_path = os.path.join(self.out_dir, f"temp_{lang}_group{gi}.mp3")
                                all_created_files.append(group_path)
                                self.log_signal.emit(_pipeline_t("tts_group_progress", self.ui_language, gi=gi+1, total=len(groups), n=len(group), chars=len(group_text)))
                                await edge_tts.Communicate(group_text, voice).save(group_path)
                                # Split back to segments"""

new_group_logic = """                        groups = []  # [(grp_voice, cur_group)]
                        cur_group = []
                        cur_chars = 0
                        cur_voice = None
                        MAX_SEGMENTS = 6     # Max segments per TTS group
                        MAX_CHARS = 400       # Max total characters per group (~30 sec of speech)

                        speaker_genders = {}
                        for _, tseg, _ in tts_segments:
                            spk = tseg.get("speaker", "SPEAKER_00")
                            g = tseg.get("gender", "unknown")
                            if g in ["male", "female"]:
                                if spk not in speaker_genders: speaker_genders[spk] = []
                                speaker_genders[spk].append(g)
                        
                        final_speaker_gender = {}
                        for spk, genders in speaker_genders.items():
                            if genders:
                                final_speaker_gender[spk] = max(set(genders), key=genders.count)
                            else:
                                final_speaker_gender[spk] = "male"

                        for _, tseg, clip_path in tts_segments:
                            seg_chars = len(tseg["text"].strip())
                            spk = tseg.get("speaker", "SPEAKER_00")
                            spk_gender = final_speaker_gender.get(spk, "male")
                            voice_to_use = EDGE_VOICES_FEMALE.get(lang, "en-US-AriaNeural") if spk_gender == "female" else EDGE_VOICES_MALE.get(lang, "en-US-ChristopherNeural")
                            
                            if cur_voice is None:
                                cur_voice = voice_to_use

                            # Force break if exceeding limits OR voice changes
                            if cur_group and (
                                len(cur_group) >= MAX_SEGMENTS or
                                cur_chars + seg_chars > MAX_CHARS or
                                cur_voice != voice_to_use
                            ):
                                groups.append((cur_voice, cur_group))
                                cur_group = []
                                cur_chars = 0
                                cur_voice = voice_to_use

                            cur_group.append((tseg, clip_path))
                            cur_chars += seg_chars
                            # Natural break at sentence end
                            if _ends_sentence(tseg["text"]):
                                groups.append((cur_voice, cur_group))
                                cur_group = []
                                cur_chars = 0
                                cur_voice = None
                        
                        if cur_group:
                            groups.append((cur_voice, cur_group))

                        async def gen_all_groups():
                            for gi, (grp_voice, group) in enumerate(groups):
                                parts = []
                                for tseg, _ in group:
                                    t = tseg["text"].strip()
                                    if t and not _ends_sentence(t) and t[-1] not in {'.', '!', '?', ' ', '?'}:
                                        t += '. '  # Force sentence break for TTS naturalness
                                    parts.append(t)
                                group_text = ' '.join(parts)
                                group_path = os.path.join(self.out_dir, f"temp_{lang}_group{gi}.mp3")
                                all_created_files.append(group_path)
                                self.log_signal.emit(_pipeline_t("tts_group_progress", self.ui_language, gi=gi+1, total=len(groups), n=len(group), chars=len(group_text)))
                                await edge_tts.Communicate(group_text, grp_voice).save(group_path)
                                # Split back to segments"""  # noqa: W293

code = code.replace(old_edge_init, new_edge_init)
code = code.replace(old_group_logic, new_group_logic)

with open("engine.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Patch applied!")
