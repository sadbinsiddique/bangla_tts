"""
@Author : Sad Bin Siddique
@Email : sadbinsiddique@gmail.com
"""
import time
import sys
import os
import asyncio
import requests
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, Literal, Optional, Tuple
from uuid import uuid4

vendor_tts_path = Path(__file__).parent / "vendor_tts"
if vendor_tts_path.is_dir() and str(vendor_tts_path) not in sys.path:
    sys.path.insert(0, str(vendor_tts_path))

import soundfile as sf
from fastapi import FastAPI, HTTPException  # pyright: ignore[reportMissingImports]
from fastapi.middleware.cors import CORSMiddleware  # pyright: ignore[reportMissingImports]
from fastapi.responses import FileResponse  # pyright: ignore[reportMissingImports]
from fastapi.staticfiles import StaticFiles  # pyright: ignore[reportMissingImports]
from pydantic import BaseModel, Field  # pyright: ignore[reportMissingImports]

from pipeline import bangla_tts, model_loading


class TTSRequest(BaseModel):
    text: str = Field(min_length=1)
    save_dir: str = Field(default="output")
    gender: Literal["female", "male"] = Field(default="female")


class TTSResponse(BaseModel):
    audio_url: str
    gender: str
    status: int
    processing_time: float


class TalkRequest(BaseModel):
    provider: Literal["chatgpt", "deepseek", "gemini", "grok"]
    prompt: str = Field(min_length=1, max_length=160)
    model: Optional[str] = Field(default=None)
    system_prompt: str = Field(default="You are a helpful assistant. Respond only in Bangla. Keep the answer short.")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    save_dir: str = Field(default="output")
    gender: Literal["female", "male"] = Field(default="female")


class TalkResponse(BaseModel):
    provider: str
    model: str
    prompt: str
    assistant_text: str
    audio_url: str
    gender: str
    status: int
    processing_time: float


def _synthesize_and_save(tts_model, text: str, audio_path: Path, is_male: bool = False) -> None:
    # Use is_male flag to select voice if the model supports it
    audio = bangla_tts(model=tts_model, text=text, is_male=is_male, is_e2e_vits=True, log_dir=str(audio_path))
    sf.write(audio_path, audio, 22050)


def _is_bangla_text(text: str) -> bool:
    if not text:
        return False
    # Count Bangla and Latin letters; require majority Bangla
    bangla_chars_count = len(re.findall(r"[\u0980-\u09FF]", text))
    latin_chars_count = len(re.findall(r"[A-Za-z]", text))
    total_letters = bangla_chars_count + latin_chars_count
    if total_letters == 0:
        # No Bangla/Latin letters found — fail
        return False
    ratio = bangla_chars_count / total_letters
    # Require majority Bangla and no Latin letters
    return ratio >= 0.6 and latin_chars_count == 0


def _validate_bangla_prompt(prompt: str, max_len: int = 160) -> str:
    cleaned_prompt = prompt.strip()
    if not cleaned_prompt:
        raise HTTPException(status_code=400, detail="prompt is required")
    if len(cleaned_prompt) > max_len:
        raise HTTPException(status_code=400, detail=f"prompt must be {max_len} characters or fewer")
    if not _is_bangla_text(cleaned_prompt):
        raise HTTPException(status_code=400, detail="prompt must be written in Bangla only")
    return cleaned_prompt


def _validate_bangla_output(text: str, max_len: int = 400) -> str:
    cleaned_text = text.strip()
    if not cleaned_text:
        raise ValueError("Provider returned empty text")
    if len(cleaned_text) > max_len:
        raise ValueError(f"Provider response too long (>{max_len} chars)")
    if not _is_bangla_text(cleaned_text):
        raise ValueError("Provider response must be in Bangla only")
    return cleaned_text


def _resolve_provider_config(provider: str, model: Optional[str]) -> Tuple[str, str, str]:
    provider = provider.lower().strip()
    if provider == "chatgpt":
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        return api_key, "https://api.openai.com/v1/chat/completions", model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if provider == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        return api_key, "https://api.deepseek.com/chat/completions", model or os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    if provider == "grok":
        api_key = os.getenv("XAI_API_KEY", "").strip()
        return api_key, "https://api.x.ai/v1/chat/completions", model or os.getenv("XAI_MODEL", "grok-2-latest")
    if provider == "gemini":
        api_key = os.getenv("GOOGLE_API_KEY", "").strip()
        return api_key, "https://generativelanguage.googleapis.com/v1beta/models", model or os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    raise ValueError("Unsupported provider. Use one of: chatgpt, deepseek, gemini, grok")


