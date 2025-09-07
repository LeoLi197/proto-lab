# backend/src/services/basic_service.py (已优化CSV专注提取功能)
import logging
from pathlib import Path
from typing import List
import pandas as pd
from docling.document_converter import DocumentConverter, ConversionResult
from docling_core.types.doc.document import DoclingDocument

def _save_to_file(content: str, output_path: Path):
    """将文本内容写入文件。"""
    try:
        output_path.write_text(content, encoding='utf-8')
        logging.info(f"基础版: 成功保存文件到: {output_path}")
    except IOError as e:
        logging.error(f"基础版: 无法写入文件 {output_path}: {e}")

def _convert_tables_to_csv(document: DoclingDocument, base_output_path: Path):
    """从 DoclingDocument 中提取表格并保存为多个 CSV 文件。"""
    if not document.tables:
        logging.warning(f"基础版: 文件 {base_output_path.stem} 中未检测到表格，跳过CSV转换。")
        return
    for i, table in enumerate(document.tables):
        df = table.export_to_dataframe()
        csv_output_path = base_output_path.with_name(f"{base_output_path.stem}_docling_table_{i + 1}.csv")
        try:
            df.to_csv(csv_output_path, index=False, encoding='utf-8-sig')
            logging.info(f"基础版: 成功提取并保存表格到: {csv_output_path}")
        except Exception as e:
            logging.error(f"基础版: 无法将表格保存到 {csv_output_path}: {e}")

def _convert_excel_to_csv(source_path: Path, output_dir: Path):
    """使用 pandas 将 Excel 文件的每个工作表转换为 CSV。"""
    try:
        xls = pd.ExcelFile(source_path)
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            output_path = output_dir / f"{source_path.stem}_sheet_{sheet_name}.csv"
            df.to_csv(output_path, index=False, encoding='utf-8-sig')
            logging.info(f"基础版: 成功将工作表 '{sheet_name}' 转换为: {output_path}")
    except Exception as e:
        logging.error(f"基础版: 处理 Excel 文件 {source_path} 失败: {e}")

def _convert_excel_to_markdown(source_path: Path, output_dir: Path):
    """使用 pandas 将 Excel 文件的每个工作表转换为 Markdown 表格。"""
    try:
        xls = pd.ExcelFile(source_path)
        full_markdown_content = []
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            full_markdown_content.append(f"## {sheet_name}\n\n")
            full_markdown_content.append(df.to_markdown(index=False))
            full_markdown_content.append("\n\n")
        output_path = output_dir / f"{source_path.stem}.md"
        _save_to_file("".join(full_markdown_content), output_path)
    except Exception as e:
        logging.error(f"基础版: 将 Excel 文件 {source_path} 转换为 Markdown 失败: {e}")

def _handle_docling_result(result: ConversionResult, output_dir: Path, output_format: str):
    """【修改】统一处理Docling转换结果，根据output_format决定输出。"""
    if not result or not result.document:
        filename = result.input.file.name if result and result.input else '未知文件'
        logging.error(f"基础版: Docling 无法处理文件: {filename}")
        return

    source_path = Path(result.input.file.name)
    document = result.document
    base_output_path = output_dir / source_path.stem
    
    # --- 【核心修改点】 ---
    if output_format == 'csv':
        logging.info("基础版: 用户请求CSV格式，将仅提取表格。")
        _convert_tables_to_csv(document, base_output_path)
    
    elif output_format == 'md':
        logging.info("基础版: 用户请求Markdown格式，将生成完整的MD文件。")
        md_content = document.export_to_markdown()
        md_output_path = base_output_path.with_suffix('.md')
        _save_to_file(md_content, md_output_path)
        # 如果需要，也可以在生成MD的同时附带CSV
        # _convert_tables_to_csv(document, base_output_path)

def convert_batch_documents_basic(
    source_paths: List[Path],
    output_dir: Path,
    output_format: str,
    docling_converter: DocumentConverter
):
    """基础版批量转换入口函数。"""
    excel_files, docling_files = [], []
    for path in source_paths:
        if path.suffix.lower() in {".xlsx", ".xls"}:
            excel_files.append(path)
        else:
            docling_files.append(path)

    # 处理Excel文件
    for source_path in excel_files:
        if output_format == 'csv':
            _convert_excel_to_csv(source_path, output_dir)
        elif output_format == 'md':
            _convert_excel_to_markdown(source_path, output_dir)
    
    # 使用Docling处理其他文件
    if docling_files:
        logging.info(f"基础版: 使用 Docling 批量处理 {len(docling_files)} 个文件...")
        conv_results = docling_converter.convert_all([str(p) for p in docling_files], raises_on_error=False)
        for result in conv_results:
            try:
                _handle_docling_result(result, output_dir, output_format)
            except Exception as e:
                filename = result.input.file.name if result and result.input else '未知文件'
                logging.error(f"基础版: 批量转换文件 {filename} 时发生严重错误: {e}", exc_info=True)