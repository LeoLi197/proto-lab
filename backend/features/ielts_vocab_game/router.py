"""IELTS vocabulary training game feature module."""
from __future__ import annotations

import base64
import json
import random
import secrets
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/ielts-vocab", tags=["IELTS Vocabulary Lab"])


class GenerateRoundRequest(BaseModel):
    """Schema for requesting a new quiz round."""

    difficulty: str
    mode: Optional[str] = None
    previous_outcome: Optional[str] = Field(default=None, alias="previousOutcome")

    model_config = ConfigDict(populate_by_name=True)


class VerifyRoundRequest(BaseModel):
    """Schema for verifying an answer."""

    round_id: str = Field(alias="roundId")
    answer_payload: str = Field(alias="answerPayload")
    selected_option_id: Optional[str] = Field(default=None, alias="selectedOptionId")

    model_config = ConfigDict(populate_by_name=True)


DIFFICULTY_PROFILES: Dict[str, Dict[str, Any]] = {
    "foundation": {
        "label": "Foundation Core",
        "band": "Band 5-6",
        "description": "着重建立 IELTS 写作和口语常见主题的基础词汇储备。",
        "countdown": 75,
        "default_session": 6,
        "score": {"correct": 80, "incorrect": -18, "timeout": -12},
        "skills": ["释义理解", "语境匹配", "搭配敏感度"],
        "mantras": [
            "先快速构建自己的释义，再对照选项验证。",
            "注意句子的主语和动词，帮助判断词性。",
            "观察常见搭配，基础词汇也要精准表达。",
        ],
        "celebrations": [
            "稳稳拿下一题，基础词汇已经被你吃透了！",
            "Nice！你的释义判断很准确，继续保持节奏。",
        ],
        "remedies": [
            "回想该词在 Task 1/Task 2 范文中的常见搭配。",
            "把正确释义大声读两遍，强化语感记忆。",
        ],
        "palette": {"primary": "#5eead4", "glow": "rgba(94,234,212,0.35)"},
    },
    "advanced": {
        "label": "Advanced Precision",
        "band": "Band 6.5-7",
        "description": "拓展表达力，掌握议论文和报告写作的高级词汇。",
        "countdown": 65,
        "default_session": 8,
        "score": {"correct": 110, "incorrect": -28, "timeout": -20},
        "skills": ["语义细节", "语域判断", "逻辑衔接"],
        "mantras": [
            "抓住语气差异：是中性、积极还是消极？",
            "先判断词性，再判断语义强度。",
            "同义词不等于完全相同，注意语境。",
        ],
        "celebrations": [
            "漂亮！这一题的词汇掌握度已经达到高分要求。",
            "你的语义辨析非常敏锐，完全具备高级表达力。",
        ],
        "remedies": [
            "留意该词常搭配的名词或动词，再记忆一次。",
            "尝试把该词造一个句子，与题干不同语境。",
        ],
        "palette": {"primary": "#38bdf8", "glow": "rgba(56,189,248,0.35)"},
    },
    "expert": {
        "label": "Expert Mastery",
        "band": "Band 7.5+",
        "description": "攻克语义细腻、可用于高分写作与口语的高级词汇。",
        "countdown": 55,
        "default_session": 10,
        "score": {"correct": 140, "incorrect": -40, "timeout": -28},
        "skills": ["语气精准", "抽象概念表达", "复杂搭配"],
        "mantras": [
            "抽象词先想象一个具体场景，再匹配选项。",
            "思考该词在官方范文中的角色：动词？名词？",
            "注意负面与正面语义的微妙差异。",
        ],
        "celebrations": [
            "惊艳！这是母语者级别的词汇掌控力。",
            "优秀！你已经具备雅思写作的高级表达格局。",
        ],
        "remedies": [
            "把正确选项与错误选项的语气差异写下来。",
            "结合例句再造两个新句子，强化迁移能力。",
        ],
        "palette": {"primary": "#a855f7", "glow": "rgba(168,85,247,0.35)"},
    },
}


