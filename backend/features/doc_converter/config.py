# src/config.py (采用全新的“一步到位”策略)
"""
集中管理项目的所有配置，实现配置与代码的分离。
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# --- 加载 .env 文件中的环境变量 ---
load_dotenv()

# --- 核心路径定义 ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / "output"

# --- 文件格式定义 ---
SUPPORTED_INPUT_EXTENSIONS = {".pdf", ".docx", ".txt", ".xlsx", ".xls"}

# --- 常量定义 ---
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

# --- 大语言模型 (LLM) 配置 ---
LLM_API_KEY = os.getenv("LLM_API_KEY")

# --- 增强版模块配置 ---

# 模型选择：必须是支持多图片输入的强大模型
ENHANCED_VISION_MODEL_NAME = "qwen-vl-max"

# 【全新】一步到位式的全局Prompt
ENHANCED_HOLISTIC_PROMPT = (
    "你是一位顶级的文档分析和重组专家。\n"
    "我将按顺序提供一个文档的所有页面图片。你的任务是综合分析所有图片，生成一份单一、完整、结构化的Markdown文档。\n\n"
    "请严格遵循以下两个步骤：\n\n"
    "**第一部分：正文内容**\n"
    "1. 按页面顺序，提取所有页面的全部内容（标题、段落、列表、表格等），并组合成流畅的Markdown正文。\n"
    "2. 在原文中分页符的位置，你可以使用 `---_page_break_---` 来标记。\n\n"
    "**第二部分：表格附录**\n"
    "1. 在完成正文内容后，另起一行，添加一个Markdown二级标题 `## Appendix: Consolidated Tables`。\n"
    "2. 仔细检查你在正文中识别出的所有表格。如果发现一个表格因为分页被拆分（例如，一个表格的结尾在第一张图，开头在第二张图），你必须将它们智能地合并成一个完整的表格。\n"
    "3. 将所有经过整理和合并后的最终表格，在附录部分逐一列出。每个表格前使用一个三级标题，如 `### Table 1`, `### Table 2` 等。\n\n"
    "【输出要求】\n"
    "- 最终输出必须是一个单一的Markdown文本，同时包含【正文】和【附录】两部分。\n"
    "- 如果整个文档中没有任何表格，则不需要创建第二部分的附录。\n"
    "- 如果文档无内容，请返回 'NO_CONTENT_DETECTED'。"
)



# 用于CSV生成的唯一分隔符（依然有用）
LLM_TABLE_SEPARATOR = "---TABLE_SEPARATOR---"