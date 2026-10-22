# Beekeeper opening parity check

This is a narrow move-set comparison, not a claim that Beekeeper is a complete
rules oracle.

## Position and mapping

The same position was built in both engines:

1. White places an Ant at axial `(0, 0)`.
2. Black places an Ant at axial `(1, 0)`.
3. Compare White's placement actions before either Queen is placed.

Beekeeper fixes its second opening placement to one adjacent tile to reduce
opening symmetries. Its skew-grid coordinates map to this engine's axial system
as `q = x - y`, `r = y - y0`, where `y0` is the initial center row. That turns
the fixed second opening tile into `(1, 0)`.

## Result

Both move generators returned 15 legal placements: each of Queen, Spider,
Beetle, Grasshopper, and Ant at each of these three cells:

- `(-1, 0)`
- `(-1, 1)`
- `(0, -1)`

The reproducible first-party assertion is
`AlphaZeroRules.OpeningPlacementSetMatchesBeekeeperAfterCanonicalSecondMove`.
The temporary Beekeeper comparison compiled its move generator directly and
did not copy its implementation into the project.

## Limits

This compares only placement generation for one opening state. It does not
check piece movement, stacking, Pass, repetition, or terminal outcomes. The
Beekeeper reference snapshot has a commented-out repetition check, a compile-time
turn cap, and no discovered license file; it remains ignored and should not be
treated as a full behavioral oracle.
