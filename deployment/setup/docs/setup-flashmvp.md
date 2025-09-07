# flashmvp 首次部署完整指南

## 文档说明

**适用场景**：您是第一次使用 flashmvp 框架，需要将其部署到自己的 Google Cloud 和 Cloudflare 账号上。  
**预计时间**：20-30分钟  
**前置条件**：
- Google Cloud 账号（已设置结算）
- GitHub 账号  
- Cloudflare 账号

## v6.0 版本特性

本版本采用**配置驱动的混合模式**，带来以下改进：

- 📝 **配置驱动**：所有个性化设置集中于 `config.sh`，一处修改，全局生效
- 🤖 **智能分工**：自动化处理包括身份联合在内的所有复杂资源创建
- 📋 **清晰指引**：为必需的手动授权步骤提供精准、自动生成的指南
- 🛡️ **更高成功率**：全自动配置 Workload Identity，彻底避免复杂的手动操作失误
- 💾 **配置备份**：自动保存所有关键配置信息到 `deployment-config.txt`
- 🔄 **自动重命名**：自动将模板中的 `flashmvp` 替换为您的项目名称

---

## 第一部分：核心配置与环境准备

### 步骤 1.1：编辑项目配置文件（3分钟）

flashmvp 采用配置驱动的部署模式。您需要编辑配置文件：

打开 `deployment/setup/config.sh` 文件，填写以下必需项：

```bash
# 1. 您的 GitHub 用户名
export GITHUB_USERNAME="your-github-username"

# 2. 项目基础名称（小写字母和连字符）
export PROJECT_NAME_BASE="your-project-name"

# 3. GitHub 仓库名称
export GITHUB_REPONAME="your-repo-name"

# 4. Google Cloud 项目 ID
# 如果还没有，请先访问 https://console.cloud.google.com/projectcreate 创建
export GCP_PROJECT_ID="your-gcp-project-id"

# 5. （可选）调整部署区域
export GCP_REGION="us-central1"  # 默认值通常即可
```

**注意**：`frontend/config.js` 包含演示用户等应用级配置。首次部署可保持默认，部署成功后再根据需要修改。

### 步骤 1.2：安装并配置 CLI 工具（5分钟）

#### A. 安装工具

