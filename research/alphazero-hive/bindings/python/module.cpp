#include <algorithm>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <utility>
#include <vector>

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "hive/Game.h"

namespace py = pybind11;

namespace {
std::string pieceName(PieceType type)
{
    switch (type)
    {
    case PieceType::Queen: return "queen";
    case PieceType::Spider: return "spider";
    case PieceType::Beetle: return "beetle";
    case PieceType::Grasshopper: return "grasshopper";
    case PieceType::Ant: return "ant";
    case PieceType::Mosquito: return "mosquito";
    case PieceType::Ladybug: return "ladybug";
    case PieceType::Pillbug: return "pillbug";
    }
    throw std::invalid_argument("Unknown Hive piece type");
}

PieceType parsePiece(const std::string &name)
{
    if (name == "queen") return PieceType::Queen;
    if (name == "spider") return PieceType::Spider;
    if (name == "beetle") return PieceType::Beetle;
    if (name == "grasshopper") return PieceType::Grasshopper;
    if (name == "ant") return PieceType::Ant;
    if (name == "mosquito") return PieceType::Mosquito;
    if (name == "ladybug") return PieceType::Ladybug;
    if (name == "pillbug") return PieceType::Pillbug;
    throw py::value_error("Unknown Hive piece: " + name);
}

Hex parseHex(const py::handle &value, const char *field)
{
    if (!py::isinstance<py::sequence>(value))
    {
        throw py::type_error(std::string("'") + field + "' must be a pair [q, r]");
    }
    const py::sequence pair = py::reinterpret_borrow<py::sequence>(value);
    if (pair.size() != 2)
    {
        throw py::value_error(std::string("'") + field + "' must contain exactly two coordinates");
    }
    return Hex{py::cast<int>(pair[0]), py::cast<int>(pair[1])};
}

py::tuple hexTuple(const Hex &hex)
{
    return py::make_tuple(hex.q, hex.r);
}

py::dict moveDict(const Move &move)
{
    return std::visit([](const auto &action) {
        using T = std::decay_t<decltype(action)>;
        py::dict result;
        if constexpr (std::is_same_v<T, Placement>)
        {
            result["kind"] = "place";
            result["piece"] = pieceName(action.type);
            result["to"] = hexTuple(action.destination);
        }
        else if constexpr (std::is_same_v<T, Movement>)
        {
            result["kind"] = "move";
            result["from"] = hexTuple(action.from);
            result["to"] = hexTuple(action.destination);
        }
        else if constexpr (std::is_same_v<T, PillbugThrow>)
        {
            result["kind"] = "pillbug_throw";
            result["pillbug"] = hexTuple(action.pillbug);
            result["victim"] = hexTuple(action.victim);
            result["to"] = hexTuple(action.destination);
        }
        else if constexpr (std::is_same_v<T, MosquitoMovement>)
        {
            result["kind"] = "mosquito_move";
            result["from"] = hexTuple(action.from);
            result["imitating"] = pieceName(action.imitating);
            result["to"] = hexTuple(action.destination);
        }
        else
        {
            result["kind"] = "pass";
        }
        return result;
    }, move);
}

Move parseMove(const py::dict &action)
{
    if (!action.contains("kind")) throw py::key_error("action requires 'kind'");
    const std::string kind = py::cast<std::string>(action["kind"]);
    if (kind == "place")
    {
        if (!action.contains("piece") || !action.contains("to"))
            throw py::key_error("placement requires 'piece' and 'to'");
        return Placement{parsePiece(py::cast<std::string>(action["piece"])),
                         parseHex(action["to"], "to")};
    }
    if (kind == "move")
    {
        if (!action.contains("from") || !action.contains("to"))
            throw py::key_error("movement requires 'from' and 'to'");
        return Movement{parseHex(action["from"], "from"), parseHex(action["to"], "to")};
    }
    if (kind == "pillbug_throw")
    {
        if (!action.contains("pillbug") || !action.contains("victim") || !action.contains("to"))
            throw py::key_error("pillbug_throw requires 'pillbug', 'victim', and 'to'");
        return PillbugThrow{parseHex(action["pillbug"], "pillbug"),
                            parseHex(action["victim"], "victim"),
                            parseHex(action["to"], "to")};
    }
    if (kind == "mosquito_move")
    {
        if (!action.contains("from") || !action.contains("imitating") || !action.contains("to"))
            throw py::key_error("mosquito_move requires 'from', 'imitating', and 'to'");
        return MosquitoMovement{parseHex(action["from"], "from"),
                                parsePiece(py::cast<std::string>(action["imitating"])),
                                parseHex(action["to"], "to")};
    }
    if (kind == "pass") return Pass{};
    throw py::value_error("Unknown Hive action kind: " + kind);
}

Game makeGame(const std::string &profile, const py::dict &options)
{
    Ruleset rules;
    if (profile == "base-hive-paper-profile" || profile == "base")
        rules = Ruleset::baseHivePaper();
    else if (profile == "legacy-expanded" || profile == "legacy")
        rules = Ruleset::legacyExpanded();
    else
        throw py::value_error("Unknown rules profile: " + profile);
    for (auto item : options)
    {
        const auto name = py::cast<std::string>(item.first);
        if (name == "queen_surround_count") rules.queenSurroundCount = py::cast<int>(item.second);
        else if (name == "max_plies") rules.maxPlies = py::cast<int>(item.second);
        else if (name == "repetition_draw_occurrences") rules.repetitionDrawOccurrences = py::cast<int>(item.second);
        else if (name == "black_wins_ties") rules.blackWinsTies = py::cast<bool>(item.second);
        else throw py::value_error("Unknown rule option: " + name);
    }
    if (!options.empty())
        rules.id += ":surround=" + std::to_string(rules.queenSurroundCount) +
                    ":cap=" + std::to_string(rules.maxPlies) +
                    ":repetition=" + std::to_string(rules.repetitionDrawOccurrences) +
                    ":black-ties=" + std::to_string(rules.blackWinsTies);
    return Game(rules);
}

py::list boardSnapshot(const Game &game)
{
    std::vector<Hex> cells = game.board().occupiedHexes();
    std::sort(cells.begin(), cells.end(), [](const Hex &a, const Hex &b) {
        return a.q != b.q ? a.q < b.q : a.r < b.r;
    });
    py::list result;
    for (const Hex &hex : cells)
    {
        py::dict cell;
        cell["q"] = hex.q;
        cell["r"] = hex.r;
        py::list stack;
        for (const Piece *piece : game.board().stackAt(hex))
        {
            py::dict item;
            item["color"] = piece->color == Color::White ? "white" : "black";
            item["piece"] = pieceName(piece->type);
            item["ordinal"] = piece->ordinal;
            stack.append(std::move(item));
        }
        cell["stack"] = std::move(stack);
        result.append(std::move(cell));
    }
    return result;
}
} // namespace

