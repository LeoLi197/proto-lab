# backend/src/services/enhanced_service.py (已优化CSV专注提取功能)
import logging
import os
import re
import tempfile
import uuid
from io import StringIO
from pathlib import Path
from typing import List

import pandas as pd
from pdf2image import convert_from_path

from src import config
from src.services import llm_service

PAGE_CHUNK_SIZE = 25

# --- 辅助函数 (保持不变) ---
def _save_to_file(content: str, output_path: Path):
    try:
        output_path.write_text(content, encoding='utf-8')
        logging.info(f"增强版: 成功保存文件到: {output_path}")
    except IOError as e:
        logging.error(f"增强版: 无法写入文件 {output_path}: {e}")

def _extract_appendix_tables_from_markdown(content: str) -> List[str]:
    appendix_section = content.split("## Appendix: Consolidated Tables")
    if len(appendix_section) < 2: return []
    pattern = re.compile(r'### Table \d+\n\n(.*?)(?=\n### Table|\Z)', re.S)
    tables = pattern.findall(appendix_section[1])
    return [table.strip() for table in tables]

def _convert_markdown_tables_to_csv(tables_md_list: List[str], base_output_path: Path):
    if not tables_md_list:
        logging.warning("增强版: 未在附录中找到任何表格用于CSV转换。")
        return
    for i, md_table in enumerate(tables_md_list):
        try:
            if '|' not in md_table or '---' not in md_table: continue
            table_io = StringIO(md_table)
            df = pd.read_csv(table_io, sep=r'\s*\|\s*', engine='python', index_col=0, skipinitialspace=True).dropna(axis=1, how='all').iloc[1:]
            if df.empty: continue
            csv_output_path = base_output_path.with_name(f"{base_output_path.stem}_appendix_table_{i + 1}.csv")
            df.to_csv(csv_output_path, index=False, encoding='utf-8-sig')
            logging.info(f"增强版: 成功从附录转换并保存表格到: {csv_output_path}")
        except Exception as pd_e:
            logging.error(f"增强版: Pandas无法解析附录表格 {i+1}。错误: {pd_e}")

def _convert_pdf_to_images(pdf_path: Path) -> List[Path]:
    temp_image_paths = []
    try:
        images = convert_from_path(pdf_path, dpi=200)
        temp_dir = Path(tempfile.gettempdir())
        for image in images:
            temp_filename = f"llm_page_{uuid.uuid4()}.png"
            temp_filepath = temp_dir / temp_filename
            image.save(temp_filepath, 'PNG')
            temp_image_paths.append(temp_filepath)
        logging.info(f"增强版: 成功将PDF '{pdf_path.name}' 转换为 {len(images)} 页图像。")
        return temp_image_paths
    except Exception as e:
        logging.error(f"增强版: PDF转图像失败: {e}。请确认Poppler已正确安装。")
        return []

# --- 核心处理流程 (已加入output_format判断) ---

def _process_document_holistically(source_path: Path, output_dir: Path, output_format: str):
    base_output_path = output_dir / source_path.stem
    all_chunks_content = []

    image_paths = []
    if source_path.suffix.lower() in {".pdf", ".docx"}:
        image_paths = _convert_pdf_to_images(source_path)
        if not image_paths: return
    elif source_path.suffix.lower() == ".txt":
        # 对于纯文本，不存在表格合并问题，直接提取表格即可
        md_content = source_path.read_text(encoding='utf-8')
        # 复用旧的提取逻辑
        from . import enhanced_service
        tables = enhanced_service._extract_tables_from_markdown(md_content) 
        _convert_markdown_tables_to_csv(tables, base_output_path)
        if output_format == 'md':
             _save_to_file(md_content, base_output_path.with_suffix('.md'))
        return # TXT文件处理完毕，提前返回
    else:
        logging.warning(f"增强版: 不支持的文件类型 {source_path.suffix}，跳过。")
        return

    if image_paths:
        try:
            total_pages = len(image_paths)
            for i in range(0, total_pages, PAGE_CHUNK_SIZE):
                chunk_paths = image_paths[i:i + PAGE_CHUNK_SIZE]
                chunk_number = (i // PAGE_CHUNK_SIZE) + 1
                logging.info(f"增强版: 正在处理文件块 {chunk_number} (页面 {i+1}-{i+len(chunk_paths)} / {total_pages})...")
                
                chunk_md = llm_service.extract_content_from_multiple_images(
                    image_paths=chunk_paths,
                    model_name=config.ENHANCED_VISION_MODEL_NAME,
                    prompt=config.ENHANCED_HOLISTIC_PROMPT
                )
                if chunk_md:
                    all_chunks_content.append(chunk_md)
        finally:
            for path in image_paths:
                try: os.remove(path)
                except OSError as e: logging.warning(f"增强版: 清理临时图片失败: {e}")
    
    final_md_content = "\n\n--- DOCUMENT_CHUNK_SEPARATOR ---\n\n".join(all_chunks_content)

    if not final_md_content or "NO_CONTENT_DETECTED" in final_md_content:
        logging.warning(f"增强版: 未能从 {source_path.name} 提取任何内容。")
        return

    # --- 【核心修改点】 ---
    # 提取附录表格，这是两种模式都需要的数据
    appendix_tables = _extract_appendix_tables_from_markdown(final_md_content)
    
    # 1. 如果用户只需要CSV，则只生成CSV
    if output_format == 'csv':
        logging.info("增强版: 用户请求CSV格式，将仅生成表格文件。")
        _convert_markdown_tables_to_csv(appendix_tables, base_output_path)
    
    # 2. 如果用户需要Markdown（默认或明确选择），则保存MD文件并顺便生成CSV
    elif output_format == 'md':
        logging.info("增强版: 用户请求Markdown格式，将生成完整的MD文件。")
        md_output_path = base_output_path.with_suffix('.md')
        _save_to_file(final_md_content, md_output_path)
        # 如果需要，也可以在生成MD的同时附带CSV
        # _convert_markdown_tables_to_csv(appendix_tables, base_output_path)
    
# --- 批量处理入口 (无需修改) ---
from .basic_service import _convert_excel_to_csv, _convert_excel_to_markdown

def convert_batch_documents_enhanced(source_paths: List[Path], output_dir: Path, output_format: str):
    for source_path in source_paths:
        logging.info(f"增强版: 开始处理文件 '{source_path.name}'...")
        try:
            file_extension = source_path.suffix.lower()
            if file_extension in {".xlsx", ".xls"}:
                # 对于Excel，CSV模式只输出CSV，MD模式只输出MD
                if output_format == 'csv': 
                    _convert_excel_to_csv(source_path, output_dir)
                elif output_format == 'md': 
                    _convert_excel_to_markdown(source_path, output_dir)
            else:
                _process_document_holistically(source_path, output_dir, output_format)
        except Exception as e:
            logging.error(f"增强版: 处理文件 '{source_path.name}' 时发生未知严重错误: {e}", exc_info=True)