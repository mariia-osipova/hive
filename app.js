const PIECES = [
  ["queen", "Queen", "fish", 1], ["spider", "Spider", "spider", 2],
  ["ant", "Ant", "ant", 3], ["mosquito", "Mosquito", "mosquito", 1],
  ["grasshopper", "Grasshopper", "grasshopper", 3], ["beetle", "Beetle", "stag-beetle", 2],
  ["ladybug", "Ladybug", "ladybug", 1], ["pillbug", "Pillbug", "pillbug", 1],
];
const DIRS = [[1, 0], [1, -1], [0, -1], [-1, 0], [-1, 1], [0, 1]];
const byId = id => PIECES.find(piece => piece[0] === id);
const key = (q, r) => `${q},${r}`;
const parse = value => value.split(",").map(Number);
const add = (a, b) => [a[0] + b[0], a[1] + b[1]];
const same = (a, b) => a[0] === b[0] && a[1] === b[1];
const neighbors = hex => DIRS.map(dir => add(hex, dir));
const asset = (type, color) => new URL(`img/insects/${color}/${byId(type)[2]}-${color}-638-550.png`, import.meta.url).href;
const colorLabel = color => color[0].toUpperCase() + color.slice(1);
const canvas = document.querySelector("#board");
const ctx = canvas.getContext("2d");
const sound = document.querySelector("#placementSound");
const initialHand = () => Object.fromEntries(PIECES.map(([id, , , count]) => [id, count]));
const hands = { white: initialHand(), black: initialHand() };
const state = { board: new Map(), turn: "white", turnNumber: 1, lastMoved: null, status: "ongoing", mode: "idle", selectedHex: null, selectedHand: null, candidates: [], imitation: null };

