// frontend/features/ielts-study-system/script.js
// 精简版雅思情景学习系统：仅保留图片识别与情景片段生成功能

checkAuth();

let currentSessionId = null;
let sessionPayload = null;
let progressHideTimer = null;

const GEMINI_KEY_STORAGE_KEY = 'ieltsStudyGeminiApiKey';
const GEMINI_REMEMBER_STORAGE_KEY = 'ieltsStudyRememberGeminiKey';

function readFromLocalStorage(key) {
    try {
        if (typeof window === 'undefined' || !window.localStorage) {
            return null;
        }
        return window.localStorage.getItem(key);
    } catch (err) {
        return null;
    }
}

function writeToLocalStorage(key, value) {
    try {
        if (typeof window === 'undefined' || !window.localStorage) {
            return;
        }
        window.localStorage.setItem(key, value);
    } catch (err) {
        return;
    }
}

function removeFromLocalStorage(key) {
    try {
        if (typeof window === 'undefined' || !window.localStorage) {
            return;
        }
        window.localStorage.removeItem(key);
    } catch (err) {
        return;
    }
}

function getStoredGeminiKey() {
    const value = readFromLocalStorage(GEMINI_KEY_STORAGE_KEY);
    return value || '';
}

function shouldRememberGeminiKey() {
    return readFromLocalStorage(GEMINI_REMEMBER_STORAGE_KEY) === 'true';
}

function getActiveGeminiApiKey() {
    const input = document.getElementById('geminiApiKey');
    if (input && typeof input.value === 'string') {
        const trimmed = input.value.trim();
        if (trimmed) {
            return trimmed;
        }
    }
    return getStoredGeminiKey();
}

function persistGeminiKey(value) {
    const trimmed = typeof value === 'string' ? value.trim() : '';
    if (trimmed) {
        writeToLocalStorage(GEMINI_KEY_STORAGE_KEY, trimmed);
    } else {
        removeFromLocalStorage(GEMINI_KEY_STORAGE_KEY);
    }
}

function persistRememberPreference(remember) {
    writeToLocalStorage(GEMINI_REMEMBER_STORAGE_KEY, remember ? 'true' : 'false');
    if (!remember) {
        removeFromLocalStorage(GEMINI_KEY_STORAGE_KEY);
    }
}

function initialiseGeminiKeyControls() {
    const apiInput = document.getElementById('geminiApiKey');
    const rememberCheckbox = document.getElementById('rememberGeminiKey');
    if (!apiInput || !rememberCheckbox) {
        return;
    }

    const storedKey = getStoredGeminiKey();
    let rememberPreference = shouldRememberGeminiKey();
    if (storedKey && !rememberPreference) {
        rememberPreference = true;
        writeToLocalStorage(GEMINI_REMEMBER_STORAGE_KEY, 'true');
    }

    rememberCheckbox.checked = rememberPreference;
    if (rememberPreference && storedKey) {
        apiInput.value = storedKey;
    }

    rememberCheckbox.addEventListener('change', () => {
        const shouldRemember = rememberCheckbox.checked;
        persistRememberPreference(shouldRemember);
        if (shouldRemember && apiInput.value.trim()) {
            persistGeminiKey(apiInput.value);
        }
    });

    apiInput.addEventListener('input', () => {
        if (!rememberCheckbox.checked) {
            return;
        }
        persistGeminiKey(apiInput.value);
    });
}

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('uploadForm');
    if (form) {
        form.addEventListener('submit', handleUploadSubmit);
    }
    initialiseGeminiKeyControls();
    setStatus('scenarioStatus', '等待生成', 'waiting');
    if (document.body) {
        document.body.classList.add('ielts-theme');
    }
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

