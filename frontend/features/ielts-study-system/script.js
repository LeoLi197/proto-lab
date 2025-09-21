// frontend/features/ielts-study-system/script.js
// 新版雅思学习系统：上传 -> 听力 -> 阅读 -> 对话

checkAuth();

let currentSessionId = null;
let sessionPayload = null;
let progressHideTimer = null;

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('uploadForm').addEventListener('submit', handleUploadSubmit);
    setStatus('listeningStatus', '等待生成', 'waiting');
    setStatus('readingStatus', '等待生成', 'waiting');
    setStatus('conversationStatus', '等待生成', 'waiting');
});

function setStatus(elementId, text, state) {
    const pill = document.getElementById(elementId);
    if (!pill) return;
    pill.textContent = text;
    pill.classList.remove('ready', 'waiting', 'error', 'loading');
    if (state) {
        pill.classList.add(state);
    }
}

function setStatusFlag(text, state) {
    const flag = document.getElementById('uploadStatusFlag');
    if (!flag) return;
    flag.textContent = text;
    flag.classList.remove('loading', 'success', 'error');
    if (state) {
        flag.classList.add(state);
    }
}

function toggleProgress(visible) {
    const wrapper = document.getElementById('uploadProgressWrapper');
    if (!wrapper) return;
    if (visible) {
        if (progressHideTimer) {
            clearTimeout(progressHideTimer);
            progressHideTimer = null;
        }
        wrapper.style.display = 'flex';
    } else {
        wrapper.style.display = 'none';
        updateUploadProgress(0);
        if (progressHideTimer) {
            clearTimeout(progressHideTimer);
            progressHideTimer = null;
        }
    }
}

function updateUploadProgress(value) {
    const fill = document.getElementById('uploadProgressFill');
    const text = document.getElementById('uploadProgressText');
    if (!fill || !text) return;
    if (typeof value !== 'number' || Number.isNaN(value)) {
        fill.style.width = '100%';
        text.textContent = '···';
        return;
    }
    const percentage = Math.max(0, Math.min(100, Math.round(value * 100)));
    fill.style.width = `${percentage}%`;
    text.textContent = `${percentage}%`;
}

function showUploadFeedback(message, type = 'info') {
    const container = document.getElementById('uploadFeedback');
    if (!container) return;
    container.textContent = message || '';
    container.classList.remove('error', 'success');
    if (type === 'error') {
        container.classList.add('error');
    } else if (type === 'success') {
        container.classList.add('success');
    }
}

function uploadWithProgress(url, formData, onProgress) {
    return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open('POST', url);
        xhr.responseType = 'json';
        xhr.upload.onprogress = (event) => {
            if (typeof onProgress === 'function') {
                if (event.lengthComputable) {
                    onProgress(event.loaded / event.total);
                } else {
                    onProgress(null);
                }
            }
        };
        xhr.onload = () => {
            if (xhr.status >= 200 && xhr.status < 300) {
                if (xhr.response && typeof xhr.response === 'object') {
                    resolve(xhr.response);
                } else if (xhr.responseText) {
                    try {
                        resolve(JSON.parse(xhr.responseText));
                    } catch (err) {
                        resolve({});
                    }
                } else {
                    resolve({});
                }
            } else {
                const message = parseXHRError(xhr) || '生成学习素材失败';
                reject(new Error(message));
            }
        };
        xhr.onerror = () => {
            reject(new Error('网络异常，请稍后重试'));
        };
        xhr.send(formData);
    });
}

function parseXHRError(xhr) {
    try {
        if (xhr.response && typeof xhr.response === 'object') {
            return xhr.response.detail || xhr.response.message || '';
        }
        if (xhr.responseText) {
            const parsed = JSON.parse(xhr.responseText);
            return parsed.detail || parsed.message || xhr.responseText;
        }
    } catch (err) {
        return xhr.responseText || '';
    }
    return '';
}

function parseManualWords(text) {
    return text
        .split(/[\n,;，\uFF0C]+/)
        .map((item) => item.trim())
        .filter(Boolean);
}