function top(hex) { return state.board.get(key(...hex))?.at(-1) ?? null; }
function occupied(hex) { return state.board.has(key(...hex)); }
function height(hex) { return state.board.get(key(...hex))?.length ?? 0; }
function cells() { return [...state.board.keys()].map(parse); }
function emptyNeighbors(hex) { return neighbors(hex).filter(next => !occupied(next)); }
function occupiedNeighbors(hex) { return neighbors(hex).filter(occupied); }
function connectedWithout(from) {
  const remaining = new Set(state.board.keys()); if (height(from) <= 1) remaining.delete(key(...from));
  if (remaining.size < 2) return true;
  const start = remaining.values().next().value, seen = new Set([start]), queue = [start];
  while (queue.length) for (const next of neighbors(parse(queue.shift()))) { const value = key(...next); if (remaining.has(value) && !seen.has(value)) { seen.add(value); queue.push(value); } }
  return seen.size === remaining.size;
}
function canSlide(from, to) {
  const index = DIRS.findIndex(dir => same(add(from, dir), to)); if (index < 0) return false;
  return !occupied(add(from, DIRS[(index + 1) % 6])) || !occupied(add(from, DIRS[(index + 5) % 6]));
}
function attached(to, from) {
  if (state.board.size <= 1) return true;
  return neighbors(to).some(next => { const value = key(...next); return state.board.has(value) && (value !== key(...from) || height(from) > 1); });
}
function queenMoves(from, movingFrom = from) { return emptyNeighbors(from).filter(to => canSlide(from, to) && attached(to, movingFrom)); }
function beetleMoves(from) { const onPile = height(from) > 1; return neighbors(from).filter(to => occupied(to) || onPile || (canSlide(from, to) && attached(to, from))); }
function grasshopperMoves(from) { const result = []; for (const dir of DIRS) { let cursor = add(from, dir); if (!occupied(cursor)) continue; while (occupied(cursor)) cursor = add(cursor, dir); result.push(cursor); } return result; }
function antMoves(from) { const seen = new Set([key(...from)]), result = [], queue = [from]; while (queue.length) for (const next of queenMoves(queue.shift(), from)) { const value = key(...next); if (!seen.has(value)) { seen.add(value); result.push(next); queue.push(next); } } return result; }
function spiderMoves(from) { const result = new Set(); function walk(current, depth, visited) { if (depth === 3) { result.add(key(...current)); return; } for (const next of queenMoves(current, from)) { const value = key(...next); if (!visited.has(value)) walk(next, depth + 1, new Set([...visited, value])); } } walk(from, 0, new Set([key(...from)])); return [...result].map(parse); }
function ladybugMoves(from) { const climbed = new Set(); const graphNeighbors = hex => neighbors(hex).filter(next => occupied(next) && key(...next) !== key(...from)); for (const first of occupiedNeighbors(from)) for (const second of graphNeighbors(first)) climbed.add(key(...second)); const result = new Set(); for (const hex of climbed) for (const destination of emptyNeighbors(parse(hex))) result.add(key(...destination)); return [...result].map(parse); }
function movement(type, from) { if (["queen", "pillbug"].includes(type)) return queenMoves(from); if (type === "beetle") return beetleMoves(from); if (type === "grasshopper") return grasshopperMoves(from); if (type === "ant") return antMoves(from); if (type === "spider") return spiderMoves(from); if (type === "ladybug") return ladybugMoves(from); return []; }
function imitatable(from) { const result = []; for (const neighbor of occupiedNeighbors(from)) { const type = top(neighbor).type; if (type !== "mosquito" && !result.includes(type)) result.push(type); } return result; }
function throwsFrom(from) { return occupiedNeighbors(from).filter(victim => height(victim) === 1 && top(victim).id !== state.lastMoved && connectedWithout(victim)).flatMap(victim => emptyNeighbors(from).map(destination => ({ kind: "throw", pillbug: from, victim, destination }))); }
function placementSpots() { const occupiedCells = cells(); if (!occupiedCells.length) return [[0, 0]]; if (occupiedCells.length === 1) return emptyNeighbors(occupiedCells[0]); const candidates = new Set(); for (const cell of occupiedCells) for (const empty of emptyNeighbors(cell)) candidates.add(key(...empty)); return [...candidates].map(parse).filter(hex => occupiedNeighbors(hex).every(neighbor => top(neighbor).color === state.turn)); }
function legalMoves() {
  if (state.status !== "ongoing") return [];
  const moves = [], hand = hands[state.turn], turnForPlayer = Math.floor((state.turnNumber + 1) / 2);
  const types = turnForPlayer === 4 && hand.queen > 0 ? ["queen"] : PIECES.map(piece => piece[0]).filter(type => hand[type] > 0);
  for (const type of types) for (const destination of placementSpots()) moves.push({ kind: "placement", type, destination });
  if (hand.queen > 0) return moves;
  for (const from of cells()) {
    const piece = top(from); if (piece.color !== state.turn || piece.id === state.lastMoved) continue;
    if (piece.type === "mosquito") {
      if (height(from) > 1) { if (connectedWithout(from)) for (const destination of beetleMoves(from)) moves.push({ kind: "movement", from, destination }); }
      else if (connectedWithout(from)) { for (const imitate of imitatable(from)) for (const destination of movement(imitate, from)) moves.push({ kind: "mosquito", from, imitate, destination }); if (imitatable(from).includes("pillbug")) moves.push(...throwsFrom(from)); }
    } else {
      if (connectedWithout(from)) for (const destination of movement(piece.type, from)) moves.push({ kind: "movement", from, destination });
      if (piece.type === "pillbug") moves.push(...throwsFrom(from));
    }
  }
  return moves;
}
function source(move) { return move.kind === "placement" ? null : move.from ?? move.pillbug; }
function destination(move) { return move.destination; }
function equalMove(a, b) { return a.kind === b.kind && same(destination(a), destination(b)) && (!source(a) || same(source(a), source(b))) && (a.type ?? a.imitate) === (b.type ?? b.imitate); }
function updateStatus() { const surrounded = color => cells().some(hex => state.board.get(key(...hex)).some(piece => piece.color === color && piece.type === "queen") && occupiedNeighbors(hex).length === 6); const white = surrounded("white"), black = surrounded("black"); state.status = white && black ? "draw" : white ? "black-wins" : black ? "white-wins" : "ongoing"; }
function resetSelection() { state.mode = "idle"; state.selectedHex = null; state.selectedHand = null; state.candidates = []; state.imitation = null; }
function applyMove(move) {
  if (!legalMoves().some(candidate => equalMove(candidate, move))) return false;
  let moved;
  if (move.kind === "placement") { moved = { id: `${state.turn}-${state.turnNumber}`, type: move.type, color: state.turn }; state.board.set(key(...move.destination), [moved]); hands[state.turn][move.type]--; }
  else { const from = move.kind === "throw" ? move.victim : move.from, stack = state.board.get(key(...from)); moved = stack.pop(); if (!stack.length) state.board.delete(key(...from)); const target = key(...move.destination); state.board.set(target, [...(state.board.get(target) ?? []), moved]); }
  state.lastMoved = moved.id; state.turn = state.turn === "white" ? "black" : "white"; state.turnNumber++; updateStatus(); resetSelection(); if (sound?.src) { sound.currentTime = 0; sound.play().catch(() => {}); } render(); return true;
}
function chooseHand(type) { const candidates = legalMoves().filter(move => move.kind === "placement" && move.type === type); if (candidates.length) { state.mode = "destination"; state.selectedHand = type; state.candidates = candidates; render(); } }
function selectBoard(hex) {
  const candidates = legalMoves().filter(move => source(move) && same(source(move), hex));
  if (!candidates.length) { resetSelection(); render(); return; }
  const direct = candidates.filter(move => move.kind === "movement" || move.kind === "mosquito");
  state.selectedHex = hex; state.imitation = null;
  if (direct.length) { state.mode = "destination"; state.candidates = direct; }
  else { state.mode = "victim"; state.candidates = candidates.filter(move => move.kind === "throw"); }
  render();
}
function actionOptions() { const move = state.candidates.some(candidate => candidate.kind === "movement" || (candidate.kind === "mosquito" && candidate.imitate === state.imitation)); const throwing = state.candidates.some(candidate => candidate.kind === "throw") && (!state.candidates.some(candidate => candidate.kind === "mosquito") || state.imitation === "pillbug"); return [move && "Move", throwing && "Throw"].filter(Boolean); }
function imitationOptions() { return state.selectedHex && top(state.selectedHex)?.type === "mosquito" ? [...new Set(state.candidates.filter(move => move.kind === "mosquito").map(move => move.imitate).concat(state.candidates.some(move => move.kind === "throw") ? ["pillbug"] : []))] : []; }
function chooseAction(kind) { const candidates = kind === "Move" ? state.candidates.filter(move => move.kind === "movement" || (move.kind === "mosquito" && move.imitate === state.imitation)) : state.candidates.filter(move => move.kind === "throw"); if (candidates.length) { state.mode = kind === "Move" ? "destination" : "victim"; state.candidates = candidates; render(); } }
function boardClick(hex) { if (state.mode === "idle") return selectBoard(hex); if (state.mode === "action") return same(hex, state.selectedHex) ? (resetSelection(), render()) : selectBoard(hex); if (state.mode === "destination") { const move = state.candidates.find(candidate => same(destination(candidate), hex)); return move ? applyMove(move) : (state.mode = "action", render()); } if (state.mode === "victim") { const candidates = state.candidates.filter(move => same(move.victim, hex)); if (candidates.length) { state.mode = "throw-destination"; state.candidates = candidates; render(); } return; } const move = state.candidates.find(candidate => same(candidate.destination, hex)); if (move) applyMove(move); }

