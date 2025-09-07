#!/bin/bash

# ==============================================================================
# flashmvp MVP 初始化脚本 - v6.3 (Git-Aware & Config-Driven, AR Auto-Fix)
# ==============================================================================
#
# 功能：
# 1. 自动检测并清理从模板复制而来的旧 Git 历史记录。
# 2. 从 config.sh 加载配置，自动创建所有基础云资源。
# 3. 动态生成第二阶段的GCP身份配置脚本 (setup_gcp_identity.sh)。
# 4. 生成一份全新的、指导用户完成后续流程的手动操作指南。
# 5. 【新增】自动处理 Cloud Run 源码部署常见 403：预创建 Artifact Registry 仓库并授权 Cloud Build。
#
# 使用方法:
# 1. (从模板) 复制项目文件夹并重命名。
# 2. 编辑 deployment/setup/config.sh 文件。
# 3. cd deployment/setup/
# 4. chmod +x init_deploy.sh
# 5. ./init_deploy.sh
#
# ==============================================================================

set -e # 任何错误都停止执行

# 更友好的错误提示：失败≠卡死；出现错误会立刻提示行号
trap 'echo -e "\033[1;31m❌ 脚本在第 ${LINENO} 行的命令执行失败。通常这是命令报错或权限/配置问题，并非\"卡死\"。请上滚查看上一条命令的输出日志定位具体原因。\033[0m"' ERR

# --- 颜色输出 ---
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
RED=$'\033[1;31m'     # 亮红色
CYAN=$'\033[0;36m'     # 青色
WHITE=$'\033[1;37m'    # 白色
PURPLE=$'\033[0;35m'   # 紫色仅用于分割线
NC=$'\033[0m'

# --- 定义占位符常量 ---
PROVIDER_PLACEHOLDER="__GCP_WORKLOAD_IDENTITY_PROVIDER_PLACEHOLDER__"

# --- 辅助函数 ---
wait_with_message() {
    local seconds=$1
    local message=$2
    echo -e "${CYAN}⏳ ${message} (等待 ${seconds} 秒)...【正常等待提示】${NC}"
    sleep $seconds
}

print_separator() {
    echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# 路径定义，以适配新的 internal/ 目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SETUP_DIR="$( cd "${SCRIPT_DIR}/.." && pwd )"        # 指向 deployment/setup
PROJECT_ROOT="$( cd "${SCRIPT_DIR}/../../.." && pwd )" # 指向项目根

# ========================= 步骤 0A: 加载并验证配置 =========================
if [ ! -f "${SETUP_DIR}/config.sh" ]; then
    echo -e "${RED}❌ 错误: 配置文件 config.sh 未找到！请确保该文件存在于 'deployment/setup/' 目录中。${NC}"
    exit 1
fi

source "${SETUP_DIR}/config.sh" # 加载所有配置变量

# ========================= （新增）命令行参数支持：指定 GCP 项目 =========================
# 用法示例：./init_deploy.sh --project flashmvp-paid
CLI_PROJECT_ID=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        -p|--project)
            if [[ -n "$2" ]]; then
                CLI_PROJECT_ID="$2"
                shift 2
            else
                echo -e "${RED}❌ --project 需要一个参数，例如：--project flashmvp-paid${NC}"
                exit 1
            fi
            ;;
        -h|--help)
            echo "用法: $0 [--project|-p <GCP_PROJECT_ID>]"
            exit 0
            ;;
        *)
            # 忽略未知参数（保持最小侵入）
            shift 1
            ;;
    esac
done
# 若命令行提供了项目，则覆盖 config.sh 中的 GCP_PROJECT_ID
if [[ -n "$CLI_PROJECT_ID" ]]; then
    GCP_PROJECT_ID="$CLI_PROJECT_ID"
fi
# 同时设置当前进程的默认项目（不修改全局 gcloud 配置）
export CLOUDSDK_CORE_PROJECT="$GCP_PROJECT_ID"

# 增强配置验证 - 添加 GCP_PROJECT_ID 检查
if [ -z "$GITHUB_USERNAME" ] || [ -z "$PROJECT_NAME_BASE" ] || [ -z "$GITHUB_REPONAME" ] || [ -z "$GCP_PROJECT_ID" ]; then
    echo -e "${RED}❌ 错误: 请先在 deployment/setup/config.sh 文件中完整设置所有必需的变量，包括 GITHUB_USERNAME, PROJECT_NAME_BASE, GITHUB_REPONAME, 和 GCP_PROJECT_ID！${NC}"
    exit 1
fi

echo -e "${GREEN}=========================================="
echo "🚀 ${PROJECT_NAME_BASE} MVP 初始化脚本 v6.3 (Git-Aware)"
echo "   第一阶段：创建基础资源"
echo -e "==========================================${NC}"
echo -e "\n${GREEN}✅ 配置加载成功: Project='${PROJECT_NAME_BASE}', User='${GITHUB_USERNAME}'${NC}"
echo -e "${CYAN}🕒 当前时间：$(date '+%Y-%m-%d %H:%M:%S')${NC}"

# --- 确认操作 ---
echo -e "\n${YELLOW}此脚本将基于 'deployment/setup/config.sh' 的内容，为您搭建基础框架并生成第二阶段脚本。${NC}"
print_separator
echo -e "${YELLOW}⚠️  权限要求：${NC}"
echo "  - 执行本脚本的GCP账号需要有创建基础资源的权限（如 Editor）。"
echo "  - 后续您需要按照指南，为自己授予更高级的 IAM 管理权限。 "
print_separator
echo ""
read -p "您已确认 'config.sh' 内容无误并准备开始吗？(y/n): " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
    echo "操作已取消。"
    exit 2  # 使用退出码2表示用户取消操作
fi

