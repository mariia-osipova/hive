#include "hive/BoardGraphAdapter.h"

#include <cstddef>

#include "hive/Bfs.h"
#include "hive/Hex.h"

// ============================================================================
//
// bfs() (include/hive/Bfs.h) es una biblioteca genérica: no sabe nada de Hive
// ni de hexágonos. Habla de nodos numerados 0..n-1 y de listas de adyacencia.
// Board, del otro lado, habla de Hex y de casilleros ocupados. Ninguno de los
// dos se puede cambiar: esta clase es la que traduce entre los dos idiomas.
//
// El header declara solo la parte pública. Tienen que decidir el ESTADO: para
// traducir en las dos direcciones hace falta guardar algo en el constructor.
// Ese estado va en la sección `private:` del header.
//
// Para pensar: `ignoring` es un parámetro del constructor, no un metodo que
// saque la pieza del tablero y después la vuelva a poner. ¿Por qué conviene
// que sea así? ¿Qué podría salir mal con la otra versión? Fíjense qué partes
// del tablero están usando el adaptador...
//
// Los tests están en tests/board_graph_adapter_test.cpp, y los de
// Board::canMove()/isConnected() —que usan esta clase— en
// tests/board_connectivity_test.cpp.
// ============================================================================

BoardGraphAdapter::BoardGraphAdapter(const Board &board, const Hex *ignoring) {
    for (const Hex &hex : board.occupiedHexes()) {
        if (ignoring != nullptr && hex == *ignoring) {continue;}

        const int node = static_cast<int>(hexes_.size());
        hexes_.push_back(hex);
        nodeByHex_.emplace(hex, node);
    }

    adjacency_.resize(hexes_.size());
    for (std::size_t node = 0; node < hexes_.size(); ++node) {
        for (const Hex &direction : hexDirections()) {
            const Hex neighbor{hexes_[node].q + direction.q, hexes_[node].r + direction.r};
            const auto neighborNode = nodeByHex_.find(neighbor);
            if (neighborNode != nodeByHex_.end()) {
                adjacency_[node].push_back(neighborNode->second);
            }
        }
    }
}

std::vector<Hex> BoardGraphAdapter::neighbors(const Hex &h) const
{
    //devolver los vecinos de `h` dentro de este grafo.
    const auto node = nodeByHex_.find(h);
    if (node == nodeByHex_.end())
    {
        return {};
    }

    std::vector<Hex> result;
    result.reserve(adjacency_[node->second].size());
    for (const int neighbor : adjacency_[node->second])
    {
        result.push_back(hexes_[neighbor]);
    }
    return result;
}

std::unordered_map<Hex, int> BoardGraphAdapter::distancesFrom(const Hex &source) const
{
    // distancias en saltos desde `source` a cada nodo, usando bfs().
    const auto sourceNode = nodeByHex_.find(source);
    if (sourceNode == nodeByHex_.end())
    {
        return {};
    }

    const std::vector<int> distances = bfs(adjacency_, sourceNode->second);
    std::unordered_map<Hex, int> result;
    result.reserve(hexes_.size());
    for (std::size_t node = 0; node < hexes_.size(); ++node)
    {
        result.emplace(hexes_[node], distances[node]);
    }
    return result;
}

bool BoardGraphAdapter::isConnected() const
{
    // devolver si todos los nodos del grafo se alcanzan entre sí.
    if (hexes_.empty())
    {
        return true;
    }

    const std::vector<int> distances = bfs(adjacency_, 0);
    for (const int distance : distances)
    {
        if (distance == -1)
        {
            return false;
        }
    }
    return true;
}
