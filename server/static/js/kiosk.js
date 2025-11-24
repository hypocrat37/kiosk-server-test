
(async function () {
  const kioskId = window.KIOSK_ID;
  const gameId = window.GAME_ID;
  const apiKey = window.API_KEY || '';

  const queueList = document.getElementById('queueList');
  const statusEl = document.getElementById('status');
  const startBtn = document.getElementById('startBtn');
  const waitingOverlay = document.getElementById('waitingOverlay');
  const modeList = document.getElementById('modeList');

  const coinStage = document.getElementById('coinStage');
  const scanPrompt = document.getElementById('scanPrompt');

  // Track queue state so we can trigger a coin and delay rendering the new slot
  // until the animation completes, and to drive UI hints.
  let lastQueueCount = 0;
  let visibleQueueCount = 0;
  let kioskStatus = 'idle';
  let queueInitialized = false;
  let isQueueAnimating = false;
  let pendingQueuePlayers = null;

  function getAvatarUrl(p){
    if (!p) return null;
    if (p.avatar_url) return p.avatar_url;
    if (p.username && p.username.startsWith('dev_player_')) {
      return '/static/avatars/default.png';
    }
    return null;
  }

  function animateCoinForPlayer(p, onComplete){
    const coin = document.createElement('div');
    coin.className = 'coin rise';
    const face = document.createElement('div');
    face.className = 'face';
    const avatar = getAvatarUrl(p);
    if (avatar) {
      face.style.backgroundImage = `url(${avatar})`;
      face.classList.add('img');
    } else {
      const initials = (p?.name || p?.username || 'P').split(' ').map(s=>s[0]).join('').slice(0,2).toUpperCase();
      face.textContent = initials || 'P';
    }
    coin.appendChild(face);
    coinStage.appendChild(coin);
    coin.addEventListener('animationend', ()=> {
      coin.remove();
      if (typeof onComplete === 'function') {
        onComplete();
      }
    });
  }

  // Keyboard-wedge collector (no input box)
  let buffer = '';
  let timer = null;

  async function enqueueDevPlayer() {
    try {
      const resp = await fetch(`/kiosks/${encodeURIComponent(kioskId)}/queue/dev_add`, {
        method: 'POST',
        headers: headers()
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok || !data.ok) {
        statusEl.textContent = (data && data.detail) || 'Failed to queue test player';
        return;
      }
      const p = await fetchPlayer(data.player_id).catch(() => null);
      if (p) { showSplash(p); }
      // Queue animation is handled in refreshQueue when the new entry appears.
      refreshQueue();
    } catch (e) {
      statusEl.textContent = 'Error while queuing test player';
    }
  }

  function flush(){
    if (!buffer) return;
    const uid = buffer; buffer='';
    handleScan(uid);
  }
  window.addEventListener('keydown', (e)=>{
    if (e.ctrlKey && e.shiftKey && (e.key === 'q' || e.key === 'Q')) {
      e.preventDefault();
      enqueueDevPlayer();
      return;
    }
    const k = e.key;
    if (k === 'Enter') { e.preventDefault(); flush(); return; }
    if (/^[0-9A-Za-z]$/.test(k)) {
      buffer += k;
      clearTimeout(timer);
      timer = setTimeout(flush, 250);
    }
  });


  let selectedMode = null;
  let kioskObjectives = [];
  let kioskTraits = {};

  function headers(extra={}){
    return Object.assign({'Content-Type':'application/json','X-API-Key': apiKey}, extra);
  }

  let splash = document.getElementById('splash');
  let splashTypeTimer = null;
  let splashHideTimer = null;
  function showSplash(p){
    const name = p.name || p.username || 'Player';
    const fullText = `${name} joined!`;
    const nameEl = document.getElementById('splashName');
    const img = document.getElementById('splashAvatar');
    const avatar = getAvatarUrl(p) || '/static/avatars/default.png';
    img.src = avatar;

    if (splashTypeTimer) { clearInterval(splashTypeTimer); splashTypeTimer = null; }
    if (splashHideTimer) { clearTimeout(splashHideTimer); splashHideTimer = null; }

    nameEl.textContent = '';
    splash.classList.remove('show'); void splash.offsetWidth;
    splash.classList.add('show');

    let idx = 0;
    splashTypeTimer = setInterval(() => {
      if (idx <= fullText.length) {
        nameEl.textContent = fullText.slice(0, idx);
        idx += 1;
      } else {
        clearInterval(splashTypeTimer);
        splashTypeTimer = null;
      }
    }, 60);

    splashHideTimer = setTimeout(()=> {
      splash.classList.remove('show');
    }, 2200);
  }

  async function refreshModes(){
    const resp = await fetch(`/kiosks/${encodeURIComponent(kioskId)}/status`);
    if (!resp.ok) return;
    const data = await resp.json();
    modeList.innerHTML = '';
    kioskObjectives = Array.isArray(data.objectives) ? data.objectives : [];
    window.KIOSK_OBJECTIVES = kioskObjectives;
    kioskTraits = data.traits || {};
    window.KIOSK_TRAITS = kioskTraits;
    // Hide trait icons that have a configured level of 0
    const iconsRow = document.querySelector('.kt-icons');
    if (iconsRow) {
      let visibleCount = 0;
      iconsRow.querySelectorAll('.kt-icon[data-trait]').forEach((btn) => {
        const key = btn.getAttribute('data-trait');
        const level = Number((kioskTraits && kioskTraits[key] != null) ? kioskTraits[key] : 0);
        if (level > 0) {
          btn.classList.remove('hidden');
          visibleCount += 1;
        } else {
          btn.classList.add('hidden');
        }
      });
      if (visibleCount === 0) {
        iconsRow.classList.add('hidden');
      } else {
        iconsRow.classList.remove('hidden');
      }
    }
    const list = data.modes && data.modes.length ? data.modes : ['default'];
    list.forEach((m,i)=>{
      const btn = document.createElement('button');
      btn.className = 'mode-btn'+(i===0?' active':'');
      if(i===0) selectedMode = m;
      btn.textContent = m;
      btn.onclick = ()=>{
        [...modeList.querySelectorAll('.mode-btn')].forEach(x=>x.classList.remove('active'));
        btn.classList.add('active'); selectedMode = m;
      };
      modeList.appendChild(btn);
    });
  }

  
  function renderQueue(players, maxSlots){
    queueList.innerHTML = '';
    for (let i = 0; i < maxSlots; i++) {
      const li = document.createElement('li');
      const p = players[i];
      if (p) {
        li.classList.add('filled');
        li.dataset.playerId = String(p.id);
        li.dataset.username = p.username || '';
        const avatar = getAvatarUrl(p);
        if (avatar) {
          const img = document.createElement('img'); img.className='avatar'; img.src = avatar; img.alt = p.username || '';
          li.appendChild(img);
        } else {
          const span = document.createElement('span'); span.className='initials';
          const parts = (p.name || p.username || '').split(' ');
          const initials = (parts[0]?.[0] || '') + (parts[1]?.[0] || '');
          span.textContent = (initials || (p.username?.slice(0,2) || 'P')).toUpperCase();
          li.appendChild(span);
        }
        li.title = `#${p.id} ${p.username}`;
      } else {
        li.classList.add('empty');
      }
      queueList.appendChild(li);
    }
  }

  function updateStartPulse(queueCount, status){
    if (!startBtn) return;
    const isRunning = status === 'running';
    if (!isRunning && queueCount >= 2) {
      startBtn.classList.add('pulse-ready');
    } else {
      startBtn.classList.remove('pulse-ready');
    }
  }

async function refreshQueue() {
  const resp = await fetch(`/kiosks/${encodeURIComponent(kioskId)}/queue`, {headers: headers({'Content-Type': undefined})});
  if (!resp.ok) return;
  const data = await resp.json();
  const maxSlots = 6;
  const queuePlayers = data.queue.map(q => q.player);
  const players = queuePlayers.slice(0, maxSlots);
  const currentCount = players.filter(Boolean).length;
  visibleQueueCount = currentCount;
  if (!queueInitialized) {
    renderQueue(players, maxSlots);
    lastQueueCount = currentCount;
    queueInitialized = true;
    updateStartPulse(visibleQueueCount, kioskStatus);
    return;
  }

  // If an animation is already running, defer updates until it completes.
  if (isQueueAnimating) {
    pendingQueuePlayers = players;
    return;
  }

  if (currentCount > lastQueueCount) {
    // New player(s) joined; animate the next one into place.
    const previousPlayers = players.slice(0, lastQueueCount);
    const newPlayer = players[lastQueueCount];
    renderQueue(previousPlayers, maxSlots);
    isQueueAnimating = true;
    pendingQueuePlayers = players;
    if (newPlayer) {
      animateCoinForPlayer(newPlayer, () => {
        isQueueAnimating = false;
        const finalPlayers = pendingQueuePlayers || players;
        renderQueue(finalPlayers, maxSlots);
        lastQueueCount = finalPlayers.filter(Boolean).length;
        pendingQueuePlayers = null;
      });
    } else {
      // Fallback: no identifiable new player, just render full queue.
      isQueueAnimating = false;
      renderQueue(players, maxSlots);
      lastQueueCount = currentCount;
      pendingQueuePlayers = null;
    }
  } else {
    renderQueue(players, maxSlots);
    lastQueueCount = currentCount;
  }

  updateStartPulse(visibleQueueCount, kioskStatus);
}

  // Expose queue refresh so other scripts (e.g., profile overlay) can trigger it.
  window.refreshQueue = refreshQueue;

  async function refreshStatus(){
    const resp = await fetch(`/kiosks/${encodeURIComponent(kioskId)}/status`);
    if(!resp.ok) return;
    const data = await resp.json();
    kioskStatus = data.status === 'running' ? 'running' : 'idle';

    // Non-blocking banner + Start button disable
    if (data.status === 'running') {
      if (waitingOverlay) { waitingOverlay.classList.add('show'); waitingOverlay.classList.remove('hidden'); }
      if (startBtn) { startBtn.disabled = true; startBtn.title = 'Game currently in play'; }
    } else {
      if (waitingOverlay) { waitingOverlay.classList.remove('show'); waitingOverlay.classList.add('hidden'); }
      if (startBtn) { startBtn.disabled = false; startBtn.title = 'Start Game'; }
    }

    updateStartPulse(visibleQueueCount, kioskStatus);
  }

  const ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/kiosk/${encodeURIComponent(kioskId)}`);
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.type === 'queue_update' || msg.type === 'session_started' || msg.type === 'session_ended') {
      refreshQueue(); refreshStatus();
    }
  };

  let agentWS = null;
  try {
    agentWS = new WebSocket('ws://127.0.0.1:8765');
    agentWS.onmessage = (ev) => handleScan(ev.data);
    agentWS.onopen = () => console.log('Kiosk agent connected');
  } catch(e) { console.log('No local agent found'); }

  
  async function fetchPlayer(playerId){
    const resp = await fetch(`/players/${playerId}`);
    if (resp.ok) return await resp.json();
    return null;
  }

  async function handleScan(uid) {
    statusEl.textContent = `Scanned: ${uid}`;
    const resp = await fetch('/rfid/scan', {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify({ kiosk_id: kioskId, rfid_uid: uid })
    });
    const data = await resp.json();
    if (resp.status === 401){
      statusEl.textContent = `Unauthorized kiosk (API key). Check configuration.`;
      return;
    }
    if (data.known) {
      statusEl.textContent = `Queued player #${data.player_id}`;
      const p = await fetchPlayer(data.player_id);
      if (p) { showSplash(p); animateCoinForPlayer(p); }
      refreshQueue();
    } else {
      statusEl.textContent = 'Unknown band. Please visit the Profile Kiosk to create your player profile.';
    }
  }

  startBtn.addEventListener('click', async () => {
    const resp = await fetch('/sessions/start', {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify({ kiosk_id: kioskId, mode: selectedMode })
    });
    const data = await resp.json().catch(()=>({}));
    if (resp.ok) {
      if (data.status === 'running') {
        statusEl.textContent = `Game started (session #${data.id}).`;
      } else {
        statusEl.textContent = `Waiting for current game...`;
      }
      refreshQueue(); refreshStatus();
    } else {
      statusEl.textContent = `Error: ${(data && data.detail) || resp.statusText}`;
    }
  });

  await refreshModes();
  refreshQueue();
  refreshStatus();
  
})();