# ==============================================================================
# 步骤 0B: Git 历史记录清理
# ==============================================================================
cd "${PROJECT_ROOT}"
if [ -d ".git" ]; then
    echo ""
    print_separator
    echo -e "${YELLOW}🔎 检测到 .git 文件夹，这可能包含了模板项目的旧历史记录。${NC}"
    echo -e "${YELLOW}为了确保您的新项目拥有一个干净的版本历史，建议将其移除并重新初始化。${NC}"
    read -p "是否要自动清理旧的 Git 历史并为 '${PROJECT_NAME_BASE}' 项目创建新的历史记录？ (y/n): " confirm_git
    if [[ "$confirm_git" == "y" || "$confirm_git" == "Y" ]]; then
        echo -e "${CYAN}  - 正在移除旧的 .git 文件夹...（正常等待；IO 操作可能需要数秒）${NC}"
        rm -rf .git
        echo -e "${CYAN}  - 正在为新项目初始化 Git 仓库...${NC}"
        git init
        echo -e "${GREEN}✅ Git 历史记录已成功清理并重新初始化！${NC}"
    else
        echo -e "${YELLOW}⚠️  已跳过 Git 历史记录清理。请注意，旧的提交历史仍然存在。${NC}"
    fi
    print_separator
fi
cd "${SCRIPT_DIR}"

# --- 从配置加载变量 ---
PROJECT_NAME="$PROJECT_NAME_BASE"
# GCP_REGION 已通过 source 加载
SERVICE_ACCOUNT_NAME="$GCP_SERVICE_ACCOUNT_NAME_BASE"
UNIQUE_SUFFIX=$(date +%Y%m%d%H%M%S)
WORKLOAD_IDENTITY_POOL_NAME="github-pool-${UNIQUE_SUFFIX}"
WORKLOAD_IDENTITY_PROVIDER_NAME="github-provider"
GCP_SETUP_SCRIPT_NAME="setup_gcp_identity.sh"

# 升级 CLI 工具检查 - 检查工具是否已登录
# --- 步骤1：环境检查 ---
echo -e "\n${YELLOW}[步骤 1/7] 检查必需的 CLI 工具...${NC}"
if ! command -v gcloud &> /dev/null || ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q "."; then
    echo -e "${RED}❌ 错误: gcloud CLI 未安装或未登录。${NC}"
    echo -e "${YELLOW}请参考文档 'deployment/setup/docs/static/cli-setup-guide.md' 完成安装和登录。${NC}"
    exit 1
fi
if ! command -v wrangler &> /dev/null || ! wrangler whoami >/dev/null 2>&1; then
    echo -e "${RED}❌ 错误: wrangler CLI 未安装或未登录。${NC}"
    echo -e "${YELLOW}请参考文档 'deployment/setup/docs/static/cli-setup-guide.md' 完成安装和登录。${NC}"
    exit 1
fi
if ! command -v git &> /dev/null; then echo -e "${RED}❌ 未找到 git CLI。${NC}"; exit 1; fi
echo -e "${GREEN}✅ 工具检查通过${NC}"

# --- 步骤 2/7: 验证 GCP 项目存在性 ---
echo -e "\n${YELLOW}[步骤 2/7] 验证 GCP 项目 '${GCP_PROJECT_ID}'...（只读检查，通常秒级完成）${NC}"
if ! gcloud projects describe "${GCP_PROJECT_ID}" --project="${GCP_PROJECT_ID}" >/dev/null 2>&1; then
    echo -e "${RED}❌ 验证失败: 项目 '${GCP_PROJECT_ID}' 不存在或您没有访问权限。${NC}"
    
    # 调用 generate_setup_guide.sh 并传递正确的路径
    "${SCRIPT_DIR}/generate_setup_guide.sh" \
      "${SETUP_DIR}/docs/templates/create-gcp-project-guide.template.md" \
      "${SETUP_DIR}/output/create-gcp-project-guide.md"

    echo -e "\n${YELLOW}为了帮助您解决问题，已为您生成一份专属操作指南，请查看:${NC}"
    echo -e "${GREEN}  📄  deployment/setup/output/create-gcp-project-guide.md${NC}"
    echo -e "\n请按照指南创建并配置好项目后，再重新运行本脚本。"
    exit 1
else
    echo -e "${GREEN}✅ 项目验证成功！${NC}"
    read -p "将在项目 '${GCP_PROJECT_ID}' 中创建资源，请确认是否继续？(y/n): " confirm_project
    if [[ "$confirm_project" != "y" && "$confirm_project" != "Y" ]]; then
        echo "操作已取消。"
        exit 2  # 使用退出码2表示用户取消操作
    fi
fi

# --- 步骤 3/7: 获取项目和账户信息 ---
echo -e "\n${YELLOW}[步骤 3/7] 获取项目和账户信息...${NC}"
USER_ACCOUNT=$(gcloud config get-value account 2>/dev/null)
CF_ACCOUNT_ID=$(wrangler whoami 2>/dev/null | grep -oE '[a-f0-9]{32}')
PROJECT_NUMBER=$(gcloud projects describe $GCP_PROJECT_ID --project=$GCP_PROJECT_ID --format="value(projectNumber)")
echo -e "${GREEN}✅ 项目和账户信息获取成功${NC}"
echo "  GCP 项目 ID: $GCP_PROJECT_ID"
echo "  GCP 登录账号: $USER_ACCOUNT"

# --- 步骤4/7：清理旧资源 ---
echo -e "\n${YELLOW}[步骤 4/7] 检查并清理旧资源...${NC}"
echo -e "${CYAN}说明：本步骤包含 Cloud Run / IAM 的只读检查与清理动作。"
echo -e "     若这是该项目首次使用相关 API，gcloud 可能在内部触发\"隐式启用 API\"，总体耗时可能 1–3 分钟。"
echo -e "     当看到\"正在删除…\"或\"正在执行…\"但无更多输出时，属于【正常等待】而非卡死。\n${NC}"

# 只读：关键 API 启用状态的可视化（不改变任何状态）
echo -e "${CYAN}🔎 只读检查：关键 API 启用情况（非必需，仅用于判断是否在正常等待）${NC}"
gcloud services list --enabled --project="$GCP_PROJECT_ID" \
  | grep -E 'run.googleapis.com|iam\.googleapis\.com|iamcredentials\.googleapis\.com|cloudbuild\.googleapis\.com|artifactregistry\.googleapis\.com|serviceusage\.googleapis\.com' \
  || true

GCP_SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${GCP_PROJECT_ID}.iam.gserviceaccount.com"