GAME_MODES: Dict[str, Dict[str, Any]] = {
    "definition": {
        "label": "释义对决",
        "description": "根据题干选择最贴近的英文释义，训练阅读-写作双向理解。",
        "skill_focus": "释义精准度",
        "sample_prompt": "Select the closest meaning to the given IELTS vocabulary item.",
    },
    "synonym": {
        "label": "同义词映射",
        "description": "甄别最贴切的同义词或表达，强化口语与写作的表达多样性。",
        "skill_focus": "表达替换",
        "sample_prompt": "Identify the synonym that preserves tone and register.",
    },
    "usage": {
        "label": "语境填空",
        "description": "通过语境判断填入正确词汇，兼顾搭配与语法准确性。",
        "skill_focus": "语境运用",
        "sample_prompt": "Complete the sentence with the word that preserves meaning and tone.",
    },
}


IELTS_VOCABULARY: List[Dict[str, Any]] = [
    {
        "word": "analyze",
        "phonetic": "ˈænəˌlaɪz",
        "translation": "分析",
        "difficulty": "foundation",
        "definition": "to examine something in detail in order to explain or understand it",
        "synonyms": ["examine", "evaluate", "study"],
        "example": "Students must analyze the chart before writing their response.",
        "usage_tip": "常用于 Task 1 描述图表，强调逐步拆解。",
        "collocations": ["analyze data", "carefully analyze", "analyze trends"],
    },
    {
        "word": "beneficial",
        "phonetic": "ˌbenəˈfɪʃəl",
        "translation": "有益的",
        "difficulty": "foundation",
        "definition": "producing good or helpful results",
        "synonyms": ["advantageous", "helpful", "favorable"],
        "example": "Regular exercise is beneficial for both physical and mental health.",
        "usage_tip": "常与 to 或 for 连用，强调积极影响。",
        "collocations": ["beneficial to", "mutually beneficial", "highly beneficial"],
    },
    {
        "word": "component",
        "phonetic": "kəmˈpoʊnənt",
        "translation": "组成部分",
        "difficulty": "foundation",
        "definition": "one part of a larger system, machine, or idea",
        "synonyms": ["element", "part", "segment"],
        "example": "Transport is a crucial component of urban infrastructure.",
        "usage_tip": "可指物理部件或抽象要素。",
        "collocations": ["key component", "essential component", "component parts"],
    },
    {
        "word": "contrast",
        "phonetic": "ˈkɒntræst",
        "translation": "对比；差异",
        "difficulty": "foundation",
        "definition": "a noticeable difference between people or things",
        "synonyms": ["difference", "distinction", "juxtapose"],
        "example": "The report highlights a contrast between rural and urban lifestyles.",
        "usage_tip": "可作名词或动词，常用于比较段落。",
        "collocations": ["in contrast", "sharp contrast", "contrast A with B"],
    },
    {
        "word": "decline",
        "phonetic": "dɪˈklaɪn",
        "translation": "下降；衰退",
        "difficulty": "foundation",
        "definition": "a gradual decrease in amount, quality, or importance",
        "synonyms": ["decrease", "drop", "deteriorate"],
        "example": "The chart shows a steady decline in car usage after 2015.",
        "usage_tip": "既可指数量下降，也可指健康或质量下降。",
        "collocations": ["steady decline", "sharp decline", "decline in"],
    },
    {
        "word": "emphasize",
        "phonetic": "ˈemfəˌsaɪz",
        "translation": "强调",
        "difficulty": "foundation",
        "definition": "to give special importance to something",
        "synonyms": ["highlight", "stress", "underline"],
        "example": "The lecturer emphasized the need for critical thinking skills.",
        "usage_tip": "常搭配 that 从句或名词短语。",
        "collocations": ["emphasize the importance", "heavily emphasize", "emphasize a point"],
    },
    {
        "word": "expand",
        "phonetic": "ɪkˈspænd",
        "translation": "扩大；扩展",
        "difficulty": "foundation",
        "definition": "to become larger in size, number, or amount",
        "synonyms": ["broaden", "enlarge", "extend"],
        "example": "The company plans to expand its services into Asia.",
        "usage_tip": "可用于经济、商业或观点延伸。",
        "collocations": ["expand rapidly", "expand opportunities", "expand a business"],
    },
    {
        "word": "factor",
        "phonetic": "ˈfæktər",
        "translation": "因素",
        "difficulty": "foundation",
        "definition": "something that influences or causes a situation",
        "synonyms": ["element", "consideration", "variable"],
        "example": "Cost is a major factor when students choose accommodation.",
        "usage_tip": "多用于分析原因或结果。",
        "collocations": ["key factor", "influential factor", "factor in"],
    },
    {
        "word": "income",
        "phonetic": "ˈɪnkʌm",
        "translation": "收入",
        "difficulty": "foundation",
        "definition": "money that someone earns or receives, especially on a regular basis",
        "synonyms": ["earnings", "revenue", "salary"],
        "example": "Household income has risen steadily over the last decade.",
        "usage_tip": "注意可数/不可数语境，搭配 household, personal 等。",
        "collocations": ["income level", "disposable income", "income inequality"],
    },
    {
        "word": "trend",
        "phonetic": "trend",
        "translation": "趋势",
        "difficulty": "foundation",
        "definition": "a general direction of change or development",
        "synonyms": ["pattern", "movement", "trajectory"],
        "example": "There is a clear upward trend in renewable energy investment.",
        "usage_tip": "Task 1 图表描述高频词。",
        "collocations": ["rising trend", "follow the trend", "long-term trend"],
    },
    {
        "word": "mitigate",
        "phonetic": "ˈmɪtɪˌɡeɪt",
        "translation": "缓解；减轻",
        "difficulty": "advanced",
        "definition": "to make something less harmful, unpleasant, or serious",
        "synonyms": ["reduce", "alleviate", "lessen"],
        "example": "Planting more trees can mitigate the impact of air pollution.",
        "usage_tip": "常用于环境或风险话题。",
        "collocations": ["mitigate risks", "mitigate the impact", "mitigation strategy"],
    },
    {
        "word": "plausible",
        "phonetic": "ˈplɔːzəbl",
        "translation": "貌似合理的",
        "difficulty": "advanced",
        "definition": "seeming likely to be true or reasonable",
        "synonyms": ["reasonable", "credible", "believable"],
        "example": "The scientist proposed a plausible explanation for the anomaly.",
        "usage_tip": "常用于评估观点或假设。",
        "collocations": ["plausible argument", "highly plausible", "plausible scenario"],
    },
    {
        "word": "resilient",
        "phonetic": "rɪˈzɪliənt",
        "translation": "有弹性的；适应力强的",
        "difficulty": "advanced",
        "definition": "able to quickly recover from difficult conditions",
        "synonyms": ["tough", "adaptable", "hardy"],
        "example": "A resilient economy can absorb unexpected shocks more effectively.",
        "usage_tip": "可修饰人、系统或经济体。",
        "collocations": ["highly resilient", "resilient workforce", "remarkably resilient"],
    },
    {
        "word": "consolidate",
        "phonetic": "kənˈsɑːləˌdeɪt",
        "translation": "巩固；整合",
        "difficulty": "advanced",
        "definition": "to combine things in order to make them stronger or more effective",
        "synonyms": ["strengthen", "combine", "merge"],
        "example": "The firm consolidated its operations to reduce overheads.",
        "usage_tip": "常与 market share、power、position 搭配。",
        "collocations": ["consolidate gains", "consolidate resources", "consolidate power"],
    },
    {
        "word": "advocate",
        "phonetic": "ˈædvəkeɪt",
        "translation": "提倡；主张",
        "difficulty": "advanced",
        "definition": "to publicly support a particular cause or policy",
        "synonyms": ["support", "champion", "promote"],
        "example": "Many experts advocate adopting stricter emission standards.",
        "usage_tip": "可作动词或名词 advocate for。",
        "collocations": ["advocate for", "strong advocate", "advocate policy"],
    },
    {
        "word": "fluctuate",
        "phonetic": "ˈflʌktʃueɪt",
        "translation": "波动",
        "difficulty": "advanced",
        "definition": "to change frequently in size, amount, or quality",
        "synonyms": ["vary", "oscillate", "shift"],
        "example": "Oil prices can fluctuate dramatically within a short period.",
        "usage_tip": "常与 figures, prices, demand 搭配。",
        "collocations": ["fluctuate wildly", "seasonal fluctuations", "fluctuate around"],
    },
    {
        "word": "incentive",
        "phonetic": "ɪnˈsentɪv",
        "translation": "激励；刺激",
        "difficulty": "advanced",
        "definition": "something that encourages a person to do something",
        "synonyms": ["motivation", "stimulus", "encouragement"],
        "example": "Tax breaks provide an incentive for companies to invest in research.",
        "usage_tip": "搭配 offer/provide/financial。",
        "collocations": ["financial incentive", "strong incentive", "create incentives"],
    },
    {
        "word": "allocate",
        "phonetic": "ˈæləˌkeɪt",
        "translation": "分配",
        "difficulty": "advanced",
        "definition": "to officially give something to someone or for a particular purpose",
        "synonyms": ["distribute", "assign", "apportion"],
        "example": "The government allocated additional funds to rural healthcare.",
        "usage_tip": "常与 resources, budget, time 搭配。",
        "collocations": ["allocate resources", "allocate efficiently", "allocation plan"],
    },
    {
        "word": "sustainable",
        "phonetic": "səˈsteɪnəbl",
        "translation": "可持续的",
        "difficulty": "advanced",
        "definition": "able to continue over a period of time without causing damage",
        "synonyms": ["viable", "enduring", "renewable"],
        "example": "Sustainable development balances economic growth with environmental protection.",
        "usage_tip": "常修饰 development, solution, practice。",
        "collocations": ["sustainable growth", "environmentally sustainable", "sustainable model"],
    },
    {
        "word": "constraint",
        "phonetic": "kənˈstreɪnt",
        "translation": "限制",
        "difficulty": "advanced",
        "definition": "a limitation or restriction that controls what you can do",
        "synonyms": ["limitation", "restriction", "restraint"],
        "example": "Budget constraints forced the team to scale back the project.",
        "usage_tip": "常与 impose, face, remove 连用。",
        "collocations": ["severe constraint", "budget constraint", "remove constraints"],
    },
    {
        "word": "ubiquitous",
        "phonetic": "juːˈbɪkwɪtəs",
        "translation": "无处不在的",
        "difficulty": "expert",
        "definition": "seeming to be everywhere or in several places at the same time",
        "synonyms": ["widespread", "omnipresent", "pervasive"],
        "example": "Mobile payments have become ubiquitous in major Chinese cities.",
        "usage_tip": "常用于描述技术或文化现象的普及。",
        "collocations": ["ubiquitous presence", "increasingly ubiquitous", "almost ubiquitous"],
    },
    {
        "word": "precipitous",
        "phonetic": "prɪˈsɪpɪtəs",
        "translation": "陡峭的；骤然的",
        "difficulty": "expert",
        "definition": "sudden and dramatic, or very steep",
        "synonyms": ["steep", "abrupt", "sudden"],
        "example": "The company experienced a precipitous drop in sales after the scandal.",
        "usage_tip": "可指物理陡峭或数字骤降。",
        "collocations": ["precipitous decline", "precipitous cliffs", "precipitous fall"],
    },
    {
        "word": "alleviate",
        "phonetic": "əˈliːvieɪt",
        "translation": "缓解",
        "difficulty": "expert",
        "definition": "to make something bad such as pain or problems less severe",
        "synonyms": ["ease", "relieve", "soothe"],
        "example": "Public transport investment could alleviate traffic congestion.",
        "usage_tip": "常与 pressure, poverty, symptoms 搭配。",
        "collocations": ["alleviate pressure", "alleviate suffering", "alleviation plan"],
    },
    {
        "word": "paradigm",
        "phonetic": "ˈpærədaɪm",
        "translation": "范式；典范",
        "difficulty": "expert",
        "definition": "a typical example or model of something",
        "synonyms": ["model", "framework", "archetype"],
        "example": "The Internet created a new paradigm for information sharing.",
        "usage_tip": "常用于讨论理论或商业模式。",
        "collocations": ["new paradigm", "paradigm shift", "dominant paradigm"],
    },
    {
        "word": "infrastructure",
        "phonetic": "ˈɪnfrəˌstrʌktʃər",
        "translation": "基础设施",
        "difficulty": "expert",
        "definition": "the basic systems and services that are necessary for a country or organization",
        "synonyms": ["framework", "facilities", "foundation"],
        "example": "Reliable infrastructure is essential for economic competitiveness.",
        "usage_tip": "常与 transport, digital, public 连用。",
        "collocations": ["transport infrastructure", "infrastructure upgrade", "critical infrastructure"],
    },
    {
        "word": "repercussion",
        "phonetic": "ˌriːpərˈkʌʃən",
        "translation": "影响；反响",
        "difficulty": "expert",
        "definition": "a usually bad effect that happens after something",
        "synonyms": ["consequence", "aftermath", "impact"],
        "example": "Ignoring climate change will have severe repercussion for coastal cities.",
        "usage_tip": "常用复数，强调长期影响。",
        "collocations": ["serious repercussion", "far-reaching repercussion", "face repercussions"],
    },
    {
        "word": "substantiate",
        "phonetic": "səbˈstænʃieɪt",
        "translation": "证实",
        "difficulty": "expert",
        "definition": "to provide evidence to prove that something is true",
        "synonyms": ["prove", "validate", "corroborate"],
        "example": "The researcher had to substantiate her claims with longitudinal data.",
        "usage_tip": "学术写作高频动词。",
        "collocations": ["substantiate a claim", "substantiate evidence", "fully substantiate"],
    },
    {
        "word": "transcend",
        "phonetic": "trænˈsend",
        "translation": "超越",
        "difficulty": "expert",
        "definition": "to rise above or go beyond the limits of something",
        "synonyms": ["surpass", "exceed", "rise above"],
        "example": "Great art can transcend cultural boundaries.",
        "usage_tip": "常用于抽象主题，如文化或情感。",
        "collocations": ["transcend boundaries", "transcend limitations", "transcend expectations"],
    },
    {
        "word": "volatile",
        "phonetic": "ˈvɒlətəl",
        "translation": "不稳定的",
        "difficulty": "expert",
        "definition": "likely to change suddenly and unexpectedly, especially by getting worse",
        "synonyms": ["unstable", "unpredictable", "turbulent"],
        "example": "Investors remain cautious in such a volatile market.",
        "usage_tip": "常描述市场、局势或情绪。",
        "collocations": ["volatile market", "highly volatile", "volatile situation"],
    },
    {
        "word": "conundrum",
        "phonetic": "kəˈnʌndrəm",
        "translation": "难题",
        "difficulty": "expert",
        "definition": "a difficult problem that seems to have no solution",
        "synonyms": ["puzzle", "dilemma", "enigma"],
        "example": "Balancing economic growth with sustainability presents a policy conundrum.",
        "usage_tip": "常用于描述令人困惑的政策或伦理难题。",
        "collocations": ["policy conundrum", "moral conundrum", "solve the conundrum"],
    },
]


