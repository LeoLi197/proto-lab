// frontend/features/ielts-study-system/script.js
// 雅思学习系统前端交互逻辑

checkAuth();

const skillLabels = {
    listening: '听力',
    speaking: '口语',
    reading: '阅读',
    writing: '写作',
};

let practiceData = null;
let currentPracticeSkill = 'listening';
let speakingTimerInterval = null;
const listeningPlaybackState = {
    script: [],
    index: 0,
    isPlaying: false,
    isPaused: false,
    playButton: null,
    activeUtterance: null,
};

document.addEventListener('DOMContentLoaded', () => {
    initialisePage();
});

async function initialisePage() {
    attachEventHandlers();
    await Promise.all([
        loadSkillModules(),
        loadSupportingTools(),
        loadMockTests(),
        loadVocabularyDeck(),
        loadSystemOverview(),
        loadPracticeLab(),
    ]);
}

function attachEventHandlers() {
    document.getElementById('assessmentForm').addEventListener('submit', handlePlanSubmit);
    document.getElementById('progressForm').addEventListener('submit', handleProgressSubmit);
    document.getElementById('vocabStage').addEventListener('change', loadVocabularyDeck);
}

async function handlePlanSubmit(event) {
    event.preventDefault();
    const planBtn = document.getElementById('planBtn');
    const planOutput = document.getElementById('planOutput');

    const payload = buildAssessmentPayload();

    planBtn.disabled = true;
    planBtn.textContent = '生成中...';
    planOutput.style.display = 'block';
    planOutput.innerHTML = '正在生成个性化学习路径，请稍候...';

    try {
        if (window.usageTracker) {
            usageTracker.track({ feature: 'ielts-study-system', action: 'plan-request' });
        }

        const response = await fetch('/api/ielts/assessment', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        if (!response.ok) {
            const message = await response.text();
            throw new Error(message || '生成学习计划失败');
        }

        const data = await response.json();
        renderPlan(data);

        if (window.usageTracker) {
            usageTracker.track({ feature: 'ielts-study-system', action: 'plan-success' });
        }
    } catch (error) {
        console.error(error);
        planOutput.innerHTML = `<span class="error">生成失败：${error.message}</span>`;
    } finally {
        planBtn.disabled = false;
        planBtn.textContent = '生成学习计划';
    }
}

function buildAssessmentPayload() {
    const targetBand = document.getElementById('targetBand').value;
    const weeklyHours = Number(document.getElementById('weeklyHours').value);
    const weeksUntilExam = Number(document.getElementById('weeksUntilExam').value);

    const currentScores = {
        listening: Number(document.getElementById('listeningScore').value),
        speaking: Number(document.getElementById('speakingScore').value),
        reading: Number(document.getElementById('readingScore').value),
        writing: Number(document.getElementById('writingScore').value),
    };

    const preferred = Array.from(document.querySelectorAll('.checkbox-row input:checked')).map((el) => el.value);

    const payload = {
        target_band: targetBand,
        weekly_study_hours: weeklyHours,
        weeks_until_exam: weeksUntilExam,
        current_scores: currentScores,
    };

    if (preferred.length > 0) {
        payload.preferred_focus = preferred;
    }

    return payload;
}

function renderPlan(plan) {
    const container = document.getElementById('planOutput');
    container.style.display = 'block';

    const priorityChips = plan.priority_skills
        .map((skill) => `<span class="chip">${skillLabels[skill] || skill}</span>`)
        .join('');

    const phasesHtml = plan.phase_plan
        .map((phase) => `
            <div class="phase-card">
                <div class="phase-header">
                    <strong>${phase.label}</strong>
                    <span>${phase.duration_weeks} 周｜${phase.intensity}</span>
                </div>
                <p class="phase-summary">${phase.summary}</p>
                <div class="phase-section">
                    <h4>阶段里程碑</h4>
                    <ul>${phase.milestones.map((item) => `<li>${item}</li>`).join('')}</ul>
                </div>
                <div class="phase-section">
                    <h4>周学习结构</h4>
                    ${renderWeeklySchedule(phase.weekly_schedule)}
                </div>
                <div class="phase-section">
                    <h4>达标指标</h4>
                    <ul>
                        ${Object.entries(phase.progress_metrics)
                            .map(([skill, text]) => `<li><strong>${skillLabels[skill] || skill}</strong>：${text}</li>`)
                            .join('')}
                    </ul>
                </div>
                <div class="phase-section">
                    <h4>阶段转入条件</h4>
                    <p>${phase.checkpoint}</p>
                </div>
            </div>
        `)
        .join('');

    const dailyTemplateHtml = Object.entries(plan.daily_template)
        .map(
            ([period, tasks]) => `
            <div class="daily-block">
                <h4>${period.toUpperCase()}</h4>
                <ul>${tasks.map((task) => `<li>${task}</li>`).join('')}</ul>
            </div>
        `,
        )
        .join('');

    container.innerHTML = `
        <div class="plan-meta">
            <div>
                <span class="meta-title">目标分数</span>
                <strong>${plan.target_band}</strong>
            </div>
            <div>
                <span class="meta-title">当前均分</span>
                <strong>${plan.current_average}</strong>
            </div>
            <div>
                <span class="meta-title">分差</span>
                <strong>${plan.overall_gap.toFixed(2)}</strong>
            </div>
            <div>
                <span class="meta-title">弱项优先</span>
                <div class="chip-group">${priorityChips}</div>
            </div>
        </div>
        <div class="plan-section">
            <h3>阶段化学习路径</h3>
            <div class="phase-grid">${phasesHtml}</div>
        </div>
        <div class="plan-section">
            <h3>每日节奏示例</h3>
            <div class="daily-template">${dailyTemplateHtml}</div>
        </div>
        <div class="plan-section">
            <h3>官方建议</h3>
            ${renderRecommendation(plan.recommendations)}
        </div>
    `;
}

function renderWeeklySchedule(schedule) {
    return `
        <ul class="schedule-list">
            ${schedule
                .map(
                    (item) => `
                        <li>
                            <div class="schedule-title">${skillLabels[item.skill] || item.skill}｜${item.hours} 小时</div>
                            <ul>${item.focus.map((focus) => `<li>${focus}</li>`).join('')}</ul>
                        </li>
                    `,
                )
                .join('')}
        </ul>
    `;
}

function renderRecommendation(recommendation) {
    return `
        <ul class="recommendation-list">
            <li><strong>分数策略：</strong>${recommendation.score_profile}</li>
            <li><strong>听力重点：</strong>${recommendation.listening_focus}</li>
            <li><strong>口语重点：</strong>${recommendation.speaking_focus}</li>
            <li><strong>阅读重点：</strong>${recommendation.reading_focus}</li>
            <li><strong>写作重点：</strong>${recommendation.writing_focus}</li>
            <li><strong>模考节奏：</strong>${recommendation.mock_test_frequency}</li>
            <li><strong>AI 反馈关注：</strong>${recommendation.ai_feedback_expectation}</li>
        </ul>
    `;
}

async function loadSkillModules() {
    try {
        const response = await fetch('/api/ielts/modules');
        if (!response.ok) throw new Error('无法获取模块信息');
        const data = await response.json();
        const grid = document.getElementById('moduleGrid');
        grid.innerHTML = Object.values(data)
            .map((module) => `
                <div class="module-card">
                    <h3>${module.title}</h3>
                    <div class="module-section">
                        <h4>核心能力</h4>
                        <ul>${module.core_features.map((item) => `<li>${item}</li>`).join('')}</ul>
                    </div>
                    <div class="module-section">
                        <h4>训练模式</h4>
                        <ul>${module.training_modes.map((item) => `<li>${item}</li>`).join('')}</ul>
                    </div>
                    <div class="module-section">
                        <h4>数据追踪</h4>
                        <ul>${module.data_points.map((item) => `<li>${item}</li>`).join('')}</ul>
                    </div>
                </div>
            `)
            .join('');
    } catch (error) {
        console.error(error);
        document.getElementById('moduleGrid').innerHTML = '<p class="error">模块信息加载失败</p>';
    }
}

async function loadSupportingTools() {
    try {
        const response = await fetch('/api/ielts/supporting-tools');
        if (!response.ok) throw new Error('无法获取支撑工具信息');
        const data = await response.json();
        const container = document.getElementById('supportingTools');
        container.innerHTML = data.tools
            .map((tool) => `
                <div class="support-card">
                    <h3>${tool.name}</h3>
                    <p>${tool.description}</p>
                    <ul>${tool.capabilities.map((cap) => `<li>${cap}</li>`).join('')}</ul>
                </div>
            `)
            .join('');
    } catch (error) {
        console.error(error);
        document.getElementById('supportingTools').innerHTML = '<p class="error">支撑系统加载失败</p>';
    }
}

async function loadMockTests() {
    try {
        const response = await fetch('/api/ielts/mock-tests');
        if (!response.ok) throw new Error('无法获取模考信息');
        const data = await response.json();
        const container = document.getElementById('mockTests');
        container.innerHTML = data.mock_tests
            .map((test) => `
                <div class="mock-card">
                    <div class="mock-header">
                        <strong>${test.title}</strong>
                        <span>${test.duration_minutes} 分钟</span>
                    </div>
                    <p>${test.score_focus}</p>
                    <h4>适用阶段</h4>
                    <p>${test.recommended_stage.map((stage) => stage.toUpperCase()).join(' / ')}</p>
                    <h4>报告内容</h4>
                    <ul>${test.report_contents.map((item) => `<li>${item}</li>`).join('')}</ul>
                </div>
            `)
            .join('');
    } catch (error) {
        console.error(error);
        document.getElementById('mockTests').innerHTML = '<p class="error">模考信息加载失败</p>';
    }
}

async function loadVocabularyDeck() {
    const stage = document.getElementById('vocabStage').value;
    try {
        const response = await fetch(`/api/ielts/vocabulary?stage=${stage}`);
        if (!response.ok) throw new Error('无法获取词汇手册');
        const data = await response.json();
        const deck = data.deck;
        document.getElementById('vocabDeck').innerHTML = `
            <div class="vocab-meta">
                <div><span class="meta-title">词汇等级</span><strong>${deck.level}</strong></div>
                <div><span class="meta-title">复习策略</span><strong>${deck.spacing_strategy}</strong></div>
                <div><span class="meta-title">每日词量</span><strong>${deck.bundle_size} 词</strong></div>
            </div>
            <h4>推荐活动</h4>
            <ul>${deck.activities.map((item) => `<li>${item}</li>`).join('')}</ul>
        `;
    } catch (error) {
        console.error(error);
        document.getElementById('vocabDeck').innerHTML = '<p class="error">词汇手册加载失败</p>';
    }
}

async function loadSystemOverview() {
    try {
        const response = await fetch('/api/ielts/system-overview');
        if (!response.ok) throw new Error('无法获取系统信息');
        const data = await response.json();
        renderSystemOverview(data);
    } catch (error) {
        console.error(error);
        document.getElementById('systemOverview').innerHTML = '<p class="error">系统信息加载失败</p>';
    }
}

function renderSystemOverview(data) {
    const integrations = Object.entries(data.integrations)
        .map(
            ([key, item]) => `
            <div class="integration-card">
                <h4>${key.toUpperCase()}</h4>
                <p>${item.purpose}</p>
                <p class="integration-boundary">接入边界：${item.service_boundary}</p>
                <ul>${item.data_output.map((out) => `<li>${out}</li>`).join('')}</ul>
            </div>
        `,
        )
        .join('');

    document.getElementById('systemOverview').innerHTML = `
        <div class="integration-grid">${integrations}</div>
        <div class="security-block">
            <h4>数据安全 & 隐私</h4>
            <div class="security-columns">
                <div>
                    <h5>存储策略</h5>
                    <ul>${data.data_safeguards.storage.map((item) => `<li>${item}</li>`).join('')}</ul>
                </div>
                <div>
                    <h5>隐私保护</h5>
                    <ul>${data.data_safeguards.privacy.map((item) => `<li>${item}</li>`).join('')}</ul>
                </div>
            </div>
        </div>
    `;
}

async function handleProgressSubmit(event) {
    event.preventDefault();
    const reviewBtn = document.getElementById('reviewBtn');
    const output = document.getElementById('progressOutput');

    const payload = {
        baseline_scores: {
            listening: Number(document.getElementById('baselineListening').value),
            speaking: Number(document.getElementById('baselineSpeaking').value),
            reading: Number(document.getElementById('baselineReading').value),
            writing: Number(document.getElementById('baselineWriting').value),
        },
        latest_scores: {
            listening: Number(document.getElementById('latestListening').value),
            speaking: Number(document.getElementById('latestSpeaking').value),
            reading: Number(document.getElementById('latestReading').value),
            writing: Number(document.getElementById('latestWriting').value),
        },
        weeks_elapsed: Number(document.getElementById('weeksElapsed').value),
        total_logged_hours: Number(document.getElementById('loggedHours').value),
        completed_mock_tests: Number(document.getElementById('mockCompleted').value),
    };

    reviewBtn.disabled = true;
    reviewBtn.textContent = '分析中...';
    output.style.display = 'block';
    output.innerHTML = '正在分析学习进度，请稍候...';

    try {
        const response = await fetch('/api/ielts/progress/review', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        if (!response.ok) {
            const message = await response.text();
            throw new Error(message || '生成复盘建议失败');
        }

        const data = await response.json();
        renderProgressReview(data);
    } catch (error) {
        console.error(error);
        output.innerHTML = `<span class="error">复盘失败：${error.message}</span>`;
    } finally {
        reviewBtn.disabled = false;
        reviewBtn.textContent = '生成复盘建议';
    }
}

function renderProgressReview(data) {
    const output = document.getElementById('progressOutput');

    const improvementList = Object.entries(data.score_improvements)
        .map(([skill, delta]) => `<li>${skillLabels[skill] || skill}：${delta >= 0 ? '+' : ''}${delta}</li>`)
        .join('');

    output.innerHTML = `
        <div class="plan-meta">
            <div>
                <span class="meta-title">完成周数</span>
                <strong>${data.weeks_elapsed}</strong>
            </div>
            <div>
                <span class="meta-title">累计时长</span>
                <strong>${data.total_logged_hours} h</strong>
            </div>
            <div>
                <span class="meta-title">当前弱项</span>
                <strong>${skillLabels[data.weakest_skill] || data.weakest_skill}</strong>
            </div>
            <div>
                <span class="meta-title">建议阶段</span>
                <strong>${data.suggested_next_stage.toUpperCase()}</strong>
            </div>
        </div>
        <div class="plan-section">
            <h3>分数变化</h3>
            <ul>${improvementList}</ul>
        </div>
        <div class="plan-section">
            <h3>下一步重点</h3>
            <p>优先关注：${data.focus_recommendations
                .map((skill) => skillLabels[skill] || skill)
                .join('、')}</p>
            <ul>${data.next_actions.map((item) => `<li>${item}</li>`).join('')}</ul>
        </div>
        <div class="plan-section">
            <h3>模考建议</h3>
            <p>已完成：${data.mock_test_suggestion.completed} 次</p>
            <p>${data.mock_test_suggestion.next}</p>
        </div>
    `;
}


async function loadPracticeLab() {
    const container = document.getElementById('practiceContent');
    if (!container) {
        return;
    }

    container.innerHTML = '<p class="practice-note">正在加载互动练习，请稍候...</p>';

    try {
        const response = await fetch('/api/ielts/interactive/practice');
        if (!response.ok) throw new Error('无法获取互动练习内容');
        practiceData = await response.json();
        setupPracticeTabs();
        renderPracticeView(currentPracticeSkill);
    } catch (error) {
        console.error(error);
        container.innerHTML = `<p class="error">互动练习加载失败：${error.message}</p>`;
    }
}


function setupPracticeTabs() {
    const tabs = document.querySelectorAll('.practice-tab');
    tabs.forEach((tab) => {
        tab.addEventListener('click', () => {
            if (tab.classList.contains('active')) {
                return;
            }
            tabs.forEach((btn) => btn.classList.remove('active'));
            tab.classList.add('active');
            currentPracticeSkill = tab.dataset.skill;
            renderPracticeView(currentPracticeSkill);
        });
    });
}


function renderPracticeView(skill) {
    const container = document.getElementById('practiceContent');
    if (!container) {
        return;
    }
    if (skill !== 'listening') {
        stopListeningPlayback(true);
    }
    if (!practiceData) {
        container.innerHTML = '<p class="practice-note">正在准备练习数据...</p>';
        return;
    }

    const data = practiceData[skill];
    if (!data) {
        container.innerHTML = '<p class="error">该练习暂未上线，稍后再试。</p>';
        return;
    }

    switch (skill) {
        case 'listening':
            renderListeningPractice(data);
            break;
        case 'reading':
            renderReadingPractice(data);
            break;
        case 'vocabulary':
            renderVocabularyPractice(data);
            break;
        case 'writing':
            renderWritingPractice(data);
            break;
        case 'speaking':
            renderSpeakingPractice(data);
            break;
        default:
            container.innerHTML = '<p class="error">暂不支持的练习类型。</p>';
    }
}


function renderListeningPractice(data) {
    stopListeningPlayback();
    const container = document.getElementById('practiceContent');
    if (!container) {
        return;
    }

    const transcript = (data.audio_script || [])
        .map(
            (line) => `
            <div class="transcript-line">
                <span class="transcript-speaker">${line.speaker}</span>
                <span>${line.text}</span>
            </div>
        `,
        )
        .join('');

    const keyPhrases = (data.key_phrases || [])
        .map((item) => `
            <span class="key-phrase-pill">
                <strong>${item.phrase}</strong>
                ${item.note ? `<span class="key-phrase-note">${item.note}</span>` : ''}
            </span>
        `)
        .join('');

    const keyPhraseSection = keyPhrases
        ? `
            <div class="practice-section key-phrase-section">
                <h4>场景关键词</h4>
                <div class="key-phrase-list">${keyPhrases}</div>
            </div>
        `
        : '';

    const transcriptSection = transcript
        ? `
            <div class="transcript-toggle">
                <button type="button" id="toggleTranscriptBtn">显示原文</button>
            </div>
            <div class="transcript-box collapsed" id="listeningTranscriptBox">${transcript}</div>
        `
        : '';

    const durationLabel = data.audio_duration_seconds
        ? `<span class="audio-duration">约 ${Math.round(data.audio_duration_seconds)} 秒</span>`
        : '';

    const audioElement = data.audio_url
        ? `<audio controls preload="metadata" src="${data.audio_url}" class="listening-audio"></audio>`
        : '';

    const audioNote = data.audio_url
        ? '<p class="practice-note audio-note">如需逐句精听，可重复播放或使用下方 AI 语音播报功能。</p>'
        : '<p class="practice-note audio-note">当前提供浏览器语音合成播报，如无声音请确认浏览器支持 SpeechSynthesis。</p>';

    container.innerHTML = `
        <div class="practice-card listening-card">
            <div class="listening-header">
                <h3>${data.title}</h3>
                <p class="practice-note">${data.description}</p>
                ${data.context ? `<p class="practice-note">练习提示：${data.context}</p>` : ''}
                ${data.audio_summary ? `<p class="practice-note">${data.audio_summary}</p>` : ''}
            </div>
            <div class="listening-audio-box">
                <div class="audio-box-header">
                    <h4>音频播放</h4>
                    ${durationLabel}
                </div>
                ${audioElement}
                <div class="audio-button-group">
                    <button type="button" id="listeningPlayBtn">播放对话</button>
                    <button type="button" id="listeningStopBtn">停止播报</button>
                </div>
                ${audioNote}
            </div>
            ${keyPhraseSection}
            ${transcriptSection}
            <form id="listeningPracticeForm">
                ${buildQuestionHtml(data)}
                <div class="practice-actions">
                    <button type="submit">提交答案</button>
                </div>
            </form>
            <div id="listeningResult" class="result-box" style="display:none;"></div>
        </div>
    `;

    setupListeningPlayback(data.audio_script || []);
    setupTranscriptToggle();

    const form = document.getElementById('listeningPracticeForm');
    form.addEventListener('submit', (event) =>
        handleMultipleChoiceSubmit(event, data, '/api/ielts/interactive/listening/evaluate', 'listeningResult'),
    );
}


function setupTranscriptToggle() {
    const toggleBtn = document.getElementById('toggleTranscriptBtn');
    const transcriptBox = document.getElementById('listeningTranscriptBox');
    if (!toggleBtn || !transcriptBox) {
        return;
    }
    toggleBtn.addEventListener('click', () => {
        const isCollapsed = transcriptBox.classList.toggle('collapsed');
        toggleBtn.textContent = isCollapsed ? '显示原文' : '隐藏原文';
    });
}


function setupListeningPlayback(script) {
    const playBtn = document.getElementById('listeningPlayBtn');
    const stopBtn = document.getElementById('listeningStopBtn');
    listeningPlaybackState.playButton = playBtn || null;

    if (!playBtn) {
        return;
    }

    if (!('speechSynthesis' in window)) {
        playBtn.disabled = true;
        playBtn.textContent = '浏览器不支持语音播报';
        if (stopBtn) {
            stopBtn.disabled = true;
            stopBtn.classList.add('disabled');
        }
        return;
    }

    playBtn.disabled = false;
    playBtn.textContent = '播放对话';
    playBtn.addEventListener('click', () => handleListeningPlayClick(script));

    if (stopBtn) {
        stopBtn.disabled = false;
        stopBtn.classList.remove('disabled');
        stopBtn.addEventListener('click', () => {
            stopListeningPlayback();
            updateListeningPlayButton();
        });
    }

    updateListeningPlayButton();
}


function handleListeningPlayClick(script) {
    if (!('speechSynthesis' in window)) {
        return;
    }

    if (!listeningPlaybackState.isPlaying) {
        startListeningPlayback(script);
    } else if (listeningPlaybackState.isPaused) {
        window.speechSynthesis.resume();
        listeningPlaybackState.isPaused = false;
    } else {
        window.speechSynthesis.pause();
        listeningPlaybackState.isPaused = true;
    }
    updateListeningPlayButton();
}


function startListeningPlayback(script) {
    if (!('speechSynthesis' in window)) {
        return;
    }

    const sanitized = (script || [])
        .filter((line) => line && line.text)
        .map((line) => ({
            speaker: line.speaker || 'Speaker',
            text: String(line.text).replace(/\s+/g, ' ').trim(),
        }));

    if (!sanitized.length) {
        return;
    }

    if (listeningPlaybackState.isPlaying) {
        window.speechSynthesis.cancel();
    }

    listeningPlaybackState.script = sanitized;
    listeningPlaybackState.index = 0;
    listeningPlaybackState.isPlaying = true;
    listeningPlaybackState.isPaused = false;
    speakNextListeningLine();
}


function speakNextListeningLine() {
    if (!('speechSynthesis' in window)) {
        return;
    }
    if (!listeningPlaybackState.isPlaying || listeningPlaybackState.isPaused) {
        return;
    }

    const currentLine = listeningPlaybackState.script[listeningPlaybackState.index];
    if (!currentLine) {
        stopListeningPlayback();
        return;
    }

    const utterance = new SpeechSynthesisUtterance(`${currentLine.speaker} says: ${currentLine.text}`);
    utterance.rate = 0.95;
    utterance.pitch = 1;
    utterance.onend = () => {
        listeningPlaybackState.activeUtterance = null;
        if (!listeningPlaybackState.isPlaying) {
            return;
        }
        listeningPlaybackState.index += 1;
        if (listeningPlaybackState.index >= listeningPlaybackState.script.length) {
            stopListeningPlayback();
        } else {
            speakNextListeningLine();
        }
    };
    utterance.onerror = () => {
        listeningPlaybackState.activeUtterance = null;
        stopListeningPlayback();
    };

    listeningPlaybackState.activeUtterance = utterance;
    window.speechSynthesis.speak(utterance);
    updateListeningPlayButton();
}


function stopListeningPlayback(clearButton = false) {
    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
    }
    listeningPlaybackState.script = [];
    listeningPlaybackState.index = 0;
    listeningPlaybackState.isPlaying = false;
    listeningPlaybackState.isPaused = false;
    listeningPlaybackState.activeUtterance = null;
    if (listeningPlaybackState.playButton) {
        listeningPlaybackState.playButton.disabled = false;
        listeningPlaybackState.playButton.textContent = '播放对话';
        if (clearButton) {
            listeningPlaybackState.playButton = null;
        }
    } else if (clearButton) {
        listeningPlaybackState.playButton = null;
    }
}


function updateListeningPlayButton() {
    const btn = listeningPlaybackState.playButton;
    if (!btn) {
        return;
    }
    if (!('speechSynthesis' in window)) {
        btn.disabled = true;
        btn.textContent = '浏览器不支持语音播报';
        return;
    }

    btn.disabled = false;
    if (!listeningPlaybackState.isPlaying) {
        btn.textContent = '播放对话';
    } else if (listeningPlaybackState.isPaused) {
        btn.textContent = '继续播报';
    } else {
        btn.textContent = '暂停播报';
    }
}


function renderReadingPractice(data) {
    const container = document.getElementById('practiceContent');
    const passage = (data.passage || [])
        .map((paragraph) => `<p>${paragraph}</p>`)
        .join('');

    container.innerHTML = `
        <div class="practice-card">
            <div>
                <h3>${data.title}</h3>
                <p class="practice-note">${data.description}</p>
            </div>
            <div class="reading-passage">${passage}</div>
            <form id="readingPracticeForm">
                ${buildQuestionHtml(data)}
                <div class="practice-actions">
                    <button type="submit">提交答案</button>
                </div>
            </form>
            <div id="readingResult" class="result-box" style="display:none;"></div>
        </div>
    `;

    document.getElementById('readingPracticeForm').addEventListener('submit', (event) =>
        handleMultipleChoiceSubmit(event, data, '/api/ielts/interactive/reading/evaluate', 'readingResult'),
    );
}


function renderVocabularyPractice(data) {
    const container = document.getElementById('practiceContent');
    container.innerHTML = `
        <div class="practice-card">
            <div>
                <h3>${data.title}</h3>
                <p class="practice-note">${data.description}</p>
            </div>
            <form id="vocabularyPracticeForm">
                ${buildQuestionHtml(data)}
                <div class="practice-actions">
                    <button type="submit">检查答案</button>
                </div>
            </form>
            <div id="vocabularyResult" class="result-box" style="display:none;"></div>
        </div>
    `;

    document.getElementById('vocabularyPracticeForm').addEventListener('submit', (event) =>
        handleMultipleChoiceSubmit(event, data, '/api/ielts/interactive/vocabulary/evaluate', 'vocabularyResult'),
    );
}


function renderWritingPractice(data) {
    const container = document.getElementById('practiceContent');
    const brainstorm = (data.brainstorm_points || [])
        .map((item) => `<li>${item}</li>`)
        .join('');
    const structure = (data.structure || [])
        .map((item) => `<li>${item}</li>`)
        .join('');
    const checklist = (data.checklist || [])
        .map((item) => `<li>${item}</li>`)
        .join('');
    const phrases = (data.useful_phrases || [])
        .map((item) => `<li>${item}</li>`)
        .join('');

    container.innerHTML = `
        <div class="practice-card">
            <div>
                <h3>${data.task_type || 'Task 2'} 写作训练</h3>
                <p><strong>题目：</strong>${data.question}</p>
                <p class="practice-note">${data.background || ''}</p>
            </div>
            <div class="practice-grid">
                <div class="practice-section">
                    <h4>思路提示</h4>
                    <ul class="tips-list">${brainstorm}</ul>
                </div>
                <div class="practice-section">
                    <h4>段落结构</h4>
                    <ul class="tips-list">${structure}</ul>
                </div>
                <div class="practice-section">
                    <h4>Checklist</h4>
                    <ul class="tips-list">${checklist}</ul>
                </div>
            </div>
            <form id="writingPracticeForm" class="writing-form">
                <label for="writingResponse">在下方输入你的英文回答：</label>
                <textarea id="writingResponse" rows="8" placeholder="建议 250 词以上，完成后点击获取反馈"></textarea>
                <div class="practice-actions">
                    <button type="submit">获取写作反馈</button>
                </div>
            </form>
            <div id="writingFeedback" class="result-box" style="display:none;"></div>
            <div class="practice-section">
                <h4>高分表达</h4>
                <ul class="tips-list">${phrases}</ul>
                <p class="practice-note">${(data.tips || []).join('，')}</p>
            </div>
        </div>
    `;

    document.getElementById('writingPracticeForm').addEventListener('submit', handleWritingFeedback);
}


function renderSpeakingPractice(data) {
    const container = document.getElementById('practiceContent');
    const part1 = (data.part1?.questions || [])
        .map((item) => `<li>${item}</li>`)
        .join('');
    const starters = (data.part1?.sample_sentence_starters || [])
        .map((item) => `<li>${item}</li>`)
        .join('');
    const part2Points = (data.part2?.bullet_points || [])
        .map((item) => `<li>${item}</li>`)
        .join('');
    const part3Questions = (data.part3?.questions || [])
        .map((item) => `<li>${item}</li>`)
        .join('');
    const part3Ideas = (data.part3?.idea_bank || [])
        .map((item) => `<li>${item}</li>`)
        .join('');

    const prepSeconds = data.part2?.prep_seconds || 60;
    const speakSeconds = data.part2?.speaking_seconds || 120;

    container.innerHTML = `
        <div class="practice-card">
            <div>
                <h3>${data.title}</h3>
                <p class="practice-note">${data.part1?.description || ''}</p>
            </div>
            <div class="practice-grid">
                <div class="practice-section">
                    <h4>Part 1 热身</h4>
                    <ul class="tips-list">${part1}</ul>
                    <p class="practice-note">开头可以参考：</p>
                    <ul class="tips-list">${starters}</ul>
                </div>
                <div class="practice-section">
                    <h4>Part 2 话题卡</h4>
                    <p>${data.part2?.task || ''}</p>
                    <ul class="tips-list">${part2Points}</ul>
                    <div class="timer-row">
                        <button type="button" class="timer-btn" data-duration="${prepSeconds}" data-target="prepTimer">准备计时 (${prepSeconds}s)</button>
                        <div class="timer-display" id="prepTimer">${formatSeconds(prepSeconds)}</div>
                    </div>
                    <div class="timer-row">
                        <button type="button" class="timer-btn" data-duration="${speakSeconds}" data-target="speakTimer">答题计时 (${speakSeconds}s)</button>
                        <div class="timer-display" id="speakTimer">${formatSeconds(speakSeconds)}</div>
                    </div>
                    <p class="practice-note">语言提示：${(data.part2?.language_tips || []).join('；')}</p>
                    <p class="practice-note">结构示例：${(data.part2?.model_outline || []).join(' → ')}</p>
                </div>
                <div class="practice-section">
                    <h4>Part 3 深度提问</h4>
                    <ul class="tips-list">${part3Questions}</ul>
                    <p class="practice-note">思路参考：</p>
                    <ul class="tips-list">${part3Ideas}</ul>
                </div>
            </div>
            <form id="speakingPracticeForm" class="writing-form">
                <label for="speakingTranscript">练习后请记录要点或台词，系统将给出改进建议：</label>
                <textarea id="speakingTranscript" rows="6" placeholder="可粘贴自己的口语稿或要点，便于生成反馈"></textarea>
                <div class="practice-actions">
                    <button type="submit">获取口语反馈</button>
                </div>
            </form>
            <div id="speakingFeedback" class="result-box" style="display:none;"></div>
        </div>
    `;

    container.querySelectorAll('.timer-btn').forEach((button) => {
        button.addEventListener('click', () => {
            const duration = Number(button.dataset.duration);
            const target = document.getElementById(button.dataset.target);
            startSpeakingTimer(duration, target);
        });
    });

    document.getElementById('speakingPracticeForm').addEventListener('submit', handleSpeakingFeedback);
}


function buildQuestionHtml(practice) {
    return (practice.questions || [])
        .map((question, index) => {
            const options = (question.options || [])
                .map(
                    (option, optionIdx) => `
                    <label class="option-row">
                        <input type="radio" name="${practice.id}-${question.id}" value="${option.key}" ${optionIdx === 0 ? 'required' : ''}>
                        <span>${option.key}. ${option.text}</span>
                    </label>
                `,
                )
                .join('');

            return `
                <div class="question-block">
                    <h4>${index + 1}. ${question.question}</h4>
                    ${options}
                </div>
            `;
        })
        .join('');
}


async function handleMultipleChoiceSubmit(event, practice, endpoint, resultId) {
    event.preventDefault();
    const resultBox = document.getElementById(resultId);
    resultBox.style.display = 'block';

    const answers = (practice.questions || []).map((question) => {
        const selector = `input[name="${practice.id}-${question.id}"]:checked`;
        const selected = event.target.querySelector(selector);
        return { question_id: question.id, answer: selected ? selected.value : '' };
    });

    if (answers.some((item) => !item.answer)) {
        resultBox.innerHTML = '<span class="error">请完成所有题目后再提交。</span>';
        return;
    }

    resultBox.innerHTML = '正在评估答案...';

    try {
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ answers }),
        });
        if (!response.ok) {
            const message = await response.text();
            throw new Error(message || '评估失败');
        }
        const data = await response.json();
        renderMultipleChoiceResult(data, resultBox, practice);
    } catch (error) {
        console.error(error);
        resultBox.innerHTML = `<span class="error">${error.message}</span>`;
    }
}