# Cloud Run 旧服务状态提示
echo -e "${CYAN}🔎 检查 Cloud Run 服务是否存在：${PROJECT_NAME}-backend（region=${GCP_REGION}）${NC}"
if gcloud run services describe ${PROJECT_NAME}-backend --region=$GCP_REGION --project=$GCP_PROJECT_ID &>/dev/null; then
    echo -e "${YELLOW}发现旧的 Cloud Run 服务，开始删除…（正常等待，可能 30–120 秒）${NC}"
    gcloud run services delete ${PROJECT_NAME}-backend --region=$GCP_REGION --project=$GCP_PROJECT_ID --quiet
    echo "已删除旧的 Cloud Run 服务。"
    # 删除后再次只读确认
    if gcloud run services describe ${PROJECT_NAME}-backend --region=$GCP_REGION --project=$GCP_PROJECT_ID &>/dev/null; then
        echo -e "${YELLOW}⚠️ 二次检查：Cloud Run 服务仍可被描述。这通常表示后台仍在收尾，稍后步骤会重新查询。${NC}"
    else
        echo -e "${GREEN}✅ 二次检查：Cloud Run 服务已不存在。${NC}"
    fi
else
    echo -e "${GREEN}未发现旧的 Cloud Run 服务。${NC}"
fi

# 服务账号只读检查与清理
echo -e "${CYAN}🔎 检查旧服务账号是否存在：${GCP_SERVICE_ACCOUNT_EMAIL}${NC}"
if gcloud iam service-accounts describe $GCP_SERVICE_ACCOUNT_EMAIL --project=$GCP_PROJECT_ID &>/dev/null; then
    echo -e "${YELLOW}发现旧的服务账号，开始删除…（正常等待，通常较快）${NC}"
    gcloud iam service-accounts delete $GCP_SERVICE_ACCOUNT_EMAIL --project=$GCP_PROJECT_ID --quiet
    echo "已删除旧的服务账号。"
    # 删除后只读确认
    if gcloud iam service-accounts describe $GCP_SERVICE_ACCOUNT_EMAIL --project=$GCP_PROJECT_ID &>/dev/null; then
        echo -e "${YELLOW}⚠️ 二次检查：服务账号仍可被描述；这通常是权限缓存尚未刷新。后续步骤会再次使用该邮箱进行创建。${NC}"
    else
        echo -e "${GREEN}✅ 二次检查：服务账号已不存在。${NC}"
    fi
else
    echo -e "${GREEN}未发现旧的服务账号。${NC}"
fi
echo -e "${GREEN}✅ 资源检查完成${NC}"

# --- 步骤5/7：创建 GCP 基础资源 ---
echo -e "\n${YELLOW}[步骤 5/7] 创建 GCP 基础资源...${NC}"

# 启用所有需要的API
echo "正在启用核心 GCP 服务 API..."
echo -e "${CYAN}提示：若首次启用，这一步可能需要 1–3 分钟，请耐心等待（正常等待）。${NC}"
gcloud services enable run.googleapis.com iamcredentials.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com serviceusage.googleapis.com --project=$GCP_PROJECT_ID

wait_with_message 5 "等待 API 启用结果在控制面板侧生效（大多数情况下已足够）"
# 只读确认
echo -e "${CYAN}🔎 只读确认：已启用的相关 API（截取）${NC}"
gcloud services list --enabled --project="$GCP_PROJECT_ID" \
  | grep -E 'run.googleapis.com|iamcredentials\.googleapis\.com|cloudbuild\.googleapis\.com|artifactregistry\.googleapis\.com|serviceusage\.googleapis\.com' \
  || true

# 【新增】Artifact Registry 预创建 + Cloud Build SA 授权（修复 CI 403：repositories.create）
echo -e "\n${YELLOW}【新增】自动修复：Artifact Registry 预创建与授权（避免 CI 403）${NC}"
# 1) 预创建 AR 仓库（与 Cloud Run 同 Region）
if gcloud artifacts repositories describe cloud-run-source-deploy --project=$GCP_PROJECT_ID --location=$GCP_REGION >/dev/null 2>&1; then
  echo -e "${GREEN}✅ 已存在 AR 仓库：cloud-run-source-deploy（region=${GCP_REGION}）${NC}"
else
  echo -e "${CYAN}⛏️  正在创建 AR 仓库 cloud-run-source-deploy（region=${GCP_REGION}）…（正常等待）${NC}"
  gcloud artifacts repositories create cloud-run-source-deploy \
    --project=$GCP_PROJECT_ID \
    --location=$GCP_REGION \
    --repository-format=docker \
    --description="Cloud Run source deploy images" \
    --quiet
  echo -e "${GREEN}✅ AR 仓库创建成功${NC}"
fi

# 2) 给 Cloud Build 默认 SA 写入权限（推镜像用）
echo -e "${CYAN}🔐 为 Cloud Build 默认服务账号授予 artifactregistry.writer…${NC}"
gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" \
  --role="roles/artifactregistry.writer" \
  --quiet
echo -e "${GREEN}✅ 授权完成（Cloud Build → AR 写入）${NC}"

# 3) 可选：输出只读列表，便于排查（不报错）
echo -e "${CYAN}📋 只读列出 AR 仓库（region=${GCP_REGION}）${NC}"
gcloud artifacts repositories list --project=$GCP_PROJECT_ID --location=$GCP_REGION || true

# 创建Cloud Run服务占位符
echo "正在创建 Cloud Run 服务占位符..."
echo -e "${CYAN}提示：Cloud Run 首次部署镜像到指定 Region 可能需要 10–60 秒（正常等待）。${NC}"
gcloud run deploy ${PROJECT_NAME}-backend \
  --image=us-docker.pkg.dev/cloudrun/container/hello \
  --region=$GCP_REGION \
  --project=$GCP_PROJECT_ID \
  --allow-unauthenticated \
  --min-instances=0 \
  --max-instances=2 \
  --memory=256Mi \
  --cpu=1 \
  --quiet

