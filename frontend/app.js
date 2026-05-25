/* global Chess, Chessboard */

const game = new Chess();
let board = null;
let boardOrientation = "white";
let fetchTimer = null;

function fenForApi() {
  return game.fen();
}

function uciFromMove(move) {
  const from = move.from;
  const to = move.to;
  const promo = move.promotion ? move.promotion : "";
  return from + to + promo;
}

async function fetchHealth() {
  const res = await fetch("/api/health");
  return res.json();
}

async function fetchStats(fen) {
  const url = `/api/position/stats?fen=${encodeURIComponent(fen)}`;
  const res = await fetch(url);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

function pct(n) {
  return (n * 100).toFixed(1) + "%";
}

function renderStats(data) {
  const tbody = document.querySelector("#stats-table tbody");
  const movesBody = document.querySelector("#moves-table tbody");
  const emptyEl = document.getElementById("stats-empty");
  const summary = document.getElementById("position-summary");

  tbody.innerHTML = "";
  movesBody.innerHTML = "";

  const bins = data.bins || [];
  const moves = data.moves || [];
  const totalMoveGames = moves.reduce((s, m) => s + m.games, 0);

  if (bins.length === 0) {
    emptyEl.classList.remove("hidden");
    summary.textContent = `Position ${data.position_key} — not in database yet`;
    return;
  }

  emptyEl.classList.add("hidden");
  summary.textContent =
    `Position ${data.position_key} — ${data.total_games.toLocaleString()} game-occurrences in DB`;

  for (const row of bins) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${row.elo_label}</td>
      <td>${row.games.toLocaleString()}</td>
      <td class="pct-win">${pct(row.win_rate)}</td>
      <td class="pct-draw">${pct(row.draw_rate)}</td>
      <td class="pct-loss">${pct(row.loss_rate)}</td>
    `;
    tbody.appendChild(tr);
  }

  for (const m of moves) {
    const share = totalMoveGames > 0 ? m.games / totalMoveGames : 0;
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><code>${m.uci}</code></td>
      <td>${m.games.toLocaleString()}</td>
      <td>${pct(share)}</td>
    `;
    movesBody.appendChild(tr);
  }
}

function scheduleStatsRefresh() {
  document.getElementById("fen-display").value = fenForApi();
  clearTimeout(fetchTimer);
  fetchTimer = setTimeout(async () => {
    try {
      const data = await fetchStats(fenForApi());
      renderStats(data);
    } catch (err) {
      console.error(err);
      document.getElementById("position-summary").textContent =
        "Error loading stats: " + err.message;
    }
  }, 150);
}

function onDragStart(source, piece) {
  if (game.game_over()) return false;
  if (
    (game.turn() === "w" && piece.search(/^b/) !== -1) ||
    (game.turn() === "b" && piece.search(/^w/) !== -1)
  ) {
    return false;
  }
}

function onDrop(source, target) {
  let promotion = undefined;
  const piece = game.get(source)?.type;
  if (piece === "p") {
    const targetRank = target[1];
    const isWhitePawn = game.get(source)?.color === "w";
    if (
      (isWhitePawn && targetRank === "8") ||
      (!isWhitePawn && targetRank === "1")
    ) {
      promotion = "q";
    }
  }

  const move = game.move({
    from: source,
    to: target,
    promotion: promotion,
  });

  if (move === null) return "snapback";

  board.position(game.fen());
  scheduleStatsRefresh();
}

function onSnapEnd() {
  board.position(game.fen());
}

function resetBoard() {
  game.reset();
  board.orientation(boardOrientation);
  board.position(game.fen());
  scheduleStatsRefresh();
}

function flipBoard() {
  boardOrientation = boardOrientation === "white" ? "black" : "white";
  board.orientation(boardOrientation);
}

async function init() {
  const cfg = {
    draggable: true,
    position: "start",
    orientation: boardOrientation,
    pieceTheme: "/static/img/chesspieces/wikipedia/{piece}.png",
    onDragStart: onDragStart,
    onDrop: onDrop,
    onSnapEnd: onSnapEnd,
  };

  board = Chessboard("board", cfg);
  $(window).resize(board.resize);

  document.getElementById("reset-btn").addEventListener("click", resetBoard);
  document.getElementById("flip-btn").addEventListener("click", flipBoard);

  try {
    const health = await fetchHealth();
    const el = document.getElementById("build-status");
    if (health.ok) {
      el.textContent = `DB: ${health.build_status} — ${Number(health.games_processed || 0).toLocaleString()} games indexed`;
      el.classList.remove("warn");
    } else {
      el.textContent = "Database unavailable: " + (health.error || "unknown");
      el.classList.add("warn");
    }
  } catch (err) {
    document.getElementById("build-status").textContent =
      "Cannot reach API: " + err.message;
  }

  scheduleStatsRefresh();
}

document.addEventListener("DOMContentLoaded", init);
