"""Owner controls, multi-file queue, cancellation/retry, countdown and QR browser checks.

Uses isolated storage and port 18768; never changes the normal server's rooms.
"""
import os
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

from playwright.sync_api import sync_playwright, expect


def main():
    with tempfile.TemporaryDirectory() as storage:
        code = "from pathlib import Path; from app import config; import os; config.UPLOAD_DIR=Path(os.environ['NETDROP_TEST_STORAGE']); from app.main import app; import uvicorn; uvicorn.run(app,host='127.0.0.1',port=18768)"
        env = {**os.environ, 'NETDROP_TEST_STORAGE': storage, 'NETDROP_FILE_TTL_SECONDS': '120',
               'NETDROP_CLEANUP_INTERVAL_SECONDS': '1', 'NETDROP_MAX_UPLOAD_MB': '1',
               'NETDROP_SHARING_MODE': 'local', 'NETDROP_LOCAL_URL': '', 'NETDROP_ONLINE_URL': ''}
        process = subprocess.Popen([sys.executable, '-c', code], env=env,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(80):
                if process.poll() is not None:
                    raise RuntimeError('Server failed to start')
                try:
                    urlopen('http://127.0.0.1:18768/up', timeout=1).close()
                    break
                except OSError:
                    time.sleep(.1)
            else:
                raise RuntimeError('Server did not start')
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path=p.chromium.executable_path)
                owner = browser.new_context()
                guest = browser.new_context(viewport={'width': 390, 'height': 844})
                a, b = owner.new_page(), guest.new_page()
                errors = []
                for page in (a, b):
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.on('dialog', lambda dialog: dialog.accept())
                    page.goto('http://127.0.0.1:18768/')
                a.locator('#action-create').click()
                a.locator('#create-display-name').fill('Owner')
                a.locator('#room-name').fill('Sharing improvements')
                a.locator('#create-pin').fill('123456')
                a.get_by_role('button', name='Create room', exact=True).click()
                expect(a.locator('#close-room')).to_be_visible()
                room_id = a.locator('#active-id').inner_text()
                b.locator('#room-id').fill(room_id)
                b.locator('#join-display-name').fill('Guest')
                b.locator('#join-pin').fill('123456')
                b.get_by_role('button', name='Join room', exact=True).click()
                expect(b.locator('#live-status')).to_have_text('Live updates connected')
                expect(b.locator('#close-room')).to_be_hidden()
                a.locator('#qr-invite summary').click()
                expect(a.locator('#invite-qr')).to_be_visible()
                assert a.locator('#invite-qr').evaluate('(img) => img.complete && img.naturalWidth > 0')
                assert '123456' not in a.locator('#invite-link').input_value()
                # A failed file must not prevent the following file from succeeding.
                calls = []
                def fail_first(route):
                    calls.append(route.request.headers.get('x-filename'))
                    if len(calls) == 1:
                        route.fulfill(status=503, content_type='application/json', body='{"detail":"Temporary upload failure"}')
                    else:
                        route.continue_()
                pattern = '**/api/rooms/*/files'
                a.route(pattern, fail_first)
                a.locator('#file').set_input_files([
                    {'name': 'first.txt', 'mimeType': 'text/plain', 'buffer': b'first'},
                    {'name': 'second.txt', 'mimeType': 'text/plain', 'buffer': b'second'},
                ])
                a.locator('#upload-submit').click()
                expect(a.locator('#upload-queue')).to_contain_text('Temporary upload failure')
                expect(b.get_by_role('link', name='second.txt', exact=True)).to_be_visible()
                a.locator('#upload-queue li').filter(has_text='first.txt').get_by_role('button', name='Retry').click()
                expect(b.get_by_role('link', name='first.txt', exact=True)).to_be_visible()
                expect(a.locator('#upload-queue li').filter(has_text='first.txt')).to_contain_text('Shared')
                a.unroute(pattern, fail_first)
                # Pause an actual XHR; Cancel must work without waiting for the response.
                held = []
                a.route(pattern, lambda route: held.append(route))
                a.locator('#file').set_input_files({'name': 'cancel.txt', 'mimeType': 'text/plain', 'buffer': b'x' * 65536})
                a.locator('#upload-submit').click()
                row = a.locator('#upload-queue li').filter(has_text='cancel.txt')
                expect(row.get_by_role('button', name='Cancel', exact=True)).to_be_visible()
                row.get_by_role('button', name='Cancel', exact=True).click()
                expect(row).to_contain_text('Cancelled')
                expect(b.get_by_role('link', name='cancel.txt', exact=True)).to_have_count(0)
                for route in held:
                    route.abort()
                a.unroute(pattern)
                row.get_by_role('button', name='Retry').click()
                expect(b.get_by_role('link', name='cancel.txt', exact=True)).to_be_visible()
                # Oversized selection is rejected per-file without a request.
                a.locator('#file').set_input_files({'name': 'too-big.bin', 'mimeType': 'application/octet-stream', 'buffer': b'x' * (1024 * 1024 + 1)})
                a.locator('#upload-submit').click()
                expect(a.locator('#upload-queue li').filter(has_text='too-big.bin')).to_contain_text('File exceeds the upload limit')
                countdown = b.locator('[data-expires]').first
                expect(countdown).to_contain_text('Expires in')
                before = countdown.inner_text()
                expect(countdown).not_to_have_text(before, timeout=3000)
                expect(b.get_by_role('button', name='Delete first.txt', exact=True)).to_have_count(0)
                a.get_by_role('button', name='Delete first.txt', exact=True).click()
                expect(b.get_by_role('link', name='first.txt', exact=True)).to_have_count(0)
                expect(a.locator('#member-count')).to_have_text('2 joined · 2 online')
                a.screenshot(path='/tmp/netdrop-controls-desktop.png', full_page=True)
                b.screenshot(path='/tmp/netdrop-controls-mobile.png', full_page=True)
                assert b.evaluate('document.documentElement.scrollWidth <= innerWidth')
                a.get_by_role('button', name='Remove Guest', exact=True).click()
                expect(b.locator('#auth-shell')).to_be_visible(timeout=10000)
                expect(a.locator('#member-count')).to_have_text('1 joined · 1 online')
                # Rejoining is explicitly allowed for anyone retaining the PIN.
                b.locator('#room-id').fill(room_id)
                b.locator('#join-pin').fill('123456')
                b.get_by_role('button', name='Join room', exact=True).click()
                expect(b.locator('#room')).to_be_visible()
                a.locator('#close-room').click()
                expect(a.locator('#auth-shell')).to_be_visible()
                expect(b.locator('#auth-shell')).to_be_visible(timeout=10000)
                assert not os.listdir(storage), os.listdir(storage)
                assert not errors, errors
                browser.close()
                print('PASS: owner controls, multi-file progress, failure/retry, cancellation/retry, size limit, countdown, QR, mobile layout and live revocation')
        finally:
            process.terminate()
            process.wait(timeout=10)


if __name__ == '__main__':
    main()
