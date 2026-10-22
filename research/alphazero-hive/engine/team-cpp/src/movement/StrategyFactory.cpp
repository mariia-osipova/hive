#include "hive/movement/StrategyFactory.h"
#include "hive/movement/QueenMovement.h"
#include "hive/movement/AntMovement.h"
#include "hive/movement/BeetleMovement.h"
#include "hive/movement/SpiderMovement.h"
#include "hive/movement/GrasshopperMovement.h"
#include "hive/movement/LadybugMovement.h"

std::unique_ptr< MovementStrategy > createMovementStrategy( PieceType type )
{
    
    std::unique_ptr< MovementStrategy > strategy;
    switch ( type )
    {
        
        case PieceType::Queen:
            strategy = std::make_unique< QueenMovement >( );
            break;

        case PieceType::Ant:
            strategy = std::make_unique< AntMovement >( );
            break;
        
        case PieceType::Beetle:
            strategy = std::make_unique< BeetleMovement >( );
            break;
        
        case PieceType::Spider:
            strategy = std::make_unique< SpiderMovement >( );
            break;
        
        case PieceType::Grasshopper:
            strategy = std::make_unique< GrasshopperMovement >( );
            break;

        case PieceType::Ladybug:
            strategy = std::make_unique< LadybugMovement >( );
            break;
        
        case PieceType::Pillbug:
            strategy = std::make_unique< QueenMovement >( );
            break;
        
        case PieceType::Mosquito:
            strategy = nullptr;
            break;

    }

    return strategy;

}