async function handleUploadSubmit(event) {
    event.preventDefault();
    const button = document.getElementById('uploadBtn');
    const summaryBox = document.getElementById('uploadSummary');
    button.disabled = true;
    button.textContent = '生成中...';
    summaryBox.style.display = 'block';
    summaryBox.innerHTML = '<p>正在解析图片并构建学习材料，请稍候...</p>';
    setStatusFlag('上传中', 'loading');
    setStatus('listeningStatus', '生成中', 'loading');
    setStatus('readingStatus', '生成中', 'loading');
    setStatus('conversationStatus', '生成中', 'loading');
    toggleProgress(true);
    updateUploadProgress(0);
    showUploadFeedback('正在上传文件并调用 Gemini 解析...', 'info');

    try {
        const formData = new FormData();
        const fileInput = document.getElementById('wordImages');
        const manualInput = document.getElementById('manualWords').value.trim();
        const scenarioInput = document.getElementById('scenarioHint').value.trim();

        if (fileInput.files.length > 0) {
            Array.from(fileInput.files).forEach((file) => formData.append('files', file));
        }
        if (manualInput) {
            const manualWords = parseManualWords(manualInput);
            if (manualWords.length > 0) {
                formData.append('manual_words', JSON.stringify(manualWords));
            }
        }
        if (scenarioInput) {
            formData.append('scenario_hint', scenarioInput);
        }

        if (window.usageTracker) {
            usageTracker.track({ feature: 'ielts-study-system', action: 'upload-start' });
        }

        const data = await uploadWithProgress('/api/ielts/upload-batch', formData, (progress) => {
            if (progress === null) {
                showUploadFeedback('正在上传文件...', 'info');
                updateUploadProgress(NaN);
            } else {
                updateUploadProgress(progress);
                if (progress >= 1) {
                    showUploadFeedback('上传完成，正在生成学习材料...', 'info');
                }
            }
        });
        if (window.usageTracker) {
            usageTracker.track({ feature: 'ielts-study-system', action: 'upload-success' });
        }
        renderSession(data);
    } catch (error) {
        const message = error && error.message ? error.message : '生成学习素材失败';
        setStatus('listeningStatus', '等待生成', 'waiting');
        setStatus('readingStatus', '等待生成', 'waiting');
        setStatus('conversationStatus', '等待生成', 'waiting');
        setStatusFlag('上传失败', 'error');
        showUploadFeedback(message, 'error');
        toggleProgress(false);
        summaryBox.innerHTML = `<p class="error">${message}</p>`;
        if (window.usageTracker) {
            usageTracker.track({ feature: 'ielts-study-system', action: 'upload-error', detail: message });
        }
    } finally {
        button.disabled = false;
        button.textContent = '生成学习素材';
    }
}

