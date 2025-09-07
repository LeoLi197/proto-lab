# 基于 flashmvp 框架创建新项目指南

## 文档说明

**适用场景**：您已经了解 flashmvp 框架，想要将它作为模板，创建一个全新的、独立的项目。  
**预计时间**：15-20分钟  
**前置条件**：
- 已获得完整的 flashmvp 源代码
- 已安装并登录 gcloud 和 wrangler CLI 工具
- 拥有 Google Cloud 和 GitHub 账号

## 核心理念

本流程利用 flashmvp 框架的两大设计优势：

1. **配置驱动**：所有环境相关的变量都集中在 `deployment/setup/config.sh`
2. **高度自动化**：安装向导会自动处理项目重命名、Git 历史清理等繁琐工作

---

## 阶段一：项目复制与配置

### 步骤 1.1：复制项目文件夹

```bash
# 复制整个 flashmvp 文件夹
cp -r flashmvp/ my-new-app/

# 进入新项目目录
cd my-new-app/
```

**重要**：后续所有操作都在新创建的 `my-new-app` 文件夹内进行。

### 步骤 1.2：修改核心配置文件

打开 `deployment/setup/config.sh` 文件，这是整个流程中最关键的一步：

```bash
# deployment/setup/config.sh

# 1. 您的 GitHub 用户名
export GITHUB_USERNAME="your-github-username"

# 2. 项目的基础名称 (小写字母和连字符)
export PROJECT_NAME_BASE="my-new-app"

# 3. 您的新 GitHub 仓库名称
export GITHUB_REPONAME="my-new-app"

# 4. 您的 Google Cloud 项目 ID
# 访问 https://console.cloud.google.com/projectcreate 创建新项目
export GCP_PROJECT_ID="my-new-app-prod-123456"

# 5. (可选) 部署区域
export GCP_REGION="us-central1"
```

### 步骤 1.3：准备 CLI 环境

如果您还未安装或登录 CLI 工具：

```bash
# 登录 Google Cloud
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# 登录 Cloudflare
wrangler login
```

详细安装说明请参考 [CLI 工具安装指南](cli-setup-guide.md)。

---

## 阶段二：自动化初始化

### 步骤 2.1：创建 GitHub 仓库

在 GitHub 上创建一个新的空仓库，名称必须与 `config.sh` 中的 `GITHUB_REPONAME` 一致。

### 步骤 2.2：运行安装向导

```bash
# 进入部署脚本目录
cd deployment/setup

# 授予执行权限
chmod +x setup-wizard.sh

# 运行向导
./setup-wizard.sh
```

**向导会自动完成**：

1. ✅ 验证配置文件
2. ✅ 检查 CLI 登录状态
3. ✅ **自动检测并清理旧的 Git 历史**（会提示确认）
4. ✅ 创建所有云资源（Cloud Run、D1 数据库等）
5. ✅ **自动将代码中的 `flashmvp` 替换为您的项目名**
6. ✅ 生成个性化的部署指南

### 步骤 2.3：处理 Git 历史

当向导检测到 `.git` 文件夹时，会询问是否清理：

```
🔎 检测到 .git 文件夹，这可能包含了模板项目的旧历史记录。
是否要自动清理旧的 Git 历史并为 'my-new-app' 项目创建新的历史记录？ (y/n): y
```

选择 `y` 将：
- 删除旧的 `.git` 文件夹
- 为新项目初始化全新的 Git 仓库
- 确保您的项目拥有独立的版本历史

---

## 阶段三：完成部署配置

### 步骤 3.1：配置身份联合

向导完成后，按照生成的 `output/manual-setup-guide.md` 文件指引：

1. **授权 GCP 账号**（步骤 A）
   - 访问 IAM 页面
   - 为您的账号授予 `IAM Workload Identity Pool Admin` 权限

2. **运行身份配置脚本**（步骤 B）
   ```bash
   cd output
   ./setup_gcp_identity.sh
   ```

### 步骤 3.2：配置 GitHub Secrets

打开 `output/github-secrets-values.txt`，文件中包含所有需要的值。

在 GitHub 仓库的 Settings > Secrets and variables > Actions 中添加：

- 基础设施 Secrets（从文件复制）
- `CLOUDFLARE_API_TOKEN`（需要手动创建）
- `GEMINI_API_KEY`（您的 AI API 密钥）

### 步骤 3.3：推送代码

```bash
# 返回项目根目录
cd ../../

# 关联远程仓库
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git

# 添加所有文件
git add .

# 创建初始提交
git commit -m "chore: Initial setup for my-new-app"

# 推送到 GitHub
git push -u origin main
```

---

## 最终成果

完成流程后，您的新项目将拥有：

✅ **独立的本地项目文件夹**  
✅ **全新的 GitHub 仓库**（独立的版本历史）  
✅ **专属的云资源**（Cloud Run 服务、D1 数据库等）  
✅ **可访问的线上应用**（`https://my-new-app.pages.dev`）

---

## 创建多个项目

如果需要基于 flashmvp 创建多个项目：

1. 为每个项目重复上述流程
2. 确保每个项目使用不同的：
   - `PROJECT_NAME_BASE`
   - `GITHUB_REPONAME`
   - `GCP_PROJECT_ID`
3. 每个项目都会拥有完全独立的资源和代码库

---

## 故障排除

### 向导执行失败

- 检查 `config.sh` 是否正确填写
- 确认 CLI 工具已登录
- 查看错误信息并按提示操作

### Git 历史未清理

如果选择不清理 Git 历史，您的新项目将保留模板的提交记录。建议手动清理：

```bash
rm -rf .git
git init
```

### 资源名称冲突

如果云资源已存在，向导会提示。您可以：
- 修改 `PROJECT_NAME_BASE` 使用不同名称
- 或手动删除旧资源后重试

---

## 下一步

项目创建成功后，您可以：

1. **修改应用配置**：编辑 `frontend/config.js` 更改默认用户等设置
2. **开始开发**：查看项目根目录的 README.md 了解开发流程
3. **添加功能**：在 `frontend/features/` 和 `backend/features/` 添加新功能模块

---

## 相关文档

- [首次部署 flashmvp](setup-flashmvp.md) - 如果您还未部署过 flashmvp 本身
- [快速参考卡](cheatsheet.md) - 命令和配置速查
- [CLI 安装指南](cli-setup-guide.md) - 详细的工具安装说明