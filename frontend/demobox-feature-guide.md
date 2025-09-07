
# flashmvp 新功能开发规范与指南

> 🎯 **本文档用途**：作为开发新功能的标准操作手册和规范文档。所有新功能开发必须严格遵循本文档规定。

## 📚 目录

1. [开发前准备](#1-开发前准备)
2. [功能目录结构规范](#2-功能目录结构规范)
3. [开发步骤详解](#3-开发步骤详解)
4. [代码规范](#4-代码规范)
5. [常用功能模式](#5-常用功能模式)
6. [测试要求](#6-测试要求)
7. [上线前检查清单](#7-上线前检查清单)
8. [常见错误与解决](#8-常见错误与解决)

---

## 1. 开发前准备

### 1.1 功能规划
在开始编码前，请明确以下内容：

- [ ] **功能名称**（英文，用于目录名）：_____________________
- [ ] **功能中文名**（用于显示）：_____________________
- [ ] **功能描述**（一句话说明）：_____________________
- [ ] **默认AI模型**：□ Gemini Flash（推荐） □ 其他：_____
- [ ] **预估Token用量**：输入_____ 输出_____
- [ ] **是否需要多页面**：□ 否（仅index.html） □ 是（列出页面：_____）

### 1.2 命名规则

| 项目 | 规则 | 示例 |
|------|------|------|
| 功能目录名 | 小写字母+连字符 | `user-analysis`, `data-report` |
| 功能中文名 | 简洁明了 | "用户分析", "数据报表" |
| 页面文件名 | 描述性英文 | `index.html`, `settings.html` |

---

## 2. 功能目录结构规范

### 2.1 标准结构
```
frontend/features/
└── your-feature/              # 功能目录（必须）
    ├── index.html            # 主页面（必须）
    ├── config.json           # 功能配置（必须）
    ├── style.css             # 功能专属样式（可选）
    ├── script.js             # 功能专属脚本（可选）
    └── assets/               # 资源目录（可选）
        ├── images/           # 图片
        └── data/             # 数据文件
```

### 2.2 文件说明

#### config.json（必须）
```json
{
    "name": "功能中文名",
    "version": "1.0.0",
    "author": "开发者",
    "defaultModel": {
        "provider": "gemini",
        "model": "gemini-2.5-flash"
    },
    "allowModelSelection": true,
    "estimatedUsage": {
        "avgInputTokens": 500,
        "avgOutputTokens": 1000
    },
    "features": {
        "requiresAuth": true,
        "trackUsage": true
    }
}
```

---

## 3. 开发步骤详解

### 3.1 创建功能目录
```bash
# 在项目 frontend/features 目录执行
mkdir your-feature
cd your-feature
```

### 3.2 创建主页面（index.html）

使用以下模板创建 `index.html`：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <title>功能名称 - flashmvp</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <!-- 全局样式 -->
    <link rel="stylesheet" href="../../style.css">
</head>
<body>
    <div class="feature-container">
        <!-- 页面头部 -->
        <header>
            <h1>功能名称</h1>
            <p>功能简要说明</p>
        </header>
        
        <!-- 主要功能区 -->
        <main>
            <textarea id="userInput" placeholder="请输入..." rows="5"></textarea>
            <button id="submitBtn" onclick="handleSubmit()">提交</button>
            <div id="result" class="result-box" style="display: none;"></div>
        </main>
        
        <!-- 页脚 -->
        <footer>
            <a href="../../dashboard.html">← 返回功能中心</a>
        </footer>
    </div>
    
    <!-- 必需的脚本 -->
    <script src="../../config.js"></script>
    <script src="../../auth.js"></script>
    <script src="../../models.js"></script>
    <script src="../../usage.js"></script>
    
    <!-- 功能逻辑 -->
    <script>
        checkAuth(); // 检查认证（必须）
        
        async function handleSubmit() {
            const userInput = document.getElementById('userInput').value.trim();
            if (!userInput) {
                alert('请输入内容');
                return;
            }
            
            const submitBtn = document.getElementById('submitBtn');
            const resultDiv = document.getElementById('result');
            
            submitBtn.disabled = true;
            submitBtn.textContent = '处理中...';
            resultDiv.style.display = 'block';
            resultDiv.innerHTML = 'AI正在思考，请稍候...';
            
            try {
                // ⚠️ API 调用规范已更新！
                // 1. 无需 .py 扩展名
                // 2. 从 localStorage 获取 API Key Tier
                const apiKeyTier = localStorage.getItem('flashmvp_api_key_tier') || 'free';

                const response = await fetch('/api/ai-proxy', { // 关键变更：移除了 .py
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        provider: 'gemini',
                        model: 'gemini-2.5-flash',
                        prompt: userInput,
                        apiKeyTier: apiKeyTier // 传递API版本
                    })
                });
                
                const data = await response.json();
                
                if (!data.success) {
                    throw new Error(data.error || 'AI调用失败');
                }
                
                // 记录使用量（必须）
                await usageTracker.recordUsage(
                    "功能名称",
                    data.provider,
                    data.model,
                    data.inputTokens,
                    data.outputTokens
                );
                
                resultDiv.innerText = data.response;
                
            } catch (error) {
                console.error('处理失败:', error);
                resultDiv.innerHTML = `<strong style="color:red;">处理失败：</strong>${error.message}`;
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = '提交';
            }
        }
    </script>
</body>
</html>
```

### 3.3 注册功能

在项目根目录的 `frontend/config.js` 中添加：

```javascript
const FEATURES = [
    // ... 现有功能 ...
    {
        path: 'your-feature',           // 功能目录名
        name: '您的功能名称',            // 显示名称
        description: '功能的简要描述'    // 描述文字
    }
];
```

---

## 4. 代码规范

### 4.1 必须遵守的规则

#### ⚠️ API调用规范 (重要更新)
```javascript
// ✅ 正确：API端点不带.py扩展名
await fetch('/api/ai-proxy', {...})
await fetch('/api/track-usage', {...})

// ❌ 错误：在Cloudflare + GCR架构下会导致404
// await fetch('/api/ai-proxy.py', {...})
```

#### ✅ 认证检查
```javascript
// 每个页面必须在开始处检查认证
checkAuth();
```

#### ✅ 使用量追踪
```javascript
// 每次AI调用成功后必须记录使用量
await usageTracker.recordUsage(
    '功能名称',
    provider,
    model,
    inputTokens,
    outputTokens
);
```

### 4.2 错误处理规范
```javascript
try {
    const response = await fetch('/api/ai-proxy', {...});
    const data = await response.json();
    
    if (!data.success) {
        throw new Error(data.error || '请求失败');
    }
    
    // 处理成功结果
} catch (error) {
    // 用户友好的错误提示
    showError(`处理失败：${error.message}`);
    // 开发调试信息
    console.error('详细错误:', error);
}
```

---

## 5. 常用功能模式
(此部分无变更，逻辑保持不变)

...

---

## 6. 测试要求
(此部分无变更，逻辑保持不变)

...

---

## 7. 上线前检查清单
(此部分无变更，逻辑保持不变)

...

---

## 8. 常见错误与解决

### 8.1 API调用404错误
**问题**：调用API返回404
**原因**：很可能是在`fetch`调用中错误地保留了`.py`扩展名。
**解决**：
```javascript
// ✅ 正确代码
fetch('/api/ai-proxy')
```

### 8.2 认证失效
**问题**：用户已登录但被重定向到登录页
**解决**：确保每个页面都调用了`checkAuth()`，并检查`auth.js`的路径是否正确。

### 8.3 使用量统计不准
**问题**：AI使用量没有被记录。
**解决**：确保在AI调用`fetch`成功后，并且`data.success`为`true`时，调用了`usageTracker.recordUsage()`。

### 8.4 跨域错误 (CORS)
**问题**：本地开发时出现CORS错误。
**解决**：推荐使用`wrangler dev`命令启动本地开发服务器，它能正确模拟Cloudflare环境。如果单独运行`backend`和`frontend`，请确保FastAPI后端已配置CORS中间件以允许来自前端源的请求。

---
<div align="center">
  <p><strong>遵循本规范，确保功能质量和一致性</strong></p>
</div>
```
