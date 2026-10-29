const $ = (id) => document.getElementById(id);
let activeRoom = null;
let maxUploadBytes = 0;
let liveSocket = null;
let reconnectTimer = null;
let heartbeatTimer = null;
let reconnectDelay = 1000;
let refreshNumber = 0;
// Keep navigation available even if an older server lacks /api/sharing.
function browserMode() {
  const host = location.hostname;
  const privateHost = host === 'localhost' || host.endsWith('.local') || host.endsWith('.lan')
    || host.endsWith('.localhost') || host === '[::1]'
    || /^(127\.|10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.)/.test(host);
  return location.protocol === 'https:' && !privateHost ? 'online' : 'local';
}
let sharingConfig = { mode: browserMode(), local_url: '', online_url: '' };
let selectedMode = sharingConfig.mode;
let modeChosen = false;
let settingsFailed = false;
let busy = false;

function setRoomAction(action) {
  for (const choice of ['join', 'create']) {
    $(`${choice}-form`).hidden = choice !== action;
    $(`action-${choice}`).setAttribute('aria-pressed', String(choice === action));
  }
}
for (const action of ['join', 'create']) {
  $(`action-${action}`).addEventListener('click', () => setRoomAction(action));
}

function updateMode() {
  const current = selectedMode === sharingConfig.mode;
  for (const mode of ['local', 'online']) {
    $(`mode-${mode}`).setAttribute('aria-pressed', String(selectedMode === mode));
    $(`mode-${mode}`).disabled = busy;
  }
  $('mode-badge').textContent = sharingConfig.mode === 'local' ? 'LOCAL NETWORK' : 'ONLINE';
  $('server-form').hidden = current;
  $('lobby').hidden = Boolean(activeRoom) || !current;
  $('retry-settings').hidden = !settingsFailed;
  $('mode-help').textContent = current
    ? (selectedMode === 'local' ? 'Share on the same Wi-Fi or LAN. No internet needed.' : 'Share across different networks through this HTTPS server.')
    : (selectedMode === 'online' ? 'Connect to an online host using its HTTPS address or invitation link.' : 'Connect to the host’s local address while on the same Wi-Fi or LAN.');
  $('server-label').textContent = selectedMode === 'online' ? 'Or paste invite link' : 'Local host or invite link';
  $('server-help').textContent = selectedMode === 'online'
    ? 'Paste the host’s HTTPS server address or room invitation link. Internet required.'
    : 'Use the host’s LAN address, for example http://192.168.1.12:8000.';
  $('switch-mode').textContent = `Connect to ${selectedMode === 'online' ? 'online' : 'local'} server`;
  $('connection-caption').textContent = selectedMode === 'online' ? 'CONNECT VIA AN HTTPS HOST' : 'DEVICES MUST BE ON THE SAME NETWORK';
}

for (const mode of ['local', 'online']) {
  $(`mode-${mode}`).addEventListener('click', () => {
    modeChosen = true;
    selectedMode = mode;
    $('server-link').value = sharingConfig[`${mode}_url`] || '';
    $('server-link').setCustomValidity('');
    updateMode();
  });
}
$('server-link').addEventListener('input', () => $('server-link').setCustomValidity(''));
$('server-form').addEventListener('submit', (event) => {
  event.preventDefault();
  const input = $('server-link');
  try {
    const target = new URL(input.value.trim());
    if (!['http:', 'https:'].includes(target.protocol) || target.username || target.password
        || target.pathname !== '/' || target.search || (selectedMode === 'online' && target.protocol !== 'https:')) {
      throw new Error('Invalid server link');
    }
    location.assign(target.href);
  } catch (error) {
    input.setCustomValidity(selectedMode === 'online'
      ? 'Enter a complete HTTPS server address or invitation link, such as https://your-host.example/#room=…'
      : 'Enter a complete local host address, such as http://192.168.1.12:8000.');
    input.reportValidity();
  }
});

