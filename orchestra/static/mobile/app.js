/**
 * Orchestra Mobile Client — app.js
 *
 * Handles both join.html and presenter.html.
 * Uses Socket.IO for real-time communication.
 * All timing uses Date.now() calibrated against server activate_epoch.
 */

"use strict";

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
const State = {
  presenterList: [],          // [{id, name, color}, ...]
  myId: null,                 // selected presenter id
  myName: null,
  myColor: null,

  session: null,              // full session snapshot
  activeBlock: null,          // current block:activate payload
  activateEpoch: null,        // ms since epoch when block started
  blockDuration: null,        // seconds
  endCondition: null,         // "time"|"click"|"either"
  totalDurationSeconds: null,

  sessionState: "idle",       // warmup|running|paused|completed|aborted
  isActive: false,            // am I the current presenter?

  // Session elapsed chronometer: adjusted ms-epoch such that
  // (Date.now() - sessionStartEpoch) / 1000 == active (non-paused) elapsed.
  sessionStartEpoch: null,
  _pauseStartMs: null,

  countdownTimer: null,
  heartbeatTimer: null,
};

// ---------------------------------------------------------------------------
// DOM helpers
// ---------------------------------------------------------------------------
function $(id)  { return document.getElementById(id); }

const SCREENS = ["screenJoin", "screenWaiting", "screenActive",
                 "screenInactive", "screenComplete"];

function showScreen(id) {
  SCREENS.forEach(s => {
    const el = $(s);
    if (el) el.classList.toggle("active", s === id);
  });
}

// ---------------------------------------------------------------------------
// Page detection
// ---------------------------------------------------------------------------
const isJoinPage = !!$("screenJoin");
const isPresenterPage = !!$("screenActive");

// ---------------------------------------------------------------------------
// Socket.IO connection
// ---------------------------------------------------------------------------
const socket = io({
  reconnection: true,
  reconnectionAttempts: Infinity,
  reconnectionDelay: 1000,
  reconnectionDelayMax: 5000,
  timeout: 10000,
});

// ---------------------------------------------------------------------------
// Reconnect banner
// ---------------------------------------------------------------------------
socket.on("connect", () => {
  $("reconnectBanner").classList.remove("show");

  // Re-join if we had a session going
  const savedId = sessionStorage.getItem("orchestra_presenter_id");
  const savedState = sessionStorage.getItem("orchestra_session_state");
  if (savedId && savedState !== "idle") {
    socket.emit("presenter:join", {
      presenter_id: savedId,
      display_name: sessionStorage.getItem("orchestra_presenter_name") || "",
    });
  }
});

socket.on("disconnect", () => {
  $("reconnectBanner").classList.add("show");
});

// ---------------------------------------------------------------------------
// JOIN PAGE LOGIC
// ---------------------------------------------------------------------------
if (isJoinPage) {
  initJoinPage();
}

