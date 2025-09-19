checkAuth();

const API_BASE = '/api/chess';
const PIECE_GLYPHS = {
    P: '♙', N: '♘', B: '♗', R: '♖', Q: '♕', K: '♔',
    p: '♟︎', n: '♞', b: '♝', r: '♜', q: '♛', k: '♚'
};
const PIECE_NAMES = {
    P: '白兵', N: '白马', B: '白主教', R: '白战车', Q: '白皇后', K: '白国王',
    p: '黑兵', n: '黑马', b: '黑主教', r: '黑战车', q: '黑皇后', k: '黑国王'
};
const STARTING_COUNTS = {
    P: 8, N: 2, B: 2, R: 2, Q: 1, K: 1,
    p: 8, n: 2, b: 2, r: 2, q: 1, k: 1
};

const state = {
    fen: '',
    turn: 'white',
    mode: 'ai',
    difficulty: 'explorer',
    moveHistory: [],
    status: {},
    coachMessage: '',
    lastMove: null,
    puzzle: null,
    puzzleActive: false,
    stack: [],
};

let orientation = 'white';
let selectedSquare = null;
let legalMoves = [];
let interactionLocked = false;

const boardElement = document.getElementById('chess-board');
const statusBanner = document.getElementById('status-banner');
const turnIndicator = document.getElementById('turn-indicator');
const coachMessageEl = document.getElementById('coach-message');
const statusGridEl = document.getElementById('status-grid');
const moveHistoryEl = document.getElementById('move-history');
const whiteCapturedEl = document.getElementById('white-captured');
const blackCapturedEl = document.getElementById('black-captured');
const puzzleCardEl = document.getElementById('puzzle-card');
const puzzleMetaEl = document.getElementById('puzzle-meta');
const puzzleGoalEl = document.getElementById('puzzle-goal');

const modeButtons = Array.from(document.querySelectorAll('#mode-card button[data-mode]'));
const difficultyButtons = Array.from(document.querySelectorAll('.difficulty-buttons button[data-difficulty]'));

const newGameBtn = document.getElementById('new-game-btn');
const undoBtn = document.getElementById('undo-btn');
const flipBoardBtn = document.getElementById('flip-board-btn');
const hintBtn = document.getElementById('hint-btn');
const puzzleBtn = document.getElementById('puzzle-btn');
const loadPuzzleBtn = document.getElementById('load-puzzle-btn');
const closePuzzleBtn = document.getElementById('close-puzzle-btn');

function setStatusBanner(message, tone = 'info') {
    statusBanner.textContent = message;
    statusBanner.className = `board-legend status-${tone}`;
}

function lockInteraction(message = '') {
    interactionLocked = true;
    if (message) {
        setStatusBanner(message, 'info');
    }
}

function unlockInteraction(message = '') {
    interactionLocked = false;
    if (message) {
        setStatusBanner(message, 'info');
    }
}

function parseFenBoard(fen) {
    const [placement] = fen.split(' ');
    const rows = placement.split('/');
    return rows.map(row => {
        const result = [];
        for (const char of row) {
            if (/\d/.test(char)) {
                const empty = parseInt(char, 10);
                for (let i = 0; i < empty; i += 1) {
                    result.push('.');
                }
            } else {
                result.push(char);
            }
        }
        return result;
    });
}

function parseFenTurn(fen) {
    try {
        const parts = fen.split(' ');
        return parts[1] === 'w' ? 'white' : 'black';
    } catch (error) {
        console.warn('Unable to parse FEN turn', error);
        return 'white';
    }
}

function getPieceMap(fen) {
    const board = parseFenBoard(fen);
    const files = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];
    const map = {};
    for (let rankIndex = 0; rankIndex < 8; rankIndex += 1) {
        const rankNumber = 8 - rankIndex;
        const row = board[rankIndex];
        for (let fileIndex = 0; fileIndex < 8; fileIndex += 1) {
            const piece = row[fileIndex];
            if (piece && piece !== '.') {
                const square = `${files[fileIndex]}${rankNumber}`;
                map[square] = piece;
            }
        }
    }
    return map;
}

function findKingSquare(fen, color) {
    const pieceToFind = color === 'white' ? 'K' : 'k';
    const map = getPieceMap(fen);
    return Object.entries(map).find(([, piece]) => piece === pieceToFind)?.[0] || null;
}