// ---------------- Player profile/history overlay ----------------
(function(){
  const overlay = document.getElementById('profileOverlay');
  const closeBtn = document.getElementById('profileClose');
  const historyBody = document.getElementById('profileHistory');
  const titleEl = document.getElementById('profileTitle');
  const leaveBtn = document.getElementById('profileLeave');
  const editBtn = document.getElementById('profileEdit');
  const editOverlay = document.getElementById('profileEditOverlay');
  const editCloseBtn = document.getElementById('profileEditClose');
  const editAvatarImg = document.getElementById('profileEditAvatar');
  const editNameInput = document.getElementById('profileEditName');
  const editRandomBtn = document.getElementById('profileRandomAvatar');
  const editSaveBtn = document.getElementById('profileEditSave');
  const editMsgEl = document.getElementById('profileEditMsg');
  const queueStatusEl = document.getElementById('profileQueueStatus');

  const kioskId = window.KIOSK_ID;
  const apiKey = window.API_KEY || '';
  const statusEl = document.getElementById('status');

  let currentPlayerId = null;

  if (!overlay || !historyBody || !titleEl) {
    return;
  }

  function closeOverlay(){
    overlay.classList.add('hidden');
    overlay.setAttribute('aria-hidden', 'true');
  }

  function closeEditOverlay(){
    if (!editOverlay) return;
    editOverlay.classList.add('hidden');
    editOverlay.setAttribute('aria-hidden', 'true');
  }

  if (closeBtn) {
    closeBtn.addEventListener('click', (e)=>{ e.preventDefault(); closeOverlay(); });
  }

  // Allow tapping the dimmed backdrop to close on touch screens.
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) {
      closeOverlay();
    }
  });

  // Escape key closes the overlay for keyboard/maintenance use.
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (!overlay.classList.contains('hidden')) {
        closeOverlay();
      }
      if (editOverlay && !editOverlay.classList.contains('hidden')) {
        closeEditOverlay();
      }
    }
  });

  function headers(extra = {}) {
    return Object.assign(
      { 'Content-Type': 'application/json', 'X-API-Key': apiKey },
      extra
    );
  }

  async function openProfileOverlay(playerId, username){
    currentPlayerId = playerId;
    titleEl.textContent = username ? `${username} — Game History` : 'Game History';
    historyBody.textContent = 'Loading…';
    if (queueStatusEl) {
      queueStatusEl.textContent = '';
    }
    overlay.classList.remove('hidden');
    overlay.setAttribute('aria-hidden', 'false');

    // Subtle note about whether this player is currently in the kiosk queue.
    if (queueStatusEl && kioskId) {
      try {
        const qResp = await fetch(`/kiosks/${encodeURIComponent(kioskId)}/queue`, {
          headers: headers({ 'Content-Type': undefined })
        });
        if (qResp.ok) {
          const qData = await qResp.json();
          const inQueue = Array.isArray(qData.queue) && qData.queue.some(
            (item) => item.player && item.player.id === Number(playerId)
          );
          queueStatusEl.textContent = inQueue
            ? 'You are currently in the queue for this kiosk.'
            : '';
        }
      } catch (e) {
        // Keep this silent; the note is a nice-to-have.
      }
    }

    try {
      const resp = await fetch(`/players/${encodeURIComponent(playerId)}/history`);
      if (!resp.ok) {
        historyBody.textContent = 'Failed to load history.';
        return;
      }
      const data = await resp.json();
      const sessions = Array.isArray(data.sessions) ? data.sessions : [];
      renderHistoryList(sessions);
    } catch (e) {
      console.error('Failed to load player history', e);
      historyBody.textContent = 'Error loading history.';
    }
  }

  function parseScoreValue(val) {
    if (val == null) return null;
    const n = Number(val);
    return Number.isFinite(n) ? n : null;
  }

  function getScoreInfo(session) {
    const metrics = session.metrics || {};
    if (metrics.stars != null) {
      const raw = parseScoreValue(metrics.stars);
      let label = `${metrics.stars}★`;
      if (raw != null && raw >= 0 && raw <= 3) {
        const starsStr = '★'.repeat(Math.max(0, Math.min(3, Math.round(raw))));
        label = starsStr || '0★';
      }
      return { raw, label };
    }
    if (session.score != null) {
      return { raw: parseScoreValue(session.score), label: session.score };
    }
    if (metrics.score != null) {
      return { raw: parseScoreValue(metrics.score), label: metrics.score };
    }
    return { raw: null, label: null };
  }

  function fmtDate(ts) {
    if (!ts) return '';
    try {
      return new Date(ts).toLocaleString();
    } catch (e) {
      return ts;
    }
  }

  function normalizeModeName(raw) {
    const str = (raw || 'default').toString().trim();
    const key = str ? str.toLowerCase() : 'default';
    const pretty = str
      ? str
          .replace(/_/g, ' ')
          .replace(/\b\w/g, (c) => c.toUpperCase())
      : 'Default';
    return { key, label: pretty };
  }

  function summarizeMode(modeSessions) {
    const sorted = modeSessions
      .slice()
      .sort((a, b) => (b.started_at || '').localeCompare(a.started_at || ''));
    const attempts = sorted.slice(0, 5).map((sess) => {
      const score = getScoreInfo(sess);
      return {
        scoreLabel: score.label,
        when: fmtDate(sess.started_at),
        kioskId: sess.kiosk_id,
      };
    });
    let bestScoreLabel = null;
    let bestScoreRaw = null;
    let bestStars = null;
    sorted.forEach((sess) => {
      const score = getScoreInfo(sess);
      if (score.raw != null && (bestScoreRaw == null || score.raw > bestScoreRaw)) {
        bestScoreRaw = score.raw;
        bestScoreLabel = score.label ?? String(score.raw);
      }
      const starsRaw =
        sess.metrics && sess.metrics.stars != null
          ? parseScoreValue(sess.metrics.stars)
          : null;
      if (starsRaw != null && (bestStars == null || starsRaw > bestStars)) {
        bestStars = starsRaw;
      }
    });
    const lastPlayed = sorted.length ? fmtDate(sorted[0].started_at) : '';
    const lastPlayedTs = sorted.length ? Date.parse(sorted[0].started_at) || 0 : 0;
    return { attempts, bestScoreLabel, bestStars, lastPlayed, lastPlayedTs };
  }

  function buildGameSummaries(sessions) {
    const games = [];
    const map = new Map();

    sessions.forEach((s) => {
      const gid = s.game_id || 'unknown';
      let game = map.get(gid);
      if (!game) {
        game = { id: gid, name: s.game_name || gid, modes: {}, sessions: [] };
        map.set(gid, game);
        games.push(game);
      }
      const rawMode = s.mode || (s.metrics && s.metrics.kiosk_mode) || 'default';
      const { key: modeKey, label: modeLabel } = normalizeModeName(rawMode);
      if (!game.modes[modeKey]) {
        game.modes[modeKey] = { label: modeLabel, sessions: [] };
      }
      game.modes[modeKey].sessions.push(s);
      game.sessions.push(s);
    });

    games.forEach((g) => {
      let bestScoreRaw = null;
      let bestScoreLabel = null;
      Object.values(g.modes).forEach((modeInfo) => {
        modeInfo.sessions.forEach((sess) => {
          const score = getScoreInfo(sess);
          if (score.raw != null && (bestScoreRaw == null || score.raw > bestScoreRaw)) {
            bestScoreRaw = score.raw;
            bestScoreLabel = score.label ?? String(score.raw);
          }
        });
      });
      g.bestScoreLabel = bestScoreLabel;
      g.totalPlays = g.sessions.length;
    });

    return games;
  }

  function renderHistoryList(sessions){
  if (!sessions.length) {
    historyBody.textContent = 'No games played yet.';
    return;
  }
  const games = buildGameSummaries(sessions);
    let selectedGameId =
      games.find((g) => g.id === window.GAME_ID)?.id ||
      (games.length ? games[0].id : null);

    historyBody.innerHTML = '';

    const grid = document.createElement('div');
    grid.className = 'history-grid';

    const gameList = document.createElement('div');
    gameList.className = 'history-game-list';

    const detail = document.createElement('div');
    detail.className = 'history-game-detail';

    grid.appendChild(gameList);
    grid.appendChild(detail);
    historyBody.appendChild(grid);

    function renderGameButtons() {
      gameList.innerHTML = '';
      games.forEach((g) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'history-game-btn' + (g.id === selectedGameId ? ' active' : '');
        const playsText = `${g.totalPlays} play${g.totalPlays === 1 ? '' : 's'}`;
        const bestScore = g.bestScoreLabel != null ? g.bestScoreLabel : '—';
        btn.innerHTML = `
          <div class="hg-name">${g.name}</div>
          <div class="hg-meta">${playsText}</div>
          <div class="hg-score">Best: ${bestScore}</div>
        `;
        btn.addEventListener('click', () => {
          if (selectedGameId === g.id) return;
          selectedGameId = g.id;
          renderGameButtons();
          renderDetail();
        });
        gameList.appendChild(btn);
      });
    }

    function renderDetail() {
      const game = games.find((g) => g.id === selectedGameId) || games[0];
      if (!game) {
        detail.innerHTML = '<div class="history-empty">No games played yet.</div>';
        return;
      }

      const modeEntries = Object.entries(game.modes).map(([modeName, modeInfo]) => {
        const summary = summarizeMode(modeInfo.sessions || []);
        return { modeName, modeLabel: modeInfo.label || modeName, summary };
      });

      const totalPossibleStars = modeEntries.length * 3;
      let earnedStars = 0;
      let hasStarData = false;
      modeEntries.forEach(({ summary }) => {
        if (summary.bestStars != null) {
          hasStarData = true;
          earnedStars += Math.max(0, Math.min(3, Math.round(summary.bestStars)));
        }
      });
      const bestScore = game.bestScoreLabel != null ? game.bestScoreLabel : '—';
      const overallLabel =
        hasStarData && totalPossibleStars > 0
          ? `${earnedStars}/${totalPossibleStars}★`
          : bestScore;

      detail.innerHTML = '';
      const head = document.createElement('div');
      head.className = 'history-game-head';
      head.innerHTML = `
        <div>
          <div class="hg-label">Selected Game</div>
          <div class="hg-title">${game.name}</div>
          <div class="hg-sub">${game.totalPlays} total play${game.totalPlays === 1 ? '' : 's'}</div>
        </div>
        <div class="hg-stat">
          <span class="hg-stat-label">Overall Score</span>
          <span class="hg-stat-value">${overallLabel}</span>
        </div>
      `;
      detail.appendChild(head);

      const modeList = document.createElement('div');
      modeList.className = 'history-mode-list';
      detail.appendChild(modeList);

      modeEntries
        .sort((a, b) => b.summary.lastPlayedTs - a.summary.lastPlayedTs)
        .forEach((entry, idx) => {
          const block = document.createElement('div');
          block.className = 'mode-block';

          const toggle = document.createElement('button');
          toggle.type = 'button';
          toggle.className = 'mode-toggle';
          const bestModeScore =
            entry.summary.bestScoreLabel != null ? entry.summary.bestScoreLabel : '—';
          toggle.innerHTML = `
            <div class="mode-left">
            <div class="mode-name">${entry.modeLabel}</div>
            <div class="mode-top">
              <span class="mode-top-label">Top score</span>
              <strong>${bestModeScore}</strong>
            </div>
          </div>
          <div class="mode-right">
              <span class="mode-last empty">${entry.summary.lastPlayed ? 'Tap to view history' : 'No plays yet'}</span>
              <span class="chevron">▾</span>
          </div>
        `;

          const attempts = document.createElement('div');
          attempts.className = 'mode-attempts';
          const attemptList = document.createElement('ul');
          attemptList.className = 'attempt-list';

          if (!entry.summary.attempts.length) {
            const li = document.createElement('li');
            li.className = 'attempt-row';
            li.textContent = 'No attempts recorded for this mode yet.';
            attemptList.appendChild(li);
          } else {
            entry.summary.attempts.forEach((attempt) => {
              const li = document.createElement('li');
              li.className = 'attempt-row';
              const scoreText = attempt.scoreLabel != null ? attempt.scoreLabel : '—';
              const kioskText = attempt.kioskId ? `@${attempt.kioskId}` : '';
              li.innerHTML = `
                <div class="attempt-score">${scoreText}</div>
                <div class="attempt-meta">
                  <div class="attempt-when">${attempt.when || 'Unknown time'}</div>
                  ${kioskText ? `<div class="attempt-kiosk">${kioskText}</div>` : ''}
                </div>
              `;
              attemptList.appendChild(li);
            });
          }

          attempts.appendChild(attemptList);
          block.appendChild(toggle);
          block.appendChild(attempts);
          modeList.appendChild(block);

          function updateAttemptsHeight(open) {
            attempts.style.maxHeight = open ? `${attempts.scrollHeight}px` : '0px';
          }

          requestAnimationFrame(() => {
            updateAttemptsHeight(block.classList.contains('open'));
          });

          toggle.addEventListener('click', () => {
            block.classList.toggle('open');
            updateAttemptsHeight(block.classList.contains('open'));
          });
        });
    }

    renderGameButtons();
    renderDetail();
  }

  async function openEditOverlay(){
    if (!editOverlay || !editAvatarImg || !editNameInput || !editMsgEl) return;
    if (!currentPlayerId) return;
    editMsgEl.textContent = '';
    try {
      const resp = await fetch(`/players/${encodeURIComponent(currentPlayerId)}`);
      if (!resp.ok) {
        editMsgEl.textContent = 'Failed to load profile.';
        return;
      }
      const data = await resp.json();
      editNameInput.value = data.name || data.username || '';
      editAvatarImg.src = data.avatar_url || '/static/avatars/default.png';
    } catch (e) {
      console.error('Failed to load player profile', e);
      editMsgEl.textContent = 'Error loading profile.';
      return;
    }
    editOverlay.classList.remove('hidden');
    editOverlay.setAttribute('aria-hidden', 'false');
  }

  if (leaveBtn) {
    leaveBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      if (!currentPlayerId || !kioskId) {
        closeOverlay();
        return;
      }
      const leavingName = titleEl && titleEl.textContent
        ? titleEl.textContent.split(' — ')[0]
        : '';
      try {
        const resp = await fetch(`/kiosks/${encodeURIComponent(kioskId)}/queue/remove`, {
          method: 'POST',
          headers: headers(),
          body: JSON.stringify({ player_id: Number(currentPlayerId) })
        });
        const data = await resp.json().catch(() => ({}));
        if (resp.ok && data && data.ok !== false) {
          if (statusEl) {
            const nameText = leavingName || 'Player';
            statusEl.classList.remove('fade-out');
            statusEl.textContent = `${nameText} has left the game.`;
            setTimeout(() => {
              statusEl.classList.add('fade-out');
            }, 2500);
          }
          if (window.refreshQueue) {
            window.refreshQueue();
          }
          if (window.refreshStatus) {
            window.refreshStatus();
          }
        } else if (statusEl) {
          statusEl.textContent = (data && data.detail) || 'Could not leave queue.';
        }
      } catch (err) {
        console.error('Failed to remove player from queue', err);
        if (statusEl) {
          statusEl.textContent = 'Error while leaving queue.';
        }
      } finally {
        closeOverlay();
      }
    });
  }

  if (editBtn && editOverlay) {
    editBtn.addEventListener('click', (e) => {
      e.preventDefault();
      openEditOverlay();
    });
  }
  if (editCloseBtn && editOverlay) {
    editCloseBtn.addEventListener('click', (e) => {
      e.preventDefault();
      closeEditOverlay();
    });
  }
  if (editOverlay) {
    editOverlay.addEventListener('click', (e) => {
      if (e.target === editOverlay) {
        closeEditOverlay();
      }
    });
  }

  if (editRandomBtn) {
    editRandomBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      if (!currentPlayerId) return;
      editMsgEl.textContent = 'Picking a new avatar…';
      try {
        const resp = await fetch(`/players/${encodeURIComponent(currentPlayerId)}`, {
          method: 'PATCH',
          headers: headers(),
          body: JSON.stringify({ random_avatar: true })
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) {
          editMsgEl.textContent = (data && data.detail) || 'Failed to update avatar.';
          return;
        }
        editAvatarImg.src = data.avatar_url || '/static/avatars/default.png';
        editMsgEl.textContent = 'Avatar updated!';
        if (window.refreshQueue) {
          window.refreshQueue();
        }
      } catch (err) {
        console.error('Failed to randomize avatar', err);
        editMsgEl.textContent = 'Error updating avatar.';
      }
    });
  }

  if (editSaveBtn) {
    editSaveBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      if (!currentPlayerId) return;
      const newName = (editNameInput.value || '').trim();
      if (!newName) {
        editMsgEl.textContent = 'Name cannot be empty.';
        return;
      }
      editMsgEl.textContent = 'Saving…';
      try {
        const resp = await fetch(`/players/${encodeURIComponent(currentPlayerId)}`, {
          method: 'PATCH',
          headers: headers(),
          body: JSON.stringify({ name: newName })
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok) {
          editMsgEl.textContent = (data && data.detail) || 'Failed to update username.';
          return;
        }
        // Update the history title with the new username
        if (titleEl) {
          titleEl.textContent = `${data.username} — Game History`;
        }
        editMsgEl.textContent = 'Profile updated!';
        if (window.refreshQueue) {
          window.refreshQueue();
        }
        setTimeout(() => {
          closeEditOverlay();
        }, 600);
      } catch (err) {
        console.error('Failed to update username', err);
        editMsgEl.textContent = 'Error updating username.';
      }
    });
  }

  // Any time a player slot in the queue is tapped, open their profile.
  const queueListEl = document.getElementById('queueList');
  if (queueListEl) {
    queueListEl.addEventListener('click', (e)=>{
      const li = e.target.closest('li[data-player-id]');
      if (!li) return;
      const pid = li.dataset.playerId;
      const name = li.dataset.username || '';
      if (pid) {
        openProfileOverlay(pid, name);
      }
    });
  }
})();