def _encode_payload(payload: Dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8")


def _decode_payload(payload: str) -> Dict[str, Any]:
    try:
        raw = base64.urlsafe_b64decode(payload.encode("utf-8"))
        return json.loads(raw)
    except (ValueError, json.JSONDecodeError) as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=400, detail="Invalid answer payload") from exc


def _word_pool_for_difficulty(difficulty: str) -> List[Dict[str, Any]]:
    pool = [entry for entry in IELTS_VOCABULARY if entry["difficulty"] == difficulty]
    if len(pool) < 4:
        raise HTTPException(status_code=500, detail="Not enough vocabulary items configured")
    return pool


def _pick_distractor_words(target_word: Dict[str, Any], count: int) -> List[Dict[str, Any]]:
    pool = [entry for entry in IELTS_VOCABULARY if entry["word"] != target_word["word"]]
    if len(pool) < count:
        raise HTTPException(status_code=500, detail="Insufficient distractor words configured")
    return random.sample(pool, count)


def _new_option_id() -> str:
    return f"opt-{secrets.token_hex(3)}"


def _build_definition_question(target: Dict[str, Any]) -> Dict[str, Any]:
    distractors = _pick_distractor_words(target, 3)
    option_bank: List[Tuple[str, str]] = []
    option_bank.append((target["word"], target["definition"]))
    for item in distractors:
        option_bank.append((item["word"], item["definition"]))
    random.shuffle(option_bank)

    options: List[Dict[str, Any]] = []
    correct_option_id: Optional[str] = None
    for word, definition in option_bank:
        option_id = _new_option_id()
        if word == target["word"]:
            correct_option_id = option_id
        options.append({"id": option_id, "label": definition})

    return {
        "question_type": "definition",
        "skill_focus": GAME_MODES["definition"]["skill_focus"],
        "prompt": f"请选择最贴近 IELTS 词汇「{target['word']}」的释义。",
        "options": options,
        "correct_option_id": correct_option_id,
        "strategy": "先用自己的话复述，再排除语气或范围不匹配的选项。",
        "supporting": {
            "keyword": target["word"],
            "phonetic": target.get("phonetic"),
            "translation": target.get("translation"),
            "quickTip": target.get("usage_tip"),
            "collocations": target.get("collocations", [])[:3],
        },
    }