1. **Google Cloud CLI**
   - 访问 [Google Cloud SDK 安装指南](https://cloud.google.com/sdk/docs/install)
   - 根据您的操作系统完成安装

2. **Cloudflare Wrangler**
   ```bash
   npm install -g wrangler
   ```

#### B. 登录并配置

```bash
# 登录 Google Cloud
gcloud auth login
gcloud config set project YOUR_PROJECT_ID  # 替换为您的实际项目ID

# 登录 Cloudflare
wrangler login
```

如需详细的 CLI 安装指导，请参考 [CLI 工具安装指南](cli-setup-guide.md)。

---

## 第二部分：运行自动化部署脚本

### 步骤 2.1：执行安装向导（5-10分钟）

```bash
# 进入部署脚本目录
cd deployment/setup

# 授予执行权限
chmod +x setup-wizard.sh

# 运行向导
./setup-wizard.sh
```

**向导会自动完成以下任务**：

1. ✅ 验证您的配置文件
2. ✅ 检查 CLI 工具登录状态
3. ✅ 验证 GCP 项目是否存在
4. ✅ 检测并清理旧的 Git 历史（如果是从模板复制）
5. ✅ 创建所有云端资源：
   - Cloud Run 服务（`${PROJECT_NAME_BASE}-backend`）
   - 服务账号和 IAM 权限
   - Cloudflare D1 数据库（`${PROJECT_NAME_BASE}-usage`）
   - Cloudflare Pages 项目
6. ✅ **自动替换项目名称**（将 `flashmvp` 替换为您的项目名）
7. ✅ 生成后续所需文件：
   - `output/manual-setup-guide.md` - 手动操作指南
   - `output/setup_gcp_identity.sh` - 身份配置脚本
   - `output/deployment-config.txt` - 配置信息备份
   - `output/github-secrets-values.txt` - GitHub Secrets 值

### 步骤 2.2：处理可能的错误

如果向导在某个步骤失败：

| 错误类型 | 解决方案 |
|---------|---------|
| 配置文件未填写 | 编辑 `config.sh`，确保所有必填项已填写 |
| CLI 未登录 | 执行相应的登录命令，然后重新运行向导 |
| GCP 项目不存在 | 向导会生成创建指南 `output/create-gcp-project-guide.md`，按指南操作后重试 |
| 网络或权限问题 | 检查网络连接和账号权限，确保有创建资源的权限 |

---

## 第三部分：配置身份联合与 GitHub Secrets

### 步骤 3.1：手动授权 GCP 账号（2分钟）

第一阶段脚本完成后，会生成 `output/manual-setup-guide.md`。您需要：

1. **打开 GCP IAM 页面**：
   ```
   https://console.cloud.google.com/iam-admin/iam?project=YOUR_PROJECT_ID
   ```

2. **为您的账号授权**：
   - 点击页面上方的 "GRANT ACCESS"（授予访问权限）
   - 在 "New principals" 字段输入您的邮箱
   - 添加角色：`IAM Workload Identity Pool Admin`
   - （可选但推荐）再添加：`Service Account Admin`
   - 点击 "Save" 保存

3. **等待 1-2 分钟让权限生效**

### 步骤 3.2：运行身份配置脚本（3分钟）

当向导询问您是否已完成授权时，输入 `y` 确认，或手动运行：

```bash
# 进入输出目录
cd output

# 授予执行权限并运行
chmod +x setup_gcp_identity.sh
./setup_gcp_identity.sh
```

**脚本会自动完成**：
- 创建 Workload Identity Pool
- 配置 OIDC 提供商
- 建立与服务账号的信任关系
- 自动更新 `manual-setup-guide.md` 中的配置值
- 生成 `github-secrets-values.txt` 文件，包含所有需要的值

### 步骤 3.3：配置 GitHub Secrets（5分钟）

#### A. 打开 GitHub Secrets 页面

在您的 GitHub 仓库中：
```
Settings → Secrets and variables → Actions → New repository secret
```

#### B. 添加必需的 Secrets

打开 `output/github-secrets-values.txt` 文件，您会看到所有需要的值。逐个添加：

| Secret 名称 | 值的来源 |
|------------|---------|
| `GCP_PROJECT_ID` | 从 github-secrets-values.txt 复制 |
| `GCP_SERVICE_ACCOUNT` | 从 github-secrets-values.txt 复制 |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | 从 github-secrets-values.txt 复制 |
| `CLOUDFLARE_ACCOUNT_ID` | 从 github-secrets-values.txt 复制 |
| `CF_PAGES_PROJECT_NAME` | 从 github-secrets-values.txt 复制 |
| `CF_D1_DATABASE_NAME` | 从 github-secrets-values.txt 复制 |
| `CLOUDFLARE_API_TOKEN` | 需要手动创建（见下方） |
| `GEMINI_API_KEY` | 您的 Gemini API 密钥（必需） |

#### C. 创建 Cloudflare API Token

1. 访问 [Cloudflare API Tokens](https://dash.cloudflare.com/profile/api-tokens)
2. 点击 "Create Token" → "Custom token"
3. 配置权限：
   - Account → D1 → Write
   - Account → Cloudflare Pages → Write
4. 点击 "Continue to summary" → "Create Token"
5. **立即复制 Token**（只显示一次！）
6. 将其添加为 `CLOUDFLARE_API_TOKEN` Secret

#### D. 获取 AI API 密钥

- **Gemini API**：访问 [Google AI Studio](https://makersuite.google.com/app/apikey)
- **OpenAI API**（可选）：访问 [OpenAI API Keys](https://platform.openai.com/api-keys)

---

## 第四部分：推送代码并验证部署

### 步骤 4.1：配置本地开发环境（可选）

如果您想在本地测试：

```bash
# 复制环境变量模板
cp .env.example .env.local

# 编辑 .env.local，添加您的 API 密钥
```

### 步骤 4.2：推送到 GitHub（2分钟）

```bash
# 返回项目根目录
cd ../../

# 初始化 Git（如果向导已处理则跳过）
git init

# 关联远程仓库
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git

# 添加所有文件
git add .

# 创建初始提交
git commit -m "chore: Initial deployment of PROJECT_NAME"

# 推送到 GitHub
git push -u origin main
```

### 步骤 4.3：监控部署进度（5-10分钟）

1. **查看 GitHub Actions**：
   - 访问您的仓库 → Actions 标签
   - 您应该看到一个正在运行的工作流
   - 绿色勾表示成功，红色叉表示失败

2. **如果部署失败**：
   - 点击失败的工作流查看详细日志
   - 常见问题：Secrets 配置错误、权限不足、API 未启用
   - 修复问题后，重新推送代码触发部署

### 步骤 4.4：访问您的应用

部署成功后，您的应用将在以下地址可用：

- **前端**：`https://YOUR_PROJECT_NAME.pages.dev`
- **后端 API**：查看 Cloud Run 服务获取 URL

默认登录凭据（在 `frontend/config.js` 中配置）：
- 用户名：`demo`
- 密码：`demo123`

---

## 第五部分：故障排除

### 常见问题解决

#### 1. 向导执行失败

**问题**：`setup-wizard.sh` 中途退出  
**解决**：
- 检查 `config.sh` 所有必填项
- 确认已登录 `gcloud` 和 `wrangler`
- 运行 `gcloud config get-value project` 确认项目 ID 设置正确
- 查看错误信息，按提示操作

#### 2. Workload Identity 配置失败

**问题**：`setup_gcp_identity.sh` 报错  
**最常见原因**：
- 未按照 `manual-setup-guide.md` 授予账号 `IAM Workload Identity Pool Admin` 权限
- 权限未生效（等待 2-3 分钟后重试）
- 选择了错误的 GCP 项目

**解决**：
- 确认已正确授权
- 检查当前项目：`gcloud config get-value project`
- 查看详细错误信息

#### 3. GitHub Actions 部署失败

**问题**：工作流显示红色失败  
**解决**：
- 检查所有 GitHub Secrets 是否正确配置
- 特别注意 `GCP_WORKLOAD_IDENTITY_PROVIDER` 值是否完整
- 确认 Cloudflare API Token 有正确权限
- 查看 Actions 日志中的具体错误信息

#### 4. 应用无法访问

**问题**：部署成功但网站打不开  
**解决**：
- 等待 2-3 分钟让 DNS 和 CDN 生效
- 检查 Cloudflare Pages 部署状态
- 验证 Cloud Run 服务是否正常运行：
  ```bash
  gcloud run services describe YOUR_PROJECT_NAME-backend --region=YOUR_REGION
  ```
- 检查浏览器控制台是否有错误信息

#### 5. API 调用失败

**问题**：前端能访问但 API 调用失败  
**解决**：
- 确认 AI API 密钥已正确配置在 GitHub Secrets
- 检查 Cloud Run 日志：
  ```bash
  gcloud run logs read --service=YOUR_PROJECT_NAME-backend
  ```
- 验证后端服务 URL 是否正确

### 获取帮助

如果遇到本指南未涵盖的问题：

1. 查看生成的配置文件：
   - `output/deployment-config.txt` - 包含所有配置信息
   - `output/github-secrets-values.txt` - 包含所有 Secret 值

2. 检查日志：
   - GitHub Actions 日志（部署过程）
   - Cloud Run 日志（后端运行时）
   - Cloudflare Pages 日志（前端部署）

3. 重新运行向导：
   - 如果需要重试，`setup-wizard.sh` 会智能跳过已完成的步骤

---

## 第六部分：下一步

### 部署成功后的建议操作

1. **修改默认用户**：
   - 编辑 `frontend/config.js`
   - 更改默认的 demo 用户凭据
   - 重新部署：`git add . && git commit -m "chore: Update credentials" && git push`

2. **配置自定义域名**（可选）：
   - 在 Cloudflare Pages 设置中添加自定义域
   - 配置 DNS 记录指向 Pages 项目

3. **调整资源配额**：
   - Cloud Run 默认配置为最小实例 0（自动缩放到 0）
   - 可根据需要调整内存（默认 256Mi）和 CPU（默认 1）限制

4. **开始开发**：
   ```bash
   # 本地开发
   cd backend && uvicorn main:app --reload --port 8080  # 后端
   cd frontend && wrangler dev --port 8787             # 前端
   
   # 创建功能分支
   git checkout -b feature/new-feature
   
   # 开发完成后推送
   git push origin feature/new-feature
   ```

---

## 相关文档

- [基于模板创建新项目](create-new-project.md) - 使用 flashmvp 作为模板启动新项目
- [快速参考卡](cheatsheet.md) - 命令和配置速查
- [CLI 安装指南](cli-setup-guide.md) - 详细的工具安装说明

---

**恭喜！您已成功部署 flashmvp 框架。** 🎉