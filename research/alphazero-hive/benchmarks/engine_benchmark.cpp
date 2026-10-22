#include <chrono>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <iomanip>
#include <string>

#include "hive/Game.h"

namespace {
using Clock = std::chrono::steady_clock;

template <typename Function>
double nanosPerCall(std::size_t iterations, Function &&function)
{
    const auto start = Clock::now();
    for (std::size_t i = 0; i < iterations; ++i) function(i);
    const auto elapsed = std::chrono::duration<double, std::nano>(Clock::now() - start).count();
    return elapsed / static_cast<double>(iterations);
}

std::uint64_t fnv1a64(const std::string &value)
{
    std::uint64_t hash = 14695981039346656037ull;
    for (unsigned char byte : value)
    {
        hash ^= byte;
        hash *= 1099511628211ull;
    }
    return hash;
}

std::size_t createPosition(Game &game, int plies)
{
    int completed = 0;
    for (; completed < plies && game.status() == GameStatus::Ongoing; ++completed)
    {
        const auto moves = game.legalMoves();
        if (moves.empty()) break;
        if (!game.applyMove(moves.front())) break;
    }
    return static_cast<std::size_t>(completed);
}
} // namespace

int main(int argc, char **argv)
{
    const std::size_t iterations = argc > 1 ? static_cast<std::size_t>(std::stoull(argv[1])) : 10000;
    Game position(Ruleset::baseHivePaper());
    const std::size_t plies = createPosition(position, 28);
    volatile std::uint64_t sink = 0;

    const double legalNs = nanosPerCall(iterations, [&](std::size_t) {
        sink += position.legalMoves().size();
    });
    const double keyNs = nanosPerCall(iterations, [&](std::size_t) {
        sink += position.stateKey().size();
    });
    const double cloneLegalApplyNs = nanosPerCall(iterations, [&](std::size_t i) {
        Game branch(position);
        const auto moves = branch.legalMoves();
        sink += moves.size();
        if (!moves.empty()) branch.applyMove(moves[i % moves.size()]);
        sink += static_cast<std::uint64_t>(branch.turnNumber());
    });
    const std::uint64_t positionDigest = fnv1a64(position.stateKey());

    std::cout << "{\"ruleset\":\"" << position.ruleset().id << "\",\"position_plies\":"
              << plies << ",\"iterations\":" << iterations
              << ",\"legal_moves_ns\":" << legalNs
              << ",\"state_key_ns\":" << keyNs
              << ",\"clone_legal_apply_ns\":" << cloneLegalApplyNs
              << ",\"state_key_fnv1a64\":\"" << std::hex << positionDigest << std::dec
              << "\",\"sink\":" << sink << "}\n";
}
