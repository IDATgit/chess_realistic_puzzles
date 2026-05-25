/**
 * Stockfish eval bar (chess.com-style) beside the board.
 * Score is always from White's perspective.
 */
class EvalBar {
  constructor(options) {
    this.wrapEl = options.wrapEl;
    this.trackEl = options.trackEl;
    this.fillEl = options.fillEl;
    this.scoreEl = options.scoreEl;
    this.orientation = options.orientation || "white";
    this.depth = options.depth || 16;
    this.movetimeMs = options.movetimeMs || 800;

    this.worker = null;
    this.ready = false;
    this.busy = false;
    this.currentFen = null;
    this.queuedFen = null;
    this.lastScore = null;
    this.debounceTimer = null;
    this.resizeObserver = null;

    this.initWorker();
    this.bindResize(options.boardEl);
  }

  initWorker() {
    try {
      this.worker = new Worker("/static/stockfish/stockfish.js");
      this.worker.onmessage = (event) => this.onEngineLine(event.data);
      this.worker.onerror = () => this.showUnavailable();
      this.worker.postMessage("uci");
      this.setStatus("…");
    } catch (err) {
      console.error(err);
      this.showUnavailable();
    }
  }

  onEngineLine(line) {
    if (typeof line !== "string") {
      return;
    }

    if (line === "uciok") {
      this.worker.postMessage("isready");
      return;
    }

    if (line === "readyok") {
      this.ready = true;
      if (this.queuedFen) {
        this.runAnalysis(this.queuedFen);
      }
      return;
    }

    if (line.startsWith("info ")) {
      const mateMatch = line.match(/\bscore mate (-?\d+)\b/);
      const cpMatch = line.match(/\bscore cp (-?\d+)\b/);
      if ((mateMatch || cpMatch) && this.currentFen) {
        this.lastScore = {
          mate: mateMatch ? Number(mateMatch[1]) : null,
          cp: cpMatch ? Number(cpMatch[1]) : null,
          fen: this.currentFen,
        };
        this.renderScore(this.lastScore);
      }
      return;
    }

    if (line.startsWith("bestmove")) {
      this.busy = false;
      if (this.queuedFen && this.queuedFen !== this.currentFen) {
        this.runAnalysis(this.queuedFen);
      }
    }
  }

  bindResize(boardEl) {
    if (!boardEl || typeof ResizeObserver === "undefined") {
      return;
    }
    this.resizeObserver = new ResizeObserver(() => this.syncHeight(boardEl));
    this.resizeObserver.observe(boardEl);
    this.syncHeight(boardEl);
  }

  syncHeight(boardEl) {
    if (!boardEl || !this.trackEl) {
      return;
    }
    const height = boardEl.offsetHeight;
    if (height > 0) {
      this.trackEl.style.height = `${height}px`;
    }
  }

  setOrientation(orientation) {
    this.orientation = orientation;
    this.wrapEl.classList.toggle("eval-flipped", orientation === "black");
  }

  scheduleEval(fen) {
    clearTimeout(this.debounceTimer);
    this.debounceTimer = setTimeout(() => this.requestEval(fen), 200);
  }

  requestEval(fen) {
    this.queuedFen = fen;
    if (!this.worker) {
      return;
    }
    if (!this.ready) {
      this.setStatus("…");
      return;
    }
    if (this.busy) {
      this.worker.postMessage("stop");
      return;
    }
    this.runAnalysis(fen);
  }

  runAnalysis(fen) {
    this.currentFen = fen;
    this.queuedFen = fen;
    this.lastScore = null;
    this.busy = true;
    this.setStatus("…");
    this.worker.postMessage("stop");
    this.worker.postMessage(`position fen ${fen}`);
    this.worker.postMessage(`go depth ${this.depth} movetime ${this.movetimeMs}`);
  }

  toWhitePerspective(score, fen) {
    if (!score || !fen) {
      return { cp: 0, mate: null };
    }
    const turn = fen.split(" ")[1];
    if (score.mate !== null) {
      return { cp: 0, mate: turn === "w" ? score.mate : -score.mate };
    }
    const cp = turn === "w" ? score.cp : -score.cp;
    return { cp, mate: null };
  }

  cpToWinPercent(cp) {
    const win = 1 / (1 + Math.exp(-0.0035 * cp));
    return Math.min(98, Math.max(2, win * 100));
  }

  formatLabel(white) {
    if (white.mate !== null) {
      if (white.mate > 0) {
        return `M${white.mate}`;
      }
      return `-M${Math.abs(white.mate)}`;
    }
    const pawns = white.cp / 100;
    if (pawns > 0) {
      return `+${pawns.toFixed(1)}`;
    }
    return pawns.toFixed(1);
  }

  renderScore(score) {
    if (!score || score.fen !== this.currentFen) {
      return;
    }
    const white = this.toWhitePerspective(score, score.fen);
    const height =
      white.mate !== null
        ? white.mate > 0
          ? 98
          : 2
        : this.cpToWinPercent(white.cp);

    this.fillEl.style.height = `${height}%`;
    this.scoreEl.textContent = this.formatLabel(white);
    this.wrapEl.classList.remove("eval-unavailable");
  }

  setStatus(text) {
    this.scoreEl.textContent = text;
    this.fillEl.style.height = "50%";
  }

  showUnavailable() {
    this.wrapEl.classList.add("eval-unavailable");
    this.scoreEl.textContent = "N/A";
    this.fillEl.style.height = "50%";
  }
}

function mountEvalBar(boardEl) {
  const wrap = document.getElementById("eval-wrap");
  const track = document.getElementById("eval-track");
  const fill = document.getElementById("eval-fill");
  const score = document.getElementById("eval-score");
  if (!wrap || !track || !fill || !score) {
    return null;
  }
  return new EvalBar({
    wrapEl: wrap,
    trackEl: track,
    fillEl: fill,
    scoreEl: score,
    boardEl,
    orientation: "white",
  });
}
