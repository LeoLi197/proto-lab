// frontend/features/ielts-study-system/script.js
// IELTS 情景化学习系统 - 多视图学习与复习体验

/* global checkAuth usageTracker */

checkAuth();

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
const ACCEPTED_TYPES = new Set(['image/jpeg', 'image/png', 'image/jpg']);
const ROUTES = ['home', 'study', 'review'];

const STORAGE_KEYS = {
    recentUploads: 'ieltsStudyRecentUploads',
    favorites: 'ieltsStudyFavorites',
    srs: 'ieltsStudySrsProgress',
    geminiKey: 'ieltsStudyGeminiApiKey',
    rememberKey: 'ieltsStudyRememberGeminiKey'
};

const MASTERY_INTERVALS = {
    0: 0,
    1: 1,
    2: 3,
    3: 7,
    4: 14,
    5: 30
};

const state = {
    route: 'home',
    uploading: false,
    uploadProgress: 0,
    uploadIndeterminate: false,
    uploadError: '',
    sessionId: '',
    session: null,
    assets: [],
    selectedAssetId: null,
    viewerTransforms: {},
    wordCards: [],
    favorites: new Set(),
    readingQuestions: [],
    readingResults: {},
    recentUploads: [],
    srs: { words: {} },
    hoverWordId: null,
    activeWordId: null,
    studySkeletonActive: false,
    lastSkeletonAt: 0
};

const elements = {};
let dragState = null;
let progressHideTimer = null;

const GEMINI_KEY_STORAGE_KEY = STORAGE_KEYS.geminiKey;
const GEMINI_REMEMBER_STORAGE_KEY = STORAGE_KEYS.rememberKey;

document.addEventListener('DOMContentLoaded', () => {
    cacheElements();
    loadStoredState();
    bindGlobalEvents();
    restoreRouteFromHash();
    initialiseGeminiKeyControls();
    renderAll();
});

function cacheElements() {
    elements.viewSections = Array.from(document.querySelectorAll('.view'));
    elements.tabNav = document.getElementById('viewTabs');
    elements.uploadBadge = document.getElementById('uploadStatusBadge');
    elements.dropZone = document.getElementById('uploadDropzone');
    elements.fileInput = document.getElementById('filePicker');
    elements.pickFilesBtn = document.getElementById('pickFilesBtn');
    elements.progressContainer = document.getElementById('uploadProgressContainer');
    elements.progressFill = document.getElementById('uploadProgressFill');
    elements.progressText = document.getElementById('uploadProgressText');
    elements.uploadError = document.getElementById('uploadError');
    elements.recentGrid = document.getElementById('recentGrid');
    elements.recentCount = document.getElementById('recentCount');
    elements.assetStrip = document.getElementById('assetStrip');
    elements.assetMeta = document.getElementById('assetMeta');
    elements.imageViewport = document.getElementById('imageViewport');
    elements.imageStage = document.getElementById('imageStage');
    elements.studyImage = document.getElementById('studyImage');
    elements.bboxLayer = document.getElementById('bboxLayer');
    elements.imagePlaceholder = document.getElementById('imagePlaceholder');
    elements.zoomControls = document.getElementById('zoomControls');
    elements.wordList = document.getElementById('wordCardList');
    elements.wordCountBadge = document.getElementById('wordCountBadge');
    elements.readingQuiz = document.getElementById('readingQuiz');
    elements.readingStatus = document.getElementById('readingStatus');
    elements.reviewList = document.getElementById('reviewList');
    elements.reviewSummary = document.getElementById('reviewSummary');
    elements.reviewOverflow = document.getElementById('reviewOverflow');
    elements.geminiInput = document.getElementById('geminiApiKey');
    elements.rememberCheckbox = document.getElementById('rememberGeminiKey');
}

function loadStoredState() {
    state.recentUploads = safeParseJson(readFromLocalStorage(STORAGE_KEYS.recentUploads), []);
    state.favorites = new Set(
        safeParseJson(readFromLocalStorage(STORAGE_KEYS.favorites), []).filter(Boolean)
    );
    const srsRaw = safeParseJson(readFromLocalStorage(STORAGE_KEYS.srs), null);
    if (srsRaw && typeof srsRaw === 'object' && srsRaw.words) {
        state.srs = srsRaw;
    }
}

