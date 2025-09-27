checkAuth();

const API_BASE = '/api/ielts-vocab';
const FEATURE_KEY = 'ielts-vocab-game';
const QUESTION_LABELS = {
    definition: '释义对决',
    synonym: '同义词映射',
    usage: '语境填空',
};

const state = {
    config: null,
    difficulty: null,
    mode: null,
    sessionLength: 0,
    sessionActive: false,
    roundsPlayed: 0,
    correctAnswers: 0,
    score: 0,
    streak: 0,
    activeRound: null,
    previousOutcome: null,
    timeline: [],
    timerHandle: null,
    timerRemaining: 0,
    questionResolved: true,
};

const elements = {};
const speech = {
    supported: typeof window !== 'undefined' && 'speechSynthesis' in window,
    voices: [],
    preferredVoice: null,
};

document.addEventListener('DOMContentLoaded', () => {
    cacheElements();
    bindEvents();
    initializeSpeechEngine();
    renderFeedbackPlaceholder('启动 Session 后，AI Navigator 会即时解析你的答案。');
    resetInterface();
    loadConfig();
});

function cacheElements() {
    elements.difficultyChips = document.getElementById('difficultyChips');
    elements.modeChips = document.getElementById('modeChips');
    elements.sessionLengthSelect = document.getElementById('sessionLengthSelect');
    elements.startSessionBtn = document.getElementById('startSessionBtn');
    elements.resetSessionBtn = document.getElementById('resetSessionBtn');
    elements.scoreValue = document.getElementById('scoreValue');
    elements.scoreMeta = document.getElementById('scoreMeta');
    elements.accuracyValue = document.getElementById('accuracyValue');
    elements.streakValue = document.getElementById('streakValue');
    elements.progressValue = document.getElementById('progressValue');
    elements.progressBar = document.getElementById('progressBar');
    elements.questionTypeBadge = document.getElementById('questionTypeBadge');
    elements.timerValue = document.getElementById('timerValue');
    elements.promptText = document.getElementById('promptText');
    elements.wordDetail = document.getElementById('wordDetail');
    elements.wordKeyword = document.getElementById('wordKeyword');
    elements.wordPhonetic = document.getElementById('wordPhonetic');
    elements.wordTranslation = document.getElementById('wordTranslation');
    elements.wordAudioBtn = document.getElementById('wordAudioBtn');
    elements.optionsGrid = document.getElementById('optionsGrid');
    elements.nextButton = document.getElementById('nextButton');
    elements.feedbackPanel = document.getElementById('feedbackPanel');
    elements.aiTip = document.getElementById('aiTip');
    elements.sessionSummary = document.getElementById('sessionSummary');
    elements.timelineList = document.getElementById('timelineList');
}

function bindEvents() {
    elements.startSessionBtn.addEventListener('click', startSession);
    elements.resetSessionBtn.addEventListener('click', () => resetInterface(true));
    if (elements.wordAudioBtn) {
        elements.wordAudioBtn.addEventListener('click', handleWordAudioPlayback);
    }
    elements.nextButton.addEventListener('click', () => {
        if (!state.sessionActive) {
            return;
        }
        elements.nextButton.disabled = true;
        fetchRound();
    });
    elements.sessionLengthSelect.addEventListener('change', event => {
        state.sessionLength = Number(event.target.value) || state.sessionLength;
        updateScoreboard();
    });
}

async function loadConfig() {
    try {
        const response = await fetch(`${API_BASE}/game-config`);
        if (!response.ok) {
            throw new Error(`配置加载失败：${response.status}`);
        }
        const data = await response.json();
        state.config = data;
        state.difficulty = data.defaultDifficulty || (data.difficulties?.[0]?.id ?? null);
        state.mode = data.defaultMode || (data.modes?.[0]?.id ?? null);

        const defaultMeta = getDifficultyMeta(state.difficulty);
        state.sessionLength = defaultMeta?.defaultSession || data.sessionLengths?.[0] || 6;

        renderDifficultyChips();
        renderModeChips();
        populateSessionLengths();
        updateScoreboard();
        updateCoachPanel();
    } catch (error) {
        console.error('Failed to load config', error);
        renderFeedbackPlaceholder('配置加载失败，请稍后重试。');
    }
}

