"""Scenario-driven IELTS study system powered by Gemini for OCR and material generation."""
from __future__ import annotations

import base64
import binascii
import io
import json
import os
import re
import uuid
from collections import OrderedDict
from copy import deepcopy
from threading import Lock
from typing import Dict, Iterable, List, Optional, Tuple
import wave

import requests
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from PIL import Image, UnidentifiedImageError


router = APIRouter(prefix="/ielts", tags=["IELTS Study System"])


class OCRUnavailableError(Exception):
    """Raised when OCR resources are missing or cannot be initialised."""


class TTSSynthesizer:
    """Gemini powered Text-To-Speech helper."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._voice_name = os.environ.get("IELTS_TTS_VOICE", "aoede")
        self._request_mime_type = os.environ.get("IELTS_TTS_MIME_TYPE", "audio/pcm")
        self._mime_type = self._request_mime_type
        self._model = (
            os.environ.get("IELTS_TTS_MODEL")
            or os.environ.get("IELTS_GEMINI_MODEL")
            or "gemini-1.5-flash"
        )
        self.available = bool(os.environ.get("GEMINI_API_KEY"))
        self._success_note = "音频由 Gemini TTS 生成。"

    def synthesize(self, text: str) -> Tuple[Optional[str], str]:
        """Convert text into base64 encoded audio via Gemini."""

        cleaned = text.strip()
        if not cleaned:
            return None, "听力脚本为空，已回退为文本内容。"
        if not self.available:
            return None, "服务器未配置 GEMINI_API_KEY，暂时无法生成音频。"

        try:
            with self._lock:
                audio_b64, resolved_mime = _call_gemini_tts(
                    cleaned,
                    model=self._model,
                    mime_type=self._request_mime_type,
                    voice_name=self._voice_name,
                )
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
            return None, f"Gemini TTS 调用失败：{detail}"
        except Exception as exc:  # pragma: no cover - defensive
            return None, f"Gemini TTS 生成异常：{exc}"

        if audio_b64:
            if resolved_mime:
                self._mime_type = resolved_mime
            else:
                self._mime_type = "audio/wav"
            return audio_b64, self._success_note
        return None, "Gemini TTS 未返回音频，已提供文本脚本。"

    @property
    def mime_type(self) -> str:
        return self._mime_type


class SessionManager:
    """Thread-safe in-memory store for generated sessions."""

    def __init__(self) -> None:
        self._sessions: Dict[str, Dict[str, object]] = {}
        self._lock = Lock()

    def save(self, session_id: str, payload: Dict[str, object]) -> None:
        with self._lock:
            self._sessions[session_id] = payload

    def get(self, session_id: str) -> Dict[str, object]:
        with self._lock:
            if session_id not in self._sessions:
                raise HTTPException(status_code=404, detail="学习会话不存在，请重新上传材料。")
            return deepcopy(self._sessions[session_id])


SESSION_STORE = SessionManager()
TTS_SYNTHESIZER = TTSSynthesizer()
DEFAULT_GEMINI_MODEL = os.environ.get("IELTS_GEMINI_MODEL", "gemini-1.5-flash")
_GEMINI_SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

_DEFAULT_PCM_SAMPLE_RATE = 24000
_DEFAULT_PCM_CHANNELS = 1
_DEFAULT_PCM_SAMPLE_WIDTH = 2
_PCM_MIME_HINTS = {
    "audio/pcm",
    "audio/x-raw",
    "audio/raw",
    "audio/basic",
    "audio/l16",
    "linear16",
}
_WAV_MIME_ALIASES = {"audio/wave", "audio/x-wav"}
_MP3_MIME_ALIASES = {"audio/mp3"}
_AUDIO_RATE_KEYS = [
    "sampleRateHz",
    "sampleRateHertz",
    "sample_rate_hz",
    "sample_rate",
    "sample_rate_hertz",
    "samplesPerSecond",
    "samples_per_second",
    "samplingRate",
    "sampling_rate",
    "sampling_rate_hz",
]
_AUDIO_CHANNEL_KEYS = [
    "channels",
    "channelCount",
    "channelsCount",
    "numChannels",
    "channel_count",
]
_AUDIO_WIDTH_KEYS = [
    "bitsPerSample",
    "bits_per_sample",
    "bitDepth",
    "sampleWidth",
    "sample_width",
    "bytesPerSample",
    "bytes_per_sample",
]


def _normalise_mime_hint(mime_hint: Optional[str]) -> Optional[str]:
    if not mime_hint:
        return None
    value = str(mime_hint).strip()
    if not value:
        return None
    base = value.split(";", 1)[0].strip().lower()
    if base == "audio/wav" or base in _WAV_MIME_ALIASES:
        return "audio/wav"
    if base == "audio/mpeg" or base in _MP3_MIME_ALIASES:
        return "audio/mpeg"
    if base in _PCM_MIME_HINTS:
        return "audio/pcm"
    return base


def _iter_audio_metadata_dicts(source: Optional[Dict[str, object]]):
    if not isinstance(source, dict):
        return
    queue: List[Dict[str, object]] = [source]
    seen: set[int] = set()
    while queue:
        current = queue.pop(0)
        identifier = id(current)
        if identifier in seen:
            continue
        seen.add(identifier)
        yield current
        for key in ("audioFormat", "audio_format", "config", "audioConfig", "format", "metadata"):
            nested = current.get(key)
            if isinstance(nested, dict):
                queue.append(nested)


def _resolve_audio_parameters(
    mime_hint: Optional[str], metadata: Optional[Dict[str, object]]
) -> Tuple[int, int, int]:
    sample_rate = _DEFAULT_PCM_SAMPLE_RATE
    channels = _DEFAULT_PCM_CHANNELS
    sample_width = _DEFAULT_PCM_SAMPLE_WIDTH

    if mime_hint:
        for token in str(mime_hint).split(";"):
            candidate = token.strip()
            if not candidate or "=" not in candidate:
                continue
            key, value = candidate.split("=", 1)
            key = key.strip().lower()
            value = value.strip()
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                continue
            if parsed <= 0:
                continue
            if key in {"rate", "samplerate", "sample_rate"}:
                sample_rate = parsed
            elif key in {"channels", "channel"}:
                channels = max(1, parsed)
            elif key in {"width", "samplewidth", "bytes_per_sample"}:
                sample_width = max(1, parsed)

    rate_found = False
    channel_found = False
    width_found = False
    for candidate in _iter_audio_metadata_dicts(metadata):
        if not rate_found:
            for key in _AUDIO_RATE_KEYS:
                if key in candidate:
                    try:
                        rate_value = int(candidate[key])
                    except (TypeError, ValueError):
                        continue
                    if rate_value > 0:
                        sample_rate = rate_value
                        rate_found = True
                        break
        if not channel_found:
            for key in _AUDIO_CHANNEL_KEYS:
                if key in candidate:
                    try:
                        channel_value = int(candidate[key])
                    except (TypeError, ValueError):
                        continue
                    if channel_value > 0:
                        channels = max(1, channel_value)
                        channel_found = True
                        break
        if not width_found:
            for key in _AUDIO_WIDTH_KEYS:
                if key in candidate:
                    try:
                        width_value = int(candidate[key])
                    except (TypeError, ValueError):
                        continue
                    if width_value <= 0:
                        continue
                    if "bit" in key.lower():
                        sample_width = max(1, width_value // 8 or 1)
                    else:
                        sample_width = max(1, width_value)
                    width_found = True
                    break
        if rate_found and channel_found and width_found:
            break

    return sample_rate, channels, sample_width


def _pcm_to_wav_bytes(
    pcm_bytes: bytes,
    *,
    sample_rate: int,
    channels: int,
    sample_width: int,
) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(max(1, channels))
        wav_file.setsampwidth(max(1, sample_width))
        wav_file.setframerate(max(1, sample_rate))
        wav_file.writeframes(pcm_bytes)
    return buffer.getvalue()


def _ensure_base64_text(value: object) -> str:
    if isinstance(value, (bytes, bytearray)):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return base64.b64encode(value).decode("utf-8")
    return str(value)


def _normalise_audio_payload(
    raw_data: object,
    raw_mime_type: Optional[str],
    requested_mime_type: Optional[str],
    metadata: Optional[Dict[str, object]] = None,
) -> Tuple[str, str]:
    base64_text = _ensure_base64_text(raw_data)
    normalised_raw = _normalise_mime_hint(raw_mime_type)
    normalised_requested = _normalise_mime_hint(requested_mime_type)
    resolved_hint = normalised_raw or normalised_requested

    if resolved_hint in _PCM_MIME_HINTS or (resolved_hint and "pcm" in resolved_hint):
        sample_rate, channels, sample_width = _resolve_audio_parameters(raw_mime_type, metadata)
        try:
            pcm_bytes = base64.b64decode(base64_text)
        except (binascii.Error, ValueError):
            return base64_text, normalised_requested or "audio/pcm"
        wav_bytes = _pcm_to_wav_bytes(
            pcm_bytes,
            sample_rate=sample_rate,
            channels=channels,
            sample_width=sample_width,
        )
        wav_b64 = base64.b64encode(wav_bytes).decode("utf-8")
        return wav_b64, "audio/wav"

    if resolved_hint == "audio/wav":
        return base64_text, "audio/wav"
    if resolved_hint == "audio/mpeg":
        return base64_text, "audio/mpeg"
    if resolved_hint:
        return base64_text, resolved_hint

    return base64_text, normalised_requested or "audio/wav"


class AnswerItem(BaseModel):
    question_id: str = Field(..., description="Question identifier")
    answer: str = Field(..., min_length=1, description="User supplied answer")


class AnswerSheet(BaseModel):
    answers: List[AnswerItem]


def _parse_manual_words(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    raw = raw.strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except json.JSONDecodeError:
        pass
    tokens = re.split(r"[\n,;，\uFF0C]+", raw)
    return [token.strip() for token in tokens if token.strip()]


def _normalise_word(token: str) -> Optional[str]:
    candidate = re.sub(r"[^A-Za-z\-' ]", "", token).strip()
    if not candidate:
        return None
    candidate = candidate.replace(" ", "-")
    if len(candidate) <= 1:
        return None
    return candidate.lower()


def _prepare_word_list(tokens: Iterable[str]) -> Tuple[List[str], List[str], List[str]]:
    ordered: "OrderedDict[str, None]" = OrderedDict()
    duplicates: List[str] = []
    rejected: List[str] = []
    for token in tokens:
        normalised = _normalise_word(token)
        if not normalised:
            if token.strip():
                rejected.append(token.strip())
            continue
        if normalised in ordered:
            duplicates.append(normalised)
            continue
        ordered[normalised] = None
    return list(ordered.keys()), duplicates, rejected


def _get_gemini_api_key() -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="服务器未配置 GEMINI_API_KEY，请先设置环境变量后重试。")
    return api_key


def _call_gemini_tts(
    text: str,
    *,
    model: Optional[str] = None,
    mime_type: Optional[str] = "audio/pcm",
    voice_name: Optional[str] = None,
    timeout: int = 120,
) -> Tuple[Optional[str], Optional[str]]:
    api_key = _get_gemini_api_key()
    resolved_model = model or os.environ.get("IELTS_TTS_MODEL") or DEFAULT_GEMINI_MODEL
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{resolved_model}:generateContent?key={api_key}"
    )
    payload: Dict[str, object] = {
        "contents": [{"role": "user", "parts": [{"text": text}]}],
        "generationConfig": {
            "temperature": 0.25,
            "topP": 0.9,
            "topK": 32,
            "maxOutputTokens": 1200,
            "responseModalities": ["AUDIO"],
        },
        "safetySettings": _GEMINI_SAFETY_SETTINGS,
    }
    if mime_type:
        payload["generationConfig"]["responseMimeType"] = mime_type
    if voice_name:
        payload["speechConfig"] = {
            "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice_name}}
        }

    try:
        response = requests.post(url, json=payload, timeout=timeout)
    except requests.RequestException as exc:  # pragma: no cover - network failure
        raise HTTPException(status_code=502, detail=f"调用 Gemini TTS 失败：{exc}") from exc

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=f"Gemini TTS error: {response.text}")

    result = response.json()
    candidates = result.get("candidates") or []
    for candidate in candidates:
        content = candidate.get("content") or {}
        parts = content.get("parts") or []
        for part in parts:
            inline = part.get("inline_data") or part.get("inlineData")
            if isinstance(inline, dict) and inline.get("data"):
                data, resolved_mime = _normalise_audio_payload(
                    inline.get("data"),
                    inline.get("mime_type") or inline.get("mimeType"),
                    mime_type,
                    inline,
                )
                return data, resolved_mime
            audio = part.get("audio")
            if isinstance(audio, dict) and audio.get("data"):
                data, resolved_mime = _normalise_audio_payload(
                    audio.get("data"),
                    audio.get("mime_type") or audio.get("mimeType"),
                    mime_type,
                    audio,
                )
                return data, resolved_mime
    finish_reasons = [
        candidate.get("finishReason")
        for candidate in candidates
        if candidate.get("finishReason")
    ]
    if finish_reasons and any(reason == "SAFETY" for reason in finish_reasons):
        raise HTTPException(status_code=400, detail="Gemini TTS 输出被安全策略拦截。")
    return None, None


def _call_gemini_sync(prompt: str, images: Optional[List[str]] = None, response_mime_type: str = "application/json") -> str:
    api_key = _get_gemini_api_key()
    model = os.environ.get("IELTS_GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    parts = [{"text": prompt}]
    for image_b64 in images or []:
        parts.append({"inline_data": {"mime_type": "image/png", "data": image_b64}})

    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": 0.35,
            "topP": 0.9,
            "topK": 32,
            "maxOutputTokens": 20000,
            "responseMimeType": response_mime_type,
        },
        "safetySettings": _GEMINI_SAFETY_SETTINGS,
    }

    try:
        response = requests.post(url, json=payload, timeout=180)
    except requests.RequestException as exc:  # pragma: no cover - network errors
        raise HTTPException(status_code=502, detail=f"调用 Gemini API 失败：{exc}") from exc

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=f"Gemini API error: {response.text}")

    result = response.json()
    prompt_feedback = result.get("promptFeedback")
    if prompt_feedback and prompt_feedback.get("blockReason"):
        raise HTTPException(status_code=400, detail=f"Gemini 拒绝了请求：{prompt_feedback['blockReason']}")

    for candidate in result.get("candidates", []):
        content = candidate.get("content") or {}
        for part in content.get("parts", []):
            if "text" in part:
                return part["text"]
    raise HTTPException(status_code=502, detail="Gemini API 未返回文本结果，请稍后重试。")


def _encode_image(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def _extract_code_fence_content(text: str) -> Optional[str]:
    """Return the content of the first markdown code fence if present."""

    match = re.search(r"```(?:json)?\s*([\s\S]+?)```", text, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def _enumerate_json_candidates(raw: str) -> Iterable[str]:
    """Yield plausible JSON substrings from a raw model response."""

    trimmed = raw.strip()
    if trimmed:
        yield trimmed

    fenced = _extract_code_fence_content(trimmed)
    if fenced:
        yield fenced

    sources: List[str] = []
    for item in (trimmed, fenced):
        if item and item not in sources:
            sources.append(item)

    for candidate_source in sources:
        stack: List[str] = []
        start: Optional[int] = None
        in_string = False
        escape = False
        for index, char in enumerate(candidate_source):
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
                continue
            if char in "{[":
                if not stack:
                    start = index
                stack.append('}' if char == '{' else ']')
            elif char in "}]":
                if stack and char == stack[-1]:
                    stack.pop()
                    if not stack and start is not None:
                        fragment = candidate_source[start : index + 1].strip()
                        if fragment:
                            yield fragment
                        start = None
                else:
                    stack.clear()
                    start = None


def _remove_trailing_commas(candidate: str) -> str:
    """Remove trailing commas before closing tokens outside of strings."""

    result: List[str] = []
    in_string = False
    escape = False
    index = 0
    length = len(candidate)
    while index < length:
        char = candidate[index]
        if in_string:
            result.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            result.append(char)
            index += 1
            continue
        if char == ',':
            look_ahead = index + 1
            while look_ahead < length and candidate[look_ahead].isspace():
                look_ahead += 1
            if look_ahead < length and candidate[look_ahead] in "}]":
                index = look_ahead
                while index < length and candidate[index].isspace():
                    index += 1
                continue
        result.append(char)
        index += 1
    return "".join(result)


def _parse_gemini_json(raw: str) -> object:
    """Attempt to parse Gemini output into JSON, repairing common issues."""

    seen: set[str] = set()
    for candidate in _enumerate_json_candidates(raw):
        fragment = candidate.strip()
        if not fragment or fragment in seen:
            continue
        seen.add(fragment)
        try:
            return json.loads(fragment)
        except json.JSONDecodeError:
            repaired = _remove_trailing_commas(fragment)
            if repaired != fragment and repaired not in seen:
                seen.add(repaired)
                try:
                    return json.loads(repaired)
                except json.JSONDecodeError:
                    continue
    snippet = raw.strip().replace("\n", " ")
    snippet = snippet[:180] + ("…" if len(snippet) > 180 else "")
    raise ValueError(f"模型返回的内容无法解析为 JSON：{snippet}")


async def _perform_ocr_via_gemini(image: Image.Image, filename: str) -> Tuple[List[str], Optional[str]]:
    encoded = _encode_image(image)
    prompt = (
        "你是一名 OCR 助手，请识别上传的学习单词图片。\n"
        "请输出 JSON 对象，包含两个字段：\n"
        "- words: 识别出的英文单词数组（全部小写、去重，只包含字母或连字符）。\n"
        "- note: 一条简短中文提示，描述识别质量（<= 40 个汉字）。若识别正常，返回“识别完成”。\n"
        "如果图像没有单词，words 用空数组，并在 note 中说明原因。\n"
        f"当前图片文件名：{filename}。\n"
        "请直接输出 JSON，勿添加额外文本。"
    )
    raw = await run_in_threadpool(_call_gemini_sync, prompt, [encoded], "application/json")
    try:
        payload = _parse_gemini_json(raw)
    except ValueError as exc:
        raise OCRUnavailableError(f"Gemini OCR 返回不可解析的 JSON：{exc}") from exc
    if not isinstance(payload, dict):
        raise OCRUnavailableError("Gemini OCR 未返回 JSON 对象，请稍后重试。")

    words: List[str] = []
    for token in payload.get("words", []):
        if isinstance(token, str):
            cleaned = re.sub(r"[^A-Za-z\-' ]", "", token).strip()
            if cleaned:
                words.append(cleaned.lower())
    note = payload.get("note")
    note_text = str(note).strip() if note else None
    return words, note_text


async def _extract_words_from_uploads(files: List[UploadFile]) -> Tuple[List[str], List[str]]:
    extracted: List[str] = []
    notes: List[str] = []
    for upload in files:
        try:
            content = await upload.read()
        except Exception as exc:  # pragma: no cover - depends on Starlette internals
            notes.append(f"读取文件 {upload.filename} 失败：{exc}")
            continue
        if not content:
            notes.append(f"文件 {upload.filename} 为空，已跳过。")
            continue
        try:
            image = Image.open(io.BytesIO(content))
        except UnidentifiedImageError:
            notes.append(f"{upload.filename} 不是有效的图片格式，已忽略。")
            continue
        try:
            words, note = await _perform_ocr_via_gemini(image, upload.filename or "uploaded image")
        except OCRUnavailableError as exc:
            notes.append(str(exc))
            continue
        except HTTPException as exc:
            notes.append(f"调用 Gemini OCR 失败（{upload.filename}）：{exc.detail}")
            continue
        if note and note not in {"", "识别完成"}:
            notes.append(f"{upload.filename}: {note}")
        if not words:
            notes.append(f"未能在 {upload.filename} 中识别出英文单词，请检查清晰度。")
        extracted.extend(words)
    return extracted, notes


def _covers_all_words(words: List[str], questions: List[Dict[str, object]]) -> bool:
    if not words:
        return False
    focus_words = {
        str(item).lower()
        for question in questions
        for item in question.get("focus_words", [])
        if isinstance(item, str)
    }
    return all(word.lower() in focus_words for word in words)


def _split_questions_and_answers(
    question_items: List[Dict[str, object]],
) -> Tuple[List[Dict[str, object]], Dict[str, Dict[str, object]]]:
    cleaned_questions: List[Dict[str, object]] = []
    answer_bank: Dict[str, Dict[str, object]] = {}
    for idx, raw in enumerate(question_items, start=1):
        if not isinstance(raw, dict):
            continue
        question_id = str(raw.get("id") or raw.get("question_id") or f"Q{idx:02d}")
        answer = str(raw.get("answer", "")).strip()
        if not answer:
            continue
        alternatives_raw = raw.get("alternatives") or []
        if isinstance(alternatives_raw, str):
            alternatives_raw = [alternatives_raw]
        alternatives = [str(item).strip() for item in alternatives_raw if str(item).strip()]
        seen: set[str] = set()
        deduped_alternatives: List[str] = []
        for option in [answer, *alternatives]:
            key = option.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped_alternatives.append(option)
        rationale = raw.get("rationale")
        answer_bank[question_id] = {
            "answer": answer,
            "alternatives": deduped_alternatives,
            "rationale": rationale,
        }
        question_payload = {
            key: value
            for key, value in raw.items()
            if key not in {"answer", "alternatives", "rationale"}
        }
        question_payload["id"] = question_id
        focus_words = question_payload.get("focus_words")
        if not isinstance(focus_words, list):
            question_payload["focus_words"] = [answer]
        cleaned_questions.append(question_payload)

    if not cleaned_questions:
        raise HTTPException(status_code=502, detail="Gemini 未生成有效题目，请稍后重试。")

    return cleaned_questions, answer_bank


def _prepare_story_payload(raw_story: Dict[str, object], words: List[str]) -> Dict[str, object]:
    story = {
        "title": str(raw_story.get("title") or "IELTS Narrative"),
        "scenario": str(raw_story.get("scenario") or ""),
        "overview": str(raw_story.get("overview") or ""),
        "paragraphs": [str(item) for item in raw_story.get("paragraphs", []) if item],
        "closing": str(raw_story.get("closing") or ""),
        "voice_role": str(raw_story.get("voice_role") or "You are an IELTS mentor guiding the learner."),
        "setting": str(raw_story.get("setting") or "learning space"),
        "audience": str(raw_story.get("audience") or "IELTS learners"),
        "sentences": [],
    }
    sentences = raw_story.get("sentences") or []
    for raw in sentences:
        if not isinstance(raw, dict):
            continue
        story["sentences"].append(
            {
                "word": str(raw.get("word") or ""),
                "sentence": str(raw.get("sentence") or ""),
                "hint": str(raw.get("hint") or ""),
                "rationale": str(raw.get("rationale") or ""),
            }
        )
    if not story["paragraphs"]:
        summary = [story["scenario"], story["overview"], story["closing"]]
        story["paragraphs"] = [part for part in summary if part]
    if not story["sentences"]:
        story["sentences"] = [
            {
                "word": word,
                "sentence": f"Learners revisit {word} within the bespoke IELTS workshop.",
                "hint": f"聚焦单词 {word} 的使用场景。",
                "rationale": "模型未提供详细句子，已自动生成占位内容。",
            }
            for word in words
        ]
    return story


def _prepare_listening_payload(
    listening_raw: Dict[str, object], story: Dict[str, object], words: List[str]
) -> Tuple[Dict[str, object], Dict[str, Dict[str, object]]]:
    script = str(listening_raw.get("script") or " ".join(story.get("paragraphs", [])))
    segments_raw = listening_raw.get("segments") or []
    segments: List[Dict[str, object]] = []
    for idx, segment in enumerate(segments_raw, start=1):
        if not isinstance(segment, dict):
            continue
        start = float(segment.get("start") or 0.0)
        end = float(segment.get("end") or 0.0)
        segments.append(
            {
                "index": int(segment.get("index") or idx),
                "start": round(start, 2),
                "end": round(end, 2),
                "text": str(segment.get("text") or ""),
                "focus_word": str(segment.get("focus_word") or ""),
            }
        )
    if not segments:
        segments = [
            {
                "index": idx + 1,
                "start": round(idx * 6.0, 2),
                "end": round((idx + 1) * 6.0, 2),
                "text": detail.get("sentence", ""),
                "focus_word": detail.get("word", ""),
            }
            for idx, detail in enumerate(story.get("sentences", []))
        ]

    questions_raw = listening_raw.get("questions") or []
    questions, answers = _split_questions_and_answers(questions_raw)
    audio_b64, tts_note = TTS_SYNTHESIZER.synthesize(script)
    audio_plan = {
        "available": audio_b64 is not None,
        "format": TTS_SYNTHESIZER.mime_type if audio_b64 else None,
        "base64": audio_b64,
        "message": tts_note,
    }
    notes = str(listening_raw.get("notes") or "").strip()
    metadata = {
        "total_questions": len(questions),
        "covers_all_words": _covers_all_words(words, questions),
        "audio_available": audio_plan["available"],
        "notes": notes or audio_plan["message"],
    }
    payload = {
        "script": script,
        "segments": segments,
        "audio": audio_plan,
        "questions": questions,
        "metadata": metadata,
    }
    return payload, answers


def _prepare_reading_payload(
    reading_raw: Dict[str, object], story: Dict[str, object], words: List[str]
) -> Tuple[Dict[str, object], Dict[str, Dict[str, object]]]:
    paragraphs = [str(item) for item in reading_raw.get("paragraphs", []) if item]
    if not paragraphs:
        paragraphs = story.get("paragraphs", [])
    glossary = []
    for item in reading_raw.get("glossary", []) or []:
        if not isinstance(item, dict):
            continue
        glossary.append(
            {
                "word": str(item.get("word") or ""),
                "summary": str(item.get("summary") or ""),
                "category": str(item.get("category") or "general"),
            }
        )
    if not glossary:
        glossary = [
            {
                "word": detail.get("word", ""),
                "summary": detail.get("hint", ""),
                "category": "general",
            }
            for detail in story.get("sentences", [])
        ]
    questions_raw = reading_raw.get("questions") or []
    questions, answers = _split_questions_and_answers(questions_raw)
    metadata_raw = reading_raw.get("metadata")
    metadata = metadata_raw if isinstance(metadata_raw, dict) else {}
    metadata.setdefault("paragraphs", len(paragraphs))
    metadata.setdefault("word_count", sum(len(str(p).split()) for p in paragraphs))
    focus_words = {
        str(item).lower()
        for question in questions
        for item in question.get("focus_words", [])
        if isinstance(item, str)
    }
    metadata.setdefault("covers_all_words", all(word.lower() in focus_words for word in words) if words else False)
    payload = {
        "title": str(reading_raw.get("title") or story.get("title") or "IELTS Reading"),
        "paragraphs": paragraphs,
        "questions": questions,
        "glossary": glossary,
        "metadata": metadata,
    }
    return payload, answers


def _prepare_conversation_payload(conversation_raw: Dict[str, object], story: Dict[str, object]) -> Dict[str, object]:
    questions: List[Dict[str, object]] = []
    for idx, item in enumerate(conversation_raw.get("questions") or [], start=1):
        if not isinstance(item, dict):
            continue
        questions.append(
            {
                "id": item.get("id") or f"C{idx:02d}",
                "question": item.get("question") or "",
                "focus_words": item.get("focus_words") or [],
                "follow_up": item.get("follow_up") or "",
                "reference_answer": item.get("reference_answer") or "",
                "answer_explanation": item.get("answer_explanation") or "",
            }
        )
    agenda = conversation_raw.get("agenda")
    if not isinstance(agenda, list) or not agenda:
        agenda = [
            {
                "step": 1,
                "goal": "Warm-up and ensure the learner recognises the scenario.",
                "actions": [
                    "播放开场语音，引导学习者描述现场布置。",
                    "确认他们已经阅读文章并熟悉核心词汇。",
                ],
            },
            {
                "step": 2,
                "goal": "Prompt lexical output covering所有关键词。",
                "actions": [
                    "逐条播报问题，鼓励回答时点名词汇。",
                    "必要时提供同义词或中文提示，降低迟疑。",
                ],
            },
            {
                "step": 3,
                "goal": "引导反思与总结。",
                "actions": [
                    "追问哪类词汇最具挑战，并建议复盘方法。",
                    "提醒记录语音答案，便于事后批改。",
                ],
            },
        ]
    voice_prompts = conversation_raw.get("voice_prompts")
    if not isinstance(voice_prompts, list) or len(voice_prompts) != len(questions):
        voice_prompts = [
            {
                "order": idx + 1,
                "text": question.get("question", ""),
                "focus_words": question.get("focus_words", []),
            }
            for idx, question in enumerate(questions)
        ]
    practice_tips = conversation_raw.get("practice_tips")
    if not isinstance(practice_tips, list) or not practice_tips:
        practice_tips = [
            "点击或按住下方按钮即可开始语音回答，浏览器会自动转写文字。",
            "如果识别不稳定，可在放开按钮后手动修改文本再提交。",
            "确保回答覆盖提示中的重点词汇，并按照追问提示进一步展开。",
        ]
    conversation = {
        "role": conversation_raw.get("role")
        or story.get("voice_role")
        or "You are the learner's IELTS speaking coach.",
        "opening_line": conversation_raw.get("opening_line") or story.get("scenario") or "",
        "questions": questions,
        "agenda": agenda,
        "voice_prompts": voice_prompts,
        "practice_tips": practice_tips,
        "closing_line": conversation_raw.get("closing_line") or story.get("closing") or "",
    }
    return conversation


def _build_materials_prompt(words: List[str], scenario_hint: Optional[str]) -> str:
    bullet_list = "\n".join(f"- {word}" for word in words)
    hint = scenario_hint.strip() if scenario_hint else "无特别提示"
    return (
        "你是一名雅思学习设计专家，请基于以下词汇生成情景化学习材料。\n"
        "请确保输出严格为 JSON（不包含代码块或多余描述）。结构如下：\n"
        "{\n"
        "  \"story\": {\n"
        "    \"title\": str, \"scenario\": str, \"overview\": str, \"paragraphs\": [str...], \"closing\": str,\n"
        "    \"voice_role\": str, \"setting\": str, \"audience\": str,\n"
        "    \"sentences\": [{\"word\": str, \"sentence\": str, \"hint\": str, \"rationale\": str}]\n"
        "  },\n"
        "  \"listening\": {\n"
        "    \"script\": str,\n"
        "    \"segments\": [{\"index\": int, \"start\": float, \"end\": float, \"text\": str, \"focus_word\": str}],\n"
        "    \"questions\": [{\"id\": str, \"prompt\": str, \"hint\": str, \"focus_words\": [str], \"answer\": str, \"alternatives\": [str], \"rationale\": str}],\n"
        "    \"notes\": str\n"
        "  },\n"
        "  \"reading\": {\n"
        "    \"title\": str, \"paragraphs\": [str], \"glossary\": [{\"word\": str, \"summary\": str, \"category\": str}],\n"
        "    \"questions\": [{\"id\": str, \"prompt\": str, \"hint\": str, \"focus_words\": [str], \"answer\": str, \"alternatives\": [str], \"rationale\": str}],\n"
        "    \"metadata\": {\"paragraphs\": int, \"word_count\": int}\n"
        "  },\n"
        "  \"conversation\": {\n"
        "    \"role\": str, \"opening_line\": str, \"closing_line\": str,\n"
        "    \"questions\": [{\"id\": str, \"question\": str, \"focus_words\": [str], \"follow_up\": str, \"reference_answer\": str, \"answer_explanation\": str}],\n"
        "    \"agenda\": [{\"step\": int, \"goal\": str, \"actions\": [str]}],\n"
        "    \"voice_prompts\": [{\"order\": int, \"text\": str, \"focus_words\": [str]}],\n"
        "    \"practice_tips\": [str]\n"
        "  }\n"
        "}\n"
        "要求：\n"
        "1. 必须在 story.sentences 中按给定顺序覆盖全部词汇，每个词提供中文提示。\n"
        "2. 听力和阅读题目的 ID 分别以 L 和 R 开头并从 01 递增，提供标准答案、备选答案和解析。\n"
        "3. 所有提示与说明使用中文，题干可使用英文。\n"
        "4. conversation.voice_prompts 数量需与 questions 对齐。\n"
        "5. 不得返回除 JSON 以外的任何内容。\n"
        "词汇列表：\n"
        f"{bullet_list}\n"
        f"情景提示：{hint}\n"
    )


async def _generate_materials_via_gemini(words: List[str], scenario_hint: Optional[str]) -> Dict[str, object]:
    prompt = _build_materials_prompt(words, scenario_hint)
    raw = await run_in_threadpool(_call_gemini_sync, prompt, None, "application/json")
    try:
        payload = _parse_gemini_json(raw)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f"Gemini 输出解析失败：{exc}") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="Gemini 输出格式异常，请稍后重试。")
    return payload


def _normalise_answer(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.strip().lower())


def _evaluate_answers(
    answer_bank: Dict[str, Dict[str, object]], submission: AnswerSheet
) -> Dict[str, object]:
    answer_lookup = {item.question_id: item.answer for item in submission.answers}
    breakdown: List[Dict[str, object]] = []
    correct = 0
    for question_id, meta in answer_bank.items():
        expected = meta["answer"]
        alternatives = {expected, *[alt for alt in meta.get("alternatives", [])]}
        user_answer = answer_lookup.get(question_id, "")
        normalised_user = _normalise_answer(user_answer)
        candidates = {_normalise_answer(str(option)) for option in alternatives}
        is_correct = bool(normalised_user) and normalised_user in candidates
        if is_correct:
            correct += 1
        breakdown.append(
            {
                "question_id": question_id,
                "user_answer": user_answer or None,
                "correct_answer": expected,
                "correct": is_correct,
                "rationale": meta.get("rationale"),
            }
        )
    total = len(answer_bank)
    accuracy = round(correct / total, 2) if total else 0.0
    return {
        "score": correct,
        "total": total,
        "accuracy": accuracy,
        "breakdown": breakdown,
    }


def _public_session_payload(session: Dict[str, object]) -> Dict[str, object]:
    return {
        "session_id": session["id"],
        "words": session["words"],
        "story": session["story"],
        "listening": session["listening"]["content"],
        "reading": session["reading"]["content"],
        "conversation": session["conversation"],
    }


@router.post("/upload-batch")
async def create_session(
    files: UploadFile | List[UploadFile] | None = File(default=None),
    manual_words: Optional[str] = Form(default=None),
    scenario_hint: Optional[str] = Form(default=None),
) -> Dict[str, object]:
    if files is None:
        uploads: List[UploadFile] = []
    elif isinstance(files, list):
        uploads = files
    else:
        uploads = [files]
    manual_tokens = _parse_manual_words(manual_words)

    if not uploads and not manual_tokens:
        raise HTTPException(status_code=400, detail="请至少上传一张图片或输入词汇列表。")

    extracted_tokens, extraction_notes = await _extract_words_from_uploads(uploads)
    combined_tokens = extracted_tokens + manual_tokens
    words, duplicates, rejected = _prepare_word_list(combined_tokens)

    if not words:
        detail = "未能提取到有效的英文单词，请上传更清晰的照片或直接输入词汇。"
        if extraction_notes:
            detail += " " + "；".join(extraction_notes)
        raise HTTPException(status_code=400, detail=detail)

    materials = await _generate_materials_via_gemini(words, scenario_hint)
    story_payload = _prepare_story_payload(materials.get("story") or {}, words)
    listening_payload, listening_answers = _prepare_listening_payload(
        materials.get("listening") or {}, story_payload, words
    )
    reading_payload, reading_answers = _prepare_reading_payload(
        materials.get("reading") or {}, story_payload, words
    )
    conversation_payload = _prepare_conversation_payload(materials.get("conversation") or {}, story_payload)

    session_id = str(uuid.uuid4())
    session_record: Dict[str, object] = {
        "id": session_id,
        "words": {
            "items": words,
            "total": len(words),
            "duplicates": duplicates,
            "rejected": rejected,
            "source_count": len(uploads),
            "extraction_notes": extraction_notes,
            "manual_additions": manual_tokens,
        },
        "story": story_payload,
        "listening": {"content": listening_payload, "answers": listening_answers},
        "reading": {"content": reading_payload, "answers": reading_answers},
        "conversation": conversation_payload,
    }
    SESSION_STORE.save(session_id, session_record)

    public_payload = _public_session_payload(session_record)
    return public_payload


@router.get("/session/{session_id}")
def fetch_session(session_id: str) -> Dict[str, object]:
    session = SESSION_STORE.get(session_id)
    return _public_session_payload(session)


@router.get("/listening/{session_id}")
def get_listening_material(session_id: str) -> Dict[str, object]:
    session = SESSION_STORE.get(session_id)
    return {
        "session_id": session_id,
        **session["listening"]["content"],
    }


@router.post("/listening/{session_id}/evaluate")
def evaluate_listening(session_id: str, submission: AnswerSheet) -> Dict[str, object]:
    session = SESSION_STORE.get(session_id)
    answer_bank = session["listening"]["answers"]
    return _evaluate_answers(answer_bank, submission)


@router.get("/reading/{session_id}")
def get_reading_material(session_id: str) -> Dict[str, object]:
    session = SESSION_STORE.get(session_id)
    return {
        "session_id": session_id,
        **session["reading"]["content"],
    }


@router.post("/reading/{session_id}/evaluate")
def evaluate_reading(session_id: str, submission: AnswerSheet) -> Dict[str, object]:
    session = SESSION_STORE.get(session_id)
    answer_bank = session["reading"]["answers"]
    return _evaluate_answers(answer_bank, submission)


@router.get("/conversation/{session_id}")
def get_conversation_playbook(session_id: str) -> Dict[str, object]:
    session = SESSION_STORE.get(session_id)
    return {
        "session_id": session_id,
        "role": session["conversation"]["role"],
        "opening_line": session["conversation"]["opening_line"],
        "questions": session["conversation"]["questions"],
        "agenda": session["conversation"]["agenda"],
        "voice_prompts": session["conversation"]["voice_prompts"],
        "practice_tips": session["conversation"]["practice_tips"],
        "closing_line": session["conversation"]["closing_line"],
    }

