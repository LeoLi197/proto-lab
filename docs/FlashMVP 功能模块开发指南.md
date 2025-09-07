
---
title: flashmvp 功能模块开发指南
**filename:** `flashmvp-Feature-Development-Guide.md`
---

> **文档概要说明**
>
> *   **文档定位**: 本文档是 `flashmvp` 框架的**核心开发人员指南**，定义了向平台添加新功能的标准作业流程。
> *   **核心内容**: 详细阐述了 "填空式" 的模块化开发模式。内容涵盖后端API模块的创建 (`backend/features`)、前端UI页面的开发 (`frontend/features`)、新功能的注册 (`frontend/config.js`)，以及最终通过 `git push` 实现的自动化部署。
> *   **适用场景**: 当您需要在 `flashmvp` 平台上开发并集成一个全新的、独立的功能模块时，必须严格遵循本指南进行操作。

---

# flashmvp 功能模块开发指南

**版本:** 1.2 (已修正)
**状态:** 正式
**编写日期:** 2025-08-21

## 1. 核心理念与设计哲学

本指南旨在为 flashmvp 框架提供一套标准化的新功能开发工作流程。flashmvp 的核心设计哲学是将基础设施的复杂性（如部署、路由、认证、计费）完全自动化并平台化，从而使开发者能够 **100% 专注于业务逻辑的实现**。

后续开发遵循“**填空式**”模式：您只需在预设的目录结构和代码规范内，编写您的前端交互与后端逻辑。其余的构建、部署、API路由和数据统计工作均由框架自动处理。

**核心设计原则:**

*   **高度解耦 (High Decoupling):** 每个新功能都是一个独立的“垂直切片”(Vertical Slice)，包含其专属的前端和后端代码，物理上存在于自己的目录中，不与其他功能模块产生直接代码依赖。
*   **约定优于配置 (Convention over Configuration):** 严格遵循框架的目录结构和命名约定，可以最大限度地利用自动化流程，实现零配置的功能集成。
*   **平台能力复用 (Platform Service Reuse):** 新功能应主动集成并复用平台提供的核心能力（如认证检查、用量统计），以减少重复开发工作并确保体验一致性。

为具象化整个流程，我们将以开发一个名为“**PDF 文档摘要生成器 (PDF Summarizer)**”的新功能为例，贯穿本指南的始末。

## 2. 准备工作

在开始开发前，请确保您的本地环境已安装并配置好以下工具：

*   Git
*   Google Cloud SDK (`gcloud`)
*   Cloudflare Wrangler CLI (`wrangler`)
*   Node.js and npm

## 3. 标准开发流程

### 第 1 步：后端模块开发 (Backend)

我们从后端逻辑开始，定义功能的计算核心。

1.  **创建功能目录:**
    *   导航至 `backend/features/` 目录。
    *   创建一个新目录，命名必须遵循 **Python 包命名规范** (小写字母和下划线)。
    *   示例: `backend/features/pdf_summarizer/`

2.  **管理依赖 (重要流程变更):**
    *   项目采用**集中式依赖管理**，以确保构建的稳定性和一致性。
    *   所有新的Python依赖库，无论用于哪个功能，都**必须**被添加到项目根目录的 `backend/requirements.txt` 文件中。
    *   **严禁**在各功能模块的子目录中创建单独的 `requirements.txt` 文件，否则依赖将不会被安装。
    *   示例：如果您的新功能需要 `pypdf` 库，请打开 `backend/requirements.txt` 文件并添加新的一行 `pypdf` (为保证部署稳定，建议固定版本号，如 `pypdf==4.2.0`)。