function renderDifficultyChips() {
    if (!elements.difficultyChips || !state.config?.difficulties) {
        return;
    }
    elements.difficultyChips.innerHTML = '';
    state.config.difficulties.forEach(diff => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'chip';
        if (diff.id === state.difficulty) {
            btn.classList.add('active');
        }
        btn.innerHTML = `<strong>${diff.label}</strong><small>${diff.band}</small>`;
        btn.addEventListener('click', () => {
            if (state.difficulty === diff.id) {
                return;
            }
            state.difficulty = diff.id;
            state.previousOutcome = null;
            renderDifficultyChips();
            const recommended = diff.defaultSession || state.sessionLength;
            if (!state.sessionActive) {
                state.sessionLength = recommended;
                populateSessionLengths();
            }
            resetInterface();
            updateCoachPanel();
        });
        elements.difficultyChips.appendChild(btn);
    });
}

function renderModeChips() {
    if (!elements.modeChips || !state.config?.modes) {
        return;
    }
    elements.modeChips.innerHTML = '';
    state.config.modes.forEach(mode => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'mode-chip';
        if (mode.id === state.mode) {
            btn.classList.add('active');
        }
        btn.innerHTML = `<strong>${mode.label}</strong><small>${mode.skillFocus}</small>`;
        btn.addEventListener('click', () => {
            if (state.mode === mode.id) {
                return;
            }
            state.mode = mode.id;
            renderModeChips();
            if (state.sessionActive) {
                renderFeedbackPlaceholder('题型已切换，请点击「下一题」或重新启动 Session。');
            } else {
                updateCoachPanel();
            }
        });
        elements.modeChips.appendChild(btn);
    });
}

function populateSessionLengths() {
    if (!elements.sessionLengthSelect || !state.config?.sessionLengths) {
        return;
    }
    elements.sessionLengthSelect.innerHTML = '';
    const lengths = state.config.sessionLengths;
    if (!lengths.includes(state.sessionLength)) {
        state.sessionLength = lengths[0] || state.sessionLength || 6;
    }
    lengths.forEach(length => {
        const option = document.createElement('option');
        option.value = String(length);
        option.textContent = `${length} 题`;
        if (length === state.sessionLength) {
            option.selected = true;
        }
        elements.sessionLengthSelect.appendChild(option);
    });
}

function resetInterface(showCoach = false) {
    clearTimer();
    state.sessionActive = false;
    state.roundsPlayed = 0;
    state.correctAnswers = 0;
    state.score = 0;
    state.streak = 0;
    state.activeRound = null;
    state.timeline = [];
    state.previousOutcome = null;
    state.questionResolved = true;

    elements.questionTypeBadge.textContent = '等待启动';
    elements.timerValue.textContent = '--';
    elements.promptText.textContent = '准备好进入雅思词汇对战了吗？点击「启动 Session」开始挑战。';
    renderWordReference(null);
    elements.optionsGrid.innerHTML = '';
    const placeholder = document.createElement('div');
    placeholder.className = 'option-card locked';
    const key = document.createElement('span');
    key.className = 'key';
    key.textContent = 'A';
    const text = document.createElement('span');
    text.className = 'text';
    text.textContent = '题目加载后，这里将出现高频 IELTS 词汇相关选项。';
    placeholder.append(key, text);
    elements.optionsGrid.appendChild(placeholder);
    elements.nextButton.disabled = true;

    elements.sessionSummary.classList.remove('active');
    elements.sessionSummary.innerHTML = '';

    renderTimeline();
    updateScoreboard();
    if (showCoach) {
        renderFeedbackPlaceholder('界面已重置，选择难度后再次启动 Session。');
    }
    updateCoachPanel();
}