async function safeRead(response) {
    try {
        const text = await response.text();
        return text?.replace(/"/g, '') || '';
    } catch (err) {
        return '';
    }
}

function renderSession(data) {
    currentSessionId = data.session_id;
    sessionPayload = data;
    setStatusFlag('上传成功', 'success');
    updateUploadProgress(1);
    showUploadFeedback('上传成功，学习材料已生成 ✅', 'success');
    if (progressHideTimer) {
        clearTimeout(progressHideTimer);
    }
    progressHideTimer = setTimeout(() => {
        toggleProgress(false);
        progressHideTimer = null;
    }, 600);
    renderUploadSummary(data);
    renderListeningSection(data.listening);
    renderReadingSection(data.reading);
    renderConversationSection(data.conversation);
}

function renderUploadSummary(data) {
    const container = document.getElementById('uploadSummary');
    const { words, story } = data;
    const duplicates = words.duplicates || [];
    const rejected = words.rejected || [];
    const notes = words.extraction_notes || [];

    const duplicatesHtml = duplicates.length
        ? `<div class="meta-note">重复词已去重：${duplicates.join(', ')}</div>`
        : '';
    const rejectedHtml = rejected.length
        ? `<div class="meta-note">忽略的内容：${rejected.join(', ')}</div>`
        : '';
    const notesHtml = notes.length
        ? `<ul class="meta-note">${notes.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`
        : '';
    const wordChips = words.items
        .map((word) => `<span class="word-chip">${escapeHtml(word)}</span>`)
        .join('');
    const sentenceHints = story.sentences
        .map((item) => `<li><strong>${escapeHtml(item.word)}</strong>：${escapeHtml(item.hint)}</li>`)
        .join('');

    container.style.display = 'block';
    container.innerHTML = `
        <div class="session-chip">会话 ID：${escapeHtml(currentSessionId.slice(0, 8))}</div>
        <p>共识别 <strong>${words.total}</strong> 个有效词汇，已全部植入后续练习。</p>
        ${duplicatesHtml}
        ${rejectedHtml}
        ${notesHtml}
        <div class="word-grid">${wordChips}</div>
        <div class="story-block">
            <h3>${escapeHtml(story.title)}</h3>
            <p class="story-overview">${escapeHtml(story.scenario)}</p>
            <p class="story-overview">${escapeHtml(story.overview)}</p>
            ${story.paragraphs.map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`).join('')}
            <p class="story-overview">${escapeHtml(story.closing)}</p>
        </div>
        <details class="hint-list">
            <summary>词汇提示列表</summary>
            <ul>${sentenceHints}</ul>
        </details>
    `;
}

function renderListeningSection(listening) {
    const container = document.getElementById('listeningContent');
    if (!listening) {
        container.innerHTML = '<p class="placeholder">未生成听力材料。</p>';
        setStatus('listeningStatus', '等待生成', 'waiting');
        return;
    }

    const { script, audio, segments, questions, metadata } = listening;
    const audioHtml = audio.available && audio.base64
        ? `<audio controls src="data:${audio.format};base64,${audio.base64}"></audio>`
        : `<p class="hint">${escapeHtml(audio.message || '未生成音频，可使用浏览器朗读。')}</p>`;

    const segmentHtml = segments
        .map(
            (segment) => `
            <div class="segment-item">
                <strong>${segment.index}.</strong>
                <span>${segment.start}s → ${segment.end}s</span>
                <div>${escapeHtml(segment.text)}</div>
            </div>
        `,
        )
        .join('');

    const questionHtml = questions
        .map(
            (question) => `
            <div class="question-card">
                <label for="listen-${question.id}">${question.id}. ${escapeHtml(question.prompt)}</label>
                <input type="text" id="listen-${question.id}" name="${question.id}" autocomplete="off">
                <div class="hint">${escapeHtml(question.hint || '')}</div>
            </div>
        `,
        )
        .join('');

    container.innerHTML = `
        <div class="audio-box">
            ${audioHtml}
            <p class="hint">${escapeHtml(metadata.notes || '')}</p>
        </div>
        <details open>
            <summary>听力脚本</summary>
            <p>${escapeHtml(script)}</p>
        </details>
        <h3>分段概览</h3>
        <div class="segment-list">${segmentHtml}</div>
        <form id="listeningForm">
            <h3>听写题</h3>
            ${questionHtml}
            <div class="form-actions">
                <button type="submit" class="primary">提交答案</button>
            </div>
            <div id="listeningResult" class="evaluation-box" style="display:none;"></div>
        </form>
    `;

    setStatus('listeningStatus', '已生成', 'ready');
    document.getElementById('listeningForm').addEventListener('submit', handleListeningSubmit);
}

function renderReadingSection(reading) {
    const container = document.getElementById('readingContent');
    if (!reading) {
        container.innerHTML = '<p class="placeholder">未生成阅读材料。</p>';
        setStatus('readingStatus', '等待生成', 'waiting');
        return;
    }

    const paragraphsHtml = reading.paragraphs.map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`).join('');
    const glossaryHtml = reading.glossary
        .map(
            (item) => `
            <div class="glossary-card">
                <strong>${escapeHtml(item.word)}</strong>
                <p>${escapeHtml(item.summary)}</p>
                <span class="meta-note">类型：${escapeHtml(item.category)}</span>
            </div>
        `,
        )
        .join('');
    const questionHtml = reading.questions
        .map(
            (question) => `
            <div class="question-card">
                <label for="read-${question.id}">${question.id}. ${escapeHtml(question.prompt)}</label>
                <input type="text" id="read-${question.id}" name="${question.id}" autocomplete="off">
                <div class="hint">${escapeHtml(question.hint || '')}</div>
            </div>
        `,
        )
        .join('');

    container.innerHTML = `
        <div class="story-block">
            <h3>${escapeHtml(reading.title)}</h3>
            ${paragraphsHtml}
        </div>
        <h3>关键词汇表</h3>
        <div class="glossary-grid">${glossaryHtml}</div>
        <form id="readingForm">
            <h3>理解题</h3>
            ${questionHtml}
            <div class="form-actions">
                <button type="submit" class="primary">提交答案</button>
            </div>
            <div id="readingResult" class="evaluation-box" style="display:none;"></div>
        </form>
    `;

    setStatus('readingStatus', '已生成', 'ready');
    document.getElementById('readingForm').addEventListener('submit', handleReadingSubmit);
}

