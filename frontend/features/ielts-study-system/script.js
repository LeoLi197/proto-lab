// frontend/features/ielts-study-system/script.js
// 新版雅思学习系统：上传 -> 听力 -> 阅读 -> 对话

checkAuth();

let currentSessionId = null;
let sessionPayload = null;
let progressHideTimer = null;
let activeConversationGuide = null;

const AUDIO_SPEED_PRESETS = [0.75, 1, 1.25, 1.5];
const DEFAULT_SPEED_INDEX = (() => {
    const index = AUDIO_SPEED_PRESETS.indexOf(1);
    return index >= 0 ? index : 0;
})();

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
    const hasAudio = Boolean(audio && audio.available && audio.base64);
    const noteMessage = typeof metadata?.notes === 'string' ? metadata.notes : '';
    let audioHtml = '';
    let audioNoteHtml = '';

    if (hasAudio) {
        const format = audio.format || 'audio/wav';
        const defaultRate = AUDIO_SPEED_PRESETS[DEFAULT_SPEED_INDEX] || 1;
        audioHtml = `
            <div class="audio-player" data-has-audio="true">
                <audio id="listeningAudio" preload="metadata" src="data:${format};base64,${audio.base64}"></audio>
                <div class="audio-player-controls">
                    <button type="button" id="listeningPlayBtn" class="audio-btn primary">▶ 开始播放</button>
                    <button type="button" id="listeningSpeedBtn" class="audio-btn secondary"
                        data-speed-index="${DEFAULT_SPEED_INDEX}">语速：${formatPlaybackRate(defaultRate)}x</button>
                </div>
                <p class="hint subtle">点击“开始播放”收听听力，可循环切换语速。</p>
            </div>
        `;
        if (noteMessage) {
            audioNoteHtml = `<p class="hint">${escapeHtml(noteMessage)}</p>`;
        }
    } else {
        const fallbackMessage = noteMessage || audio.message || '未生成音频，可使用浏览器朗读。';
        audioHtml = `<p class="hint">${escapeHtml(fallbackMessage)}</p>`;
    }

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
            ${audioNoteHtml}
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

    if (hasAudio) {
        initListeningAudioControls();
    }
    setStatus('listeningStatus', '已生成', 'ready');
    document.getElementById('listeningForm').addEventListener('submit', handleListeningSubmit);
}

function initListeningAudioControls() {
    const audioEl = document.getElementById('listeningAudio');
    const playBtn = document.getElementById('listeningPlayBtn');
    const speedBtn = document.getElementById('listeningSpeedBtn');
    if (!audioEl || !playBtn || !speedBtn) {
        return;
    }

    const applySpeed = (index) => {
        const total = AUDIO_SPEED_PRESETS.length;
        const safeIndex = ((index % total) + total) % total;
        const rate = AUDIO_SPEED_PRESETS[safeIndex] || 1;
        audioEl.playbackRate = rate;
        speedBtn.dataset.speedIndex = String(safeIndex);
        speedBtn.textContent = `语速：${formatPlaybackRate(rate)}x`;
    };

    const resetPlayLabel = (label) => {
        playBtn.textContent = label;
        playBtn.classList.remove('is-playing');
    };

    playBtn.addEventListener('click', async () => {
        if (audioEl.paused || audioEl.ended) {
            if (audioEl.ended) {
                audioEl.currentTime = 0;
            }
            try {
                await audioEl.play();
                playBtn.textContent = '⏸ 暂停';
                playBtn.classList.add('is-playing');
            } catch (err) {
                console.error('音频播放失败', err);
            }
        } else {
            audioEl.pause();
        }
    });

    audioEl.addEventListener('pause', () => {
        if (audioEl.ended || audioEl.currentTime === 0) {
            resetPlayLabel('▶ 开始播放');
        } else {
            resetPlayLabel('▶ 继续播放');
        }
    });

    audioEl.addEventListener('play', () => {
        playBtn.textContent = '⏸ 暂停';
        playBtn.classList.add('is-playing');
    });

    audioEl.addEventListener('ended', () => {
        audioEl.currentTime = 0;
        resetPlayLabel('▶ 重新播放');
    });

    speedBtn.addEventListener('click', () => {
        const currentIndex = Number.parseInt(speedBtn.dataset.speedIndex || String(DEFAULT_SPEED_INDEX), 10);
        applySpeed(currentIndex + 1);
    });

    const initialIndex = Number.parseInt(speedBtn.dataset.speedIndex || String(DEFAULT_SPEED_INDEX), 10);
    applySpeed(Number.isNaN(initialIndex) ? DEFAULT_SPEED_INDEX : initialIndex);
    resetPlayLabel('▶ 开始播放');
}