function initJoinPage() {
  // Load presenters
  fetch("/api/presenters")
    .then(r => r.json())
    .then(presenters => {
      State.presenterList = presenters;
      const sel = $("presenterSelect");
      sel.innerHTML = "";
      if (!presenters.length) {
        sel.innerHTML = '<option value="">No presenters available</option>';
        return;
      }
      presenters.forEach(p => {
        const opt = document.createElement("option");
        opt.value = p.id;
        opt.textContent = p.name;
        sel.appendChild(opt);
      });
      $("joinBtn").disabled = false;
    })
    .catch(() => {
      $("errorMsg").textContent = "Could not load presenter list. Is the server running?";
      $("errorMsg").classList.add("show");
    });

  $("joinBtn").addEventListener("click", () => {
    const sel = $("presenterSelect");
    const id = sel.value;
    const name = sel.options[sel.selectedIndex]?.textContent || "";
    if (!id) return;

    $("errorMsg").classList.remove("show");
    $("joinBtn").disabled = true;
    $("joinBtn").textContent = "Joining…";

    State.myId = id;
    State.myName = name;
    sessionStorage.setItem("orchestra_presenter_id", id);
    sessionStorage.setItem("orchestra_presenter_name", name);

    // Request vibration permission proactively before any session event
    requestVibrationPermission();

    socket.emit("presenter:join", { presenter_id: id, display_name: name });
  });

  // Update connected list during warmup
  socket.on("presenter:connected_list", ({ connected, total_expected }) => {
    const rows = $("connectedPresenterRows");
    if (!rows) return;
    rows.innerHTML = "";
    connected.forEach(p => {
      const row = document.createElement("div");
      row.className = "presenter-row";
      row.innerHTML = `
        <div class="presenter-dot" style="background:${p.color}"></div>
        <span class="presenter-name">${escHtml(p.name)}</span>
        <span class="presenter-status">✓ Connected</span>
      `;
      rows.appendChild(row);
    });
  });

  socket.on("presenter:join_ok", ({ presenter_id, name, color, session_snapshot }) => {
    State.myId = presenter_id;
    State.myName = name;
    State.myColor = color;
    State.session = session_snapshot;
    State.sessionState = session_snapshot?.state || "warmup";

    sessionStorage.setItem("orchestra_session_state", State.sessionState);
    sessionStorage.setItem("orchestra_presenter_id", presenter_id);

    if (State.sessionState === "running") {
      // Session already started — navigate directly to presenter page
      window.location.href = `/presenter/${presenter_id}`;
    } else {
      showScreen("screenWaiting");
    }
  });

  socket.on("presenter:join_error", ({ code, message }) => {
    $("joinBtn").disabled = false;
    $("joinBtn").textContent = "Join Session";
    $("errorMsg").textContent = message;
    $("errorMsg").classList.add("show");
  });

  socket.on("session:started", () => {
    sessionStorage.setItem("orchestra_session_state", "running");
    window.location.href = `/presenter/${State.myId}`;
  });
}

// ---------------------------------------------------------------------------
// PRESENTER PAGE LOGIC
// ---------------------------------------------------------------------------
if (isPresenterPage) {
  initPresenterPage();
}

