#include <gtest/gtest.h>

#include <algorithm>
#include <array>
#include <functional>
#include <set>
#include <tuple>

#include "hive/Game.h"
#include "hive/movement/BeetleMovement.h"

namespace {
Ruleset passOnlyRuleset()
{
    Ruleset rules = Ruleset::baseHivePaper();
    rules.id = "pass-only-test-fixture";
    rules.piecesPerPlayer.fill(0);
    return rules;
}

bool isPlacement(const Move &move, PieceType type)
{
    const auto *placement = std::get_if<Placement>(&move);
    return placement != nullptr && placement->type == type;
}

const Move *findMove(const std::vector<Move> &moves, const std::function<bool(const Move &)> &predicate)
{
    auto found = std::find_if(moves.begin(), moves.end(), predicate);
    return found == moves.end() ? nullptr : &*found;
}
} // namespace

TEST(AlphaZeroRules, BaseProfileHasOnlyTheElevenBasePiecesPerPlayer)
{
    Game game(Ruleset::baseHivePaper());

    EXPECT_EQ(game.ruleset().id, "base-hive-paper-profile");
    EXPECT_EQ(game.player(Color::White).remaining(PieceType::Queen), 1);
    EXPECT_EQ(game.player(Color::White).remaining(PieceType::Spider), 2);
    EXPECT_EQ(game.player(Color::White).remaining(PieceType::Beetle), 2);
    EXPECT_EQ(game.player(Color::White).remaining(PieceType::Grasshopper), 3);
    EXPECT_EQ(game.player(Color::White).remaining(PieceType::Ant), 3);
    EXPECT_EQ(game.player(Color::White).remaining(PieceType::Mosquito), 0);
    EXPECT_EQ(game.player(Color::White).remaining(PieceType::Ladybug), 0);
    EXPECT_EQ(game.player(Color::White).remaining(PieceType::Pillbug), 0);
}

TEST(AlphaZeroRules, QueenCannotBePlacedOnEitherPlayersFirstTurn)
{
    Game game(Ruleset::baseHivePaper());

    ASSERT_EQ(game.legalMoves().size(), 4u);
    for (const Move &move : game.legalMoves())
    {
        EXPECT_FALSE(isPlacement(move, PieceType::Queen));
    }
    ASSERT_TRUE(game.applyMove(game.legalMoves().front()));
    for (const Move &move : game.legalMoves())
    {
        EXPECT_FALSE(isPlacement(move, PieceType::Queen));
    }
}

TEST(AlphaZeroRules, QueenIsForcedOnTheFourthOwnTurn)
{
    Game game(Ruleset::baseHivePaper());
    for (int i = 0; i < 6; ++i)
    {
        const auto moves = game.legalMoves();
        const Move *nonQueen = findMove(moves, [](const Move &move) {
            const auto *placement = std::get_if<Placement>(&move);
            return placement != nullptr && placement->type != PieceType::Queen;
        });
        ASSERT_NE(nonQueen, nullptr);
        ASSERT_TRUE(game.applyMove(*nonQueen));
    }

    ASSERT_EQ(game.turn(), Color::White);
    ASSERT_EQ(game.turnNumber(), 7);
    for (const Move &move : game.legalMoves())
    {
        const auto *placement = std::get_if<Placement>(&move);
        ASSERT_NE(placement, nullptr);
        EXPECT_EQ(placement->type, PieceType::Queen);
    }
}