CLOUD_RUN_URL=$(gcloud run services describe ${PROJECT_NAME}-backend --region=$GCP_REGION --project=$GCP_PROJECT_ID --format="value(status.url)")
echo -e "${GREEN}✅ Cloud Run 服务已就绪：${CLOUD_RUN_URL}${NC}"

# 创建服务账号
echo "正在创建服务账号..."
echo -e "${CYAN}服务账号邮箱：${GCP_SERVICE_ACCOUNT_EMAIL}${NC}"
gcloud iam service-accounts create $SERVICE_ACCOUNT_NAME \
  --display-name="GitHub Deployer for ${PROJECT_NAME_BASE}" \
  --project=$GCP_PROJECT_ID

wait_with_message 3 "等待服务账号创建在权限系统侧可见（正常等待）"
# 只读确认
echo -e "${CYAN}🔎 只读确认：服务账号是否可见${NC}"
gcloud iam service-accounts describe "$GCP_SERVICE_ACCOUNT_EMAIL" --project="$GCP_PROJECT_ID" >/dev/null 2>&1 \
  && echo -e "${GREEN}✅ 服务账号已可见${NC}" \
  || echo -e "${YELLOW}⚠️ 服务账号暂不可见（缓存未刷新亦属正常）。后续授予权限时如遇失败，请重试一次该步骤。${NC}"

# ===== 新增：强韧等待（最多 60 秒），确保 SA 在 IAM 中完全可见后再授予角色 =====
echo -e "${CYAN}⏳ 等待服务账号在 IAM 中完全可见（最多 60 秒）...${NC}"
sa_ready=0
for i in {1..12}; do
  if gcloud iam service-accounts describe "$GCP_SERVICE_ACCOUNT_EMAIL" --project="$GCP_PROJECT_ID" >/dev/null 2>&1; then
    sa_ready=1
    break
  fi
  sleep 5
done
if [ "$sa_ready" -ne 1 ]; then
  echo -e "${RED}❌ 服务账号仍不可见，请稍后重试本步骤或手动排查（gcloud iam service-accounts list）。${NC}"
  exit 1
fi

# 为服务账号授予IAM角色
echo "正在为服务账号授予 IAM 角色..."
echo -e "${CYAN}提示：以下多条命令将串行执行；若无额外输出，属于正常等待。${NC}"
gcloud projects add-iam-policy-binding $GCP_PROJECT_ID --member="serviceAccount:${GCP_SERVICE_ACCOUNT_EMAIL}" --role="roles/run.admin" --quiet
gcloud projects add-iam-policy-binding $GCP_PROJECT_ID --member="serviceAccount:${GCP_SERVICE_ACCOUNT_EMAIL}" --role="roles/iam.serviceAccountUser" --quiet
gcloud projects add-iam-policy-binding $GCP_PROJECT_ID --member="serviceAccount:${GCP_SERVICE_ACCOUNT_EMAIL}" --role="roles/serviceusage.serviceUsageConsumer" --quiet
# （保留）给部署 SA 写 AR；结合预创建仓库，此角色已满足常见 CI 场景
gcloud projects add-iam-policy-binding $GCP_PROJECT_ID --member="serviceAccount:${GCP_SERVICE_ACCOUNT_EMAIL}" --role="roles/artifactregistry.writer" --quiet
gcloud projects add-iam-policy-binding $GCP_PROJECT_ID --member="serviceAccount:${GCP_SERVICE_ACCOUNT_EMAIL}" --role="roles/cloudbuild.builds.editor" --quiet
gcloud projects add-iam-policy-binding $GCP_PROJECT_ID --member="serviceAccount:${GCP_SERVICE_ACCOUNT_EMAIL}" --role="roles/storage.admin" --quiet
echo -e "${GREEN}✅ GCP 基础资源创建成功，并已配置完整部署权限！${NC}"
echo -e "${CYAN}（说明）本脚本已：1）预创建 AR 仓库；2）授权 Cloud Build → AR 写入；通常可避免 CI 中的 403。${NC}"

# ==============================================================================
# 步骤 5.5/7: 自动化更新项目名称以实现完全通用性
# ==============================================================================
echo -e "\n${YELLOW}[步骤 5.5/7] 正在将模板名称 'flashmvp' 替换为 '${PROJECT_NAME_BASE}'...${NC}"

# 1. 更新 wrangler.toml 中的项目名称
echo "  - 更新 frontend/wrangler.toml..."
sed -i.bak "s/name = \"flashmvp\"/name = \"${PROJECT_NAME_BASE}\"/" "${PROJECT_ROOT}/frontend/wrangler.toml"

# 2. 全局替换前端文件中 'flashmvp_' 前缀
echo "  - 更新前端 JS/HTML 文件中的 'flashmvp_' 前缀..."
find "${PROJECT_ROOT}/frontend" -type f \( -name "*.js" -o -name "*.html" \) -exec sed -i.bak "s/flashmvp_/${PROJECT_NAME_BASE}_/g" {} +

# 3. 清理 sed 命令生成的备份文件
find "${PROJECT_ROOT}/frontend" -name "*.bak" -delete

echo -e "${GREEN}✅ 项目名称自动化更新完成！${NC}"

# --- 步骤6/7：创建 Cloudflare 资源 ---
echo -e "\n${YELLOW}[步骤 6/7] 创建 Cloudflare 资源...${NC}"
cd "${PROJECT_ROOT}"
if wrangler d1 list | grep -q "${PROJECT_NAME}-usage"; then
    echo -e "${YELLOW}⚠️  D1 数据库已存在，跳过创建${NC}"
    D1_DATABASE_ID=$(wrangler d1 list --json 2>/dev/null | jq -r ".[] | select(.name == \"${PROJECT_NAME}-usage\") | .uuid")
else
    echo -e "${CYAN}正在创建 D1 数据库…（正常等待）${NC}"
    D1_DATABASE_ID=$(wrangler d1 create ${PROJECT_NAME}-usage | grep -o '"database_id": "[^"]*' | cut -d'"' -f4)
    echo -e "${GREEN}✅ D1 数据库创建成功${NC}"
