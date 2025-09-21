"""Scenario-driven IELTS study system powered by Gemini for OCR and material generation."""
from __future__ import annotations

import base64
import io
import json
import os
import re
import tempfile
import uuid
from collections import OrderedDict
from copy import deepcopy
from threading import Lock
from typing import Dict, Iterable, List, Optional, Tuple

import requests
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from PIL import Image, UnidentifiedImageError

try:  # Optional offline TTS dependency
    import pyttsx3
except Exception:  # pragma: no cover - dependency is optional at runtime
    pyttsx3 = None  # type: ignore[assignment]


router = APIRouter(prefix="/ielts", tags=["IELTS Study System"])


class OCRUnavailableError(Exception):
    """Raised when OCR resources are missing or cannot be initialised."""


class TTSSynthesizer:
    """Lightweight wrapper around pyttsx3 with graceful degradation."""

    def __init__(self) -> None:
        self._engine = None
        self._lock = Lock()
        self.available = False
        if pyttsx3 is None:  # Library not installed
            self._note = "pyttsx3 未安装，已回退为文本脚本。"
            return
        try:
            engine = pyttsx3.init()  # type: ignore[call-arg]
            engine.setProperty("rate", 158)
            engine.setProperty("volume", 0.92)
            self._engine = engine
            self.available = True
            self._note = "音频由 pyttsx3 生成。"
        except Exception as exc:  # pragma: no cover - depends on system voices
            self._engine = None
            self.available = False
            self._note = f"TTS 引擎初始化失败：{exc}."

    def synthesize(self, text: str) -> Tuple[Optional[str], str]:
        """Convert text into base64 encoded audio if the engine is available."""

        if not self.available or self._engine is None:
            return None, self._note

        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tmp_file.close()
        try:
            with self._lock:
                self._engine.save_to_file(text, tmp_file.name)
                self._engine.runAndWait()
            with open(tmp_file.name, "rb") as handle:
                audio_bytes = handle.read()
            encoded = base64.b64encode(audio_bytes).decode("utf-8")
            return encoded, self._note
        except Exception as exc:  # pragma: no cover - depends on runtime env
            message = f"TTS 生成失败：{exc}."
            return None, message
        finally:
            if os.path.exists(tmp_file.name):
                try:
                    os.remove(tmp_file.name)
                except OSError:
                    pass


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
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise OCRUnavailableError(f"Gemini OCR 返回不可解析的 JSON：{exc}") from exc

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
        "format": "audio/mp3" if audio_b64 else None,
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
            "使用浏览器 SpeechSynthesis API 可快速生成每个问题的语音播放。",
            "结合 MediaRecorder 录音，完成后上传到语音批改服务。",
            "回答时务必包含列表中的每个词汇，可在末尾自检是否覆盖。",
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
        "    \"questions\": [{\"id\": str, \"question\": str, \"focus_words\": [str], \"follow_up\": str}],\n"
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
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
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

