#!/bin/bash

# ==============================================================================
# Setup Guide Generator - v1.2
# ==============================================================================
#
# 角色与功能:
#   本脚本是一个动态的【安装设置指南】生成器。
#
#   它的核心任务是根据项目核心配置文件 `config.sh` 中的真实值，
#   渲染一个指定的指南模板，从而为用户生成一份清晰、准确、
#   “量身定制”的操作说明。
#
#   主要用于在 `init_deploy.sh` 脚本检测到环境问题时，为用户提供
#   精准的解决方案文档。
#
# 使用方法:
#   ./scripts/generate_setup_guide.sh <path/to/template.md> <path/to/output.md>
#
# ==============================================================================

# --- 脚本安全设置 ---
# -e: 如果任何命令失败（返回非零退出码），则立即退出脚本。
# -u: 如果试图使用一个未设置的变量，则视为错误并立即退出。
# -o pipefail: 如果管道中的任何命令失败，则整个管道的退出码为非零。
set -euo pipefail

# --- 颜色输出 ---
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
RED=$'\033[0;31m'
NC=$'\033[0m'

# --- 步骤 1: 验证输入参数 ---
if [ "$#" -ne 2 ]; then
    echo -e "${RED}错误: 参数数量不正确。${NC}"
    echo "用法: $0 <模板文件路径> <输出文件路径>"
    exit 1
fi

TEMPLATE_FILE="$1"
OUTPUT_FILE="$2"

# --- 步骤 2: 验证依赖文件是否存在 ---
# [修改] 调整 config.sh 的查找逻辑。
# 由于此脚本和 config.sh 都在同一目录 (deployment/setup/)，可以直接相对查找。
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
CONFIG_FILE="${SCRIPT_DIR}/../config.sh"

if [ ! -f "$TEMPLATE_FILE" ]; then
    echo -e "${RED}错误: 模板文件未找到: ${TEMPLATE_FILE}${NC}"
    exit 1
fi

if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}错误: 核心配置文件未找到: ${CONFIG_FILE}${NC}"
    echo "请确保 'config.sh' 文件与本脚本位于同一目录中。"
    exit 1
fi

# --- 步骤 3: 加载环境变量 ---
# 使用 'source' 或 '.' 命令来在当前 shell 会话中执行脚本，从而加载其 'export' 的变量。
# shellcheck source=../config.sh
source "$CONFIG_FILE"

# --- 步骤 4: 确保输出目录存在 ---
# `dirname` 获取文件的目录部分，`mkdir -p` 会创建所有必需的父目录且不会因目录已存在而报错。
mkdir -p "$(dirname "$OUTPUT_FILE")"

# --- 步骤 5: 读取模板并执行替换 ---
echo -e "${YELLOW}正在根据模板 '${TEMPLATE_FILE}' 生成设置指南...${NC}"

# 将模板文件的内容读入一个变量
content=$(cat "$TEMPLATE_FILE")

# 从 config.sh 中安全地提取所有被 'export' 的变量名
vars_to_replace=$(grep "^export " "$CONFIG_FILE" | sed 's/^export \([^=]*\)=.*/\1/')

# 循环遍历每个找到的变量名，并进行替换
for var_name in $vars_to_replace; do
    placeholder="{{${var_name}}}"
    # 使用间接变量引用 `${!var_name}` 来获取变量的值
    value="${!var_name}"

    # 使用 | 作为 sed 的分隔符，以避免当变量值包含斜杠 / 时出现问题
    content=$(echo "$content" | sed "s|$placeholder|$value|g")
done

# --- 步骤 6: 将处理后的内容写入输出文件 ---
echo "$content" > "$OUTPUT_FILE"

echo -e "${GREEN}✅ 成功生成指南: ${OUTPUT_FILE}${NC}"

exit 0