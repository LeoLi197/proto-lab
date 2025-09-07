# 🚀 GCP & Cloudflare CLI 工具安装与登录指南

## 文档说明

**适用场景**：在运行 flashmvp 部署脚本之前，您需要安装并配置必要的命令行工具。  
**预计时间**：10-15分钟  
**工具清单**：
- Google Cloud CLI (`gcloud`)
- Cloudflare CLI (`wrangler`)
- Git（通常已预装）

---

## ✅ 场景一：已安装工具，但尚未登录或配置（最常见）

如果您的电脑上已经安装过 `gcloud` 和 `wrangler`，但脚本提示您"未登录"或"项目未设置"，请按以下步骤操作。

### 1. 登录并配置 Google Cloud (`gcloud`)

**步骤 A: 登录**

执行这个命令后，您的浏览器会自动打开一个谷歌登录页面，请选择您用于GCP的账号完成授权。

```bash
gcloud auth login
```

**步骤 B: 设置项目（关键步骤）**

登录后，您必须告诉 `gcloud` 您希望对哪个项目进行操作。请将 `YOUR_PROJECT_ID` 替换为您在 `config.sh` 中配置的GCP项目ID。

```bash
gcloud config set project YOUR_PROJECT_ID
```

**步骤 C: 验证配置**

```bash
# 检查当前登录账号
gcloud auth list

# 检查当前项目设置
gcloud config get-value project
```

### 2. 登录 Cloudflare (`wrangler`)

执行这个命令后，您的浏览器会自动打开一个Cloudflare登录页面，请完成授权。

```bash
wrangler login
```

**验证登录状态**

```bash
# 检查登录账号信息
wrangler whoami
```

---

## 🛠️ 场景二：需要从零开始安装

如果您是第一次配置环境，请按以下步骤完整安装和配置。

### 1. 安装与配置 Google Cloud CLI (`gcloud`)

#### Windows

1. 下载安装程序：[Google Cloud SDK Installer](https://dl.google.com/dl/cloudsdk/channels/rapid/GoogleCloudSDKInstaller.exe)
2. 运行安装程序，按照向导完成安装
3. 安装完成后，在新的命令提示符或 PowerShell 中执行：
   ```bash
   gcloud init
   ```

#### macOS

**方式一：使用 Homebrew（推荐）**
```bash
# 安装
brew install --cask google-cloud-sdk

# 初始化
gcloud init
```

**方式二：手动安装**
```bash
# 下载并解压
curl https://sdk.cloud.google.com | bash

# 重启终端或执行
source ~/.bashrc  # 或 source ~/.zshrc

# 初始化
gcloud init
```

#### Linux (Ubuntu/Debian)

```bash
# 添加 Cloud SDK 发行版 URI 作为包源
echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list

# 导入 Google Cloud 公钥
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key --keyring /usr/share/keyrings/cloud.google.gpg add -

# 更新并安装
sudo apt-get update && sudo apt-get install google-cloud-cli

# 初始化
gcloud init
```

#### 安装后的配置

无论使用哪种方式安装，都需要执行：

```bash
# 登录您的 Google 账号
gcloud auth login

# 设置默认项目（替换为您的项目ID）
gcloud config set project YOUR_PROJECT_ID
```

### 2. 安装与配置 Cloudflare Wrangler (`wrangler`)

#### 前提条件

您需要先安装 [Node.js](https://nodejs.org/)（推荐 LTS 版本）。

验证 Node.js 是否已安装：
```bash
node --version
npm --version
```

#### 安装 Wrangler

在终端中执行以下命令通过 npm 全局安装 Wrangler：

```bash
npm install -g wrangler
```

#### 登录 Cloudflare

安装完成后，执行登录命令：

```bash
wrangler login
```

浏览器会打开 Cloudflare 授权页面，点击 "Allow" 完成授权。

### 3. 安装 Git（如果尚未安装）

#### Windows

下载并安装 [Git for Windows](https://git-scm.com/download/win)

#### macOS

Git 通常已预装。如果没有，可以通过 Homebrew 安装：
```bash
brew install git
```

#### Linux

```bash
# Ubuntu/Debian
sudo apt-get install git

# Fedora
sudo dnf install git

# CentOS/RHEL
sudo yum install git
```

---

## 🔍 如何验证所有工具是否就绪？

完成以上所有步骤后，您可以通过以下命令来验证是否一切就绪：

### 验证 `gcloud`

```bash
# 检查您是否已成功登录，应能看到您的邮箱
gcloud auth list

# 检查当前项目是否已正确设置，应能看到您的项目ID
gcloud config get-value project

# 测试项目访问权限
gcloud projects describe YOUR_PROJECT_ID
```

### 验证 `wrangler`

```bash
# 检查您是否已成功登录，应能看到您的账户信息
wrangler whoami
```

### 验证 `git`

```bash
# 检查 Git 版本
git --version
```

如果以上命令都能成功返回预期的信息，那么您的环境就已经准备就绪，可以继续执行 `setup-wizard.sh` 脚本了！

---

## 💡 常见问题

### 问题 1：gcloud 命令找不到

**症状**：`command not found: gcloud`

**解决方案**：
- 确认安装已完成
- 重启终端或重新加载配置文件
- 检查 PATH 环境变量是否包含 gcloud 路径

### 问题 2：wrangler 登录失败

**症状**：浏览器无法打开或授权失败

**解决方案**：
- 手动复制终端中显示的 URL 到浏览器
- 检查防火墙或代理设置
- 使用 `wrangler login --browser=false` 进行无浏览器登录

### 问题 3：项目 ID 设置错误

**症状**：脚本提示项目不存在或无权访问

**解决方案**：
```bash
# 列出所有可用项目
gcloud projects list

# 重新设置正确的项目 ID
gcloud config set project CORRECT_PROJECT_ID
```

### 问题 4：权限不足

**症状**：执行命令时提示权限错误

**解决方案**：
- 确认您的 Google 账号有项目的 Editor 或 Owner 权限
- 在 [GCP Console](https://console.cloud.google.com) 中检查 IAM 设置

---

## 📚 更多资源

- [Google Cloud SDK 官方文档](https://cloud.google.com/sdk/docs)
- [Wrangler CLI 官方文档](https://developers.cloudflare.com/workers/wrangler/)
- [Git 官方文档](https://git-scm.com/doc)

---

## ✨ 下一步

环境准备就绪后，您可以：

1. 返回 [首次部署指南](setup-flashmvp.md) 继续部署流程
2. 或者查看 [快速参考卡](cheatsheet.md) 了解常用命令

---

**准备好了吗？** 现在您可以返回主部署流程，运行 `setup-wizard.sh` 脚本了！ 🚀