fi
echo -e "${CYAN}写入开发环境变量文件：frontend/.dev.vars${NC}"
cat > "${PROJECT_ROOT}/frontend/.dev.vars" << EOF
# Auto-generated by init_deploy.sh
[[d1_databases]]
binding = "DB"
database_name = "${PROJECT_NAME}-usage"
database_id = "${D1_DATABASE_ID}"
EOF

if wrangler pages project list | grep -q "$PROJECT_NAME"; then
    echo -e "${YELLOW}⚠️  Pages 项目已存在，跳过创建${NC}"
else
    echo -e "${CYAN}正在创建 Cloudflare Pages 项目…（正常等待）${NC}"
    wrangler pages project create $PROJECT_NAME --production-branch main
    echo -e "${GREEN}✅ Pages 项目创建成功${NC}"
fi
cd "${SCRIPT_DIR}"
echo -e "${GREEN}✅ Cloudflare 资源配置完成${NC}"

# --- 步骤7/7：生成最终产出物 ---
echo -e "\n${YELLOW}[步骤 7/7] 生成第二阶段脚本和操作指南...${NC}"

mkdir -p "${SETUP_DIR}/output"
date > "${SETUP_DIR}/output/.init-complete"

MANUAL_GUIDE_FILENAME="manual-setup-guide.md"
GITHUB_REPO="${GITHUB_USERNAME}/${GITHUB_REPONAME}"

# ==============================================================================
# 动态生成第二阶段的自动化脚本 setup_gcp_identity.sh
# ==============================================================================
cat > "${SETUP_DIR}/output/${GCP_SETUP_SCRIPT_NAME}" << 'EOF'
#!/bin/bash
set -e
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
CYAN=$'\033[0;36m'
RED=$'\033[1;31m'
NC=$'\033[0m'

# 定义路径
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
MANUAL_GUIDE_PATH="${SCRIPT_DIR}/manual-setup-guide.md"

echo -e "${GREEN}======================================================"
echo "🚀 开始执行第二阶段：全自动配置 GCP Workload Identity"
echo -e "======================================================${NC}"
EOF

# 继续写入变量替换后的内容
cat >> "${SETUP_DIR}/output/${GCP_SETUP_SCRIPT_NAME}" << EOF
# 让二阶段脚本始终指向正确的项目
export CLOUDSDK_CORE_PROJECT="${GCP_PROJECT_ID}"

# 0. 预授权：为当前登录用户自动补齐必要角色，避免 PERMISSION_DENIED
USER_ACCOUNT=\$(gcloud config get-value account 2>/dev/null)
echo "0. 正在为当前用户(\${USER_ACCOUNT})补齐必要角色..."
gcloud projects add-iam-policy-binding "${GCP_PROJECT_ID}" \\
  --member="user:\${USER_ACCOUNT}" \\
  --role="roles/iam.workloadIdentityPoolAdmin" \\
  --quiet || true
gcloud projects add-iam-policy-binding "${GCP_PROJECT_ID}" \\
  --member="user:\${USER_ACCOUNT}" \\
  --role="roles/iam.serviceAccountAdmin" \\
  --quiet || true

echo "1. 正在创建 Workload Identity Pool: ${WORKLOAD_IDENTITY_POOL_NAME}..."
gcloud iam workload-identity-pools create "${WORKLOAD_IDENTITY_POOL_NAME}" \\
  --project="${GCP_PROJECT_ID}" \\
  --location="global" \\
  --display-name="GitHub Actions Pool"
echo "2. 正在创建 OIDC Provider 并设置映射与条件..."
gcloud iam workload-identity-pools providers create-oidc "${WORKLOAD_IDENTITY_PROVIDER_NAME}" \\
  --project="${GCP_PROJECT_ID}" \\
  --location="global" \\
  --workload-identity-pool="${WORKLOAD_IDENTITY_POOL_NAME}" \\
  --display-name="GitHub Actions Provider" \\
  --issuer-uri="https://token.actions.githubusercontent.com" \\
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \\
  --attribute-condition="attribute.repository.startsWith('${GITHUB_USERNAME}/')"
echo "3. 正在为服务账号授予信任关系..."
gcloud iam service-accounts add-iam-policy-binding "${GCP_SERVICE_ACCOUNT_EMAIL}" \\
  --project="${GCP_PROJECT_ID}" \\
  --role="roles/iam.workloadIdentityUser" \\
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WORKLOAD_IDENTITY_POOL_NAME}/attribute.repository/${GITHUB_REPO}"
echo "4. 正在获取 Provider 的资源名称..."
# 直接构造（无需等待控制面板可见性）
PROVIDER_RESOURCE_NAME="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${WORKLOAD_IDENTITY_POOL_NAME}/providers/${WORKLOAD_IDENTITY_PROVIDER_NAME}"

# （可选）最多重试 8 次，仅用于“可描述性”确认，避免后续文档替换时还没生效
for i in 1 2 3 4 5 6 7 8; do
  if gcloud iam workload-identity-pools providers describe "${WORKLOAD_IDENTITY_PROVIDER_NAME}" \\
      --project="${GCP_PROJECT_ID}" \\
      --location="global" \\
      --workload-identity-pool="${WORKLOAD_IDENTITY_POOL_NAME}" \\
      --format="value(name)" >/dev/null 2>&1; then
    break
  fi
  echo "   Provider 尚未可见，等待 5s 后重试（第 \$i 次）..."
  sleep 5
done
echo -e "${GREEN}✅ Workload Identity 配置成功！${NC}"

# ===== 自动更新 manual-setup-guide.md =====
echo ""
echo -e "\${CYAN}🔄 正在自动更新操作指南...${NC}"

if [ -f "\${MANUAL_GUIDE_PATH}" ]; then
    # 创建备份
    cp "\${MANUAL_GUIDE_PATH}" "\${MANUAL_GUIDE_PATH}.bak"
    
    # 使用占位符进行精确替换
    sed -i "s|${PROVIDER_PLACEHOLDER}|\${PROVIDER_RESOURCE_NAME}|g" "\${MANUAL_GUIDE_PATH}"
    
    # 验证替换
    if grep -q "\${PROVIDER_RESOURCE_NAME}" "\${MANUAL_GUIDE_PATH}"; then
        echo -e "\${GREEN}✅ 文档更新成功！Provider 值已自动填入。${NC}"
        rm -f "\${MANUAL_GUIDE_PATH}.bak"
    else
        echo -e "\${YELLOW}⚠️  文档更新可能失败，备份已保留。${NC}"
    fi
