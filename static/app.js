const $ = (id) => document.getElementById(id);
let activeRoom = null;
let maxUploadBytes = 0;
let fileTtlSeconds = 1800;
let liveSocket = null;
let reconnectTimer = null;
let heartbeatTimer = null;
let reconnectDelay = 1000;
let refreshNumber = 0;
let busy = false;
let feedItems = [];
let feedPage = 1;
let filteredItems = [];
let statusTimer;
let statusSequence = 0;
const FEED_PAGE_SIZE = 6;

function setRoomAction(action) {
  document.querySelector('.action-tabs').dataset.action = action;
  for (const choice of ['join', 'create']) {
    $(`${choice}-form`).hidden = choice !== action;
    $(`action-${choice}`).setAttribute('aria-pressed', String(choice === action));
  }
}
for (const action of ['join', 'create']) {
  $(`action-${action}`).addEventListener('click', () => {
    setRoomAction(action);
    $(action === 'create' ? 'room-name' : 'room-id').focus();
  });
}

function showLocalSharing(open) {
  $('online-lobby').hidden = open;
  $('local-sharing').hidden = !open;
  $('lobby').setAttribute('aria-label', open ? 'Local Sharing' : 'Connect to NetDrop');
  if (open) $('lobby').removeAttribute('aria-labelledby');
  else $('lobby').setAttribute('aria-labelledby', 'entry-title');
  if (open) {
    history.replaceState(null, '', '#local-sharing');
    $('local-sharing').querySelector('button')?.focus();
  } else if (location.hash === '#local-sharing') {
    history.replaceState(null, '', location.pathname + location.search);
    $('local-sharing-link').focus();
  }
}

$('local-sharing-link').addEventListener('click', () => showLocalSharing(true));
window.addEventListener('hashchange', () => showLocalSharing(location.hash === '#local-sharing'));
if (location.hash === '#local-sharing') showLocalSharing(true);

function showInvitation(room) {
  $('email-invitation').hidden = !room.is_owner;
  $('email-invitation').reset();
  $('email-result').textContent = '';
  const link = new URL(location.origin);
  // A fragment keeps the room ID out of server access logs. PINs are never included.
  link.hash = `room=${room.id}`;
  $('invite-link').value = link.href;
  $('invite-qr').src = `/api/rooms/${room.id}/invitation.svg`;
  $('qr-invite').open = false;
  $('room-mode').textContent = 'Online room · Internet required · Share with people on any network.';
  const loopback = ['localhost', '127.0.0.1', '[::1]'].includes(link.hostname);
  $('invite-help').textContent = loopback
    ? 'This address works only on this computer. Configure the public HTTPS address before sharing the link with another device. Share the PIN separately.'
    : 'Share the PIN separately. Opening this link still requires the room PIN.';
}

$('copy-invite').addEventListener('click', async () => {
  try {
    if (!navigator.clipboard) throw new Error('Clipboard unavailable');
    await navigator.clipboard.writeText($('invite-link').value);
    status('Invitation link copied. Share the PIN separately.');
  } catch (error) {
    $('invite-link').focus();
    $('invite-link').select();
    status('Select and copy the invitation link above.');
  }
});

$('email-invitation').addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!activeRoom?.is_owner) return;
  const button = event.currentTarget.querySelector('button');
  button.disabled = true;
  $('email-result').textContent = 'Sending invitation…';
  try {
    const result = await api(`/rooms/${activeRoom.id}/email-invitation`, {
      ...json({ email: $('invite-email').value.trim() }),
      signal: AbortSignal.timeout(25000),
    });
    $('email-result').textContent = result.message;
  } catch (error) {
    $('email-result').textContent = error.name === 'TimeoutError'
      ? 'Email acceptance is unknown. Check the inbox before trying again.' : error.message;
  } finally {
    button.disabled = false;
  }
});

