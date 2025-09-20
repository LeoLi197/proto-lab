"""Scenario-driven IELTS study system with upload, listening, reading and conversation modules."""
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

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from PIL import Image, UnidentifiedImageError

try:  # Optional OCR dependency
    import pytesseract
    from pytesseract import TesseractNotFoundError
except Exception:  # pragma: no cover - dependency is optional at runtime
    pytesseract = None  # type: ignore[assignment]

    class TesseractNotFoundError(RuntimeError):
        """Fallback error when Tesseract is unavailable."""

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
        self._lock = Lock()
        self._engine = None
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

        # pyttsx3 is not thread safe; guard with a lock.
        with self._lock:
            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            tmp_file.close()
            try:
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


def _article(word: str) -> str:
    return "an" if word[:1].lower() in {"a", "e", "i", "o", "u"} else "a"


def _categorise_word(word: str) -> str:
    lower = word.lower()
    if lower.endswith(("ist", "ian", "er", "or", "ologist")):
        return "professional"
    if lower.endswith(("ology", "graphy", "ics", "logy")):
        return "discipline"
    if lower.endswith(("tion", "sion", "ment", "ness", "ity", "ship")):
        return "concept"
    if lower.endswith("ing"):
        return "process"
    if lower.endswith(("al", "ive", "ous", "ary", "ant", "ent", "ic")):
        return "adjective"
    return "general"


SCENARIOS = [
    {
        "title": "Orientation Day at the Global Learning Institute",
        "lead": "The Global Learning Institute hosted an orientation fair where new international students explored every academic wing.",
        "overview": "Mentors from science, humanities and professional schools each showcased how their expertise supports IELTS success.",
        "setting": "orientation fair",
        "audience": "new cohorts preparing for postgraduate study",
        "voice_role": "You are the institute's IELTS mentor guiding visitors booth by booth.",
        "closing": "By the end of the tour everyone designed a personalised action plan and scheduled a follow-up coaching call.",
    },
    {
        "title": "Interdisciplinary Research Expo",
        "lead": "A bustling research expo filled the innovation center, pairing students with scholars from emerging disciplines.",
        "overview": "Each booth linked cutting-edge projects to the communicative demands of IELTS tasks, proving academic language can be vibrant.",
        "setting": "research expo",
        "audience": "curious scholars and language learners",
        "voice_role": "You are the academic liaison helping visitors translate complex research into IELTS-ready explanations.",
        "closing": "The expo concluded with students promising to record reflections and share them in the mentorship forum.",
    },
    {
        "title": "Global Careers Strategy Workshop",
        "lead": "Career advisors, faculty and alumni collaborated during a strategy workshop tailored for future international professionals.",
        "overview": "Sessions blended technical insight with communication practice so participants could narrate expertise confidently in IELTS interviews.",
        "setting": "career planning workshop",
        "audience": "graduates targeting overseas positions",
        "voice_role": "You are the workshop facilitator coaching learners to articulate their academic achievements with precision.",
        "closing": "Everyone left with a recorded mock interview and commitments to rehearse vocabulary daily.",
    },
]


SENTENCE_PREFIXES = [
    "To kick things off",
    "At the next booth",
    "Soon afterwards",
    "Meanwhile on the main stage",
    "Later that afternoon",
    "Before the break",
    "As the tour continued",
    "In the final showcase",
]


def _build_sentence(word: str, index: int, scenario: Dict[str, str]) -> Dict[str, str]:
    category = _categorise_word(word)
    prefix = SENTENCE_PREFIXES[index % len(SENTENCE_PREFIXES)]
    start_hint = word[:2].upper()

    if category == "professional":
        sentence = (
            f"{prefix}, {_article(word)} {word} described mentoring {scenario['audience']} so they can narrate research in IELTS speaking tasks."
        )
        hint = f"the specialist title introduced for mentoring support (开头字母 {start_hint})."
        rationale = "讲述导师如何辅导学生准备口语。"
    elif category == "discipline":
        sentence = (
            f"{prefix}, the host linked {word} to real case studies, proving the {scenario['setting']} blends theory with communication practice."
        )
        hint = f"the academic field that connects theory to communication (开头字母 {start_hint})."
        rationale = "文章强调该学科如何成为跨学科话题。"
    elif category == "concept":
        sentence = (
            f"{prefix}, planners stressed that {word} underpins every support programme, ensuring learners build rigorous habits for IELTS."
        )
        hint = f"the abstract concept emphasised as programme foundation (开头字母 {start_hint})."
        rationale = "段落指出该概念构成学习基石。"
    elif category == "process":
        sentence = (
            f"{prefix}, participants practised {word} together so they could immediately rehearse terminology while staying confident."
        )
        hint = f"the collaborative activity rehearsed on-site (开头字母 {start_hint})."
        rationale = "说明现场演练的活动。"
    elif category == "adjective":
        sentence = (
            f"{prefix}, mentors highlighted {word} learning environments that make complex vocabulary memorable during the {scenario['setting']}."
        )
        hint = f"the descriptive adjective used to portray the learning environment (开头字母 {start_hint})."
        rationale = "形容场景氛围的关键词。"
    else:
        sentence = (
            f"{prefix}, organisers revisited the word {word} to anchor discussions and remind everyone to weave it into study reflections."
        )
        hint = f"the general keyword organisers repeated for emphasis (开头字母 {start_hint})."
        rationale = "主办方反复提醒记忆的词汇。"

    return {
        "word": word,
        "category": category,
        "sentence": sentence,
        "hint": hint,
        "rationale": rationale,
    }


