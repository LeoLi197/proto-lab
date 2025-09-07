// 1. 【必需】在脚本开始时进行认证检查
checkAuth();

// 获取DOM元素
const form = document.getElementById('conversion-form');
const fileUploader = document.getElementById('file-uploader');
const statusArea = document.getElementById('status-area');
// ... (获取其他所有需要的元素)

let pollInterval; // 用于存储轮询计时器

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    statusArea.style.display = 'block';
    // ... (重置UI状态)

    const formData = new FormData();
    for (const file of fileUploader.files) {
        formData.append('files', file);
    }
    formData.append('engine', document.querySelector('input[name="engine"]:checked').value);
    formData.append('output_format', document.querySelector('input[name="output_format"]:checked').value);

    try {
        // 2. 【必需】调用后端API
        const response = await fetch('/api/convert-batch', {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) throw new Error(`提交失败: ${await response.text()}`);

        const data = await response.json();
        const taskId = data.task_id;

        // 开始轮询状态
        pollStatus(taskId);

    } catch (error) {
        // ... (处理提交错误)
    }
});

function pollStatus(taskId) {
    pollInterval = setInterval(async () => {
        try {
            const statusResponse = await fetch(`/api/status/${taskId}`);
            const statusData = await statusResponse.json();

            if (statusData.status === 'completed') {
                clearInterval(pollInterval);
                // ... (更新UI为完成状态)

                const downloadLink = document.getElementById('download-link');
                downloadLink.href = `/api/download/${taskId}`;
                downloadLink.download = statusData.filename; // 设置建议的文件名
                document.getElementById('download-area').style.display = 'block';

                // 3. 【必需】调用全局usageTracker记录成本
                // 注意: 您的后端API未返回token用量，此处需要估算或硬编码
                await usageTracker.recordUsage(
                    '高性能文档转换器', // 与注册时名称一致
                    'qwen-vl-max',  // 示例模型
                    'qwen-vl-max',
                    1000, // 示例输入Tokens
                    500   // 示例输出Tokens
                );

            } else if (statusData.status === 'failed') {
                clearInterval(pollInterval);
                // ... (处理失败状态)
            } else {
                // ... (处理 "processing" 或 "queued" 状态)
            }
        } catch (error) {
            clearInterval(pollInterval);
            // ... (处理轮询错误)
        }
    }, 3000); // 每3秒轮询一次
}