$('upload-alerts').addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!activeRoom) return;
  try {
    const result = await api(`/rooms/${activeRoom.id}/subscriptions`, json({ email: $('alert-email').value.trim(), enabled: true }));
    $('alert-result').textContent = result.message;
  } catch (error) { $('alert-result').textContent = error.message; }
});
$('disable-alerts').addEventListener('click', async () => {
  if (!activeRoom || !$('alert-email').value.trim()) return;
  try {
    const result = await api(`/rooms/${activeRoom.id}/subscriptions`, json({ email: $('alert-email').value.trim(), enabled: false }));
    $('alert-result').textContent = result.message;
  } catch (error) { $('alert-result').textContent = error.message; }
});

function stopLive() {
  clearTimeout(reconnectTimer);
  clearTimeout(heartbeatTimer);
  if (liveSocket) {
    const previous = liveSocket;
    liveSocket = null;
    previous.close();
  }
}

function connectLive() {
  if (!activeRoom) return;
  stopLive();
  const room = activeRoom;
  $('live-status').textContent = 'Connecting to live updates…';
  $('live-status').dataset.state = 'connecting';
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const socket = new WebSocket(`${protocol}//${location.host}/api/rooms/${room.id}/live`);
  liveSocket = socket;
  socket.onmessage = async (event) => {
    if (socket !== liveSocket || activeRoom !== room) return;
    clearTimeout(heartbeatTimer);
    heartbeatTimer = setTimeout(() => socket.close(), 25000);
    const message = JSON.parse(event.data);
    if (message.type === 'heartbeat') {
      try { await refreshMembers(room); } catch (error) { /* Retry on the next update. */ }
    }
    if (message.type === 'ready' || message.type === 'changed') {
      try {
        await refresh();
        if (socket !== liveSocket) return;
        reconnectDelay = 1000;
        $('live-status').textContent = 'Live updates connected';
        $('live-status').dataset.state = 'connected';
      } catch (error) {
        if (socket === liveSocket) socket.close();
      }
    }
  };
  socket.onclose = async (event) => {
    if (socket !== liveSocket || activeRoom !== room) return;
    clearTimeout(heartbeatTimer);
    if (event.code === 1008) {
      showRoom(null);
      status('Room access ended. Join again to continue.', true);
      return;
    }
    $('live-status').textContent = 'Connection lost. Reconnecting…';
    $('live-status').dataset.state = 'reconnecting';
    try { await api(`/rooms/${room.id}`); }
    catch (error) {
      if (activeRoom !== room || socket !== liveSocket) return;
      if (error.status === 403 || error.status === 404) {
        showRoom(null);
        status('Room access ended. The host may have restarted.', true);
        return;
      }
    }
    if (activeRoom !== room || socket !== liveSocket) return;
    reconnectTimer = setTimeout(connectLive, reconnectDelay);
    reconnectDelay = Math.min(reconnectDelay * 2, 10000);
  };
}

window.addEventListener('online', () => { if (activeRoom) connectLive(); });
document.addEventListener('visibilitychange', () => {
  if (!document.hidden && activeRoom) connectLive();
});

function status(message, error = false) {
  const sequence = ++statusSequence;
  clearTimeout(statusTimer);
  $('status').textContent = message;
  $('status').classList.toggle('error', error);
  $('status').getAnimations().forEach(animation => animation.cancel());
  if (message) motion($('status'), [{opacity:0, translate:'0 8px'}, {opacity:1, translate:'0 0'}]);
  if (message && !error) statusTimer = setTimeout(async () => {
    await motion($('status'), [{opacity:1}, {opacity:0, translate:'0 6px'}]);
    if (sequence === statusSequence) $('status').textContent = '';
  }, 6000);
}

async function api(path, options = {}) {
  const response = await fetch(`/api${path}`, {
    signal: AbortSignal.timeout(10000),
    cache: 'no-store',
    ...options,
    headers: { 'X-NetDrop': '1', ...options.headers },
  });
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(typeof data.detail === 'string' ? data.detail : 'Check the entered values and try again.');
    error.status = response.status;
    throw error;
  }
  return data;
}

