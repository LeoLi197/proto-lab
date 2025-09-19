# backend/features/doc_converter/router.py

import logging
import os
import shutil
import uuid
import zipfile
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, File, Form, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse

# ==============================================================================
# 【核心修改】: 导入路径从项目级 (src.) 变更为模块级相对路径 (.)
# 您需要将原 src/ 目录下的 services, utils, config.py 文件移动到
# backend/features/doc_converter/ 目录下
# ==============================================================================
from .config import SUPPORTED_INPUT_EXTENSIONS, LOG_FORMAT
from .services import basic_service, enhanced_service
from .utils import file_utils

# ==============================================================================
# 【核心修改】: 使用 APIRouter 替代 FastAPI()
# tags 参数会在API文档中为这个模块的功能创建一个分组
# ==============================================================================
router = APIRouter(
    tags=["Doc Converter"]
)

# --- 模块级全局变量 ---
# 这些变量和服务函数现在被封装在此模块内部，不会污染全局命名空间
TEMP_INPUT_DIR = Path("temp_input")
TEMP_OUTPUT_DIR = Path("temp_output")
task_statuses = {}
docling_converter = None  # 全局变量，延迟初始化
docling_import_error: Optional[Exception] = None

# 确保临时目录在模块加载时就准备好
# 注意：在多进程或无状态环境中，可能需要更健壮的目录管理策略
file_utils.ensure_dir_exists(TEMP_INPUT_DIR)
file_utils.ensure_dir_exists(TEMP_OUTPUT_DIR)


# --- 模块内部辅助函数 ---
# 以下函数从原 main.py 直接迁移过来，无需修改其内部逻辑

def initialize_docling_converter() -> None:
    """懒加载方式初始化Docling转换器，仅在需要时执行。"""

    global docling_converter, docling_import_error

    if docling_converter is not None:
        return

    try:
        from docling.datamodel.base_models import PipelineOptions, TableStructureOptions
        from docling.document_converter import DocumentConverter
    except Exception as exc:  # pragma: no cover - 仅在运行时缺少依赖时触发
        docling_import_error = exc
        logging.error("无法导入 Docling 相关依赖: %s", exc, exc_info=True)
        raise

    logging.info("正在配置并初始化 Docling 转换器...")

    pipeline_options = PipelineOptions(
        do_ocr=True,
        table_structure_options=TableStructureOptions(do_cell_matching=True),
    )

    docling_converter = DocumentConverter(pipeline_options=pipeline_options)
    docling_import_error = None
    logging.info("Docling 转换器初始化成功。")


def ensure_docling_ready() -> None:
    """确保 Docling 转换器可用，否则向调用方抛出 HTTP 异常。"""

    try:
        initialize_docling_converter()
    except Exception as exc:  # pragma: no cover - 运行时异常
        message = (
            "Docling 转换功能未正确配置。请确认已安装 `docling` 和"
            " `deepsearch-toolkit` 依赖，并且镜像具备所需的系统组件。"
        )
        raise HTTPException(status_code=503, detail=message) from exc

def process_and_zip_results(task_id: str, input_dir: Path, output_dir: Path, final_zip_name: str):
    """通用后处理函数：处理输出文件并打包成ZIP。"""
    output_files = [p for p in output_dir.glob('*') if p.is_file()]

    if not output_files:
        logging.warning(f"[{task_id}] 转换后未生成任何文件。将创建一个提示文件。")
        readme_path = output_dir / "_CONVERSION_NOTES.txt"
        readme_path.write_text(
            f"在处理 {len(list(input_dir.glob('*')))} 个文件的批量任务后，未能提取任何内容。\n"
            f"这通常发生在请求提取表格（CSV），但所有文档中均未检测到任何表格时。",
            encoding="utf-8"
        )

    zip_path = output_dir / final_zip_name
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for f_path in output_dir.glob('*'):
            if f_path.is_file() and f_path.suffix != '.zip':
                zipf.write(f_path, f_path.name)

    task_statuses[task_id] = {"status": "completed", "filename": final_zip_name}
    logging.info(f"[{task_id}] 任务成功完成。结果: {final_zip_name}")


