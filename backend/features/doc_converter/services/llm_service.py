# backend/src/services/llm_service.py (已修复 list object has no attribute 'get' 错误)
# backend/src/services/llm_service.py (增加多图输入功能)
import logging
from http import HTTPStatus
from pathlib import Path
from typing import Optional, List
from dashscope import MultiModalConversation
from .. import config

def extract_content_from_multiple_images(
    image_paths: List[Path],
    model_name: str,
    prompt: str
) -> Optional[str]:
    """
    【新】通用函数：将多个图像文件一次性发送给指定的DashScope视觉模型。
    """
    if not config.LLM_API_KEY:
        logging.error("LLM_API_KEY 未配置，跳过LLM处理。")
        return None
    if not image_paths:
        logging.warning("未提供任何图像路径，跳过LLM处理。")
        return None

    logging.info(f"正在使用模型 '{model_name}' 分析 {len(image_paths)} 张图像...")

    # 构建包含多张图片的内容列表
    content_list = []
    for img_path in image_paths:
        local_file_uri = f'file://{img_path.resolve()}'
        content_list.append({'image': local_file_uri})
    
    # 将文本prompt添加到列表末尾
    content_list.append({'text': prompt})
    
    messages = [{'role': 'user', 'content': content_list}]

    try:
        response = MultiModalConversation.call(
            model=model_name, messages=messages, api_key=config.LLM_API_KEY
        )

        if response.status_code == HTTPStatus.OK:
            logging.info("LLM成功完成多图分析。")
            raw_content = ''
            if response.output and response.output.choices:
                first_choice = response.output.choices[0]
                if first_choice.message and first_choice.message.content:
                    raw_content = first_choice.message.content
            
            # 复用健壮的解析逻辑
            if isinstance(raw_content, list) and raw_content:
                content_dict = raw_content[0]
                content = content_dict.get('text', '') if isinstance(content_dict, dict) else ''
            elif isinstance(raw_content, dict):
                content = raw_content.get('text', '')
            else:
                content = str(raw_content)

            if content:
                # 清理Markdown代码块标记
                if content.strip().startswith("```markdown"): content = content.strip()[10:]
                if content.strip().endswith("```"): content = content.strip()[:-3]
                return content.strip()
            else:
                return None
        else:
            logging.error(f"LLM多图API调用失败: Code: {response.code}, Message: {response.message}")
            return None
    except Exception as e:
        logging.error(f"调用LLM多图API时发生未知异常: {e}", exc_info=True)
        return None

#def stitch_tables_with_llm(tables_md: List[str]) -> List[str]:
    """
    【最终修复版】使用强大的 qwen-vl-max 模型来智能拼接Markdown表格片段列表。
    """
    if not tables_md or len(tables_md) < 2:
        return tables_md

    model_for_stitching = "qwen-vl-max" 
    input_text = f"\n\n{config.LLM_TABLE_SEPARATOR}\n\n".join(tables_md)
    
    prompt = (
        "你是一个严格遵守指令的文档数据处理专家。\n"
        "任务：分析并合并我提供的一系列Markdown表格片段。一个完整的表格可能因分页被拆分。\n"
        "指令：\n"
        "1. 如果这些片段明显属于同一个逻辑表格（例如，表头结构相似，内容连续），请将它们合并成一个完整的Markdown表格。合并时，请移除后续片段中多余的表头。\n"
        "2. 如果它们是完全不同的表格，请保持它们独立。\n"
        "3. 返回最终的、整理后的完整表格列表。\n\n"
        "【！！！绝对输出规则！！！】:\n"
        f"- 必须且只能使用 `{config.LLM_TABLE_SEPARATOR}` 作为不同表格之间的唯一分隔符。\n"
        "- 你的回复中严禁包含任何解释、介绍、总结或任何非表格内容。你的回复必须直接以表格的 `|` 字符开始。"
        "\n\n"
        "【待处理的表格列表】:\n"
        f"{input_text}"
    )

    logging.info(f"正在调用模型 '{model_for_stitching}' 进行表格智能拼接...")
    messages = [{'role': 'user', 'content': [{'text': prompt}]}]

    try:
        response = MultiModalConversation.call(
            model=model_for_stitching,
            messages=messages,
            api_key=config.LLM_API_KEY
        )

        if response.status_code == HTTPStatus.OK:
            raw_content = ''
            if response.output and response.output.choices:
                first_choice = response.output.choices[0]
                if first_choice.message and first_choice.message.content:
                    raw_content = first_choice.message.content
            
            # --- 【核心修复点】---
            # 增加对 list 类型的判断，使其能够正确处理 API 的不同返回格式
            merged_content = ''
            if isinstance(raw_content, list) and raw_content:
                content_dict = raw_content[0]
                merged_content = content_dict.get('text', '') if isinstance(content_dict, dict) else ''
            elif isinstance(raw_content, dict):
                merged_content = raw_content.get('text', '')
            else:
                merged_content = str(raw_content)
            merged_content = merged_content.strip()
            # --- 修复结束 ---

            final_tables = []
            if config.LLM_TABLE_SEPARATOR in merged_content:
                final_tables = [
                    table.strip() for table in merged_content.split(config.LLM_TABLE_SEPARATOR) if table.strip().startswith('|')
                ]
            elif merged_content.startswith('|') and '---' in merged_content:
                logging.warning(f"{model_for_stitching}未返回分隔符，但内容看似一个有效表格，将整体视为单次合并结果。")
                final_tables = [merged_content]
            else:
                logging.warning(f"{model_for_stitching}返回了非预期的内容。内容: {merged_content[:200]}...")
            
            if not final_tables and tables_md:
                logging.warning("拼接后未生成有效表格，将优雅降级，返回原始表格块。")
                return tables_md

            logging.info(f"模型 '{model_for_stitching}' 成功完成拼接，生成了 {len(final_tables)} 个最终表格。")
            return final_tables
        else:
            logging.error(f"模型 '{model_for_stitching}' API调用失败: Code: {response.code}, Message: {response.message}")
            return tables_md
    except Exception as e:
        logging.error(f"调用模型 '{model_for_stitching}' 时发生异常: {e}", exc_info=True)
        # 在异常情况下，优雅降级返回原始表格
        logging.warning("因异常，表格拼接失败，将返回原始表格块。")
        return tables_md