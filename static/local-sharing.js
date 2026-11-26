(() => {
  const root = document.getElementById('local-sharing');
  if (!root) return;

  root.innerHTML = `
    <p class="eyebrow">LOCAL SHARING</p>
    <h2 id="local-sharing-heading">Checking local sharing…</h2>
    <p id="local-sharing-description" role="status" aria-live="polite">
      Loading the options for this NetDrop instance.
    </p>
    <div id="local-sharing-actions" class="local-demo-actions"></div>
    <p id="local-sharing-note" class="demo-caption"></p>
    <div class="demo-navigation">
      <button id="local-sharing-back" class="secondary" type="button">Back to room options</button>
    </div>`;

  const heading = document.getElementById('local-sharing-heading');
  const description = document.getElementById('local-sharing-description');
  const actions = document.getElementById('local-sharing-actions');
  const note = document.getElementById('local-sharing-note');

  document.getElementById('local-sharing-back').addEventListener('click', () => {
    showLocalSharing(false);
  });

  async function loadOptions() {
    try {
      const response = await fetch('/api/sharing', { cache: 'no-store' });
      const settings = await response.json();
      if (!response.ok) {
        throw new Error(typeof settings.detail === 'string'
          ? settings.detail : `Unable to load sharing options (HTTP ${response.status}).`);
      }

      if (settings.mode === 'local') {
        heading.textContent = 'Share with nearby devices.';
        description.textContent =
          'This NetDrop host is running on your local network. Create or join a room from the room options.';
        note.textContent =
          'Other devices must use the same Wi-Fi or LAN. No internet connection is needed.';
        if (settings.local_url) {
          const hostname = new URL(settings.local_url).hostname;
          if (!['localhost', '127.0.0.1', '[::1]'].includes(hostname)) {
            const link = document.createElement('a');
            link.className = 'local-download';
            link.href = settings.local_url;
            link.textContent = 'Open the LAN address';
            actions.append(link);
          } else {
            note.textContent += ' To join from another device, use the host computer’s Wi-Fi or LAN IPv4 address, not 127.0.0.1.';
          }
        }
      } else {
        heading.textContent = 'Share without the internet.';
        description.textContent =
          'Install NetDrop Local on Windows or Ubuntu to host rooms for nearby devices.';
        note.textContent =
          'Choose “Host a local room” after installation. The Ubuntu download is for 64-bit systems. Other devices must use the same Wi-Fi or LAN.';
        for (const [url, label] of [
          [settings.local_installer_url, 'Download NetDrop Local for Windows'],
          [settings.ubuntu_installer_url, 'Download NetDrop Local for Ubuntu (.deb)'],
        ]) {
          const link = document.createElement('a');
          link.className = 'local-download';
          link.href = url;
          link.textContent = label;
          actions.append(link);
        }
      }

      if (!root.hidden) heading.focus({ preventScroll: true });
    } catch (error) {
      description.textContent = error.message || 'Unable to load local sharing options.';
      description.classList.add('error');
    }
  }

  loadOptions();
})();
