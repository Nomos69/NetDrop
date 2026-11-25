// This walkthrough keeps all state in this page and makes no network requests.
(() => {
  const root = document.getElementById('local-sharing-demo');
  let roomName = 'Design studio';
  function render(view) {
    const screens = {
      home: `<h2>Nearby devices.<br>One shared space.</h2><p>Explore sharing over your local network.</p><div class="local-demo-actions"><button data-demo="host"><span data-icon="plus"></span>Host a room<span data-icon="arrow"></span></button><button class="secondary" data-demo="join"><span data-icon="search"></span>Find a room<span data-icon="arrow"></span></button></div><div class="demo-preview"><span data-icon="laptop"></span><span>My laptop</span><span class="badge">THIS DEVICE · SAMPLE</span></div>`,
      host: `<h2>Start a local room.</h2><p>Give your demo space a name.</p><form id="demo-host-form"><label for="demo-room-name">Room name</label><input id="demo-room-name" maxlength="60" required placeholder="e.g. Design studio" value="Design studio"><label for="demo-pin">Demo PIN</label><input id="demo-pin" inputmode="numeric" pattern="[0-9]{4}" maxlength="4" value="1234" required><small>Use any 4 digits for this walkthrough.</small><button class="primary-action">Open demo room<span data-icon="arrow"></span></button></form>`,
      join: `<h2>Find your people.</h2><p>Sample rooms on your network. Select one to preview joining.</p><button class="demo-room-choice secondary" data-demo="connect"><span data-icon="laptop"></span><span><strong>Design studio</strong><small>Alex’s laptop · 2 sample devices</small></span><span data-icon="arrow"></span></button><button class="secondary" data-demo="scan"><span data-icon="refresh"></span>Scan again</button><p id="demo-scan-status" role="status"></p>`,
      connect: `<h2>Join Design studio.</h2><p>Try the sample PIN <strong>1234</strong>.</p><form id="demo-join-form"><label for="demo-join-pin">Room PIN</label><input id="demo-join-pin" inputmode="numeric" pattern="1234" maxlength="4" required placeholder="1234" title="Use the sample PIN 1234"><button class="primary-action">Join demo room<span data-icon="arrow"></span></button></form>`,
      room: `<h2 id="demo-room-heading"></h2><p><span class="badge">DEMO ROOM</span> · 3 sample devices</p><div class="demo-preview"><span data-icon="laptop"></span>My laptop <span data-icon="phone"></span>Alex’s phone</div><div class="local-demo-actions"><button data-demo="file"><span data-icon="upload"></span>Add sample file</button><button class="secondary" data-demo="note"><span data-icon="text"></span>Add a note</button></div><form id="demo-note-form" hidden><label for="demo-note">Your demo note</label><textarea id="demo-note" maxlength="500" required placeholder="Write a note…"></textarea><button type="submit">Add to preview</button></form><h3>In this space</h3><ul id="demo-items"><li class="demo-item"><span data-icon="file"></span><span>Project brief.pdf<small>Sample file · 240 KB</small></span><button class="secondary" data-demo="download">Preview</button></li></ul><p id="demo-feedback" role="status" aria-live="polite"></p>`
    };
    root.innerHTML = `<p class="eyebrow">LOCAL SHARING / INTERACTIVE DEMO</p>${screens[view]}<p class="demo-caption">Demo only · No devices connected or files transferred.</p><div class="demo-navigation">${view !== 'home' ? '<button class="secondary" data-demo="home">← Back to local menu</button>' : ''}<button class="secondary" data-demo="exit">Back to online sharing</button></div>`;
    if (view === 'room') document.getElementById('demo-room-heading').textContent = roomName;
    hydrateIcons(root);
    root.querySelector('h2').tabIndex = -1;
    if (!root.hidden) root.querySelector('h2').focus({preventScroll: true});
    root.querySelector('#demo-host-form')?.addEventListener('submit', event => {
      event.preventDefault(); roomName = document.getElementById('demo-room-name').value.trim() || 'My local room'; render('room');
    });
    root.querySelector('#demo-join-form')?.addEventListener('submit', event => {
      event.preventDefault(); roomName = 'Design studio'; render('room');
    });
    root.querySelector('#demo-note-form')?.addEventListener('submit', event => {
      event.preventDefault(); addItem(document.getElementById('demo-note').value, 'Demo note · visible only here'); event.target.reset(); event.target.hidden = true;
    });
  }
  function addItem(name, detail) {
    const item = document.createElement('li'); item.className = 'demo-item';
    const body = document.createElement('span'); body.textContent = name;
    const small = document.createElement('small'); small.textContent = detail; body.append(small);
    const remove = document.createElement('button'); remove.className = 'secondary'; remove.textContent = 'Remove'; remove.onclick = () => item.remove();
    item.append(body, remove); document.getElementById('demo-items').prepend(item);
    document.getElementById('demo-feedback').textContent = 'Added to this demo preview.';
  }
  root.addEventListener('click', event => {
    const action = event.target.closest('[data-demo]')?.dataset.demo;
    if (!action) return;
    if (action === 'exit') { showLocalSharingDemo(false); document.getElementById('lobby').setAttribute('aria-labelledby', 'entry-title'); }
    else if (action === 'scan') document.getElementById('demo-scan-status').textContent = 'Demo scan complete. 1 sample room found.';
    else if (action === 'file') addItem('Moodboard.png', 'Sample file · 1.2 MB · simulated upload');
    else if (action === 'note') { document.getElementById('demo-note-form').hidden = false; document.getElementById('demo-note').focus(); }
    else if (action === 'download') document.getElementById('demo-feedback').textContent = 'Sample file selected. Downloads are simulated in this demo.';
    else render(action);
  });
  render('home');
})();
