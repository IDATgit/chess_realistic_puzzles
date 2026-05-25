/* global Chess, Chessboard */

const game = new Chess();
let board = null;
let boardOrientation = "white";
let playerElo = 1500;
let currentPuzzle = null;
let puzzleSolved = false;

function pct(n) {
  return (n * 100).toFixed(1) + "%";
}

function uciFromMove(move) {
  return move.from + move.to + (move.promotion || "");
}

function sanFromUci(fen, uci) {
  if (!uci) return "";
  const temp = new Chess(fen);
  const from = uci.slice(0, 2);
  const to = uci.slice(2, 4);
  const promotion = uci.length > 4 ? uci[4] : undefined;
  const m = temp.move({ from, to, promotion });
  return m ? m.san : uci;
}

function applyUciMove(uci) {
  const from = uci.slice(0, 2);
  const to = uci.slice(2, 4);
  const promotion = uci.length > 4 ? uci[4] : undefined;
  return game.move({ from, to, promotion });
}

function hideMoveStats() {
  document.getElementById("move-stats-section").classList.add("hidden");
  document.querySelector("#low-moves-body").innerHTML = "";
  document.querySelector("#high-moves-body").innerHTML = "";
}

function renderMoveStatsTable(tbodyId, moves, fen, highlightUci) {
  const tbody = document.getElementById(tbodyId);
  tbody.innerHTML = "";
  if (!moves || moves.length === 0) {
    const tr = document.createElement("tr");
    tr.innerHTML = '<td colspan="3">No move data</td>';
    tbody.appendChild(tr);
    return;
  }

  const total = moves.reduce((sum, m) => sum + m.games, 0);
  for (const m of moves) {
    const san = sanFromUci(fen, m.uci);
    const share = total > 0 ? m.games / total : 0;
    const tr = document.createElement("tr");
    if (highlightUci && m.uci === highlightUci) {
      tr.className = "move-highlight";
    }
    tr.innerHTML = `
      <td><code>${san}</code></td>
      <td>${m.games.toLocaleString()}</td>
      <td>${pct(share)}</td>
    `;
    tbody.appendChild(tr);
  }
}

function showMoveStats() {
  if (!currentPuzzle) return;

  document.getElementById("low-moves-title").textContent =
    currentPuzzle.bin_low_label;
  document.getElementById("high-moves-title").textContent =
    currentPuzzle.bin_high_label;

  renderMoveStatsTable(
    "low-moves-body",
    currentPuzzle.low_moves,
    currentPuzzle.fen,
    currentPuzzle.player_move_uci
  );
  renderMoveStatsTable(
    "high-moves-body",
    currentPuzzle.high_moves,
    currentPuzzle.fen,
    currentPuzzle.solution_uci
  );

  document.getElementById("move-stats-section").classList.remove("hidden");
}

function finishAttempt() {
  showMoveStats();
  document.querySelector(".puzzle-hint").classList.add("hidden");
}

function showScreen(name) {
  document.getElementById("start-screen").classList.toggle("hidden", name !== "start");
  document.getElementById("puzzle-screen").classList.toggle("hidden", name !== "puzzle");
  document.getElementById("loading-screen").classList.toggle("hidden", name !== "loading");
}

function ensureBoard() {
  if (board) return;

  board = Chessboard("board", {
    draggable: true,
    position: "start",
    orientation: boardOrientation,
    pieceTheme: "/static/img/chesspieces/wikipedia/{piece}.png",
    onDragStart,
    onDrop,
    onSnapEnd,
  });
  $(window).resize(board.resize);
}

function resizeBoard() {
  if (!board) return;
  requestAnimationFrame(() => {
    board.resize();
    board.position(game.fen());
  });
}

function orientationForTurn(fen) {
  const turn = fen.split(" ")[1];
  return turn === "w" ? "white" : "black";
}

async function fetchHealth() {
  const res = await fetch("/api/health");
  return res.json();
}

const PHASE_LABELS = {
  idle: "",
  scanning_pgn: "Scanning games and checking positions…",
  found: "Puzzle found!",
  failed: "Search failed",
};