function startSession() {
    if (!state.config || !state.difficulty || !state.mode) {
        return;
    }
    clearTimer();
    state.sessionLength = Number(elements.sessionLengthSelect.value) || state.sessionLength || 6;
    state.sessionActive = true;
    state.roundsPlayed = 0;
    state.correctAnswers = 0;
    state.score = 0;
    state.streak = 0;
    state.timeline = [];
    state.previousOutcome = null;
    state.questionResolved = true;

    elements.sessionSummary.classList.remove('active');
    elements.sessionSummary.innerHTML = '';

    renderTimeline();
    updateScoreboard();
    renderFeedbackPlaceholder('题目生成中，请稍候...');
    elements.promptText.textContent = '正在唤醒题库，载入你的第一道挑战...';
    elements.optionsGrid.innerHTML = '';
    elements.questionTypeBadge.textContent = `${QUESTION_LABELS[state.mode] || '准备'} · ${getModeMeta(state.mode)?.skillFocus ?? ''}`;
    elements.nextButton.disabled = true;

    if (window.usageTracker) {
        window.usageTracker.track({
            feature: FEATURE_KEY,
            action: 'session_start',
            metadata: {
                difficulty: state.difficulty,
                mode: state.mode,
                length: state.sessionLength,
            },
        });
    }

    fetchRound(true).catch(error => {
        state.sessionActive = false;
        renderFeedbackPlaceholder(`题目加载失败：${error.message}`);
    });
}

async function fetchRound(isSessionStart = false) {
    if (!state.sessionActive) {
        return;
    }
    state.questionResolved = false;
    elements.timerValue.textContent = '--';
    elements.nextButton.disabled = true;
    elements.optionsGrid.classList.add('loading');

    const requestBody = {
        difficulty: state.difficulty,
        mode: state.mode,
    };
    if (!isSessionStart && state.previousOutcome) {
        requestBody.previousOutcome = state.previousOutcome;
    }

    try {
        const response = await fetch(`${API_BASE}/generate-round`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody),
        });
        if (!response.ok) {
            const message = await response.text().catch(() => '');
            throw new Error(message || `服务返回状态码 ${response.status}`);
        }
        const data = await response.json();
        state.activeRound = {
            ...data.round,
            insight: data.insight,
        };
        renderRound();
        updateCoachPanel(data.insight, data.round?.supporting);
        startTimer(data.round?.countdownSeconds ?? 60);
        if (window.usageTracker) {
            window.usageTracker.track({
                feature: FEATURE_KEY,
                action: 'round_generated',
                metadata: {
                    difficulty: state.difficulty,
                    mode: state.mode,
                    questionType: data.round?.questionType,
                },
            });
        }
    } catch (error) {
        console.error('Failed to generate round', error);
        renderFeedbackPlaceholder(`题目加载失败：${error.message}`);
        state.sessionActive = false;
    } finally {
        elements.optionsGrid.classList.remove('loading');
    }
}

function renderRound() {
    if (!state.activeRound) {
        return;
    }
    const { questionType, prompt, options, skillFocus } = state.activeRound;
    elements.questionTypeBadge.textContent = `${QUESTION_LABELS[questionType] || '挑战'} · ${skillFocus ?? ''}`;
    elements.promptText.textContent = prompt;
    renderWordReference(state.activeRound.supporting);
    elements.optionsGrid.innerHTML = '';

    options.forEach((option, index) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'option-card';
        button.dataset.optionId = option.id;

        const key = document.createElement('span');
        key.className = 'key';
        key.textContent = String.fromCharCode(65 + index);

        const text = document.createElement('span');
        text.className = 'text';
        text.textContent = option.label;

        button.append(key, text);
        button.addEventListener('click', () => handleOptionSelect(option.id, button));
        elements.optionsGrid.appendChild(button);
    });
}