function renderMultipleChoiceResult(result, container, practice) {
    const breakdown = (result.breakdown || [])
        .map((item) => `
            <li class="${item.correct ? 'correct' : 'incorrect'}">
                <strong>${item.question}</strong><br>
                ${item.correct ? '回答正确！' : `正确答案：${item.correct_answer}`}
                ${item.explanation ? `<div class="practice-note">${item.explanation}</div>` : ''}
            </li>
        `)
        .join('');

    const tips = (result.tips || []).map((tip) => `<li>${tip}</li>`).join('');
    const nextSteps = (result.next_steps || []).map((step) => `<li>${step}</li>`).join('');

    const aiBlock = practice && practice.id
        ? `
            <div class="ai-coach-block">
                <button type="button" class="ai-coach-btn" data-practice="${practice.id}" data-skill="${result.skill}">
                    生成 AI 讲解（Gemini 2.5 Flash）
                </button>
                <div class="ai-coach-output" id="${practice.id}-ai-feedback" style="display:none;"></div>
            </div>
        `
        : '';

    container.innerHTML = `
        <div class="result-summary">得分：${result.score}/${result.total}（${result.percentage}%）</div>
        <ul class="breakdown-list">${breakdown}</ul>
        ${tips ? `<div class="practice-section"><h4>技巧提示</h4><ul class="tips-list">${tips}</ul></div>` : ''}
        ${nextSteps ? `<div class="practice-section"><h4>下一步建议</h4><ul class="tips-list">${nextSteps}</ul></div>` : ''}
        ${aiBlock}
    `;

    setupAiCoachButton(result, practice, container);
}


