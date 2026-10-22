#include "hive/Game.h"

#include <algorithm>
#include <sstream>
#include <stdexcept>
#include <tuple>
#include <utility>

#include "hive/MosquitoAbility.h"
#include "hive/movement/StrategyFactory.h"

namespace {
auto moveSortKey(const Move &move)
{
    return std::visit([](const auto &action) {
        using T = std::decay_t<decltype(action)>;
        if constexpr (std::is_same_v<T, Placement>)
        {
            return std::tuple<int, int, int, int, int, int, int, int, int>{
                0, static_cast<int>(action.type), action.destination.q, action.destination.r,
                0, 0, 0, 0, 0};
        }
        else if constexpr (std::is_same_v<T, Movement>)
        {
            return std::tuple<int, int, int, int, int, int, int, int, int>{
                1, action.from.q, action.from.r, action.destination.q, action.destination.r,
                0, 0, 0, 0};
        }
        else if constexpr (std::is_same_v<T, PillbugThrow>)
        {
            return std::tuple<int, int, int, int, int, int, int, int, int>{
                2, action.pillbug.q, action.pillbug.r, action.victim.q, action.victim.r,
                action.destination.q, action.destination.r, 0, 0};
        }
        else if constexpr (std::is_same_v<T, MosquitoMovement>)
        {
            return std::tuple<int, int, int, int, int, int, int, int, int>{
                3, action.from.q, action.from.r, static_cast<int>(action.imitating),
                action.destination.q, action.destination.r, 0, 0, 0};
        }
        else
        {
            return std::tuple<int, int, int, int, int, int, int, int, int>{4, 0, 0, 0, 0, 0, 0, 0, 0};
        }
    }, move);
}

int ownTurnNumber(Color color, int globalTurn)
{
    return color == Color::White ? (globalTurn + 1) / 2 : globalTurn / 2;
}
} // namespace

Game::Game(Ruleset ruleset)
    : ruleset_(std::move(ruleset)),
      white_(Color::White, ruleset_.piecesPerPlayer),
      black_(Color::Black, ruleset_.piecesPerPlayer)
{
    if (ruleset_.id.empty() || ruleset_.queenMustBePlacedByOwnTurn < 1 ||
        ruleset_.repetitionDrawOccurrences < 0 || ruleset_.queenSurroundCount < 1 ||
        ruleset_.queenSurroundCount > 6 || ruleset_.maxPlies < 0)
    {
        throw std::invalid_argument("Invalid Hive ruleset");
    }
    for (int count : ruleset_.piecesPerPlayer)
    {
        if (count < 0)
        {
            throw std::invalid_argument("Ruleset inventory counts cannot be negative");
        }
    }
    if (ruleset_.repetitionDrawOccurrences > 0)
    {
        repetitionCounts_.emplace(positionKey(), 1);
    }
}

Game::Game(const Game &other)
    : ruleset_(other.ruleset_),
      white_(other.white_),
      black_(other.black_),
      turn_(other.turn_),
      turnNumber_(other.turnNumber_),
      status_(other.status_),
      repetitionCounts_(other.repetitionCounts_)
{
    std::unordered_map<const Piece *, Piece *> replacements;
    pieces_.reserve(other.pieces_.size());
    for (const auto &piece : other.pieces_)
    {
        auto copy = std::make_unique<Piece>(*piece);
        replacements.emplace(piece.get(), copy.get());
        pieces_.push_back(std::move(copy));
    }
    board_ = other.board_.remapPieces(replacements);
    lastMoved_ = other.lastMoved_ == nullptr ? nullptr : replacements.at(other.lastMoved_);
}

Game &Game::operator=(const Game &other)
{
    if (this != &other)
    {
        Game copy(other);
        swap(copy);
    }
    return *this;
}

void Game::swap(Game &other) noexcept
{
    using std::swap;
    swap(ruleset_, other.ruleset_);
    swap(board_, other.board_);
    swap(white_, other.white_);
    swap(black_, other.black_);
    swap(turn_, other.turn_);
    swap(turnNumber_, other.turnNumber_);
    swap(status_, other.status_);
    swap(lastMoved_, other.lastMoved_);
    swap(pieces_, other.pieces_);
    swap(repetitionCounts_, other.repetitionCounts_);
}

const Ruleset &Game::ruleset() const
{
    return ruleset_;
}