function formatPlaybackRate(rate) {
    if (!Number.isFinite(rate)) {
        return '1.0';
    }
    if (Math.abs(rate % 1) < 1e-8) {
        return rate.toFixed(1);
    }
    const formatted = rate.toFixed(2);
    return formatted.endsWith('0') ? formatted.slice(0, -1) : formatted;
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
    if (activeConversationGuide && typeof activeConversationGuide.destroy === 'function') {
        activeConversationGuide.destroy();
        activeConversationGuide = null;
    }

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

    const tipsHtml = conversation.practice_tips
        .map((tip) => `<li>${escapeHtml(tip)}</li>`)
        .join('');

    const progressHtml = conversation.questions
        .map((item, index) => `<li data-index="${index}"><span>Q${index + 1}</span></li>`)
        .join('');

    container.innerHTML = `
        <div class="story-block">
            <h3>AI 角色</h3>
            <p>${escapeHtml(conversation.role)}</p>
            <p>${escapeHtml(conversation.opening_line)}</p>
        </div>
        <h3>互动步骤</h3>
        <div class="conversation-steps">${agendaHtml}</div>
        <h3>引导式语音练习</h3>
        <div class="coach-wrapper" id="conversationCoach">
            <div class="coach-header">
                <div class="coach-question-label">当前提问</div>
                <div id="conversationQuestionText" class="coach-question-text"></div>
                <button type="button" id="conversationRepeatBtn" class="coach-repeat">重播问题</button>
            </div>
            <div class="coach-body">
                <div id="conversationTranscript" class="coach-transcript hint">按住下方按钮即可开始回答，系统会自动转写你的语音。</div>
                <div id="conversationFeedback" class="coach-feedback"></div>
                <button type="button" id="conversationAnswerBtn" class="push-to-talk">按住回答</button>
                <div id="conversationFallback" class="manual-answer" style="display:none;">
                    <textarea id="conversationManualInput" rows="3" placeholder="若语音识别不可用，可在此输入答案。"></textarea>
                    <button type="button" id="conversationManualSubmit" class="coach-manual-submit">提交文本回答</button>
                </div>
            </div>
            <ol id="conversationProgress" class="coach-progress">${progressHtml}</ol>
            <div id="conversationClosingHint" class="coach-closing hint"></div>
        </div>
        <h3>练习提示</h3>
        <ul>${tipsHtml}</ul>
        <p class="hint">${escapeHtml(conversation.closing_line)}</p>
    `;

    activeConversationGuide = setupGuidedConversation(container, conversation);

    setStatus('conversationStatus', '已生成', 'ready');
}