3.  **创建 API 端点 (Router):**
    *   在模块目录中创建 `router.py` 文件。所有该功能的 API 逻辑都将在此文件中定义。
    *   文件内必须定义一个名为 `router` 的 `APIRouter` 实例。
    *   **[修正]** 示例 `backend/features/pdf_summarizer/router.py` (已更新为最佳实践):
        ```python
        import io
        from pydantic import BaseModel
        from fastapi import APIRouter, UploadFile, File, HTTPException
        # from pypdf import PdfReader # 假设您已在 requirements.txt 中添加了 pypdf

        # 1. 创建一个专属的路由器实例
        # 注意：prefix="/api" 由 main.py 统一管理，此处无需添加
        router = APIRouter(
            tags=["PDF Summarizer"]  # 在API文档中为此功能创建一个分组
        )

        # 2. 定义清晰的请求/响应数据模型 (符合规范)
        class PdfSummaryResponse(BaseModel):
            success: bool
            summary: str
            filename: str
            # 如果需要，可以添加 token 计费信息
            # inputTokens: int
            # outputTokens: int

        # 3. 定义API端点 (使用 FastAPI 的依赖注入处理文件上传)
        @router.post("/summarize-pdf", response_model=PdfSummaryResponse)
        async def summarize_pdf(file: UploadFile = File(...)):
            if file.content_type != "application/pdf":
                raise HTTPException(status_code=400, detail="文件类型错误，请上传PDF文件。")
            
            try:
                # ... 此处是您的核心业务逻辑 ...
                # 例如：读取PDF内容
                # pdf_content = await file.read()
                # reader = PdfReader(io.BytesIO(pdf_content))
                # text = "".join(page.extract_text() for page in reader.pages)
                
                # 调用 AI 服务进行摘要 (此处为模拟)
                # ai_summary = call_ai_service(text) 
                ai_summary = "这是对PDF内容的模拟摘要..."

                return PdfSummaryResponse(
                    success=True,
                    summary=ai_summary,
                    filename=file.filename
                )
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"处理PDF时发生错误: {e}")
        ```

4.  **注册模块 (关键步骤):**
    *   **[新增]** 您必须在主应用中手动加载并注册您的新模块。
    *   打开 `backend/main.py` 文件，并完成以下两处修改：
        1.  **导入您的新路由**：在文件顶部，与其他路由一起导入。
            ```python
            # backend/main.py

            # --- 静态导入所有功能模块的路由 ---
            from features.core_api.router import router as core_api_router
            from features.pdf_summarizer.router import router as pdf_summarizer_router # <-- 添加此行
            ```
        2.  **注册您的新路由**：在文件下方，使用 `app.include_router()` 进行注册。
            ```python
            # backend/main.py
            
            # --- 注册所有已导入的路由 ---
            app.include_router(core_api_router, prefix="/api")
            print("✅ Successfully loaded feature: core_api")

            app.include_router(pdf_summarizer_router, prefix="/api") # <-- 添加此行
            print("✅ Successfully loaded feature: pdf_summarizer")
            ```
    *   **警告**: 忽略此步骤将导致您新建的API端点无法被发现，并返回404错误。

### 第 2 步：前端模块开发 (Frontend)

1.  **创建功能目录:**
    *   导航至 `frontend/features/` 目录。
    *   创建一个新目录，命名建议遵循 **kebab-case 规范** (小写字母和连字符)。
    *   示例: `frontend/features/pdf-summarizer/`

2.  **编写功能页面:**
    *   在功能目录中创建 `index.html`。这是您功能的入口。
    *   页面中必须引入平台的核心脚本，以复用平台能力。
        ```html
        <!-- ... head and body structure ... -->

        <!-- 引入框架提供的核心JS库 -->
        <script src="../../auth.js"></script>
        <script src="../../models.js"></script>
        <script src="../../usage.js"></script>
        <script src="script.js"></script> <!-- 功能专属逻辑 -->
        ```

3.  **编写交互逻辑:**
    *   在功能目录中创建 `script.js` 文件。
    *   在此文件中，您需要调用平台服务并与后端API交互。
        ```javascript
        // 1. 【必需】在脚本开始时进行认证检查
        checkAuth();

        // ... 获取DOM元素和绑定事件 ...

        async function callApi() {
            // ... UI加载状态处理 ...

            try {
                // 2. 【必需】调用后端API，使用/api/前缀的相对路径
                const response = await fetch('/api/summarize-pdf', { /* ... */ });
                const data = await response.json();
                
                // ... 检查响应是否成功 ...

                // 3. 【必需】调用全局usageTracker记录本次操作的成本
                // 注意：如果您的后端不返回token信息，您可能需要估算或硬编码
                const usage = await usageTracker.recordUsage(
                    'PDF文档摘要生成器', // 功能名称，与后续注册时保持一致
                    'gemini', // 示例 provider
                    'gemini-2.5-flash', // 示例 model
                    500,  // 示例 inputTokens
                    150   // 示例 outputTokens
                );
                
                // ... 在UI上显示结果和费用 ...

            } catch (error) {
                // ... 错误处理 ...
            }
        }
        ```