function bindGlobalEvents() {
    if (elements.tabNav) {
        elements.tabNav.addEventListener('click', (event) => {
            const button = event.target.closest('button[data-route]');
            if (!button) return;
            setRoute(button.dataset.route);
        });
    }

    if (elements.dropZone) {
        ['dragenter', 'dragover'].forEach((type) => {
            elements.dropZone.addEventListener(type, (event) => {
                event.preventDefault();
                event.stopPropagation();
                elements.dropZone.classList.add('drag-over');
            });
        });
        ['dragleave', 'dragend'].forEach((type) => {
            elements.dropZone.addEventListener(type, () => {
                elements.dropZone.classList.remove('drag-over');
            });
        });
        elements.dropZone.addEventListener('drop', (event) => {
            event.preventDefault();
            elements.dropZone.classList.remove('drag-over');
            if (event.dataTransfer && event.dataTransfer.files) {
                handleFiles(Array.from(event.dataTransfer.files));
            }
        });
        elements.dropZone.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                if (elements.fileInput) elements.fileInput.click();
            }
        });
    }

    if (elements.pickFilesBtn && elements.fileInput) {
        elements.pickFilesBtn.addEventListener('click', () => {
            elements.fileInput.click();
        });
        elements.fileInput.addEventListener('change', () => {
            const files = Array.from(elements.fileInput.files || []);
            if (files.length) {
                handleFiles(files);
                elements.fileInput.value = '';
            }
        });
    }

    if (elements.wordList) {
        elements.wordList.addEventListener('pointerover', (event) => {
            const card = event.target.closest('.word-card');
            if (!card) return;
            setHoverWord(card.dataset.wordCard || null);
        });
        elements.wordList.addEventListener('pointerout', (event) => {
            const card = event.target.closest('.word-card');
            if (!card) {
                setHoverWord(null);
                return;
            }
            if (!card.contains(event.relatedTarget)) {
                setHoverWord(null);
            }
        });
        elements.wordList.addEventListener('click', (event) => {
            const favButton = event.target.closest('.favorite-toggle');
            if (favButton) {
                event.stopPropagation();
                toggleFavorite(favButton.dataset.wordFav || '');
                return;
            }
            const card = event.target.closest('.word-card');
            if (card) {
                setActiveWord(card.dataset.wordCard || null, true);
            }
        });
    }

    if (elements.bboxLayer) {
        elements.bboxLayer.addEventListener('pointerover', (event) => {
            const box = event.target.closest('.bbox-box');
            if (!box) return;
            setHoverWord(box.dataset.wordBox || null);
        });
        elements.bboxLayer.addEventListener('pointerout', (event) => {
            const box = event.target.closest('.bbox-box');
            if (!box || !box.contains(event.relatedTarget)) {
                setHoverWord(null);
            }
        });
        elements.bboxLayer.addEventListener('click', (event) => {
            const box = event.target.closest('.bbox-box');
            if (!box) return;
            const wordId = box.dataset.wordBox || null;
            setActiveWord(wordId, true);
            scrollWordIntoView(wordId);
        });
    }

    if (elements.assetStrip) {
        elements.assetStrip.addEventListener('click', (event) => {
            const button = event.target.closest('[data-asset]');
            if (!button) return;
            selectAsset(button.dataset.asset);
        });
    }

    if (elements.zoomControls) {
        elements.zoomControls.addEventListener('click', (event) => {
            const button = event.target.closest('button[data-zoom]');
            if (!button) return;
            adjustZoom(button.dataset.zoom);
        });
    }

    if (elements.imageViewport) {
        elements.imageViewport.addEventListener('pointerdown', handleViewportPointerDown);
        window.addEventListener('pointermove', handleViewportPointerMove);
        window.addEventListener('pointerup', handleViewportPointerUp);
        elements.imageViewport.addEventListener('wheel', (event) => {
            if (!state.selectedAssetId) return;
            event.preventDefault();
            const direction = event.deltaY > 0 ? 'out' : 'in';
            adjustZoom(direction, { x: event.offsetX, y: event.offsetY });
        }, { passive: false });
    }

    if (elements.readingQuiz) {
        elements.readingQuiz.addEventListener('click', (event) => {
            const option = event.target.closest('.reading-option');
            if (!option) return;
            const question = option.closest('.reading-question');
            if (!question) return;
            const questionId = question.dataset.questionId;
            const value = option.dataset.questionOption || option.textContent || '';
            handleReadingSelection(questionId, value.trim());
        });
    }

    if (elements.reviewList) {
        elements.reviewList.addEventListener('click', (event) => {
            const button = event.target.closest('.review-btn');
            if (!button) return;
            const wordId = button.dataset.reviewWord;
            if (!wordId) return;
            const action = button.dataset.reviewAction;
            handleReviewAction(wordId, action === 'pass');
        });
    }

    window.addEventListener('hashchange', restoreRouteFromHash);
}

function restoreRouteFromHash() {
    const hash = window.location.hash.replace('#', '');
    if (ROUTES.includes(hash)) {
        state.route = hash;
    } else if (state.session) {
        state.route = 'study';
    } else {
        state.route = 'home';
    }
    renderRoute();
}

function setRoute(route) {
    if (!ROUTES.includes(route)) return;
    if (state.route === route) return;
    state.route = route;
    window.location.hash = route;
    renderRoute();
}

function renderAll() {
    renderRoute();
    renderHome();
    renderStudy();
    renderReview();
}

function renderRoute() {
    elements.viewSections.forEach((section) => {
        const isActive = section.dataset.view === state.route;
        section.classList.toggle('view-active', isActive);
        section.setAttribute('aria-hidden', isActive ? 'false' : 'true');
    });
    if (elements.tabNav) {
        const buttons = elements.tabNav.querySelectorAll('button[data-route]');
        buttons.forEach((button) => {
            const active = button.dataset.route === state.route;
            button.classList.toggle('is-active', active);
            button.setAttribute('aria-selected', active ? 'true' : 'false');
        });
    }
}

function renderHome() {
    if (!elements.uploadBadge) return;
    if (state.uploading) {
        elements.uploadBadge.textContent = '上传中';
        elements.uploadBadge.classList.add('loading');
    } else if (state.sessionId) {
        elements.uploadBadge.textContent = '已生成';
        elements.uploadBadge.classList.remove('loading');
    } else {
        elements.uploadBadge.textContent = '待开始';
        elements.uploadBadge.classList.remove('loading');
    }

    if (elements.progressContainer) {
        elements.progressContainer.classList.toggle('active', state.uploading);
        if (state.uploading) {
            if (typeof state.uploadProgress === 'number' && !state.uploadIndeterminate) {
                const percentage = Math.max(0, Math.min(100, Math.round(state.uploadProgress * 100)));
                elements.progressFill.style.width = `${percentage}%`;
                elements.progressText.textContent = `${percentage}%`;
            } else {
                elements.progressFill.style.width = '100%';
                elements.progressText.textContent = '···';
            }
        } else {
            elements.progressFill.style.width = '0%';
            elements.progressText.textContent = '0%';
        }
    }

    if (elements.uploadError) {
        elements.uploadError.textContent = state.uploadError || '';
    }

    renderRecentUploads();
}

function renderRecentUploads() {
    if (!elements.recentGrid) return;
    if (!Array.isArray(state.recentUploads) || state.recentUploads.length === 0) {
        elements.recentGrid.innerHTML = buildRecentSkeleton();
        if (elements.recentCount) {
            elements.recentCount.textContent = '0';
        }
        return;
    }
    const items = state.recentUploads.slice(0, 10);
    elements.recentGrid.innerHTML = items
        .map((item) => {
            const metaParts = [];
            if (item.width && item.height) {
                metaParts.push(`${item.width}×${item.height}`);
            }
            if (item.words) {
                metaParts.push(`${item.words} 词`);
            }
            metaParts.push(formatRelativeTime(item.uploadedAt));
            const preview = item.thumbnail
                ? `<img src="${item.thumbnail}" alt="${escapeHtml(item.name || '学习图片')} 缩略图">`
                : '<div class="skeleton-block skeleton-thumb"></div>';
            return `
                <div class="recent-card">
                    ${preview}
                    <div class="recent-meta">${escapeHtml(item.name || '未命名')}</div>
                    <div class="recent-meta">${metaParts.map(escapeHtml).join(' · ')}</div>
                </div>
            `;
        })
        .join('');
    if (elements.recentCount) {
        elements.recentCount.textContent = `${items.length}`;
    }
}