function setupAiCoachButton(result, practice, container) {
    if (!practice || !practice.id) {
        return;
    }
    const button = container.querySelector(`.ai-coach-btn[data-practice="${practice.id}"]`);
    const output = container.querySelector(`#${practice.id}-ai-feedback`);
    if (!button || !output) {
        return;
    }
    button.addEventListener('click', () => handleAiCoachRequest(result, practice, output, button));
}


async function handleAiCoachRequest(result, practice, output, button) {
    if (button.disabled) {
        return;
    }

    output.style.display = 'block';
    output.innerHTML = 'Gemini 正在生成解析，请稍候...';
    button.disabled = true;

    try {
        const prompt = buildAiCoachPrompt(result, practice);
        const response = await fetch('/api/ai-proxy', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                provider: 'gemini',
                model: 'gemini-2.5-flash',
                prompt,
                system: 'You are a supportive IELTS coach. Respond in Chinese using concise Markdown headings and bullet points.',
            }),
        });

        if (!response.ok) {
            const message = await response.text();
            throw new Error(message || 'AI 服务暂不可用');
        }

        const data = await response.json();
        const text = data?.response ? data.response.trim() : '';

        if (!text) {
            output.innerHTML = '<span class="error">AI 未返回内容，请稍后再试。</span>';
        } else {
            output.innerHTML = formatAiCoachResponse(text);
        }

        if (window.usageTracker && data) {
            usageTracker.recordUsage(
                'ielts-study-system',
                data.provider || 'gemini',
                data.model || 'gemini-2.5-flash',
                data.inputTokens || 0,
                data.outputTokens || 0,
            );
        }
    } catch (error) {
        console.error(error);
        output.innerHTML = `<span class="error">AI 解析失败：${error.message}</span>`;
    } finally {
        button.disabled = false;
    }
}


