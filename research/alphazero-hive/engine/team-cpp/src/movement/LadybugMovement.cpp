#include "hive/movement/LadybugMovement.h"

#include "hive/Board.h"
#include "hive/BoardGraphAdapter.h"

#include <unordered_set>

// (Ladybug), y registrarla en StrategyFactory.
//
// Es el segundo cliente de BoardGraphAdapter, y la razón por la que el
// adaptador es una clase y no código suelto dentro de Board: los dos primeros
// pasos de la vaquita son saltos sobre casilleros ocupados, es decir, caminata
// sobre el mismo grafo que usa la regla de la colmena (el que determina la
// conectividad).
//
// Al terminar, miren qué archivos hubo que tocar para agregar una pieza
// entera: la clase nueva, y el switch de la fábrica. Board, Piece y Game no se
// tocan.
//
// La regla está en include/hive/movement/LadybugMovement.h y los tests en
// tests/ladybug_movement_test.cpp.

std::vector<Hex> LadybugMovement::moves(const Board &board, const Hex &from, const Piece &self) const {
    (void)self;

    BoardGraphAdapter occupiedGraph(board, &from);

    std::unordered_set<Hex> climbedTwice;
    for (const Hex &first : board.occupiedNeighbors(from))
    {
        for (const Hex &second : occupiedGraph.neighbors(first))
        {
            climbedTwice.insert(second);
        }
    }

    std::unordered_set<Hex> destinations;
    for (const Hex &topHex : climbedTwice)
    {
        for (const Hex &destination : board.emptyNeighbors(topHex))
        {
            destinations.insert(destination);
        }
    }

    return std::vector<Hex>(destinations.begin(), destinations.end());
}