const SETTINGS_KEY = "puzzleSettings";

const DEFAULT_SETTINGS = {
  eloDiff: 300,
  improvementPct: 10,
  minGames: 25,
  maxAttempts: 5000,
};

function loadSettings() {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (raw) {
      return { ...DEFAULT_SETTINGS, ...JSON.parse(raw) };
    }
  } catch {
    /* ignore */
  }
  return { ...DEFAULT_SETTINGS };
}

function saveSettings(settings) {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
}

function applySettingsToForm(settings) {
  document.getElementById("elo-diff-input").value = settings.eloDiff;
  document.getElementById("improvement-input").value = settings.improvementPct;
  document.getElementById("min-games-input").value = settings.minGames;
  document.getElementById("max-attempts-input").value = settings.maxAttempts;
}

function readSettingsFromForm() {
  return {
    eloDiff: Number(document.getElementById("elo-diff-input").value),
    improvementPct: Number(document.getElementById("improvement-input").value),
    minGames: Number(document.getElementById("min-games-input").value),
    maxAttempts: Number(document.getElementById("max-attempts-input").value),
  };
}

function getSearchSettings() {
  const fromForm = readSettingsFromForm();
  if (!document.getElementById("start-screen").classList.contains("hidden")) {
    return fromForm;
  }
  return { ...loadSettings(), ...fromForm };
}

function bindSettingsPersistence() {
  for (const id of [
    "elo-diff-input",
    "improvement-input",
    "min-games-input",
    "max-attempts-input",
  ]) {
    document.getElementById(id).addEventListener("change", () => {
      saveSettings(readSettingsFromForm());
    });
  }
}

let activePuzzleStream = null;
let searchGeneration = 0;

function validateSettings(settings) {
  if (!Number.isFinite(settings.eloDiff) || settings.eloDiff < 50 || settings.eloDiff > 800) {
    return "Elo difference must be between 50 and 800.";
  }
  if (
    !Number.isFinite(settings.improvementPct) ||
    settings.improvementPct < 1 ||
    settings.improvementPct > 50
  ) {
    return "Min improvement must be between 1% and 50%.";
  }
  if (!Number.isFinite(settings.minGames) || settings.minGames < 5 || settings.minGames > 1000) {
    return "Min games must be between 5 and 1000.";
  }
  if (
    !Number.isFinite(settings.maxAttempts) ||
    settings.maxAttempts < 100 ||
    settings.maxAttempts > 50000
  ) {
    return "Max positions to check must be between 100 and 50,000.";
  }
  return null;
}

const REJECTION_LABELS_FALLBACK = {
  insufficient_low_games: "Your Elo band has too few games",
  missing_high_bin: "No stats in higher Elo band",
  insufficient_high_games: "Higher band has too few games",
  insufficient_improvement: "Win+draw improvement below threshold",
  same_top_move: "Same most popular move at both Elo bands",
};