function renderStudy() {
    if (!elements.assetMeta) return;
    if (!state.session || !state.assets.length) {
        elements.assetMeta.textContent = '无图像';
        elements.assetStrip.innerHTML = '';
        elements.imagePlaceholder.style.display = 'flex';
        elements.studyImage.hidden = true;
        elements.bboxLayer.innerHTML = '';
        elements.wordCountBadge.textContent = '0';
        elements.wordList.innerHTML = buildWordSkeleton();
        elements.readingStatus.textContent = '未生成';
        elements.readingQuiz.innerHTML = buildReadingSkeleton();
        return;
    }

    const selectedAsset = getSelectedAsset();
    elements.assetMeta.textContent = selectedAsset
        ? `${Math.round(selectedAsset.width)}×${Math.round(selectedAsset.height)}`
        : `${state.assets.length} 张图像`;

    elements.assetStrip.innerHTML = state.assets
        .map((asset) => `
            <button type="button" class="asset-thumb ${asset.id === state.selectedAssetId ? 'is-active' : ''}" data-asset="${asset.id}">
                ${asset.thumbnail ? `<img src="${asset.thumbnail}" alt="${escapeHtml(asset.name || '图片')} 缩略图">` : '<div class="skeleton-block skeleton-thumb"></div>'}
            </button>
        `)
        .join('');

    if (selectedAsset) {
        elements.imageStage.style.width = `${selectedAsset.width}px`;
        elements.imageStage.style.height = `${selectedAsset.height}px`;
        elements.studyImage.src = selectedAsset.url;
        elements.studyImage.hidden = false;
        elements.imagePlaceholder.style.display = 'none';
        renderBoundingBoxes(selectedAsset);
        applyViewerTransform();
    } else {
        elements.studyImage.hidden = true;
        elements.imagePlaceholder.style.display = 'flex';
        elements.bboxLayer.innerHTML = '';
        elements.imageStage.style.width = '0px';
        elements.imageStage.style.height = '0px';
    }

    elements.wordCountBadge.textContent = `${state.wordCards.length}`;
    if (state.wordCards.length === 0) {
        elements.wordList.innerHTML = buildWordSkeleton();
    } else {
        elements.wordList.innerHTML = state.wordCards
            .map((card) => renderWordCard(card, state.favorites.has(card.id)))
            .join('');
    }
    updateHighlights();

    if (!state.readingQuestions.length) {
        elements.readingStatus.textContent = '未生成';
        elements.readingQuiz.innerHTML = buildReadingSkeleton();
    } else {
        const answered = Object.keys(state.readingResults).length;
        elements.readingStatus.textContent = `已生成 ${answered}/${state.readingQuestions.length}`;
        elements.readingQuiz.innerHTML = state.readingQuestions
            .map((question, index) => renderReadingQuestion(question, index))
            .join('');
    }
}

function renderReview() {
    if (!elements.reviewList) return;
    const { dueToday, overflowCount } = computeDailyReviewList();
    const totalWords = Object.keys(state.srs.words || {}).length;
    const summaryText = `今日 ${dueToday.length} / 累积 ${totalWords}`;
    elements.reviewSummary.textContent = summaryText;

    if (!dueToday.length) {
        elements.reviewList.innerHTML = `<div class="empty-placeholder">今日暂无待复习词汇，请完成阅读练习或继续打卡。</div>`;
    } else {
        elements.reviewList.innerHTML = dueToday.map(renderReviewItem).join('');
    }

    if (overflowCount > 0) {
        elements.reviewOverflow.textContent = `已将额外的 ${overflowCount} 个词自动顺延至明日待复习。`;
    } else {
        elements.reviewOverflow.textContent = '';
    }
}

function buildRecentSkeleton() {
    return Array.from({ length: 6 })
        .map(
            () => `
            <div class="recent-card">
                <div class="skeleton-block skeleton-thumb"></div>
                <div class="skeleton-block skeleton-line" style="width: 80%"></div>
                <div class="skeleton-block skeleton-line" style="width: 60%"></div>
            </div>
        `
        )
        .join('');
}

function buildWordSkeleton() {
    return Array.from({ length: 6 })
        .map(
            () => `
            <div class="word-card">
                <div class="skeleton-block skeleton-line" style="width: 40%; height: 18px"></div>
                <div class="skeleton-block skeleton-line" style="width: 60%"></div>
                <div class="skeleton-block skeleton-line" style="width: 90%"></div>
                <div class="skeleton-block skeleton-line" style="width: 75%"></div>
            </div>
        `
        )
        .join('');
}

function buildReadingSkeleton() {
    return Array.from({ length: 3 })
        .map(
            () => `
            <div class="reading-question">
                <div class="skeleton-block skeleton-line" style="width: 60%; height: 18px"></div>
                <div class="skeleton-block skeleton-line" style="width: 100%"></div>
                <div class="skeleton-block skeleton-line" style="width: 90%"></div>
            </div>
        `
        )
        .join('');
}

function renderWordCard(card, isFavorite) {
    const topics = (card.topics || []).slice(0, 3).map((topic) => `<span class="topic-chip">${escapeHtml(topic)}</span>`).join('');
    return `
        <article class="word-card ${state.hoverWordId === card.id ? 'is-highlighted' : ''} ${state.activeWordId === card.id ? 'is-active' : ''}" data-word-card="${card.id}">
            <header>
                <div>
                    <h3>${escapeHtml(card.lemma)}</h3>
                    <div class="word-meta">${escapeHtml(card.pos)} · <span class="phonetic">${escapeHtml(card.phonetic)}</span></div>
                </div>
                <button type="button" class="favorite-toggle" aria-pressed="${isFavorite ? 'true' : 'false'}" data-word-fav="${card.id}" title="收藏">
                    ${isFavorite ? '★' : '☆'}
                </button>
            </header>
            <p class="word-definition">${escapeHtml(card.definition)}</p>
            <p class="word-example">${escapeHtml(card.example)}</p>
            <div class="word-topics">${topics}</div>
        </article>
    `;
}