function renderWordReference(supporting) {
    if (!elements.wordDetail) {
        return;
    }
    if (!supporting?.keyword) {
        elements.wordDetail.classList.add('hidden');
        if (elements.wordKeyword) {
            elements.wordKeyword.textContent = '—';
        }
        if (elements.wordPhonetic) {
            elements.wordPhonetic.textContent = '';
            elements.wordPhonetic.classList.add('is-hidden');
        }
        if (elements.wordTranslation) {
            elements.wordTranslation.textContent = '';
            elements.wordTranslation.classList.add('is-hidden');
        }
        if (elements.wordAudioBtn) {
            elements.wordAudioBtn.disabled = true;
            elements.wordAudioBtn.removeAttribute('data-word');
            elements.wordAudioBtn.title = speech.supported ? '等待下一题解锁发音' : '当前浏览器不支持语音播放';
        }
        return;
    }

    if (elements.wordKeyword) {
        elements.wordKeyword.textContent = supporting.keyword;
    }
    if (elements.wordPhonetic) {
        const phonetic = supporting.phonetic ? `/${supporting.phonetic}/` : '';
        elements.wordPhonetic.textContent = phonetic;
        elements.wordPhonetic.classList.toggle('is-hidden', !supporting.phonetic);
    }
    if (elements.wordTranslation) {
        elements.wordTranslation.textContent = supporting.translation || '';
        elements.wordTranslation.classList.toggle('is-hidden', !supporting.translation);
    }
    if (elements.wordAudioBtn) {
        const playable = speech.supported && Boolean(supporting.keyword);
        elements.wordAudioBtn.disabled = !playable;
        if (playable) {
            elements.wordAudioBtn.dataset.word = supporting.keyword;
            elements.wordAudioBtn.title = `播放 ${supporting.keyword} 的发音`;
        } else {
            elements.wordAudioBtn.removeAttribute('data-word');
            elements.wordAudioBtn.title = speech.supported ? '当前浏览器支持语音播放，但暂无可播放单词' : '当前浏览器不支持语音播放';
        }
    }

    elements.wordDetail.classList.remove('hidden');
}

function handleOptionSelect(optionId, button) {
    if (state.questionResolved || !state.activeRound) {
        return;
    }
    state.questionResolved = true;
    clearTimer();
    lockOptions();
    gradeRound(optionId);
    button.classList.add('selected');
}

function lockOptions() {
    elements.optionsGrid.querySelectorAll('.option-card').forEach(btn => {
        btn.disabled = true;
        btn.classList.add('locked');
    });
}

async function gradeRound(selectedOptionId) {
    if (!state.activeRound) {
        return;
    }
    try {
        const response = await fetch(`${API_BASE}/verify-answer`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                roundId: state.activeRound.roundId,
                answerPayload: state.activeRound.answerPayload,
                selectedOptionId,
            }),
        });
        if (!response.ok) {
            const message = await response.text().catch(() => '');
            throw new Error(message || `服务返回状态码 ${response.status}`);
        }
        const result = await response.json();
        applyResult(result, selectedOptionId);
        if (window.usageTracker) {
            window.usageTracker.track({
                feature: FEATURE_KEY,
                action: 'answer',
                metadata: {
                    difficulty: state.difficulty,
                    mode: state.mode,
                    questionType: state.activeRound.questionType,
                    outcome: result.outcome,
                },
            });
        }
    } catch (error) {
        console.error('Failed to verify answer', error);
        renderFeedbackPlaceholder(`验证失败：${error.message}`);
        state.sessionActive = false;
    }
}

function applyResult(result, selectedOptionId) {
    if (!result || !state.activeRound) {
        return;
    }
    const { outcome, correctOptionId } = result;
    highlightOptions(correctOptionId, selectedOptionId, outcome);

    state.roundsPlayed += 1;
    if (result.correct) {
        state.correctAnswers += 1;
        state.streak += 1;
        state.score += result.scoreDelta;
    } else {
        state.streak = 0;
        state.score = Math.max(0, state.score + result.scoreDelta);
    }
    state.previousOutcome = outcome;

    updateScoreboard();
    renderFeedback(result);
    pushTimelineEntry(result);

    const sessionComplete = state.roundsPlayed >= state.sessionLength;
    elements.nextButton.disabled = sessionComplete;
    if (sessionComplete) {
        finalizeSession();
    }
}