fi

# ===== 生成可直接复制的配置文件 =====
cat > "\${SCRIPT_DIR}/github-secrets-values.txt" << SECRETS_EOF
# ===== GitHub Secrets 配置值 =====
# 直接复制每一行的值到 GitHub Secrets

CLOUDFLARE_ACCOUNT_ID=${CF_ACCOUNT_ID}
GCP_PROJECT_ID=${GCP_PROJECT_ID}
GCP_SERVICE_ACCOUNT=${GCP_SERVICE_ACCOUNT_EMAIL}
GCP_WORKLOAD_IDENTITY_PROVIDER=\${PROVIDER_RESOURCE_NAME}
CF_PAGES_PROJECT_NAME=${PROJECT_NAME}
CF_D1_DATABASE_NAME=${PROJECT_NAME}-usage
CF_D1_DATABASE_ID=${D1_DATABASE_ID}

# API Keys (需要您手动填入)
GEMINI_API_KEY=<您的Gemini API Key>
CLOUDFLARE_API_TOKEN=<您的Cloudflare API Token>
SECRETS_EOF

# ===== 更新 deployment-config.txt =====
echo "GCP_WORKLOAD_IDENTITY_PROVIDER=\${PROVIDER_RESOURCE_NAME}" >> "\${SCRIPT_DIR}/deployment-config.txt"

# ===== 用户友好的输出 =====
echo ""
echo -e "\${GREEN}============================================================================================"
echo -e "✅ GCP Workload Identity 配置成功!"
echo -e "============================================================================================\${NC}"
echo ""
echo -e "\${YELLOW}📋 所有配置值已准备就绪：\${NC}"
echo -e "   1. \${GREEN}manual-setup-guide.md\${NC} - 已自动更新所有值"
echo -e "   2. \${GREEN}github-secrets-values.txt\${NC} - 可直接复制的 Secrets 列表"
echo -e "   3. \${GREEN}deployment-config.txt\${NC} - 完整的部署配置记录"
echo ""
echo -e "\${CYAN}💡 提示：您现在可以直接从文档中复制所有配置，无需手动记录 Provider 值！\${NC}"
echo ""
echo -e "\${YELLOW}============================================================================================"
echo "GCP_WORKLOAD_IDENTITY_PROVIDER = \${PROVIDER_RESOURCE_NAME}"
echo -e "============================================================================================\${NC}"
EOF
chmod +x "${SETUP_DIR}/output/${GCP_SETUP_SCRIPT_NAME}"
echo "✅ 已生成第二阶段自动化脚本: deployment/setup/output/${GCP_SETUP_SCRIPT_NAME}"