def _build_synonym_question(target: Dict[str, Any]) -> Dict[str, Any]:
    synonyms = list(dict.fromkeys(target.get("synonyms", [])))
    if not synonyms:
        return _build_definition_question(target)

    correct_synonym = random.choice(synonyms)
    distractor_pool: List[str] = []
    for entry in IELTS_VOCABULARY:
        if entry["word"] == target["word"]:
            continue
        distractor_pool.extend(entry.get("synonyms", []))
    distractor_candidates = [
        item
        for item in dict.fromkeys(distractor_pool)
        if item.lower() != correct_synonym.lower()
    ]
    if len(distractor_candidates) < 3:
        distractor_candidates.extend([entry["word"] for entry in _pick_distractor_words(target, 3)])
    random.shuffle(distractor_candidates)
    distractors = distractor_candidates[:3]

    options: List[Dict[str, Any]] = []
    correct_option_id: Optional[str] = None
    ordered_options = [correct_synonym, *distractors]
    random.shuffle(ordered_options)
    for synonym in ordered_options:
        option_id = _new_option_id()
        if synonym == correct_synonym:
            correct_option_id = option_id
        options.append({"id": option_id, "label": synonym})

    return {
        "question_type": "synonym",
        "skill_focus": GAME_MODES["synonym"]["skill_focus"],
        "prompt": f"请选择与「{target['word']}」语气最贴近的同义词。",
        "options": options,
        "correct_option_id": correct_option_id,
        "strategy": "比较语气强度与使用场景，筛掉过于口语或过于极端的选项。",
        "supporting": {
            "keyword": target["word"],
            "phonetic": target.get("phonetic"),
            "translation": target.get("translation"),
            "quickTip": "关注搭配对象：人、政策或抽象概念。",
            "collocations": target.get("collocations", [])[:2],
        },
    }


