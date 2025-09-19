"""Chess Academy feature router.

Provides endpoints that power the kid-friendly chess training module.  The
endpoints expose move validation, AI move calculation with multiple difficulty
levels, hint generation, and curated practice puzzles.  The implementation is
fully self-contained so that it does not interfere with other backend modules.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import chess
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/chess", tags=["Chess Academy"])

CHECKMATE_SCORE = 100_000
STARTING_FEN = chess.STARTING_FEN

PIECE_VALUES: Dict[chess.PieceType, int] = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20_000,
}

# Simplified piece-square tables that gently nudge the AI to develop pieces and
# value center control.  Values are expressed from White's perspective and are
# mirrored for Black pieces at runtime.
PAWN_TABLE = [
    0, 0, 0, 0, 0, 0, 0, 0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
    5, 5, 10, 25, 25, 10, 5, 5,
    0, 0, 0, 20, 20, 0, 0, 0,
    5, -5, -10, 0, 0, -10, -5, 5,
    5, 10, 10, -20, -20, 10, 10, 5,
    0, 0, 0, 0, 0, 0, 0, 0,
]
KNIGHT_TABLE = [
    -50, -40, -30, -30, -30, -30, -40, -50,
    -40, -20, 0, 0, 0, 0, -20, -40,
    -30, 0, 10, 15, 15, 10, 0, -30,
    -30, 5, 15, 20, 20, 15, 5, -30,
    -30, 0, 15, 20, 20, 15, 0, -30,
    -30, 5, 10, 15, 15, 10, 5, -30,
    -40, -20, 0, 5, 5, 0, -20, -40,
    -50, -40, -30, -30, -30, -30, -40, -50,
]
BISHOP_TABLE = [
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10, 5, 0, 0, 0, 0, 5, -10,
    -10, 10, 10, 10, 10, 10, 10, -10,
    -10, 0, 10, 10, 10, 10, 0, -10,
    -10, 5, 5, 10, 10, 5, 5, -10,
    -10, 0, 5, 10, 10, 5, 0, -10,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -20, -10, -10, -10, -10, -10, -10, -20,
]
ROOK_TABLE = [
    0, 0, 5, 10, 10, 5, 0, 0,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    5, 10, 10, 10, 10, 10, 10, 5,
    0, 0, 0, 0, 0, 0, 0, 0,
]
QUEEN_TABLE = [
    -20, -10, -10, -5, -5, -10, -10, -20,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -10, 0, 5, 5, 5, 5, 0, -10,
    -5, 0, 5, 5, 5, 5, 0, -5,
    0, 0, 5, 5, 5, 5, 0, -5,
    -10, 5, 5, 5, 5, 5, 0, -10,
    -10, 0, 5, 0, 0, 0, 0, -10,
    -20, -10, -10, -5, -5, -10, -10, -20,
]
KING_TABLE_MID = [
    20, 30, 10, 0, 0, 10, 30, 20,
    20, 20, 0, 0, 0, 0, 20, 20,
    -10, -20, -20, -20, -20, -20, -20, -10,
    -20, -30, -30, -40, -40, -30, -30, -20,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
]
KING_TABLE_END = [
    -50, -40, -30, -20, -20, -30, -40, -50,
    -30, -20, -10, 0, 0, -10, -20, -30,
    -30, -10, 20, 30, 30, 20, -10, -30,
    -30, -10, 30, 40, 40, 30, -10, -30,
    -30, -10, 30, 40, 40, 30, -10, -30,
    -30, -10, 20, 30, 30, 20, -10, -30,
    -30, -30, 0, 0, 0, 0, -30, -30,
    -50, -30, -30, -30, -30, -30, -30, -50,
]

TABLE_LOOKUP = {
    chess.PAWN: PAWN_TABLE,
    chess.KNIGHT: KNIGHT_TABLE,
    chess.BISHOP: BISHOP_TABLE,
    chess.ROOK: ROOK_TABLE,
    chess.QUEEN: QUEEN_TABLE,
}

CENTER_SQUARES = {chess.D4, chess.E4, chess.D5, chess.E5}

DIFFICULTY_SETTINGS = {
    "explorer": {"depth": 1, "max_random_moves": 0.6},
    "beginner": {"depth": 1, "max_random_moves": 0.4},
    "intermediate": {"depth": 2, "max_random_moves": 0.1},
    "advanced": {"depth": 3, "max_random_moves": 0.0},
}

COACH_TIPS = {
    "opening": [
        "开局时试着让两个小兵走到中心，棋盘会更好玩喔！",
        "记得先发展骑士和主教，它们就像你的探索队。",
        "别急着动皇后，先让小伙伴们帮忙打开道路。",
    ],
    "middle": [
        "注意保护国王，可以试着进行王车易位。",
        "看一看对方的棋子在攻击哪里，计划好下一步。",
        "把棋子放在中心，它们会变得更有力量！",
    ],
    "endgame": [
        "进入残局时，国王也可以成为勇敢的冒险家。",
        "记得把兵推进去，如果能升变成皇后就太棒啦！",
        "试着用皇后加国王合作，让对手没有落脚地。",
    ],
}


@dataclass
class MoveScore:
    move: chess.Move
    score: float


class FenRequest(BaseModel):
    fen: str = Field(..., title="Forsyth-Edwards Notation", min_length=1)


class LegalMovesRequest(FenRequest):
    square: str = Field(..., regex=r"^[a-h][1-8]$", description="Square in algebraic notation")


class MoveRequest(FenRequest):
    move: str = Field(..., regex=r"^[a-h][1-8][a-h][1-8][qrbn]?$")
    promotion: Optional[str] = Field(None, regex=r"^[qrbn]$")


class AIMoveRequest(FenRequest):
    difficulty: str = Field("beginner", description="Difficulty label: explorer, beginner, intermediate, advanced")


class HintRequest(FenRequest):
    difficulty: Optional[str] = Field(None, description="Desired difficulty for the hint (defaults to board turn)")


class PracticePuzzle(BaseModel):
    fen: str
    theme: str
    side_to_move: str
    goal: str
    coach_tip: str
    solution: List[str]


class MoveInfo(BaseModel):
    from_square: str
    to_square: str
    uci: str
    san: str
    promotion: Optional[str] = None
    is_capture: bool = False
    gives_check: bool = False
    is_safe: bool = True


class MoveOutcome(BaseModel):
    fen: str
    turn: str
    move: MoveInfo
    halfmove_clock: int
    fullmove_number: int
    status: Dict[str, Optional[str]]
    evaluation: Optional[float] = None
    message: Optional[str] = None


class MoveCollection(BaseModel):
    success: bool
    side_to_move: str
    in_check: bool
    legal_moves: List[MoveInfo]
    message: str


class AIMoveResponse(BaseModel):
    success: bool
    difficulty: str
    depth: int
    move: MoveInfo
    fen: str
    evaluation: float
    coach_message: str
    status: Dict[str, Optional[str]]


class HintResponse(BaseModel):
    success: bool
    hint: MoveInfo
    evaluation: float
    suggestion: str
    status: Dict[str, Optional[str]]


PRACTICE_PUZZLES: List[PracticePuzzle] = [
    PracticePuzzle(
        fen="8/8/8/4k3/4N3/4K3/8/8 w - - 0 1",
        theme="一步将军",
        side_to_move="white",
        goal="白方先行，一步将死黑方。",
        coach_tip="善用你的骑士和国王合作，就能像团队英雄一样解决难题！",
        solution=["e4f6#"],
    ),
    PracticePuzzle(
        fen="6k1/5ppp/8/8/4Q3/5K2/8/6q1 w - - 0 1",
        theme="后王夹击",
        side_to_move="white",
        goal="白方先行，找到一步制胜的妙招。",
        coach_tip="让皇后和国王合作，就像最佳拍档。",
        solution=["e4e8#"],
    ),
    PracticePuzzle(
        fen="8/8/8/2k5/2P5/4K3/8/8 w - - 0 1",
        theme="兵的升变",
        side_to_move="white",
        goal="白方先行，让兵顺利升变并赢得比赛。",
        coach_tip="一步一步往前走，小兵也能成为大英雄！",
        solution=["c4c5", "c5c6", "c6c7", "c7c8Q"],
    ),
]


def _board_from_fen(fen: str) -> chess.Board:
    try:
        board = chess.Board(fen)
    except ValueError as exc:  # pragma: no cover - defensive guardrail
        raise HTTPException(status_code=400, detail=f"Invalid FEN string: {exc}") from exc
    return board


def _mirror_square_for_black(square: chess.Square) -> int:
    return chess.square(chess.square_file(square), 7 - chess.square_rank(square))


def _piece_square_value(piece: chess.Piece, square: chess.Square, endgame: bool) -> int:
    table = TABLE_LOOKUP.get(piece.piece_type)
    if table is None:
        # Kings are handled separately with dedicated tables.
        if piece.piece_type == chess.KING:
            return (KING_TABLE_END if endgame else KING_TABLE_MID)[square]
        return 0

    if piece.color == chess.WHITE:
        return table[square]
    return -table[_mirror_square_for_black(square)]


def _evaluate_board(board: chess.Board) -> float:
    if board.is_checkmate():
        return -CHECKMATE_SCORE
    if board.is_stalemate() or board.is_insufficient_material():
        return 0.0

    white_material = 0
    black_material = 0
    positional_score = 0

    total_minor_pieces = len(board.pieces(chess.BISHOP, chess.WHITE)) + len(board.pieces(chess.KNIGHT, chess.WHITE)) + len(
        board.pieces(chess.BISHOP, chess.BLACK)
    ) + len(board.pieces(chess.KNIGHT, chess.BLACK))
    endgame = total_minor_pieces <= 4 and (len(board.pieces(chess.QUEEN, chess.WHITE)) + len(board.pieces(chess.QUEEN, chess.BLACK))) == 0

    for piece_type, value in PIECE_VALUES.items():
        white_pieces = list(board.pieces(piece_type, chess.WHITE))
        black_pieces = list(board.pieces(piece_type, chess.BLACK))
        white_material += value * len(white_pieces)
        black_material += value * len(black_pieces)
        for square in white_pieces:
            positional_score += _piece_square_value(chess.Piece(piece_type, chess.WHITE), square, endgame)
        for square in black_pieces:
            positional_score += _piece_square_value(chess.Piece(piece_type, chess.BLACK), square, endgame)

    material_score = white_material - black_material

    center_control = 0
    for square in CENTER_SQUARES:
        piece = board.piece_at(square)
        if piece is None:
            continue
        if piece.color == chess.WHITE:
            center_control += 15
        else:
            center_control -= 15

    mobility_bonus = 5 * len(list(board.legal_moves))

    king_safety = 0
    if board.has_kingside_castling_rights(chess.WHITE) or board.has_queenside_castling_rights(chess.WHITE):
        king_safety += 30
    if board.has_kingside_castling_rights(chess.BLACK) or board.has_queenside_castling_rights(chess.BLACK):
        king_safety -= 30

    bishop_pair_bonus = 35 * (
        int(len(board.pieces(chess.BISHOP, chess.WHITE)) >= 2) - int(len(board.pieces(chess.BISHOP, chess.BLACK)) >= 2)
    )

    score_from_white_perspective = (
        material_score
        + positional_score
        + center_control
        + king_safety
        + bishop_pair_bonus
    )

    if board.turn == chess.WHITE:
        return score_from_white_perspective + mobility_bonus
    return -score_from_white_perspective + mobility_bonus


def _move_order_score(board: chess.Board, move: chess.Move) -> int:
    score = 0
    if board.is_capture(move):
        captured_piece = board.piece_at(move.to_square)
        if captured_piece:
            score += 10 * PIECE_VALUES.get(captured_piece.piece_type, 0)
    if board.gives_check(move):
        score += 80
    if board.is_castling(move):
        score += 40
    if chess.square_name(move.to_square) in {"d4", "e4", "d5", "e5"}:
        score += 25
    return score


def _negamax(board: chess.Board, depth: int, alpha: float, beta: float) -> float:
    if depth == 0 or board.is_game_over():
        return _evaluate_board(board)

    max_eval = -math.inf
    ordered_moves = sorted(board.legal_moves, key=lambda mv: _move_order_score(board, mv), reverse=True)
    for move in ordered_moves:
        board.push(move)
        score = -_negamax(board, depth - 1, -beta, -alpha)
        board.pop()
        if score > max_eval:
            max_eval = score
        if max_eval > alpha:
            alpha = max_eval
        if alpha >= beta:
            break
    return max_eval


def _find_best_move(board: chess.Board, depth: int) -> MoveScore:
    alpha = -math.inf
    beta = math.inf
    best_move: Optional[chess.Move] = None
    best_score = -math.inf

    ordered_moves = sorted(board.legal_moves, key=lambda mv: _move_order_score(board, mv), reverse=True)
    for move in ordered_moves:
        board.push(move)
        score = -_negamax(board, depth - 1, -beta, -alpha)
        board.pop()
        if score > best_score or best_move is None:
            best_score = score
            best_move = move
        if score > alpha:
            alpha = score
    if best_move is None:
        raise HTTPException(status_code=400, detail="No legal moves available. The game might be over.")
    return MoveScore(best_move, best_score)


def _is_move_safe(board: chess.Board, move: chess.Move) -> bool:
    board.push(move)
    try:
        if board.is_check():
            return False
        opponent = board.turn
        return not board.is_attacked_by(opponent, move.to_square)
    finally:
        board.pop()


def _serialize_move(board: chess.Board, move: chess.Move) -> MoveInfo:
    san = board.san(move)
    promotion = None
    if move.promotion:
        promotion = chess.piece_symbol(move.promotion)
    return MoveInfo(
        from_square=chess.square_name(move.from_square),
        to_square=chess.square_name(move.to_square),
        uci=move.uci(),
        san=san,
        promotion=promotion,
        is_capture=board.is_capture(move),
        gives_check=board.gives_check(move),
        is_safe=_is_move_safe(board, move),
    )


def _status_payload(board: chess.Board) -> Dict[str, Optional[str]]:
    outcome = board.outcome()
    status = {
        "is_check": board.is_check(),
        "is_checkmate": board.is_checkmate(),
        "is_stalemate": board.is_stalemate(),
        "is_insufficient_material": board.is_insufficient_material(),
        "is_seventyfive_moves": board.is_seventyfive_moves(),
        "is_fivefold_repetition": board.is_fivefold_repetition(),
        "winner": None,
        "result": None,
    }
    if outcome:
        status["winner"] = "white" if outcome.winner == chess.WHITE else "black" if outcome.winner == chess.BLACK else "draw"
        status["result"] = outcome.result()
    return status


def _coach_message(board: chess.Board) -> str:
    total_moves = board.fullmove_number
    if total_moves <= 10:
        return random.choice(COACH_TIPS["opening"])
    if total_moves <= 25:
        return random.choice(COACH_TIPS["middle"])
    return random.choice(COACH_TIPS["endgame"])


def _difficulty_from_label(label: str) -> Tuple[str, Dict[str, float]]:
    canonical = label.lower().strip()
    if canonical not in DIFFICULTY_SETTINGS:
        raise HTTPException(status_code=400, detail=f"Unknown difficulty '{label}'. Choose from {', '.join(DIFFICULTY_SETTINGS)}")
    return canonical, DIFFICULTY_SETTINGS[canonical]


def _choose_beginner_move(board: chess.Board, randomness: float) -> MoveScore:
    moves = list(board.legal_moves)
    random.shuffle(moves)
    safe_moves: List[chess.Move] = []
    smart_moves: List[Tuple[chess.Move, float]] = []
    for move in moves:
        safety = _is_move_safe(board, move)
        board.push(move)
        score = -_evaluate_board(board)
        board.pop()
        if safety:
            safe_moves.append(move)
            smart_moves.append((move, score))
        else:
            smart_moves.append((move, score - 150))

    if safe_moves and random.random() > randomness:
        best_safe = max(safe_moves, key=lambda mv: _move_order_score(board, mv))
        board.push(best_safe)
        score = -_evaluate_board(board)
        board.pop()
        return MoveScore(best_safe, score)

    # Fallback to the highest scoring move according to our evaluation.
    chosen_move, best_score = max(smart_moves, key=lambda item: item[1])
    return MoveScore(chosen_move, best_score)


@router.get("/new-game", response_model=MoveOutcome)
def start_new_game() -> MoveOutcome:
    board = chess.Board()
    first_move = MoveInfo(
        from_square="", to_square="", uci="", san="", promotion=None, is_capture=False, gives_check=False, is_safe=True
    )
    return MoveOutcome(
        fen=board.fen(),
        turn="white",
        move=first_move,
        halfmove_clock=board.halfmove_clock,
        fullmove_number=board.fullmove_number,
        status=_status_payload(board),
        evaluation=_evaluate_board(board),
        message="新的一局已经准备好啦！请选择难度，然后开始你的第一步冒险。",
    )


@router.post("/legal-moves", response_model=MoveCollection)
def legal_moves(payload: LegalMovesRequest) -> MoveCollection:
    board = _board_from_fen(payload.fen)
    if board.is_game_over():
        raise HTTPException(status_code=400, detail="Game is already over. Start a new game to continue playing.")

    square = chess.parse_square(payload.square)
    if board.piece_at(square) is None:
        raise HTTPException(status_code=404, detail="There is no piece on the selected square.")
    if board.piece_at(square).color != board.turn:
        raise HTTPException(status_code=400, detail="It's not that piece's turn to move.")

    moves = [mv for mv in board.legal_moves if mv.from_square == square]
    serialized = [_serialize_move(board, mv) for mv in moves]
    message = (
        "这里是可行走法，点击亮起的格子就能完成移动。"
        if serialized
        else "这个棋子现在不能移动，换一个试试吧。"
    )
    return MoveCollection(
        success=True,
        side_to_move="white" if board.turn == chess.WHITE else "black",
        in_check=board.is_check(),
        legal_moves=serialized,
        message=message,
    )


@router.post("/apply-move", response_model=MoveOutcome)
def apply_move(payload: MoveRequest) -> MoveOutcome:
    board = _board_from_fen(payload.fen)
    try:
        move = chess.Move.from_uci(payload.move)
    except ValueError as exc:  # pragma: no cover - defensive guardrail
        raise HTTPException(status_code=400, detail="Invalid move encoding.") from exc

    if payload.promotion and not move.promotion:
        move = chess.Move.from_uci(payload.move[:4] + payload.promotion)
    if move not in board.legal_moves:
        raise HTTPException(status_code=400, detail="Illegal move for the current board state.")

    move_info = _serialize_move(board, move)
    board.push(move)

    status = _status_payload(board)
    evaluation = _evaluate_board(board)
    next_turn = "white" if board.turn == chess.WHITE else "black"
    message = _coach_message(board)

    return MoveOutcome(
        fen=board.fen(),
        turn=next_turn,
        move=move_info,
        halfmove_clock=board.halfmove_clock,
        fullmove_number=board.fullmove_number,
        status=status,
        evaluation=evaluation,
        message=message,
    )


@router.post("/ai-move", response_model=AIMoveResponse)
def ai_move(payload: AIMoveRequest) -> AIMoveResponse:
    board = _board_from_fen(payload.fen)
    if board.is_game_over():
        raise HTTPException(status_code=400, detail="Game is already finished. No moves available.")

    label, settings = _difficulty_from_label(payload.difficulty)
    randomness = settings.get("max_random_moves", 0.0)
    depth = settings.get("depth", 1)

    if label in {"explorer", "beginner"} and random.random() < randomness:
        choice = _choose_beginner_move(board, randomness)
    else:
        choice = _find_best_move(board, depth)

    move_info = _serialize_move(board, choice.move)
    board.push(choice.move)
    status = _status_payload(board)
    evaluation = _evaluate_board(board)

    coach_message = _coach_message(board)
    if status.get("is_checkmate"):
        coach_message = "太棒啦！这是致胜一击。再来一局挑战自己吧！"

    return AIMoveResponse(
        success=True,
        difficulty=label,
        depth=depth,
        move=move_info,
        fen=board.fen(),
        evaluation=evaluation,
        coach_message=coach_message,
        status=status,
    )


@router.post("/hint", response_model=HintResponse)
def hint(payload: HintRequest) -> HintResponse:
    board = _board_from_fen(payload.fen)
    if board.is_game_over():
        raise HTTPException(status_code=400, detail="Game is already finished.")

    difficulty_label = payload.difficulty or ("advanced" if board.fullmove_number > 20 else "intermediate")
    label, settings = _difficulty_from_label(difficulty_label)
    depth = max(1, settings.get("depth", 1))

    suggestion = _find_best_move(board, depth)
    move_info = _serialize_move(board, suggestion.move)
    status = _status_payload(board)
    evaluation = suggestion.score
    guidance = (
        "这个走法可以守住你的国王并准备反击，试试看！"
        if label in {"explorer", "beginner"}
        else "这是当前最聪明的计划，可以帮助你获得更好的局面。"
    )
    return HintResponse(
        success=True,
        hint=move_info,
        evaluation=evaluation,
        suggestion=guidance,
        status=status,
    )


@router.get("/practice-puzzle", response_model=PracticePuzzle)
def practice_puzzle() -> PracticePuzzle:
    return random.choice(PRACTICE_PUZZLES)