function renderReadingQuestion(question, index) {
    const result = state.readingResults[question.id];
    const statusClass = result ? (result.status === 'correct' ? 'correct' : 'incorrect') : '';
    const explanation = result ? result.explanation || '' : '';
    const selectedValue = result ? result.selected : '';
    const optionsHtml = question.options
        .map((option) => {
            const normalisedOption = option.trim();
            const resultClass = !result
                ? ''
                : normaliseAnswer(normalisedOption) === normaliseAnswer(selectedValue)
                ? `is-selected ${result.status === 'correct' ? 'is-correct' : 'is-incorrect'}`
                : '';
            return `
                <button type="button" class="reading-option ${resultClass}" data-question-option="${escapeAttribute(normalisedOption)}" ${result ? 'disabled' : ''}>
                    ${escapeHtml(option)}
                </button>
            `;
        })
        .join('');
    return `
        <div class="reading-question" data-question-id="${question.id}">
            <div class="question-header">
                <span class="question-index">${index + 1}</span>
                <p class="question-prompt">${escapeHtml(question.prompt)}</p>
            </div>
            <div class="option-list">${optionsHtml}</div>
            <p class="question-hint">提示：${escapeHtml(question.hint || '仔细阅读情境段落')}</p>
            <p class="question-result ${statusClass}">${escapeHtml(explanation)}</p>
        </div>
    `;
}

function renderBoundingBoxes(asset) {
    if (!asset || !elements.bboxLayer) return;
    const boxesHtml = (asset.boxes || [])
        .map((box) => {
            const styles = `left:${box.x}px;top:${box.y}px;width:${box.width}px;height:${box.height}px;`;
            const highlightClass = [state.hoverWordId, state.activeWordId].includes(box.wordId) ? 'is-highlighted' : '';
            const activeClass = state.activeWordId === box.wordId ? 'is-active' : '';
            return `<div class="bbox-box ${highlightClass} ${activeClass}" data-word-box="${box.wordId}" data-label="${escapeAttribute(box.label || '')}" style="${styles}"></div>`;
        })
        .join('');
    elements.bboxLayer.innerHTML = boxesHtml;
}

function renderReviewItem(entry) {
    const display = entry.display || {};
    const topics = Array.isArray(display.topics)
        ? display.topics.slice(0, 3).map((topic) => `<span class="topic-chip">${escapeHtml(topic)}</span>`).join('')
        : '';
    const masteryLabel = `记忆等级 Lv.${entry.mastery ?? 0}`;
    return `
        <div class="review-item" data-review-word="${entry.id}">
            <div class="review-word">
                <h3>${escapeHtml(entry.lemma || entry.id)}</h3>
                <p>${escapeHtml(display.pos || '—')} · ${escapeHtml(display.phonetic || '—')}</p>
            </div>
            <div>
                <div class="review-definition">${escapeHtml(display.definition || '情境词汇')}</div>
                <div class="word-topics">${topics}</div>
                <div class="review-meta">${masteryLabel} · 下次复习：${formatDate(entry.nextReview)}</div>
            </div>
            <div class="review-actions">
                <button type="button" class="review-btn" data-review-word="${entry.id}" data-review-action="again">仍需复习</button>
                <button type="button" class="review-btn primary" data-review-word="${entry.id}" data-review-action="pass">我会了</button>
            </div>
        </div>
    `;
}

function handleFiles(files) {
    if (!files.length || state.uploading) {
        return;
    }
    const errors = [];
    const accepted = [];
    files.slice(0, 3).forEach((file) => {
        const validation = validateFile(file);
        if (validation) {
            errors.push(`${file.name}: ${validation}`);
        } else {
            accepted.push(file);
        }
    });
    if (errors.length) {
        state.uploadError = errors.join('；');
        renderHome();
    }
    if (!accepted.length) {
        return;
    }
    startUpload(accepted);
}

function validateFile(file) {
    if (!file) return '无法读取文件';
    if (!ACCEPTED_TYPES.has(file.type)) {
        const name = file.name || '';
        if (!/\.(jpe?g|png)$/i.test(name)) {
            return '格式不支持，请上传 JPG 或 PNG 图片';
        }
    }
    if (file.size > MAX_FILE_SIZE) {
        return '文件过大，请控制在 10MB 以内';
    }
    return '';
}

async function startUpload(files) {
    state.uploading = true;
    state.uploadError = '';
    state.uploadProgress = 0;
    state.uploadIndeterminate = false;
    state.studySkeletonActive = true;
    state.lastSkeletonAt = Date.now();
    renderHome();
    renderStudy();

    try {
        const assets = await Promise.all(files.map(createAssetFromFile));
        const formData = new FormData();
        files.forEach((file) => formData.append('files', file));
        const apiKey = getActiveGeminiApiKey();
        if (apiKey) {
            formData.append('gemini_api_key', apiKey);
        }

        if (window.usageTracker) {
            usageTracker.track({ feature: 'ielts-study-system', action: 'upload-start' });
        }

        const payload = await uploadWithProgress('/api/ielts/upload-batch', formData, (progress) => {
            if (progress == null) {
                state.uploadIndeterminate = true;
            } else {
                state.uploadIndeterminate = false;
                state.uploadProgress = progress;
            }
            renderHome();
        });

        processSessionPayload(payload, assets);

        if (window.usageTracker) {
            usageTracker.track({ feature: 'ielts-study-system', action: 'upload-success' });
        }
    } catch (error) {
        const message = (error && error.message) || '生成学习素材失败，请稍后重试';
        state.uploadError = message;
        if (elements.uploadBadge) {
            elements.uploadBadge.textContent = '上传失败';
            elements.uploadBadge.classList.add('error');
        }
        if (window.usageTracker) {
            usageTracker.track({ feature: 'ielts-study-system', action: 'upload-error', detail: message });
        }
    } finally {
        state.uploading = false;
        state.uploadIndeterminate = false;
        state.uploadProgress = 0;
        if (progressHideTimer) {
            clearTimeout(progressHideTimer);
        }
        progressHideTimer = setTimeout(() => {
            renderHome();
            progressHideTimer = null;
        }, 600);
    }
}

function processSessionPayload(data, assets) {
    if (!data || typeof data !== 'object') {
        state.uploadError = '服务器未返回有效数据';
        renderHome();
        return;
    }
    state.sessionId = data.session_id || '';
    state.session = {
        words: data.words || {},
        story: data.story || {},
        reading: data.reading || {},
        listening: data.listening || {},
        conversation: data.conversation || {}
    };
    state.assets = assets.map((asset) => ({ ...asset, boxes: [] }));
    state.selectedAssetId = state.assets[0] ? state.assets[0].id : null;
    state.viewerTransforms = {};

    state.wordCards = buildWordCards(state.session);
    registerWordsForSrs(state.wordCards);
    assignBoundingBoxes();
    state.activeWordId = state.wordCards[0] ? state.wordCards[0].id : null;

    state.readingQuestions = buildReadingQuestions(state.session.reading, state.wordCards);
    state.readingResults = {};

    appendRecentUploads(assets, state.session.words);
    saveRecentUploads();
    saveFavorites();
    saveSrsProgress();

    state.studySkeletonActive = false;
    renderAll();
    setRoute('study');
}

