"""Glossary CRUD API — manage custom translation term dictionaries."""
import json
import logging
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("autodub")
router = APIRouter(prefix="/api/glossaries", tags=["glossaries"])

GLOSSARIES_DIR = os.environ.get(
    "AUTODUB_GLOSSARIES",
    os.path.join(os.path.dirname(__file__), "data", "glossaries"),
)


def _ensure_dir():
    os.makedirs(GLOSSARIES_DIR, exist_ok=True)


class GlossaryItem(BaseModel):
    source: str
    target: str


class GlossaryCreate(BaseModel):
    name: str
    items: list[GlossaryItem]


class GlossaryGenerate(BaseModel):
    transcript: str = ""
    source_lang: str = "en"
    target_lang: str = "ru"


@router.get("/")
def list_glossaries():
    _ensure_dir()
    result = []
    try:
        for fname in os.listdir(GLOSSARIES_DIR):
            if fname.endswith(".json"):
                fpath = os.path.join(GLOSSARIES_DIR, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    result.append({
                        "id": fname.replace(".json", ""),
                        "name": data.get("name", fname),
                        "count": len(data.get("items", [])),
                    })
                except (json.JSONDecodeError, OSError):
                    pass
    except OSError:
        pass
    return {"glossaries": result}


@router.get("/{glossary_id}")
def get_glossary(glossary_id: str):
    _ensure_dir()
    fpath = os.path.join(GLOSSARIES_DIR, f"{glossary_id}.json")
    if not os.path.isfile(fpath):
        raise HTTPException(status_code=404, detail="Glossary not found")
    with open(fpath, "r", encoding="utf-8") as f:
        return json.load(f)


@router.post("/")
def create_glossary(body: GlossaryCreate):
    _ensure_dir()
    safe_name = "".join(c for c in body.name if c.isalnum() or c in " _-")[:64]
    fpath = os.path.join(GLOSSARIES_DIR, f"{safe_name}.json")
    data = {"name": body.name, "items": [i.model_dump() for i in body.items]}
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return {"status": "created", "id": safe_name}


@router.delete("/{glossary_id}")
def delete_glossary(glossary_id: str):
    fpath = os.path.join(GLOSSARIES_DIR, f"{glossary_id}.json")
    if not os.path.isfile(fpath):
        raise HTTPException(status_code=404, detail="Glossary not found")
    os.remove(fpath)
    return {"status": "deleted"}


@router.post("/generate")
def generate_glossary(body: GlossaryGenerate):
    """Use Gemini to auto-generate a glossary draft from a transcript."""
    if not body.transcript:
        raise HTTPException(status_code=400, detail="Transcript is required")

    # Try to use Gemma4 via Translator class
    try:
        from .translator import Translator

        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "config.json"
        )
        gemini_key = ""
        engine = "ollama"
        model = "gemma4:e4b"

        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                gemini_key = cfg.get("gemini_key", "")
                engine = cfg.get("translator_engine", "ollama")
                model = cfg.get("translator_model", "gemma4:e4b")

        # Create dummy segments from transcript for the Translator
        segments = [{"text": body.transcript[:10000]}]

        translator = Translator(
            engine_name=engine,
            gemini_key=gemini_key,
            translator_model=model,
            device="cuda"  # assume cuda
        )

        # Use our new generate_glossary method inside Translator
        raw_text = translator.generate_glossary(segments, target_lang=body.target_lang, max_terms=15)

        items = []
        if raw_text:
            for line in raw_text.split("\n"):
                if "=" in line:
                    parts = line.split("=", 1)
                    items.append({"source": parts[0].strip(), "target": parts[1].strip()})

        # Provide fallback if Gemma4 failed
        if not items and gemini_key:
            import google.genai as genai
            client = genai.Client(api_key=gemini_key)
            prompt = (
                f"You are a professional translator. Read the following transcript excerpt and "
                f"identify key terms, names, and specialized vocabulary that should be kept "
                f"consistent across translations from {body.source_lang} to {body.target_lang}.\n\n"
                f"Transcript:\n{body.transcript[:3000]}\n\n"
                f"Return a JSON object with an 'items' array. Each item has 'source' (original term) "
                f"and 'target' (recommended translation). Return ONLY valid JSON, no markdown."
            )
            response = client.models.generate_content(
                model="gemini-2.5-flash", contents=prompt
            )
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            data = json.loads(text)
            items = data.get("items", [])

        return {"items": items}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Glossary generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)[:200]}")
