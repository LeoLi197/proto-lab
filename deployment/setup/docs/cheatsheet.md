# 🚀 flashmvp 部署快速参考卡

## 一、准备工作清单 ✅

- [ ] **编辑 `deployment/setup/config.sh`，填入你的项目信息**
  - `GITHUB_USERNAME` - 你的 GitHub 用户名
  - `PROJECT_NAME_BASE` - 项目基础名称（小写字母和连字符）
  - `GITHUB_REPONAME` - GitHub 仓库名称
  - `GCP_PROJECT_ID` - Google Cloud 项目 ID
- [ ] **(可选) 编辑 `frontend/config.js`，修改默认演示用户**
- [ ] 安装 gcloud CLI
- [ ] 安装 wrangler (`npm install -g wrangler`)
- [ ] 登录 gcloud (`gcloud auth login`)
- [ ] 设置项目 (`gcloud config set project YOUR_PROJECT_ID`)
- [ ] 登录 wrangler (`wrangler login`)

## 二、执行脚本 🤖

```bash
# 从项目根目录执行
cd deployment/setup
chmod +x setup-wizard.sh
./setup-wizard.sh
```

**脚本会读取 `config.sh` 的配置，并自动完成：**
- ✅ Cloud Run 服务
- ✅ D1 数据库
- ✅ Pages 项目
- ✅ 服务账号和权限
- ✅ **生成后续操作指南 (`output/manual-setup-guide.md`)**

## 三、配置 Workload Identity 🔧

1. **打开生成的 `output/manual-setup-guide.md` 文件**
2. 严格遵照指南中的 **"步骤 A"**，为你的 GCP 账号授予必要权限
3. 运行生成的身份配置脚本：
   ```bash
   cd output
   chmod +x setup_gcp_identity.sh
   ./setup_gcp_identity.sh
   ```

## 四、配置 GitHub Secrets 🔐

在 GitHub 仓库 Settings > Secrets and variables > Actions 添加：

| Secret | 值的来源 |
|--------|---------|
| `GCP_PROJECT_ID` | 从 `output/github-secrets-values.txt` 复制 |
| `GCP_SERVICE_ACCOUNT` | 从 `output/github-secrets-values.txt` 复制 |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | 从 `output/github-secrets-values.txt` 复制 |
| `CLOUDFLARE_ACCOUNT_ID` | 从 `output/github-secrets-values.txt` 复制 |
| `CF_PAGES_PROJECT_NAME` | 从 `output/github-secrets-values.txt` 复制 |
| `CF_D1_DATABASE_NAME` | 从 `output/github-secrets-values.txt` 复制 |
| `CLOUDFLARE_API_TOKEN` | 需创建（见下方） |
| `GEMINI_API_KEY` | **必需** - 您的 Google Gemini API 密钥 |
| `GEMINI_API_KEY_PAID` | 可选 - 您的付费版 Gemini 密钥 |

### 创建 Cloudflare Token

1. 访问 [https://dash.cloudflare.com/profile/api-tokens](https://dash.cloudflare.com/profile/api-tokens)
2. Create Token → Custom token
3. 权限：**D1 Write** + **Pages Write**
4. 创建并立即复制 Token（只显示一次！）

## 五、部署 🏁

```bash
# 配置本地开发环境（可选）
cp .env.example .env.local
# 编辑 .env.local 添加 API 密钥

# 推送代码触发部署
git add .
git commit -m "chore: Initial deployment"
git push origin main
```

## 六、验证命令 🔍

```bash
# 查看 Workload Identity
gcloud iam workload-identity-pools list --location=global

# 查看 Cloud Run 日志
gcloud run logs read --service=YOUR_PROJECT_NAME-backend --region=YOUR_REGION

# 查看部署状态
# 访问 GitHub 仓库的 Actions 页面
```

## 七、本地开发 💻

```bash
# 启动后端
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8080

# 启动前端
cd frontend
wrangler dev --port 8787
```

访问 http://localhost:8787，使用 `demo/demo123` 登录

## 八、常见问题快速解决 ⚡

| 问题 | 解决方案 |
|------|---------|
| 向导提示配置文件未填写 | 编辑 `config.sh`，确保所有必填项已填写 |
| CLI 未登录 | 执行 `gcloud auth login` 或 `wrangler login` |
| GCP 项目不存在 | 查看生成的 `output/create-gcp-project-guide.md` |
| Workload Identity 配置失败 | 确认已授予 IAM Workload Identity Pool Admin 权限 |
| GitHub Actions 失败 | 检查所有 Secrets 是否正确配置 |
| 应用无法访问 | 等待 2-3 分钟让 DNS 生效 |

## 九、重要文件位置 📁

```
deployment/setup/
├── config.sh                    # 项目配置（必须编辑）
├── setup-wizard.sh             # 一站式安装向导
└── output/                     # 生成的文件
    ├── manual-setup-guide.md   # 个性化操作指南
    ├── deployment-config.txt   # 配置备份
    └── github-secrets-values.txt # Secret 值列表
```

## 十、相关文档 📚

- [首次部署完整指南](setup-flashmvp.md) - 详细的部署流程说明
- [创建新项目指南](create-new-project.md) - 基于模板创建独立项目
- [CLI 工具安装指南](cli-setup-guide.md) - 详细的工具安装说明

---

💡 **提示**：所有配置值都保存在 `output/` 目录下，建议备份！