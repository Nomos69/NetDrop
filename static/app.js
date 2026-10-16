const $ = (id) => document.getElementById(id);
let activeRoom = null;
let maxUploadBytes = 0;
let liveSocket = null;
let reconnectTimer = null;
let heartbeatTimer = null;
let reconnectDelay = 1000;
let refreshNumber = 0;

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
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const socket = new WebSocket(`${protocol}//${location.host}/api/rooms/${room.id}/live`);
  liveSocket = socket;
  socket.onmessage = async (event) => {
    if (socket !== liveSocket || activeRoom !== room) return;
    clearTimeout(heartbeatTimer);
    heartbeatTimer = setTimeout(() => socket.close(), 25000);
    const message = JSON.parse(event.data);
    if (message.type === 'ready' || message.type === 'changed') {
      try {
        await refresh();
        if (socket !== liveSocket) return;
        reconnectDelay = 1000;
        $('live-status').textContent = 'Live updates connected';
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
  $('status').textContent = message;
  $('status').classList.toggle('error', error);
}

async function api(path, options = {}) {
  const response = await fetch(`/api${path}`, {
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
  const buttons = [...document.querySelectorAll("button")];
  buttons.forEach((control) => { control.disabled = true; });
  try { await action(); } catch (error) { status(error.message, true); }
  finally { buttons.forEach((control) => { control.disabled = false; }); }
}

function showRoom(room) {
  stopLive();
  refreshNumber += 1;
  activeRoom = room;
  $('lobby').hidden = Boolean(room);
  $('room').hidden = !room;
  if (room) {
    $('active-name').textContent = room.name;
    $('active-id').textContent = room.id;
    sessionStorage.setItem('netdrop-room', room.id);
    reconnectDelay = 1000;
    connectLive();
  } else {
    sessionStorage.removeItem('netdrop-room');
    $('items').replaceChildren();
  }
}

async function refresh() {
  const room = activeRoom;
  if (!room) return;
  const number = ++refreshNumber;
  const data = await api(`/rooms/${room.id}/items`);
  if (activeRoom !== room || number !== refreshNumber) return;
  maxUploadBytes = data.max_upload_bytes;
  $('upload-limit').textContent = `Maximum file size: ${maxUploadBytes / 1024 / 1024} MiB. Shared items expire after ${data.ttl_seconds / 60} minutes.`;
  $('items').replaceChildren();
  if (!data.items.length) {
    const item = document.createElement('li');
    item.textContent = 'Nothing shared yet. Add the first file, note, or link.';
    $('items').append(item);
  }
  for (const item of data.items) {
    const row = document.createElement('li');
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
    details.textContent = `${item.kind}${item.kind === 'file' ? ` · ${item.size.toLocaleString()} bytes` : ''} · ${new Date(item.created_at).toLocaleString()} · Expires ${new Date(item.expires_at * 1000).toLocaleTimeString()}`;
    row.append(label, details);
    $('items').append(row);
  }
}

// Normalize copied input before validation so spaces cannot block submission.
function validateRoomForm(action) {
  const pin = $(`${action}-pin`);
  pin.value = pin.value.trim();
  pin.setCustomValidity(/^[0-9]{6,12}$/.test(pin.value) ? '' : 'Enter a PIN containing 6 to 12 digits (0–9).');
  if (action === 'join') {
    const id = $('room-id');
    id.value = id.value.replace(/\s/g, '').toLowerCase();
    id.setCustomValidity(/^[a-f0-9]{12}$/.test(id.value) ? '' : 'Enter the 12-character room ID shown on the host: only 0–9 and a–f. Do not enter the room name.');
  }
  return $(`${action}-form`).reportValidity();
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
      const body = { pin: $(`${action}-pin`).value };
      if (action === 'create') body.name = $('room-name').value.trim();
      const room = await api(path, json(body));
      $(`${action}-pin`).value = '';
      showRoom(room);
      await refresh();
      status(`Joined ${room.name}.`);
    });
  });
}

$('upload-form').addEventListener('submit', (event) => {
  event.preventDefault();
  perform(event.submitter, async () => {
    const file = $('file').files[0];
    if (!file) throw new Error('Choose a file first.');
    if (file.size > maxUploadBytes) throw new Error('File exceeds the upload limit.');
    status('Uploading file…');
    await api(`/rooms/${activeRoom.id}/files`, {
      method: 'POST', headers: { 'Content-Type': 'application/octet-stream', 'X-Filename': encodeURIComponent(file.name) }, body: file,
    });
    $('upload-form').reset();
    await refresh();
    status('File shared.');
  });
});

$('content-form').addEventListener('submit', (event) => {
  event.preventDefault();
  perform(event.submitter, async () => {
    await api(`/rooms/${activeRoom.id}/items`, json({ kind: $('kind').value, content: $('content').value }));
    $('content').value = '';
    await refresh();
    status('Content shared.');
  });
});

$('refresh').addEventListener('click', (event) => perform(event.currentTarget, async () => {
  await refresh(); status('Content refreshed.');
}));
$('leave').addEventListener('click', (event) => perform(event.currentTarget, async () => {
  await api(`/rooms/${activeRoom.id}/leave`, { method: 'POST' });
  showRoom(null); status('Left room.');
}));

(async () => {
  const id = sessionStorage.getItem('netdrop-room');
  if (!id) return;
  try { showRoom(await api(`/rooms/${id}`)); await refresh(); }
  catch (error) { showRoom(null); status('Join your room again to continue.', true); }
})();
