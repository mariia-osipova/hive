#pragma once

#include <SFML/Graphics.hpp>
#include <optional>
#include <unordered_map>

#include "hive/Enums.h"
#include "hive/Game.h"
#include "hive/Hex.h"
#include "input/InputState.h"

class InputController;

// Where a window-space click (e.g. from sf::Event::MouseButtonPressed)
// landed, in game terms, as classified by GameView::hitTest: a board
// hex, a specific hand-panel piece, one of the top-bar action-menu
// buttons, the Cancel button, one of the imitation-popup icons, or
// neither. At most one of boardHex / (handColor, handType) / actionKind
// / imitationType is ever set, and cancel is true only when none of the
// others are. A plain struct rather than e.g. a variant, since it's
// built in exactly one place (hitTest) and consumed in exactly one
// (main.cpp's event loop).
struct ClickTarget
{
    std::optional<Hex> boardHex;
    std::optional<Color> handColor;
    std::optional<PieceType> handType;
    std::optional<ActionKind> actionKind;
    bool cancel = false;
    std::optional<PieceType> imitationType;
};

// Renders game state to an SFML render target.
class GameView
{
public:
    // Loads every piece/background texture and the label font. Throws
    // std::runtime_error if an asset can't be found (run ./hive from the
    // repo root -- assets/ and img/ are loaded via relative paths).
    GameView();

    // Draws the board-table background from img/background. Kept as a
    // separate pass so main.cpp can place it between window.clear() and
    // the actual game surfaces.
    void drawBackground(sf::RenderTarget &target, const Game &game) const;

    // Two vertical panels, White on the left edge and Black on the right,
    // one image-backed hex swatch per PieceType with Player::remaining(type)
    // printed beside it.
    void drawHands(sf::RenderTarget &target, const Game &game) const;

    // Every occupied hex, centered on the target: tile artwork chosen from
    // the top piece's owner/type, and a small height badge
    // when stackHeight(hex) > 1 (only the top piece is ever drawn -- it's
    // also the only one that's ever clickable, via Board::topAt).
    void drawBoard(sf::RenderTarget &target, const Game &game) const;

    // A ring around controller.selectedHex() (if any -- nullopt for a
    // hand-originated Placement, which has no board source), a
    // matching ring on controller.selectedHandPieceType()'s hand-panel
    // row (the Placement counterpart -- exactly one of the two is ever
    // set), a hex-shaped border -- same visual language as the
    // selection ring, just a different color -- on every
    // controller.highlightedHexes() entry, so a legal destination reads
    // as a bordered hex rather than an unmarked gap, whether or not
    // it's currently occupied (climbing), and, for a selected Mosquito
    // currently imitating something, a small glyph badge on its own hex
    // (the "icon on current imitation target" from the original design)
    // -- see drawImitationPopup for choosing/switching that target.
    void drawSelection(sf::RenderTarget &target, const Game &game, const InputController &controller) const;

    // Top-center turn indicator ("White's turn -- Turn N"). Once
    // status() leaves Ongoing, also darkens the whole target and shows a
    // win/draw banner -- status()/winner() read more directly for this
    // than an empty legalMoves() would.
    void drawStatus(sf::RenderTarget &target, const Game &game) const;

    // The Move/Throw buttons for controller.actionOptions(), drawn
    // inside the top bar (drawStatus must run first -- this draws on
    // top of it). No-op when actionOptions() is empty (nothing
    // selected, a Mosquito that hasn't picked an imitation target yet,
    // or -- see drawCancelButton -- mid-throw, where the Cancel button
    // takes this same slot instead). Still missing: the imitation
    // popup (see InputController.h).
    void drawActionMenu(sf::RenderTarget &target, const InputController &controller) const;

    // The explicit Cancel button, shown in the same top-bar slot
    // drawActionMenu's buttons use, only while
    // controller.requiresExplicitCancel() is true (AwaitingVictim/
    // AwaitingThrowDestination -- see InputController.h). Those two
    // states deliberately treat a stray click as a no-op rather than
    // an implicit cancel, since a throw is a two-step commitment
    // touching a second piece -- this is the one, always-visible way
    // out of that flow instead. Never shown at the same time as
    // drawActionMenu's buttons (a piece selection can't be both
    // "choosing an action" and "mid-throw" at once), so reusing the
    // slot can't clash.
    void drawCancelButton(sf::RenderTarget &target, const InputController &controller) const;

    // The Mosquito imitation popup: one glyph icon per
    // controller.imitationOptions() entry, dropped down from the top
    // bar (below it, not inside it -- unlike the Move/Throw buttons,
    // this needs its own room rather than squeezing into the bar's
    // fixed height) and centered in the window. The icon matching
    // controller.currentImitation(), if any, gets a gold outline, same
    // language as every other selection indicator here. No-op when
    // imitationOptions() is empty (nothing selected, a non-Mosquito
    // piece, or an elevated Mosquito -- see ActionMenu.h). Can be shown
    // at the same time as drawActionMenu's buttons (switching imitation
    // target and choosing Move/Throw are independent, per the "at any
    // time" design), but never at the same time as drawCancelButton
    // (imitationOptions() is empty once past ActionMenu into a throw).
    void drawImitationPopup(sf::RenderTarget &target, const Game &game, const InputController &controller) const;

    // Classifies `point` (window-space pixels) against the exact same
    // layout/panel/button geometry drawBoard/drawHands/drawActionMenu/
    // drawCancelButton/drawImitationPopup used for the most recent
    // frame at this windowSize -- main.cpp's event loop calls this once
    // per click instead of duplicating any of that math. `controller`
    // is read-only here (to know which buttons are currently showing);
    // it's up to the caller to act on the result.
    ClickTarget hitTest(sf::Vector2f point, const Game &game, const InputController &controller,
                         sf::Vector2u windowSize) const;

private:
    // Draws one of the ready-made tile+insect images from img/insects.
    // Pillbug has no matching image in that folder, so it falls back to
    // a regular hex plus the legacy transparent glyph.
    void drawPieceTile(sf::RenderTarget &target, Color color, PieceType type, sf::Vector2f center, float hexSize) const;

    // The old transparent glyphs still fit the tiny red status badges:
    // drawing the full img/insects tile there would put a hex inside a
    // circle and make the badge noisy.
    void drawGlyph(sf::RenderTarget &target, sf::Color tint, PieceType type, sf::Vector2f center, float hexSize) const;

    void drawHighlightTile(sf::RenderTarget &target, sf::Vector2f center, float hexSize) const;

    std::unordered_map<Color, std::unordered_map<PieceType, sf::Texture>> pieceTileTextures_;
    std::unordered_map<PieceType, sf::Texture> glyphTextures_;
    sf::Texture backgroundTexture_;
    sf::Texture highlightTexture_;
    sf::Font font_;
};