int Game::nextPieceOrdinal(PieceType type) const
{
    const std::size_t index = pieceTypeIndex(type);
    return ruleset_.piecesPerPlayer[index] - currentPlayer().remaining(type);
}

Color Game::turn() const
{
    return turn_;
}

int Game::turnNumber() const
{
    return turnNumber_;
}

GameStatus Game::status() const
{
    return status_;
}

std::optional<Color> Game::winner() const
{
    if (status_ == GameStatus::WhiteWins)
    {
        return Color::White;
    }
    if (status_ == GameStatus::BlackWins)
    {
        return Color::Black;
    }
    return std::nullopt;
}

const Board &Game::board() const
{
    return board_;
}

const Player &Game::player(Color color) const
{
    return color == Color::White ? white_ : black_;
}

Piece *Game::lastMoved() const
{
    return lastMoved_;
}

Player &Game::currentPlayer()
{
    return turn_ == Color::White ? white_ : black_;
}

const Player &Game::currentPlayer() const
{
    return turn_ == Color::White ? white_ : black_;
}

std::vector<Move> Game::legalMoves() const
{
    std::vector<Move> moves;

    if (status_ != GameStatus::Ongoing)
    {
        return moves;
    }

    const Player &current = currentPlayer();
    const std::vector<Hex> spots = board_.legalPlacementSpots(turn_);

    const int playerTurnCount = ownTurnNumber(turn_, turnNumber_);
    const bool mustPlaceQueen = playerTurnCount >= ruleset_.queenMustBePlacedByOwnTurn &&
                                !current.hasPlacedQueen();

    std::vector<PieceType> types = mustPlaceQueen
                                       ? std::vector<PieceType>{PieceType::Queen}
                                       : current.availableTypes();
    if (ruleset_.forbidQueenOnFirstOwnTurn && playerTurnCount == 1 &&
        !current.hasPlacedQueen())
    {
        types.erase(std::remove(types.begin(), types.end(), PieceType::Queen), types.end());
    }

    for (PieceType type : types)
    {
        for (const Hex &spot : spots)
        {
            moves.push_back(Placement{type, spot});
        }
    }

    if (current.hasPlacedQueen())
    {
        for (const Hex &hex : board_.occupiedHexes())
        {
            Piece *piece = board_.topAt(hex);
            if (piece->color != turn_)
            {
                continue;
            }
            if (piece == lastMoved_)
            {
                continue; // neither moving nor using its ability
            }

            addMoves(moves, hex, *piece);
        }
    }

    if (moves.empty() && ruleset_.passWhenNoLegalMove)
    {
        moves.emplace_back(Pass{});
    }
    std::sort(moves.begin(), moves.end(), [](const Move &a, const Move &b) {
        return moveSortKey(a) < moveSortKey(b);
    });
    return moves;
}

void Game::addMoves(std::vector<Move> &moves, const Hex &hex, const Piece &piece) const
{
    if (piece.type == PieceType::Mosquito)
    {
        addMosquitoMoves(moves, hex, piece);
        return;
    }

    // Estar clavada impide irse del casillero, no usar una habilidad que la deja
    // donde está: por eso se chequea aparte de la rama del PillbugThrow de abajo.
    if (board_.canMove(hex))
    {
        for (const Hex &destination : piece.legalMoves(board_, hex))
        {
            moves.push_back(Movement{hex, destination});
        }
    }

    if (piece.type == PieceType::Pillbug)
    {
        for (const PillbugThrow &t : pillbugThrows(board_, hex, lastMoved_))
        {
            moves.push_back(t);
        }
    }
}