function assignBoundingBoxes() {
    if (!state.assets.length || !state.wordCards.length) return;
    const assetCount = state.assets.length;
    const wordsPerAsset = Math.max(1, Math.ceil(state.wordCards.length / assetCount));
    state.assets.forEach((asset) => {
        asset.boxes = [];
    });
    state.wordCards.forEach((card, index) => {
        const assetIndex = Math.min(state.assets.length - 1, Math.floor(index / wordsPerAsset));
        const asset = state.assets[assetIndex];
        const box = generateBoundingBox(asset, card, index);
        asset.boxes.push(box);
    });
}

function generateBoundingBox(asset, card, index) {
    const width = asset.width || 800;
    const height = asset.height || 600;
    const hash = stringHash(`${card.id}-${asset.id}-${index}`);
    const boxWidth = Math.max(80, Math.min(width * 0.45, 120 + (hash % 140)));
    const boxHeight = Math.max(48, Math.min(height * 0.3, 60 + ((hash >> 3) % 100)));
    const maxX = Math.max(0, width - boxWidth);
    const maxY = Math.max(0, height - boxHeight);
    const x = maxX ? (hash * 31) % maxX : 0;
    const y = maxY ? (hash * 17) % maxY : 0;
    return {
        id: `${asset.id}-${card.id}`,
        wordId: card.id,
        label: card.lemma,
        x,
        y,
        width: boxWidth,
        height: boxHeight
    };
}

function buildWordCards(session) {
    const result = [];
    const words = (session.words && session.words.items) || [];
    const story = session.story || {};
    const sentences = Array.isArray(story.sentences) ? story.sentences : [];
    const paragraphs = Array.isArray(story.paragraphs) ? story.paragraphs : [];
    const topics = buildStoryTopics(story);

    words.forEach((word, index) => {
        const normalised = (word || '').toLowerCase();
        const detail = sentences.find((item) => (item.word || '').toLowerCase() === normalised) || {};
        const lemma = capitalize(detail.word || word || '');
        const pos = detail.pos || guessPartOfSpeech(word);
        const phonetic = normalisePhonetic(detail.phonetic) || buildPseudoPhonetic(word);
        const definitionSource = detail.hint || detail.rationale || paragraphs[index % (paragraphs.length || 1)] || story.overview || `关注 ${lemma} 在情境中的作用。`;
        const example = detail.sentence || paragraphs[index % (paragraphs.length || 1)] || story.scenario || story.overview || '结合情境理解词义。';
        result.push({
            id: normalised,
            lemma,
            pos,
            phonetic,
            definition: truncateWords(definitionSource, 16),
            example: truncateWords(example, 22),
            topics,
            focus: Array.isArray(detail.focus_words) ? detail.focus_words : []
        });
    });
    return result;
}

function buildStoryTopics(story) {
    const candidates = [story.setting, story.audience, story.title, story.scenario, story.overview];
    const topics = [];
    candidates.forEach((candidate) => {
        if (!candidate) return;
        String(candidate)
            .split(/[、,，\/]/)
            .map((item) => item.trim())
            .filter(Boolean)
            .forEach((item) => {
                if (!topics.includes(item) && topics.length < 5) {
                    topics.push(item);
                }
            });
    });
    if (!topics.length) {
        topics.push('IELTS');
    }
    return topics;
}

function buildReadingQuestions(reading, wordCards) {
    const questions = Array.isArray(reading?.questions) ? reading.questions.slice(0, 3) : [];
    const fallbackWords = wordCards.map((card) => card.lemma);
    return questions.map((question, index) => {
        const id = question.id || `R${index + 1}`;
        const focusWords = Array.isArray(question.focus_words)
            ? question.focus_words.map((item) => String(item).trim()).filter(Boolean)
            : [];
        const answerKey = (focusWords[0] || question.answer || '').trim();
        const hint = question.hint || (question.rationale ? truncateWords(question.rationale, 18) : '留意故事中的关键词。');
        const prompt = question.prompt || '根据情境选择最合适的单词。';
        const options = buildQuestionOptions(question, fallbackWords, answerKey);
        return {
            id,
            prompt,
            hint,
            options,
            focusWords,
            answerKey
        };
    });
}

function buildQuestionOptions(question, fallbackWords, answerKey) {
    const options = new Set();
    const questionOptions = question.options || question.choices || [];
    questionOptions.forEach((option) => {
        if (typeof option === 'string' && option.trim()) {
            options.add(option.trim());
        }
    });
    (question.focus_words || []).forEach((option) => {
        if (typeof option === 'string' && option.trim()) {
            options.add(option.trim());
        }
    });
    if (answerKey) {
        options.add(answerKey.trim());
    }
    const pool = fallbackWords.filter((word) => word && !options.has(word));
    while (options.size < 3 && pool.length) {
        const index = Math.floor(Math.random() * pool.length);
        options.add(pool.splice(index, 1)[0]);
    }
    while (options.size < 3) {
        options.add(`选项 ${options.size + 1}`);
    }
    return Array.from(options).slice(0, 3);
}