function renderBoard() {
    const board = parseFenBoard(state.fen);
    const ranks = orientation === 'white' ? ['8', '7', '6', '5', '4', '3', '2', '1'] : ['1', '2', '3', '4', '5', '6', '7', '8'];
    const files = orientation === 'white' ? ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'] : ['h', 'g', 'f', 'e', 'd', 'c', 'b', 'a'];

    boardElement.innerHTML = '';

    ranks.forEach((rank, rankIndex) => {
        const sourceRankIndex = orientation === 'white' ? rankIndex : 7 - rankIndex;
        const row = board[sourceRankIndex];
        files.forEach((file, fileIndex) => {
            const sourceFileIndex = orientation === 'white' ? fileIndex : 7 - fileIndex;
            const piece = row[sourceFileIndex];
            const square = document.createElement('div');
            square.classList.add('square');
            square.dataset.square = `${file}${rank}`;
            square.dataset.color = (rankIndex + fileIndex) % 2 === 0 ? 'light' : 'dark';
            if (piece && piece !== '.') {
                square.textContent = PIECE_GLYPHS[piece] || '';
                square.dataset.piece = piece;
                square.title = PIECE_NAMES[piece] || '棋子';
            } else {
                square.textContent = '';
                square.dataset.piece = '';
            }
            boardElement.appendChild(square);
        });
    });

    highlightSpecialSquares();
}

function highlightSpecialSquares() {
    const squares = boardElement.querySelectorAll('.square');
    squares.forEach(square => {
        square.classList.remove('selected', 'highlight-move', 'highlight-capture', 'in-check', 'last-move-from', 'last-move-to');
    });

    if (selectedSquare) {
        const selectedEl = boardElement.querySelector(`[data-square="${selectedSquare}"]`);
        if (selectedEl) {
            selectedEl.classList.add('selected');
        }
    }

    legalMoves.forEach(move => {
        const target = boardElement.querySelector(`[data-square="${move.to_square}"]`);
        if (target) {
            target.classList.add('highlight-move');
            if (move.is_capture) {
                target.classList.add('highlight-capture');
            }
        }
    });

    if (state.lastMove) {
        const fromEl = boardElement.querySelector(`[data-square="${state.lastMove.from_square}"]`);
        const toEl = boardElement.querySelector(`[data-square="${state.lastMove.to_square}"]`);
        if (fromEl) {
            fromEl.classList.add('last-move-from');
        }
        if (toEl) {
            toEl.classList.add('last-move-to');
        }
    }

    if (state.status?.is_check) {
        const kingSquare = findKingSquare(state.fen, state.turn);
        if (kingSquare) {
            const kingEl = boardElement.querySelector(`[data-square="${kingSquare}"]`);
            if (kingEl) {
                kingEl.classList.add('in-check');
            }
        }
    }
}

function recordMove(actor, san) {
    if (!san) {
        return;
    }
    if (actor === 'white') {
        state.moveHistory.push({
            moveNumber: state.moveHistory.length + 1,
            white: san,
            black: ''
        });
    } else {
        if (!state.moveHistory.length) {
            state.moveHistory.push({ moveNumber: 1, white: '…', black: san });
        } else {
            state.moveHistory[state.moveHistory.length - 1].black = san;
        }
    }
}

function updateMoveHistory() {
    moveHistoryEl.innerHTML = '';
    state.moveHistory.forEach(entry => {
        const li = document.createElement('li');
        const parts = [];
        parts.push(`${entry.moveNumber}.`);
        parts.push(entry.white || '…');
        if (entry.black) {
            parts.push(entry.black);
        }
        li.textContent = parts.join(' ');
        moveHistoryEl.appendChild(li);
    });
    moveHistoryEl.scrollTop = moveHistoryEl.scrollHeight;
}

