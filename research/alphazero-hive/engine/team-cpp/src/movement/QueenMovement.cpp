#include "hive/movement/QueenMovement.h"
#include "hive/Board.h"

std::vector< Hex > QueenMovement::moves( const Board &board, const Hex &from, const Piece &self ) const
{

    std::vector< Hex > destinations;
    for ( const Hex &next : board.emptyNeighbors( from ) )
    {

        if (!board.canSlide( from, next ) )
        {

            continue;

        }

        if (!board.wouldStayAttached( next, self ) )
        {

            continue;

        }
    
        destinations.push_back( next );
    }

    return destinations;

}