function json(body) {
  return { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
}

async function perform(button, action) {
  busy = true;
  const buttons = [...document.querySelectorAll("button:not(.upload-control)")];
  buttons.forEach((control) => { control.disabled = true; });
  try { await action(); } catch (error) { status(error.message, true); }
  finally {
    buttons.forEach((control) => { control.disabled = false; });
    busy = false;
    if (activeRoom) updatePagination();
  }
}

function showRoom(room) {
  stopLive();
  refreshNumber += 1;
  if (activeRoom && (!room || activeRoom.id !== room.id)) clearUploads();
  activeRoom = room;
  feedPage = 1;
  feedItems = [];
  filteredItems = [];
  $('feed-search').value = '';
  $('feed-filter').value = 'all';
  document.querySelectorAll('dialog[open]').forEach(dialog => dialog.close());
  $('close-room').hidden = !room?.is_owner;
  $('auth-shell').hidden = Boolean(room);
  document.body.classList.toggle('in-room', Boolean(room));
  $('room').hidden = !room;
  if (room) {
    $('active-name').textContent = room.name;
    $('active-id').textContent = room.id;
    $('room-mode').dataset.expires = room.expires_at;
    showInvitation(room);
    sessionStorage.setItem('netdrop-room', room.id);
    reconnectDelay = 1000;
    connectLive();
    $('items').innerHTML = '<li class="skeleton" aria-label="Loading shared content"></li><li class="skeleton" aria-hidden="true"></li>';
  } else {
    sessionStorage.removeItem('netdrop-room');
    $('items').replaceChildren();
    $('members').replaceChildren();
    $('member-count').textContent = '';
  }
}

async function refresh() {
  const room = activeRoom;
  if (!room) return;
  const number = ++refreshNumber;
  const [data] = await Promise.all([api(`/rooms/${room.id}/items`), refreshMembers(room)]);
  if (activeRoom !== room || number !== refreshNumber) return;
  maxUploadBytes = data.max_upload_bytes;
  fileTtlSeconds = data.ttl_seconds;
  $('upload-limit').textContent = `Up to ${formatBytes(maxUploadBytes)} per file · Files expire after ${data.ttl_seconds / 60} minutes.`;
  feedItems = data.items;
  const pageCount = Math.max(1, Math.ceil(feedItems.length / FEED_PAGE_SIZE));
  feedPage = Math.min(feedPage, pageCount);
  renderFeed(room);
}

function renderFeed(room) {
  const search = $('feed-search').value.trim().toLowerCase();
  const filter = $('feed-filter').value;
  filteredItems = feedItems.filter(item => (filter === 'all' || item.kind === filter) && (item.name || item.content || '').toLowerCase().includes(search));
  feedPage = Math.min(feedPage, Math.max(1, Math.ceil(filteredItems.length / FEED_PAGE_SIZE)));
  const list = $('items');
  const previousIds = new Set([...list.children].map(row => row.dataset.id));
  list.replaceChildren();
  if (!filteredItems.length) {
    const item = document.createElement('li');
    item.className = 'empty-feed';
    item.append(icon('file'));
    const title = document.createElement('strong');
    title.textContent = feedItems.length ? 'No matches in this space' : 'A fresh space for your next idea.';
    const hint = document.createElement('p');
    hint.textContent = feedItems.length ? 'Try another search or choose a different content type.' : 'Drop a file or share a note. It will appear here for everyone.';
    item.append(title, hint);
    list.append(item);
  }
  const start = (feedPage - 1) * FEED_PAGE_SIZE;
  for (const item of filteredItems.slice(start, start + FEED_PAGE_SIZE)) {
    const row = document.createElement('li');
    row.className = 'feed-item';
    row.dataset.id = item.id;
    if (previousIds.has(item.id)) row.style.animation = 'none';
    const typeIcon = document.createElement('span');
    typeIcon.className = `content-icon ${item.kind}`;
    typeIcon.append(icon(item.kind));
    const body = document.createElement('div');
    body.className = 'feed-item-body';
    const label = document.createElement(item.kind === 'text' ? 'p' : 'a');
    label.textContent = item.kind === 'file' ? item.name : item.content;
    if (item.kind === 'file') {
      label.href = `/api/rooms/${room.id}/files/${item.id}`;
      label.download = item.name;
    } else if (item.kind === 'link') {
      label.href = item.content;
      label.target = '_blank';
      label.rel = 'noopener noreferrer';
    }
    const details = document.createElement('small');
    details.textContent = `${item.kind === 'text' ? 'Note' : item.kind === 'file' ? formatBytes(item.size) : 'Link'} · ${new Date(item.created_at).toLocaleString()}${item.kind === 'file' ? '' : ' · Until room closes'}`;
    body.append(label, details);
    row.append(typeIcon, body);
    if (item.kind === 'file') {
      const timer = document.createElement('div');
      timer.className = 'file-timer';
      timer.dataset.expires = item.expires_at;
      timer.dataset.duration = Math.max(1, item.expires_at - Date.parse(item.created_at) / 1000) || fileTtlSeconds;
      timer.setAttribute('role', 'timer');
      timer.setAttribute('aria-live', 'off');
      timer.setAttribute('aria-label', 'File expiration countdown');
      timer.innerHTML = '<svg viewBox="0 0 42 42" aria-hidden="true"><circle class="timer-track" cx="21" cy="21" r="17"></circle><circle class="timer-progress" cx="21" cy="21" r="17"></circle></svg><span class="timer-value"></span><small class="timer-label">left</small>';
      row.append(timer);
    }
    if (item.kind !== 'file') {
      const copy = document.createElement('button');
      copy.className = 'secondary';
      copy.setAttribute('aria-label', `Copy ${item.kind === 'text' ? 'note' : 'link'}`);
      copy.append(icon('copy'));
      copy.onclick = () => copyText(item.content, 'Copied to clipboard.', copy);
      row.append(copy);
    } else {
      const download = document.createElement('a');
      download.href = label.href;
      download.download = item.name;
      download.className = 'download-action';
      download.setAttribute('aria-label', `Download ${item.name}`);
      download.append(icon('download'));
      row.append(download);
    }
    if (room.is_owner) {
      const remove = document.createElement('button');
      remove.className = 'secondary';
      remove.textContent = 'Delete';
      remove.setAttribute('aria-label', `Delete ${item.kind === 'file' ? item.name : item.kind}`);
      remove.onclick = () => {
        if (!confirm('Delete this shared item for everyone?')) return;
        perform(remove, async () => {
          await api(`/rooms/${room.id}/items/${item.id}`, {method: 'DELETE'});
          await refresh();
          status('Shared item deleted.');
        });
      };
      row.append(remove);
    }
    list.append(row);
  }
  updatePagination();
  updateCountdowns();
}

function updatePagination() {
  const pageCount = Math.max(1, Math.ceil(filteredItems.length / FEED_PAGE_SIZE));
  $('feed-pagination').hidden = filteredItems.length <= FEED_PAGE_SIZE;
  $('feed-page').textContent = `Page ${feedPage} of ${pageCount}`;
  $('feed-prev').disabled = feedPage === 1;
  $('feed-next').disabled = feedPage === pageCount;
}

let memberRefreshNumber = 0;

async function refreshMembers(room) {
  const number = ++memberRefreshNumber;
  const data = await api(`/rooms/${room.id}/members`);
  if (activeRoom !== room || number !== memberRefreshNumber) return;
  const online = data.members.filter((member) => member.online).length;
  $('member-count').textContent = `${data.members.length} joined · ${online} online`;
  const previousMembers = [...$('members').children];
  const existingMembers = new Set(previousMembers.map(row => row.dataset.member));
  $('members').replaceChildren();
  for (const member of data.members) {
    const row = document.createElement('li');
    row.className = 'member';
    row.dataset.member = member.id;
    if (existingMembers.has(member.id)) row.style.animation = 'none';
    const avatar = document.createElement('span');
    avatar.className = 'avatar';
    avatar.textContent = member.name.trim().slice(0, 2).toUpperCase();
    avatar.setAttribute('aria-hidden', 'true');
    const dot = document.createElement('span');
    dot.className = `presence-dot${member.online ? ' online' : ''}`;
    dot.setAttribute('aria-hidden', 'true');
    const name = document.createElement('span');
    name.className = 'member-name';
    name.textContent = `${member.name}${member.is_you ? ' (You)' : ''}`;
    const state = document.createElement('span');
    state.className = 'member-state';
    state.textContent = member.online ? 'Online' : 'Offline';
    row.append(avatar, dot, name, state);
    if (room.is_owner && !member.is_you) {
      const remove = document.createElement('button');
      remove.className = 'secondary';
      remove.textContent = 'Remove';
      remove.setAttribute('aria-label', `Remove ${member.name}`);
      remove.onclick = () => {
        if (!confirm(`Remove ${member.name}? They can rejoin using the PIN.`)) return;
        perform(remove, async () => {
          await api(`/rooms/${room.id}/members/${member.id}`, {method: 'DELETE'});
          await refreshMembers(room);
          status('Member removed.');
        });
      };
      row.append(remove);
    }
    $('members').append(row);
  }
  const currentIds = new Set(data.members.map(member => member.id));
  for (const row of previousMembers) {
    if (currentIds.has(row.dataset.member) || row.classList.contains('departing')) continue;
    row.classList.add('departing');
    row.setAttribute('aria-hidden', 'true');
    row.querySelectorAll('button').forEach(button => { button.disabled = true; });
    $('members').append(row);
    setTimeout(() => row.remove(), 180);
  }
}

// Normalize copied input before validation so spaces cannot block submission.
function validateRoomForm(action) {
  const pin = $(`${action}-pin`);
  pin.value = pin.value.trim();
  pin.setCustomValidity(/^[0-9]{4}$/.test(pin.value) ? '' : 'Enter a four-digit PIN (0–9).');
  if (action === 'join') {
    const id = $('room-id');
    id.value = id.value.replace(/\s/g, '').toLowerCase();
    id.setCustomValidity(/^[a-f0-9]{12}$/.test(id.value) ? '' : 'Enter the 12-character room ID shown on the host: only 0–9 and a–f. Do not enter the room name.');
  }
  return $(`${action}-form`).reportValidity();
}

// Render masked dots in actual grid cells; native password text can scroll
// independently without shifting the visible dots. The input keeps its label,
// validation, paste, autofill and keyboard editing behavior.
function renderPin(input) {
  const cells = input.nextElementSibling;
  const count = 4;
  cells.style.setProperty('--pin-slots', count);
  cells.replaceChildren();
  for (let index = 0; index < count; index += 1) {
    const cell = document.createElement('span');
    const filled = index < input.value.length;
    cell.className = `pin-cell${filled ? ' filled' : ''}${index === Math.min(input.selectionStart ?? 0, count - 1) ? ' active' : ''}`;
    cell.textContent = filled || !input.value ? '•' : '';
    cells.append(cell);
  }
}
for (const input of document.querySelectorAll('.pin-entry')) {
  for (const event of ['input', 'change', 'focus', 'keyup', 'select']) {
    input.addEventListener(event, () => renderPin(input));
  }
  input.addEventListener('click', (event) => {
    if (event.detail !== 1 || event.shiftKey || input.selectionStart !== input.selectionEnd) {
      renderPin(input);
      return;
    }
    const bounds = input.getBoundingClientRect();
    const count = 4;
    const position = Math.max(0, Math.min(input.value.length,
      Math.round((event.clientX - bounds.left) / bounds.width * count)));
    input.setSelectionRange(position, position);
    renderPin(input);
  });
  renderPin(input);
}

for (const id of ['room-id', 'join-pin', 'create-pin']) {
  $(id).addEventListener('input', () => $(id).setCustomValidity(''));
}

for (const action of ['create', 'join']) {
  $(`${action}-form`).addEventListener('submit', (event) => {
    event.preventDefault();
    if (!validateRoomForm(action)) return;
    perform(event.submitter, async () => {
      const path = action === 'create' ? '/rooms' : `/rooms/${$('room-id').value.trim().toLowerCase()}/join`;
      const body = { pin: $(`${action}-pin`).value, display_name: $(`${action}-display-name`).value.trim() };
      if (action === 'create') body.name = $('room-name').value.trim();
      const room = await api(path, json(body));
      $(`${action}-pin`).value = '';
      renderPin($(`${action}-pin`));
      showRoom(room);
      await refresh();
      status(`Joined ${room.name}.`);
    });
  });
}

// Upload sequentially so a batch does not flood the host or connection.
let uploads = [];
let uploadRunning = false;
function clearUploads() {
  const previous = uploads;
  uploads = [];
  for (const task of previous) {
    task.cancelled = true;
    task.xhr?.abort();
  }
  $('upload-queue').replaceChildren();
}
function updateCountdowns() {
  for (const timer of document.querySelectorAll('.file-timer')) {
    const seconds = Math.max(0, Math.ceil(Number(timer.dataset.expires) - Date.now() / 1000));
    const duration = Math.max(1, Number(timer.dataset.duration) || fileTtlSeconds);
    const progress = Math.min(1, seconds / duration);
    const ring = timer.querySelector('.timer-progress');
    ring.style.strokeDashoffset = String(107 * (1 - progress));
    timer.querySelector('.timer-value').textContent = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
    timer.querySelector('.timer-label').textContent = seconds ? 'left' : 'expired';
    timer.classList.toggle('warning', seconds > 0 && seconds <= Math.min(300, duration * .2));
    timer.classList.toggle('expired', seconds === 0);
    timer.setAttribute('aria-label', seconds ? `${seconds} seconds until this file expires` : 'This file has expired');
  }
  if (activeRoom?.expires_at) {
    const seconds = Math.max(0, Math.ceil(Number(activeRoom.expires_at) - Date.now() / 1000));
    $('room-mode').textContent = `Online room · Room expires in ${Math.floor(seconds / 86400)}d ${Math.floor(seconds % 86400 / 3600)}h`;
  }
}
setInterval(updateCountdowns, 1000);

function drawUpload(task) {
  task.message.closest('li').dataset.state = task.state;
  task.message.textContent = `${task.file.name} · ${task.state}`;
  if (task.state === 'Shared') { const check = icon('check'); check.classList.add('completion-check'); task.message.prepend(check); }
  task.progress.value = task.percent;
  task.cancel.hidden = !['Queued', 'Uploading', 'Saving…'].includes(task.state);
  task.retry.hidden = !task.retryable;
}
function sendUpload(task) {
  return new Promise((resolve) => {
    const xhr = new XMLHttpRequest();
    task.xhr = xhr;
    xhr.open('POST', `/api/rooms/${task.roomId}/files`);
    xhr.timeout = 30 * 60 * 1000;
    xhr.setRequestHeader('X-NetDrop', '1');
    xhr.setRequestHeader('X-Filename', encodeURIComponent(task.file.name));
    xhr.setRequestHeader('Content-Type', 'application/octet-stream');
    task.state = 'Uploading';
    drawUpload(task);
    xhr.upload.onprogress = (event) => {
      task.percent = event.lengthComputable ? Math.round(event.loaded / event.total * 100) : 0;
      task.state = task.percent === 100 ? 'Saving…' : 'Uploading';
      task.message.textContent = `${task.file.name} · ${task.percent}%${task.percent === 100 ? ' · Saving…' : ''}`;
      task.progress.value = task.percent;
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        task.state = 'Shared'; task.percent = 100;
      } else {
        let detail = 'Upload failed';
        try { detail = JSON.parse(xhr.responseText).detail || detail; } catch (error) { /* Non-JSON server error. */ }
        task.state = typeof detail === 'string' ? detail : 'Upload failed';
        task.retryable = true;
      }
      drawUpload(task); resolve();
    };
    const failed = (message) => { task.state = message; task.retryable = true; drawUpload(task); resolve(); };
    xhr.onerror = () => failed('Connection failed · check the feed before retrying');
    xhr.ontimeout = () => failed('Timed out · check the feed before retrying');
    xhr.onabort = () => failed('Cancelled · check the feed if sending had finished');
    xhr.send(task.file);
  });
}
async function runUploads() {
  if (uploadRunning) return;
  uploadRunning = true;
  try {
    let task;
    while ((task = uploads.find((entry) => entry.state === 'Queued'))) {
      if (!activeRoom || task.roomId !== activeRoom.id) break;
      await sendUpload(task);
      task.xhr = null;
      if (activeRoom?.id === task.roomId) {
        try { await refresh(); } catch (error) { status(error.message, true); }
      }
    }
  } finally {
    uploadRunning = false;
    // A room switch can enqueue a new batch while an aborted request settles.
    if (uploads.some((task) => task.state === 'Queued')) runUploads();
  }
}
$('upload-form').addEventListener('submit', (event) => {
  event.preventDefault();
  if (!activeRoom) return;
  for (const file of $('file').files) {
    const row = document.createElement('li');
    const message = document.createElement('span');
    message.setAttribute('role', 'status');
    const progress = document.createElement('progress');
    progress.max = 100;
    progress.setAttribute('aria-label', `Upload progress for ${file.name}`);
    const cancel = document.createElement('button');
    cancel.type = 'button'; cancel.className = 'secondary upload-control'; cancel.textContent = 'Cancel';
    const retry = document.createElement('button');
    retry.type = 'button'; retry.className = 'secondary upload-control'; retry.textContent = 'Retry';
    const task = {file, roomId: activeRoom.id, message, progress, cancel, retry, percent: 0,
      state: file.size > maxUploadBytes ? 'File exceeds the upload limit' : 'Queued'};
    cancel.onclick = () => {
      if (task.xhr) task.xhr.abort();
      else { task.state = 'Cancelled'; task.retryable = true; drawUpload(task); }
    };
    retry.onclick = () => {
      if (activeRoom?.id !== task.roomId) return;
      task.state = 'Queued'; task.percent = 0; task.retryable = false;
      drawUpload(task); runUploads();
    };
    row.append(message, progress, cancel, retry);
    $('upload-queue').append(row);
    uploads.push(task);
    drawUpload(task);
  }
  $('upload-form').reset();
  runUploads();
});