PYBIND11_MODULE(_hive_cpp, module)
{
    module.doc() = "C++ Hive rules engine used by the AlphaZero Hive experiments";
    module.def("available_profiles", [] {
        return std::vector<std::string>{"base-hive-paper-profile", "legacy-expanded"};
    });

    py::class_<Game>(module, "Game")
        .def(py::init(&makeGame), py::arg("profile") = "base-hive-paper-profile",
             py::arg("options") = py::dict())
        .def("clone", [](const Game &game) { return Game(game); })
        .def_property_readonly("ruleset_id", [](const Game &game) { return game.ruleset().id; })
        .def_property_readonly("current_player", [](const Game &game) {
            return game.turn() == Color::White ? "white" : "black";
        })
        .def_property_readonly("turn_number", &Game::turnNumber)
        .def_property_readonly("status", [](const Game &game) {
            switch (game.status())
            {
            case GameStatus::Ongoing: return std::string("ongoing");
            case GameStatus::WhiteWins: return std::string("white_wins");
            case GameStatus::BlackWins: return std::string("black_wins");
            case GameStatus::Draw: return std::string("draw");
            }
            return std::string("unknown");
        })
        .def_property_readonly("winner", [](const Game &game) -> py::object {
            const auto winner = game.winner();
            if (!winner) return py::none();
            return py::str(*winner == Color::White ? "white" : "black");
        })
        .def_property_readonly("board", &boardSnapshot)
        .def("remaining", [](const Game &game, const std::string &color,
                            const std::string &piece) {
            const Color owner = color == "white" ? Color::White
                                : color == "black" ? Color::Black
                                                     : throw py::value_error("Color must be 'white' or 'black'");
            return game.player(owner).remaining(parsePiece(piece));
        }, py::arg("color"), py::arg("piece"))
        .def("legal_actions", [](const Game &game) {
            py::list result;
            for (const Move &move : game.legalMoves())
            {
                py::dict action = moveDict(move);
                if (const auto *placement = std::get_if<Placement>(&move))
                    action["ordinal"] = game.nextPieceOrdinal(placement->type);
                result.append(std::move(action));
            }
            return result;
        })
        .def("apply_action", [](Game &game, const py::dict &action) {
            return game.applyMove(parseMove(action));
        }, py::arg("action"))
        .def("state_key", &Game::stateKey)
        .def("terminal_result", [](const Game &game) -> py::object {
            switch (game.status())
            {
            case GameStatus::Ongoing: return py::none();
            case GameStatus::Draw: return py::float_(0.0);
            case GameStatus::WhiteWins: return py::float_(1.0);
            case GameStatus::BlackWins: return py::float_(-1.0);
            }
            return py::none();
        });
}
