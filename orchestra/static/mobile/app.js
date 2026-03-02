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
  blockDuration: null,        // effective duration seconds (incl. budget surplus)
  endCondition: null,         // "time"|"click"|"either"
  totalDurationSeconds: null,

  // Slide navigation within the active block
  slideStart: null,           // first slide of current block
  slideEnd: null,             // last slide of current block
  currentSlide: null,         // slide we are currently on

  // Budget tracking
  sessionBudgetSeconds: 0,    // accumulated surplus(+) / deficit(-) in seconds

  sessionState: "idle",       // warmup|running|paused|completed|aborted
  isActive: false,            // am I the current presenter?

  // Session elapsed chronometer: adjusted ms-epoch such that
  // (Date.now() - sessionStartEpoch) / 1000 == active (non-paused) elapsed.
  sessionStartEpoch: null,
  _pauseStartMs: null,

  countdownTimer: null,
  heartbeatTimer: null,
  awaitingPresenterStart: false,  // true for block 0 until presenter taps Start Timer
};

// AudioContext singleton for notification sounds (must be declared before any
// function calls since `let` is not hoisted like `var`).
let _audioCtx = null;
// Keep-alive source node: a near-silent looping buffer that prevents mobile
// browsers (iOS Safari, Chrome Android) from auto-suspending the AudioContext
// between vibration events.
let _keepAliveSource = null;

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
// Exclude join.html (which now also contains screenActive as a SPA).
// isPresenterPage is only true on the standalone presenter.html fallback.
const isPresenterPage = !!$("screenActive") && !$("screenJoin");

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
// Reconnect banner + global connect/disconnect
// ---------------------------------------------------------------------------
socket.on("disconnect", () => {
  const b = $("reconnectBanner");
  if (b) b.classList.add("show");
});

