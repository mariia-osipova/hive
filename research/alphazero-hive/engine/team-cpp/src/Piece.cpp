#include "hive/Piece.h"

#include "hive/movement/StrategyFactory.h"

Piece::Piece(Color color, PieceType type, int ordinal)
    : color(color), type(type), ordinal(ordinal), movement(createMovementStrategy(type))
{
}

Piece::Piece(const Piece &other)
    : color(other.color),
      type(other.type),
      ordinal(other.ordinal),
      movement(other.movement
                   ? createMovementStrategy(type == PieceType::Mosquito ? PieceType::Beetle : type)
                   : nullptr)
{
}

std::vector<Hex> Piece::legalMoves(const Board &board, const Hex &from) const
{
    if (!movement)
    {
        return {};
    }
    return movement->moves(board, from, *this);
}
