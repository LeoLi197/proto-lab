#!/bin/bash
# ==============================================================================
# flashmvp Project Configuration
# ==============================================================================
#
# !! IMPORTANT !!
# This is the ONLY file you need to edit before deploying your own version.
# Fill in the variables below, then run the ./init_deploy.sh script.
#
# ==============================================================================

# --- [REQUIRED] Core Settings ---

# 1. Your GitHub Username
# This is crucial for configuring GCP's trust policy for GitHub Actions.
# Example: "my-github-user"
export GITHUB_USERNAME="LeoLi197"

# 2. Your Project's Base Name
# A short, unique, lowercase name. This will be used for the GCP service,
# Cloudflare Pages project, and D1 Database name.
# WARNING: Changing this after the first deployment requires manual resource cleanup.
# Example: "my-cool-app"
export PROJECT_NAME_BASE="proto-lab"

# 3. Your GitHub Repository Name
# This usually matches PROJECT_NAME_BASE, but can be different if you forked it.
# Example: "MyCoolApp"
export GITHUB_REPONAME="ProtoLab"

# 4. [新增] Your Google Cloud Project ID
# ==============================================================================
# 这是您希望将后端服务部署到的 GCP 项目的唯一ID。
#
# 操作指引:
#   1. 访问 Google Cloud 控制台创建一个全新的、空的项目：
#      https://console.cloud.google.com/projectcreate
#
#   2. 为项目命名 (例如: flashmvp-production)，然后记下系统为您生成的、
#      全球唯一的【项目ID】(例如: flashmvp-production-123456)。
#
#   3. 确保这个新项目已经关联到您的结算账号 (Billing Account)。
#
#   4. 将复制好的【项目ID】填写在下面。
#
# 重要提示：部署脚本不会自动为您创建GCP项目。它只会验证您在此处填写的项目ID
# 是否真实存在且您有权访问。
# ==============================================================================
export GCP_PROJECT_ID="proto-lab-470603"


# --- [OPTIONAL] Advanced Settings ---

# 5. Google Cloud Region
# The region where your backend service will be deployed.
# Find available regions here: https://cloud.google.com/run/docs/locations
# Example: "us-east1"
export GCP_REGION="us-central1"

# 6. GCP Service Account Name (Base)
# The name for the service account used by GitHub Actions.
# The final email will be <name>@<your-gcp-project-id>.iam.gserviceaccount.com
export GCP_SERVICE_ACCOUNT_NAME_BASE="github-deployer"