function highlightOptions(correctId, selectedId, outcome) {
    elements.optionsGrid.querySelectorAll('.option-card').forEach(btn => {
        const optionId = btn.dataset.optionId;
        btn.classList.add('locked');
        btn.disabled = true;
        if (optionId === correctId) {
            btn.classList.add('correct');
        }
        if (selectedId && optionId === selectedId && selectedId !== correctId) {
            btn.classList.add('incorrect');
        }
        if (!selectedId && outcome === 'timeout' && optionId === correctId) {
            btn.classList.add('timeout');
        }
    });
}

function initializeSpeechEngine() {
    if (!speech.supported) {
        if (elements.wordAudioBtn) {
            elements.wordAudioBtn.disabled = true;
            elements.wordAudioBtn.title = '当前浏览器不支持语音播放';
        }
        return;
    }

    const updateVoices = () => {
        speech.voices = window.speechSynthesis.getVoices();
        speech.preferredVoice = (
            speech.voices.find(voice => voice.lang?.toLowerCase().startsWith('en-gb')) ||
            speech.voices.find(voice => voice.lang?.toLowerCase().startsWith('en-us')) ||
            speech.voices.find(voice => voice.lang?.toLowerCase().startsWith('en')) ||
            speech.voices[0] ||
            null
        );
    };

    updateVoices();
    window.speechSynthesis.addEventListener('voiceschanged', updateVoices);
}

function handleWordAudioPlayback() {
    if (!speech.supported || !elements.wordAudioBtn) {
        return;
    }
    const word = elements.wordAudioBtn.dataset.word;
    if (!word) {
        return;
    }

    const utterance = new SpeechSynthesisUtterance(word);
    const voice = speech.preferredVoice || window.speechSynthesis.getVoices().find(v => v.lang?.startsWith('en')) || null;
    if (voice) {
        utterance.voice = voice;
        utterance.lang = voice.lang;
    } else {
        utterance.lang = 'en-US';
    }
    utterance.rate = 0.95;
    utterance.pitch = 1;

    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
}

function renderFeedback(result) {
    if (!elements.feedbackPanel) {
        return;
    }
    const detail = result.detail ?? {};
    const feedbackInfo = result.feedback ?? {};
    const { scoreDelta = 0, outcome, correct } = result;
    const statusLabel = correct ? '✅ 正确' : outcome === 'timeout' ? '⌛ 超时' : '❌ 再接再厉';
    const deltaLabel = scoreDelta >= 0 ? `+${scoreDelta}` : `${scoreDelta}`;
    const synonyms = detail.synonyms?.length ? detail.synonyms.join(' · ') : '—';
    const collocations = detail.collocations?.length ? detail.collocations.join(' / ') : '—';

    const bodyLines = [];
    const descriptors = [];
    if (detail.phonetic) {
        descriptors.push(`/${detail.phonetic}/`);
    }
    if (detail.translation) {
        descriptors.push(detail.translation);
    }
    if (detail.definition) {
        const meta = descriptors.length ? `<span class="word-inline">${descriptors.join(' · ')}</span>` : '';
        const metaSuffix = meta ? ` ${meta}` : '';
        bodyLines.push(`<p><strong>${detail.word}</strong>${metaSuffix} · ${detail.definition}</p>`);
    } else if (detail.word) {
        const inlineMeta = descriptors.length ? ` · ${descriptors.join(' · ')}` : '';
        bodyLines.push(`<p><strong>${detail.word}</strong>${inlineMeta}</p>`);
    } else if (descriptors.length) {
        bodyLines.push(`<p>${descriptors.join(' · ')}</p>`);
    }
    if (detail.example) {
        bodyLines.push(`<p>Example: ${detail.example}</p>`);
    }

    elements.feedbackPanel.innerHTML = `
        <div class="feedback-header">
            <span class="status">${statusLabel}</span>
            <span class="delta">Score Δ ${deltaLabel}</span>
        </div>
        <div class="feedback-body">
            ${bodyLines.join('')}
            <div class="feedback-grid">
                <span class="pill">Synonyms: ${synonyms}</span>
                <span class="pill">Collocations: ${collocations}</span>
                ${detail.usageTip ? `<span class="pill">Usage Tip: ${detail.usageTip}</span>` : ''}
            </div>
            <p>${feedbackInfo.summary ?? ''}</p>
            <p><strong>Next:</strong> ${feedbackInfo.nextStep ?? ''}</p>
            <p><strong>AI Hint:</strong> ${feedbackInfo.microHint ?? ''}</p>
        </div>
    `;
}