# ==============================================================================
# 动态生成全新的 manual-setup-guide.md（使用占位符）
# ==============================================================================
GUIDE_CONTENT=$(cat << EOF

${GREEN}==============================================================================
🎉 第一阶段完成！基础框架已搭建。
==============================================================================${NC}

${YELLOW}下一步，请严格按照以下手动步骤操作，以完成整个部署流程。${NC}

${RED}==============================================================================
⚠️  重要：手动操作指南
==============================================================================${NC}

${YELLOW}步骤 A: 【必需】为您的GCP账号授予权限 (Grant Permissions)${NC}
${WHITE}为了确保第二阶段的自动化脚本能成功运行，您必须先为自己授予必需的权限。${NC}
1. 打开项目的 IAM 权限页面：
   ${CYAN}https://console.cloud.google.com/iam-admin/iam?project=${GCP_PROJECT_ID}${NC}
2. 点击页面上方的 ${GREEN}"授予访问权限" (GRANT ACCESS)${NC} 按钮。
3. 在 "新的主账号" (New principals) 字段，输入您的邮箱: ${GREEN}${USER_ACCOUNT}${NC}
4. 在 "选择角色" (Select a role) 字段，搜索并添加 ${GREEN}IAM Workload Identity Pool Admin${NC} 角色。
5. ${YELLOW}(推荐)${NC} 再次添加 ${GREEN}Service Account Admin${NC} 角色。
6. 点击 "保存" (Save)，并等待1-2分钟让权限生效。

${CYAN}--- AI Assistant Prompt (步骤A) ---${NC}
${WHITE}如果您需要更详细的操作指引，可以将以下内容复制给任何AI助手：${NC}

"我需要在 GCP (Google Cloud Platform) 中为我的账号授予权限。请提供零基础的详细操作步骤。
- 我的 GCP 项目 ID 是: ${GCP_PROJECT_ID}
- 我的 GCP 账号邮箱是: ${USER_ACCOUNT}
- 我需要授予的角色是: IAM Workload Identity Pool Admin 和 Service Account Admin
- IAM 页面直接链接: https://console.cloud.google.com/iam-admin/iam?project=${GCP_PROJECT_ID}

请告诉我：
1. 如何找到并点击 'GRANT ACCESS' 按钮（包括按钮的具体位置、颜色等视觉特征）
2. 如何正确输入我的邮箱地址
3. 如何搜索并添加这两个角色（包括搜索框位置、如何输入搜索关键词）
4. 如何确认并保存（包括保存按钮的位置）
5. 如何验证权限是否已经生效

请用最简单直白的语言，假设我完全不了解 GCP 界面。"

${CYAN}════════════════════════════════════════════════════════════════════════════${NC}
${CYAN}════════════════════════════════════════════════════════════════════════════${NC}


${YELLOW}步骤 B: 【自动】配置GCP身份联合${NC}
${WHITE}完成上述授权后，回到您的终端：${NC}
1. 当系统询问您是否已完成步骤 A 时，输入 ${GREEN}y${NC} 并按回车。
2. 脚本将自动执行第二阶段配置。
3. 执行成功后，会输出一个 ${GREEN}GCP_WORKLOAD_IDENTITY_PROVIDER${NC} 的值。请复制它，用于下一步。

${CYAN}注意：如果您意外关闭了终端或脚本中断，请重新运行 setup_wizard.sh 即可。${NC}

${CYAN}════════════════════════════════════════════════════════════════════════════${NC}
${CYAN}════════════════════════════════════════════════════════════════════════════${NC}

${YELLOW}步骤 C: 配置 GitHub Secrets${NC}
在您的 GitHub 仓库 (${GITHUB_REPO}) 中添加以下 Secrets。
${WHITE}路径: Settings > Secrets and variables > Actions > New repository secret${NC}

${CYAN}--- 基础设施 Secrets (必需) ---${NC}
1. ${GREEN}CLOUDFLARE_ACCOUNT_ID${NC} = ${CF_ACCOUNT_ID}
2. ${GREEN}GCP_PROJECT_ID${NC} = ${GCP_PROJECT_ID}
3. ${GREEN}GCP_SERVICE_ACCOUNT${NC} = ${GCP_SERVICE_ACCOUNT_EMAIL}
4. ${GREEN}GCP_WORKLOAD_IDENTITY_PROVIDER${NC} = ${PROVIDER_PLACEHOLDER}
5. ${GREEN}CF_PAGES_PROJECT_NAME${NC} = ${PROJECT_NAME}
6. ${GREEN}CF_D1_DATABASE_NAME${NC} = ${PROJECT_NAME}-usage
7. ${GREEN}CF_D1_DATABASE_ID${NC} = ${D1_DATABASE_ID}

${CYAN}--- AI 服务 API 密钥 (至少配置一个) ---${NC}
${WHITE}这些密钥将通过CI/CD安全地注入到您的后端服务中。${NC}
8. ${GREEN}GEMINI_API_KEY${NC} = [填入您的Google Gemini API密钥]
9. ${GREEN}GEMINI_API_KEY_PAID${NC} = ${YELLOW}(可选)${NC} [填入您付费版的Gemini密钥]
10. ${GREEN}OPENAI_API_KEY${NC} = ${YELLOW}(可选)${NC} [填入您的OpenAI API密钥]

${CYAN}--- AI Assistant Prompt (步骤C) ---${NC}
${WHITE}如果您需要更详细的操作指引，可以将以下内容复制给任何AI助手：${NC}

"我需要在 GitHub 仓库中配置 Secrets。请提供零基础的详细操作步骤。
- 我的 GitHub 仓库是: https://github.com/${GITHUB_REPO}
- 我需要添加以下 Secrets（名称必须完全一致，包括大小写）：
  * CLOUDFLARE_ACCOUNT_ID = ${CF_ACCOUNT_ID}
  * GCP_PROJECT_ID = ${GCP_PROJECT_ID}
  * GCP_SERVICE_ACCOUNT = ${GCP_SERVICE_ACCOUNT_EMAIL}
  * GCP_WORKLOAD_IDENTITY_PROVIDER = ${PROVIDER_PLACEHOLDER}
  * CF_PAGES_PROJECT_NAME = ${PROJECT_NAME}
  * CF_D1_DATABASE_NAME = ${PROJECT_NAME}-usage
  * CF_D1_DATABASE_ID = ${D1_DATABASE_ID}
  * GEMINI_API_KEY = [我需要指导如何获取]
  * CLOUDFLARE_API_TOKEN = [我会在步骤D创建]

请告诉我：
1. 如何导航到 Settings 页面（包括按钮/链接的具体位置）
2. 如何找到 'Secrets and variables' 然后点击 'Actions'
3. 如何点击 'New repository secret' 按钮
4. 如何正确输入 Secret 名称和值（包括输入框的位置、如何粘贴值）
5. 如何保存每个 Secret
6. 如何验证 Secrets 是否已添加成功
7. 如何获取 Google Gemini API Key（包括注册链接和步骤）

请用最简单直白的语言，包括每个按钮的视觉描述。"

${CYAN}════════════════════════════════════════════════════════════════════════════${NC}
${CYAN}════════════════════════════════════════════════════════════════════════════${NC}

${YELLOW}步骤 D: 创建 Cloudflare API Token${NC}
1. 访问：${CYAN}https://dash.cloudflare.com/profile/api-tokens${NC}
2. 创建一个自定义令牌，并授予 ${GREEN}D1 Write${NC} 和 ${GREEN}Pages Write${NC} 权限。
3. 将生成的 Token 添加到名为 ${GREEN}CLOUDFLARE_API_TOKEN${NC} 的 GitHub Secret 中。

${CYAN}--- AI Assistant Prompt (步骤D) ---${NC}
${WHITE}如果您需要更详细的操作指引，可以将以下内容复制给任何AI助手：${NC}

"我需要创建一个 Cloudflare API Token。请提供零基础的详细操作步骤。
- Cloudflare API Tokens 页面: https://dash.cloudflare.com/profile/api-tokens
- 我需要的权限: D1 Write 和 Pages Write
- 我的 Cloudflare 账号 ID: ${CF_ACCOUNT_ID}

请告诉我：
1. 如何在页面上找到并点击 'Create Token' 按钮
2. 如何选择 'Custom token' 选项
3. 如何为 Token 命名（建议名称）
4. 如何添加 'D1 Write' 权限（包括如何搜索、选择权限级别）
5. 如何添加 'Pages Write' 权限（包括如何搜索、选择权限级别）
6. 如何设置 Token 的有效期（建议设置）
7. 如何完成创建并复制 Token
8. 重要安全提示：Token 只显示一次，必须立即复制保存
9. 如何将这个 Token 添加到 GitHub Secret（名称必须是 CLOUDFLARE_API_TOKEN）

请用最简单直白的语言，包括每个选项和按钮的详细描述。"

${CYAN}════════════════════════════════════════════════════════════════════════════${NC}
${CYAN}════════════════════════════════════════════════════════════════════════════${NC}

${YELLOW}步骤 E: 触发最终部署${NC}
${WHITE}完成以上所有 Secrets 配置后，您的云环境已准备就绪。${NC}
1. ${RED}(重要)${NC} 关联您新创建的 GitHub 仓库并进行首次提交:
   ${GREEN}cd ../../  # 返回项目根目录
   ${GREEN}git remote add origin https://github.com/${GITHUB_REPO}.git${NC}
   ${GREEN}git add .${NC}
   ${GREEN}git commit -m "chore: Initial setup for ${PROJECT_NAME_BASE}"${NC}
2. 将代码推送到远程仓库以触发 GitHub Actions 自动部署：
   ${GREEN}git push -u origin main${NC}

${CYAN}--- AI Assistant Prompt (步骤E) ---${NC}
${WHITE}如果您需要更详细的操作指引，可以将以下内容复制给任何AI助手：${NC}

"我需要将本地代码推送到 GitHub 仓库并触发自动部署。请提供零基础的详细操作步骤。
- 我的 GitHub 仓库: https://github.com/${GITHUB_REPO}
- 我的项目名称: ${PROJECT_NAME_BASE}
- 我当前在目录: deployment/setup/internal/

请告诉我：
1. 如何使用终端命令返回到项目根目录
2. 如何关联远程 GitHub 仓库（git remote add 命令的详细解释）
3. 如何添加所有文件到 git（git add . 的含义）
4. 如何创建首次提交（commit message 的规范）
5. 如何推送代码到 GitHub（git push 命令的详细解释）
6. 如何在 GitHub 网站上查看部署状态（Actions 页面位置）
7. 如何判断部署是否成功（绿色勾号的含义）
8. 部署成功后如何访问我的应用
9. 如果部署失败如何查看错误日志

请用最简单直白的语言，假设我不熟悉 Git 和命令行操作。"

${WHITE}部署成功后，您的 ${PROJECT_NAME_BASE} 应用即可在线访问！${NC}

${CYAN}════════════════════════════════════════════════════════════════════════════${NC}
${CYAN}════════════════════════════════════════════════════════════════════════════${NC}

${YELLOW}附录 F：Artifact Registry 403 处理（CI 从源码部署常见问题）${NC}

${WHITE}典型报错：${NC}
- ${RED}IAM_PERMISSION_DENIED / Permission 'artifactregistry.repositories.create' denied${NC}

${WHITE}成因与方案：${NC}
1) ${GREEN}方案一（已由本脚本自动完成）${NC}：预创建仓库 ${CYAN}cloud-run-source-deploy${NC}（region=${GCP_REGION}），并给 Cloud Build 默认服务账号 ${CYAN}${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com${NC} 授予 ${GREEN}roles/artifactregistry.writer${NC}。CI 随后将直接推镜像，无需创建仓库。
2) 方案二（可选）: 若您希望 CI 具备“自动创建仓库”的能力，可追加给部署服务账号 ${CYAN}${GCP_SERVICE_ACCOUNT_EMAIL}${NC} 角色 ${GREEN}roles/artifactregistry.admin${NC}（项目级）。请评估安全策略后再使用。
3) 排错建议：在 CI 中加入以下探针方便定位：
   - ${CYAN}gcloud config get-value account${NC}（确认真实使用的服务账号）
   - ${CYAN}gcloud artifacts repositories list --project=${GCP_PROJECT_ID} --location=${GCP_REGION}${NC}（确认仓库存在/区域正确）

