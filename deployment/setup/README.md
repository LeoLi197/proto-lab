# 部署设置文档导航

欢迎来到 `flashmvp` 项目的部署设置目录。本目录包含了部署和配置项目所需的所有工具和文档。

## 🎯 快速导航：您属于哪种情况？

### 情况 A：我是第一次使用 flashmvp 框架

您需要将 flashmvp 框架部署到自己的云账号上。

**👉 请阅读：[setup-flashmvp.md](setup-flashmvp.md)**

这份指南将帮助您：
- 配置项目基本信息
- 创建 Google Cloud 和 Cloudflare 资源
- 设置 GitHub Actions 自动部署
- 完成首次部署验证

预计用时：20-30 分钟

---

### 情况 B：我想基于 flashmvp 创建一个全新的项目

您已经了解 flashmvp，想要将它作为模板，创建一个独立的新项目（拥有独立的代码库、云资源和版本历史）。

**👉 请阅读：[create-new-project.md](create-new-project.md)**

这份指南将帮助您：
- 复制并配置新项目
- 清理模板历史记录
- 自动重命名项目标识
- 创建独立的云环境

预计用时：15-20 分钟

---

### 情况 C：我已经熟悉流程，需要快速查阅

您已经成功部署过项目，现在需要快速查找命令或配置项。

**👉 请阅读：[cheatsheet.md](cheatsheet.md)**

这份速查卡包含：
- 核心命令列表
- GitHub Secrets 配置表
- 常用验证命令
- 关键文件位置

---

## 📁 目录结构说明

```
deployment/setup/
│
├── 📘 README.md                  # 当前文件（导航中心）
├── 📗 setup-flashmvp.md          # 首次部署完整指南
├── 📙 create-new-project.md      # 基于模板创建新项目
├── 📕 cheatsheet.md              # 快速参考速查卡
├── 📖 cli-setup-guide.md         # CLI 工具安装指南
│
├── 🔧 setup-wizard.sh            # 一站式安装向导（所有部署的入口）
├── ⚙️ config.sh                  # 项目配置文件（部署前必须编辑）
│
├── 📂 internal/                  # 内部脚本（无需直接操作）
│   ├── init_deploy.sh           # 核心部署逻辑
│   └── generate_setup_guide.sh  # 文档生成工具
│
├── 📂 docs/                      # 辅助文档和模板
│   ├── static/                  # 静态参考文档
│   ├── sop/                     # 标准操作流程
│   └── templates/               # 动态文档模板
│
└── 📂 output/                    # 运行时生成的文件
    ├── manual-setup-guide.md    # 个性化操作指南
    ├── deployment-config.txt    # 配置备份
    └── github-secrets-values.txt # Secret 值列表
```

---

## 🚀 核心工作流程

无论您是哪种情况，基本流程都是：

```mermaid
graph LR
    A[编辑 config.sh] --> B[运行 setup-wizard.sh]
    B --> C[按提示完成配置]
    C --> D[推送代码部署]
```

1. **配置**：编辑 `config.sh` 文件，填写项目信息
2. **执行**：运行 `setup-wizard.sh` 向导
3. **授权**：按照生成的指南完成必要的手动步骤
4. **部署**：推送代码到 GitHub，自动触发部署

---

## ❓ 常见问题

### 我应该从哪里开始？

- 如果这是您第一次接触 flashmvp → 阅读 **setup-flashmvp.md**
- 如果您想创建新项目 → 阅读 **create-new-project.md**
- 如果您只是忘记了某个命令 → 查看 **cheatsheet.md**
- 如果需要安装 CLI 工具 → 查看 **cli-setup-guide.md**

### 为什么有这么多文档？

每份文档针对不同的使用场景：
- `setup-flashmvp.md` - 详细的首次部署指南，包含所有细节和故障排除
- `create-new-project.md` - 专门针对模板复用场景，强调差异化步骤
- `cheatsheet.md` - 精简的命令和配置速查，方便日常使用
- `cli-setup-guide.md` - CLI 工具的安装和配置说明

### 我可以直接运行 internal/ 下的脚本吗？

**不建议**。请始终通过 `setup-wizard.sh` 运行，它会：
- 验证您的环境配置
- 检查前置条件
- 提供清晰的错误提示
- 生成个性化的后续指南

### 如果部署失败了怎么办？

1. 查看错误信息，通常会有明确的提示
2. 检查 `output/` 目录下的日志和配置文件
3. 参考相应指南中的"故障排除"部分
4. 重新运行 `setup-wizard.sh`（会智能跳过已完成步骤）

---

## 💡 提示

- **第一次使用**：不要跳过步骤，按照指南逐步操作
- **保存配置**：`output/deployment-config.txt` 包含所有重要配置，建议备份
- **密钥安全**：永远不要将 API 密钥提交到代码库
- **寻求帮助**：如果遇到问题，先查看相应文档的故障排除部分

---

## 📚 其他资源

- **项目文档**：查看项目根目录的 `/docs` 了解框架功能
- **API 文档**：后端 API 文档在部署后可通过 `/docs` 端点访问
- **社区支持**：通过 GitHub Issues 报告问题或寻求帮助

---

## 📝 文档列表

### 主要指南
- [setup-flashmvp.md](setup-flashmvp.md) - 首次部署 flashmvp 框架
- [create-new-project.md](create-new-project.md) - 基于模板创建新项目
- [cheatsheet.md](cheatsheet.md) - 快速参考和命令速查
- [cli-setup-guide.md](cli-setup-guide.md) - CLI 工具安装与配置

### 辅助文档（docs/ 目录）
- `docs/sop/` - 标准操作流程文档
- `docs/static/` - 静态参考文档
- `docs/templates/` - 动态生成文档的模板

### 生成文档（output/ 目录）
运行向导后会生成：
- `manual-setup-guide.md` - 针对您项目的个性化指南
- `deployment-config.txt` - 本次部署的配置记录
- `github-secrets-values.txt` - GitHub Secrets 配置值

---

**准备好了吗？** 根据您的情况，选择上方对应的指南开始部署吧！ 🚀