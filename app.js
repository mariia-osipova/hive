const PIECES = [
  ["queen", "Queen", "fish", 1], ["spider", "Spider", "spider", 2],
  ["ant", "Ant", "ant", 3], ["mosquito", "Mosquito", "mosquito", 1],
  ["grasshopper", "Grasshopper", "grasshopper", 3], ["beetle", "Beetle", "stag-beetle", 2],
  ["ladybug", "Ladybug", "ladybug", 1], ["pillbug", "Pillbug", "pillbug", 1],
];
const DIRS = [[1, 0], [1, -1], [0, -1], [-1, 0], [-1, 1], [0, 1]];
const key = (q, r) => `${q},${r}`;
const parseKey = (value) => value.split(",").map(Number);
const add = (a, b) => [a[0] + b[0], a[1] + b[1]];
const same = (a, b) => a[0] === b[0] && a[1] === b[1];
const neighbors = (hex) => DIRS.map((dir) => add(hex, dir));
const canvas = document.querySelector("#board");
const ctx = canvas.getContext("2d");
const state = { board: new Map(), turn: "white", turnNumber: 1, lastMoved: null, selectedHand: null, selectedHex: null, pendingTargets: new Set(), targets: new Set(), message: "Choose a piece from your hand" };
const emptyHand = () => Object.fromEntries(PIECES.map(([id, , , count]) => [id, count]));
const hands = { white: emptyHand(), black: emptyHand() };
const imageCache = new Map();
const sound = document.querySelector("#placementSound");

function asset(id, color) {
  const piece = PIECES.find(([pieceId]) => pieceId === id);
  return new URL(`img/insects/${color}/${piece[2]}-${color}-638-550.png`, import.meta.url).href;
}
function imageFor(id, color) {
  const src = asset(id, color);
  if (!imageCache.has(src)) {
    const image = new Image();
    image.onload = () => draw();
    image.onerror = () => console.error(`Could not load piece image: ${src}`);
    image.src = src;
    imageCache.set(src, image);
  }
  return imageCache.get(src);
}
function occupied(hex) { return state.board.has(key(...hex)); }
function top(hex) { const stack = state.board.get(key(...hex)); return stack?.at(-1) ?? null; }

function axialToPixel(hex, size, center) { return [center[0] + size * 1.5 * hex[0], center[1] + size * Math.sqrt(3) * (hex[1] + hex[0] / 2)]; }
function pixelToAxial(point, size, center) {
  const x = (point[0] - center[0]) / size, y = (point[1] - center[1]) / size;
  const qf = (2 / 3) * x, rf = (-1 / 3) * x + (Math.sqrt(3) / 3) * y;
  let q = Math.round(qf), r = Math.round(rf), s = Math.round(-qf - rf);
  if (Math.abs(q - qf) > Math.abs(r - rf) && Math.abs(q - qf) > Math.abs(s + qf + rf)) q = -r - s;
  else if (Math.abs(r - rf) > Math.abs(s + qf + rf)) r = -q - s;
  return [q, r];
}
function hexPath(center, size) { const path = new Path2D(); for (let i = 0; i < 6; i++) { const angle = Math.PI / 180 * (60 * i); const point = [center[0] + size * Math.cos(angle), center[1] + size * Math.sin(angle)]; i ? path.lineTo(...point) : path.moveTo(...point); } path.closePath(); return path; }
function boardCells() { const cells = new Set(state.board.keys()); for (const cell of state.board.keys()) for (const neighbor of neighbors(parseKey(cell))) cells.add(key(...neighbor)); for (const target of state.targets) cells.add(target); if (!cells.size) cells.add("0,0"); return [...cells].map(parseKey); }
function geometry() { const rect = canvas.getBoundingClientRect(), cells = boardCells(); const qs = cells.map(([q]) => q), rs = cells.map(([, r]) => r); const spanX = Math.max(4, Math.max(...qs) - Math.min(...qs) + 3), spanY = Math.max(4, Math.max(...rs) - Math.min(...rs) + 3); return { rect, size: Math.max(24, Math.min((rect.width - 56) / (1.5 * spanX), (rect.height - 56) / (Math.sqrt(3) * spanY))), center: [rect.width / 2, rect.height / 2] }; }

