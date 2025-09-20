"""FastAPI router powering the IELTS study system feature.

The router exposes read-only configuration endpoints and lightweight planning
helpers that orchestrate the IELTS listening, speaking, reading and writing
modules.  Business logic is intentionally declarative so the feature can evolve
without impacting other backend modules.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import re
from typing import Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, conint

router = APIRouter(prefix="/ielts", tags=["IELTS Study System"])

SkillName = Literal["listening", "speaking", "reading", "writing"]
TARGET_BANDS = {"5.5": 5.5, "6.5": 6.5, "7.5+": 7.5}


STAGE_LIBRARY: Dict[str, Dict[str, object]] = {
    "foundation": {
        "id": "foundation",
        "label": "入门衔接",
        "summary": "针对语言基础较弱或首次接触雅思的学习者，目标是构建稳定的语音语感和核心语法框架。",
        "base_weeks": 6,
        "intensity_hours": "每周 12-15 小时",
        "skill_weights": {
            "listening": 0.28,
            "speaking": 0.18,
            "reading": 0.26,
            "writing": 0.28,
        },
        "skill_focus": {
            "listening": [
                "每日 15 分钟语音热身，建立语音辨识能力",
                "分段精听真题录音并使用逐句播放功能反复跟读",
                "通过自动转写比对，记录高频错词并加入生词本",
            ],
            "speaking": [
                "围绕 Part1 高频话题进行 1 分钟限时输出",
                "使用语音识别生成实时字幕，修正发音与语调",
                "模仿高分范例的句式，积累描述性词汇",
            ],
            "reading": [
                "精读短篇文章，标注核心句式与逻辑连接词",
                "练习段落主旨题，结合即点即义功能快速查词",
                "建立错题本，按题型记录失分原因",
            ],
            "writing": [
                "拆解 Task1 数据描述框架，熟悉常用表达",
                "以 30 分钟为单位练习小作文草稿，使用 AI 批改纠错",
                "整理常见句式模板，完善语法基础",
            ],
        },
        "milestones": [
            "完成至少 20 条精听笔记并整理首轮生词表",
            "掌握 8 组 Part1 高频话题的核心回答结构",
            "完成 6 篇 Task1 草稿并获得 AI 批改评分 ≥ 5.0",
        ],
        "checkpoint": "通过阶段测评，四项分数均达到 5.0 左右即可转入基础夯实阶段",
        "progress_metrics": {
            "listening": "分段听写准确率 ≥ 70%",
            "speaking": "语音识别正确率 ≥ 85%，语法大错≤1",
            "reading": "词汇推断题正确率 ≥ 60%",
            "writing": "AI 批改语法评分 ≥ 5.0",
        },
    },
    "core": {
        "id": "core",
        "label": "基础夯实",
        "summary": "面向 5.0-5.5 水平学习者，重点解决信息提取效率与句型多样性不足的问题。",
        "base_weeks": 5,
        "intensity_hours": "每周 14-16 小时",
        "skill_weights": {
            "listening": 0.26,
            "speaking": 0.22,
            "reading": 0.26,
            "writing": 0.26,
        },
        "skill_focus": {
            "listening": [
                "以段落为单位完成精听 + 听写比对，强化信息捕捉",
                "每周 2 次跟读练习并查看发音准确度评分",
                "错词复盘结合 TTS 朗读，巩固拼写与语音映射",
            ],
            "speaking": [
                "进入模拟考试模式，完成 Part2 2 分钟陈述",
                "根据 AI 考官反馈调整语法与词汇多样性",
                "积累高分连接词和衔接句，提升连贯性",
            ],
            "reading": [
                "精读与略读结合，控制定位时间",
                "使用高亮提示快速定位同义替换",
                "针对匹配题、判断题建立专属解题流程",
            ],
            "writing": [
                "每周输出 1 篇 Task2 草稿，聚焦结构与论证",
                "比对高分范文，总结段落展开方式",
                "扩充主题词汇表，记录可替换表达",
            ],
        },
        "milestones": [
            "完成 3 套听力真题并将错词同步至词汇手册",
            "建立 12 个 Part2 主题的故事素材库",
            "完成 4 套阅读精读笔记，错题分类清晰",
        ],
        "checkpoint": "模考分数稳定在 6.0 左右后，进入进阶突破阶段",
        "progress_metrics": {
            "listening": "听力 Section 2 正确率 ≥ 70%",
            "speaking": "AI 反馈中语法错误率下降 30%",
            "reading": "定位题平均耗时 ≤ 75 秒",
            "writing": "Task2 逻辑结构得分 ≥ 6.0",
        },
    },
    "advanced": {
        "id": "advanced",
        "label": "进阶突破",
        "summary": "面向 6.0+ 学习者，聚焦难题突破与语言高级感的打造。",
        "base_weeks": 4,
        "intensity_hours": "每周 16-18 小时",
        "skill_weights": {
            "listening": 0.25,
            "speaking": 0.25,
            "reading": 0.25,
            "writing": 0.25,
        },
        "skill_focus": {
            "listening": [
                "全真模考 + 精听复盘组合，锻炼注意力切换",
                "围绕同义替换和细节捕捉建立听力笔记模板",
                "练习高难度跟读，关注语调和断句",
            ],
            "speaking": [
                "Part3 深度问答演练，突出论证深度",
                "利用 AI 考官反馈打磨高级词汇与句型",
                "模拟考试模式下强化时间管理与逻辑衔接",
            ],
            "reading": [
                "强化段落信息比对，训练快速略读",
                "通过错题本追踪高难题型并二次练习",
                "拆解文章结构，积累论证框架",
            ],
            "writing": [
                "Task2 全流程 40 分钟模写，提升时间掌控",
                "针对不同题型准备替换模板和例证库",
                "AI 批改聚焦词汇多样性与高级句式",
            ],
        },
        "milestones": [
            "连续两周保持听力 Section 3 正确率 ≥ 75%",
            "完成 6 套口语模拟并获得流利度评分 ≥ 6.5",
            "阅读题型错题率降至 20% 以内",
        ],
        "checkpoint": "模考平均分达到目标分数 -0.5，即可进入冲刺拔高阶段",
        "progress_metrics": {
            "listening": "困难题型（多选/地图题）正确率 ≥ 65%",
            "speaking": "高级词汇密度 ≥ 15%",
            "reading": "每篇文章总耗时 ≤ 18 分钟",
            "writing": "Task2 词汇多样性评分 ≥ 6.5",
        },
    },
    "sprint": {
        "id": "sprint",
        "label": "冲刺拔高",
        "summary": "考试前的综合冲刺，确保状态稳定并模拟真实考场节奏。",
        "base_weeks": 3,
        "intensity_hours": "每周 18-20 小时",
        "skill_weights": {
            "listening": 0.26,
            "speaking": 0.24,
            "reading": 0.22,
            "writing": 0.28,
        },
        "skill_focus": {
            "listening": [
                "每周完成 2 套全真听力并进行错题复盘",
                "利用跟读功能保持语速和语调的敏感度",
                "重点攻克高频错词，结合词汇手册巩固",
            ],
            "speaking": [
                "隔日进行一次完整的口语模考，强化考场感",
                "复盘 AI 反馈中的弱项并即时修正",
                "打磨个性化开场白与结束语，保持自信",
            ],
            "reading": [
                "保持做题速度，复习题型策略",
                "错题本每日回顾，防止旧错再犯",
                "强化段落定位与关键词预测能力",
            ],
            "writing": [
                "保持 Task1+Task2 全套练习的节奏",
                "用 AI 批改确认最后的语言准确度",
                "整理高分范文亮点，确保考试前形成记忆",
            ],
        },
        "milestones": [
            "完成 3 套全真模考并生成完整分数报告",
            "四项能力雷达图趋于均衡，无明显短板",
            "建立考试日前三天的维持方案（睡眠、复习、模拟）",
        ],
        "checkpoint": "模考成绩达到或高于目标分数，进入考前维护阶段",
        "progress_metrics": {
            "listening": "全真模考波动 ≤ 1.0 分",
            "speaking": "AI 流利度 ≥ 7.0",
            "reading": "错题率维持在 15% 以内",
            "writing": "Task2 总分稳定在目标分数",
        },
    },
}

TARGET_RECOMMENDATIONS: Dict[str, Dict[str, object]] = {
    "5.5": {
        "score_profile": "建议将重点放在基础语音、语法与核心词汇积累上，逐步提升做题速度。",
        "listening_focus": "坚持精听+跟读结合，利用自动转写确认基础听辨能力。",
        "speaking_focus": "建立常见话题回答模板，确保语法准确率。",
        "reading_focus": "优先掌握段落主旨题与信息匹配题的定位方法。",
        "writing_focus": "Task1 描述准确，Task2 避免跑题，句型以清晰简洁为主。",
        "mock_test_frequency": "每 3 周一次阶段性模考，关注时间管理。",
        "ai_feedback_expectation": "重点跟踪发音准确度和语法纠错建议。",
    },
    "6.5": {
        "score_profile": "需要在保持基础稳定的同时，提升词汇表达和论证深度。",
        "listening_focus": "关注 Section 3&4 的细节信息与同义替换能力。",
        "speaking_focus": "通过 AI 反馈提高词汇多样性与逻辑连贯。",
        "reading_focus": "强化推断题与句子插入题的准确率。",
        "writing_focus": "确保 Task2 结构完整，段内论证充分，有清晰的段首主题句。",
        "mock_test_frequency": "每 2 周一次全真模考，记录波动区间。",
        "ai_feedback_expectation": "同时关注语法、词汇和逻辑结构维度的改进。",
    },
    "7.5+": {
        "score_profile": "需要高强度训练与细节打磨，目标是突破高级表达与稳定度。",
        "listening_focus": "保持高频全真模考，精听高难度题型并追求接近满分。",
        "speaking_focus": "强化论证深度与地道表达，练习考场随机应变能力。",
        "reading_focus": "控制全篇耗时 55 分钟以内，保证复杂题型的准确率。",
        "writing_focus": "Task2 目标达到 7.5+，关注语篇衔接、论证力度与词汇高级感。",
        "mock_test_frequency": "每周一次全真模考并输出完整分析报告。",
        "ai_feedback_expectation": "需要细化到句法复杂度、词汇多样性和论证逻辑的高阶反馈。",
    },
}

DEFAULT_DAILY_TEMPLATE = {
    "morning": [
        "15 分钟发音热身 + 前一天错词复习",
        "听力精听或阅读精读 45 分钟",
    ],
    "afternoon": [
        "写作或口语主攻训练 60 分钟",
        "题型专项练习 45 分钟",
    ],
    "evening": [
        "当天错题与 AI 反馈复盘",
        "安排次日学习任务并打卡进度",
    ],
}

SKILL_LIBRARY: Dict[str, Dict[str, object]] = {
    "listening": {
        "title": "听力训练模块",
        "core_features": [
            "真题音频导入与逐句/逐段播放",
            "听写对比与自动转写，识别错词",
            "错词统计与个人生词本自动生成",
            "跟读功能 + 发音准确度评分",
        ],
        "training_modes": [
            "精听模式：逐句播放并配合自动转写比对",
            "泛听模式：整段播放并生成摘要，考查全局理解",
            "错词巩固：同步到词汇手册，进行间隔复习",
        ],
        "data_points": [
            "精听准确率与错词类型分布",
            "跟读打分趋势（发音/语调/连读）",
            "真题完成时间与正确率",
        ],
    },
    "speaking": {
        "title": "口语练习模块",
        "core_features": [
            "雅思口语题库（Part1/Part2/Part3）",
            "模拟考试模式：计时问答与自动录音",
            "语音识别转写与实时字幕",
            "AI 考官反馈（发音、流利度、语法、词汇）",
        ],
        "training_modes": [
            "限时单题演练：1-2 分钟输出",
            "全套模拟：按考场流程自动计时与录音",
            "AI 回放：查看逐句字幕与纠错建议",
        ],
        "data_points": [
            "发音准确度、语法错误密度、词汇多样性",
            "Part2 结构完整度评分",
            "回答时长与停顿分布",
        ],
    },
    "reading": {
        "title": "阅读理解模块",
        "core_features": [
            "精读/略读双模式切换",
            "自动批改并标注定位句",
            "单词高亮提示（即点即义）",
            "错题本按题型与难度归类",
        ],
        "training_modes": [
            "精读拆解：突出长难句结构与逻辑",
            "略读冲刺：限定时间完成整篇文章",
            "错题重做：根据题型再次演练并追踪准确率",
        ],
        "data_points": [
            "不同题型正确率与平均耗时",
            "关键生词与同义替换清单",
            "阅读速度（词/分钟）趋势",
        ],
    },
    "writing": {
        "title": "写作练习模块",
        "core_features": [
            "Task1/Task2 作文输入与版本管理",
            "AI 批改（结构、逻辑、语法、词汇）",
            "高分范文对照与亮点提示",
            "常用句式与模板推荐",
        ],
        "training_modes": [
            "结构梳理：拆解段落主题与逻辑",
            "限时模写：Task2 全流程 40 分钟训练",
            "AI 精修：根据建议二次润色并追踪改动",
        ],
        "data_points": [
            "段落逻辑得分与语法准确率",
            "词汇丰富度与搭配错误",
            "不同题型（对比、流程、观点）的表现",
        ],
    },
}

SUPPORTING_TOOLS = [
    {
        "id": "progress-tracker",
        "name": "学习进度追踪",
        "description": "提供学习日历、目标完成度可视化以及学习曲线趋势图。",
        "capabilities": [
            "可视化学习日历与累计时长",
            "按技能展示达标进度与差距",
            "生成阶段性总结和提醒",
        ],
    },
    {
        "id": "review-engine",
        "name": "错题本与复习机制",
        "description": "自动整理错题与高频错词，结合间隔复习算法推送复习任务。",
        "capabilities": [
            "题型/难度双维度分类",
            "自动生成复习提醒与巩固练习",
            "与词汇手册联动形成个性化材料",
        ],
    },
    {
        "id": "mock-exam-center",
        "name": "模拟考试中心",
        "description": "支持全真模考、计时与自动评分，生成分析报告。",
        "capabilities": [
            "听说读写全流程计时",
            "自动整合 AI 批改与评分",
            "输出雷达图与弱项分析",
        ],
    },
    {
        "id": "vocabulary-lab",
        "name": "词汇手册",
        "description": "整合个人错词与雅思高频词，提供发音、例句与间隔复习。",
        "capabilities": [
            "自动同步听力错词与阅读生词",
            "TTS 发音与真题例句",
            "灵活设定复习节奏与提醒",
        ],
    },
    {
        "id": "insight-reports",
        "name": "学习报告与反馈",
        "description": "生成四项能力雷达图、弱项分析与提升建议。",
        "capabilities": [
            "跨阶段对比，识别波动",
            "针对弱项推送专项任务",
            "提供下一阶段学习建议",
        ],
    },
]

MOCK_EXAMS = [
    {
        "id": "standard-full",
        "title": "全真模拟套题",
        "duration_minutes": 170,
        "recommended_stage": ["core", "advanced", "sprint"],
        "score_focus": "用于评估综合水平，生成详细分数报告。",
        "report_contents": [
            "四项能力得分与目标差距",
            "时间管理分析",
            "高频错误词汇与题型预警",
        ],
    },
    {
        "id": "speaking-intensive",
        "title": "口语强化模考",
        "duration_minutes": 15,
        "recommended_stage": ["core", "advanced", "sprint"],
        "score_focus": "突出发音、流利度与词汇多样性评分。",
        "report_contents": [
            "AI 考官逐句点评",
            "语法与词汇建议",
            "情景化改进建议",
        ],
    },
    {
        "id": "writing-dual",
        "title": "写作双任务演练",
        "duration_minutes": 90,
        "recommended_stage": ["advanced", "sprint"],
        "score_focus": "检验 Task1/Task2 时间掌控与结构合理性。",
        "report_contents": [
            "结构与逻辑评分",
            "语法准确性与词汇密度",
            "高分范文对照分析",
        ],
    },
]

VOCABULARY_DECKS: Dict[str, Dict[str, object]] = {
    "foundation": {
        "level": "A2-B1",
        "focus": "核心场景词汇与生活化表达",
        "spacing_strategy": "2-2-3-5 天间隔复习",
        "bundle_size": 20,
        "activities": [
            "跟读 + TTS 发音记忆",
            "语境例句理解",
            "拼写听写双模式巩固",
        ],
    },
    "core": {
        "level": "B1-B2",
        "focus": "题型高频词与搭配",
        "spacing_strategy": "1-2-4-6 天间隔复习",
        "bundle_size": 25,
        "activities": [
            "词根词缀拆解",
            "阅读同义替换练习",
            "结合写作模板造句",
        ],
    },
    "advanced": {
        "level": "B2-C1",
        "focus": "学术词汇与表达升级",
        "spacing_strategy": "1-3-5-7 天间隔复习",
        "bundle_size": 25,
        "activities": [
            "主题词汇扩展",
            "口语即兴应用",
            "写作多样化替换训练",
        ],
    },
    "sprint": {
        "level": "C1",
        "focus": "高分搭配与考前必背",
        "spacing_strategy": "1-2-3-4 天短周期巩固",
        "bundle_size": 30,
        "activities": [
            "口语模考实时调用",
            "写作段落速记",
            "听力错词最后冲刺",
        ],
    },
}

AI_INTEGRATIONS = {
    "asr": {
        "purpose": "口语录音自动转写、发音分析与听写对比",
        "service_boundary": "通过独立 ASR 服务接口接入，支持后续替换供应商",
        "data_output": ["逐句文本", "发音评分", "停顿/语速分析"],
    },
    "tts": {
        "purpose": "词汇与范文朗读、听力精听辅助",
        "service_boundary": "TTS 服务独立部署，通过统一音频缓存层供前端调用",
        "data_output": ["多语速音频", "语音标注"],
    },
    "llm": {
        "purpose": "写作批改、口语反馈与个性化学习建议",
        "service_boundary": "统一的 LLM Gateway 负责路由至不同大模型",
        "data_output": ["结构点评", "语言建议", "定制任务列表"],
    },
    "analytics": {
        "purpose": "学习行为统计与报告生成",
        "service_boundary": "事件流进入数据仓库，支持进度备份与恢复",
        "data_output": ["学习曲线", "词汇掌握度", "模考波动"]
    },
}


LISTENING_PRACTICE = {
    "id": "listening-transport",
    "title": "公共交通咨询",
    "description": "模拟雅思听力 Section 1：新生向公交中心咨询最划算的票种与班车时间。",
    "context": "建议先浏览题目关键词，再带着问题听/读对话。",
    "audio_summary": "Student 和交通服务人员讨论月票、首班车时间以及机场班车预订要求的对话。",
    "audio_duration_seconds": 85,
    "key_phrases": [
        {"phrase": "student monthly pass", "note": "学生月票，工作日与周末均可无限次乘坐"},
        {"phrase": "first bus at 6:15 a.m.", "note": "工作日首班车时间"},
        {"phrase": "shuttle every Saturday 8 a.m.", "note": "机场班车发车频率"},
        {"phrase": "book at least two days in advance", "note": "预约班车需要提前两天"},
    ],
    "audio_script": [
        {
            "speaker": "Student",
            "text": "Hello, I'm new to the city and I need some advice about the bus passes.",
        },
        {"speaker": "Agent", "text": "Of course. Are you staying here long term?"},
        {
            "speaker": "Student",
            "text": "I'll be studying at the college for the next three months.",
        },
        {
            "speaker": "Agent",
            "text": "Then the student monthly pass would be the best value. It gives unlimited travel on weekdays and weekends.",
        },
        {
            "speaker": "Student",
            "text": "That sounds good. What time do the first buses leave campus in the morning?",
        },
        {
            "speaker": "Agent",
            "text": "The earliest bus on weekdays is at 6:15 a.m., and on Sundays it starts at 7:30 a.m.",
        },
        {
            "speaker": "Student",
            "text": "I also heard there is a shuttle to the airport.",
        },
        {
            "speaker": "Agent",
            "text": "Yes, it runs every Saturday at 8 a.m. You need to book at least two days in advance.",
        },
    ],
    "questions": [
        {
            "id": "l1",
            "type": "multiple-choice",
            "question": "学生最终选择的票种是什么？",
            "options": [
                {"key": "A", "text": "一周通票"},
                {"key": "B", "text": "月度学生票"},
                {"key": "C", "text": "单次票"},
            ],
            "answer": "B",
            "explanation": "对话中工作人员建议购买月度学生票，并说明其最划算。",
        },
        {
            "id": "l2",
            "type": "multiple-choice",
            "question": "工作日校园首班车的出发时间是？",
            "options": [
                {"key": "A", "text": "6:15 a.m."},
                {"key": "B", "text": "6:45 a.m."},
                {"key": "C", "text": "7:30 a.m."},
            ],
            "answer": "A",
            "explanation": "工作人员明确提到工作日首班车在 6:15 出发。",
        },
        {
            "id": "l3",
            "type": "multiple-choice",
            "question": "机场班车的运行频率是？",
            "options": [
                {"key": "A", "text": "每天上午"},
                {"key": "B", "text": "每周六上午"},
                {"key": "C", "text": "仅在考试周"},
            ],
            "answer": "B",
            "explanation": "工作人员提到班车在每周六早上 8 点运行。",
        },
        {
            "id": "l4",
            "type": "multiple-choice",
            "question": "机场班车需要提前多久预约？",
            "options": [
                {"key": "A", "text": "至少提前 1 天"},
                {"key": "B", "text": "至少提前 2 天"},
                {"key": "C", "text": "至少提前 5 天"},
            ],
            "answer": "B",
            "explanation": "对话最后指出需提前两天预订班车座位。",
        },
    ],
    "tips": [
        "先读题目定位关键词（票种、时间、频率），听时重点捕捉对应信息。",
        "注意数字表达的差异（six fifteen 与 six fifty）。",
        "做完后可跟读对话，模仿节奏与语调。",
    ],
    "next_steps": [
        "重新听一遍并尝试记笔记，检验是否能快速提取关键信息。",
        "用自己的话复述对话内容，训练口语复述能力。",
    ],
}


READING_PRACTICE = {
    "id": "reading-coworking",
    "title": "共享办公空间的发展",
    "description": "模拟雅思阅读 Section 2，文章探讨共享办公模式兴起的原因与未来趋势。",
    "passage": [
        "Paragraph A: Co-working spaces have grown rapidly over the last decade as start-ups sought flexible lease agreements. Instead of committing to long-term contracts, entrepreneurs could rent a desk for a month and scale up or down whenever necessary.",
        "Paragraph B: Beyond cost savings, companies value the community element. Managers note that informal events in these spaces encourage cross-team collaboration and provide access to professional workshops that would otherwise be unaffordable.",
        "Paragraph C: Analysts predict that hybrid working will keep the demand steady. However, operators must adapt by offering quieter zones, advanced video-conferencing facilities and membership models tailored to corporate teams rather than only freelancers.",
    ],
    "questions": [
        {
            "id": "r1",
            "type": "multiple-choice",
            "question": "Paragraph A 表明共享办公空间快速增长的主要原因是什么？",
            "options": [
                {"key": "A", "text": "租赁合同灵活，方便扩张或缩减"},
                {"key": "B", "text": "设备比传统办公室更先进"},
                {"key": "C", "text": "政府给予税收减免"},
            ],
            "answer": "A",
            "explanation": "段落强调初创企业能灵活租用工位，随业务规模调整。",
        },
        {
            "id": "r2",
            "type": "multiple-choice",
            "question": "Paragraph B 提到企业看重共享办公空间的什么优势？",
            "options": [
                {"key": "A", "text": "空间装修更具现代感"},
                {"key": "B", "text": "社区活动促进团队合作"},
                {"key": "C", "text": "租金更低"},
            ],
            "answer": "B",
            "explanation": "该段突出社区活动带来的协作机会和专业工作坊。",
        },
        {
            "id": "r3",
            "type": "multiple-choice",
            "question": "Paragraph C 预测运营者未来需要做什么？",
            "options": [
                {"key": "A", "text": "停止服务企业客户"},
                {"key": "B", "text": "增加安静区域和远程会议设施"},
                {"key": "C", "text": "仅服务自由职业者"},
            ],
            "answer": "B",
            "explanation": "分析师认为需提供安静区、视频会议设备以及企业会员方案。",
        },
    ],
    "tips": [
        "先浏览题干关键词，定位到对应段落，再精读相关句子。",
        "注意题干与原文的同义替换（例如 flexible lease 与租赁合同灵活）。",
        "答题后总结段落主旨，训练摘要能力。",
    ],
    "next_steps": [
        "尝试用一句话概括每个段落的核心观点。",
        "记录出现的学术词汇并造句，加强写作与口语输出。",
    ],
}


VOCABULARY_PRACTICE = {
    "id": "vocabulary-growth",
    "title": "词汇精准辨析",
    "description": "围绕雅思常见的学术词汇，练习辨别最贴切的释义或近义替换。",
    "questions": [
        {
            "id": "v1",
            "type": "multiple-choice",
            "question": "单词 “allocate” 最接近的含义是？",
            "options": [
                {"key": "A", "text": "储存"},
                {"key": "B", "text": "分配"},
                {"key": "C", "text": "忽视"},
            ],
            "answer": "B",
            "explanation": "allocate 指按照计划分配资源。",
        },
        {
            "id": "v2",
            "type": "multiple-choice",
            "question": "“mitigate” 的含义是？",
            "options": [
                {"key": "A", "text": "使……恶化"},
                {"key": "B", "text": "使……缓和"},
                {"key": "C", "text": "详细阐述"},
            ],
            "answer": "B",
            "explanation": "mitigate 表示减轻或缓和不利影响。",
        },
        {
            "id": "v3",
            "type": "multiple-choice",
            "question": "选择与 “robust” 含义最接近的一项。",
            "options": [
                {"key": "A", "text": "脆弱的"},
                {"key": "B", "text": "强健的"},
                {"key": "C", "text": "孤立的"},
            ],
            "answer": "B",
            "explanation": "robust 描述体系或论点扎实、强健。",
        },
        {
            "id": "v4",
            "type": "multiple-choice",
            "question": "在写作中，用哪个词可替换 “important”？",
            "options": [
                {"key": "A", "text": "negligible"},
                {"key": "B", "text": "significant"},
                {"key": "C", "text": "trivial"},
            ],
            "answer": "B",
            "explanation": "significant 在学术语境中表示重要、显著。",
        },
    ],
    "tips": [
        "回忆单词在真题中的语境，判断搭配是否自然。",
        "尝试用选出的词造句，巩固搭配记忆。",
    ],
    "next_steps": [
        "将易混淆词汇整理到词汇手册并标注例句。",
        "用这些词写一个 100 词的短段落，练习灵活运用。",
    ],
}


SPEAKING_PRACTICE = {
    "id": "speaking-weekend",
    "title": "口语主题：团队协作与周末活动",
    "part1": {
        "description": "热身问题，关注生活习惯与团队协作经历。",
        "questions": [
            "你通常周末会做些什么来放松自己？",
            "你喜欢独自完成任务还是与他人合作？",
            "你是否参加过社区组织的活动？那是什么？",
        ],
        "sample_sentence_starters": [
            "I usually spend my weekends...",
            "Working with others helps me...",
            "One community activity I joined was...",
        ],
    },
    "part2": {
        "task": "描述一次你参与的小组项目或活动，并说明它为何让你印象深刻。",
        "prep_seconds": 60,
        "speaking_seconds": 120,
        "bullet_points": [
            "项目或活动的背景",
            "你在团队中的角色",
            "遇到的挑战以及如何解决",
            "你从中学到的经验",
        ],
        "language_tips": [
            "使用 firstly, moreover, as a result 等衔接词维持逻辑。",
            "描述感受时结合形容词（rewarding, demanding, eye-opening）。",
        ],
        "model_outline": [
            "开场点题并介绍背景",
            "分两到三个要点描述任务",
            "总结团队收获或个人反思",
        ],
    },
    "part3": {
        "description": "深入讨论团队协作在社会中的影响。",
        "questions": [
            "为什么越来越多的公司强调跨部门合作？",
            "在线协作工具会如何改变未来的团队合作方式？",
            "政府是否应该资助社区团队项目？为什么？",
        ],
        "idea_bank": [
            "跨部门合作可以整合资源并激发创新。",
            "数字工具降低沟通成本，但需要培训确保有效使用。",
            "公共资金可提升社区凝聚力，但需透明管理。",
        ],
    },
    "follow_up_prompts": [
        "尝试录下自己的回答，回放并记录停顿和重复的词。",
        "将 Part 2 的回答整理成提纲，再转化为写作段落。",
    ],
}


WRITING_PRACTICE = {
    "id": "writing-remote-work",
    "task_type": "Task 2",
    "question": "More people are choosing to work remotely. Do the advantages of working from home outweigh the disadvantages?",
    "background": "题目要求讨论远程办公的利弊，可采用正反对比或权衡结构。",
    "brainstorm_points": [
        "优势：节省通勤时间、提升工作自主性、企业节约办公成本。",
        "劣势：社交隔离、沟通效率下降、家庭环境可能造成干扰。",
        "可以结合实例说明远程办公对不同行业员工的影响。",
    ],
    "structure": [
        "引言：改写题目并给出总体立场。",
        "主体段 1：优势论证，使用数据或案例支持。",
        "主体段 2：劣势论证，提出缓解策略。",
        "结论：重申观点，可提出平衡建议。",
    ],
    "checklist": [
        "字数不少于 250 词。",
        "每段都有清晰主题句。",
        "使用至少 3 个高级衔接词。",
        "提供例证或数据支撑论点。",
    ],
    "useful_phrases": [
        "One compelling advantage is that...",
        "This can be mitigated by...",
        "From a broader perspective...",
    ],
    "tips": [
        "写作前用 5 分钟列提纲，确保论点均衡。",
        "写完后按照 checklist 自查，再进行润色。",
    ],
}


INTERACTIVE_PRACTICE = {
    "listening": LISTENING_PRACTICE,
    "reading": READING_PRACTICE,
    "vocabulary": VOCABULARY_PRACTICE,
    "speaking": SPEAKING_PRACTICE,
    "writing": WRITING_PRACTICE,
}


CONNECTOR_WORDS = {
    "however",
    "therefore",
    "moreover",
    "furthermore",
    "nevertheless",
    "consequently",
    "meanwhile",
    "additionally",
    "in addition",
    "as a result",
    "on the other hand",
    "for example",
    "for instance",
    "in contrast",
    "overall",
}


ACADEMIC_VOCABULARY = {
    "significant",
    "sustainable",
    "contribute",
    "mitigate",
    "allocate",
    "enhance",
    "infrastructure",
    "productivity",
    "flexibility",
    "collaboration",
    "consequence",
    "innovation",
    "efficiency",
    "robust",
    "facilitate",
}


FILLER_WORDS = {"um", "uh", "erm", "er", "like"}
FILLER_PHRASES = {"you know", "sort of", "kind of"}


class SkillScores(BaseModel):
    """User skill scores in IELTS scale."""

    listening: float = Field(..., ge=0.0, le=9.0)
    speaking: float = Field(..., ge=0.0, le=9.0)
    reading: float = Field(..., ge=0.0, le=9.0)
    writing: float = Field(..., ge=0.0, le=9.0)


class AssessmentRequest(BaseModel):
    current_scores: SkillScores
    target_band: Literal["5.5", "6.5", "7.5+"]
    weekly_study_hours: conint(ge=5, le=60) = Field(
        ..., description="Available study hours per week"
    )
    weeks_until_exam: conint(ge=1, le=52)
    preferred_focus: Optional[List[SkillName]] = Field(
        None, description="Optional skills that the learner wants to emphasise"
    )


class ProgressReviewRequest(BaseModel):
    baseline_scores: SkillScores
    latest_scores: SkillScores
    weeks_elapsed: conint(ge=1, le=52)
    total_logged_hours: conint(ge=1, le=800)
    completed_mock_tests: Optional[conint(ge=0, le=40)] = 0


class MultipleChoiceAnswer(BaseModel):
    question_id: str
    answer: str = Field(..., min_length=1)


class MultipleChoiceSubmission(BaseModel):
    answers: List[MultipleChoiceAnswer]


class WritingFeedbackRequest(BaseModel):
    response: str = Field(..., min_length=20, description="Learner's writing response")


class SpeakingFeedbackRequest(BaseModel):
    transcript: str = Field(..., min_length=20, description="Learner's speaking transcript or笔记")
    focus_part: Optional[Literal["part1", "part2", "part3"]] = "part2"


def _average_score(scores: SkillScores) -> float:
    values = scores.dict().values()
    return round(sum(values) / len(values), 2)


def _min_score(scores: SkillScores) -> float:
    return min(scores.dict().values())


def _phase_sequence(scores: SkillScores, target_score: float) -> List[str]:
    avg = _average_score(scores)
    min_score = _min_score(scores)
    gap = max(target_score - avg, 0)
    phases: List[str] = []

    if gap > 1.4 or min_score < 4.5:
        phases.append("foundation")
    if gap > 1.0 or min_score < 5.5:
        phases.append("core")
    if gap > 0.6 or min_score < 6.0:
        phases.append("advanced")
    phases.append("sprint")

    ordered = []
    for stage in ["foundation", "core", "advanced", "sprint"]:
        if stage in phases and stage not in ordered:
            ordered.append(stage)
    return ordered


def _allocate_weeks(phases: List[str], total_weeks: int) -> Dict[str, int]:
    if not phases:
        return {}
    if total_weeks < len(phases):
        phases = phases[-total_weeks:]

    base_total = sum(int(STAGE_LIBRARY[p]["base_weeks"]) for p in phases)
    allocations = [
        [
            stage,
            max(
                1,
                int(round(total_weeks * (STAGE_LIBRARY[stage]["base_weeks"] / base_total))),
            ),
        ]
        for stage in phases
    ]
    diff = total_weeks - sum(value for _, value in allocations)
    idx = 0
    while diff != 0 and allocations:
        stage, weeks = allocations[idx % len(allocations)]
        if diff > 0:
            allocations[idx % len(allocations)][1] = weeks + 1
            diff -= 1
        elif weeks > 1:
            allocations[idx % len(allocations)][1] = weeks - 1
            diff += 1
        idx += 1
    return {stage: weeks for stage, weeks in allocations}


def _build_weekly_schedule(stage: str, weekly_hours: int) -> List[Dict[str, object]]:
    stage_info = STAGE_LIBRARY[stage]
    weights = stage_info["skill_weights"]
    allocation = []
    total_hours = 0.0
    for skill, weight in weights.items():
        hours = round(weekly_hours * weight, 1)
        total_hours += hours
        allocation.append({
            "skill": skill,
            "hours": hours,
            "focus": stage_info["skill_focus"][skill],
        })
    # Adjust rounding drift so the sum equals weekly_hours approximately.
    if allocation:
        drift = round(weekly_hours - total_hours, 1)
        if abs(drift) >= 0.1:
            allocation[0]["hours"] = round(allocation[0]["hours"] + drift, 1)
    return allocation


def _render_phase_payload(stage: str, weeks: int, weekly_hours: int) -> Dict[str, object]:
    stage_info = STAGE_LIBRARY[stage]
    weekly_schedule = _build_weekly_schedule(stage, weekly_hours)
    return {
        "stage": stage,
        "label": stage_info["label"],
        "duration_weeks": weeks,
        "intensity": stage_info["intensity_hours"],
        "summary": stage_info["summary"],
        "milestones": stage_info["milestones"],
        "checkpoint": stage_info["checkpoint"],
        "progress_metrics": stage_info["progress_metrics"],
        "weekly_schedule": weekly_schedule,
    }


def _detect_priority_skills(scores: SkillScores, preferred: Optional[List[SkillName]]) -> List[SkillName]:
    values = scores.dict()
    sorted_skills = sorted(values.items(), key=lambda item: item[1])
    priority = [skill for skill, _ in sorted_skills[:2]]
    if preferred:
        for skill in preferred:
            if skill not in priority:
                priority.append(skill)
    return priority[:4]


def _calculate_improvement(baseline: SkillScores, latest: SkillScores) -> Dict[str, float]:
    return {
        skill: round(latest.dict()[skill] - baseline.dict()[skill], 2)
        for skill in baseline.dict().keys()
    }


def _weakest_skill(scores: SkillScores) -> SkillName:
    values = scores.dict()
    return min(values, key=values.get)  # type: ignore[return-value]


def _strip_answers(practice: Dict[str, object]) -> Dict[str, object]:
    sanitized = deepcopy(practice)
    questions = sanitized.get("questions")
    if isinstance(questions, list):
        sanitized["questions"] = [
            {key: value for key, value in question.items() if key != "answer"}
            for question in questions
        ]
    return sanitized


def _get_practice_or_404(skill: str) -> Dict[str, object]:
    practice = INTERACTIVE_PRACTICE.get(skill)
    if not practice:
        raise HTTPException(status_code=404, detail="未找到对应的练习任务")
    return practice


def _evaluate_multiple_choice_practice(
    skill: str, submission: MultipleChoiceSubmission
) -> Dict[str, object]:
    practice = _get_practice_or_404(skill)
    questions = practice.get("questions", [])
    if not questions:
        raise HTTPException(status_code=400, detail="该练习暂不支持自动批改")

    answer_map = {
        answer.question_id: answer.answer.strip().upper()
        for answer in submission.answers
    }
    missing = [q["id"] for q in questions if q["id"] not in answer_map]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"缺少题目答案：{', '.join(missing)}",
        )

    breakdown = []
    score = 0
    for question in questions:
        user_answer = answer_map.get(question["id"], "")
        correct_answer = question.get("answer", "")
        is_correct = user_answer == correct_answer
        if is_correct:
            score += 1
        breakdown.append(
            {
                "question_id": question["id"],
                "question": question["question"],
                "user_answer": user_answer or None,
                "correct_answer": correct_answer,
                "correct": is_correct,
                "explanation": question.get("explanation", ""),
            }
        )

    total = len(questions)
    percentage = round(score / total * 100, 1) if total else 0.0
    return {
        "skill": skill,
        "title": practice.get("title"),
        "description": practice.get("description"),
        "score": score,
        "total": total,
        "percentage": percentage,
        "breakdown": breakdown,
        "tips": practice.get("tips", []),
        "next_steps": practice.get("next_steps", []),
    }


def _tokenise_text(text: str) -> List[str]:
    return re.findall(r"[A-Za-z']+", text.lower())


def _detect_connectors(text: str) -> List[str]:
    lowered = text.lower()
    found = {phrase for phrase in CONNECTOR_WORDS if phrase in lowered}
    return sorted(found)


def _count_academic_words(tokens: List[str]) -> List[str]:
    return sorted({token for token in tokens if token in ACADEMIC_VOCABULARY})


def _count_filler_usage(tokens: List[str], raw_text: str) -> Counter:
    counts = Counter(token for token in tokens if token in FILLER_WORDS)
    lowered = raw_text.lower()
    for phrase in FILLER_PHRASES:
        occurrences = lowered.count(phrase)
        if occurrences:
            counts[phrase] += occurrences
    return counts


def _analyse_writing_response(payload: WritingFeedbackRequest) -> Dict[str, object]:
    text = payload.response.strip()
    tokens = _tokenise_text(text)
    if len(tokens) < 40:
        raise HTTPException(status_code=400, detail="请至少输入 40 个英文单词，便于生成有效反馈")

    word_count = len(tokens)
    unique_words = len(set(tokens))
    lexical_density = round(unique_words / word_count, 2) if word_count else 0.0
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    sentence_count = len(sentences) if sentences else 1
    average_sentence_length = round(word_count / sentence_count, 1)
    connectors = _detect_connectors(text)
    academic_words = _count_academic_words(tokens)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    strengths: List[str] = []
    improvements: List[str] = []

    if word_count >= 260:
        strengths.append("字数达标，论点展开充分。")
    else:
        improvements.append("字数略少，建议扩展论证确保达到 260 词以上。")

    if connectors:
        strengths.append(f"使用了衔接词：{', '.join(connectors)}。")
    else:
        improvements.append("可增加 moreover, consequently 等衔接词增强逻辑。")

    if lexical_density >= 0.55:
        strengths.append("词汇多样性良好。")
    else:
        improvements.append("词汇重复率较高，尝试使用同义替换提升表达。")

    if average_sentence_length < 12:
        improvements.append("句子偏短，可尝试使用从句或连接词增加复杂度。")
    elif average_sentence_length > 28:
        improvements.append("部分句子偏长，注意断句以提升可读性。")
    else:
        strengths.append("句子长度控制合理。")

    if len(paragraphs) >= 4:
        strengths.append("段落结构完整，符合 Task 2 写作要求。")
    else:
        improvements.append("建议将文章划分为至少四段，突出论点层次。")

    band_projection = "5.5-6.0"
    if word_count >= 260 and lexical_density >= 0.5 and len(connectors) >= 2:
        band_projection = "6.0-6.5"
    if word_count >= 280 and lexical_density >= 0.58 and len(connectors) >= 4:
        band_projection = "6.5-7.0"
    if word_count >= 300 and lexical_density >= 0.62 and len(connectors) >= 5:
        band_projection = "7.0+"

    return {
        "skill": "writing",
        "word_count": word_count,
        "unique_words": unique_words,
        "sentence_count": sentence_count,
        "average_sentence_length": average_sentence_length,
        "lexical_density": lexical_density,
        "connectors": connectors,
        "academic_vocabulary": academic_words,
        "paragraphs": len(paragraphs),
        "strengths": strengths,
        "improvements": improvements,
        "band_projection": band_projection,
        "checklist": WRITING_PRACTICE.get("checklist", []),
    }


def _analyse_speaking_transcript(payload: SpeakingFeedbackRequest) -> Dict[str, object]:
    text = payload.transcript.strip()
    tokens = _tokenise_text(text)
    if len(tokens) < 30:
        raise HTTPException(status_code=400, detail="请至少整理约 30 个英文单词的回答记录，以便生成反馈")

    word_count = len(tokens)
    unique_words = len(set(tokens))
    lexical_variety = round(unique_words / word_count, 2) if word_count else 0.0
    connectors = _detect_connectors(text)
    filler_counter = _count_filler_usage(tokens, text)
    filler_total = sum(filler_counter.values())

    strengths: List[str] = []
    improvements: List[str] = []

    if connectors:
        strengths.append(f"能够使用衔接词（{', '.join(connectors)}）组织答案。")
    else:
        improvements.append("尝试加入 however, in addition 等衔接词增强逻辑。")

    if lexical_variety >= 0.55:
        strengths.append("词汇覆盖面较广，表达自然。")
    else:
        improvements.append("词汇重复率较高，可准备主题词替换表达。")

    if filler_total:
        sample_terms = ", ".join(term for term, _ in filler_counter.most_common(3))
        improvements.append(
            f"检测到 {filler_total} 个口头语（例如 {sample_terms}），建议用停顿或连接词替代。"
        )
    else:
        strengths.append("几乎没有口头语，语流控制良好。")

    if word_count < 110:
        improvements.append("输出时长略短，建议补充细节使回答接近 2 分钟。")

    band_projection = "5.5-6.0"
    if word_count >= 100 and lexical_variety >= 0.52 and filler_total <= max(2, int(word_count * 0.05)):
        band_projection = "6.0-6.5"
    if word_count >= 120 and lexical_variety >= 0.58 and filler_total <= max(2, int(word_count * 0.04)) and len(connectors) >= 3:
        band_projection = "6.5-7.0"
    if word_count >= 150 and lexical_variety >= 0.62 and filler_total <= 2 and len(connectors) >= 4:
        band_projection = "7.0+"

    filler_usage = [
        {"term": term, "count": count}
        for term, count in filler_counter.items()
        if count > 0
    ]

    return {
        "skill": "speaking",
        "word_count": word_count,
        "unique_words": unique_words,
        "lexical_variety": lexical_variety,
        "connectors": connectors,
        "filler_usage": filler_usage,
        "band_projection": band_projection,
        "strengths": strengths,
        "improvements": improvements,
        "follow_up_prompts": SPEAKING_PRACTICE.get("follow_up_prompts", []),
        "focus_part": payload.focus_part,
    }


@router.get("/modules")
def get_skill_modules() -> Dict[str, Dict[str, object]]:
    """Return descriptions of the four IELTS skill modules."""

    return SKILL_LIBRARY


@router.get("/supporting-tools")
def get_supporting_tools() -> Dict[str, object]:
    return {"tools": SUPPORTING_TOOLS}


@router.get("/mock-tests")
def get_mock_tests() -> Dict[str, object]:
    return {"mock_tests": MOCK_EXAMS}


@router.get("/vocabulary")
def get_vocabulary_deck(stage: Literal["foundation", "core", "advanced", "sprint"] = Query("core")) -> Dict[str, object]:
    deck = VOCABULARY_DECKS.get(stage)
    if not deck:
        raise HTTPException(status_code=404, detail="Vocabulary deck not found")
    return {"stage": stage, "deck": deck}


@router.get("/system-overview")
def get_system_overview() -> Dict[str, object]:
    return {
        "modules": SKILL_LIBRARY,
        "supporting_tools": SUPPORTING_TOOLS,
        "integrations": AI_INTEGRATIONS,
        "data_safeguards": {
            "storage": [
                "题库与素材库独立管理，支持定期更新",
                "用户作答、音频与作文档案按租户隔离存储",
            ],
            "privacy": [
                "音频与文本数据加密存储，可按需删除",
                "进度数据支持导出、备份与恢复",
            ],
        },
    }


@router.get("/interactive/practice")
def get_interactive_practice() -> Dict[str, object]:
    """Return interactive practice packs without answer keys."""

    return {skill: _strip_answers(practice) for skill, practice in INTERACTIVE_PRACTICE.items()}


@router.post("/interactive/listening/evaluate")
def evaluate_listening(submission: MultipleChoiceSubmission) -> Dict[str, object]:
    return _evaluate_multiple_choice_practice("listening", submission)


@router.post("/interactive/reading/evaluate")
def evaluate_reading(submission: MultipleChoiceSubmission) -> Dict[str, object]:
    return _evaluate_multiple_choice_practice("reading", submission)


@router.post("/interactive/vocabulary/evaluate")
def evaluate_vocabulary(submission: MultipleChoiceSubmission) -> Dict[str, object]:
    return _evaluate_multiple_choice_practice("vocabulary", submission)


@router.post("/interactive/writing/feedback")
def generate_writing_feedback(payload: WritingFeedbackRequest) -> Dict[str, object]:
    return _analyse_writing_response(payload)


@router.post("/interactive/speaking/coach")
def generate_speaking_feedback(payload: SpeakingFeedbackRequest) -> Dict[str, object]:
    return _analyse_speaking_transcript(payload)


@router.post("/assessment")
def create_learning_plan(payload: AssessmentRequest) -> Dict[str, object]:
    target_score = TARGET_BANDS[payload.target_band]
    current_avg = _average_score(payload.current_scores)
    weakest_skill = _weakest_skill(payload.current_scores)
    phases = _phase_sequence(payload.current_scores, target_score)
    if not phases:
        raise HTTPException(status_code=400, detail="无法生成学习阶段，请检查输入分数")

    weeks_allocation = _allocate_weeks(phases, payload.weeks_until_exam)
    plan = [
        _render_phase_payload(stage, weeks_allocation.get(stage, 0), payload.weekly_study_hours)
        for stage in phases
        if weeks_allocation.get(stage)
    ]
    priority_skills = _detect_priority_skills(payload.current_scores, payload.preferred_focus)

    return {
        "target_band": payload.target_band,
        "target_score_numeric": target_score,
        "current_average": current_avg,
        "overall_gap": round(target_score - current_avg, 2),
        "phase_plan": plan,
        "priority_skills": priority_skills,
        "recommendations": TARGET_RECOMMENDATIONS[payload.target_band],
        "daily_template": DEFAULT_DAILY_TEMPLATE,
        "ai_integrations": AI_INTEGRATIONS,
        "weakest_skill": weakest_skill,
    }


@router.post("/progress/review")
def review_progress(payload: ProgressReviewRequest) -> Dict[str, object]:
    improvements = _calculate_improvement(payload.baseline_scores, payload.latest_scores)
    weakest = _weakest_skill(payload.latest_scores)
    avg_latest = _average_score(payload.latest_scores)

    suggested_stage = "sprint"
    for stage in ["foundation", "core", "advanced"]:
        if avg_latest < TARGET_BANDS["6.5"] and stage == "foundation":
            suggested_stage = stage
            break
        if avg_latest < TARGET_BANDS["7.5+"] and stage == "core":
            suggested_stage = stage
            break
    priority = sorted(improvements.items(), key=lambda item: item[1])[:2]
    focus_skills = [skill for skill, _ in priority]

    return {
        "weeks_elapsed": payload.weeks_elapsed,
        "total_logged_hours": payload.total_logged_hours,
        "score_improvements": improvements,
        "weakest_skill": weakest,
        "suggested_next_stage": suggested_stage,
        "focus_recommendations": focus_skills,
        "next_actions": [
            "根据错题本安排阶段性复盘，锁定弱项技能",
            "安排下一次模考并关联 AI 反馈报告",
            "更新词汇手册的复习节奏，保持记忆曲线",
        ],
        "mock_test_suggestion": {
            "completed": payload.completed_mock_tests,
            "next": "建议 7 天内安排一次全真模考" if payload.completed_mock_tests < 3 else "保持每周一次模考频率",
        },
    }
