#pragma once

#include <cstddef>

/** @brief Los dos jugadores: las blancas arrancan. */
enum class Color {
    White,
    Black,
};

/**
 * @brief Los 8 tipos de pieza del juego, con las tres expansiones incluidas
 *        (mosquito, vaquita de San Antonio y bicho bolita).
 *
 * Cada tipo se mueve distinto, y esa diferencia no vive acá: vive en una
 * clase por tipo (ver MovementStrategy.h) que `createMovementStrategy()`
 * sabe elegir.
 */
enum class PieceType {
    Queen,
    Spider,
    Beetle,
    Grasshopper,
    Ant,
    Mosquito,
    Ladybug,
    Pillbug,
};

/** Stable ordering shared by inventory, serialization, and action encoding. */
constexpr std::size_t pieceTypeIndex(PieceType type)
{
    switch (type)
    {
    case PieceType::Queen: return 0;
    case PieceType::Spider: return 1;
    case PieceType::Beetle: return 2;
    case PieceType::Grasshopper: return 3;
    case PieceType::Ant: return 4;
    case PieceType::Mosquito: return 5;
    case PieceType::Ladybug: return 6;
    case PieceType::Pillbug: return 7;
    }
    return 0;
}

constexpr PieceType pieceTypeAt(std::size_t index)
{
    constexpr PieceType types[] = {
        PieceType::Queen, PieceType::Spider, PieceType::Beetle, PieceType::Grasshopper,
        PieceType::Ant, PieceType::Mosquito, PieceType::Ladybug, PieceType::Pillbug,
    };
    return types[index < 8 ? index : 0];
}
