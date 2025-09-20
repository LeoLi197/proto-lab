// Path: frontend/config.js
// flashmvp配置文件 - 直接修改此文件来管理用户和功能

const USERS = [
    { username: 'demo', password: 'demo123' },
    { username: 'client1', password: 'test2024' },
];

const FEATURES = [
    // ==============================================================================
    // [示例] 如何注册一个新的前端功能模块
    // ------------------------------------------------------------------------------
    // 在此数组中添加一个新对象，即可在功能中心看到您的新功能卡片。
    //
    // {
    //     path: 'my-new-feature/index.html',         // 路径指向 frontend/features/ 下的文件
    //     name: '🚀 我的新功能',                      // 显示在卡片上的名称
    //     description: '这是对我的新功能的简要描述，帮助用户理解它的用途。',
    //     isFullPath: true                          // 通常保持为 true
    // },
    // ==============================================================================

    // --- [已移除功能的示例] ---
    // {
    //     path: 'kidtype-english/index.html',
    //     name: '⌨️ KidType 英文打字',
    //     description: '为加拿大小学生设计的趣味打字练习工具。AI生成适合其年龄段的英文短文或对话，并提供实时的指法引导。',
    //     isFullPath: true
    // },
    // {
    //     path: 'english-writing-practice/index.html',
    //     name: '💬 英语写作陪练',
    //     description: '在真实场景中练习英语对话，AI教练将对您的每一句话提供语法、地道性和表达习惯的实时反馈。',
    //     isFullPath: true
    // },
    // {
    //     path: 'second-hand-valuer/index.html',
    //     name: '🤖 AI 二手商品估价',
    //     description: '上传任意商品的照片和描述，让AI专家为您进行快速、准确的市场估价。',
    //     isFullPath: true
    // },
    // {
    //     path: 'bank-statement-analyzer/index.html',
    //     name: '🏦 银行流水分析工具',
    //     description: '上传银行流水PDF，自动提取并分析交易数据，并从贷款审批视角生成专业分析报告。',
    //     isFullPath: true
    // },

    // --- 开发者专用样板 (保留作为开发起点) ---
    {
        path: 'boilerplate-gemini/index.html',
        name: '⚙️ Gemini 功能开发样板',
        description: '【开发者专用】提供调用 Gemini 服务的最小代码范例，可作为新功能开发的起点。',
        isFullPath: true
    },
    {
        path: 'boilerplate-openai/index.html',
        name: '⚙️ OpenAI 功能开发样板',
        description: '【开发者专用】提供调用 OpenAI 服务的最小代码范例，展示了框架的多供应商支持能力。',
        isFullPath: true
    },
    {
        path: 'chess-academy/index.html',
        name: '♟️ 星空儿童国际象棋学院',
        description: '面向小学生的国际象棋学习和对弈模块，包含智能棋友、友好提示与每日谜题。',
        isFullPath: true
    },
    {
        path: 'ielts-study-system/index.html',
        name: '🎓 雅思智能学习系统',
        description: '专业雅思备考平台，整合听说读写训练、个性化学习路径、词汇复习与模考分析。',
        isFullPath: true
    },
];