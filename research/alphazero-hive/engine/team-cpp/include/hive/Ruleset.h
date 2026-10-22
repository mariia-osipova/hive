#pragma once

#include <array>
#include <string>

#include "hive/Enums.h"

/** Rules that change legal actions or terminal outcomes. */
struct Ruleset {
    std::string id;
    std::array<int, 8> piecesPerPlayer{};
    bool forbidQueenOnFirstOwnTurn = false;
    int queenMustBePlacedByOwnTurn = 4;
    bool passWhenNoLegalMove = true;
    int repetitionDrawOccurrences = 0;
    int queenSurroundCount = 6;
    int maxPlies = 0; // zero means no cap; a ply is one player's action
    bool blackWinsTies = false;

    /** Preserve the copied GUI engine's expanded-piece behavior. */
    static Ruleset legacyExpanded();
    /** Base Hive, no expansions, tournament opening, third repetition draws. */
    static Ruleset baseHivePaper();
};