function draw() {
  const { rect, size, center } = geometry(), dpr = window.devicePixelRatio || 1;
  canvas.width = rect.width * dpr; canvas.height = rect.height * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, rect.width, rect.height);
  for (const hex of boardCells()) {
    const point = axialToPixel(hex, size, center), value = key(...hex), path = hexPath(point, size - 2);
    ctx.fillStyle = state.targets.has(value) ? "#77bd91" : "#d9a9a1"; ctx.fill(path); ctx.strokeStyle = state.targets.has(value) ? "#2d7e5b" : "#c5817e"; ctx.lineWidth = 2; ctx.stroke(path);
    if (state.selectedHex && same(hex, state.selectedHex)) { ctx.strokeStyle = "#f7d36b"; ctx.lineWidth = 4; ctx.stroke(hexPath(point, size - 4)); }
    const piece = top(hex); if (!piece) continue; const image = imageFor(piece.type, piece.color); if (image.complete) ctx.drawImage(image, point[0] - size, point[1] - size * .862, size * 2, size * 1.724);
    const stack = state.board.get(value); if (stack.length > 1) { ctx.fillStyle = "#8e3f4b"; ctx.beginPath(); ctx.arc(point[0] + size * .55, point[1] + size * .55, size * .23, 0, Math.PI * 2); ctx.fill(); ctx.fillStyle = "#fff7e8"; ctx.font = `700 ${Math.max(11, size * .24)}px DM Sans`; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(stack.length, point[0] + size * .55, point[1] + size * .55); }
  }
}

function connectedAfterMoving(from) { const remaining = new Set(state.board.keys()); remaining.delete(key(...from)); if (remaining.size < 2) return true; const start = remaining.values().next().value, seen = new Set([start]), queue = [start]; while (queue.length) { const current = parseKey(queue.shift()); for (const neighbor of neighbors(current)) { const value = key(...neighbor); if (remaining.has(value) && !seen.has(value)) { seen.add(value); queue.push(value); } } } return seen.size === remaining.size; }
function canSlide(from, to) { const shared = neighbors(from).filter((hex) => neighbors(to).some((other) => same(hex, other))); return shared.some((hex) => !occupied(hex)); }
function attachedAfterMove(from, to) { if (state.board.size <= 1) return true; const remaining = new Set(state.board.keys()); remaining.delete(key(...from)); return neighbors(to).some((hex) => remaining.has(key(...hex))); }
function emptyNeighborMoves(from) { return neighbors(from).filter((to) => !occupied(to) && canSlide(from, to) && attachedAfterMove(from, to)); }
function movementTargets(from, piece) {
  if (!connectedAfterMoving(from)) return [];
  if (["queen", "pillbug"].includes(piece.type)) return emptyNeighborMoves(from);
  if (piece.type === "beetle") return neighbors(from).filter((to) => occupied(to) || (canSlide(from, to) && attachedAfterMove(from, to)));
  if (piece.type === "grasshopper") return DIRS.flatMap((dir) => { let cursor = add(from, dir); if (!occupied(cursor)) return []; while (occupied(cursor)) cursor = add(cursor, dir); return [cursor]; });
  if (piece.type === "ant") { const found = new Set(), queue = [...emptyNeighborMoves(from)]; queue.forEach((hex) => found.add(key(...hex))); while (queue.length) { const current = queue.shift(); for (const next of emptyNeighborMoves(current)) { const value = key(...next); if (!found.has(value) && !same(next, from)) { found.add(value); queue.push(next); } } } return [...found].map(parseKey); }
  if (piece.type === "spider") { const found = new Set(); function walk(current, depth, visited) { if (depth === 3) { found.add(key(...current)); return; } for (const next of emptyNeighborMoves(current)) { const value = key(...next); if (!visited.has(value)) walk(next, depth + 1, new Set([...visited, value])); } } walk(from, 0, new Set([key(...from)])); return [...found].map(parseKey); }
  return [];
}
function placementTargets() {
  if (!state.board.size) return [[0, 0]];
  const candidates = new Set(); for (const cell of state.board.keys()) for (const neighbor of neighbors(parseKey(cell))) if (!occupied(neighbor)) candidates.add(key(...neighbor));
  return [...candidates].map(parseKey).filter((hex) => { const touching = neighbors(hex).filter(occupied); return touching.length && (state.board.size === 1 || touching.every((neighbor) => top(neighbor).color === state.turn)); });
}
function availableTypes() { const personalTurn = Math.ceil(state.turnNumber / 2), hand = hands[state.turn]; return PIECES.filter(([id]) => hand[id] > 0 && !(personalTurn >= 4 && hand.queen > 0 && id !== "queen")); }
function selectHand(type) { if (!availableTypes().some(([id]) => id === type)) return; state.selectedHand = type; state.selectedHex = null; state.targets = new Set(placementTargets().map((hex) => key(...hex))); state.message = `Place ${PIECES.find(([id]) => id === type)[1]}`; render(); }
function selectBoard(hex) { const piece = top(hex); if (!piece || piece.color !== state.turn || state.lastMoved === key(...hex) || hands[state.turn].queen > 0) return; state.selectedHex = hex; state.selectedHand = null; state.pendingTargets = new Set(movementTargets(hex, piece).map((target) => key(...target))); state.targets = new Set(); state.message = state.pendingTargets.size ? `Selected ${piece.type}` : "This piece has no legal destination"; render(); }
function chooseMove() { state.targets = new Set(state.pendingTargets); state.message = "Choose a green destination"; render(); }
function playSound() { if (!sound.src) return; sound.currentTime = 0; sound.play().catch(() => {}); }
function moveTo(hex) { const value = key(...hex); if (!state.targets.has(value)) { state.message = "Choose a highlighted hex"; render(); return; } if (state.selectedHand) { state.board.set(value, [{ type: state.selectedHand, color: state.turn }]); hands[state.turn][state.selectedHand]--; playSound(); } else { const stack = state.board.get(key(...state.selectedHex)); const piece = stack.pop(); if (!stack.length) state.board.delete(key(...state.selectedHex)); state.board.set(value, [...(state.board.get(value) || []), piece]); } state.lastMoved = value; state.turn = state.turn === "white" ? "black" : "white"; state.turnNumber++; state.selectedHand = null; state.selectedHex = null; state.targets = new Set(); state.message = "Choose a piece from your hand"; render(); }
function renderHand(color) {
  const root = document.querySelector(`#${color}Hand`);
  root.replaceChildren();
  for (const [id, name, , initial] of PIECES) {
    const button = document.createElement("button");
    button.className = `piece-card ${state.selectedHand === id && state.turn === color ? "selected" : ""}`;
    button.type = "button";
    button.disabled = color !== state.turn || hands[color][id] === 0;

    const image = document.createElement("img");
    image.src = asset(id, color);
    image.alt = name;
    image.width = 68;
    image.height = 68;
    image.onerror = () => console.error(`Could not load hand image: ${image.src}`);
    button.append(image);

    const label = document.createElement("span");
    label.className = "piece-name";
    label.textContent = name;
    button.append(label);

    const count = document.createElement("span");
    count.className = "piece-count";
    count.textContent = `${hands[color][id]}/${initial}`;
    button.append(count);
    button.addEventListener("click", () => selectHand(id));
    root.append(button);
  }
}
function render() { draw(); renderHand("white"); renderHand("black"); document.querySelector("#turnReadout").innerHTML = `${state.turn[0].toUpperCase() + state.turn.slice(1)} to move <span>${String(state.turnNumber).padStart(2, "0")}</span>`; document.querySelector("#statusText").textContent = state.message; document.querySelector("#hintText").textContent = state.selectedHand ? "Click a green hex to place the piece." : state.selectedHex ? "Click a green hex to move the selected piece." : "Select a tile from the hand, then place it on a highlighted hex."; document.querySelector("#whiteScore").textContent = [...state.board.values()].flat().filter((piece) => piece.color === "white").length; document.querySelector("#blackScore").textContent = [...state.board.values()].flat().filter((piece) => piece.color === "black").length; document.querySelector("#boardEmpty").classList.toggle("hidden", state.board.size > 0); }