TEST(AlphaZeroRules, OpeningPlacementSetMatchesBeekeeperAfterCanonicalSecondMove)
{
    Game game(Ruleset::baseHivePaper());
    const auto firstMoves = game.legalMoves();
    const Move *whiteAnt = findMove(firstMoves, [](const Move &move) {
        const auto *placement = std::get_if<Placement>(&move);
        return placement != nullptr && placement->type == PieceType::Ant &&
               placement->destination == Hex{0, 0};
    });
    ASSERT_NE(whiteAnt, nullptr);
    ASSERT_TRUE(game.applyMove(*whiteAnt));

    const auto secondMoves = game.legalMoves();
    const Move *blackAnt = findMove(secondMoves, [](const Move &move) {
        const auto *placement = std::get_if<Placement>(&move);
        return placement != nullptr && placement->type == PieceType::Ant &&
               placement->destination == Hex{1, 0};
    });
    ASSERT_NE(blackAnt, nullptr);
    ASSERT_TRUE(game.applyMove(*blackAnt));

    const std::array<Hex, 3> referenceSpots = {Hex{-1, 0}, Hex{-1, 1}, Hex{0, -1}};
    const auto moves = game.legalMoves();
    ASSERT_EQ(moves.size(), 15u);
    std::set<std::tuple<int, int, int>> uniqueActions;
    for (const Move &move : moves)
    {
        const auto *placement = std::get_if<Placement>(&move);
        ASSERT_NE(placement, nullptr);
        EXPECT_TRUE(std::find(referenceSpots.begin(), referenceSpots.end(),
                              placement->destination) != referenceSpots.end());
        uniqueActions.emplace(static_cast<int>(placement->type),
                              placement->destination.q, placement->destination.r);
    }
    EXPECT_EQ(uniqueActions.size(), moves.size());
}

TEST(AlphaZeroRules, CloneHasIndependentPiecesAndPreservesSearchState)
{
    Game game(Ruleset::baseHivePaper());
    const auto opening = game.legalMoves();
    ASSERT_TRUE(game.applyMove(opening.front()));

    Game clone(game);
    EXPECT_EQ(clone.stateKey(), game.stateKey());
    ASSERT_NE(clone.board().topAt(Hex{0, 0}), game.board().topAt(Hex{0, 0}));
    ASSERT_NE(clone.lastMoved(), game.lastMoved());

    const auto cloneMoves = clone.legalMoves();
    ASSERT_FALSE(cloneMoves.empty());
    ASSERT_TRUE(clone.applyMove(cloneMoves.front()));
    EXPECT_EQ(game.turn(), Color::Black);
    EXPECT_EQ(game.turnNumber(), 2);
    EXPECT_EQ(game.board().occupiedHexes().size(), 1u);
}

TEST(AlphaZeroRules, LegacyGameProfileRemainsExpandedForTheExistingGui)
{
    Game game;
    EXPECT_EQ(game.ruleset().id, "legacy-expanded");
    EXPECT_EQ(game.legalMoves().size(), 8u);
}

TEST(AlphaZeroRules, ClonePreservesAnElevatedMosquitosMovementStrategy)
{
    Game game;
    const auto applyFirst = [&](const std::function<bool(const Move &)> &predicate) {
        const auto moves = game.legalMoves();
        const Move *move = findMove(moves, predicate);
        return move != nullptr && game.applyMove(*move);
    };

    ASSERT_TRUE(applyFirst([](const Move &move) { return isPlacement(move, PieceType::Queen); }));
    ASSERT_TRUE(applyFirst([](const Move &) { return true; }));
    ASSERT_TRUE(applyFirst([](const Move &move) { return isPlacement(move, PieceType::Mosquito); }));
    ASSERT_TRUE(applyFirst([](const Move &) { return true; }));

    Hex queenHex{};
    Hex mosquitoHex{};
    for (const Hex &hex : game.board().occupiedHexes())
    {
        const Piece *piece = game.board().topAt(hex);
        if (piece->color == Color::White && piece->type == PieceType::Queen) queenHex = hex;
        if (piece->color == Color::White && piece->type == PieceType::Mosquito) mosquitoHex = hex;
    }

    ASSERT_TRUE(applyFirst([&](const Move &move) {
        const auto *placement = std::get_if<Placement>(&move);
        return placement != nullptr && placement->type == PieceType::Beetle &&
               distance(placement->destination, queenHex) == 1 &&
               distance(placement->destination, mosquitoHex) == 1;
    }));
    ASSERT_TRUE(applyFirst([](const Move &) { return true; }));

    const auto availableClimbs = game.legalMoves();
    const Move *climb = findMove(availableClimbs, [&](const Move &move) {
        const auto *mosquitoMove = std::get_if<MosquitoMovement>(&move);
        return mosquitoMove != nullptr && mosquitoMove->imitating == PieceType::Beetle &&
               game.board().isOccupied(mosquitoMove->destination);
    });
    ASSERT_NE(climb, nullptr);
    const Hex elevatedHex = std::get<MosquitoMovement>(*climb).destination;
    ASSERT_TRUE(game.applyMove(*climb));

    Game clone(game);
    EXPECT_EQ(clone.stateKey(), game.stateKey());
    ASSERT_NE(clone.board().topAt(elevatedHex), game.board().topAt(elevatedHex));
    const Piece *copiedMosquito = clone.board().topAt(elevatedHex);
    ASSERT_NE(copiedMosquito, nullptr);
    EXPECT_NE(dynamic_cast<const BeetleMovement *>(copiedMosquito->movement.get()), nullptr);
    EXPECT_EQ(clone.legalMoves(), game.legalMoves());
}