def _build_usage_question(target: Dict[str, Any]) -> Dict[str, Any]:
    sentence = target.get("example", "")
    placeholder_sentence = sentence.replace(target["word"], "_____")
    if placeholder_sentence == sentence:
        placeholder_sentence = f"_____: {sentence}"

    distractors = _pick_distractor_words(target, 3)
    options: List[Dict[str, Any]] = []
    correct_option_id: Optional[str] = None
    word_options = [target["word"], *[item["word"] for item in distractors]]
    random.shuffle(word_options)

    for word in word_options:
        option_id = _new_option_id()
        if word == target["word"]:
            correct_option_id = option_id
        options.append({"id": option_id, "label": word})

    return {
        "question_type": "usage",
        "skill_focus": GAME_MODES["usage"]["skill_focus"],
        "prompt": f"将最恰当的词汇填入句中空格：{placeholder_sentence}",
        "options": options,
        "correct_option_id": correct_option_id,
        "strategy": "观察空格前后的搭配，判断词性与语义是否匹配。",
        "supporting": {
            "keyword": target["word"],
            "phonetic": target.get("phonetic"),
            "translation": target.get("translation"),
            "quickTip": target.get("usage_tip"),
            "collocations": target.get("collocations", [])[:2],
        },
    }


QUESTION_BUILDERS = {
    "definition": _build_definition_question,
    "synonym": _build_synonym_question,
    "usage": _build_usage_question,
}


