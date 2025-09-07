// frontend/models.js
// flashmvp AI模型配置文件 - 包含所有支持的AI模型信息和价格
// 价格需要手动更新，单位为美元/百万tokens

const AI_MODELS = {
    // Google Gemini系列
    gemini: {
        name: 'Google Gemini',
        models: {
            'gemini-2.5-pro': {
                name: 'Gemini 2.5 Pro',
                description: '增强的思考和推理能力，多模态理解，高级编码等功能。',
                pricing: { input: 3.50, output: 10.50 }, // Per 1M tokens
                context: 1000000,
                features: ['增强思考和推理', '多模态理解', '高级编码', '复杂问题处理', '音频/图像/视频/文本/PDF输入']
            },
            'gemini-2.5-flash': {
                name: 'Gemini 2.5 Flash',
                description: '自适应思考，成本效益高，支持1M token上下文窗口。',
                pricing: { input: 0.35, output: 1.05 }, // Per 1M tokens
                context: 1000000,
                features: ['自适应思考', '成本效益高', '多模态理解', '音频/图像/视频/文本输入']
            },
            'gemini-2.5-flash-lite': {
                name: 'Gemini 2.5 Flash-Lite',
                description: '最具成本效益的模型，支持高吞吐量。',
                pricing: { input: 0.15, output: 0.45 }, // Per 1M tokens - estimated pricing
                context: 1000000,
                features: ['最高成本效益', '高吞吐量', '文本/图像/视频/音频输入']
            }
        }
    },

    // Alibaba Qwen系列
    qwen: {
        name: 'Alibaba Qwen',
        models: {
            'qwen-long': {
                name: 'Qwen Long',
                description: '阿里最强大的长文本模型，支持中英文',
                pricing: { input: 0.50, output: 1.00 }, // Per 1M tokens, example pricing
                context: 10000000,
                features: ['超长文本处理', '中文优化', '复杂推理']
            },
            'qwen-plus': {
                name: 'Qwen Plus',
                description: '性能均衡的中型模型',
                pricing: { input: 2.00, output: 4.00 }, // Per 1M tokens, example pricing
                context: 32000,
                features: ['中文理解', '代码生成', '知识问答']
            }
        }
    },

    // Anthropic Claude系列
    claude: {
        name: 'Anthropic Claude',
        models: {
            'claude-3-opus-20240229': {
                name: 'Claude 3 Opus',
                description: 'Claude最强大的模型，适合复杂任务',
                pricing: { input: 15.00, output: 75.00 }, // Per 1M tokens
                context: 200000,
                features: ['顶级智能', '复杂分析', '专业任务']
            },
            'claude-3-sonnet-20240229': {
                name: 'Claude 3.5 Sonnet',
                description: '最新的Claude模型，智能与速度的完美平衡',
                pricing: { input: 3.00, output: 15.00 }, // Per 1M tokens
                context: 200000,
                features: ['高级推理', '代码生成', '创意写作']
            },
            'claude-3-haiku-20240307': {
                name: 'Claude 3 Haiku',
                description: '快速且经济的Claude模型',
                pricing: { input: 0.25, output: 1.25 }, // Per 1M tokens
                context: 200000,
                features: ['快速响应', '日常任务', '客户服务']
            }
        }
    },

    // OpenAI GPT系列
    openai: {
        name: 'OpenAI GPT',
        models: {
            'gpt-4-turbo': {
                name: 'GPT-4 Turbo',
                description: 'OpenAI最新的GPT-4模型',
                pricing: { input: 10.00, output: 30.00 }, // Per 1M tokens
                context: 128000,
                features: ['顶级性能', '多模态', '函数调用']
            },
            'gpt-3.5-turbo': {
                name: 'GPT-3.5 Turbo',
                description: '经济实惠的GPT模型',
                pricing: { input: 0.50, output: 1.50 }, // Per 1M tokens
                context: 16000,
                features: ['快速响应', '通用对话', '成本效益']
            }
        }
    }
};

/**
 * Calculates the estimated cost of an AI API call.
 * @param {string} provider - The AI provider (e.g., 'gemini').
 * @param {string} model - The model ID (e.g., 'gemini-2.5-flash').
 * @param {number} inputTokens - The number of input tokens.
 * @param {number} outputTokens - The number of output tokens.
 * @param {object} options - Optional parameters for complex pricing.
 * @returns {object|null} An object with costs or null if model not found.
 */
function calculateCost(provider, model, inputTokens, outputTokens, options = {}) {
    const modelInfo = AI_MODELS[provider]?.models[model];
    if (!modelInfo) {
        console.error(`Cost calculation failed: Model ${provider}/${model} not found.`);
        return null;
    }

    // Default pricing
    let inputPrice = modelInfo.pricing.input;
    let outputPrice = modelInfo.pricing.output;

    // Here you could add more complex pricing logic if needed,
    // for example, based on the 'options' parameter.
    // For now, it uses the standard input/output pricing.

    const inputCost = (inputTokens / 1000000) * inputPrice;
    const outputCost = (outputTokens / 1000000) * outputPrice;

    return {
        inputCost: inputCost,
        outputCost: outputCost,
        totalCost: inputCost + outputCost
    };
}

/**
 * Gets a flattened list of all available models from all providers.
 * @returns {Array<object>} A list of model objects.
 */
function getAvailableModels() {
    const models = [];
    for (const [provider, providerInfo] of Object.entries(AI_MODELS)) {
        for (const [modelId, modelInfo] of Object.entries(providerInfo.models)) {
            models.push({
                provider: provider,
                providerName: providerInfo.name,
                modelId: modelId,
                ...modelInfo
            });
        }
    }
    return models;
}