def run_batch_conversion_task(
    task_id: str,
    engine: str,
    input_dir: Path,
    output_dir: Path,
    output_format: str
):
    try:
        logging.info(f"[{task_id}] 批量后台任务开始 (引擎: {engine})，输入目录: {input_dir.name}")
        task_statuses[task_id] = {"status": "processing"}

        source_paths = list(input_dir.glob('*'))
        if not source_paths:
            raise ValueError("批量任务的输入目录为空。")

        if engine == "basic":
            try:
                initialize_docling_converter()  # 确保Docling已初始化
            except Exception as exc:
                logging.error(f"[{task_id}] Docling 初始化失败: {exc}")
                task_statuses[task_id] = {"status": "failed", "error": str(exc)}
                return
            basic_service.convert_batch_documents_basic(
                source_paths=source_paths,
                output_dir=output_dir,
                output_format=output_format,
                docling_converter=docling_converter
            )
        elif engine == "enhanced":
            enhanced_service.convert_batch_documents_enhanced(
                source_paths=source_paths,
                output_dir=output_dir,
                output_format=output_format
            )
        else:
            raise ValueError(f"未知的处理引擎: {engine}")

        # 统一进行后处理和打包
        zip_filename = f"batch_{task_id}_{engine}_converted.zip"
        process_and_zip_results(task_id, input_dir, output_dir, zip_filename)

    except Exception as e:
        logging.error(f"[{task_id}] 批量任务失败: {e}", exc_info=True)
        task_statuses[task_id] = {"status": "failed", "error": str(e)}
    finally:
        if input_dir.exists():
            shutil.rmtree(input_dir)


# --- API 端点定义 ---

# ==============================================================================
# 【核心修改】:
# 1. 装饰器从 @app.post 变更为 @router.post
# 2. 路由路径从 "/api/v1/convert-batch" 变更为 "/convert-batch"
#    框架的 main.py 会统一添加 "/api" 前缀
# ==============================================================================
@router.post("/convert-batch", summary="提交一个批量文档转换任务")
async def submit_batch_conversion_task(
    background_tasks: BackgroundTasks,
    engine: str = Form(..., description="处理引擎: 'basic' 或 'enhanced'"),
    output_format: str = Form(..., description="目标格式: 'md' 或 'csv'"),
    files: List[UploadFile] = File(..., description="要批量转换的文档")
):
    if engine not in ["basic", "enhanced"]:
        raise HTTPException(status_code=400, detail="无效的处理引擎。请选择 'basic' 或 'enhanced'。")

    # 在处理文件之前确保 Docling 转换器可用
    if engine == "basic":
        ensure_docling_ready()

    for file in files:
        file_extension = Path(file.filename).suffix.lower()
        if file_extension not in SUPPORTED_INPUT_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"文件 '{file.filename}' 的类型不支持。")

    task_id = str(uuid.uuid4())

    task_input_dir = TEMP_INPUT_DIR / task_id
    task_output_dir = TEMP_OUTPUT_DIR / task_id
    file_utils.ensure_dir_exists(task_input_dir)
    file_utils.ensure_dir_exists(task_output_dir)

    for file in files:
        input_path = task_input_dir / file.filename
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

    background_tasks.add_task(
        run_batch_conversion_task,
        task_id,
        engine,
        task_input_dir,
        task_output_dir,
        output_format
    )

    task_statuses[task_id] = {"status": "queued"}
    return {"task_id": task_id, "message": f"批量任务已提交 ({len(files)}个文件，使用 {engine} 引擎)，正在排队处理。"}


# ==============================================================================
# 【核心修改】: 装饰器和路由路径已更新
# ==============================================================================
@router.get("/status/{task_id}", summary="查询任务状态")
def get_task_status(task_id: str):
    status = task_statuses.get(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="找不到指定的任务 ID。")
    return status


# ==============================================================================
# 【核心修改】: 装饰器和路由路径已更新
# ==============================================================================
@router.get("/download/{task_id}", summary="下载任务结果")
def download_result(task_id: str):
    status = task_statuses.get(task_id)
    if not status or status.get("status") != "completed":
        raise HTTPException(status_code=404, detail="任务未完成或不存在。")

    output_dir = TEMP_OUTPUT_DIR / task_id
    file_path = output_dir / status["filename"]

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="结果文件不存在。")

    return FileResponse(
        path=file_path,
        media_type='application/octet-stream',
        filename=status["filename"]
    )