function setupGuidedConversation(container, conversation) {
    const questionBox = container.querySelector('#conversationQuestionText');
    const repeatBtn = container.querySelector('#conversationRepeatBtn');
    const answerBtn = container.querySelector('#conversationAnswerBtn');
    const transcriptBox = container.querySelector('#conversationTranscript');
    const feedbackBox = container.querySelector('#conversationFeedback');
    const progressItems = Array.from(container.querySelectorAll('#conversationProgress li'));
    const fallbackWrapper = container.querySelector('#conversationFallback');
    const manualInput = container.querySelector('#conversationManualInput');
    const manualSubmit = container.querySelector('#conversationManualSubmit');
    const closingHint = container.querySelector('#conversationClosingHint');

    let currentIndex = 0;
    let recognition = createSpeechRecognition();
    let isListening = false;
    let hasResult = false;
    let nextQuestionTimer = null;
    let destroyed = false;
    let manualHandlerAttached = false;

    if (manualSubmit) {
        manualSubmit.disabled = true;
    }

    if (!Array.isArray(conversation.questions) || conversation.questions.length === 0) {
        if (questionBox) {
            questionBox.innerHTML = '<div class="coach-question-main">暂未生成可用问题。</div>';
        }
        if (answerBtn) {
            answerBtn.disabled = true;
            answerBtn.textContent = '暂无问题';
        }
        if (fallbackWrapper) {
            fallbackWrapper.style.display = 'none';
        }
        return {
            destroy() {
                destroyed = true;
            },
        };
    }

    const resetTranscript = () => {
        if (transcriptBox) {
            transcriptBox.textContent = '准备好后按住下方按钮开始回答。';
        }
        if (feedbackBox) {
            feedbackBox.innerHTML = '';
        }
        if (manualInput) {
            manualInput.value = '';
        }
    };

    const getCurrentQuestion = () => conversation.questions[currentIndex];

    const updateQuestionView = () => {
        const question = getCurrentQuestion();
        if (!question || !questionBox) return;
        const focusWords = (question.focus_words || []).filter(Boolean);
        const focusHtml = focusWords.length
            ? `<div class="hint">聚焦词汇：${focusWords.map(escapeHtml).join('、')}</div>`
            : '';
        const followUp = question.follow_up
            ? `<div class="hint">追问：${escapeHtml(question.follow_up)}</div>`
            : '';
        questionBox.innerHTML = `
            <div class="coach-question-main"><strong>${escapeHtml(question.id || `Q${currentIndex + 1}`)}.</strong> ${escapeHtml(question.question)}</div>
            ${focusHtml}
            ${followUp}
        `;
    };

    const updateProgress = (completed = false) => {
        updateConversationProgress(progressItems, currentIndex, completed);
    };

    const speakCurrentQuestion = () => {
        const question = getCurrentQuestion();
        if (!question) return;
        const prompt = conversation.voice_prompts && conversation.voice_prompts[currentIndex];
        const line = prompt && prompt.text ? prompt.text : question.question;
        if (line) {
            if ('speechSynthesis' in window) {
                speakText(line);
            }
        }
    };

    const askQuestion = () => {
        clearTimeout(nextQuestionTimer);
        resetTranscript();
        updateQuestionView();
        updateProgress(false);
        if (closingHint) {
            closingHint.textContent = '';
        }
        speakCurrentQuestion();
    };

    const finishConversation = () => {
        clearTimeout(nextQuestionTimer);
        updateConversationProgress(progressItems, progressItems.length, true);
        if (answerBtn) {
            answerBtn.disabled = true;
            answerBtn.classList.remove('recording');
            answerBtn.textContent = '练习已完成';
        }
        if (feedbackBox) {
            feedbackBox.innerHTML = '<div class="coach-feedback-success">🎉 已完成全部问题，继续复盘练习提示吧！</div>';
        }
        if (closingHint && conversation.closing_line) {
            closingHint.textContent = conversation.closing_line;
        }
        if (manualSubmit) {
            manualSubmit.disabled = true;
        }
    };

    const evaluateAndRespond = (transcript) => {
        if (!transcriptBox || !feedbackBox) return;
        const trimmed = transcript.trim();
        if (!trimmed) {
            transcriptBox.textContent = '未捕捉到语音内容，请重试。';
            return;
        }
        transcriptBox.textContent = trimmed;
        const question = getCurrentQuestion();
        if (!question) {
            return;
        }
        const result = evaluateConversationAnswer(trimmed, question);
        if (result.passed) {
            feedbackBox.innerHTML = `<div class="coach-feedback-success">👍 ${result.adviceHtml}</div>`;
            if (currentIndex < conversation.questions.length - 1) {
                clearTimeout(nextQuestionTimer);
                nextQuestionTimer = window.setTimeout(() => {
                    currentIndex += 1;
                    askQuestion();
                }, 1200);
            } else {
                finishConversation();
            }
        } else {
            const reference = result.referenceHtml
                ? `<div class="coach-reference"><strong>参考答案：</strong>${result.referenceHtml}</div>`
                : '';
            feedbackBox.innerHTML = `<div class="coach-feedback-error">❗ ${result.adviceHtml}</div>${reference}`;
        }
    };

    const handleManualSubmit = () => {
        if (!manualInput) return;
        evaluateAndRespond(manualInput.value || '');
    };

    const enableManualFallback = (message) => {
        if (fallbackWrapper) {
            fallbackWrapper.style.display = 'block';
        }
        if (answerBtn) {
            answerBtn.disabled = true;
            if (message) {
                answerBtn.textContent = message;
            }
        }
        if (manualSubmit) {
            manualSubmit.disabled = false;
            if (!manualHandlerAttached) {
                manualSubmit.addEventListener('click', handleManualSubmit);
                manualHandlerAttached = true;
            }
        }
        if (transcriptBox && message) {
            transcriptBox.textContent = `${message}，可在下方手动输入答案。`;
        }
    };

    const attachRecognitionHandlers = () => {
        if (!recognition || !answerBtn) {
            enableManualFallback('当前浏览器不支持语音识别');
            return;
        }
        const startListening = (event) => {
            event.preventDefault();
            if (!recognition || isListening) {
                return;
            }
            hasResult = false;
            try {
                recognition.start();
            } catch (err) {
                enableManualFallback('语音识别不可用');
                return;
            }
        };
        const stopListening = () => {
            if (!recognition || !isListening) {
                return;
            }
            try {
                recognition.stop();
            } catch (err) {
                // Ignore stop errors
            }
        };

        answerBtn.addEventListener('pointerdown', startListening);
        answerBtn.addEventListener('pointerup', stopListening);
        answerBtn.addEventListener('pointerleave', stopListening);
        answerBtn.addEventListener('pointercancel', stopListening);

        recognition.onstart = () => {
            isListening = true;
            if (answerBtn) {
                answerBtn.classList.add('recording');
                answerBtn.textContent = '录音中... 松开结束';
            }
            if (transcriptBox) {
                transcriptBox.textContent = '录音中，请大胆表达你的答案...';
            }
            if (feedbackBox) {
                feedbackBox.innerHTML = '';
            }
        };

        recognition.onend = () => {
            isListening = false;
            if (answerBtn) {
                answerBtn.classList.remove('recording');
                answerBtn.textContent = '按住回答';
            }
            if (!hasResult && transcriptBox) {
                transcriptBox.textContent = '未识别到语音，请重试或手动输入。';
            }
        };

        recognition.onerror = (event) => {
            hasResult = true;
            isListening = false;
            if (answerBtn) {
                answerBtn.classList.remove('recording');
                answerBtn.textContent = '按住回答';
            }
            const message = event.error === 'no-speech'
                ? '没有检测到语音，请再试一次。'
                : `语音识别出错：${event.error || event.message || '请稍后重试'}`;
            if (transcriptBox) {
                transcriptBox.textContent = message;
            }
            const fatalErrors = ['not-allowed', 'service-not-allowed', 'audio-capture'];
            if (fatalErrors.includes(event.error)) {
                enableManualFallback('语音识别不可用');
            }
        };

        recognition.onresult = (event) => {
            hasResult = true;
            const results = Array.from(event.results || []);
            let transcript = '';
            results.forEach((item) => {
                if (item.isFinal && item[0]) {
                    transcript += item[0].transcript;
                }
            });
            if (!transcript && results.length > 0 && results[results.length - 1][0]) {
                transcript = results[results.length - 1][0].transcript;
            }
            evaluateAndRespond(transcript || '');
        };
    };

    updateQuestionView();
    updateProgress(false);
    resetTranscript();
    if (repeatBtn) {
        repeatBtn.addEventListener('click', () => {
            speakCurrentQuestion();
        });
    }

    attachRecognitionHandlers();
    speakCurrentQuestion();

    return {
        destroy() {
            if (destroyed) return;
            destroyed = true;
            clearTimeout(nextQuestionTimer);
            if (recognition) {
                try {
                    recognition.onresult = null;
                    recognition.onend = null;
                    recognition.onerror = null;
                    recognition.stop();
                } catch (err) {
                    // Ignore errors during cleanup
                }
            }
            recognition = null;
        },
    };
}

function createSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        return null;
    }
    try {
        const instance = new SpeechRecognition();
        instance.lang = 'en-US';
        instance.interimResults = false;
        instance.maxAlternatives = 1;
        return instance;
    } catch (err) {
        return null;
    }
}

function evaluateConversationAnswer(transcript, question) {
    const normalisedTranscript = normaliseUtterance(transcript);
    const focusPairs = (question.focus_words || [])
        .map((word) => ({ original: word, normalised: normaliseUtterance(word) }))
        .filter((item) => !!item.normalised);
    const missing = focusPairs.filter((item) => !normalisedTranscript.includes(item.normalised));
    const passed = Boolean(normalisedTranscript) && missing.length === 0;

    const referenceHtml = question.reference_answer
        ? formatMultilineText(question.reference_answer)
        : buildReferenceAnswer(question);

    let adviceHtml;
    if (passed) {
        adviceHtml = question.answer_explanation
            ? formatMultilineText(question.answer_explanation)
            : '你的回答已经涵盖了核心词汇，可以进入下一题。';
    } else {
        adviceHtml = buildFailureAdvice(missing, question);
    }

    return {
        passed,
        referenceHtml,
        adviceHtml,
    };
}

function normaliseUtterance(text) {
    return text
        .toLowerCase()
        .replace(/[^a-z0-9\s]/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
}

function formatMultilineText(text) {
    return escapeHtml(text).replace(/\n/g, '<br>');
}

function buildReferenceAnswer(question) {
    const focusWords = (question.focus_words || []).filter(Boolean);
    if (focusWords.length) {
        const focusHtml = focusWords.map((word) => `<mark>${escapeHtml(word)}</mark>`).join('、');
        const follow = question.follow_up ? `。可进一步说明：${escapeHtml(question.follow_up)}` : '';
        return `理想回答应覆盖关键词：${focusHtml}${follow}`;
    }
    if (question.follow_up) {
        return `可按照以下提示展开：${escapeHtml(question.follow_up)}`;
    }
    return '请围绕问题给出结构清晰的完整作答。';
}

function buildFailureAdvice(missingPairs, question) {
    const missingText = missingPairs.length
        ? `缺少关键词：${missingPairs.map((item) => `<mark>${escapeHtml(item.original)}</mark>`).join('、')}。`
        : '';
    const explanation = question.answer_explanation
        ? formatMultilineText(question.answer_explanation)
        : '请尝试补充提示中的关键词，并按照追问提示展开更多细节。';
    return missingText ? `${missingText}<br>${explanation}` : explanation;
}

function updateConversationProgress(items, activeIndex, completed) {
    items.forEach((item, index) => {
        if (completed) {
            item.classList.remove('active');
            item.classList.add('complete');
            return;
        }
        item.classList.toggle('active', index === activeIndex);
        item.classList.toggle('complete', index < activeIndex);
    });
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