def _chunk_sentences(sentences: List[Dict[str, str]], size: int = 4) -> List[str]:
    paragraphs: List[str] = []
    for idx in range(0, len(sentences), size):
        chunk = sentences[idx : idx + size]
        paragraph = " ".join(item["sentence"] for item in chunk)
        paragraphs.append(paragraph)
    return paragraphs


def _select_scenario(word_count: int, hint: Optional[str]) -> Dict[str, str]:
    scenario = deepcopy(SCENARIOS[word_count % len(SCENARIOS)])
    if hint:
        hint = hint.strip()
        if hint:
            scenario["lead"] += f" The user request highlights {hint}, so the narrative keeps that context vivid."
            scenario["overview"] += f" The activities are tailored around {hint} to keep the storyline coherent."
    return scenario


def _build_story(words: List[str], scenario_hint: Optional[str]) -> Tuple[Dict[str, object], List[Dict[str, str]]]:
    scenario = _select_scenario(len(words), scenario_hint)
    sentence_details = [_build_sentence(word, idx, scenario) for idx, word in enumerate(words)]
    paragraphs = _chunk_sentences(sentence_details, size=4)

    story_payload: Dict[str, object] = {
        "title": scenario["title"],
        "scenario": scenario["lead"],
        "overview": scenario["overview"],
        "closing": scenario["closing"],
        "paragraphs": paragraphs,
        "sentences": sentence_details,
        "word_count": len(words),
    }
    story_payload["voice_role"] = scenario["voice_role"]
    story_payload["setting"] = scenario["setting"]
    story_payload["audience"] = scenario["audience"]
    return story_payload, sentence_details


def _build_segments(sentences: List[Dict[str, str]]) -> List[Dict[str, object]]:
    segments: List[Dict[str, object]] = []
    cursor = 0.0
    for idx, detail in enumerate(sentences, start=1):
        sentence = detail["sentence"]
        words = len(sentence.split())
        duration = max(4.0, round(words * 0.48, 2))
        segment = {
            "index": idx,
            "start": round(cursor, 2),
            "end": round(cursor + duration, 2),
            "text": sentence,
            "focus_word": detail["word"],
        }
        segments.append(segment)
        cursor += duration
    return segments


def _build_listening_package(
    story: Dict[str, object], sentences: List[Dict[str, str]]
) -> Tuple[Dict[str, object], Dict[str, Dict[str, object]]]:
    script_parts = [story["scenario"], story["overview"], " ".join(story["paragraphs"]), story["closing"]]
    script = " ".join(part for part in script_parts if part)

    segments = _build_segments(sentences)
    audio_b64, tts_note = TTS_SYNTHESIZER.synthesize(script)
    audio_plan = {
        "available": audio_b64 is not None,
        "format": "audio/mp3" if audio_b64 else None,
        "base64": audio_b64,
        "message": tts_note,
    }

    questions: List[Dict[str, object]] = []
    answer_bank: Dict[str, Dict[str, object]] = {}
    for idx, detail in enumerate(sentences):
        question_id = f"L{idx + 1:02d}"
        prompt = (
            f"When the narrator discusses {detail['hint']}, write down the exact keyword you hear."
        )
        question = {
            "id": question_id,
            "type": "dictation",
            "prompt": prompt,
            "hint": f"Starts with {detail['word'][:2].upper()} and appears in the listening script.",
            "focus_words": [detail["word"]],
        }
        questions.append(question)
        answer_bank[question_id] = {
            "answer": detail["word"],
            "alternatives": [detail["word"], detail["word"].capitalize()],
            "rationale": detail["rationale"],
        }

    metadata = {
        "total_questions": len(questions),
        "covers_all_words": True,
        "audio_available": audio_plan["available"],
        "notes": audio_plan["message"],
    }

    payload = {
        "script": script,
        "segments": segments,
        "audio": audio_plan,
        "questions": questions,
        "metadata": metadata,
    }
    return payload, answer_bank