function renderSearchProgress(search) {
  if (!search) return;

  document.getElementById("search-evaluated").textContent =
    `Positions evaluated: ${search.evaluated.toLocaleString()}`;

  const phaseLabel = PHASE_LABELS[search.phase] || search.phase;
  let phaseText = phaseLabel;
  if (search.settings) {
    const s = search.settings;
    const minPct = (s.improvement_threshold * 100).toFixed(0);
    phaseText += ` — min ${minPct}% @ +${s.elo_diff}, ≥${s.min_games} games`;
  }
  document.getElementById("search-phase").textContent = phaseText;

  document.getElementById("search-pgn").textContent =
    `PGN games scanned: ${(search.pgn_games_scanned || 0).toLocaleString()}`;

  const tbody = document.querySelector("#rejection-table tbody");
  tbody.innerHTML = "";
  const labels = search.rejection_labels || REJECTION_LABELS_FALLBACK;
  const rejections = search.rejections || {};
  const keys = Object.keys(labels);

  for (const key of keys) {
    const count = rejections[key] || 0;
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${labels[key] || key}</td><td>${count.toLocaleString()}</td>`;
    tbody.appendChild(tr);
  }
}

function resetSearchLog() {
  renderSearchProgress({
    evaluated: 0,
    rejections: {},
    pgn_games_scanned: 0,
    phase: "idle",
  });
}

function fetchPuzzleStream(elo, settings, onProgress) {
  return new Promise((resolve, reject) => {
    if (activePuzzleStream) {
      activePuzzleStream.close();
      activePuzzleStream = null;
    }

    const generation = ++searchGeneration;
    const params = new URLSearchParams({
      elo: String(elo),
      min_games: String(settings.minGames),
      improvement: String(settings.improvementPct / 100),
      max_attempts: String(settings.maxAttempts),
      elo_diff: String(settings.eloDiff),
    });
    const es = new EventSource(`/api/puzzle/next/stream?${params}`);
    activePuzzleStream = es;

    function finish() {
      if (activePuzzleStream === es) {
        es.close();
        activePuzzleStream = null;
      }
    }

    es.onmessage = (event) => {
      if (generation !== searchGeneration) {
        return;
      }

      let data;
      try {
        data = JSON.parse(event.data);
      } catch {
        return;
      }

      if (data.event === "progress") {
        onProgress(data.search);
        return;
      }

      finish();

      if (data.event === "puzzle") {
        const threshold = data.improvement_threshold ?? settings.improvementPct / 100;
        if (data.improvement < threshold - 1e-9) {
          reject(
            new Error(
              `Puzzle did not meet the ${settings.improvementPct}% improvement threshold (got ${(data.improvement * 100).toFixed(1)}%). Try again.`
            )
          );
          return;
        }
        resolve(data);
        return;
      }

      const message = data.message || data.reason || "Puzzle search failed";
      const err = new Error(message);
      err.search = data.search;
      reject(err);
    };

    es.onerror = () => {
      if (generation !== searchGeneration) {
        return;
      }
      finish();
      reject(new Error("Connection lost while searching for a puzzle."));
    };
  });
}

function renderPuzzle(data) {
  currentPuzzle = data;
  puzzleSolved = false;

  game.load(data.fen);
  boardOrientation = orientationForTurn(data.fen);
  board.orientation(boardOrientation);
  board.position(game.fen());

  const turn = game.turn() === "w" ? "White" : "Black";
  document.getElementById("turn-label").textContent = `${turn} to move`;
  document.getElementById("feedback").textContent = "";
  document.getElementById("feedback").className = "feedback";
  hideMoveStats();
  document.querySelector(".puzzle-hint").classList.remove("hidden");

  document.getElementById("search-summary").textContent =
    `Found after ${data.attempts} sample(s) at Elo ${data.player_elo}` +
    (data.search ? ` — ${data.search.evaluated} evaluated` : "");

  document.getElementById("low-bin-title").textContent = data.bin_low_label;
  document.getElementById("high-bin-title").textContent = data.bin_high_label;

  document.getElementById("low-bin-stats").textContent =
    `${data.low.games.toLocaleString()} games — ${data.low.wins}W ${data.low.draws}D ${data.low.losses}L`;
  document.getElementById("high-bin-stats").textContent =
    `${data.high.games.toLocaleString()} games — ${data.high.wins}W ${data.high.draws}D ${data.high.losses}L`;

  document.getElementById("low-bin-rate").textContent =
    `Win+draw: ${pct(data.low.not_loss_rate)}`;
  document.getElementById("high-bin-rate").textContent =
    `Win+draw: ${pct(data.high.not_loss_rate)}`;

  document.getElementById("improvement-line").textContent =
    `Improvement (+${data.elo_diff}): +${pct(data.improvement)} win+draw (required ≥ ${pct(data.improvement_threshold)})`;

  resizeBoard();
}

function onDragStart(source, piece) {
  if (puzzleSolved || game.game_over()) return false;
  if (
    (game.turn() === "w" && piece.search(/^b/) !== -1) ||
    (game.turn() === "b" && piece.search(/^w/) !== -1)
  ) {
    return false;
  }
}

function onDrop(source, target) {
  if (puzzleSolved) return "snapback";

  let promotion;
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

  const move = game.move({ from: source, to: target, promotion });
  if (move === null) return "snapback";

  const playedSan = move.san;
  const solution = currentPuzzle?.solution_uci;
  const feedback = document.getElementById("feedback");

  if (!solution) {
    puzzleSolved = true;
    feedback.textContent = `You played ${playedSan}. (No move data in +300 band.)`;
    feedback.className = "feedback";
    board.position(game.fen());
    finishAttempt();
    return;
  }

  if (uciFromMove(move) === solution) {
    puzzleSolved = true;
    let message =
      `Correct! ${playedSan} is the most popular move in the ${currentPuzzle.bin_high_label} band.`;
    const playerMove = currentPuzzle.player_move_uci;
    if (playerMove) {
      const playerSan = sanFromUci(currentPuzzle.fen, playerMove);
      message += ` At your level (${currentPuzzle.bin_low_label}), players most often play ${playerSan}.`;
    }
    feedback.textContent = message;
    feedback.className = "feedback success";
    board.position(game.fen());
    finishAttempt();
    return;
  }

  game.undo();
  const correctSan = sanFromUci(game.fen(), solution);
  const correctMove = applyUciMove(solution);
  puzzleSolved = true;
  feedback.textContent = correctMove
    ? `Wrong. The best move is ${correctSan} (you played ${playedSan}).`
    : `Wrong. The best move is ${solution} (you played ${playedSan}).`;
  feedback.className = "feedback miss";
  board.position(game.fen());
  finishAttempt();
}

function onSnapEnd() {
  board.position(game.fen());
}

async function loadPuzzle() {
  const eloInput = document.getElementById("elo-input");
  const errorEl = document.getElementById("start-error");
  errorEl.classList.add("hidden");

  const elo = Number(eloInput.value);
  if (!Number.isFinite(elo) || elo < 400 || elo > 3500) {
    errorEl.textContent = "Enter an Elo between 400 and 3500.";
    errorEl.classList.remove("hidden");
    return;
  }

  const settings = getSearchSettings();
  const settingsError = validateSettings(settings);
  if (settingsError) {
    errorEl.textContent = settingsError;
    errorEl.classList.remove("hidden");
    return;
  }
  saveSettings(settings);

  playerElo = elo;
  showScreen("loading");
  document.getElementById("loading-text").textContent = "Searching for a puzzle…";
  resetSearchLog();

  try {
    const data = await fetchPuzzleStream(elo, settings, renderSearchProgress);
    showScreen("puzzle");
    ensureBoard();
    renderPuzzle(data);
  } catch (err) {
    showScreen("start");
    let message = err.message;
    if (err.search) {
      const parts = Object.entries(err.search.rejections || {})
        .filter(([, count]) => count > 0)
        .map(([key, count]) => {
          const labels = err.search.rejection_labels || REJECTION_LABELS_FALLBACK;
          return `${labels[key] || key}: ${count}`;
        });
      if (parts.length > 0) {
        message += `\n\nEvaluated ${err.search.evaluated} positions. Rejected: ${parts.join("; ")}.`;
      }
    }
    errorEl.textContent = message;
    errorEl.classList.remove("hidden");
    errorEl.style.whiteSpace = "pre-wrap";
  }
}

function flipBoard() {
  ensureBoard();
  boardOrientation = boardOrientation === "white" ? "black" : "white";
  board.orientation(boardOrientation);
}

async function init() {
  applySettingsToForm(loadSettings());
  bindSettingsPersistence();

  document.getElementById("start-btn").addEventListener("click", loadPuzzle);
  document.getElementById("next-btn").addEventListener("click", loadPuzzle);
  document.getElementById("flip-btn").addEventListener("click", flipBoard);
  document.getElementById("elo-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") loadPuzzle();
  });

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

  showScreen("start");
}

document.addEventListener("DOMContentLoaded", init);
