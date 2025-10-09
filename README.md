本文档是 `flashmvp` 项目的核心说明书，旨在为开发者提供一个全面的指南。它详细介绍了项目的核心理念、技术架构、开发流程以及一套完整的"黄金部署路径"。无论您是初次接触本项目，还是希望进行后续的功能开发，本文档都将是您最重要的参考起点。

# flashmvp - 混合云MVP开发框架

<div align="center">
<h3>🚀 一个基于 Cloudflare 和 Google Cloud Run 的高性能MVP开发框架</h3>
<p>快速构建产品原型 | 边缘计算与中心化计算结合 | 实时成本追踪 | 一键式部署</p>
</div>

## 📋 目录

  - 项目介绍
  - 核心特性
  - 技术架构
  - 框架理念与开发流程
  - 部署黄金路径 (Recommended Setup Flow)
  - 项目结构
  - API端点说明
  - 配置说明
  - 常见问题
  - 许可证

## 🎯 项目介绍

flashmvp 是一个专为快速产品验证设计的混合云框架。它将 `flashmvp` 项目的理念提升到了一个新的高度，通过结合 Cloudflare 的全球边缘网络和 Google Cloud Run 的强大容器化计算能力，提供了一套完整的基础设施，让您能够：

1.  **快速搭建演示平台** - 内置用户认证、功能管理和边缘数据统计。
2.  **灵活集成AI能力** - 支持任何 Python 库，通过 Google Cloud Run 突破了 Serverless 的环境限制。
3.  **成本可控且性能卓越** - 利用边缘函数处理高频、低计算任务，利用中心化服务处理复杂任务，实现了性能与成本的最佳平衡。
4.  **一键式部署** - 通过 CLI 工具链 (`wrangler` 和 `gcloud`) 实现高度自动化的部署流程。

### 框架定位

  - ✅ 适合：产品原型验证、客户演示、内部工具、需要复杂 Python 依赖的 AI 应用 POC。
  - ❌ 不适合：需要极低延迟的复杂计算任务（因存在边缘到中心的网络跃点）。

## 🌟 核心特性

### 1\. 混合云架构

  - **Cloudflare (边缘层)**: 处理用户认证、静态内容分发、API 路由，并利用 D1 数据库实现高性能的使用量追踪。
  - **Google Cloud Run (计算层)**: 运行容器化的 FastAPI 应用，处理计算密集型任务（如 AI 调用），支持任何 Python 依赖。

### 2\. 真实的数据持久化

  - 利用 **Cloudflare D1** 数据库在边缘实时记录和查询 AI 调用数据，解决了原架构中无法持久化的问题。

### 3\. 无限制的 Python 生态

  - 后端迁移到 **Google Cloud Run** 和 **Docker**，可以安装和使用任何复杂的 Python 库（如 `pandas`, `scikit-learn` 等），为功能扩展提供了无限可能。

### 4\. 模块化设计

  - 功能模块（`features/`）保持高度独立，新增功能不影响平台核心，便于团队协作和 LLM 辅助开发。

