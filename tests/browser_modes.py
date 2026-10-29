"""Two isolated local servers exercise Local/Online routing and HTTPS sharing.

Requires Chromium, Playwright, and the openssl command. No public service is used.
"""
import os
from pathlib import Path
import ssl
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

from playwright.sync_api import sync_playwright, expect

local = 'http://127.0.0.1:18766'
online = 'https://127.0.0.1:18767'
processes = []
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    cert, key = root / 'cert.pem', root / 'key.pem'
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                    '-keyout', str(key), '-out', str(cert), '-days', '1',
                    '-subj', '/CN=localhost'], check=True, capture_output=True)
    try:
        for mode, port in [('local', 18766), ('online', 18767)]:
            storage = root / mode
            storage.mkdir()
            code = (
                'import os; from pathlib import Path; from app import config; '
                'config.UPLOAD_DIR=Path(os.environ["TEST_STORAGE"]); '
                'from app.main import app; import uvicorn; '
                f'uvicorn.run(app, host="127.0.0.1", port={port}'
                + (f', ssl_certfile={str(cert)!r}, ssl_keyfile={str(key)!r}' if mode == 'online' else '')
                + ')'
            )
            env = {**os.environ, 'NETDROP_SHARING_MODE': mode,
                   'NETDROP_LOCAL_URL': local, 'NETDROP_ONLINE_URL': online,
                   'NETDROP_FILE_TTL_SECONDS': '1800', 'TEST_STORAGE': str(storage)}
            process = subprocess.Popen([sys.executable, '-c', code], env=env,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            processes.append(process)
            for _ in range(100):
                if process.poll() is not None:
                    raise RuntimeError(f'{mode} server failed to start')
                try:
                    urlopen((local if mode == 'local' else online) + '/up',
                            context=ssl._create_unverified_context(), timeout=1).close()
                    break
                except OSError:
                    time.sleep(.1)
            else:
                raise RuntimeError(f'{mode} server did not start')
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, executable_path=playwright.chromium.executable_path)
            owner = browser.new_context(ignore_https_errors=True)
            guest = browser.new_context(ignore_https_errors=True, viewport={'width': 390, 'height': 844})
            a, b = owner.new_page(), guest.new_page()
            errors = []
            a.on('pageerror', lambda error: errors.append(str(error)))
            b.on('pageerror', lambda error: errors.append(str(error)))
            for mode, origin in [('local', local), ('online', online)]:
                a.goto(origin)
                expect(a.locator('#sharing-mode')).to_be_enabled()
                expect(a.locator('#sharing-mode')).to_have_value(mode)
                a.screenshot(path=f'/tmp/netdrop-{mode}-lobby.png', full_page=True)
                a.locator('#room-name').fill(f'{mode} room')
                a.locator('#create-pin').fill('123456')
                a.get_by_role('button', name='Create room', exact=True).click()
                expect(a.locator('#live-status')).to_have_text('Live updates connected')
                invitation = a.locator('#invite-link').input_value()
                assert invitation.startswith(origin + '/#room=')
                assert '123456' not in invitation
                a.evaluate("Object.defineProperty(navigator, 'clipboard', {value: undefined, configurable: true})")
                a.locator('#copy-invite').click()
                expect(a.locator('#status')).to_have_text('Select and copy the invitation link above.')
                b.goto(invitation)
                expect(b.locator('#room-id')).to_have_value(a.locator('#active-id').inner_text())
                expect(b.locator('#room')).to_be_hidden()
                b.locator('#join-pin').fill('123456')
                b.get_by_role('button', name='Join room', exact=True).click()
                expect(b.locator('#live-status')).to_have_text('Live updates connected')
                a.locator('#file').set_input_files({'name': f'{mode}.txt',
                    'mimeType': 'text/plain', 'buffer': mode.encode()})
                a.get_by_role('button', name='Upload file', exact=True).click()
                expect(b.get_by_role('link', name=f'{mode}.txt', exact=True)).to_be_visible()
                with b.expect_download() as downloaded:
                    b.get_by_role('link', name=f'{mode}.txt', exact=True).click()
                assert Path(downloaded.value.path()).read_bytes() == mode.encode()
                assert b.evaluate('document.documentElement.scrollWidth <= innerWidth')
                b.screenshot(path=f'/tmp/netdrop-{mode}-mobile.png', full_page=True)
                a.screenshot(path=f'/tmp/netdrop-{mode}-desktop.png', full_page=True)
                a.get_by_role('button', name='Leave room', exact=True).click()
                b.get_by_role('button', name='Leave room', exact=True).click()
                target_mode, target = ('online', online) if mode == 'local' else ('local', local)
                a.locator('#sharing-mode').select_option(target_mode)
                expect(a.get_by_role('button', name='Create room', exact=True)).to_be_disabled()
                a.locator('#switch-mode').click()
                expect(a).to_have_url(target + '/')
                expect(a.locator('#sharing-mode')).to_have_value(target_mode)
            # Missing online configuration must explain the limitation, never create a local room.
            a.route('**/api/sharing', lambda route: route.fulfill(json={
                'mode': 'local', 'local_url': local, 'online_url': ''}))
            a.goto(local)
            expect(a.locator('#sharing-mode')).to_be_enabled()
            a.locator('#sharing-mode').select_option('online')
            expect(a.locator('#mode-help')).to_contain_text('has not configured')
            expect(a.locator('#switch-mode')).to_be_hidden()
            expect(a.get_by_role('button', name='Create room', exact=True)).to_be_disabled()
            assert not errors, errors
            browser.close()
        print('PASS: Local/HTTPS Online transfers, invitations, live updates, mode routing, unavailable mode, and mobile layout. Public cross-network access not tested.')
    finally:
        for process in processes:
            process.terminate()
        for process in processes:
            process.wait(timeout=10)
