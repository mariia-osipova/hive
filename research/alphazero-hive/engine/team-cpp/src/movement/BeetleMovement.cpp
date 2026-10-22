#include "hive/movement/BeetleMovement.h"
#include "hive/Board.h"
#include <algorithm>

std::vector< Hex > BeetleMovement::moves( const Board &board, const Hex &from, const Piece &self ) const
{
    
    std::vector< Hex > destinations;
    const bool onPile = board.stackHeight( from ) > 1;
    for ( const Hex &next : neighbors( from ) )
    {

        const bool climbing = board.isOccupied( next );
        // A beetle crosses at the higher of its starting and landing levels.
        // Two flanking stacks reaching that level form an impassable gate.
        const auto level = std::max(board.stackHeight(from), board.stackHeight(next) + 1);
        int blocked = 0;
        for (const Hex &flank : neighbors(from))
            if (distance(flank, next) == 1 && board.stackHeight(flank) >= level) ++blocked;
        if (blocked == 2) continue;
        if ( !onPile && !climbing )
        {

            if ( !board.canSlide( from, next ) )
            {

                continue;

            }

            if ( !board.wouldStayAttached( next, self ) )
            {

                continue;

            }

        }

        destinations.push_back( next );
        
    }

    return destinations;

}