function normaliseErrorDetail(value) {
    if (value == null) {
        return '';
    }
    if (typeof value === 'string') {
        return value;
    }
    if (Array.isArray(value)) {
        return value
            .map((item) => normaliseErrorDetail(item))
            .filter(Boolean)
            .join('；');
    }
    if (typeof value === 'object') {
        const preferredKeys = ['detail', 'message', 'msg', 'error'];
        for (const key of preferredKeys) {
            if (key in value) {
                const result = normaliseErrorDetail(value[key]);
                if (result) {
                    return result;
                }
            }
        }
        const parts = Object.values(value)
            .map((item) => normaliseErrorDetail(item))
            .filter(Boolean);
        if (parts.length > 0) {
            return parts.join('；');
        }
        try {
            return JSON.stringify(value);
        } catch (err) {
            return String(value);
        }
    }
    return String(value);
}

function parseXHRError(xhr) {
    try {
        if (xhr.response && typeof xhr.response === 'object') {
            const message = normaliseErrorDetail(xhr.response.detail || xhr.response.message || xhr.response);
            if (message) {
                return message;
            }
        }
        if (xhr.responseText) {
            try {
                const parsed = JSON.parse(xhr.responseText);
                const message = normaliseErrorDetail(parsed.detail || parsed.message || parsed);
                if (message) {
                    return message;
                }
            } catch (err) {
                return xhr.responseText;
            }
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
    const scenarioBox = document.getElementById('scenarioContent');

    button.disabled = true;
    button.textContent = '生成中...';
    if (summaryBox) {
        summaryBox.style.display = 'block';
        summaryBox.innerHTML = '<p>正在解析图片并提取词汇，请稍候...</p>';
    }
    if (scenarioBox) {
        scenarioBox.innerHTML = '<p class="placeholder">正在生成情景片段...</p>';
    }
    setStatusFlag('上传中', 'loading');
    setStatus('scenarioStatus', '生成中', 'loading');
    toggleProgress(true);
    updateUploadProgress(0);
    showUploadFeedback('正在上传文件并调用 Gemini 解析...', 'info');

    try {
        const formData = new FormData();
        const fileInput = document.getElementById('wordImages');
        const manualInput = document.getElementById('manualWords');
        const scenarioInput = document.getElementById('scenarioHint');
        const apiInput = document.getElementById('geminiApiKey');
        const rememberCheckbox = document.getElementById('rememberGeminiKey');
        const geminiApiKey = apiInput ? apiInput.value.trim() : '';
        const rememberGeminiKey = rememberCheckbox ? rememberCheckbox.checked : false;

        if (fileInput && fileInput.files.length > 0) {
            Array.from(fileInput.files).forEach((file) => formData.append('files', file));
        }
        if (manualInput) {
            const manualWords = parseManualWords(manualInput.value.trim());
            if (manualWords.length > 0) {
                formData.append('manual_words', JSON.stringify(manualWords));
            }
        }
        if (scenarioInput && scenarioInput.value.trim()) {
            formData.append('scenario_hint', scenarioInput.value.trim());
        }
        if (geminiApiKey) {
            formData.append('gemini_api_key', geminiApiKey);
        }

        if (rememberCheckbox) {
            if (rememberGeminiKey) {
                persistRememberPreference(true);
                persistGeminiKey(geminiApiKey);
            } else {
                persistRememberPreference(false);
            }
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
                    showUploadFeedback('上传完成，正在生成情景片段...', 'info');
                }
            }
        });

        if (window.usageTracker) {
            usageTracker.track({ feature: 'ielts-study-system', action: 'upload-success' });
        }

        renderSession(data || {});
    } catch (error) {
        const message = error && error.message ? error.message : '生成学习素材失败';
        setStatus('scenarioStatus', '等待生成', 'waiting');
        setStatusFlag('上传失败', 'error');
        showUploadFeedback(message, 'error');
        toggleProgress(false);
        if (summaryBox) {
            summaryBox.innerHTML = `<p class="error">${escapeHtml(message)}</p>`;
        }
        if (scenarioBox) {
            scenarioBox.innerHTML = '<p class="placeholder">请重新上传文件以生成情景片段。</p>';
        }
        if (window.usageTracker) {
            usageTracker.track({ feature: 'ielts-study-system', action: 'upload-error', detail: message });
        }
    } finally {
        button.disabled = false;
        button.textContent = '生成情景素材';
    }
}