async function createAssetFromFile(file) {
    const dataUrl = await readFileAsDataUrl(file);
    const imageMeta = await loadImageMeta(dataUrl);
    const thumbnail = await createThumbnail(dataUrl, 320, 240);
    return {
        id: `asset-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
        name: file.name,
        size: file.size,
        type: file.type,
        url: dataUrl,
        thumbnail,
        width: imageMeta.width,
        height: imageMeta.height,
        uploadedAt: Date.now(),
        boxes: []
    };
}

function readFileAsDataUrl(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(new Error('无法读取文件内容'));
        reader.readAsDataURL(file);
    });
}

function loadImageMeta(dataUrl) {
    return new Promise((resolve) => {
        const image = new Image();
        image.onload = () => {
            resolve({ width: image.naturalWidth || 0, height: image.naturalHeight || 0 });
        };
        image.onerror = () => resolve({ width: 0, height: 0 });
        image.src = dataUrl;
    });
}

async function createThumbnail(dataUrl, targetWidth, targetHeight) {
    try {
        const image = await loadImageElement(dataUrl);
        const width = image.naturalWidth || targetWidth;
        const height = image.naturalHeight || targetHeight;
        const ratio = Math.min(targetWidth / width, targetHeight / height, 1);
        const canvas = document.createElement('canvas');
        canvas.width = Math.round(width * ratio);
        canvas.height = Math.round(height * ratio);
        const ctx = canvas.getContext('2d');
        ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
        return canvas.toDataURL('image/jpeg', 0.7);
    } catch (error) {
        console.warn('Failed to create thumbnail', error);
        return '';
    }
}

function loadImageElement(dataUrl) {
    return new Promise((resolve, reject) => {
        const image = new Image();
        image.onload = () => resolve(image);
        image.onerror = (err) => reject(err);
        image.src = dataUrl;
    });
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
                resolve(xhr.response || {});
            } else {
                reject(new Error(parseXHRError(xhr) || '上传失败'));
            }
        };
        xhr.onerror = () => reject(new Error('网络异常，请稍后重试'));
        xhr.send(formData);
    });
}

function parseXHRError(xhr) {
    try {
        if (xhr.response && typeof xhr.response === 'object') {
            return normaliseErrorDetail(xhr.response.detail || xhr.response.message || xhr.response);
        }
        if (xhr.responseText) {
            const parsed = JSON.parse(xhr.responseText);
            return normaliseErrorDetail(parsed.detail || parsed.message || parsed);
        }
    } catch (error) {
        return xhr.responseText || '请求失败';
    }
    return '';
}

function normaliseErrorDetail(value) {
    if (!value) return '';
    if (typeof value === 'string') return value;
    if (Array.isArray(value)) {
        return value.map((item) => normaliseErrorDetail(item)).filter(Boolean).join('；');
    }
    if (typeof value === 'object') {
        const keys = ['detail', 'message', 'error'];
        for (const key of keys) {
            if (key in value) {
                const result = normaliseErrorDetail(value[key]);
                if (result) return result;
            }
        }
        return Object.values(value)
            .map((item) => normaliseErrorDetail(item))
            .filter(Boolean)
            .join('；');
    }
    return String(value);
}

function setHoverWord(wordId) {
    if (state.hoverWordId === wordId) return;
    state.hoverWordId = wordId;
    updateHighlights();
}

function setActiveWord(wordId, pin = false) {
    if (wordId && pin) {
        state.activeWordId = wordId;
    } else if (!pin) {
        state.activeWordId = wordId;
    }
    updateHighlights();
}

function updateHighlights() {
    if (elements.wordList) {
        const cards = elements.wordList.querySelectorAll('.word-card');
        cards.forEach((card) => {
            const wordId = card.dataset.wordCard;
            card.classList.toggle('is-highlighted', wordId === state.hoverWordId);
            card.classList.toggle('is-active', wordId === state.activeWordId);
            const fav = card.querySelector('.favorite-toggle');
            if (fav) {
                fav.setAttribute('aria-pressed', state.favorites.has(wordId) ? 'true' : 'false');
                fav.textContent = state.favorites.has(wordId) ? '★' : '☆';
            }
        });
    }
    if (elements.bboxLayer) {
        const boxes = elements.bboxLayer.querySelectorAll('.bbox-box');
        boxes.forEach((box) => {
            const wordId = box.dataset.wordBox;
            box.classList.toggle('is-highlighted', wordId === state.hoverWordId || wordId === state.activeWordId);
            box.classList.toggle('is-active', wordId === state.activeWordId);
        });
    }
}

function scrollWordIntoView(wordId) {
    if (!wordId || !elements.wordList) return;
    const target = elements.wordList.querySelector(`.word-card[data-word-card="${wordId}"]`);
    if (target && typeof target.scrollIntoView === 'function') {
        target.scrollIntoView({ block: 'center', behavior: 'smooth' });
    }
}

function selectAsset(assetId) {
    if (!assetId || state.selectedAssetId === assetId) return;
    state.selectedAssetId = assetId;
    if (!state.viewerTransforms[assetId]) {
        state.viewerTransforms[assetId] = { scale: 1, translateX: 0, translateY: 0 };
    }
    renderStudy();
}

function getSelectedAsset() {
    if (!state.selectedAssetId) {
        return state.assets[0] || null;
    }
    return state.assets.find((asset) => asset.id === state.selectedAssetId) || state.assets[0] || null;
}

function adjustZoom(action, center) {
    const asset = getSelectedAsset();
    if (!asset) return;
    const transform = getCurrentTransform(asset.id);
    const factor = action === 'in' ? 1.2 : action === 'out' ? 1 / 1.2 : 1;
    if (action === 'reset') {
        state.viewerTransforms[asset.id] = { scale: 1, translateX: 0, translateY: 0 };
        applyViewerTransform();
        return;
    }
    let newScale = transform.scale * factor;
    newScale = Math.max(0.5, Math.min(3, newScale));
    const viewportRect = elements.imageViewport.getBoundingClientRect();
    const originX = center ? center.x : viewportRect.width / 2;
    const originY = center ? center.y : viewportRect.height / 2;
    const translateX = transform.translateX + (originX - viewportRect.width / 2) * (1 - factor);
    const translateY = transform.translateY + (originY - viewportRect.height / 2) * (1 - factor);
    state.viewerTransforms[asset.id] = {
        scale: newScale,
        translateX,
        translateY
    };
    applyViewerTransform();
}

function getCurrentTransform(assetId) {
    if (!state.viewerTransforms[assetId]) {
        state.viewerTransforms[assetId] = { scale: 1, translateX: 0, translateY: 0 };
    }
    return state.viewerTransforms[assetId];
}

function applyViewerTransform() {
    const asset = getSelectedAsset();
    if (!asset) return;
    const transform = getCurrentTransform(asset.id);
    elements.imageStage.style.setProperty('--scale', transform.scale);
    elements.imageStage.style.setProperty('--translate-x', `${transform.translateX}px`);
    elements.imageStage.style.setProperty('--translate-y', `${transform.translateY}px`);
    renderBoundingBoxes(asset);
    updateHighlights();
}

function handleViewportPointerDown(event) {
    if (!state.selectedAssetId) return;
    const asset = getSelectedAsset();
    if (!asset) return;
    dragState = {
        assetId: asset.id,
        startX: event.clientX,
        startY: event.clientY,
        baseX: getCurrentTransform(asset.id).translateX,
        baseY: getCurrentTransform(asset.id).translateY,
        moved: false
    };
    elements.imageViewport.setPointerCapture(event.pointerId);
}

function handleViewportPointerMove(event) {
    if (!dragState) return;
    event.preventDefault();
    const deltaX = event.clientX - dragState.startX;
    const deltaY = event.clientY - dragState.startY;
    if (Math.abs(deltaX) > 1 || Math.abs(deltaY) > 1) {
        dragState.moved = true;
    }
    const transform = getCurrentTransform(dragState.assetId);
    state.viewerTransforms[dragState.assetId] = {
        ...transform,
        translateX: dragState.baseX + deltaX,
        translateY: dragState.baseY + deltaY
    };
    applyViewerTransform();
}

function handleViewportPointerUp(event) {
    if (!dragState) return;
    if (elements.imageViewport.hasPointerCapture(event.pointerId)) {
        elements.imageViewport.releasePointerCapture(event.pointerId);
    }
    dragState = null;
}

function toggleFavorite(wordId) {
    if (!wordId) return;
    if (state.favorites.has(wordId)) {
        state.favorites.delete(wordId);
    } else {
        state.favorites.add(wordId);
    }
    saveFavorites();
    updateHighlights();
}

function appendRecentUploads(assets, wordsMeta) {
    const wordCount = wordsMeta?.total || (wordsMeta?.items ? wordsMeta.items.length : 0) || 0;
    const entries = assets.map((asset) => ({
        id: asset.id,
        name: asset.name,
        uploadedAt: asset.uploadedAt,
        thumbnail: asset.thumbnail,
        width: Math.round(asset.width),
        height: Math.round(asset.height),
        words: wordCount
    }));
    state.recentUploads = [...entries, ...state.recentUploads].slice(0, 10);
}

function saveRecentUploads() {
    writeToLocalStorage(STORAGE_KEYS.recentUploads, JSON.stringify(state.recentUploads));
}

function saveFavorites() {
    writeToLocalStorage(STORAGE_KEYS.favorites, JSON.stringify(Array.from(state.favorites)));
}

function registerWordsForSrs(wordCards) {
    if (!Array.isArray(wordCards)) return;
    const now = Date.now();
    state.srs.words = state.srs.words || {};
    wordCards.forEach((card) => {
        const existing = state.srs.words[card.id];
        const display = {
            pos: card.pos,
            phonetic: card.phonetic,
            definition: card.definition,
            example: card.example,
            topics: card.topics
        };
        if (existing) {
            existing.lemma = card.lemma;
            existing.display = display;
        } else {
            state.srs.words[card.id] = {
                id: card.id,
                lemma: card.lemma,
                mastery: 0,
                nextReview: now,
                history: [],
                display
            };
        }
    });
}

function updateSrsEntry(wordId, success, source, context) {
    if (!wordId) return;
    state.srs.words = state.srs.words || {};
    if (!state.srs.words[wordId]) {
        state.srs.words[wordId] = {
            id: wordId,
            lemma: capitalize(wordId),
            mastery: 0,
            nextReview: Date.now(),
            history: [],
            display: { pos: '—', phonetic: '—', definition: '情境词汇', example: '', topics: [] }
        };
    }
    const entry = state.srs.words[wordId];
    entry.mastery = entry.mastery || 0;
    if (success) {
        entry.mastery = Math.min(5, entry.mastery + 1);
    } else {
        entry.mastery = Math.max(0, entry.mastery - 1);
    }
    const days = MASTERY_INTERVALS[entry.mastery] ?? 1;
    entry.nextReview = Date.now() + days * 24 * 60 * 60 * 1000;
    entry.history = entry.history || [];
    entry.history.push({
        timestamp: Date.now(),
        success,
        source,
        context
    });
    entry.lastResult = success ? 'correct' : 'incorrect';
    saveSrsProgress();
}

function saveSrsProgress() {
    writeToLocalStorage(STORAGE_KEYS.srs, JSON.stringify(state.srs));
}

function handleReadingSelection(questionId, selectedOption) {
    if (!questionId || !selectedOption) return;
    const question = state.readingQuestions.find((item) => item.id === questionId);
    if (!question || state.readingResults[questionId]) return;

    const isCorrectLocal = normaliseAnswer(selectedOption) === normaliseAnswer(question.answerKey || question.focusWords[0]);
    state.readingResults[questionId] = {
        status: isCorrectLocal ? 'correct' : 'incorrect',
        explanation: isCorrectLocal ? '选择正确！' : '再想想情境中的线索。',
        selected: selectedOption,
        confirmed: false
    };
    renderStudy();
    updateSrsForQuestion(question, isCorrectLocal, 'instant');
    evaluateReadingAnswer(questionId, selectedOption, question).catch((error) => {
        console.warn('Reading evaluation failed', error);
    });
}

async function evaluateReadingAnswer(questionId, selectedOption, question) {
    if (!state.sessionId) return;
    try {
        const response = await fetch(`/api/ielts/reading/${state.sessionId}/evaluate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ answers: [{ question_id: questionId, answer: selectedOption }] })
        });
        if (!response.ok) {
            throw new Error(`判分失败：${response.status}`);
        }
        const data = await response.json();
        if (!data || !Array.isArray(data.breakdown)) return;
        const detail = data.breakdown.find((item) => item.question_id === questionId);
        if (!detail) return;
        const isCorrect = Boolean(detail.correct);
        const rationale = detail.rationale || question.hint || '';
        state.readingResults[questionId] = {
            status: isCorrect ? 'correct' : 'incorrect',
            explanation: rationale,
            selected: selectedOption,
            confirmed: true,
            reference: detail.correct_answer
        };
        renderStudy();
        updateSrsForQuestion(question, isCorrect, 'evaluate');
    } catch (error) {
        console.warn(error);
        const result = state.readingResults[questionId];
        if (result && !result.confirmed) {
            result.explanation = `${result.explanation || ''}（暂未获取解析）`;
            renderStudy();
        }
    }
}

