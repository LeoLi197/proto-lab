#!/bin/bash

# 1. 添加所有更改到暂存区
git add .

# 2. 提交更改，并使用默认或传入的提交信息
#    "$1" 表示脚本的第一个参数。如果没有提供，则使用 "update"
commit_message="${1:-"update"}"
git commit -m "$commit_message"

# 3. 推送到远程仓库的 main 分支
git push origin main

# 4. 执行位于项目根目录的打包脚本
python bundle_project.py

# 脚本结束提示
echo "✅  部署脚本执行完毕！"