// Objectives overlay
(function () {
  const overlay = document.getElementById('objectivesOverlay');
  const closeBtn = document.getElementById('objectivesClose');
  const listEl = document.getElementById('objectivesList');
  const btn = document.getElementById('objectivesBtn');

  if (!overlay || !listEl || !btn) {
    return;
  }

  function closeOverlay() {
    overlay.classList.add('hidden');
    overlay.setAttribute('aria-hidden', 'true');
  }

  function openOverlay() {
    const items = Array.isArray(window.KIOSK_OBJECTIVES) ? window.KIOSK_OBJECTIVES : [];
    listEl.innerHTML = '';
    if (!items.length) {
      const li = document.createElement('li');
      li.textContent = 'No objectives configured yet.';
      listEl.appendChild(li);
    } else {
      items.forEach((text) => {
        const li = document.createElement('li');
        li.textContent = text;
        listEl.appendChild(li);
      });
    }
    overlay.classList.remove('hidden');
    overlay.setAttribute('aria-hidden', 'false');
  }

  btn.addEventListener('click', (e) => {
    e.preventDefault();
    openOverlay();
  });
  if (closeBtn) {
    closeBtn.addEventListener('click', (e) => {
      e.preventDefault();
      closeOverlay();
    });
  }
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) {
      closeOverlay();
    }
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !overlay.classList.contains('hidden')) {
      closeOverlay();
    }
  });
})();