### 🔄 Firecrawl Markdown 导出器（新增）

  - 后端新增 `firecrawl_exporter` 功能模块，调用开源项目 [Firecrawl](https://github.com/firecrawl/firecrawl) 的爬虫能力，将指定站点的当前页面及子页面转化为 Markdown。
  - 前端提供独立的「🪄 Firecrawl Markdown 导出器」界面，输入网址即可发起任务、追踪进度并下载归档 ZIP 文件。
  - 通过环境变量配置 `FIRECRAWL_API_KEY`（必填）和 `FIRECRAWL_BASE_URL`（选填，默认官方云服务）即可完成接入，不影响现有功能。

## 🏗️ 技术架构

1.  **用户请求** 首先到达 **Cloudflare Pages**。
2.  所有请求被 **Cloudflare Worker (`_worker.js`)** 拦截。
3.  如果是静态资源请求，直接由 Pages 提供。
4.  如果是 `/api/track-usage` 或 `/api/usage-report`，Worker 直接读写 **Cloudflare D1 数据库**。
5.  如果是其他 `/api/*` 请求（如 `/api/ai-proxy`），Worker 会将其代理到 **Google Cloud Run** 上部署的 **FastAPI 后端服务**。
6.  FastAPI 服务执行复杂逻辑（如调用外部 AI API）并将结果返回。

## 💡 框架理念与开发流程

### 1\. 一个可以直接部署的"骨架"应用

这个项目**不是一个半成品**，而是一个功能完备、**可以被立即部署并投入使用的 MVP 框架**。它的核心价值在于，已经为您解决了构建一个现代化 Web 应用中最复杂、最耗时、最容易出错的底层工作，包括：

  - **基础设施即代码 (`init_deploy.sh`)**: 一键创建所有云端资源。
  - **全自动 CI/CD (`deploy.yml`)**: `git push` 即可完成前后端部署。
  - **内置通用模块**: 用户认证、API网关、数据统计等功能开箱即用。

您可以通过运行初始化脚本，在30分钟内拥有一个完全属于您自己的、功能齐全的线上应用。

### 2\. "填空式"的后续功能开发

在完成首次部署后，您将几乎不再需要关心任何与"部署"相关的问题。开发新功能被简化为一套清晰、线性的流程，真正做到**让开发者100%专注于业务逻辑本身**。

以开发一个**"PDF文档摘要生成器"**为例，您的全部工作如下：

#### **第一步：开发前端界面 (UI)**

1.  在 `frontend/features/` 目录下创建一个新文件夹 `pdf-summarizer`。
2.  在其中编写 `index.html` (上传按钮、结果区域) 和 `script.js`。
3.  在 `frontend/config.js` 的 `FEATURES` 数组中，注册您的新功能：
    ```javascript
    {
        path: 'pdf-summarizer/index.html',
        name: 'PDF文档摘要生成器',
        description: '上传PDF，自动为您生成核心内容摘要。',
        isFullPath: true
    },
    ```

#### **第二步：开发后端逻辑**

1.  在 `backend/features/` 目录下创建一个符合 Python 包命名规范的新文件夹，例如 `pdf_summarizer`。
2.  在该文件夹内创建一个 `router.py` 文件，并定义您的 API 接口。此文件必须包含一个名为 `router` 的 `APIRouter` 实例：
    ```python
    # backend/features/pdf_summarizer/router.py
    from fastapi import APIRouter, Request

    # 创建一个专属的路由器实例
    router = APIRouter()

    @router.post("/summarize-pdf")
    async def summarize_pdf(request: Request):
        # ... 您的核心业务逻辑 ...
        summary_text = "这是生成的摘要..."
        return {"success": True, "summary": summary_text}
    ```
3.  在 `backend/main.py` 文件中，导入并注册您的新路由模块。`main.py` 的作用是模块加载器：
    ```python
    # backend/main.py

    # ... (已有代码) ...
    # 导入您的新路由
    from features.pdf_summarizer.router import router as pdf_summarizer_router
    
    # ... (已有代码) ...
    # 注册您的新路由
    app.include_router(pdf_summarizer_router, prefix="/api")
    print("✅ Successfully loaded feature: pdf_summarizer")
    ```
4.  如果您的功能需要新的Python库，请将其添加到项目根目录下的 `backend/requirements.txt` 文件中。

#### **第三步：连接前后端**

1.  在 `frontend/features/pdf-summarizer/script.js` 中，使用 `fetch` 调用后端接口：
    ```javascript
    const response = await fetch('/api/summarize-pdf', {
        method: 'POST',
        body: pdfFileData
    });
    const result = await response.json();
    // 将 result.summary 显示在您的HTML页面上
    ```

#### **第四步：上线！**

1.  将所有代码修改提交到 Git，并推送到 `main` 分支。
    ```bash
    git add .
    git commit -m "feat: Add PDF summarizer feature"
    git push origin main
    ```
2.  **完成！** GitHub Actions 将自动接管后续所有部署工作。几分钟后，您的新功能即可在线访问。

## 🚀 部署黄金路径 (Recommended Setup Flow)

为了获得最流畅的部署体验，请严格遵循以下三步操作。这将引导您完成所有必需的准备工作，以确保核心安装脚本能够一次性成功。

### **第 1 步：环境准备 (安装与登录CLI工具)**

在开始之前，您的电脑需要准备好与 Google Cloud 和 Cloudflare 通信的命令行工具。

*   **目标**: 确保 `gcloud` 和 `wrangler` 两个命令可以正常使用。
*   **操作指南**: 我们已为您准备了一份详细的静态指南。请打开并遵循其中的说明完成操作：
    *   ➡️ **[CLI工具安装与登录指南](deployment/setup/docs/static/0.cli-setup-guide.md)**

完成本步骤后，您应该已经成功登录了您的GCP和Cloudflare账号。

### **第 2 步：项目配置 (填写 `config.sh`)**

这是整个部署流程中最关键的一步。您需要告诉脚本您的项目信息。

*   **目标**: 完整、正确地填写 `deployment/setup/config.sh` 文件。
*   **操作指南**:
    1.  打开 `deployment/setup/config.sh` 文件。
    2.  依次填写 `GITHUB_USERNAME`, `PROJECT_NAME_BASE`, 和 `GITHUB_REPONAME`。
    3.  **重点：填写 `GCP_PROJECT_ID`**
        *   这个ID是脚本将要在哪个GCP项目中创建资源的目标。
        *   **如果您还没有GCP项目**，请遵循以下指引创建一个：
            1.  访问 [Google Cloud项目创建页面](https://console.cloud.google.com/projectcreate)。
            2.  为项目命名 (例如: `flashmvp-prod`)。
            3.  **复制**系统为您生成的、全球唯一的**项目ID** (例如: `flashmvp-prod-123456`)。
            4.  确保新项目已**关联到您的结算账号**。
        *   将您准备好的**项目ID**填入 `config.sh` 的 `GCP_PROJECT_ID` 变量中。

### **第 3 步：执行一站式安装向导**

当您完成以上所有准备工作后，现在就可以运行我们为您准备的安装向导了。

*   **目标**: 运行 `setup-wizard.sh` 来自动化地检查环境并创建所有云端资源。
*   **操作指南**:
    在项目根目录的终端中，运行以下命令：
    ```bash
    # 切换到部署脚本目录
    cd deployment/setup
    
    # 授予向导执行权限并运行它
    chmod +x setup-wizard.sh
    ./setup-wizard.sh
    ```
    向导将会引导您完成所有后续步骤。如果遇到任何问题，它会提供清晰的指引。成功后，它会自动调用核心脚本，并生成一份位于 `deployment/setup/output/manual-setup-guide.md` 的最终指南，请根据该指南完成最后的GitHub Secrets配置。

> 💡 **智能安全网**: 如果您跳过了前面的步骤，不必担心。`init_deploy.sh` 脚本非常智能，它会**自动检测**环境问题（如CLI未登录、GCP项目不存在等），并为您提供**动态生成的、上下文相关的帮助文档**，引导您解决问题。

## 📁 项目结构

```
flashmvp/
├── .github/workflows/       # CI/CD 自动化工作流
│   └── deploy.yml
├── backend/                 # 后端 (FastAPI on Google Cloud Run)
│   ├── features/            # [核心] 后端功能模块
│   ├── main.py              # FastAPI 应用加载器
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                # 前端 (Cloudflare Pages & Workers)
│   ├── features/            # [核心] 前端功能模块
│   ├── _worker.js           # Cloudflare Worker (边缘API网关)
│   ├── schema.sql           # D1 数据库表结构
│   └── ...
├── deployment/              # [核心] 部署与初始化脚本
│   └── setup/
│       ├── init_deploy.sh   # 自动化部署初始化脚本
│       └── config.sh        # [核心] 项目配置文件
└── README.md
```

## 🔌 API端点说明

所有 API 均通过 Cloudflare Worker 进行路由：

  - `/api/track-usage` (POST): 由 Worker 直接处理，将使用数据写入 D1 数据库。
  - `/api/usage-report` (GET): 由 Worker 直接处理，从 D1 查询统计数据并返回。
  - `/api/ai-proxy` (POST): 由 Worker 代理到 Google Cloud Run 后端处理 AI 调用。
  - `/api/health`, `/api/version` (GET): 由 Worker 代理到 Google Cloud Run 后端。

## ⚙️ 配置说明

本项目将所有关键的可配置参数集中在 `deployment/setup/config.sh` 文件中。在进行首次部署前，**这是您唯一需要编辑的文件**。

  - **`GITHUB_USERNAME`**: 您的 GitHub 用户名。
  - **`PROJECT_NAME_BASE`**: 项目的基础名称，将用于命名所有云端资源。
  - **`GITHUB_REPONAME`**: 您的 GitHub 仓库名称。
  - **`GCP_PROJECT_ID`**: 您希望部署后端服务的 Google Cloud 项目的唯一ID。
  - **`GCP_REGION`**: 您希望部署后端服务的 Google Cloud 区域。

正确填写此文件是自动化部署成功的前提。

除了核心的 `config.sh` 文件，项目还有一个应用层配置文件位于 `frontend/config.js`。该文件负责管理前端应用本身的行为，例如：

  - **`USERS`**: 预置的演示用户列表，您可以在此修改默认的用户名和密码。
  - **`FEATURES`**: 功能中心显示的功能卡片列表。

## ❓ 常见问题

### Q1: API 调用返回 404 或 5xx 错误

**A**:

1.  **检查后端URL**: 在首次部署后，GitHub Actions 会自动将后端URL注入到Cloudflare Worker中。如果手动部署或修改，请确保Cloudflare Pages项目的`BACKEND_URL`环境变量设置正确。
2.  **API路径**: 确认您在前端代码中 `fetch` API时，路径**不包含 `.py` 扩展名**（例如，使用 `/api/ai-proxy` 而不是 `/api/ai-proxy.py`），这是新架构的要求。

### Q2: 使用量统计不工作

**A**:

1.  **本地开发**: 确保已成功运行 `deployment/setup/init_deploy.sh`，它会自动为本地开发创建 `frontend/.dev.vars` 文件并填入正确的数据库ID。
2.  **生产环境**: 检查GitHub Actions的部署日志，确认"Apply D1 Schema"步骤是否成功执行。该步骤负责创建数据表。

### Q3: 如何修改登录密码？

**A**: 直接编辑 `frontend/config.js` 中的 `USERS` 数组。

### Q4: GitHub Actions 部署失败，并提示 Wrangler 相关错误？

**A**:
本项目的CI/CD流程依赖于`wrangler` CLI的特定行为，在调试过程中可能遇到复杂问题。如果遇到部署失败，请优先检查`.github/workflows/deploy.yml`文件。该文件经过了多次迭代，包含了**动态生成`wrangler.toml`配置**等关键步骤，是部署逻辑的最终实现。任何关于环境变量或D1数据库的绑定修改，都应在工作流的`Dynamically Configure All Bindings in wrangler.toml`步骤中进行，而不是直接修改仓库中的`wrangler.toml`文件。

## 📄 许可证

MIT License