EOF
)

# 将手动指南写入文件（去除颜色控制符）
echo "${GUIDE_CONTENT}" | sed 's/\x1b\[[0-9;]*m//g' > "${SETUP_DIR}/output/${MANUAL_GUIDE_FILENAME}"
echo "✅ 已生成手动操作指南: deployment/setup/output/${MANUAL_GUIDE_FILENAME}"

# 生成部署配置文件
cat > "${SETUP_DIR}/output/deployment-config.txt" << EOF
# Auto-generated by init_deploy.sh
# This file contains a snapshot of the configuration for this deployment run.
GCP_PROJECT_ID=${GCP_PROJECT_ID}
GCP_PROJECT_NUMBER=${PROJECT_NUMBER}
GCP_USER_ACCOUNT=${USER_ACCOUNT}
CF_ACCOUNT_ID=${CF_ACCOUNT_ID}
D1_DATABASE_ID=${D1_DATABASE_ID}
GCP_SERVICE_ACCOUNT_EMAIL=${GCP_SERVICE_ACCOUNT_EMAIL}
GITHUB_REPO=${GITHUB_REPO}
CLOUD_RUN_URL=${CLOUD_RUN_URL}
WORKLOAD_IDENTITY_POOL_NAME=${WORKLOAD_IDENTITY_POOL_NAME}
EOF
echo "✅ 已生成部署配置文件: deployment/setup/output/deployment-config.txt"

# ==============================================================================
# 交互式执行第二阶段
# ==============================================================================
print_separator
echo -e "${GREEN}✅ 第一阶段脚本执行完毕！${NC}"
echo -e "${YELLOW}下一步是配置 GCP Workload Identity，这需要您先手动为自己的 GCP 账号授予权限。${NC}"
echo -e "请打开新生成的 '${WHITE}deployment/setup/output/${MANUAL_GUIDE_FILENAME}${NC}' 文件，并严格按照其中的【步骤 A】进行操作。"
echo ""
read -p "您是否已经完成了【步骤 A】中的手动授权？(y/n): " confirm_phase2

if [[ "$confirm_phase2" == "y" || "$confirm_phase2" == "Y" ]]; then
    echo -e "\n${GREEN}好的，将立即为您自动执行第二阶段脚本...${NC}"
    cd "${SETUP_DIR}/output"
    ./${GCP_SETUP_SCRIPT_NAME}
    cd "${SCRIPT_DIR}"
    
    echo -e "\n${GREEN}✅ 第二阶段脚本执行完毕！${NC}"
    echo -e "${YELLOW}请继续参照 'deployment/setup/output/${MANUAL_GUIDE_FILENAME}' 文件，完成剩余的【步骤 C, D, E】，以完成全部部署流程。${NC}"
else
    echo -e "\n${CYAN}好的，操作已暂停。${NC}"
    echo -e "${YELLOW}请您务必先完成手动授权，然后重新运行 setup_wizard.sh 即可继续。${NC}"
    echo -e "${YELLOW}如果您已经完成了第一阶段，重新运行 setup_wizard.sh 时会自动跳过已完成的步骤。${NC}"
fi