void Game::addMosquitoMoves(std::vector<Move> &moves, const Hex &hex, const Piece &piece) const
{
    if (board_.stackHeight(hex) > 1)
    {
        // En altura: piece.movement ya tiene una BeetleMovement, puesta cuando se
        // subió (ver la rama de MosquitoMovement en applyMove). Mientras está
        // arriba no elige a quién imitar: va por el mismo camino genérico que
        // cualquier otra pieza.
        if (board_.canMove(hex))
        {
            for (const Hex &destination : piece.legalMoves(board_, hex))
            {
                moves.push_back(Movement{hex, destination});
            }
        }
        return;
    }

    const std::vector<PieceType> imitating = imitatableTypes(board_, hex);

    // El bicho bolita ya no se saltea en este loop: su movimiento propio es
    // QueenMovement (ver StrategyFactory), así que imitarlo acá produce entradas
    // MosquitoMovement{imitating=Pillbug} igual que cualquier otro tipo vecino
    // —exactamente lo que ofrecería el Movement de un bicho bolita de verdad—. El
    // lanzamiento (abajo) es una habilidad aparte y adicional, no una alternativa
    // a esto.
    if (board_.canMove(hex))
    {
        for (PieceType type : imitating)
        {
            auto strategy = createMovementStrategy(type);
            for (const Hex &destination : strategy->moves(board_, hex, piece))
            {
                moves.push_back(MosquitoMovement{hex, type, destination});
            }
        }
    }

    // Tocar un bicho bolita, sin importar qué más esté tocando, alcanza para
    // prestarse el lanzamiento: igual que Game::addMoves() le ofrece a un bicho
    // bolita de verdad su Movement y su PillbugThrow a la vez.
    const bool touchesPillbug =
        std::find(imitating.begin(), imitating.end(), PieceType::Pillbug) != imitating.end();
    if (touchesPillbug)
    {
        for (const PillbugThrow &t : pillbugThrows(board_, hex, lastMoved_))
        {
            moves.push_back(t);
        }
    }
}

void Game::syncMosquitoStrategy(Piece *piece, const Hex &at) const
{
    if (piece->type != PieceType::Mosquito)
    {
        return;
    }
    piece->movement = board_.stackHeight(at) > 1 ? createMovementStrategy(PieceType::Beetle)
                                                  : nullptr;
}

bool Game::applyMove(const Move &move)
{
    if (status_ != GameStatus::Ongoing)
    {
        return false;
    }

    const std::vector<Move> legal = legalMoves();
    if (std::find(legal.begin(), legal.end(), move) == legal.end())
    {
        return false;
    }

    if (std::holds_alternative<Placement>(move))
    {
        const auto &placement = std::get<Placement>(move);

        pieces_.push_back(std::make_unique<Piece>(turn_, placement.type,
                                                  nextPieceOrdinal(placement.type)));
        Piece *piece = pieces_.back().get();

        board_.place(piece, placement.destination);
        currentPlayer().place(placement.type);
        lastMoved_ = piece; // the placed piece replaces whatever moved before it
    }
    else if (std::holds_alternative<Movement>(move))
    {
        const auto &movement = std::get<Movement>(move);
        Piece *piece = board_.topAt(movement.from);

        board_.move(movement.from, movement.destination);
        lastMoved_ = piece;
        syncMosquitoStrategy(piece, movement.destination);
    }
    else if (std::holds_alternative<PillbugThrow>(move))
    {
        const auto &t = std::get<PillbugThrow>(move);
        Piece *victim = board_.topAt(t.victim);

        board_.move(t.victim, t.destination);
        lastMoved_ = victim; // the victim moved, not the thrower
    }
    else if (std::holds_alternative<MosquitoMovement>(move))
    {
        const auto &m = std::get<MosquitoMovement>(move);
        Piece *piece = board_.topAt(m.from);

        board_.move(m.from, m.destination);
        lastMoved_ = piece; // the mosquito itself moved
        syncMosquitoStrategy(piece, m.destination);
    }
    else if (std::holds_alternative<Pass>(move))
    {
        // A pass means the last action was not a piece action, so the one-turn
        // Pillbug restriction from the prior ply expires.
        lastMoved_ = nullptr;
    }

    turn_ = (turn_ == Color::White) ? Color::Black : Color::White;
    ++turnNumber_;
    updateStatus();

    if (status_ == GameStatus::Ongoing && ruleset_.repetitionDrawOccurrences > 0)
    {
        const int occurrences = ++repetitionCounts_[positionKey()];
        if (occurrences >= ruleset_.repetitionDrawOccurrences)
        {
            status_ = GameStatus::Draw;
        }
    }

    return true;
}