socket.on("connect", () => {
  const b = $("reconnectBanner");
  if (b) b.classList.remove("show");

  // Re-join if we already had a session identity stored
  const savedId = sessionStorage.getItem("orchestra_presenter_id");
  const savedState = sessionStorage.getItem("orchestra_session_state");
  // On the presenter page we always rejoin (page was loaded because we got
  // session:started).  On the join page only rejoin if session was active.
  const shouldRejoin = savedId && (isPresenterPage || savedState !== "idle");
  if (shouldRejoin) {
    socket.emit("presenter:join", {
      presenter_id: savedId,
      display_name: sessionStorage.getItem("orchestra_presenter_name") || "",
    });
  }
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

    // Stay on the same page (SPA) — AudioContext survives, no page reload.
    applySessionSnapshot(session_snapshot);
    startHeartbeat();
  });

  socket.on("presenter:join_error", ({ code, message }) => {
    $("joinBtn").disabled = false;
    $("joinBtn").textContent = "Join Session";
    $("errorMsg").textContent = message;
    $("errorMsg").classList.add("show");
  });

  socket.on("session:started", () => {
    sessionStorage.setItem("orchestra_session_state", "running");
    // Update URL without reloading — AudioContext is preserved.
    if (State.myId) history.pushState({}, "", `/presenter/${State.myId}`);
    // screenWaiting is already visible; block:activate will switch screens.
  });

  // ---------------------------------------------------------------------------
  // Presenter socket handlers (join.html is a SPA — all screens live here)
  // ---------------------------------------------------------------------------

  socket.on("block:activate", (payload) => {
    handleBlockActivate(payload);
  });

  socket.on("block:completed", () => {
    // Superseded by the next block:activate or session:completed
  });

  socket.on("block:overrun", () => {
    if (State.isActive) {
      const cd = $("countdownDisplay");
      if (cd) {
        cd.style.color = "#e85454";
        setTimeout(() => { cd.style.color = ""; }, 500);
      }
    }
  });

  socket.on("slide:goto", ({ slide_number }) => {
    State.currentSlide = slide_number;
    updateSlideButtonLabels();
  });

  socket.on("timer:tick", (payload) => {
    handleTimerTick(payload);
  });

  socket.on("presenter:vibrate", ({ pattern_ms }) => {
    triggerVibration(pattern_ms);
  });

  socket.on("session:paused", () => {
    $("pausedOverlay").classList.add("show");
    State.sessionState = "paused";
    State._pauseStartMs = Date.now();
    clearCountdown();
  });

  socket.on("session:resumed", () => {
    $("pausedOverlay").classList.remove("show");
    State.sessionState = "running";
    if (State._pauseStartMs !== null) {
      State.sessionStartEpoch += (Date.now() - State._pauseStartMs);
      State._pauseStartMs = null;
    }
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

  socket.on("presenter:advance_rejected", () => {
    const nb = $("nextSlideBtn");
    if (nb && State.isActive) {
      nb.disabled = false;
      updateSlideButtonLabels();
    }
  });

  socket.on("presenter:prev_block_rejected", () => {
    const pb = $("prevSlideBtn");
    if (pb) pb.disabled = false;
  });

  // Start Timer button (shown on the first block before timer begins)
  const startTimerBtn = $("startTimerBtn");
  if (startTimerBtn) {
    startTimerBtn.addEventListener("click", () => {
      if (!State.awaitingPresenterStart) return;
      State.awaitingPresenterStart = false;
      startTimerBtn.style.display = "none";

      const slideNavRow = $("slideNavRow");
      if (slideNavRow) slideNavRow.style.display = "";

      const prevBtn = $("prevSlideBtn");
      const nextBtn = $("nextSlideBtn");
      if (prevBtn) prevBtn.disabled = false;
      if (nextBtn) nextBtn.disabled = false;

      // Shift session elapsed anchor forward by the pre-start wait so the
      // displayed elapsed time doesn't include the period before Start Timer.
      const waitMs = Date.now() - State.activateEpoch;
      if (State.sessionStartEpoch !== null && waitMs > 0) {
        State.sessionStartEpoch += waitMs;
      }
      // Use current time as the start epoch; first timer:tick will correct drift
      State.activateEpoch = Date.now();

      socket.emit("presenter:start_timer", {
        presenter_id: State.myId,
        block_id: State.activeBlock?.block_id,
      });

      updateSlideButtonLabels();
      startCountdown();
    });
  }

  // Slide navigation buttons
  const prevBtn = $("prevSlideBtn");
  if (prevBtn) {
    prevBtn.addEventListener("click", () => {
      if (!State.isActive || !State.activeBlock) return;
      if (State.currentSlide > 1) {
        State.currentSlide--;
        socket.emit("presenter:goto_slide", {
          presenter_id: State.myId,
          slide_number: State.currentSlide,
        });
        updateSlideButtonLabels();
      }
    });
  }

  const nextBtn = $("nextSlideBtn");
  if (nextBtn) {
    nextBtn.addEventListener("click", () => {
      if (!State.isActive || !State.activeBlock) return;
      if (State.currentSlide < State.slideEnd) {
        State.currentSlide++;
        socket.emit("presenter:goto_slide", {
          presenter_id: State.myId,
          slide_number: State.currentSlide,
        });
        updateSlideButtonLabels();
      } else {
        const canClick = ["click", "either"].includes(State.endCondition);
        if (canClick) {
          nextBtn.disabled = true;
          nextBtn.textContent = "Advancing…";
          socket.emit("presenter:request_advance", {
            presenter_id: State.myId,
            block_id: State.activeBlock.block_id,
            request_epoch: Date.now() / 1000,
          });
        }
      }
    });
  }
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

  // Mobile browsers require a real user gesture before AudioContext can play.
  // Register a one-time touch/click listener — the first tap on anything
  // (a nav button, the screen, etc.) will prime the audio context.
  document.addEventListener("touchstart", requestVibrationPermission, { once: true });
  document.addEventListener("click",      requestVibrationPermission, { once: true });

  // Safety timer: if still on the waiting screen after 8 s, something went
  // wrong — send back to join so the presenter can re-select.
  const _safetyTimer = setTimeout(() => {
    const waiting = $("screenWaiting");
    const stuckOnWaiting = waiting && waiting.classList.contains("active");
    if (stuckOnWaiting) window.location.href = "/join";
  }, 8000);

  // Note: the global "connect" handler (top of file) already emits presenter:join
  // when isPresenterPage is true, so no second handler is needed here.

  socket.on("presenter:join_ok", ({ presenter_id, name, color, session_snapshot }) => {
    clearTimeout(_safetyTimer);
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
    } else if (code === "unknown_presenter_id") {
      // Stale sessionStorage from a previous session with a different timeline.
      sessionStorage.removeItem("orchestra_presenter_id");
      sessionStorage.removeItem("orchestra_presenter_name");
      window.location.href = "/join";
    }
  });

  // Block events
  socket.on("block:activate", (payload) => {
    handleBlockActivate(payload);
  });

  socket.on("block:completed", () => {
    // Superseded by the next block:activate or session:completed
  });

  socket.on("block:overrun", () => {
    if (State.isActive) {
      // Flash the countdown red briefly
      const cd = $("countdownDisplay");
      if (cd) {
        cd.style.color = "#e85454";
        setTimeout(() => { cd.style.color = ""; }, 500);
      }
    }
  });

  // Slide navigation confirmation from server
  socket.on("slide:goto", ({ slide_number, reason }) => {
    State.currentSlide = slide_number;
    updateSlideButtonLabels();
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

  // ---------------------------------------------------------------------------
  // Slide navigation buttons
  // ---------------------------------------------------------------------------
  const prevBtn = $("prevSlideBtn");
  if (prevBtn) {
    prevBtn.addEventListener("click", () => {
      if (!State.isActive || !State.activeBlock) return;
      if (State.currentSlide > 1) {
        State.currentSlide--;
        socket.emit("presenter:goto_slide", {
          presenter_id: State.myId,
          slide_number: State.currentSlide,
        });
        updateSlideButtonLabels();
      }
    });
  }

  const nextBtn = $("nextSlideBtn");
  if (nextBtn) {
    nextBtn.addEventListener("click", () => {
      if (!State.isActive || !State.activeBlock) return;
      if (State.currentSlide < State.slideEnd) {
        // Navigate to next slide within the block
        State.currentSlide++;
        socket.emit("presenter:goto_slide", {
          presenter_id: State.myId,
          slide_number: State.currentSlide,
        });
        updateSlideButtonLabels();
      } else {
        // Already at the last slide — advance the block (if click is allowed)
        const canClick = ["click", "either"].includes(State.endCondition);
        if (canClick) {
          nextBtn.disabled = true;
          nextBtn.textContent = "Advancing…";
          socket.emit("presenter:request_advance", {
            presenter_id: State.myId,
            block_id: State.activeBlock.block_id,
            request_epoch: Date.now() / 1000,
          });
        }
      }
    });
  }

  socket.on("presenter:advance_rejected", () => {
    const nb = $("nextSlideBtn");
    if (nb && State.isActive) {
      nb.disabled = false;
      updateSlideButtonLabels();
    }
  });

  socket.on("presenter:prev_block_rejected", () => {
    const pb = $("prevSlideBtn");
    if (pb) pb.disabled = false;
  });

  // Start Timer button (shown on the first block before timer begins)
  const startTimerBtnP = $("startTimerBtn");
  if (startTimerBtnP) {
    startTimerBtnP.addEventListener("click", () => {
      if (!State.awaitingPresenterStart) return;
      State.awaitingPresenterStart = false;
      startTimerBtnP.style.display = "none";

      const slideNavRow = $("slideNavRow");
      if (slideNavRow) slideNavRow.style.display = "";

      const prevBtn = $("prevSlideBtn");
      const nextBtn = $("nextSlideBtn");
      if (prevBtn) prevBtn.disabled = false;
      if (nextBtn) nextBtn.disabled = false;

      // Shift session elapsed anchor forward by the pre-start wait so the
      // displayed elapsed time doesn't include the period before Start Timer.
      const waitMsP = Date.now() - State.activateEpoch;
      if (State.sessionStartEpoch !== null && waitMsP > 0) {
        State.sessionStartEpoch += waitMsP;
      }
      // Use current time as the start epoch; first timer:tick will correct drift
      State.activateEpoch = Date.now();

      socket.emit("presenter:start_timer", {
        presenter_id: State.myId,
        block_id: State.activeBlock?.block_id,
      });

      updateSlideButtonLabels();
      startCountdown();
    });
  }
}

// ---------------------------------------------------------------------------
// Session snapshot (mid-session join)
// ---------------------------------------------------------------------------
function applySessionSnapshot(snapshot) {
  State.sessionState = snapshot.state;
  State.session = snapshot;

  // Guard against a race condition: block:activate can arrive before join_ok
  // (both are in flight at the same time near the end of the start delay).
  // If we already processed block:activate, keep the screen as-is.
  if (State.activeBlock) {
    return;
  }

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

  // During warmup the server snapshot already has current_block = blocks[0],
  // but activate_epoch is 0 (block not yet started).  Never show the active
  // screen prematurely — just show the waiting spinner until block:activate
  // arrives with the real epoch when GO is pressed.
  if (snapshot.state === "warmup") {
    showScreen("screenWaiting");
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
        effective_duration_seconds: snapshot.effective_duration_seconds || b.duration,
        session_budget_seconds: snapshot.session_budget_seconds || 0,
        end_condition: b.end_condition,
        overrun_behavior: b.overrun_behavior,
        activate_epoch: snapshot.activate_epoch,
        notes: b.notes,
        awaiting_presenter_start: snapshot.awaiting_presenter_start || false,
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
  // Use effective_duration for the countdown so budget surplus is visible
  State.blockDuration = payload.effective_duration_seconds || payload.duration_seconds;
  State.endCondition = payload.end_condition;
  State.isActive = payload.presenter_id === State.myId;

  // Slide tracking
  State.slideStart = payload.slide_start ?? null;
  State.slideEnd = payload.slide_end ?? null;
  State.currentSlide = payload.slide_start ?? null;
  State.sessionBudgetSeconds = payload.session_budget_seconds || 0;

  // Block 0 waits for the presenting participant to tap "Start Timer"
  State.awaitingPresenterStart = !!(payload.awaiting_presenter_start && State.isActive);

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

  const startTimerBtn = $("startTimerBtn");
  const slideNavRow = $("slideNavRow");

  if (State.awaitingPresenterStart) {
    // Show full-duration label and the Start Timer button; hide nav
    const cd = $("countdownDisplay");
    if (cd) cd.textContent = formatSeconds(State.blockDuration);
    if (startTimerBtn) startTimerBtn.style.display = "block";
    if (slideNavRow) slideNavRow.style.display = "none";
  } else {
    // Normal flow: hide start button, show nav, start countdown
    if (startTimerBtn) startTimerBtn.style.display = "none";
    if (slideNavRow) slideNavRow.style.display = "";

    // Re-enable nav buttons
    const prevBtn = $("prevSlideBtn");
    const nextBtn = $("nextSlideBtn");
    if (prevBtn) prevBtn.disabled = false;
    if (nextBtn) nextBtn.disabled = false;

    // Update slide info and button labels
    updateSlideButtonLabels();
    startCountdown();
  }
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
    const nextMyBlock = myBlocks.find((b) => {
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
// Slide navigation helpers
// ---------------------------------------------------------------------------
function updateSlideButtonLabels() {
  if (!State.isActive || State.slideStart === null || State.slideEnd === null) return;

  const prevBtn = $("prevSlideBtn");
  const nextBtn = $("nextSlideBtn");
  const slideInfo = $("slideInfo");

  const atFirst = State.currentSlide <= 1;
  const atLast  = State.currentSlide >= State.slideEnd;
  const canClickAdvance = ["click", "either"].includes(State.endCondition);

  if (prevBtn) {
    prevBtn.disabled = atFirst;
    if (!atFirst) prevBtn.textContent = "← Prev";
  }

  if (nextBtn && !nextBtn.disabled) {
    if (atLast && canClickAdvance) {
      nextBtn.textContent = "Done →";
    } else if (atLast && !canClickAdvance) {
      nextBtn.textContent = "Next →";
      nextBtn.disabled = true;  // can't advance past last slide on a time-only block
    } else {
      nextBtn.textContent = "Next →";
    }
  }

  if (slideInfo) {
    if (State.currentSlide >= State.slideStart) {
      const blockSlides = State.slideEnd - State.slideStart + 1;
      const slideInBlock = State.currentSlide - State.slideStart + 1;
      slideInfo.textContent = `Slide ${slideInBlock} of ${blockSlides}`;
    } else {
      slideInfo.textContent = `Slide ${State.currentSlide}`;
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

  // Budget indicator: (+MM:SS) surplus / (-MM:SS) deficit
  const budgetEl = $("budgetDisplay");
  if (budgetEl) {
    const budget = State.sessionBudgetSeconds;
    if (Math.abs(budget) >= 1) {
      const sign = budget >= 0 ? "+" : "-";
      const abs = Math.abs(budget);
      budgetEl.textContent = `(${sign}${formatSeconds(abs)})`;
      budgetEl.classList.toggle("surplus", budget > 0);
      budgetEl.classList.toggle("deficit", budget < 0);
    } else {
      budgetEl.classList.remove("surplus", "deficit");
    }
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
// Audio notification (replaces Vibration API — works without HTTPS)
// ---------------------------------------------------------------------------

function _getAudioContext() {
  if (!_audioCtx || _audioCtx.state === "closed") {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    _audioCtx = new AC();
    _keepAliveSource = null;  // reset so keep-alive restarts on new context
  }
  return _audioCtx;
}

// Prime the AudioContext on first user gesture (browsers require user
// interaction before audio can play — call this from a click/tap handler).
function requestVibrationPermission() {
  const ctx = _getAudioContext();
  if (!ctx) return;
  // iOS Safari requires a BufferSourceNode to be started *synchronously*
  // within the user gesture to truly unlock the AudioContext.  A plain
  // ctx.resume() without accompanying audio output is not sufficient.
  const silentBuf = ctx.createBuffer(1, 1, ctx.sampleRate);
  const unlock = ctx.createBufferSource();
  unlock.buffer = silentBuf;
  unlock.connect(ctx.destination);
  unlock.start(0);  // synchronous — happens inside the gesture call stack
  if (ctx.state === "suspended") {
    ctx.resume().then(() => { _startKeepAlive(ctx); }).catch(() => {});
  } else {
    _startKeepAlive(ctx);
  }
}

// Start a near-silent looping buffer so the AudioContext stays "running"
// between vibration events. Mobile browsers (iOS Safari, Chrome Android)
// auto-suspend idle AudioContexts; without this the second and later
// presenter:vibrate events arrive on a suspended context and ctx.resume()
// can no longer be called without a user gesture.
function _startKeepAlive(ctx) {
  if (_keepAliveSource) return;  // already running
  const buf = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate);
  const src = ctx.createBufferSource();
  src.buffer = buf;
  src.loop = true;
  const gain = ctx.createGain();
  gain.gain.value = 0.00001;   // effectively inaudible
  src.connect(gain);
  gain.connect(ctx.destination);
  src.start();
  _keepAliveSource = src;
}

// Play a short buzz-tone pattern that mimics the feel of a vibration alert.
// patternMs follows the same on/off/on/... convention as navigator.vibrate():
//   even indices = "on" (tone plays), odd indices = silence gaps.
function triggerVibration(patternMs) {
  const ctx = _getAudioContext();
  if (!ctx) return;
  const doPlay = () => {
    let time = ctx.currentTime;
    patternMs.forEach((durationMs, i) => {
      if (i % 2 === 0) {  // "on" segment — play a buzz tone
        const osc  = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        const dur = durationMs / 1000;
        osc.type = "sine";
        osc.frequency.value = 180;          // low buzz frequency
        gain.gain.setValueAtTime(0.8, time);
        gain.gain.exponentialRampToValueAtTime(0.001, time + dur);
        osc.start(time);
        osc.stop(time + dur);
      }
      time += durationMs / 1000;            // advance clock past this segment
    });
  };
  if (ctx.state === "suspended") {
    ctx.resume().then(() => { _startKeepAlive(ctx); doPlay(); }).catch(() => {});
  } else {
    _startKeepAlive(ctx);
    doPlay();
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
