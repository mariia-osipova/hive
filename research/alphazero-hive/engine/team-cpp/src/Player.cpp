#include "hive/Player.h"

#include <array>

Player::Player(Color color)
    : Player(color, std::array<int, 8>{1, 2, 2, 3, 3, 1, 1, 1})
{
}

Player::Player(Color color, const std::array<int, 8> &inventory)
    : _color(color), _mano{}
{
    for (std::size_t i = 0; i < inventory.size(); ++i)
    {
        _mano.emplace(pieceTypeAt(i), inventory[i]);
    }
}

Color Player::color( ) const
{
    
    return _color;

}

int Player::remaining( PieceType type ) const
{
    
    return _mano.at(type);
    
}

std::vector< PieceType > Player::availableTypes( ) const
{
    
    std::vector< PieceType > resultado;
    for (std::size_t i = 0; i < 8; ++i) {
        const PieceType type = pieceTypeAt(i);
        if (_mano.at(type) > 0) {
            resultado.push_back(type);
        }
    }

    return resultado;

}

void Player::place( PieceType type )
{

    --_mano.at( type );

}

bool Player::hasPlacedQueen() const
{

    //para mi no hace falta porque si guardo aparte y alguien agrega otra forma
    //de sacar las piezas entonces ese dato queda afectado y deja al jugador o
    //bloqueado o se pueden romper las jugadas naturales

    return remaining( PieceType::Queen ) == 0;

}