function computeCapturedPieces(fen) {
    const boardMap = getPieceMap(fen);
    const whiteCounts = { P: 0, N: 0, B: 0, R: 0, Q: 0, K: 0 };
    const blackCounts = { p: 0, n: 0, b: 0, r: 0, q: 0, k: 0 };

    Object.values(boardMap).forEach(piece => {
        if (piece === piece.toUpperCase()) {
            whiteCounts[piece] += 1;
        } else {
            blackCounts[piece] += 1;
        }
    });

    const capturedByWhite = { q: 0, r: 0, b: 0, n: 0, p: 0 };
    const capturedByBlack = { Q: 0, R: 0, B: 0, N: 0, P: 0 };

    Object.entries({ q: 'q', r: 'r', b: 'b', n: 'n', p: 'p' }).forEach(([key, piece]) => {
        capturedByWhite[key] = STARTING_COUNTS[piece] - blackCounts[piece];
    });
    Object.entries({ Q: 'Q', R: 'R', B: 'B', N: 'N', P: 'P' }).forEach(([key, piece]) => {
        capturedByBlack[key] = STARTING_COUNTS[piece] - whiteCounts[piece];
    });

    return { capturedByWhite, capturedByBlack };
}

function formatCaptured(map, order) {
    const parts = [];
    order.forEach(piece => {
        const count = map[piece] || 0;
        if (count > 0) {
            const glyph = PIECE_GLYPHS[piece];
            if (count >= 4) {
                parts.push(`${glyph}×${count}`);
            } else {
                parts.push(glyph.repeat(count));
            }
        }
    });
    return parts.length ? parts.join(' ') : '暂无';
}

function updateCapturedPieces() {
    const { capturedByWhite, capturedByBlack } = computeCapturedPieces(state.fen);
    whiteCapturedEl.textContent = formatCaptured(capturedByWhite, ['q', 'r', 'b', 'n', 'p']);
    blackCapturedEl.textContent = formatCaptured(capturedByBlack, ['Q', 'R', 'B', 'N', 'P']);
}

function updateCoachMessage(message) {
    coachMessageEl.textContent = message || '星际教练正在观察棋局，等你走出第一步就会有暖心建议。';
}

function updateStatusGrid() {
    const items = [];
    items.push({ label: '当前轮到', value: state.turn === 'white' ? '白方' : '黑方' });
    if (state.status?.is_checkmate) {
        items.push({ label: '胜负结果', value: state.status.winner ? `${state.status.winner === 'white' ? '白方' : '黑方'}胜利` : '平局' });
    } else if (state.status?.is_stalemate) {
        items.push({ label: '局面', value: '僵局，双方平手' });
    } else if (state.status?.is_check) {
        items.push({ label: '警报', value: '当前一方被将军！' });
    }
    if (state.status?.is_insufficient_material) {
        items.push({ label: '素材', value: '双方棋子不足以将死' });
    }
    if (state.puzzleActive) {
        items.push({ label: '模式', value: '谜题挑战中' });
    } else {
        items.push({ label: '模式', value: state.mode === 'ai' ? '与智能棋友对战' : '同桌轮流对战' });
    }

    statusGridEl.innerHTML = '';
    items.forEach(item => {
        const div = document.createElement('div');
        div.className = 'status-pill';
        div.textContent = `${item.label}: ${item.value}`;
        statusGridEl.appendChild(div);
    });
}

function updateTurnIndicator() {
    const friendly = state.turn === 'white' ? '白方' : '黑方';
    if (state.status?.is_checkmate) {
        turnIndicator.textContent = state.status.winner ? `${state.status.winner === 'white' ? '白方' : '黑方'}赢得胜利！` : '和棋结束。';
    } else if (state.status?.is_stalemate) {
        turnIndicator.textContent = '棋局僵住啦，双方握手言和。';
    } else {
        turnIndicator.textContent = `轮到${friendly}出招，加油！`;
    }
}

function clearSelection() {
    selectedSquare = null;
    legalMoves = [];
    highlightSpecialSquares();
}

function captureSnapshot() {
    const snapshot = {
        fen: state.fen,
        turn: state.turn,
        mode: state.mode,
        difficulty: state.difficulty,
        moveHistory: state.moveHistory.map(entry => ({ ...entry })),
        status: { ...state.status },
        coachMessage: state.coachMessage,
        lastMove: state.lastMove ? { ...state.lastMove } : null,
        puzzle: state.puzzle ? { ...state.puzzle } : null,
        puzzleActive: state.puzzleActive,
        orientation,
    };
    state.stack.push(snapshot);
}