function initPresenterPage() {
  // Restore identity from sessionStorage (after page load)
  State.myId = sessionStorage.getItem("orchestra_presenter_id");
  State.myName = sessionStorage.getItem("orchestra_presenter_name") || "";
  State.sessionState = sessionStorage.getItem("orchestra_session_state") || "running";

  if (!State.myId) {
    // No saved session — go back to join
    window.location.href = "/join";
    return;
  }

  // Request vibration permission
  requestVibrationPermission();

  // Rejoin on connect (handles initial load and reconnects)
  socket.on("connect", () => {
    socket.emit("presenter:join", {
      presenter_id: State.myId,
      display_name: State.myName,
    });
  });

  socket.on("presenter:join_ok", ({ presenter_id, name, color, session_snapshot }) => {
    State.myId = presenter_id;
    State.myName = name;
    State.myColor = color;

    if (session_snapshot) {
      applySessionSnapshot(session_snapshot);
    }

    startHeartbeat();
  });

  socket.on("presenter:join_error", ({ code }) => {
    if (code === "no_active_session") {
      window.location.href = "/join";
    }
  });

  // Block events
  socket.on("block:activate", (payload) => {
    handleBlockActivate(payload);
  });

  socket.on("block:completed", (payload) => {
    // Will be superseded by the next block:activate or session:completed
  });

  socket.on("block:overrun", (payload) => {
    if (State.isActive) {
      // Flash the countdown red briefly
      const cd = $("countdownDisplay");
      if (cd) {
        cd.style.color = "#e85454";
        setTimeout(() => { cd.style.color = ""; }, 500);
      }
    }
  });

  // Timer correction
  socket.on("timer:tick", (payload) => {
    handleTimerTick(payload);
  });

  // Vibration
  socket.on("presenter:vibrate", ({ pattern_ms }) => {
    triggerVibration(pattern_ms);
  });

  // Session lifecycle
  socket.on("session:paused", () => {
    $("pausedOverlay").classList.add("show");
    State.sessionState = "paused";
    State._pauseStartMs = Date.now();
    clearCountdown();
  });

  socket.on("session:resumed", () => {
    $("pausedOverlay").classList.remove("show");
    State.sessionState = "running";
    // Stretch the anchor by the pause duration so elapsed stays accurate.
    if (State._pauseStartMs !== null) {
      State.sessionStartEpoch += (Date.now() - State._pauseStartMs);
      State._pauseStartMs = null;
    }
    // Restart countdown from server state
    if (State.activeBlock && State.activateEpoch) {
      startCountdown();
    }
  });

  socket.on("session:completed", ({ total_actual_duration_seconds }) => {
    sessionStorage.setItem("orchestra_session_state", "idle");
    clearCountdown();
    showScreen("screenComplete");
    const dur = formatSeconds(total_actual_duration_seconds);
    const el = $("completeDuration");
    if (el) el.textContent = `Total duration: ${dur}`;
  });

  socket.on("session:aborted", () => {
    sessionStorage.setItem("orchestra_session_state", "idle");
    clearCountdown();
    showScreen("screenComplete");
    const el = $("completeDuration");
    if (el) el.textContent = "Session was ended by the operator.";
  });

  // Advance button
  const advBtn = $("advanceBtn");
  if (advBtn) {
    advBtn.addEventListener("click", () => {
      if (!State.activeBlock || !State.isActive) return;
      advBtn.disabled = true;
      advBtn.textContent = "Advancing…";
      socket.emit("presenter:request_advance", {
        presenter_id: State.myId,
        block_id: State.activeBlock.block_id,
        request_epoch: Date.now() / 1000,
      });
    });
  }

  socket.on("presenter:advance_rejected", () => {
    const advBtn = $("advanceBtn");
    if (advBtn) {
      advBtn.disabled = false;
      advBtn.textContent = "Done — Next Section";
    }
  });
}

// ---------------------------------------------------------------------------
// Session snapshot (mid-session join)
// ---------------------------------------------------------------------------
function applySessionSnapshot(snapshot) {
  State.sessionState = snapshot.state;
  State.session = snapshot;

  // Anchor the session elapsed chronometer.
  // Use completed block durations + current block elapsed for accuracy.
  const completedDuration = (snapshot.blocks_summary || [])
    .slice(0, snapshot.current_block_index || 0)
    .reduce((sum, b) => sum + b.duration, 0);
  const snapshotElapsed = completedDuration + (snapshot.block_elapsed_seconds || 0);
  State.sessionStartEpoch = Date.now() - snapshotElapsed * 1000;

  if (snapshot.state === "completed" || snapshot.state === "aborted") {
    showScreen("screenComplete");
    return;
  }

  if (snapshot.current_block) {
    const b = snapshot.current_block;
    const isMyBlock = b.presenter_id === State.myId;
    State.isActive = isMyBlock;

    if (isMyBlock) {
      // Reconstruct active block payload from snapshot
      const payload = {
        block_id: b.id,
        presenter_id: b.presenter_id,
        presenter_name: snapshot.presenters?.find(p => p.id === b.presenter_id)?.name || "?",
        presenter_color: snapshot.presenters?.find(p => p.id === b.presenter_id)?.color || "#888",
        block_index: snapshot.current_block_index,
        total_blocks: snapshot.blocks_summary?.length || 0,
        slide_start: b.slide_start,
        slide_end: b.slide_end,
        duration_seconds: b.duration,
        end_condition: b.end_condition,
        overrun_behavior: b.overrun_behavior,
        activate_epoch: snapshot.activate_epoch,
        notes: b.notes,
      };
      handleBlockActivate(payload);
    } else {
      showInactiveScreen(snapshot);
    }
  } else if (snapshot.state === "warmup") {
    showScreen("screenWaiting");
  } else {
    showInactiveScreen(snapshot);
  }
}

