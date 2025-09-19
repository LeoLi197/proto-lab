# backend/src/services/basic_service.py (已优化CSV专注提取功能)
import logging
from pathlib import Path
from typing import Any, Iterable, List

import pandas as pd


def _save_to_file(content: str, output_path: Path) -> None:
    """将文本内容写入文件。"""
    try:
        output_path.write_text(content, encoding="utf-8")
        logging.info(f"基础版: 成功保存文件到: {output_path}")
    except IOError as exc:  # pragma: no cover - 仅在文件系统异常时触发
        logging.error(f"基础版: 无法写入文件 {output_path}: {exc}")


def _convert_tables_to_csv(document: Any, base_output_path: Path) -> None:
    """从 DoclingDocument 中提取表格并保存为多个 CSV 文件。"""
    tables = getattr(document, "tables", None)
    if not tables:
        logging.warning(
            f"基础版: 文件 {base_output_path.stem} 中未检测到表格，跳过CSV转换。"
        )
        return

    for index, table in enumerate(tables):
        try:
            dataframe = table.export_to_dataframe()
        except Exception as exc:  # pragma: no cover - 依赖第三方实现
            logging.error(
                f"基础版: 无法从表格对象导出 DataFrame (索引 {index}): {exc}",
                exc_info=True,
            )
            continue

        csv_output_path = base_output_path.with_name(
            f"{base_output_path.stem}_docling_table_{index + 1}.csv"
        )
        try:
            dataframe.to_csv(csv_output_path, index=False, encoding="utf-8-sig")
            logging.info(f"基础版: 成功提取并保存表格到: {csv_output_path}")
        except Exception as exc:  # pragma: no cover - 仅在写入失败时触发
            logging.error(f"基础版: 无法将表格保存到 {csv_output_path}: {exc}")


def _convert_excel_to_csv(source_path: Path, output_dir: Path) -> None:
    """使用 pandas 将 Excel 文件的每个工作表转换为 CSV。"""
    try:
        workbook = pd.ExcelFile(source_path)
        for sheet_name in workbook.sheet_names:
            dataframe = pd.read_excel(workbook, sheet_name=sheet_name)
            output_path = output_dir / f"{source_path.stem}_sheet_{sheet_name}.csv"
            dataframe.to_csv(output_path, index=False, encoding="utf-8-sig")
            logging.info(f"基础版: 成功将工作表 '{sheet_name}' 转换为: {output_path}")
    except Exception as exc:  # pragma: no cover - 依赖 pandas/Excel 解析
        logging.error(f"基础版: 处理 Excel 文件 {source_path} 失败: {exc}")


def _convert_excel_to_markdown(source_path: Path, output_dir: Path) -> None:
    """使用 pandas 将 Excel 文件的每个工作表转换为 Markdown 表格。"""
    try:
        workbook = pd.ExcelFile(source_path)
        markdown_chunks: List[str] = []
        for sheet_name in workbook.sheet_names:
            dataframe = pd.read_excel(workbook, sheet_name=sheet_name)
            markdown_chunks.append(f"## {sheet_name}\n\n")
            markdown_chunks.append(dataframe.to_markdown(index=False))
            markdown_chunks.append("\n\n")

        output_path = output_dir / f"{source_path.stem}.md"
        _save_to_file("".join(markdown_chunks), output_path)
    except Exception as exc:  # pragma: no cover - 依赖 pandas/Excel 解析
        logging.error(f"基础版: 将 Excel 文件 {source_path} 转换为 Markdown 失败: {exc}")


def _resolve_source_path(result: Any) -> Path:
    """从 Docling 结果中提取原始文件名。"""

    input_obj = getattr(result, "input", None)
    file_obj = getattr(input_obj, "file", None)

    if file_obj is None:
        return Path("unknown_document")

    filename = getattr(file_obj, "name", None)
    if not filename:
        filename = str(file_obj)

    return Path(filename)


def _extract_document_payload(result: Any) -> Any:
    """兼容不同 Docling 版本的输出结构。"""

    document = getattr(result, "document", None)
    if document is not None:
        return document

    return getattr(result, "output", None)


def _handle_docling_result(result: Any, output_dir: Path, output_format: str) -> None:
    """根据指定格式处理 Docling 转换结果。"""

    if not result:
        logging.error("基础版: Docling 返回空结果，跳过处理。")
        return

    document = _extract_document_payload(result)
    if document is None:
        filename = getattr(getattr(result, "input", None), "file", None)
        logging.error(f"基础版: Docling 结果缺少文档内容，文件: {filename or '未知文件'}")
        return

    source_path = _resolve_source_path(result)
    base_output_path = output_dir / source_path.stem

    if output_format == "csv":
        logging.info("基础版: 用户请求CSV格式，将仅提取表格。")
        _convert_tables_to_csv(document, base_output_path)
    elif output_format == "md":
        logging.info("基础版: 用户请求Markdown格式，将生成完整的MD文件。")
        export_md = getattr(document, "export_to_markdown", None)
        if callable(export_md):
            markdown_content = export_md()
            markdown_path = base_output_path.with_suffix(".md")
            _save_to_file(markdown_content, markdown_path)
        else:
            logging.error("基础版: 当前 Docling 文档对象不支持导出 Markdown。")


def _iter_docling_results(docling_converter: Any, docling_files: List[Path]) -> Iterable[Any]:
    """兼容不同 Docling 版本的批量转换接口。"""

    if hasattr(docling_converter, "convert_all"):
        return docling_converter.convert_all(
            [str(path) for path in docling_files], raises_on_error=False
        )

    try:
        from docling.datamodel.document import DocumentConversionInput
    except Exception as exc:  # pragma: no cover - 仅在缺少依赖时触发
        raise RuntimeError(
            "Docling 转换器缺少 convert_all 方法，并且无法导入 DocumentConversionInput。"
        ) from exc

    doc_input = DocumentConversionInput.from_paths(docling_files)
    return list(docling_converter.convert(doc_input))


def convert_batch_documents_basic(
    source_paths: List[Path],
    output_dir: Path,
    output_format: str,
    docling_converter: Any,
) -> None:
    """基础版批量转换入口函数。"""

    excel_files: List[Path] = []
    docling_files: List[Path] = []
    for path in source_paths:
        if path.suffix.lower() in {".xlsx", ".xls"}:
            excel_files.append(path)
        else:
            docling_files.append(path)

    # 处理Excel文件
    for source_path in excel_files:
        if output_format == "csv":
            _convert_excel_to_csv(source_path, output_dir)
        elif output_format == "md":
            _convert_excel_to_markdown(source_path, output_dir)

    # 使用Docling处理其他文件
    if docling_files:
        logging.info(f"基础版: 使用 Docling 批量处理 {len(docling_files)} 个文件...")
        for result in _iter_docling_results(docling_converter, docling_files):
            try:
                _handle_docling_result(result, output_dir, output_format)
            except Exception as exc:  # pragma: no cover - 捕获第三方运行时异常
                filename = (
                    result.input.file.name
                    if result and getattr(result, "input", None)
                    else "未知文件"
                )
                logging.error(
                    f"基础版: 批量转换文件 {filename} 时发生严重错误: {exc}",
                    exc_info=True,
                )