function applySnapshot(snapshot) {
    state.fen = snapshot.fen;
    state.turn = snapshot.turn;
    state.mode = snapshot.mode;
    state.difficulty = snapshot.difficulty;
    state.moveHistory = snapshot.moveHistory.map(entry => ({ ...entry }));
    state.status = { ...snapshot.status };
    state.coachMessage = snapshot.coachMessage;
    state.lastMove = snapshot.lastMove ? { ...snapshot.lastMove } : null;
    state.puzzle = snapshot.puzzle ? { ...snapshot.puzzle } : null;
    state.puzzleActive = snapshot.puzzleActive;
    orientation = snapshot.orientation;
    selectedSquare = null;
    legalMoves = [];
    updateAll();
}

function undoLastMove() {
    if (state.stack.length <= 1) {
        setStatusBanner('已经回到最初的状态，无法再悔棋啦。', 'warning');
        return;
    }
    state.stack.pop();
    const snapshot = state.stack[state.stack.length - 1];
    applySnapshot(snapshot);
    setStatusBanner('悔棋成功，我们回到了前一步。', 'success');
}

function isGameOver() {
    return Boolean(state.status?.is_checkmate || state.status?.is_stalemate || state.status?.winner);
}

function updateAll() {
    renderBoard();
    updateMoveHistory();
    updateCapturedPieces();
    updateCoachMessage(state.coachMessage);
    updateStatusGrid();
    updateTurnIndicator();
    if (state.puzzleActive) {
        showPuzzleCard(state.puzzle);
    } else {
        hidePuzzleCard();
    }
}

async function apiGet(path) {
    const response = await fetch(`${API_BASE}${path}`);
    if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || data.error || '请求失败');
    }
    return response.json();
}