async function loadSharingSettings() {
  try {
    const data = await api('/sharing');
    if (!['local', 'online'].includes(data.mode)) throw new Error('Invalid settings');
    sharingConfig = data;
    if (!modeChosen) selectedMode = data.mode;
    if (!$('server-link').value) $('server-link').value = data[`${selectedMode}_url`] || '';
    settingsFailed = false;
    status('');
  } catch (error) {
    settingsFailed = true;
    status('Connection settings are unavailable. You can still choose a mode and paste the host’s invite link. Restart or update the server, then retry.', true);
  }
  updateMode();
}
$('retry-settings').addEventListener('click', loadSharingSettings);

function showInvitation(room) {
  const base = sharingConfig[`${room.mode}_url`] || location.origin;
  const link = new URL(base);
  // A fragment keeps the room ID out of server access logs. PINs are never included.
  link.hash = `room=${room.id}`;
  $('invite-link').value = link.href;
  $('room-mode').textContent = room.mode === 'online'
    ? 'Online room · Internet required · Share with people on any network.'
    : 'Local room · Participants must be on the same Wi-Fi / LAN.';
  const loopback = ['localhost', '127.0.0.1', '[::1]'].includes(link.hostname);
  $('invite-help').textContent = loopback
    ? `This address works only on this computer. Configure ${room.mode === 'online' ? 'the public HTTPS address' : 'the host’s LAN address'} before sharing the link with another device. Share the PIN separately.`
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
    if (message.type === 'heartbeat') {
      try { await refreshMembers(room); } catch (error) { /* Retry on the next update. */ }
    }
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
  const buttons = [...document.querySelectorAll("button")];
  buttons.forEach((control) => { control.disabled = true; });
  try { await action(); } catch (error) { status(error.message, true); }
  finally {
    buttons.forEach((control) => { control.disabled = false; });
    busy = false;
    updateMode();
  }
}

function showRoom(room) {
  stopLive();
  refreshNumber += 1;
  activeRoom = room;
  $('auth-shell').hidden = Boolean(room);
  document.body.classList.toggle('in-room', Boolean(room));
  $('room').hidden = !room;
  if (room) {
    $('active-name').textContent = room.name;
    $('active-id').textContent = room.id;
    showInvitation(room);
    $('sharing-options').hidden = true;
    sessionStorage.setItem('netdrop-room', room.id);
    reconnectDelay = 1000;
    connectLive();
  } else {
    $('sharing-options').hidden = false;
    sessionStorage.removeItem('netdrop-room');
    $('items').replaceChildren();
    $('members').replaceChildren();
    $('member-count').textContent = '';
    updateMode();
  }
}

async function refresh() {
  const room = activeRoom;
  if (!room) return;
  const number = ++refreshNumber;
  const [data] = await Promise.all([api(`/rooms/${room.id}/items`), refreshMembers(room)]);
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

let memberRefreshNumber = 0;

async function refreshMembers(room) {
  const number = ++memberRefreshNumber;
  const data = await api(`/rooms/${room.id}/members`);
  if (activeRoom !== room || number !== memberRefreshNumber) return;
  const online = data.members.filter((member) => member.online).length;
  $('member-count').textContent = `${data.members.length} joined · ${online} online`;
  $('members').replaceChildren();
  for (const member of data.members) {
    const row = document.createElement('li');
    row.className = 'member';
    const dot = document.createElement('span');
    dot.className = `presence-dot${member.online ? ' online' : ''}`;
    dot.setAttribute('aria-hidden', 'true');
    const name = document.createElement('span');
    name.className = 'member-name';
    name.textContent = `${member.name}${member.is_you ? ' (You)' : ''}`;
    const state = document.createElement('span');
    state.className = 'member-state';
    state.textContent = member.online ? 'Online' : 'Offline';
    row.append(dot, name, state);
    $('members').append(row);
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
    if (selectedMode !== sharingConfig.mode) {
      status('Open the selected sharing server first.', true);
      return;
    }
    if (!validateRoomForm(action)) return;
    perform(event.submitter, async () => {
      const path = action === 'create' ? '/rooms' : `/rooms/${$('room-id').value.trim().toLowerCase()}/join`;
      const body = { pin: $(`${action}-pin`).value, display_name: $(`${action}-display-name`).value.trim() };
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

updateMode();
(async () => {
  await loadSharingSettings();
  const invitation = new URLSearchParams(location.hash.slice(1)).get('room');
  if (invitation && /^[a-f0-9]{12}$/.test(invitation)) {
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
