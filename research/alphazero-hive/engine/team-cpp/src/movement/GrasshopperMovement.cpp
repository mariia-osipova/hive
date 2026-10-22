#include "hive/movement/GrasshopperMovement.h"
#include "hive/Board.h"

std::vector< Hex > GrasshopperMovement::moves( const Board &board, const Hex &from, const Piece &self ) const
{
    
    std::vector< Hex > destinations;
    for ( const Hex &dir : hexDirections( ) )
    {

        Hex cur{ from.q + dir.q, from.r + dir.r };

        if ( !board.isOccupied( cur ) )
        {

            continue;

        }

        while ( board.isOccupied( cur ) )
        {

            cur = Hex{ cur.q + dir.q, cur.r + dir.r };

        }

        destinations.push_back( cur );

    }

    return destinations;

}