def _call_openai_compatible_chat(*, endpoint: str, api_key: str, model: str, prompt: str, system_prompt: str, temperature: float) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
    }
    response = requests.post(endpoint, headers=headers, json=payload, timeout=90)
    response.raise_for_status()
    data = response.json()

    choices = data.get("choices", [])
    if not choices:
        raise ValueError("No response choices returned from provider")
    message = choices[0].get("message", {})
    content = message.get("content", "")
    if not content:
        raise ValueError("Empty response content returned from provider")
    return str(content)


def _call_gemini_chat(*, base_endpoint: str, api_key: str, model: str, prompt: str, system_prompt: str, temperature: float) -> str:
    endpoint = f"{base_endpoint}/{model}:generateContent?key={api_key}"
    payload = {
        "system_instruction": {
            "parts": [{"text": system_prompt}],
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "temperature": temperature,
        },
    }
    response = requests.post(endpoint, json=payload, timeout=90)
    response.raise_for_status()
    data = response.json()

    candidates = data.get("candidates", [])
    if not candidates:
        raise ValueError("No Gemini candidates returned")
    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts:
        raise ValueError("No Gemini content parts returned")
    text = parts[0].get("text", "")
    if not text:
        raise ValueError("Empty Gemini response text")
    return str(text)


def _generate_ai_text(
    provider: str,
    prompt: str,
    model: Optional[str],
    system_prompt: str,
    temperature: float,
) -> Tuple[str, str]:
    api_key, endpoint, resolved_model = _resolve_provider_config(provider, model)
    if not api_key:
        raise ValueError(f"Missing API key for provider '{provider}'. Set corresponding environment variable.")

    if provider == "gemini":
        text = _call_gemini_chat(
            base_endpoint=endpoint,
            api_key=api_key,
            model=resolved_model,
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
        )
        return _validate_bangla_output(text), resolved_model

    text = _call_openai_compatible_chat(
        endpoint=endpoint,
        api_key=api_key,
        model=resolved_model,
        prompt=prompt,
        system_prompt=system_prompt,
        temperature=temperature,
    )
    return _validate_bangla_output(text), resolved_model


async def _get_or_load_model(app_instance: FastAPI, gender: str):
    models: Dict[str, object] = getattr(app_instance.state, "tts_models", {})
    model = models.get(gender)
    if model is not None:
        return model

    lock: asyncio.Lock = app_instance.state.tts_model_lock
    async with lock:
        model = app_instance.state.tts_models.get(gender)
        if model is not None:
            return model

        loaded_model = await asyncio.to_thread(model_loading, None, None, gender)
        app_instance.state.tts_models[gender] = loaded_model
        return loaded_model


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    preload_gender = os.getenv("DEFAULT_GENDER", "female").strip().lower()
    if preload_gender not in {"female", "male"}:
        preload_gender = "female"

    app_instance.state.tts_models = {}
    app_instance.state.tts_model_lock = asyncio.Lock()

    app_instance.state.tts_models[preload_gender] = await asyncio.to_thread(model_loading, None, None, preload_gender)

    max_concurrency = int(os.getenv("TTS_MAX_CONCURRENCY", "1"))
    app_instance.state.tts_max_concurrency = max_concurrency
    app_instance.state.tts_preload_gender = preload_gender
    app_instance.state.tts_semaphore = asyncio.Semaphore(max_concurrency)
    yield


