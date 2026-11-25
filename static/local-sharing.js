// Replace this in-memory adapter with LAN API methods during backend integration.
// Nothing is transferred between devices by this default adapter.
(() => {
  const rooms = new Map();
  const api = window.netdropLocalAdapter || {
    async list() { return [...rooms.values()]; },
    async create(name, pin) { const room = {id:crypto.randomUUID().slice(0,8), name, pin, items:[]}; rooms.set(room.id, room); return room; },
    async join(id, pin) { const room = rooms.get(id); if (!room || room.pin !== pin) throw Error('Room not found or incorrect PIN.'); return room; },
    async items(id) { return rooms.get(id).items; },
    async add(id, item) { rooms.get(id).items.unshift({...item, id:crypto.randomUUID()}); },
    async remove(id, key) { const room = rooms.get(id); room.items = room.items.filter(item => item.id !== key); },
    async leave(id) {},
  };
  const root = document.getElementById('local-sharing');
  const el = id => root.querySelector('#' + id);
  let room;
  async function run(fn) {
    const buttons = [...root.querySelectorAll('button')]; buttons.forEach(b => b.disabled = true);
    try { await fn(); } catch (error) { el('local-feedback').textContent = error.message; }
    finally { buttons.forEach(b => b.disabled = false); }
  }
  async function render(view) {
    const screens = {
      home: `<h2>Nearby devices.<br>One shared space.</h2><p>Share files and notes over your local network.</p><div class="local-demo-actions"><button data-local="host">Host a room →</button><button class="secondary" data-local="join">Find a room →</button></div><div class="demo-preview"><span data-icon="laptop"></span>My device<span class="badge">THIS DEVICE</span></div>`,
      host: `<h2>Start a local room.</h2><p>A space for your files, notes, and links.</p><form id="local-host"><label for="local-name">Room name</label><input id="local-name" maxlength="60" required placeholder="e.g. Design studio"><label for="local-pin">Choose a PIN</label><input id="local-pin" type="password" inputmode="numeric" pattern="[0-9]{4}" maxlength="4" required><small>4 digits. Share the PIN separately.</small><button class="primary-action">Create room →</button></form>`,
      join: `<h2>Find your people.</h2><p>Choose a room or enter its room ID.</p><div id="local-rooms"></div><button class="secondary" data-local="refresh">Refresh rooms</button><form id="local-join"><label for="local-id-input">Room ID</label><input id="local-id-input" required placeholder="Enter room ID"><label for="local-pin-input">Room PIN</label><input id="local-pin-input" type="password" inputmode="numeric" pattern="[0-9]{4}" maxlength="4" required><button class="primary-action">Join room →</button></form>`,
      room: `<h2 id="local-heading"></h2><p>Room ID <strong id="local-id"></strong></p><div class="local-demo-actions"><button data-local="files">Choose files</button><input type="file" id="local-files" multiple hidden></div><form id="local-note-form"><label for="local-note">Share a note or link</label><textarea id="local-note" required maxlength="10000" placeholder="Write a note or paste a link…"></textarea><button>Share</button></form><label for="local-search">Search content</label><input id="local-search" type="search" placeholder="Search files and notes…"><h3 style="margin-top:24px">In this space</h3><ul id="local-items"></ul>`
    };
    root.innerHTML = `<p class="eyebrow">LOCAL SHARING</p>${screens[view]}<p id="local-feedback" role="status" aria-live="polite"></p><div class="demo-navigation">${view !== 'home' ? `<button class="secondary" data-local="${view === 'room' ? 'leave' : 'home'}">${view === 'room' ? 'Leave room' : '← Back'}</button>` : ''}<button class="secondary" data-local="exit">Back to online sharing</button></div>`;
    hydrateIcons(root);
    for (const input of root.querySelectorAll('input[type="password"]')) {
      const control = document.createElement('div');
      control.className = 'pin-control';
      input.before(control);
      input.classList.add('pin-entry');
      input.minLength = 4;
      const cells = document.createElement('span');
      cells.className = 'pin-cells';
      cells.setAttribute('aria-hidden', 'true');
      control.append(input, cells);
      initializePin(input);
    }
    const heading = root.querySelector('h2'); heading.tabIndex = -1; if (!root.hidden) heading.focus({preventScroll:true});
    el('local-host')?.addEventListener('submit', event => { event.preventDefault(); run(async () => {
      const name = el('local-name').value.trim(); if (!name) throw Error('Enter a room name.');
      room = await api.create(name, el('local-pin').value); await render('room');
    }); });
    el('local-join')?.addEventListener('submit', event => { event.preventDefault(); run(async () => { room = await api.join(el('local-id-input').value.trim(), el('local-pin-input').value); await render('room'); }); });
    if (view === 'join') await listRooms();
    if (view === 'room') {
      el('local-heading').textContent = room.name; el('local-id').textContent = room.id;
      el('local-files').onchange = () => run(async () => { for (const file of el('local-files').files) await api.add(room.id, {name:file.name, file, size:file.size}); el('local-files').value = ''; await listItems(); });
      el('local-note-form').onsubmit = event => { event.preventDefault(); run(async () => { const name = el('local-note').value.trim(); if (!name) throw Error('Enter a note or link.'); await api.add(room.id, {name}); el('local-note').value = ''; await listItems(); }); };
      el('local-search').oninput = () => run(listItems);
      await listItems();
    }
  }
  async function listRooms() {
    const available = await api.list(); el('local-rooms').replaceChildren();
    if (!available.length) el('local-rooms').textContent = 'No rooms found. Create a room to get started.';
    available.forEach(item => { const button = document.createElement('button'); button.className = 'demo-room-choice secondary'; button.textContent = item.name; button.onclick = () => { el('local-id-input').value = item.id; el('local-pin-input').focus(); }; el('local-rooms').append(button); });
  }
  async function listItems() {
    const items = await api.items(room.id); const query = el('local-search').value.toLowerCase(); const visible = items.filter(item => item.name.toLowerCase().includes(query));
    el('local-items').replaceChildren(); if (!visible.length) el('local-items').textContent = query ? 'No matching items.' : 'Nothing shared yet. Add a file or a note.';
    visible.forEach(item => {
      const row = document.createElement('li'); row.className = 'demo-item'; const body = document.createElement('span'); body.textContent = item.name; row.append(body);
      if (item.file || item.url) {
        const small = document.createElement('small'); small.textContent = formatBytes(item.size); body.append(small);
        const download = document.createElement('button'); download.className = 'secondary'; download.textContent = 'Download';
        download.onclick = () => { const url = item.url || URL.createObjectURL(item.file); const link = document.createElement('a'); link.href = url; link.download = item.name; link.click(); if (!item.url) setTimeout(() => URL.revokeObjectURL(url), 1000); }; row.append(download);
      }
      const remove = document.createElement('button'); remove.className = 'secondary'; remove.textContent = 'Remove'; remove.onclick = () => run(async () => { await api.remove(room.id, item.id); await listItems(); }); row.append(remove); el('local-items').append(row);
    });
  }
  root.addEventListener('click', event => {
    const action = event.target.closest('[data-local]')?.dataset.local; if (!action) return;
    run(async () => {
      if (action === 'exit') showLocalSharing(false);
      else if (action === 'files') el('local-files').click();
      else if (action === 'refresh') await listRooms();
      else if (action === 'leave') { await api.leave(room.id); room = null; await render('home'); }
      else await render(action);
    });
  });
  render('home');
})();
