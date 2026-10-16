import os
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen
from playwright.sync_api import sync_playwright, expect

with tempfile.TemporaryDirectory() as storage:
    code = "from pathlib import Path; from app import config; import os; config.UPLOAD_DIR=Path(os.environ['NETDROP_TEST_STORAGE']); from app.main import app; import uvicorn; uvicorn.run(app,host='127.0.0.1',port=18765)"
    env = {**os.environ, 'NETDROP_TEST_STORAGE': storage, 'NETDROP_FILE_TTL_SECONDS':'8', 'NETDROP_CLEANUP_INTERVAL_SECONDS':'1'}
    def start():
        proc = subprocess.Popen([sys.executable, '-c', code], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            if proc.poll() is not None: raise RuntimeError('Server failed to start')
            try:
                urlopen('http://127.0.0.1:18765/', timeout=1).close()
                return proc
            except OSError: time.sleep(.1)
        raise RuntimeError('Server did not start')
    process = start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, executable_path=p.chromium.executable_path)
            owner = browser.new_context()
            guest = browser.new_context(viewport={'width':390,'height':844})
            a, b = owner.new_page(), guest.new_page()
            errors = []
            a.on('pageerror', lambda error: errors.append(str(error)))
            b.on('pageerror', lambda error: errors.append(str(error)))
            a.goto('http://127.0.0.1:18765/')
            a.locator('#room-name').fill('Live test')
            a.locator('#create-pin').fill('123456')
            a.get_by_role('button', name='Create room').click()
            expect(a.locator('#live-status')).to_have_text('Live updates connected')
            room_id = a.locator('#active-id').inner_text()
            b.goto('http://127.0.0.1:18765/')
            b.locator('#room-id').fill('Live test')
            b.locator('#join-pin').fill('123456')
            b.get_by_role('button', name='Join room').click()
            assert '12-character room ID' in b.locator('#room-id').evaluate('(el) => el.validationMessage')
            b.locator('#room-id').fill(room_id)
            b.locator('#join-pin').fill('1234')
            b.get_by_role('button', name='Join room').click()
            assert '6 to 12 digits' in b.locator('#join-pin').evaluate('(el) => el.validationMessage')
            b.locator('#room-id').fill(' ' + room_id[:6].upper() + ' ' + room_id[6:].upper() + ' ')
            b.locator('#join-pin').fill(' 123456 ')
            b.get_by_role('button', name='Join room').click()
            expect(b.locator('#live-status')).to_have_text('Live updates connected')
            a.locator('#file').set_input_files({'name':'live.txt','mimeType':'text/plain','buffer':b'live file'})
            a.get_by_role('button', name='Upload file').click()
            expect(b.get_by_role('link', name='live.txt')).to_be_visible()
            file_url = b.get_by_role('link', name='live.txt').get_attribute('href')
            with b.expect_download() as result:
                b.get_by_role('link',name='live.txt').click()
            with open(result.value.path(), 'rb') as downloaded:
                assert downloaded.read() == b'live file'
            b.locator('#file').set_input_files({'name':'reply.txt','mimeType':'text/plain','buffer':b'return file'})
            b.get_by_role('button', name='Upload file').click()
            expect(a.get_by_role('link', name='reply.txt')).to_be_visible()
            with a.expect_download() as reply:
                a.get_by_role('link', name='reply.txt').click()
            with open(reply.value.path(), 'rb') as downloaded:
                assert downloaded.read() == b'return file'
            a.locator('#kind').select_option('link')
            a.locator('#content').fill('https://example.com')
            a.get_by_role('button', name='Share', exact=True).click()
            expect(b.get_by_role('link', name='https://example.com', exact=True)).to_be_visible()
            guest.set_offline(True)
            b.evaluate('liveSocket.close()')
            expect(b.locator('#live-status')).to_have_text('Connection lost. Reconnecting…')
            a.locator('#kind').select_option('text')
            a.locator('#content').fill('Added while offline')
            a.get_by_role('button', name='Share', exact=True).click()
            expect(a.get_by_text('Added while offline', exact=True)).to_be_visible()
            guest.set_offline(False)
            expect(b.locator('#live-status')).to_have_text('Live updates connected', timeout=15000)
            expect(b.get_by_text('Added while offline', exact=True)).to_be_visible()
            expect(b.get_by_role('link', name='live.txt')).to_have_count(0, timeout=12000)
            expect(b.get_by_text('Added while offline', exact=True)).to_have_count(0, timeout=12000)
            assert owner.request.get('http://127.0.0.1:18765' + file_url).status in (404,410)
            assert not os.listdir(storage), os.listdir(storage)
            assert b.evaluate('document.documentElement.scrollWidth <= innerWidth')
            # Restart disconnects sockets and invalidates the old in-memory room.
            process.terminate()
            process.wait(timeout=10)
            process = start()
            expect(b.locator('#lobby')).to_be_visible(timeout=20000)
            assert not errors, errors
            browser.close()
            print('PASS: join-form validation and pasted-input normalization, bidirectional file sharing/downloads, automatic file/link updates, offline reconnect with missed content, automatic expiry/deletion, expired download denial, mobile layout, and host restart recovery.')
    finally:
        process.terminate()
        process.wait(timeout=10)