app = FastAPI(title="Bangla TTS API", version="1.0.0", lifespan=lifespan)
frontend_dir = Path(__file__).parent / "frontend"
frontend_dir.mkdir(parents=True, exist_ok=True)
output_root_dir = Path(__file__).parent / "output"
output_root_dir.mkdir(parents=True, exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def frontend() -> FileResponse:
    return FileResponse(frontend_dir / "index.html")


@app.get("/health")
def health_check() -> dict:
    max_concurrency = getattr(app.state, "tts_max_concurrency", None)
    loaded_genders = sorted(list(getattr(app.state, "tts_models", {}).keys()))
    return {
        "status": "ok",
        "service": "bangla-tts",
        "model_loaded": len(loaded_genders) > 0,
        "loaded_genders": loaded_genders,
        "preload_gender": getattr(app.state, "tts_preload_gender", None),
        "max_concurrency": max_concurrency,
    }


@app.post("/tts", response_model=TTSResponse)
async def process_text(payload: TTSRequest) -> TTSResponse:
    if payload.gender not in {"female", "male"}:
        raise HTTPException(status_code=400, detail="gender must be 'female' or 'male'")

    start_time = time.time()
    output_dir = Path(payload.save_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    file_name = f"bangla_tts_{payload.gender}_{uuid4().hex}.wav"
    audio_path = output_dir / file_name

    semaphore = getattr(app.state, "tts_semaphore", None)
    if semaphore is None:
        raise HTTPException(status_code=503, detail="TTS semaphore is not initialized")

    async with semaphore:
        tts_model = await _get_or_load_model(app, payload.gender)
        is_male = payload.gender == "male"
        await asyncio.to_thread(_synthesize_and_save, tts_model, payload.text, audio_path, is_male)

    return TTSResponse(
        audio_url=f"/{audio_path.as_posix()}",
        gender=payload.gender,
        status=200,
        processing_time=time.time() - start_time,
    )


@app.post("/talk", response_model=TalkResponse)
async def talk_and_speak(payload: TalkRequest) -> TalkResponse:
    start_time = time.time()
    prompt = _validate_bangla_prompt(payload.prompt)
    output_dir = Path(payload.save_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    file_name = f"talk_{payload.provider}_{payload.gender}_{uuid4().hex}.wav"
    audio_path = output_dir / file_name

    semaphore = getattr(app.state, "tts_semaphore", None)
    if semaphore is None:
        raise HTTPException(status_code=503, detail="TTS semaphore is not initialized")

    try:
        assistant_text, resolved_model = await asyncio.to_thread(
            _generate_ai_text,
            payload.provider,
            prompt,
            payload.model,
            payload.system_prompt,
            payload.temperature,
        )
    except requests.HTTPError as exc:
        resp = exc.response
        if resp is None:
            raise HTTPException(status_code=502, detail="Provider API error: no response") from exc
        # try to parse provider JSON error
        try:
            err_json = resp.json()
        except Exception:
            err_text = resp.text
            raise HTTPException(status_code=502, detail=f"Provider API error: {err_text}") from exc

        err_obj = err_json.get("error", err_json) if isinstance(err_json, dict) else err_json
        code = None
        message = str(err_obj)
        if isinstance(err_obj, dict):
            code = err_obj.get("code") or err_obj.get("type") or err_obj.get("status")
            message = err_obj.get("message") or message

        # Map common provider failures to clear HTTP codes/messages
        lc_code = str(code).lower() if code is not None else ""
        if resp.status_code == 401 or "invalid" in lc_code or "unauthorized" in lc_code:
            raise HTTPException(status_code=401, detail=f"{payload.provider} authentication failed: {message}") from exc
        if "quota" in lc_code or "insufficient" in lc_code or resp.status_code == 402:
            raise HTTPException(status_code=402, detail=f"{payload.provider} quota exceeded: {message}") from exc
        if resp.status_code == 429:
            raise HTTPException(status_code=429, detail=f"{payload.provider} rate limited: {message}") from exc

        # fallback provider error
        raise HTTPException(status_code=502, detail=f"{payload.provider} provider error: {message}") from exc
    except ValueError as exc:
        msg = str(exc)
        if msg.startswith("Missing API key"):
            raise HTTPException(status_code=401, detail=msg) from exc
        raise HTTPException(status_code=400, detail=msg) from exc

    async with semaphore:
        tts_model = await _get_or_load_model(app, payload.gender)
        is_male = payload.gender == "male"
        await asyncio.to_thread(_synthesize_and_save, tts_model, assistant_text, audio_path, is_male)

    return TalkResponse(
        provider=payload.provider,
        model=resolved_model,
        prompt=prompt,
        assistant_text=assistant_text,
        audio_url=f"/{audio_path.as_posix()}",
        gender=payload.gender,
        status=200,
        processing_time=time.time() - start_time,
    )


app.mount("/frontend", StaticFiles(directory=frontend_dir), name="frontend")
app.mount("/output", StaticFiles(directory=output_root_dir), name="output")


if __name__ == "__main__":
    import uvicorn  # pyright: ignore[reportMissingImports]

    host = os.getenv("API_HOST", "192.168.0.1")
    port = int(os.getenv("API_PORT", "3000"))
    uvicorn.run("app:app", host=host, port=port, reload=False)