function renderFeedbackPlaceholder(message) {
    if (!elements.feedbackPanel) {
        return;
    }
    elements.feedbackPanel.innerHTML = `
        <div class="feedback-header">
            <span class="status">AI Navigator</span>
            <span class="delta">Score Δ --</span>
        </div>
        <div class="feedback-body">
            <p>${message}</p>
            <div class="feedback-grid">
                <span class="pill">Synonyms · Collocations · Usage Tips</span>
            </div>
        </div>
    `;
}

function pushTimelineEntry(result) {
    const entry = {
        word: result.detail?.word || 'Unknown',
        outcome: result.outcome,
        correct: result.correct,
        summary: result.feedback?.summary,
        nextStep: result.feedback?.nextStep,
        mode: state.activeRound?.questionType,
        difficulty: state.difficulty,
        timestamp: new Date(),
    };
    state.timeline.unshift(entry);
    if (state.timeline.length > 12) {
        state.timeline.length = 12;
    }
    renderTimeline();
}

function renderTimeline() {
    if (!elements.timelineList) {
        return;
    }
    elements.timelineList.innerHTML = '';
    if (!state.timeline.length) {
        const item = document.createElement('li');
        item.className = 'timeline-item';
        const title = document.createElement('div');
        title.className = 'title';
        title.innerHTML = '<span>暂未开始</span><span class="status">--</span>';
        const detail = document.createElement('div');
        detail.className = 'detail';
        detail.textContent = '启动 Session 后，这里会记录每一题的表现与复盘要点。';
        item.append(title, detail);
        elements.timelineList.appendChild(item);
        return;
    }

    state.timeline.forEach(entry => {
        const item = document.createElement('li');
        item.className = 'timeline-item';

        const title = document.createElement('div');
        title.className = 'title';
        const word = document.createElement('span');
        word.textContent = `${entry.word} · ${QUESTION_LABELS[entry.mode] || ''}`;
        const status = document.createElement('span');
        status.className = 'status';
        status.textContent = entry.outcome === 'timeout' ? 'TIME' : entry.correct ? 'PASS' : 'RETRY';
        status.style.color = entry.correct
            ? 'var(--success)'
            : entry.outcome === 'timeout'
            ? 'var(--warning)'
            : 'var(--danger)';
        title.append(word, status);

        const detail = document.createElement('div');
        detail.className = 'detail';
        detail.textContent = `${formatTimestamp(entry.timestamp)} · ${entry.summary || '持续留意语境与搭配。'}`;

        const action = document.createElement('div');
        action.className = 'detail';
        action.textContent = entry.nextStep || '';

        item.append(title, detail);
        if (action.textContent) {
            item.append(action);
        }
        elements.timelineList.appendChild(item);
    });
}

function formatTimestamp(date) {
    if (!(date instanceof Date)) {
        return '';
    }
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
}

function updateScoreboard() {
    const difficultyMeta = getDifficultyMeta(state.difficulty);
    const modeMeta = getModeMeta(state.mode);
    elements.scoreValue.textContent = Math.max(0, Math.round(state.score));
    elements.scoreMeta.textContent = `${difficultyMeta?.label ?? ''} · ${modeMeta?.label ?? ''}`;

    const accuracy = state.roundsPlayed === 0 ? 0 : Math.round((state.correctAnswers / state.roundsPlayed) * 100);
    elements.accuracyValue.textContent = `${accuracy}%`;
    elements.streakValue.textContent = state.streak;
    elements.progressValue.textContent = `${state.roundsPlayed}/${state.sessionLength || 0}`;
    updateProgressBar();
}