$('close-room').addEventListener('click', (event) => {
  if (!confirm('Close this room and delete all shared content? Existing downloads may finish.')) return;
  perform(event.currentTarget, async () => {
    await api(`/rooms/${activeRoom.id}`, {method: 'DELETE'});
    showRoom(null);
    status('Room closed.');
  });
});

$('content-form').addEventListener('submit', (event) => {
  event.preventDefault();
  perform(event.submitter, async () => {
    await api(`/rooms/${activeRoom.id}/items`, json({ kind: $('kind').value, content: $('content').value }));
    $('content').value = '';
    $('content').dispatchEvent(new Event('input'));
    await refresh();
    status('Content shared.');
  });
});

$('refresh').addEventListener('click', (event) => perform(event.currentTarget, async () => {
  await refresh(); status('Content refreshed.');
}));
$('feed-prev').addEventListener('click', () => {
  if (!activeRoom || feedPage === 1) return;
  feedPage -= 1;
  renderFeed(activeRoom);
});
$('feed-next').addEventListener('click', () => {
  const pageCount = Math.ceil(filteredItems.length / FEED_PAGE_SIZE);
  if (!activeRoom || feedPage >= pageCount) return;
  feedPage += 1;
  renderFeed(activeRoom);
});
$('leave').addEventListener('click', (event) => perform(event.currentTarget, async () => {
  if (!confirm('Leave this room? You can rejoin with the room ID and PIN.')) return;
  await api(`/rooms/${activeRoom.id}/leave`, { method: 'POST' });
  showRoom(null); status('Left room.');
}));