async function apiPost(path, payload) {
    const response = await fetch(`${API_BASE}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || data.error || '请求失败');
    }
    return response.json();
}

async function startNewGame() {
    try {
        lockInteraction('正在设置新棋局...');
        const data = await apiGet('/new-game');
        state.fen = data.fen;
        state.turn = data.turn;
        state.status = data.status || {};
        state.moveHistory = [];
        state.coachMessage = data.message;
        state.lastMove = null;
        state.puzzle = null;
        state.puzzleActive = false;
        orientation = 'white';
        state.stack = [];
        selectedSquare = null;
        legalMoves = [];
        updateAll();
        captureSnapshot();
        unlockInteraction('新局已准备就绪，白方先行。');
    } catch (error) {
        console.error(error);
        unlockInteraction('启动棋局时出现小问题，请稍后再试。');
    }
}

function setMode(mode, { fromPuzzle = false } = {}) {
    state.mode = mode;
    if (!fromPuzzle) {
        state.puzzleActive = false;
        state.puzzle = null;
    }
    modeButtons.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.mode === mode);
    });
    updateStatusGrid();
}

function setDifficulty(level) {
    state.difficulty = level;
    difficultyButtons.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.difficulty === level);
    });
}

async function requestLegalMoves(square) {
    try {
        lockInteraction('正在分析这个棋子的走法...');
        const data = await apiPost('/legal-moves', { fen: state.fen, square });
        legalMoves = data.legal_moves;
        selectedSquare = square;
        setStatusBanner(data.message, 'info');
        unlockInteraction();
        highlightSpecialSquares();
    } catch (error) {
        console.error(error);
        unlockInteraction(error.message || '无法获取走法');
        clearSelection();
    }
}

function requiresPromotion(moveCandidates) {
    return moveCandidates.some(move => Boolean(move.promotion));
}

function buildPromotionOverlay(color, candidates) {
    return new Promise(resolve => {
        const overlay = document.createElement('div');
        overlay.className = 'promotion-overlay';
        const dialog = document.createElement('div');
        dialog.className = 'promotion-dialog';
        const title = document.createElement('h3');
        title.textContent = '选择想升变的棋子';
        const subtitle = document.createElement('p');
        subtitle.textContent = color === 'white' ? '白兵到达终点，可以变身啦！' : '黑兵到达终点，可以变身啦！';
        const options = document.createElement('div');
        options.className = 'promotion-options';
        const promotionOrder = ['q', 'r', 'b', 'n'];
        promotionOrder.forEach(symbol => {
            const candidate = candidates.find(move => move.promotion === symbol) || candidates[0];
            const btn = document.createElement('button');
            btn.className = 'secondary';
            btn.dataset.promotion = candidate.promotion || 'q';
            btn.textContent = symbol === 'q' ? '变成皇后' : symbol === 'r' ? '变成战车' : symbol === 'b' ? '变成主教' : '变成骑士';
            btn.addEventListener('click', () => {
                document.body.removeChild(overlay);
                resolve(candidate);
            });
            options.appendChild(btn);
        });
        dialog.appendChild(title);
        dialog.appendChild(subtitle);
        dialog.appendChild(options);
        overlay.appendChild(dialog);
        document.body.appendChild(overlay);
    });
}

async function submitMove(moveInfo, actor) {
    try {
        const payload = { fen: state.fen, move: moveInfo.uci };
        if (moveInfo.promotion) {
            payload.promotion = moveInfo.promotion;
        }
        const data = await apiPost('/apply-move', payload);
        state.fen = data.fen;
        state.turn = data.turn;
        state.status = data.status || {};
        state.coachMessage = data.message || state.coachMessage;
        state.lastMove = moveInfo;
        recordMove(actor, moveInfo.san);
        updateAll();
        captureSnapshot();
        if (typeof usageTracker !== 'undefined' && usageTracker.recordUsage) {
            await usageTracker.recordUsage('chess-academy', 'local-engine', state.difficulty, 0, 0);
        }
        return data;
    } catch (error) {
        console.error(error);
        setStatusBanner(error.message || '这一步似乎行不通，换个想法试试吧。', 'warning');
        throw error;
    }
}

async function requestAiMove() {
    const actor = state.turn;
    try {
        setStatusBanner('星际棋友正在思考最聪明的走法...', 'info');
        const data = await apiPost('/ai-move', { fen: state.fen, difficulty: state.difficulty });
        state.fen = data.fen;
        state.turn = parseFenTurn(data.fen);
        state.status = data.status || {};
        state.coachMessage = data.coach_message || state.coachMessage;
        state.lastMove = data.move;
        recordMove(actor, data.move.san);
        updateAll();
        captureSnapshot();
        if (typeof usageTracker !== 'undefined' && usageTracker.recordUsage) {
            await usageTracker.recordUsage('chess-academy', 'python-chess', state.difficulty, 0, 0);
        }
        setStatusBanner('轮到你啦，星际教练等着看你的妙手。', 'success');
    } catch (error) {
        console.error(error);
        setStatusBanner(error.message || '星际棋友暂时没有回应，请再试一次。', 'warning');
    }
}

async function handleMoveSelection(targetSquare) {
    const candidates = legalMoves.filter(move => move.to_square === targetSquare);
    if (!candidates.length) {
        return;
    }
    let chosenMove = candidates[0];
    if (candidates.length > 1 && requiresPromotion(candidates)) {
        chosenMove = await buildPromotionOverlay(state.turn, candidates);
    }
    try {
        lockInteraction('星际教练正在确认你的走法...');
        const actor = state.turn;
        const response = await submitMove(chosenMove, actor);
        clearSelection();
        if (state.puzzleActive) {
            unlockInteraction('继续完成谜题目标吧！');
            return;
        }
        if (state.mode === 'ai' && !isGameOver()) {
            await requestAiMove();
        }
        unlockInteraction('轮到你继续规划啦！');
    } catch (error) {
        console.error(error);
        unlockInteraction(error.message || '请再尝试其它走法。');
    }
}

function squareBelongsToCurrentPlayer(piece) {
    if (!piece) {
        return false;
    }
    const isWhitePiece = piece === piece.toUpperCase();
    return (state.turn === 'white' && isWhitePiece) || (state.turn === 'black' && !isWhitePiece);
}

async function handleSquareClick(event) {
    if (interactionLocked) {
        return;
    }
    const square = event.target.closest('.square');
    if (!square) {
        return;
    }
    const squareName = square.dataset.square;
    if (!squareName) {
        return;
    }

    if (selectedSquare && squareName === selectedSquare) {
        clearSelection();
        return;
    }

    const targetIsLegal = legalMoves.some(move => move.to_square === squareName);
    if (selectedSquare && targetIsLegal) {
        await handleMoveSelection(squareName);
        return;
    }

    const piece = square.dataset.piece;
    if (!piece) {
        clearSelection();
        return;
    }
    if (!squareBelongsToCurrentPlayer(piece)) {
        setStatusBanner('现在轮到另一方啦，耐心等待一下。', 'warning');
        clearSelection();
        return;
    }
    await requestLegalMoves(squareName);
}

async function requestHint() {
    try {
        lockInteraction('星际教练正在为你观察局势...');
        const data = await apiPost('/hint', { fen: state.fen, difficulty: state.difficulty });
        setStatusBanner(data.suggestion, 'success');
        legalMoves = [data.hint];
        selectedSquare = data.hint.from_square;
        highlightSpecialSquares();
        updateCoachMessage(`${data.suggestion} 推荐走法：${data.hint.san}`);
        unlockInteraction();
    } catch (error) {
        console.error(error);
        unlockInteraction(error.message || '暂时无法提供提示，请稍后再试。');
    }
}

function showPuzzleCard(puzzle) {
    if (!puzzle) {
        return;
    }
    puzzleCardEl.style.display = 'block';
    puzzleMetaEl.innerHTML = '';
    const theme = document.createElement('span');
    theme.textContent = `主题：${puzzle.theme}`;
    const side = document.createElement('span');
    side.textContent = `先手方：${puzzle.side_to_move === 'white' ? '白方' : '黑方'}`;
    const tip = document.createElement('span');
    tip.textContent = `教练小贴士：${puzzle.coach_tip}`;
    puzzleMetaEl.appendChild(theme);
    puzzleMetaEl.appendChild(side);
    puzzleMetaEl.appendChild(tip);
    puzzleGoalEl.textContent = puzzle.goal;
}

function hidePuzzleCard() {
    puzzleCardEl.style.display = 'none';
    puzzleMetaEl.innerHTML = '';
    puzzleGoalEl.textContent = '';
}

async function activatePuzzle() {
    try {
        lockInteraction('星际教练正在挑选今日谜题...');
        const puzzle = await apiGet('/practice-puzzle');
        state.puzzle = puzzle;
        state.puzzleActive = true;
        state.stack = [];
        state.fen = puzzle.fen;
        state.turn = parseFenTurn(puzzle.fen);
        state.status = {};
        state.coachMessage = puzzle.coach_tip;
        state.moveHistory = [];
        state.lastMove = null;
        selectedSquare = null;
        legalMoves = [];
        setMode('friend', { fromPuzzle: true });
        updateAll();
        captureSnapshot();
        unlockInteraction('谜题准备完毕，按照目标尝试解答吧！');
    } catch (error) {
        console.error(error);
        unlockInteraction('获取谜题失败，请稍后再试。');
    }
}

function closePuzzle() {
    state.puzzleActive = false;
    state.puzzle = null;
    hidePuzzleCard();
    setMode('ai');
    startNewGame();
}

function attachEvents() {
    boardElement.addEventListener('click', event => {
        event.preventDefault();
        handleSquareClick(event);
    });
    newGameBtn.addEventListener('click', () => {
        if (interactionLocked) { return; }
        state.puzzleActive = false;
        state.puzzle = null;
        hidePuzzleCard();
        startNewGame();
    });
    undoBtn.addEventListener('click', () => {
        if (interactionLocked) { return; }
        undoLastMove();
    });
    flipBoardBtn.addEventListener('click', () => {
        orientation = orientation === 'white' ? 'black' : 'white';
        renderBoard();
    });
    hintBtn.addEventListener('click', () => {
        if (interactionLocked) { return; }
        requestHint();
    });
    puzzleBtn.addEventListener('click', () => {
        if (interactionLocked) { return; }
        activatePuzzle();
    });
    loadPuzzleBtn.addEventListener('click', () => {
        if (interactionLocked) { return; }
        activatePuzzle();
    });
    closePuzzleBtn.addEventListener('click', () => {
        if (interactionLocked) { return; }
        closePuzzle();
    });
    modeButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const mode = btn.dataset.mode;
            setMode(mode);
        });
    });
    difficultyButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            setDifficulty(btn.dataset.difficulty);
        });
    });
}

async function init() {
    attachEvents();
    setMode(state.mode);
    setDifficulty(state.difficulty);
    await startNewGame();
}

init();