std::string Game::positionKey() const
{
    std::ostringstream key;
    key << ruleset_.id << '|' << static_cast<int>(turn_) << '|';
    std::vector<Hex> hexes = board_.occupiedHexes();
    std::sort(hexes.begin(), hexes.end(), [](const Hex &a, const Hex &b) {
        return a.q != b.q ? a.q < b.q : a.r < b.r;
    });
    for (const Hex &hex : hexes)
    {
        key << hex.q << ',' << hex.r << '[';
        for (const Piece *piece : board_.stackAt(hex))
        {
            key << static_cast<int>(piece->color) << ':' << static_cast<int>(piece->type) << ',';
        }
        key << "]";
    }
    return key.str();
}

std::string Game::stateKey() const
{
    std::ostringstream key;
    key << positionKey() << "|deadline:";
    if (ruleset_.maxPlies > 0) key << "ply=" << turnNumber_ << ';';
    for (Color color : {Color::White, Color::Black})
    {
        const Player &p = player(color);
        const int progress = p.hasPlacedQueen()
                                 ? ruleset_.queenMustBePlacedByOwnTurn
                                 : std::min(ownTurnNumber(color, turnNumber_),
                                            ruleset_.queenMustBePlacedByOwnTurn);
        key << progress << ',';
    }

    key << "|last:";
    if (lastMoved_ == nullptr)
    {
        key << '-';
    }

    else
    {
        bool found = false;
        std::vector<Hex> hexes = board_.occupiedHexes();
        std::sort(hexes.begin(), hexes.end(), [](const Hex &a, const Hex &b) {
            return a.q != b.q ? a.q < b.q : a.r < b.r;
        });
        for (const Hex &hex : hexes)
        {
            const auto stack = board_.stackAt(hex);
            for (std::size_t i = 0; i < stack.size(); ++i)
            {
                if (stack[i] == lastMoved_)
                {
                    key << hex.q << ',' << hex.r << ',' << i;
                    found = true;
                    break;
                }
            }
            if (found) break;
        }
        if (!found) key << "off-board";
    }

    key << "|action-slots:";
    std::vector<Hex> actionHexes = board_.occupiedHexes();
    std::sort(actionHexes.begin(), actionHexes.end(), [](const Hex &a, const Hex &b) {
        return a.q != b.q ? a.q < b.q : a.r < b.r;
    });
    for (const Hex &hex : actionHexes)
    {
        for (const Piece *piece : board_.stackAt(hex))
        {
            key << hex.q << ',' << hex.r << ':' << static_cast<int>(piece->color) << ':'
                << static_cast<int>(piece->type) << ':' << piece->ordinal << ';';
        }
    }

    std::vector<std::pair<std::string, int>> history(repetitionCounts_.begin(),
                                                      repetitionCounts_.end());
    std::sort(history.begin(), history.end());
    key << "|history:";
    for (const auto &entry : history)
    {
        key << entry.first.size() << ':' << entry.first << '=' << entry.second << ';';
    }
    return key.str();
}

void Game::updateStatus()
{
    const bool whiteSurrounded = isQueenSurrounded(Color::White);
    const bool blackSurrounded = isQueenSurrounded(Color::Black);

    if (whiteSurrounded && blackSurrounded)
    {
        status_ = ruleset_.blackWinsTies ? GameStatus::BlackWins : GameStatus::Draw;
    }
    else if (whiteSurrounded)
    {
        status_ = GameStatus::BlackWins;
    }
    else if (blackSurrounded)
    {
        status_ = GameStatus::WhiteWins;
    }
    else if (ruleset_.maxPlies > 0 && turnNumber_ - 1 >= ruleset_.maxPlies)
    {
        const auto neighborsOfQueen = [&](Color color) {
            for (const Hex &hex : board_.occupiedHexes())
                if (board_.contains(hex, color, PieceType::Queen))
                    return board_.occupiedNeighbors(hex).size();
            return std::size_t{0};
        };
        const auto white = neighborsOfQueen(Color::White);
        const auto black = neighborsOfQueen(Color::Black);
        status_ = white < black ? GameStatus::WhiteWins
                  : black < white || ruleset_.blackWinsTies ? GameStatus::BlackWins
                                                         : GameStatus::Draw;
    }
}

bool Game::isQueenSurrounded(Color color) const
{
    for (const Hex &hex : board_.occupiedHexes())
    {
        if (board_.contains(hex, color, PieceType::Queen))
        {
            return board_.occupiedNeighbors(hex).size() >=
                   static_cast<std::size_t>(ruleset_.queenSurroundCount);
        }
    }
    return false; // that color hasn't placed its queen yet
}