function render() {
  renderHand("white");
  renderHand("black");
  draw();
  document.querySelector("#turnReadout").textContent = `${state.turn[0].toUpperCase() + state.turn.slice(1)}'s turn -- Turn ${state.turnNumber}`;
  document.querySelector("#statusText").textContent = state.message;
  document.querySelector("#hintText").textContent = state.selectedHand ? "Click a green hex to place the piece." : state.selectedHex ? "Choose Move, then click a green hex." : "Select a tile from the hand, then place it on a highlighted hex.";
  document.querySelector("#whiteScore").textContent = [...state.board.values()].flat().filter((piece) => piece.color === "white").length;
  document.querySelector("#blackScore").textContent = [...state.board.values()].flat().filter((piece) => piece.color === "black").length;
  const actionMenu = document.querySelector("#actionMenu");
  actionMenu.innerHTML = state.selectedHex && state.pendingTargets.size ? '<button type="button" title="Move">Move</button>' : "";
  const moveButton = actionMenu.querySelector("button");
  if (moveButton) moveButton.addEventListener("click", chooseMove);
}

canvas.addEventListener("click", (event) => { const { rect, size, center } = geometry(), point = [event.clientX - rect.left, event.clientY - rect.top], hex = pixelToAxial(point, size, center); if (state.targets.has(key(...hex))) moveTo(hex); else if (occupied(hex)) selectBoard(hex); });
document.querySelector("#resetButton").addEventListener("click", () => { state.board.clear(); state.turn = "white"; state.turnNumber = 1; state.lastMoved = null; state.selectedHand = null; state.selectedHex = null; state.targets = new Set(); Object.assign(hands.white, emptyHand()); Object.assign(hands.black, emptyHand()); state.message = "Choose a piece from your hand"; render(); });
window.addEventListener("resize", draw); render();