TEST(AlphaZeroRules, PassIsTheOnlyActionWhenNoMoveExists)
{
    Game game(passOnlyRuleset());
    const auto moves = game.legalMoves();

    ASSERT_EQ(moves.size(), 1u);
    EXPECT_TRUE(std::holds_alternative<Pass>(moves.front()));
    ASSERT_TRUE(game.applyMove(moves.front()));
    EXPECT_EQ(game.turn(), Color::Black);
    EXPECT_EQ(game.turnNumber(), 2);
}

TEST(AlphaZeroRules, ThirdOccurrenceDrawsAndSearchKeyKeepsRepetitionHistory)
{
    Game game(passOnlyRuleset());
    const std::string initialKey = game.stateKey();

    for (int ply = 0; ply < 2; ++ply)
    {
        const auto moves = game.legalMoves();
        ASSERT_EQ(moves.size(), 1u);
        ASSERT_TRUE(game.applyMove(moves.front()));
    }
    EXPECT_EQ(game.turn(), Color::White);
    EXPECT_EQ(game.status(), GameStatus::Ongoing);
    EXPECT_NE(game.stateKey(), initialKey);

    for (int ply = 0; ply < 2; ++ply)
    {
        const auto moves = game.legalMoves();
        ASSERT_EQ(moves.size(), 1u);
        ASSERT_TRUE(game.applyMove(moves.front()));
    }
    EXPECT_EQ(game.status(), GameStatus::Draw);
    EXPECT_TRUE(game.legalMoves().empty());
}

TEST(AlphaZeroRules, ExplicitPlyCapAdjudicatesTiesAndClonePreservesRemainingBudget)
{
    Ruleset rules = passOnlyRuleset();
    rules.repetitionDrawOccurrences = 0;
    rules.maxPlies = 2;
    rules.blackWinsTies = true;
    Game game(rules);
    const std::string before = game.stateKey();
    ASSERT_TRUE(game.applyMove(Pass{}));
    Game clone(game);
    EXPECT_EQ(game.stateKey(), clone.stateKey());
    EXPECT_NE(before, game.stateKey());
    ASSERT_TRUE(clone.applyMove(Pass{}));
    EXPECT_EQ(clone.status(), GameStatus::BlackWins);
    EXPECT_EQ(game.status(), GameStatus::Ongoing);
    EXPECT_TRUE(clone.legalMoves().empty());

    rules.blackWinsTies = false;
    Game drawing(rules);
    ASSERT_TRUE(drawing.applyMove(Pass{}));
    ASSERT_TRUE(drawing.applyMove(Pass{}));
    EXPECT_EQ(drawing.status(), GameStatus::Draw);
}

TEST(AlphaZeroRules, InvalidThresholdsAndCapsAreRejected)
{
    auto rules = Ruleset::baseHivePaper();
    rules.queenSurroundCount = 7;
    EXPECT_THROW(Game{rules}, std::invalid_argument);
    rules.queenSurroundCount = 4;
    rules.maxPlies = -1;
    EXPECT_THROW(Game{rules}, std::invalid_argument);
}