function updateSrsForQuestion(question, isCorrect, source) {
    const focusWords = question.focusWords && question.focusWords.length
        ? question.focusWords
        : [question.answerKey].filter(Boolean);
    focusWords
        .map((word) => (word || '').toLowerCase())
        .filter(Boolean)
        .forEach((word) => updateSrsEntry(word, isCorrect, source, { questionId: question.id }));
    renderReview();
}

function handleReviewAction(wordId, success) {
    updateSrsEntry(wordId, success, 'manual');
    renderReview();
}

function computeDailyReviewList() {
    const entries = Object.values(state.srs.words || {}).map((entry) => ({ ...entry, id: entry.id || entry.lemma.toLowerCase() }));
    const endOfToday = new Date();
    endOfToday.setHours(23, 59, 59, 999);
    const due = entries
        .filter((entry) => (entry.nextReview || 0) <= endOfToday.getTime())
        .sort((a, b) => (a.nextReview || 0) - (b.nextReview || 0));
    let overflowCount = 0;
    if (due.length > 20) {
        const overflow = due.splice(20);
        overflowCount = overflow.length;
        const startOfTomorrow = new Date();
        startOfTomorrow.setHours(24, 0, 0, 0);
        overflow.forEach((entry, index) => {
            const newTime = startOfTomorrow.getTime() + index * 60 * 1000;
            state.srs.words[entry.id].nextReview = newTime;
        });
        saveSrsProgress();
    }
    return { dueToday: due, overflowCount };
}

