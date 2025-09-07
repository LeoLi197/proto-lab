#!/bin/bash
# ==============================================================================
# flashmvp - 主安装向导 (v1.0)
# ==============================================================================
#
# 这是新项目设置的唯一入口点。它将引导您完成所有必需的检查。
#
# ==============================================================================

set -e # 任何错误都停止执行

# --- 颜色输出 ---
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
RED=$'\033[1;31m'     # 亮红色
CYAN=$'\033[0;36m'     # 青色替代蓝色
WHITE=$'\033[1;37m'    # 白色替代紫色文字
PURPLE=$'\033[0;35m'   # 紫色仅用于分割线
NC=$'\033[0m'

# ==============================================================================
# 辅助函数定义
# ==============================================================================
print_separator() {
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}
# ==============================================================================

# --- 脚本路径定义 ---
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
INTERNAL_DIR="${SCRIPT_DIR}/internal"
CONFIG_FILE="${SCRIPT_DIR}/config.sh"
OUTPUT_DIR="${SCRIPT_DIR}/output"

# --- 打印标题 ---
echo -e "${PURPLE}=======================================================${NC}"
echo -e "${WHITE}🚀 欢迎使用 flashmvp 项目一站式安装向导 🚀${NC}"
echo -e "${PURPLE}=======================================================${NC}"
echo "本向导将验证您的环境配置，并确保所有部署前置条件都已满足。"
echo ""


# --- 步骤 1: 检查 config.sh 是否已修改 ---
echo -e "${CYAN}[步骤 1/4] 检查核心配置文件 (config.sh)...${NC}"
source "$CONFIG_FILE"

if [ "$GITHUB_USERNAME" == "Your-username" ] || [ -z "$GITHUB_USERNAME" ]; then
    echo -e "${RED}❌ 检查失败: 您尚未配置 'config.sh' 文件。${NC}"
    echo -e "${YELLOW}👉 请打开 '${CONFIG_FILE}'，填写您的 GitHub 用户名、项目名等信息，然后再重新运行此向导。${NC}"
    exit 1
fi
echo -e "${GREEN}✅ 配置文件已填写。项目基础名称: ${PROJECT_NAME_BASE}${NC}"
echo ""


# --- 步骤 2: 检查 CLI 登录状态 ---
echo -e "${CYAN}[步骤 2/4] 检查云平台登录状态...${NC}"
# 检查 gcloud
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q "."; then
    echo -e "${RED}❌ 检查失败: 您尚未登录 Google Cloud (gcloud)。${NC}"
    echo -e "${YELLOW}👉 请在新终端中执行以下命令完成登录，然后重新运行本向导:${NC}"
    echo "   gcloud auth login"
    echo "   gcloud config set project ${GCP_PROJECT_ID}"
    exit 1
fi
echo -e "${GREEN}  - Google Cloud: 已登录为 $(gcloud config get-value account)${NC}"

# 检查 wrangler
if ! wrangler whoami >/dev/null 2>&1; then
    echo -e "${RED}❌ 检查失败: 您尚未登录 Cloudflare (wrangler)。${NC}"
    echo -e "${YELLOW}👉 请在新终端中执行 'wrangler login' 完成登录，然后重新运行本向导。${NC}"
    exit 1
fi
echo -e "${GREEN}  - Cloudflare: 已登录。${NC}"
echo ""


# --- 步骤 3: 检查 GCP 项目有效性 ---
echo -e "${CYAN}[步骤 3/4] 验证 GCP 项目 '${GCP_PROJECT_ID}'...${NC}"
if ! gcloud projects describe "${GCP_PROJECT_ID}" --project="${GCP_PROJECT_ID}" >/dev/null 2>&1; then
    echo -e "${RED}❌ 验证失败: 项目 '${GCP_PROJECT_ID}' 不存在或您没有访问权限。${NC}"
    
    # 动态生成帮助文档
    "${INTERNAL_DIR}/generate_setup_guide.sh" \
      "${SCRIPT_DIR}/docs/templates/create-gcp-project-guide.template.md" \
      "${OUTPUT_DIR}/create-gcp-project-guide.md"

    echo -e "\n${YELLOW}为了帮助您解决问题，我已为您生成了一份专属操作指南，请查看:${NC}"
    echo -e "  📄  ${GREEN}${OUTPUT_DIR}/create-gcp-project-guide.md${NC}"
    echo -e "\n请按照指南创建并配置好项目后，再重新运行本向导。"
    exit 1
fi
echo -e "${GREEN}✅ GCP 项目验证成功！${NC}"
echo ""


# --- 步骤 4: 最终确认 ---
echo -e "${CYAN}[步骤 4/4] 所有检查已通过，准备执行部署...${NC}"
print_separator
echo -e "${YELLOW}⚠️  即将开始在云端创建和配置以下资源:${NC}"
echo "  - GCP Project: ${GCP_PROJECT_ID}"
echo "  - GCP Region: ${GCP_REGION}"
echo "  - Cloud Run Service: ${PROJECT_NAME_BASE}-backend"
echo "  - Cloudflare Pages Project: ${PROJECT_NAME_BASE}"
echo "  - Cloudflare D1 Database: ${PROJECT_NAME_BASE}-usage"
echo "  - 以及相关的服务账号和权限。"
print_separator
echo ""
read -p "您确定要继续吗？(y/n): " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
    echo "操作已取消。"
    exit 0
fi


# --- 执行核心脚本 ---
echo ""
echo -e "${GREEN}确认完毕，正在启动核心部署脚本...${NC}"
echo "--------------------------------------------------------"
chmod +x "${INTERNAL_DIR}/init_deploy.sh"
"${INTERNAL_DIR}/init_deploy.sh"

echo "--------------------------------------------------------"
echo -e "${GREEN}🎉 所有操作已成功启动！请根据上方核心脚本的输出，完成后续步骤。${NC}"