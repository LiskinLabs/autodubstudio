import logging
from typing import Dict, List

import spacy

logger = logging.getLogger(__name__)

# Cache loaded models so we don't reload them for every file
_loaded_models = {}

# Map whisper/lang codes to Spacy models
_MODEL_MAP = {
    "en": "en_core_web_sm",
    "ru": "ru_core_news_sm",
    "es": "es_core_news_sm",
    "de": "de_core_news_sm",
    "fr": "fr_core_news_sm",
    "it": "it_core_news_sm",
    "pt": "pt_core_news_sm",
    "tr": "xx_ent_wiki_sm",     # Turkish: multi-language model (no dedicated TR model)
    "ar": "xx_ent_wiki_sm",     # Arabic: multi-language model
    "zh": "xx_ent_wiki_sm",     # Chinese: multi-language model
    "ja": "xx_ent_wiki_sm",     # Japanese: multi-language model
    "ko": "xx_ent_wiki_sm",     # Korean: multi-language model
    "pl": "xx_ent_wiki_sm",     # Polish: multi-language model
    "hi": "xx_ent_wiki_sm",     # Hindi: multi-language model
}

# Languages for which we have dedicated sentence segmentation models
_HAS_DEDICATED_MODEL = {"en", "ru", "es", "de", "fr", "it", "pt"}


def get_spacy_model(language_code: str):
    """
    Returns the appropriate spacy model for the given language.
    Falls back to 'en_core_web_sm' or multi-language model.
    """
    if not language_code:
        language_code = "en"

    lang = language_code[:2].lower()

    if lang in _loaded_models:
        return _loaded_models[lang]

    model_name = _MODEL_MAP.get(lang, "xx_ent_wiki_sm")
    try:
        nlp = spacy.load(model_name)
    except OSError:
        # Fallback chain: dedicated → multi → english
        for fallback in ["xx_ent_wiki_sm", "en_core_web_sm"]:
            if fallback == model_name:
                continue
            try:
                nlp = spacy.load(fallback)
                model_name = fallback
                break
            except OSError:
                continue
        else:
            logger.error("No Spacy models installed. NLP splitting disabled.")
            return None

    _loaded_models[lang] = nlp
    return nlp


def split_segments_by_meaning(
    segments: List[Dict], language_code: str
) -> List[Dict]:
    """
    Takes Whisper segments and splits them into logical sentences using Spacy NLP.

    Uses per-segment language (seg['language']) when available, falling back
    to the global language_code. This is critical for bilingual videos where
    different segments may be in different languages.
    """
    new_segments = []

    for seg in segments:
        text = seg["text"].strip()
        if not text:
            continue

        # Use per-segment language if available, otherwise fall back to global
        seg_lang = seg.get("language", language_code)
        nlp = get_spacy_model(seg_lang)
        if not nlp:
            new_segments.append(seg)
            continue

        doc = nlp(text)

        # If there's only 1 sentence, don't split
        sentences = [sent.text.strip() for sent in doc.sents if sent.text.strip()]

        if len(sentences) <= 1:
            new_segments.append(seg)
            continue

        # We have multiple sentences in this segment, let's split it!
        total_chars = sum(len(s) for s in sentences)
        current_start = seg["start"]
        seg_duration = seg["end"] - seg["start"]

        for sent in sentences:
            sent_len = len(sent)
            ratio = sent_len / max(1, total_chars)
            sent_duration = seg_duration * ratio
            sent_end = current_start + sent_duration

            new_seg = seg.copy()
            new_seg.update(
                {
                    "start": current_start,
                    "end": sent_end,
                    "text": sent,
                    "speaker": seg.get("speaker", "SPEAKER_00"),
                }
            )
            new_segments.append(new_seg)
            current_start = sent_end

    return new_segments