function getActiveGeminiApiKey() {
    const input = elements.geminiInput;
    if (input && typeof input.value === 'string' && input.value.trim()) {
        return input.value.trim();
    }
    const stored = getStoredGeminiKey();
    return stored || '';
}

function initialiseGeminiKeyControls() {
    const apiInput = elements.geminiInput;
    const rememberCheckbox = elements.rememberCheckbox;
    if (!apiInput || !rememberCheckbox) {
        return;
    }
    const storedKey = getStoredGeminiKey();
    let remember = shouldRememberGeminiKey();
    if (storedKey && !remember) {
        remember = true;
        writeToLocalStorage(GEMINI_REMEMBER_STORAGE_KEY, 'true');
    }
    rememberCheckbox.checked = remember;
    if (remember && storedKey) {
        apiInput.value = storedKey;
    }
    rememberCheckbox.addEventListener('change', () => {
        const shouldRemember = rememberCheckbox.checked;
        persistRememberPreference(shouldRemember);
        if (shouldRemember && apiInput.value.trim()) {
            persistGeminiKey(apiInput.value.trim());
        }
    });
    apiInput.addEventListener('input', () => {
        if (rememberCheckbox.checked) {
            persistGeminiKey(apiInput.value);
        }
    });
}

function getStoredGeminiKey() {
    return readFromLocalStorage(GEMINI_KEY_STORAGE_KEY) || '';
}

function shouldRememberGeminiKey() {
    return readFromLocalStorage(GEMINI_REMEMBER_STORAGE_KEY) === 'true';
}

function persistGeminiKey(value) {
    if (value && value.trim()) {
        writeToLocalStorage(GEMINI_KEY_STORAGE_KEY, value.trim());
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

function guessPartOfSpeech(word) {
    const lower = (word || '').toLowerCase();
    if (/ly$/.test(lower)) return 'adv.';
    if (/(tion|ment|ness|ity|ship|ence|ance)$/.test(lower)) return 'n.';
    if (/(able|ible|ous|ive|ful|less|al|ic)$/.test(lower)) return 'adj.';
    if (/(ing|ed)$/.test(lower)) return 'v.';
    return 'n.';
}

function normalisePhonetic(value) {
    if (!value) return '';
    const text = String(value).trim();
    if (!text) return '';
    return text.startsWith('/') ? text : `/${text}/`;
}

function buildPseudoPhonetic(word) {
    const lower = (word || '').toLowerCase().replace(/[^a-z]/g, '');
    if (!lower) return '—';
    const map = { a: 'æ', e: 'e', i: 'ɪ', o: 'ɒ', u: 'ʌ', c: 'k', g: 'g', y: 'i', x: 'ks' };
    const phonetic = lower
        .split('')
        .map((char) => map[char] || char)
        .join('');
    return `/${phonetic}/`;
}

function truncateWords(text, limit) {
    if (!text) return '';
    const words = String(text).split(/\s+/).filter(Boolean);
    if (words.length <= limit) return String(text);
    return `${words.slice(0, limit).join(' ')}…`;
}

function normaliseAnswer(text) {
    return String(text || '').toLowerCase().replace(/[^a-z]/g, '');
}

function formatRelativeTime(timestamp) {
    if (!timestamp) return '刚刚';
    const diff = Date.now() - Number(timestamp);
    if (diff < 60 * 1000) return '刚刚';
    if (diff < 3600 * 1000) return `${Math.floor(diff / (60 * 1000))} 分钟前`;
    if (diff < 24 * 3600 * 1000) return `${Math.floor(diff / (3600 * 1000))} 小时前`;
    return `${Math.floor(diff / (24 * 3600 * 1000))} 天前`;
}

function formatDate(timestamp) {
    if (!timestamp) return '今日';
    const date = new Date(timestamp);
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function capitalize(text) {
    if (!text) return '';
    const str = String(text);
    return str.charAt(0).toUpperCase() + str.slice(1);
}

function stringHash(text) {
    let hash = 0;
    const str = String(text);
    for (let i = 0; i < str.length; i += 1) {
        hash = (hash << 5) - hash + str.charCodeAt(i);
        hash |= 0;
    }
    return Math.abs(hash);
}

function escapeHtml(value) {
    if (value == null) return '';
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function escapeAttribute(value) {
    return escapeHtml(value).replace(/"/g, '&quot;');
}

function safeParseJson(text, fallback) {
    if (!text) return fallback;
    try {
        return JSON.parse(text);
    } catch (error) {
        return fallback;
    }
}

function readFromLocalStorage(key) {
    try {
        return window.localStorage ? window.localStorage.getItem(key) : null;
    } catch (error) {
        return null;
    }
}

function writeToLocalStorage(key, value) {
    try {
        if (window.localStorage) {
            window.localStorage.setItem(key, value);
        }
    } catch (error) {
        console.warn('Unable to write localStorage', error);
    }
}

function removeFromLocalStorage(key) {
    try {
        if (window.localStorage) {
            window.localStorage.removeItem(key);
        }
    } catch (error) {
        console.warn('Unable to remove from localStorage', error);
    }
}