async function copyText(value, message, button) {
  try {
    await navigator.clipboard.writeText(value); status(message);
    if (button) {
      button.replaceChildren(icon('check')); button.classList.add('copy-confirmed');
      clearTimeout(button.copyTimer);
      button.copyTimer = setTimeout(() => { button.replaceChildren(icon('copy')); button.classList.remove('copy-confirmed'); }, 1800);
    }
  }
  catch (_) { status('Clipboard access is unavailable. Select the text and copy it manually.', true); }
}
$('copy-room-id').onclick = () => copyText(activeRoom.id, 'Room ID copied.', $('copy-room-id'));
for (const id of ['feed-search', 'feed-filter']) {
  $(id).addEventListener(id === 'feed-search' ? 'input' : 'change', () => {
    feedPage = 1;
    if (activeRoom) renderFeed(activeRoom);
  });
}
$('content').addEventListener('input', () => {
  const value = $('content').value;
  $('character-count').textContent = `${value.length.toLocaleString()} / 10,000 · Ctrl/⌘ + Enter`;
  if (/^https?:\/\/\S+$/i.test(value.trim())) $('kind').value = 'link';
  else if (!value) $('kind').value = 'text';
});
$('content').addEventListener('keydown', event => {
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter' && !busy) {
    event.preventDefault();
    $('content-form').requestSubmit();
  }
});
let previewUrls = [];
function showSelectedFiles() {
  previewUrls.forEach(url => URL.revokeObjectURL(url));
  previewUrls = [];
  $('upload-selection').replaceChildren();
  const files = [...$('file').files];
  for (const file of files.slice(0, 4)) {
    // Preview only locally selected raster images. Remote downloads trigger email
    // alerts, so do not fetch room files automatically for thumbnails.
    if (['image/png', 'image/jpeg', 'image/webp', 'image/gif'].includes(file.type)) {
      const img = document.createElement('img');
      img.src = URL.createObjectURL(file); previewUrls.push(img.src);
      img.alt = `Selected image: ${file.name}`;
      $('upload-selection').append(img);
    }
  }
  if (files.length) {
    const count = document.createElement('small');
    count.textContent = `${files.length} file${files.length === 1 ? '' : 's'} selected · ${formatBytes(files.reduce((sum, file) => sum + file.size, 0))}`;
    $('upload-selection').append(count);
  }
}
$('file').addEventListener('change', showSelectedFiles);
$('upload-form').addEventListener('reset', () => setTimeout(showSelectedFiles, 0));
for (const type of ['dragenter', 'dragover']) $('drop-zone').addEventListener(type, event => {
  event.preventDefault(); $('drop-zone').classList.add('dragging');
});
for (const type of ['dragleave', 'drop']) $('drop-zone').addEventListener(type, event => {
  event.preventDefault(); $('drop-zone').classList.remove('dragging');
});
$('drop-zone').addEventListener('drop', event => {
  if (event.dataTransfer.files.length) {
    $('file').files = event.dataTransfer.files;
    showSelectedFiles();
  }
});

(async () => {
  const parameters = new URLSearchParams(location.hash.slice(1));
  const invitation = parameters.get('room');
  const invitationToken = parameters.get('invite');
  if (invitation && /^[a-f0-9]{12}$/.test(invitation)) {
    if (invitationToken) {
      try { await api(`/rooms/${invitation}/validate-invitation`, json({ token: invitationToken })); }
      catch (error) { status(error.message, true); return; }
    }
    setRoomAction('join');
    $('room-id').value = invitation;
    history.replaceState(null, '', location.pathname + location.search);
    // An invitation takes priority over a previously visited room.
    status('Invitation opened. Enter the room PIN to join.');
    $('join-pin').focus();
    return;
  }
  const id = sessionStorage.getItem('netdrop-room');
  if (!id) return;
  try { showRoom(await api(`/rooms/${id}`)); await refresh(); }
  catch (error) { showRoom(null); status('Join your room again to continue.', true); }
})();
