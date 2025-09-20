// frontend/features/ielts-study-system/script.js
// 雅思学习系统前端交互逻辑

checkAuth();

const skillLabels = {
    listening: '听力',
    speaking: '口语',
    reading: '阅读',
    writing: '写作',
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