def _build_reading_package(
    story: Dict[str, object], sentences: List[Dict[str, str]]
) -> Tuple[Dict[str, object], Dict[str, Dict[str, object]]]:
    paragraphs = story["paragraphs"]
    questions: List[Dict[str, object]] = []
    answer_bank: Dict[str, Dict[str, object]] = {}

    for idx, detail in enumerate(sentences):
        question_id = f"R{idx + 1:02d}"
        prompt = (
            f"Which word in the reading passage captures {detail['hint']}"
            "? Provide the single vocabulary item used by the author."
        )
        question = {
            "id": question_id,
            "type": "short-answer",
            "prompt": prompt,
            "focus_words": [detail["word"]],
            "hint": f"Look for the sentence mentioning the storyline of {story['setting']}.",
        }
        questions.append(question)
        answer_bank[question_id] = {
            "answer": detail["word"],
            "alternatives": [detail["word"], detail["word"].capitalize()],
            "rationale": detail["rationale"],
        }

    glossary = [
        {
            "word": detail["word"],
            "summary": detail["hint"],
            "category": detail["category"],
        }
        for detail in sentences
    ]

    total_words = sum(len(paragraph.split()) for paragraph in paragraphs)
    metadata = {
        "paragraphs": len(paragraphs),
        "word_count": total_words,
        "covers_all_words": True,
    }

    payload = {
        "title": story["title"],
        "paragraphs": paragraphs,
        "questions": questions,
        "glossary": glossary,
        "metadata": metadata,
    }
    return payload, answer_bank


def _build_conversation_package(story: Dict[str, object], words: List[str]) -> Dict[str, object]:
    groups = [words[idx : idx + 3] for idx in range(0, len(words), 3)]
    questions = []
    voice_prompts = []
    for idx, group in enumerate(groups, start=1):
        readable = ", ".join(group)
        prompt = (
            f"Explain how {readable} appear in {story['setting']} and connect the ideas to IELTS speaking or listening practice."
        )
        follow_up = (
            f"Which of {readable} would you prioritise when coaching a peer, and why?"
        )
        question = {
            "id": f"C{idx:02d}",
            "question": prompt,
            "focus_words": group,
            "follow_up": follow_up,
        }
        questions.append(question)
        voice_prompts.append({"order": idx, "text": prompt, "focus_words": group})

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

    conversation = {
        "role": story["voice_role"],
        "opening_line": story["scenario"],
        "questions": questions,
        "agenda": agenda,
        "voice_prompts": voice_prompts,
        "closing_line": story["closing"],
        "practice_tips": [
            "使用浏览器 SpeechSynthesis API 可快速生成每个问题的语音播放。",
            "结合 MediaRecorder 录音，完成后上传到语音批改服务。",
            "回答时务必包含列表中的每个词汇，可在末尾自检是否覆盖。",
        ],
    }
    return conversation


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
            text = _perform_ocr(image)
        except OCRUnavailableError as exc:
            notes.append(str(exc))
            continue
        tokens = re.findall(r"[A-Za-z][A-Za-z\-' ]+", text)
        if not tokens:
            notes.append(f"未能在 {upload.filename} 中识别出英文单词，请检查清晰度。")
        extracted.extend(tokens)
    return extracted, notes


def _perform_ocr(image: Image.Image) -> str:
    if pytesseract is None:
        raise OCRUnavailableError("服务器未安装 pytesseract，建议配置 OCR 服务或提供手动词汇。")
    try:
        gray = image.convert("L")
        text = pytesseract.image_to_string(gray)
        return text
    except TesseractNotFoundError:
        raise OCRUnavailableError("未检测到 Tesseract OCR 引擎，请在服务器安装后重试。")
    except Exception as exc:  # pragma: no cover - depends on Tesseract runtime
        raise OCRUnavailableError(f"OCR 解析失败：{exc}")


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
    files: List[UploadFile] | None = File(default=None),
    manual_words: Optional[str] = Form(default=None),
    scenario_hint: Optional[str] = Form(default=None),
) -> Dict[str, object]:
    uploads = files or []
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

    story_payload, sentence_details = _build_story(words, scenario_hint)
    listening_payload, listening_answers = _build_listening_package(story_payload, sentence_details)
    reading_payload, reading_answers = _build_reading_package(story_payload, sentence_details)
    conversation_payload = _build_conversation_package(story_payload, words)

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