// ---------------------------------------------------------------------------
// Block activation
// ---------------------------------------------------------------------------
function handleBlockActivate(payload) {
  State.activeBlock = payload;
  State.activateEpoch = payload.activate_epoch * 1000;  // convert to ms
  State.blockDuration = payload.duration_seconds;
  State.endCondition = payload.end_condition;
  State.isActive = payload.presenter_id === State.myId;

  clearCountdown();

  if (State.isActive) {
    showActiveScreen(payload);
  } else {
    showInactiveScreen(null, payload);
  }
}

function showActiveScreen(payload) {
  showScreen("screenActive");

  const screen = $("screenActive");
  if (screen) {
    screen.classList.remove("warn", "danger");
  }

  // Block badge
  const badge = $("blockBadge");
  if (badge) badge.textContent = `Block ${payload.block_index + 1} of ${payload.total_blocks}`;

  // Slide info
  const slideInfo = $("slideInfo");
  if (slideInfo) slideInfo.textContent = `Slides ${payload.slide_start}–${payload.slide_end}`;

  // Notes
  const notesBox = $("notesBox");
  if (notesBox) {
    if (payload.notes && payload.notes.trim()) {
      notesBox.textContent = payload.notes;
      notesBox.classList.add("has-content");
    } else {
      notesBox.textContent = "";
      notesBox.classList.remove("has-content");
    }
  }

  // Advance button
  const advBtn = $("advanceBtn");
  if (advBtn) {
    const canClick = ["click", "either"].includes(payload.end_condition);
    advBtn.classList.toggle("visible", canClick);
    advBtn.disabled = false;
    advBtn.textContent = "Done — Next Section";
  }

  startCountdown();
}

function showInactiveScreen(snapshot, currentBlockPayload) {

  showScreen("screenInactive");

  const block = currentBlockPayload || (snapshot?.current_block ? {
    presenter_id: snapshot.current_block.presenter_id,
    presenter_name: snapshot.presenters?.find(p => p.id === snapshot.current_block.presenter_id)?.name || "?",
    presenter_color: snapshot.presenters?.find(p => p.id === snapshot.current_block.presenter_id)?.color || "#888",
  } : null);

  // Now presenting badge
  const badge = $("nowPresenterBadge");
  if (badge && block) {
    badge.textContent = block.presenter_name || "?";
    badge.style.background = block.presenter_color || "#444";
    badge.style.color = isColorDark(block.presenter_color) ? "#fff" : "#000";
  }

  // Up-next label
  const upNext = $("upNextLabel");
  if (upNext && State.session) {
    const summary = State.session.blocks_summary || [];
    const myBlocks = summary.filter(b => b.presenter_id === State.myId);
    const currentIdx = State.session.current_block_index || 0;
    const nextMyBlock = myBlocks.find((b, _, arr) => {
      const blockIdx = summary.findIndex(s => s.block_id === b.block_id);
      return blockIdx > currentIdx;
    });
    if (nextMyBlock) {
      const nextIdx = summary.findIndex(s => s.block_id === nextMyBlock.block_id);
      const diff = nextIdx - currentIdx;
      upNext.textContent = diff === 1 ? "You're up next!" : `You're up in ${diff} blocks`;
    } else {
      upNext.textContent = "You have no more blocks — sit back and enjoy.";
    }
  }
}

// ---------------------------------------------------------------------------
// Countdown
// ---------------------------------------------------------------------------
function startCountdown() {
  clearCountdown();
  updateCountdownDisplay();
  State.countdownTimer = setInterval(updateCountdownDisplay, 100);
}

function clearCountdown() {
  if (State.countdownTimer) {
    clearInterval(State.countdownTimer);
    State.countdownTimer = null;
  }
}