function renderSession(data) {
    currentSessionId = data.session_id || '';
    sessionPayload = data;
    setStatusFlag('上传成功', 'success');
    updateUploadProgress(1);
    showUploadFeedback('上传成功，情景片段已生成 ✅', 'success');
    if (progressHideTimer) {
        clearTimeout(progressHideTimer);
    }
    progressHideTimer = setTimeout(() => {
        toggleProgress(false);
        progressHideTimer = null;
    }, 600);

    renderUploadSummary(data);
    renderScenarioContent(data.story, data.words);
}

function renderUploadSummary(data) {
    const container = document.getElementById('uploadSummary');
    if (!container) return;

    const words = data.words || {};
    const items = Array.isArray(words.items) ? words.items : [];
    const duplicates = Array.isArray(words.duplicates) ? words.duplicates : [];
    const rejected = Array.isArray(words.rejected) ? words.rejected : [];
    const notes = Array.isArray(words.extraction_notes) ? words.extraction_notes : [];

    const duplicatesHtml = duplicates.length
        ? `<div class="meta-note">重复词已去重：${duplicates.map(escapeHtml).join(', ')}</div>`
        : '';
    const rejectedHtml = rejected.length
        ? `<div class="meta-note">忽略的内容：${rejected.map(escapeHtml).join(', ')}</div>`
        : '';
    const notesHtml = notes.length
        ? `<ul class="meta-note">${notes.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`
        : '';
    const wordChips = items.length
        ? items.map((word) => `<span class="word-chip">${escapeHtml(word)}</span>`).join('')
        : '<span class="placeholder">未识别到有效词汇。</span>';

    container.style.display = 'block';
    container.innerHTML = `
        <div class="session-chip">会话 ID：${currentSessionId ? escapeHtml(currentSessionId.slice(0, 8)) : '暂无'}</div>
        <p>共识别 <strong>${words.total || items.length}</strong> 个有效词汇，全部用于生成下方情景片段。</p>
        ${duplicatesHtml}
        ${rejectedHtml}
        ${notesHtml}
        <div class="word-grid">${wordChips}</div>
    `;
}

function renderScenarioContent(story, words) {
    const container = document.getElementById('scenarioContent');
    if (!container) return;

    if (!story) {
        container.innerHTML = '<p class="placeholder">未能生成情景片段，请重试或补充更多提示。</p>';
        setStatus('scenarioStatus', '等待生成', 'waiting');
        return;
    }

    const title = story.title ? escapeHtml(story.title) : '情景片段';
    const scenario = story.scenario ? `<p class="story-overview">${escapeHtml(story.scenario)}</p>` : '';
    const overview = story.overview ? `<p class="story-overview">${escapeHtml(story.overview)}</p>` : '';
    const paragraphs = Array.isArray(story.paragraphs)
        ? story.paragraphs.map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`).join('')
        : '';
    const closing = story.closing ? `<p class="story-overview">${escapeHtml(story.closing)}</p>` : '';

    const segments = Array.isArray(story.sentences) ? story.sentences : [];
    const segmentList = segments.length
        ? `<div class="scenario-list-wrapper">
                <h3>逐词情景提示</h3>
                <ul class="segment-list">
                    ${segments
                        .map(
                            (item, index) => `
                                <li class="segment-item">
                                    <strong>${index + 1}. ${escapeHtml(item.word || '')}</strong>
                                    <p>${escapeHtml(item.hint || '')}</p>
                                </li>
                            `,
                        )
                        .join('')}
                </ul>
            </div>`
        : '';

    const focusWordList = words && Array.isArray(words.items) ? words.items : [];
    const focusHtml = focusWordList.length
        ? `<div class="meta-note">本段故事聚焦词汇：${focusWordList.map(escapeHtml).join('、')}</div>`
        : '';

    container.innerHTML = `
        <div class="story-block">
            <h3>${title}</h3>
            ${scenario}
            ${overview}
            ${paragraphs}
            ${closing}
            ${focusHtml}
        </div>
        ${segmentList}
    `;

    setStatus('scenarioStatus', '已生成', 'ready');
}

function escapeHtml(value) {
    if (value == null) {
        return '';
    }
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
