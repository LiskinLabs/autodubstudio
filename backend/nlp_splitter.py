import logging
from typing import Dict, List

import spacy

logger = logging.getLogger(__name__)

# Cache loaded models so we don't reload them for every file
_loaded_models = {}


def get_spacy_model(language_code: str):
    """
    Returns the appropriate spacy model for the given language.
    Falls back to 'en_core_web_sm' or returns None if we want to skip.
    """
    if language_code in _loaded_models:
        return _loaded_models[language_code]

    # Map whisper lang code to Spacy models
    model_map = {
        "en": "en_core_web_sm",
        "ru": "ru_core_news_sm",
    }

    model_name = model_map.get(language_code, "en_core_web_sm")
    try:
        nlp = spacy.load(model_name)
    except OSError:
        logger.warning(
            f"Spacy model {model_name} not found. Falling back to en_core_web_sm."
        )
        try:
            nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.error("No Spacy models installed. NLP splitting disabled.")
            return None

    _loaded_models[language_code] = nlp
    return nlp


def split_segments_by_meaning(segments: List[Dict], language_code: str) -> List[Dict]:
    """
    Takes Whisper segments and splits them into logical sentences using Spacy NLP.
    Interpolates start/end times based on character length.
    """
    nlp = get_spacy_model(language_code)
    if not nlp:
        return segments  # Return unmodified if spacy is totally unavailable

    new_segments = []

    for seg in segments:
        text = seg["text"].strip()
        if not text:
            continue

        doc = nlp(text)

        # If there's only 1 sentence, don't split
        sentences = [sent.text.strip() for sent in doc.sents if sent.text.strip()]

        if len(sentences) <= 1:
            new_segments.append(seg)
            continue

        # We have multiple sentences in this segment, let's split it!
        total_chars = sum(
            len(s) for s in sentences
        )  # use sum of sent lengths to be perfectly accurate to ratio
        current_start = seg["start"]
        seg_duration = seg["end"] - seg["start"]

        for sent in sentences:
            sent_len = len(sent)
            # Calculate proportion of time
            ratio = sent_len / max(1, total_chars)

            sent_duration = seg_duration * ratio
            sent_end = current_start + sent_duration

            new_seg = {
                "start": current_start,
                "end": sent_end,
                "text": sent,
                "speaker": seg.get("speaker", "SPEAKER_00"),
            }
            new_segments.append(new_seg)

            current_start = sent_end

    return new_segments