def _ensure_mode(mode: Optional[str]) -> str:
    if mode and mode in QUESTION_BUILDERS:
        return mode
    return random.choice(list(QUESTION_BUILDERS.keys()))


def _difficulty_meta(difficulty: str) -> Dict[str, Any]:
    try:
        return DIFFICULTY_PROFILES[difficulty]
    except KeyError as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=400, detail="Unsupported difficulty level") from exc


@router.get("/game-config")
def read_game_config() -> Dict[str, Any]:
    """Return static configuration for the IELTS vocabulary module."""

    return {
        "success": True,
        "difficulties": [
            {
                "id": key,
                "label": value["label"],
                "band": value["band"],
                "description": value["description"],
                "skills": value["skills"],
                "countdown": value["countdown"],
                "score": value["score"],
                "defaultSession": value["default_session"],
                "palette": value.get("palette", {}),
            }
            for key, value in DIFFICULTY_PROFILES.items()
        ],
        "modes": [
            {
                "id": key,
                "label": value["label"],
                "description": value["description"],
                "skillFocus": value["skill_focus"],
                "samplePrompt": value["sample_prompt"],
            }
            for key, value in GAME_MODES.items()
        ],
        "sessionLengths": [5, 6, 8, 12, 15],
        "defaultDifficulty": "foundation",
        "defaultMode": "definition",
        "focusNotes": {
            diff: {
                "mantras": meta["mantras"],
                "strategy": meta["skills"][0] if meta["skills"] else "精准理解",
            }
            for diff, meta in DIFFICULTY_PROFILES.items()
        },
        "wordInventory": len(IELTS_VOCABULARY),
    }