function updateProgressBar() {
    if (!elements.progressBar) {
        return;
    }
    const total = state.sessionLength || 0;
    const percent = total === 0 ? 0 : Math.min(100, Math.round((state.roundsPlayed / total) * 100));
    elements.progressBar.style.width = `${percent}%`;
}

function updateCoachPanel(insight, supporting) {
    if (!elements.aiTip) {
        return;
    }
    const difficultyMeta = getDifficultyMeta(state.difficulty);
    const lines = [];
    if (insight?.mantra) {
        lines.push(`<div class="mantra">✦ ${insight.mantra}</div>`);
    } else if (difficultyMeta?.description) {
        lines.push(`<div class="mantra">✦ ${difficultyMeta.description}</div>`);
    }

    if (insight?.strategy) {
        lines.push(`<div class="tip-line">策略：${insight.strategy}</div>`);
    } else if (difficultyMeta?.skills?.length) {
        lines.push(`<div class="tip-line">重点：${difficultyMeta.skills.join(' · ')}</div>`);
    }

    if (supporting?.quickTip) {
        lines.push(`<div class="tip-line">提示：${supporting.quickTip}</div>`);
    }

    if (supporting?.translation) {
        lines.push(`<div class="tip-line">中文：${supporting.translation}</div>`);
    }

    if (supporting?.phonetic) {
        lines.push(`<div class="tip-line">音标：/${supporting.phonetic}/</div>`);
    }

    if (supporting?.collocations?.length) {
        lines.push(`<div class="tip-line">搭配：${supporting.collocations.join(' · ')}</div>`);
    }

    elements.aiTip.innerHTML = lines.length
        ? lines.join('')
        : '选择难度后点击「启动 Session」即可开始训练。';
}

function finalizeSession() {
    state.sessionActive = false;
    clearTimer();

    const accuracy = state.roundsPlayed === 0 ? 0 : Math.round((state.correctAnswers / state.roundsPlayed) * 100);
    const difficultyMeta = getDifficultyMeta(state.difficulty);

    elements.sessionSummary.classList.add('active');
    elements.sessionSummary.innerHTML = `
        <h3>Session 完成</h3>
        <div class="summary-grid">
            <div class="box"><strong>总分</strong><span>${Math.round(state.score)}</span></div>
            <div class="box"><strong>正确率</strong><span>${accuracy}%</span></div>
            <div class="box"><strong>完成题数</strong><span>${state.roundsPlayed}</span></div>
            <div class="box"><strong>最长连对</strong><span>${state.streak}</span></div>
        </div>
        <p>${difficultyMeta?.mantras?.[0] || '继续保持节奏，下一轮尝试提升难度或题量。'}</p>
    `;
}

function startTimer(seconds) {
    clearTimer();
    state.timerRemaining = Number(seconds) || 60;
    updateTimerDisplay();
    state.timerHandle = window.setInterval(() => {
        state.timerRemaining -= 1;
        if (state.timerRemaining <= 0) {
            clearTimer();
            updateTimerDisplay();
            if (!state.questionResolved) {
                state.questionResolved = true;
                lockOptions();
                gradeRound(null);
            }
        } else {
            updateTimerDisplay();
        }
    }, 1000);
}

function clearTimer() {
    if (state.timerHandle) {
        window.clearInterval(state.timerHandle);
        state.timerHandle = null;
    }
}

function updateTimerDisplay() {
    elements.timerValue.textContent = `${Math.max(0, state.timerRemaining)}s`;
}

function getDifficultyMeta(id) {
    return state.config?.difficulties?.find(item => item.id === id) || null;
}

function getModeMeta(id) {
    return state.config?.modes?.find(item => item.id === id) || null;
}