function renderConversationSection(conversation) {
    const container = document.getElementById('conversationContent');
    if (!conversation) {
        container.innerHTML = '<p class="placeholder">未生成对话脚本。</p>';
        setStatus('conversationStatus', '等待生成', 'waiting');
        return;
    }

    const agendaHtml = conversation.agenda
        .map(
            (step) => `
            <div class="agenda-card">
                <strong>步骤 ${step.step}：${escapeHtml(step.goal)}</strong>
                <ul>${step.actions.map((action) => `<li>${escapeHtml(action)}</li>`).join('')}</ul>
            </div>
        `,
        )
        .join('');

    const questionList = conversation.questions
        .map(
            (item, index) => `
            <div class="voice-row" data-index="${index}">
                <div>
                    <strong>Q${index + 1}.</strong> ${escapeHtml(item.question)}
                    <div class="hint">聚焦词汇：${item.focus_words.map(escapeHtml).join(', ')}</div>
                    <div class="hint">追问：${escapeHtml(item.follow_up)}</div>
                </div>
                <button type="button" class="speak-btn">播放</button>
            </div>
        `,
        )
        .join('');

    const tipsHtml = conversation.practice_tips
        .map((tip) => `<li>${escapeHtml(tip)}</li>`)
        .join('');

    container.innerHTML = `
        <div class="story-block">
            <h3>AI 角色</h3>
            <p>${escapeHtml(conversation.role)}</p>
            <p>${escapeHtml(conversation.opening_line)}</p>
        </div>
        <h3>互动步骤</h3>
        <div class="conversation-steps">${agendaHtml}</div>
        <h3>语音问题</h3>
        <div class="voice-list">${questionList}</div>
        <h3>练习提示</h3>
        <ul>${tipsHtml}</ul>
        <p class="hint">${escapeHtml(conversation.closing_line)}</p>
    `;

    container.querySelectorAll('.voice-row').forEach((row) => {
        const index = Number(row.dataset.index);
        const button = row.querySelector('button');
        if (button) {
            button.addEventListener('click', () => {
                const prompt = conversation.voice_prompts[index];
                if (prompt) {
                    speakText(prompt.text);
                }
            });
        }
    });

    setStatus('conversationStatus', '已生成', 'ready');
}

function speakText(text) {
    if (!('speechSynthesis' in window)) {
        alert('当前浏览器不支持语音合成，请手动朗读。');
        return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'en-US';
    utterance.rate = 0.95;
    window.speechSynthesis.speak(utterance);
}

function escapeHtml(value) {
    if (!value) return '';
    return value
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

async function handleListeningSubmit(event) {
    event.preventDefault();
    if (!currentSessionId || !sessionPayload) return;

    const form = event.target;
    const inputs = Array.from(form.querySelectorAll('input'));
    const answers = inputs.map((input) => ({
        question_id: input.name,
        answer: input.value.trim(),
    }));

    const button = form.querySelector('button[type="submit"]');
    const resultBox = document.getElementById('listeningResult');
    button.disabled = true;
    button.textContent = '判分中...';

    try {
        const response = await fetch(`/api/ielts/listening/${currentSessionId}/evaluate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ answers }),
        });
        if (!response.ok) {
            const message = await safeRead(response);
            throw new Error(message || '听力判分失败');
        }
        const result = await response.json();
        renderEvaluationResult(resultBox, result);
    } catch (error) {
        resultBox.style.display = 'block';
        resultBox.innerHTML = `<p class="error">${error.message}</p>`;
    } finally {
        button.disabled = false;
        button.textContent = '提交答案';
    }
}

async function handleReadingSubmit(event) {
    event.preventDefault();
    if (!currentSessionId || !sessionPayload) return;

    const form = event.target;
    const inputs = Array.from(form.querySelectorAll('input'));
    const answers = inputs.map((input) => ({
        question_id: input.name,
        answer: input.value.trim(),
    }));

    const button = form.querySelector('button[type="submit"]');
    const resultBox = document.getElementById('readingResult');
    button.disabled = true;
    button.textContent = '判分中...';

    try {
        const response = await fetch(`/api/ielts/reading/${currentSessionId}/evaluate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ answers }),
        });
        if (!response.ok) {
            const message = await safeRead(response);
            throw new Error(message || '阅读判分失败');
        }
        const result = await response.json();
        renderEvaluationResult(resultBox, result);
    } catch (error) {
        resultBox.style.display = 'block';
        resultBox.innerHTML = `<p class="error">${error.message}</p>`;
    } finally {
        button.disabled = false;
        button.textContent = '提交答案';
    }
}

function renderEvaluationResult(container, result) {
    container.style.display = 'block';
    const accuracy = Math.round((result.accuracy || 0) * 100);
    const breakdown = (result.breakdown || [])
        .map((item) => {
            const cls = item.correct ? 'correct' : 'incorrect';
            const rationale = item.rationale ? `<div class="hint">${escapeHtml(item.rationale)}</div>` : '';
            return `<li class="${cls}">${item.question_id}：${item.correct ? '正确' : `正确答案 ${escapeHtml(item.correct_answer)}`} ${rationale}</li>`;
        })
        .join('');

    container.innerHTML = `
        <strong>得分：${result.score}/${result.total}</strong>
        <p>正确率：${accuracy}%</p>
        <ul>${breakdown}</ul>
    `;
}