### 第 3 步：功能注册

为了让用户能在功能中心看到并访问您的新功能，必须在前端配置文件中进行注册。

*   **文件:** `frontend/config.js`
*   **操作:** 在 `FEATURES` 数组中添加一个新的对象。
    ```javascript
    const FEATURES = [
        // ... (保留已有的功能)

        // --- 新增的功能 ---
        {
            path: 'pdf-summarizer/index.html', // 路径相对于 frontend/features/
            name: 'PDF文档摘要生成器',
            description: '上传PDF，自动为您生成核心内容摘要。',
            isFullPath: true // 固定为 true
        },
    ];
    ```

### 第 4 步：部署

至此，所有开发工作已完成。CI/CD 流程是全自动的。

1.  **提交代码:**
    ```bash
    git add .
    git commit -m "feat: Add PDF summarizer feature"
    git push origin main
    ```
2.  **等待自动化部署:**
    `git push` 命令将触发 `.github/workflows/deploy.yml` 中定义的 GitHub Actions。它将自动完成所有构建和部署工作。几分钟后，您的新功能即可在线访问。

## 4. 技术规范细则

### 4.1. 目录与命名约定

| 模块  | 路径                        | 命名规范              | 必须文件                |
| :---- | :-------------------------- | :-------------------- | :---------------------- |
| 前端  | `frontend/features/`        | `kebab-case`          | `index.html`            |
| 后端  | `backend/features/`         | `snake_case`          | `router.py`             |

### 4.2. 后端规范

*   **Router:** 每个后端模块的 `router.py` **必须**导出一个名为 `router` 的 `APIRouter` 实例。
*   **注册:** 每个新的后端模块**必须**在 `backend/main.py` 中被手动导入和注册。
*   **依赖:** 所有Python依赖**必须**统一添加到根目录的 `backend/requirements.txt` 文件中。**严禁**在功能子目录中创建 `requirements.txt`。
*   **API设计:**
    *   API路径**不应**包含 `/api/` 前缀，该前缀由 `main.py` 统一应用。
    *   返回的数据**必须**是JSON格式，并包含一个 `success: true/false` 字段，便于前端统一处理。
    *   **必须**为请求和响应体定义Pydantic模型以确保数据校验和API文档的清晰性。

### 4.3. 前端规范

*   **认证:** 每个功能页面的主JS脚本**必须**在执行任何逻辑前调用 `checkAuth()`。
*   **API消费:** 对后端的 `fetch` 请求**必须**使用以 `/api/` 开头的相对路径。
*   **用量统计:** 每次成功的AI调用后，**必须**调用 `usageTracker.recordUsage()` 方法。
*   **资源引用:** 页面内对平台级资源的引用（如 `style.css`）**必须**使用相对路径 (`../../style.css`)。

## 5. 最佳实践

*   **保持模块独立:** 一个功能的所有特定资源都应包含在 `frontend/features/my-feature` 和 `backend/features/my_feature` 这两个目录中。**绝对不要**跨功能目录引用文件。
*   **保持核心纯净:** **不要**向 `backend/main.py` 添加任何业务逻辑。`main.py` 的唯一作用是作为模块加载器。
*   **配置分离:**
    *   **基础设施级配置** (如项目名、区域) 在 `config.sh` 中管理。
    *   **应用级配置** (如功能列表、用户) 在 `frontend/config.js` 中管理。

## 6. 开发者自查清单

在提交新功能代码前，请根据以下清单进行自查：

- [ ] 是否已创建 `frontend/features/[feature-name]` 和 `backend/features/[feature_name]` 两个目录？
- [ ] 目录命名是否符合规范 (kebab-case / snake_case)？
- [ ] 后端模块的 `router.py` 中是否定义了名为 `router` 的实例？
- [ ] **[关键]** 新的后端路由是否已在 `backend/main.py` 中导入并注册？
- [ ] 新的Python依赖是否已添加到**根目录的 `backend/requirements.txt`** 中？
- [ ] 前端页面是否已在 `frontend/config.js` 中注册？
- [ ] 前端JS脚本是否在开头调用了 `checkAuth()`？
- [ ] AI调用成功后，是否调用了 `usageTracker.recordUsage()`？
- [ ] 所有对后端API的 `fetch` 调用是否都使用了 `/api/` 前缀？