// Physical / Mental / Skill overlay
(function () {
  const overlay = document.getElementById('traitOverlay');
  const closeBtn = document.getElementById('traitClose');
  const titleEl = document.getElementById('traitTitle');
  const descEl = document.getElementById('traitDescription');
  const levelEl = document.getElementById('traitLevel');
  const iconsRow = document.querySelector('.kt-icons');

  if (!overlay || !titleEl || !descEl || !levelEl || !iconsRow) {
    return;
  }

  const TRAIT_CONFIG = {
    physical: {
      label: 'Physical',
      description: 'Requires physically moving, climbing, jumping, or avoiding obstacles.'
    },
    mental: {
      label: 'Mental',
      description: 'Requires problem solving skills, critical thinking, and/or communication skills.'
    },
    skill: {
      label: 'Skill',
      description: 'May require a level of special skill or ability.'
    }
  };

  function closeOverlay() {
    overlay.classList.add('hidden');
    overlay.setAttribute('aria-hidden', 'true');
  }

  function openOverlay(key) {
    const cfg = TRAIT_CONFIG[key];
    if (!cfg) return;

    const traits = window.KIOSK_TRAITS || {};
    const level = Number(traits[key] || 0);
    titleEl.textContent = `${cfg.label}:`;
    descEl.textContent = cfg.description;

    const clamped = Math.max(0, Math.min(level, 5));
    if (clamped > 0) {
      const dots = Array.from({ length: 5 }, (_, i) => i < clamped ? '●' : '○').join('');
      levelEl.innerHTML = `<span class="dots">${dots}</span><span>${clamped} / 5</span>`;
    } else {
      levelEl.textContent = 'Level not configured yet.';
    }

    overlay.classList.remove('hidden');
    overlay.setAttribute('aria-hidden', 'false');
  }

  iconsRow.addEventListener('click', (e) => {
    const btn = e.target.closest('.kt-icon[data-trait]');
    if (!btn) return;
    const key = btn.getAttribute('data-trait');
    openOverlay(key);
  });

  if (closeBtn) {
    closeBtn.addEventListener('click', (e) => {
      e.preventDefault();
      closeOverlay();
    });
  }
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) {
      closeOverlay();
    }
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !overlay.classList.contains('hidden')) {
      closeOverlay();
    }
  });
})();

// Wait text (demo) — could be wired to /games/ready or a polling endpoint
const waitEl = document.getElementById('waitMins');
if (waitEl) {
  // Placeholder: show READY; when a game is running, we can change to "IN PLAY"
  function updateWait(status){
    if (status === 'running') { waitEl.textContent = 'IN PLAY'; }
    else { waitEl.textContent = 'READY'; }
  }
  // Integrate with status refresh (only if available in this scope)
  if (typeof refreshStatus === 'function') {
    const _origRefreshStatus = refreshStatus;
    // Re-assign on window so the kiosk script can call the wrapped version,
    // regardless of where refreshStatus was originally declared.
    window.refreshStatus = async function(){
      await _origRefreshStatus();
      const resp = await fetch(`/kiosks/${encodeURIComponent(kioskId)}/status`);
      if(resp.ok){
        const data = await resp.json();
        updateWait(data.status);
      }
    }
  }
}