function buildAiCoachPrompt(result, practice) {
    const skillName = skillLabels[result.skill] || result.skill;
    const correctCount = (result.breakdown || []).filter((item) => item.correct).length;
    const incorrectItems = (result.breakdown || [])
        .filter((item) => !item.correct)
        .map((item, index) =>
            `${index + 1}. 题干：${item.question}\n   学生答案：${item.user_answer || '未作答'}\n   正确答案：${item.correct_answer}\n   官方解析：${item.explanation || '无'}`,
        )
        .join('\n');

    const questionDigest = (result.breakdown || [])
        .map((item, index) =>
            `${index + 1}. 题干：${item.question}\n   学生答案：${item.user_answer || '未作答'}\n   正确答案：${item.correct_answer}\n   原始解析：${item.explanation || '无'}`,
        )
        .join('\n');

    const tips = Array.isArray(practice?.tips) && practice.tips.length ? practice.tips.join('；') : '';
    const nextSteps = Array.isArray(practice?.next_steps) && practice.next_steps.length ? practice.next_steps.join('；') : '';
    const keyPhrases = Array.isArray(practice?.key_phrases) && practice.key_phrases.length
        ? practice.key_phrases
              .map((item) => `${item.phrase}${item.note ? `（${item.note}）` : ''}`)
              .join('；')
        : '';

    const sectionsInstruction = result.skill === 'listening'
        ? '围绕「场景概要」「错题复盘」「听力技巧与下一步训练」三个小节组织回答。'
        : '请包含「核心考点」「错题复盘」「下一步训练」三个小节。';

    return `# flashmvp::Gemini-2.5-Flash 指令
你是 flashmvp IELTS 学习系统中的资深${skillName}教练。
当前通过 flashmvp LLM Gateway 调用了 Gemini 2.5 Flash API，请在回复开头用一句话明确告诉学员你使用的是 Gemini 2.5 Flash 生成的讲解。

[练习信息]
- 标题：${practice.title}
- 描述：${practice.description || '（无描述）'}
${practice.context ? `- 练习提示：${practice.context}` : ''}
${practice.audio_summary ? `- 音频概要：${practice.audio_summary}` : ''}
${keyPhrases ? `- 场景关键词：${keyPhrases}` : ''}

[成绩数据]
- 得分：${result.score}/${result.total}（${result.percentage}%）
- 答对题目数：${correctCount}
- 错题数：${(result.breakdown || []).length - correctCount}

[题目明细]
${questionDigest || '全部答对'}

${incorrectItems ? `[错题重点]\n${incorrectItems}` : '[错题重点]\n全部答对，请提供巩固建议'}
${tips ? `\n[原始技巧提示] ${tips}` : ''}
${nextSteps ? `\n[推荐后续任务] ${nextSteps}` : ''}

输出要求：
- ${sectionsInstruction}
- 先肯定亮点，再给出针对性的改进建议。
- 对每道错题说明应抓取的听力或阅读线索，如需要可引用英文原句片段。
- 提供至少两条课后自学建议，可结合听力复述、词汇积累或延伸练习。
- 全程使用中文输出，保留必要的英文关键词，并使用 Markdown 标题和列表。
`;
}