function updateCountdownDisplay() {
  if (!State.activateEpoch || !State.blockDuration) return;
  const elapsed = (Date.now() - State.activateEpoch) / 1000;
  const remaining = Math.max(0, State.blockDuration - elapsed);

  const cd = $("countdownDisplay");
  if (cd) cd.textContent = formatSeconds(remaining);

  // Session elapsed chronometer
  const sesEl = $("sessionElapsed");
  if (sesEl && State.sessionStartEpoch) {
    const sesElapsed = Math.max(0, (Date.now() - State.sessionStartEpoch) / 1000);
    sesEl.textContent = `${formatSeconds(sesElapsed)} total elapsed`;
  }

  // Color transitions
  const pct = remaining / State.blockDuration;
  const screen = $("screenActive");
  if (screen) {
    screen.classList.toggle("warn",   pct <= 0.20 && pct > 0.10);
    screen.classList.toggle("danger", pct <= 0.10);
  }

  // Update session progress
  if (State.session) {
    const sesElapsed = (Date.now() / 1000) - (State.session.activate_epoch || 0) +
                       (State.session.session_elapsed_seconds || 0);
    const total = State.session.total_duration_seconds || 1;
    const pctSes = Math.min(1, sesElapsed / total);
    const fill = $("sessionProgressFill");
    if (fill) fill.style.width = `${(pctSes * 100).toFixed(1)}%`;
  }
}

function handleTimerTick(payload) {
  // Correct local drift using authoritative server value
  if (State.activateEpoch && payload.block_remaining_seconds !== undefined) {
    const serverRemaining = payload.block_remaining_seconds;
    const localRemaining = Math.max(0,
      State.blockDuration - (Date.now() - State.activateEpoch) / 1000
    );
    const drift = Math.abs(serverRemaining - localRemaining);
    // Only re-sync if drift > 2 seconds (avoid jitter)
    if (drift > 2) {
      State.activateEpoch = Date.now() - (State.blockDuration - serverRemaining) * 1000;
    }
  }
  // Update session progress for inactive screen
  if (!State.isActive) {
    const total = State.totalDurationSeconds || State.session?.total_duration_seconds || 1;
    const elapsed = payload.session_elapsed_seconds || 0;
    const pct = Math.min(1, elapsed / total);
    const fill = $("sessionProgressFill");
    if (fill) fill.style.width = `${(pct * 100).toFixed(1)}%`;
    const lbl = $("sessionProgressLabel");
    if (lbl) lbl.textContent = `${formatSeconds(elapsed)} elapsed`;
  }
}

// ---------------------------------------------------------------------------
// Vibration
// ---------------------------------------------------------------------------
function requestVibrationPermission() {
  // On iOS, vibration requires a user gesture — we trigger a 0ms vibration to prime it
  if ("vibrate" in navigator) {
    navigator.vibrate(0);
  }
}

function triggerVibration(patternMs) {
  if ("vibrate" in navigator) {
    navigator.vibrate(patternMs);
  }
}

// ---------------------------------------------------------------------------
// Heartbeat
// ---------------------------------------------------------------------------
function startHeartbeat() {
  if (State.heartbeatTimer) clearInterval(State.heartbeatTimer);
  State.heartbeatTimer = setInterval(() => {
    socket.emit("presenter:heartbeat", { presenter_id: State.myId });
  }, 15000);
}

// ---------------------------------------------------------------------------
// Utility
// ---------------------------------------------------------------------------
function formatSeconds(totalSeconds) {
  const t = Math.max(0, Math.round(totalSeconds));
  const m = Math.floor(t / 60);
  const s = t % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function isColorDark(hex) {
  // Returns true if the color is dark (should use white text)
  if (!hex) return true;
  const c = hex.replace("#", "");
  const r = parseInt(c.substr(0,2), 16);
  const g = parseInt(c.substr(2,2), 16);
  const b = parseInt(c.substr(4,2), 16);
  const luminance = (0.299*r + 0.587*g + 0.114*b) / 255;
  return luminance < 0.5;
}