@router.post("/generate-round")
def generate_round(payload: GenerateRoundRequest) -> Dict[str, Any]:
    """Generate a new quiz round based on difficulty and mode."""

    difficulty = payload.difficulty
    if difficulty not in DIFFICULTY_PROFILES:
        raise HTTPException(status_code=400, detail="Unsupported difficulty level")

    mode = _ensure_mode(payload.mode)
    builder = QUESTION_BUILDERS[mode]

    pool = _word_pool_for_difficulty(difficulty)
    target = random.choice(pool)
    round_id = secrets.token_hex(8)

    question = builder(target)
    correct_option_id = question.get("correct_option_id")
    if not correct_option_id:
        raise HTTPException(status_code=500, detail="Question generation failed")

    meta = _difficulty_meta(difficulty)
    answer_payload = _encode_payload(
        {
            "round_id": round_id,
            "correct_option_id": correct_option_id,
            "word": target["word"],
            "phonetic": target.get("phonetic"),
            "translation": target.get("translation"),
            "definition": target["definition"],
            "synonyms": target.get("synonyms", []),
            "example": target.get("example"),
            "usage_tip": target.get("usage_tip"),
            "collocations": target.get("collocations", []),
            "difficulty": difficulty,
            "mode": mode,
            "skill_focus": question.get("skill_focus"),
        }
    )

    insight = {
        "mantra": random.choice(meta["mantras"]),
        "strategy": question.get("strategy"),
        "difficultyLabel": meta["label"],
        "modeLabel": GAME_MODES[mode]["label"],
        "previousOutcome": payload.previous_outcome,
    }

    return {
        "success": True,
        "round": {
            "roundId": round_id,
            "difficulty": difficulty,
            "mode": mode,
            "questionType": question["question_type"],
            "skillFocus": question.get("skill_focus"),
            "prompt": question["prompt"],
            "options": question["options"],
            "answerPayload": answer_payload,
            "countdownSeconds": meta["countdown"],
            "supporting": question.get("supporting", {}),
        },
        "insight": insight,
    }