function formatAiCoachResponse(text) {
    const lines = text.trim().split(/\r?\n/);
    const htmlParts = [];
    let buffer = [];
    let listType = null;

    const flushBuffer = () => {
        if (!buffer.length) {
            return;
        }
        const items = buffer.map((item) => `<li>${formatAiInline(item)}</li>`).join('');
        htmlParts.push(listType === 'ol' ? `<ol>${items}</ol>` : `<ul>${items}</ul>`);
        buffer = [];
        listType = null;
    };

    lines.forEach((rawLine) => {
        const line = rawLine.trim();
        if (!line) {
            flushBuffer();
            return;
        }

        if (/^#{1,6}\s+/.test(line)) {
            flushBuffer();
            const level = Math.min(line.match(/^#{1,6}/)[0].length + 2, 5);
            const content = formatAiInline(line.replace(/^#{1,6}\s+/, ''));
            htmlParts.push(`<h${level}>${content}</h${level}>`);
            return;
        }

        if (/^\d+[\.)]\s+/.test(line)) {
            const content = line.replace(/^\d+[\.)]\s+/, '');
            if (listType !== 'ol') {
                flushBuffer();
                listType = 'ol';
            }
            buffer.push(content);
            return;
        }

        if (/^[-*•]\s+/.test(line)) {
            const content = line.replace(/^[-*•]\s+/, '');
            if (listType !== 'ul') {
                flushBuffer();
                listType = 'ul';
            }
            buffer.push(content);
            return;
        }

        flushBuffer();
        htmlParts.push(`<p>${formatAiInline(line)}</p>`);
    });

    flushBuffer();
    return htmlParts.join('');
}


function formatAiInline(text) {
    const escaped = escapeHtml(text);
    return escaped
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/`([^`]+)`/g, '<code>$1</code>');
}


function escapeHtml(value) {
    return value
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}


async function handleWritingFeedback(event) {
    event.preventDefault();
    const textarea = document.getElementById('writingResponse');
    const feedbackBox = document.getElementById('writingFeedback');
    const content = textarea.value.trim();

    if (content.length < 80) {
        feedbackBox.style.display = 'block';
        feedbackBox.innerHTML = '<span class="error">请至少输入一段完整的英文回答。</span>';
        return;
    }

    feedbackBox.style.display = 'block';
    feedbackBox.innerHTML = '正在生成写作反馈...';

    try {
        const response = await fetch('/api/ielts/interactive/writing/feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ response: content }),
        });
        if (!response.ok) {
            const message = await response.text();
            throw new Error(message || '获取写作反馈失败');
        }
        const data = await response.json();
        renderWritingFeedback(data, feedbackBox);
    } catch (error) {
        console.error(error);
        feedbackBox.innerHTML = `<span class="error">${error.message}</span>`;
    }
}


function renderWritingFeedback(data, container) {
    const strengths = (data.strengths && data.strengths.length ? data.strengths : ['继续保持稳定的论证结构。'])
        .map((item) => `<li>${item}</li>`)
        .join('');
    const improvements = (data.improvements && data.improvements.length
        ? data.improvements
        : ['尝试加入更多例证并使用高级衔接词。'])
        .map((item) => `<li>${item}</li>`)
        .join('');

    const connectorText = data.connectors && data.connectors.length ? data.connectors.join(', ') : '建议补充衔接词';
    const academicText = data.academic_vocabulary && data.academic_vocabulary.length
        ? data.academic_vocabulary.join(', ')
        : '可增加学术词汇';

    container.innerHTML = `
        <div class="feedback-grid">
            <div class="feedback-card">
                <h4>字数与结构</h4>
                <p>总词数：${data.word_count}</p>
                <p>句子数：${data.sentence_count}</p>
                <p>平均句长：${data.average_sentence_length}</p>
                <p>段落数：${data.paragraphs}</p>
            </div>
            <div class="feedback-card">
                <h4>词汇表现</h4>
                <p>词汇多样性：${data.lexical_density}</p>
                <p>衔接词：${connectorText}</p>
                <p>学术词汇：${academicText}</p>
            </div>
            <div class="feedback-card">
                <h4>预估分档</h4>
                <p>Band 预测：${data.band_projection}</p>
                <p class="practice-note">估算仅供参考，请结合官方评分标准。</p>
            </div>
        </div>
        <div class="practice-section">
            <h4>亮点</h4>
            <ul class="tips-list">${strengths}</ul>
        </div>
        <div class="practice-section">
            <h4>改进建议</h4>
            <ul class="tips-list">${improvements}</ul>
        </div>
        <div class="practice-section">
            <h4>Checklist 自查</h4>
            <ul class="tips-list">${(data.checklist || []).map((item) => `<li>${item}</li>`).join('')}</ul>
        </div>
    `;
}


async function handleSpeakingFeedback(event) {
    event.preventDefault();
    const textarea = document.getElementById('speakingTranscript');
    const feedbackBox = document.getElementById('speakingFeedback');
    const content = textarea.value.trim();

    if (content.length < 60) {
        feedbackBox.style.display = 'block';
        feedbackBox.innerHTML = '<span class="error">请至少记录完整的口语要点或稿件。</span>';
        return;
    }

    feedbackBox.style.display = 'block';
    feedbackBox.innerHTML = '正在分析口语表达...';

    try {
        const response = await fetch('/api/ielts/interactive/speaking/coach', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ transcript: content, focus_part: 'part2' }),
        });
        if (!response.ok) {
            const message = await response.text();
            throw new Error(message || '生成口语反馈失败');
        }
        const data = await response.json();
        renderSpeakingFeedback(data, feedbackBox);
    } catch (error) {
        console.error(error);
        feedbackBox.innerHTML = `<span class="error">${error.message}</span>`;
    }
}


function renderSpeakingFeedback(data, container) {
    const strengths = (data.strengths && data.strengths.length ? data.strengths : ['继续保持自然的语速与语音。'])
        .map((item) => `<li>${item}</li>`)
        .join('');
    const improvements = (data.improvements && data.improvements.length
        ? data.improvements
        : ['尝试补充细节并使用更多衔接词。'])
        .map((item) => `<li>${item}</li>`)
        .join('');

    const fillerUsage = data.filler_usage && data.filler_usage.length
        ? `<ul class="tips-list">${data.filler_usage.map((item) => `<li>${item.term} × ${item.count}</li>`).join('')}</ul>`
        : '<p class="practice-note">未检测到明显口头语。</p>';

    container.innerHTML = `
        <div class="feedback-grid">
            <div class="feedback-card">
                <h4>输出概览</h4>
                <p>总词数：${data.word_count}</p>
                <p>独立词数：${data.unique_words}</p>
                <p>词汇多样性：${data.lexical_variety}</p>
            </div>
            <div class="feedback-card">
                <h4>衔接与口头语</h4>
                <p>衔接词：${data.connectors && data.connectors.length ? data.connectors.join(', ') : '建议补充衔接词'}</p>
                ${fillerUsage}
            </div>
            <div class="feedback-card">
                <h4>预估分档</h4>
                <p>Band 预测：${data.band_projection}</p>
                <p class="practice-note">结合流利度、词汇与连贯性估算，仅供参考。</p>
            </div>
        </div>
        <div class="practice-section">
            <h4>亮点</h4>
            <ul class="tips-list">${strengths}</ul>
        </div>
        <div class="practice-section">
            <h4>改进建议</h4>
            <ul class="tips-list">${improvements}</ul>
        </div>
        ${data.follow_up_prompts && data.follow_up_prompts.length
            ? `<div class="practice-section"><h4>延展练习</h4><ul class="tips-list">${data.follow_up_prompts.map((item) => `<li>${item}</li>`).join('')}</ul></div>`
            : ''}
    `;
}


function startSpeakingTimer(duration, displayElement) {
    if (!displayElement) {
        return;
    }
    clearInterval(speakingTimerInterval);
    let remaining = duration;
    displayElement.textContent = formatSeconds(remaining);

    speakingTimerInterval = setInterval(() => {
        remaining -= 1;
        if (remaining <= 0) {
            clearInterval(speakingTimerInterval);
            displayElement.textContent = '00:00';
            return;
        }
        displayElement.textContent = formatSeconds(remaining);
    }, 1000);
}


function formatSeconds(value) {
    const minutes = String(Math.floor(value / 60)).padStart(2, '0');
    const seconds = String(value % 60).padStart(2, '0');
    return `${minutes}:${seconds}`;
}


window.addEventListener('beforeunload', () => stopListeningPlayback(true));
