# src/utils/file_utils.py
"""
提供文件和目录操作相关的辅助函数。
"""
import os
from pathlib import Path
from typing import List, Set

def ensure_dir_exists(directory: Path) -> None:
    """
    确保指定的目录存在，如果不存在则创建它。

    Args:
        directory (Path): 需要检查或创建的目录路径。
    """
    if not directory.exists():
        print(f"创建输出目录: {directory}")
        directory.mkdir(parents=True, exist_ok=True)

def find_supported_files(directory: Path, supported_extensions: Set[str]) -> List[Path]:
    """
    在指定目录中查找所有支持的格式的文件。

    Args:
        directory (Path): 要搜索的目录。
        supported_extensions (Set[str]): 支持的文件扩展名集合 (例如: {".pdf", ".docx"})。

    Returns:
        List[Path]: 找到的文件的路径列表。
    """
    found_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if Path(file).suffix.lower() in supported_extensions:
                found_files.append(Path(root) / file)
    return found_files