function boardCells() { const result = new Set(state.board.keys()); for (const cell of state.board.keys()) for (const neighbor of neighbors(parse(cell))) result.add(key(...neighbor)); for (const move of state.candidates) result.add(key(...destination(move))); if (!result.size) result.add("0,0"); return [...result].map(parse); }
function layout() {
  const rect = canvas.getBoundingClientRect();
  const windowWidth = window.innerWidth, windowHeight = window.innerHeight;
  const playableLeft = 190 + 55, playableRight = windowWidth - 190 - 55;
  const playableTop = 64 + 55, playableBottom = windowHeight - 55;
  const desired = [(playableLeft + playableRight) / 2, (playableTop + playableBottom) / 2];
  const occupied = cells();
  let scale = 0.32, offset = [0, 0];
  if (occupied.length) {
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const [q, r] of occupied) { const x = 528 * q, y = 308 * q + 616 * r; minX = Math.min(minX, x); maxX = Math.max(maxX, x); minY = Math.min(minY, y); maxY = Math.max(maxY, y); }
    minX -= 319; maxX += 319; minY -= 275; maxY += 275;
    scale = Math.max(0.025, Math.min(0.32, (playableRight - playableLeft) / (maxX - minX), (playableBottom - playableTop) / (maxY - minY)));
    offset = [(minX + maxX) / 2, (minY + maxY) / 2];
  }
  return { rect, scale, size: 319 * scale, origin: [desired[0] - offset[0] * scale, desired[1] - offset[1] * scale], qStep: [528 * scale, 308 * scale], rStep: [0, 616 * scale] };
}
function toPixel(hex, boardLayout) { return [boardLayout.origin[0] + boardLayout.qStep[0] * hex[0] + boardLayout.rStep[0] * hex[1], boardLayout.origin[1] + boardLayout.qStep[1] * hex[0] + boardLayout.rStep[1] * hex[1]]; }
function fromPixel(point, boardLayout) {
  const x = point[0] - boardLayout.origin[0], y = point[1] - boardLayout.origin[1];
  const det = boardLayout.qStep[0] * boardLayout.rStep[1] - boardLayout.qStep[1] * boardLayout.rStep[0];
  const qf = (x * boardLayout.rStep[1] - y * boardLayout.rStep[0]) / det;
  const rf = (boardLayout.qStep[0] * y - boardLayout.qStep[1] * x) / det;
  const sf = -qf - rf; let q = Math.round(qf), r = Math.round(rf), s = Math.round(sf);
  const qDiff = Math.abs(q - qf), rDiff = Math.abs(r - rf), sDiff = Math.abs(s - sf);
  if (qDiff > rDiff && qDiff > sDiff) q = -r - s; else if (rDiff > sDiff) r = -q - s;
  return [q, r];
}
function hexPath(point, size) { const path = new Path2D(); for (let i = 0; i < 6; i++) { const angle = Math.PI / 3 * i + Math.PI / 6, x = point[0] + size * Math.cos(angle), y = point[1] + size * .862 * Math.sin(angle); i ? path.lineTo(x, y) : path.moveTo(x, y); } path.closePath(); return path; }
const imageCache = new Map();
function imageFor(type, color) { const src = asset(type, color); if (!imageCache.has(src)) { const image = new Image(); image.onload = draw; image.src = src; imageCache.set(src, image); } return imageCache.get(src); }
let highlightTexture = null;
let selectionTexture = null;
const highlightSource = new Image();
highlightSource.onload = () => {
  const source = document.createElement("canvas"), sourceContext = source.getContext("2d");
  source.width = highlightSource.naturalWidth; source.height = highlightSource.naturalHeight;
  sourceContext.drawImage(highlightSource, 0, 0);
  const image = sourceContext.getImageData(0, 0, source.width, source.height);
  const originalAlpha = new Uint8ClampedArray(image.data);
  const edgeRadius = 12, threshold = 8;
  for (let y = 0; y < source.height; y++) for (let x = 0; x < source.width; x++) {
    const index = (y * source.width + x) * 4, alpha = originalAlpha[index + 3];
    if (alpha <= threshold) continue;
    let edge = false;
    for (let dy = -edgeRadius; dy <= edgeRadius && !edge; dy++) for (let dx = -edgeRadius; dx <= edgeRadius; dx++) {
      const nx = x + dx, ny = y + dy;
      if (nx < 0 || ny < 0 || nx >= source.width || ny >= source.height || originalAlpha[(ny * source.width + nx) * 4 + 3] <= threshold) { edge = true; break; }
    }
    image.data[index] = edge ? 28 : 54; image.data[index + 1] = edge ? 215 : 225; image.data[index + 2] = edge ? 104 : 120; image.data[index + 3] = edge ? 235 : 52;
  }
  sourceContext.putImageData(image, 0, 0); highlightTexture = source;
  const selection = document.createElement("canvas"), selectionContext = selection.getContext("2d");
  selection.width = source.width; selection.height = source.height;
  const selectionImage = selectionContext.createImageData(selection.width, selection.height);
  for (let y = 0; y < source.height; y++) for (let x = 0; x < source.width; x++) {
    const index = (y * source.width + x) * 4, alpha = originalAlpha[index + 3];
    if (alpha > 8 && (x < 12 || y < 12 || x >= source.width - 12 || y >= source.height - 12 || originalAlpha[(y * source.width + Math.max(0, x - 12)) * 4 + 3] <= 8 || originalAlpha[(Math.min(source.height - 1, y + 12) * source.width + x) * 4 + 3] <= 8)) {
      selectionImage.data[index] = 255; selectionImage.data[index + 1] = 205; selectionImage.data[index + 2] = 60; selectionImage.data[index + 3] = 255;
    }
  }
  selectionContext.putImageData(selectionImage, 0, 0); selectionTexture = selection; draw();
};
highlightSource.src = new URL("img/insects/white/bee-white-638-550.png", import.meta.url).href;
function draw() {
  const boardLayout = layout(), { rect, size } = boardLayout, dpr = window.devicePixelRatio || 1;
  const stage = document.querySelector(".board-stage");
  if (stage) {
    stage.style.backgroundSize = `${2112 * boardLayout.scale}px ${2464 * boardLayout.scale}px`;
    stage.style.backgroundPosition = `${boardLayout.origin[0] - rect.left - 527.5 * boardLayout.scale}px ${boardLayout.origin[1] - rect.top - 307.5 * boardLayout.scale}px`;
  }
  canvas.width = rect.width * dpr; canvas.height = rect.height * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, rect.width, rect.height);
  const targetKeys = new Set(state.candidates.map(move => key(...destination(move))));
  for (const hex of boardCells()) {
    const globalPoint = toPixel(hex, boardLayout), point = [globalPoint[0] - rect.left, globalPoint[1] - rect.top];
    const value = key(...hex);
    const piece = top(hex); if (!piece) continue;
    const image = imageFor(piece.type, piece.color);
    if (image.complete) ctx.drawImage(image, point[0] - size, point[1] - size * .862, size * 2, size * 1.724);
    const stack = state.board.get(value);
    if (stack.length > 1) {
      ctx.fillStyle = "#8e3f4b"; ctx.beginPath(); ctx.arc(point[0] + size * .55, point[1] + size * .55, size * .23, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = "#fff7e8"; ctx.font = `700 ${Math.max(11, size * .24)}px HiveSans`; ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillText(stack.length, point[0] + size * .55, point[1] + size * .55);
    }
  }
  // The original SFML renderer draws board pieces first and selections/highlights
  // afterwards. This second pass keeps beetle destinations visible even when
  // the destination is an occupied hexagon.
  for (const hex of boardCells()) {
    const globalPoint = toPixel(hex, boardLayout), point = [globalPoint[0] - rect.left, globalPoint[1] - rect.top];
    const value = key(...hex);
    if (targetKeys.has(value) && highlightTexture) { const scale = Math.min((2 * size) / highlightTexture.width, (Math.sqrt(3) * size) / highlightTexture.height); const width = highlightTexture.width * scale, height = highlightTexture.height * scale; ctx.drawImage(highlightTexture, point[0] - width / 2, point[1] - height / 2, width, height); }
    if (state.selectedHex && same(hex, state.selectedHex) && selectionTexture) { const scale = Math.min((2 * size) / selectionTexture.width, (Math.sqrt(3) * size) / selectionTexture.height); const width = selectionTexture.width * scale, height = selectionTexture.height * scale; ctx.drawImage(selectionTexture, point[0] - width / 2, point[1] - height / 2, width, height); }
  }
}
function renderHands(color) { const root = document.querySelector(`#${color}Hand`); root.replaceChildren(); for (const [id, name] of PIECES) { const button = document.createElement("button"); button.className = `piece-card ${state.selectedHand === id ? "selected" : ""}`; button.type = "button"; button.disabled = color !== state.turn || hands[color][id] === 0; const image = document.createElement("img"); image.src = asset(id, color); image.alt = name; button.append(image); const label = document.createElement("span"); label.className = "piece-name"; label.textContent = name; button.append(label); const count = document.createElement("span"); count.className = "piece-count"; count.textContent = `x${hands[color][id]}`; button.append(count); button.addEventListener("click", () => chooseHand(id)); root.append(button); } }
function renderMenu() { const menu = document.querySelector("#actionMenu"); menu.replaceChildren(); if (state.mode === "action") for (const option of actionOptions()) { const button = document.createElement("button"); button.type = "button"; button.textContent = option; button.addEventListener("click", () => chooseAction(option)); menu.append(button); } if (["victim", "throw-destination"].includes(state.mode)) { const button = document.createElement("button"); button.type = "button"; button.textContent = "Cancel"; button.className = "cancel"; button.addEventListener("click", () => { state.mode = "action"; state.candidates = legalMoves().filter(move => source(move) && same(source(move), state.selectedHex)); render(); }); menu.append(button); } const imitation = document.querySelector("#imitationMenu"); if (imitation) { imitation.replaceChildren(); for (const type of imitationOptions()) { const button = document.createElement("button"); button.type = "button"; button.textContent = type; button.className = type === state.imitation ? "selected" : ""; button.addEventListener("click", () => { state.imitation = type; render(); }); imitation.append(button); } } }
function render() { renderHands("white"); renderHands("black"); renderMenu(); draw(); const label = state.status === "ongoing" ? `${colorLabel(state.turn)}'s turn -- Turn ${state.turnNumber}` : state.status === "draw" ? "Draw!" : `${colorLabel(state.status.replace("-wins", ""))} wins!`; document.querySelector("#turnReadout").textContent = label; const status = document.querySelector("#statusText"); if (status) status.textContent = state.mode === "destination" ? "Choose a highlighted destination" : state.mode === "victim" ? "Choose a piece to throw" : state.mode === "throw-destination" ? "Choose a throw destination" : "Choose a piece"; }
canvas.addEventListener("click", event => { boardClick(fromPixel([event.clientX, event.clientY], layout())); });
document.querySelector("#resetButton")?.addEventListener("click", () => { state.board.clear(); hands.white = initialHand(); hands.black = initialHand(); state.turn = "white"; state.turnNumber = 1; state.lastMoved = null; state.status = "ongoing"; resetSelection(); render(); });
window.addEventListener("resize", draw);
render();