@router.post("/verify-answer")
def verify_answer(payload: VerifyRoundRequest) -> Dict[str, Any]:
    """Verify the learner's answer and return coaching feedback."""

    answer_data = _decode_payload(payload.answer_payload)
    if answer_data.get("round_id") != payload.round_id:
        raise HTTPException(status_code=400, detail="Round mismatch")

    difficulty = answer_data.get("difficulty")
    meta = _difficulty_meta(difficulty)

    correct_option_id = answer_data.get("correct_option_id")
    selected_option_id = payload.selected_option_id

    outcome: str
    if selected_option_id is None:
        outcome = "timeout"
        is_correct = False
    else:
        is_correct = selected_option_id == correct_option_id
        outcome = "correct" if is_correct else "incorrect"

    score_scheme = meta["score"]
    if outcome == "correct":
        score_delta = score_scheme["correct"]
    elif outcome == "timeout":
        score_delta = score_scheme["timeout"]
    else:
        score_delta = score_scheme["incorrect"]

    detail = {
        "word": answer_data.get("word"),
        "phonetic": answer_data.get("phonetic"),
        "translation": answer_data.get("translation"),
        "definition": answer_data.get("definition"),
        "synonyms": answer_data.get("synonyms", []),
        "example": answer_data.get("example"),
        "usageTip": answer_data.get("usage_tip"),
        "collocations": answer_data.get("collocations", []),
        "skillFocus": answer_data.get("skill_focus"),
    }

    if is_correct:
        summary = random.choice(meta["celebrations"]).replace("这一题", f"「{detail['word']}」")
        next_step = "尝试在下一题更快锁定语义细节。"
        micro_hint = f"巩固搭配：{', '.join(detail['collocations'][:2])}" if detail["collocations"] else "继续保持语境敏感度。"
    else:
        summary = (
            f"正确选项应为与「{detail['word']}」匹配的释义/词汇。"
            if outcome == "timeout"
            else f"正确答案揭示了「{detail['word']}」的核心语义：{detail['definition']}。"
        )
        next_step = random.choice(meta["remedies"])
        micro_hint = (
            f"记忆提示：{detail['word']} → {', '.join(detail['synonyms'][:2])}" if detail["synonyms"] else "结合例句重建语境。"
        )

    return {
        "success": True,
        "correct": is_correct,
        "outcome": outcome,
        "scoreDelta": score_delta,
        "correctOptionId": correct_option_id,
        "detail": detail,
        "feedback": {
            "summary": summary,
            "nextStep": next_step,
            "microHint": micro_hint,
        },
    }
