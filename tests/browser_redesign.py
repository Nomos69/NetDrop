"""Run against an isolated local HTTPS NetDrop server; never a production URL.

NETDROP_TEST_URL=https://localhost:18443 .venv/bin/python tests/browser_redesign.py
Email delivery is intercepted in the browser. Screenshots go to /tmp/netdrop-ui-qa.
"""
import os
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright, expect

URL = os.getenv('NETDROP_TEST_URL', 'https://localhost:18443')
assert urlsplit(URL).hostname in {'localhost', '127.0.0.1'}, 'Local test server only'
OUT = Path(os.getenv('NETDROP_SCREENSHOTS', '/tmp/netdrop-ui-qa'))
OUT.mkdir(exist_ok=True)


def screenshot(page, name):
    page.screenshot(path=str(OUT / f'{name}.png'), full_page=True, animations='disabled')


def no_overflow(page):
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Horizontal overflow'


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=p.chromium.executable_path)
    owner = browser.new_context(ignore_https_errors=True, permissions=['clipboard-read', 'clipboard-write'])
    guest = browser.new_context(ignore_https_errors=True, permissions=['clipboard-read', 'clipboard-write'])
    a, b = owner.new_page(), guest.new_page()
    errors = []
    for page in [a, b]:
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('dialog', lambda dialog: dialog.accept())
    a.goto(URL)
    for width in [360, 390, 768, 1024, 1440]:
        a.set_viewport_size({'width': width, 'height': 1000})
        no_overflow(a)
        screenshot(a, f'landing-dark-{width}')
    a.locator('#theme-toggle').click()
    # Every input has a programmatic label, and reduced motion disables effects.
    assert a.evaluate("[...document.querySelectorAll('input,textarea,select')].every(el => el.labels.length || el.getAttribute('aria-label'))")
    a.emulate_media(reduced_motion='reduce')
    assert a.locator('.signal').evaluate("el => getComputedStyle(el).animationName") == 'none'
    a.emulate_media(reduced_motion='no-preference')
    # Motion is real, and the reduced-motion alternative is fully static.
    first_transform = a.locator('.packet').first.evaluate('el => getComputedStyle(el).transform')
    a.wait_for_timeout(1100)  # Includes the intentional 600 ms pause at the device.
    assert a.locator('.packet').first.evaluate('el => getComputedStyle(el).transform') != first_transform
    expect(a.locator('html')).to_have_attribute('data-theme', 'light')
    screenshot(a, 'landing-light-1440')
    a.reload()
    expect(a.locator('html')).to_have_attribute('data-theme', 'light')
    a.locator('#theme-toggle').click()
    a.locator('[data-network-device="Phone"]').click()
    expect(a.locator('#network-caption')).to_contain_text('Phone')
    a.locator('[data-room-action="create"]').click()
    expect(a.locator('.action-tabs')).to_have_attribute('data-action', 'create')
    a.locator('#room-name').fill('Design studio')
    a.locator('#create-pin').fill('12')
    a.locator('#create-form button').click()
    expect(a.locator('#auth-shell')).to_be_visible()
    a.locator('#create-pin').fill('1234')
    a.locator('#create-display-name').fill('Alex')
    screenshot(a, 'create-room')
    a.locator('#create-form button').click()
    expect(a.locator('#room')).to_be_visible()
    expect(a.locator('#live-status')).to_have_attribute('data-state', 'connected')
    room_id = a.locator('#active-id').inner_text()
    a.locator('#copy-room-id').click()
    expect(a.locator('#copy-room-id')).to_have_class('copy-confirmed')
    assert a.evaluate('navigator.clipboard.readText()') == room_id
    b.goto(URL + '/#room=' + room_id)
    expect(b.locator('#room-id')).to_have_value(room_id)
    b.locator('#join-pin').fill('1234')
    b.locator('#join-display-name').fill('Sam')
    screenshot(b, 'join-room')
    b.locator('#join-form button').click()
    expect(b.locator('#room')).to_be_visible()
    expect(a.locator('#member-count')).to_contain_text('2 joined')
    a.locator('#content').fill('A shared note from the design studio.')
    a.locator('#content').press('Control+Enter')
    expect(b.locator('#items')).to_contain_text('A shared note')
    b.locator('[aria-label="Copy note"]').click()
    assert 'A shared note' in b.evaluate('navigator.clipboard.readText()')
    a.locator('#content').fill('https://example.com/design')
    expect(a.locator('#kind')).to_have_value('link')
    a.locator('#content-form button').click()
    expect(b.locator('#items a')).to_have_attribute('href', 'https://example.com/design')
    a.locator('#file').set_input_files({'name': 'project-brief.txt', 'mimeType': 'text/plain', 'buffer': b'Harmless NetDrop test file.'})
    expect(a.locator('#upload-selection')).to_contain_text('1 file selected')
    a.locator('#upload-submit').click()
    expect(a.locator('#upload-queue')).to_contain_text('Shared')
    expect(b.locator('#items')).to_contain_text('project-brief.txt')
    expect(a.locator('.file-timer svg')).to_have_count(1)
    a.wait_for_timeout(1200)
    expect(a.locator('.file-timer svg')).to_have_count(1)
    expect(a.locator('.timer-value')).to_contain_text(':')
    # Test visual countdown boundaries without changing server expiry.
    a.evaluate("document.querySelector('.file-timer').dataset.expires = Date.now()/1000 + 120; updateCountdowns()")
    expect(a.locator('.file-timer')).to_have_class('file-timer warning')
    a.evaluate("document.querySelector('.file-timer').dataset.expires = Date.now()/1000 - 1; updateCountdowns()")
    expect(a.locator('.timer-label')).to_have_text('expired')
    a.locator('#refresh').click()
    expect(a.locator('.file-timer')).not_to_have_class('file-timer expired')
    with b.expect_download() as download_info:
        b.locator('[aria-label="Download project-brief.txt"]').click()
    download = download_info.value
    assert Path(download.path()).read_bytes() == b'Harmless NetDrop test file.'
    a.locator('#feed-search').fill('project')
    expect(a.locator('.feed-item')).to_have_count(1)
    a.locator('#feed-search').fill('no-such-file')
    expect(a.locator('.empty-feed')).to_contain_text('No matches')
    a.locator('#feed-search').fill('')
    a.locator('#feed-filter').select_option('text')
    expect(a.locator('.feed-item')).to_have_count(1)
    a.locator('#feed-filter').select_option('all')
    # Real drag/drop selection; fail the first upload, then retry successfully.
    transfer = a.evaluate_handle("""() => {
      const data = new DataTransfer();
      data.items.add(new File(['Dropped sample'], 'dropped.txt', {type:'text/plain'}));
      return data;
    }""")
    a.locator('#drop-zone').dispatch_event('dragover', {'dataTransfer':transfer})
    expect(a.locator('#drop-zone')).to_have_class('drop-zone dragging')
    a.locator('#drop-zone').dispatch_event('drop', {'dataTransfer':transfer})
    expect(a.locator('#upload-selection')).to_contain_text('1 file selected')
    a.route('**/files', lambda route: route.fulfill(status=503, json={'detail':'Temporary test failure'}), times=1)
    a.locator('#upload-submit').click()
    expect(a.locator('#upload-queue')).to_contain_text('Temporary test failure')
    a.locator('#upload-queue').get_by_role('button', name='Retry').click()
    expect(b.locator('#items')).to_contain_text('dropped.txt')
    # Preview raster selections without downloading any room file.
    import base64
    a.locator('#file').set_input_files({'name':'pixel.png','mimeType':'image/png','buffer':base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')})
    expect(a.locator('#upload-selection img')).to_have_count(1)
    a.locator('#file').set_input_files([])
    for i in range(6):
        response = owner.request.post(URL + f'/api/rooms/{room_id}/items', headers={'X-NetDrop': '1'}, data={'kind':'text','content':f'Team note {i + 1}'})
        assert response.status == 201
    expect(a.locator('#feed-pagination')).to_be_visible()
    expect(a.locator('.feed-item')).to_have_count(6)
    a.locator('#feed-next').click()
    expect(a.locator('#feed-page')).to_contain_text('Page 2 of 2')
    expect(a.locator('#feed-next')).to_be_disabled()
    a.locator('#refresh').click()
    expect(a.locator('#feed-next')).to_be_disabled()
    a.locator('#feed-prev').click()
    a.locator('#feed-filter').select_option('file')
    for width in [360, 390, 768, 1024, 1440]:
        a.set_viewport_size({'width':width, 'height':1000})
        no_overflow(a)
        screenshot(a, f'workspace-dark-{width}')
    a.locator('#theme-toggle').click()
    screenshot(a, 'workspace-light-1440')
    a.locator('#theme-toggle').click()
    a.locator('.workspace-header [data-dialog="invite-dialog"]').click()
    expect(a.locator('#invite-dialog')).to_be_visible()
    assert '1234' not in a.locator('#invite-link').input_value()
    a.locator('#copy-invite').click()
    assert room_id in a.evaluate('navigator.clipboard.readText()')
    a.locator('#qr-invite summary').click()
    expect(a.locator('#invite-qr')).to_be_visible()
    assert a.locator('#invite-qr').evaluate('(img) => img.complete && img.naturalWidth > 0')
    a.route('**/email-invitation', lambda route: route.fulfill(json={'message':'Invitation accepted (test).'}))
    a.locator('#invite-email').fill('test@example.com')
    a.locator('#email-invitation button').click()
    expect(a.locator('#email-result')).to_contain_text('accepted')
    screenshot(a, 'invitation-dialog')
    a.keyboard.press('Escape')
    expect(a.locator('#invite-dialog')).not_to_be_visible()
    expect(a.locator('.workspace-header [data-dialog="invite-dialog"]')).to_be_focused()
    a.locator('[data-dialog="alerts-dialog"]').click()
    expect(a.locator('.disclosure')).to_contain_text('attachment outside this room')
    a.route('**/subscriptions', lambda route: route.fulfill(json={'message':'Preferences saved (test).'}))
    a.locator('#alert-email').fill('test@example.com')
    a.locator('#upload-alerts button[type=submit]').click()
    expect(a.locator('#alert-result')).to_contain_text('Preferences saved')
    a.locator('#disable-alerts').click()
    screenshot(a, 'alerts-dialog')
    a.set_viewport_size({'width':360,'height':800})
    no_overflow(a)
    screenshot(a, 'alerts-mobile')
    a.keyboard.press('Escape')
    expect(a.locator('#alerts-dialog')).not_to_be_visible()
    # Unsafe-looking notes remain plain text, never executable HTML.
    b.locator('#content').fill('<img src=x onerror=alert(1)>')
    b.locator('#content-form button').click()
    expect(b.locator('#items')).to_contain_text('<img src=x onerror=alert(1)>')
    expect(b.locator('#items img')).to_have_count(0)
    # Owner deletion remains available with filtering active.
    a.locator('#feed-search').fill('dropped.txt')
    a.locator('#items').get_by_role('button',name='Delete dropped.txt').click()
    expect(a.locator('.empty-feed')).to_be_visible()
    b.locator('#leave').click()
    expect(b.locator('#auth-shell')).to_be_visible()
    a.locator('.workspace-header [data-dialog="invite-dialog"]').click()
    a.locator('#close-room').click()
    expect(a.locator('#auth-shell')).to_be_visible()
    expect(a.locator('#invite-dialog')).not_to_be_visible()
    assert not errors, errors
    browser.close()
    print('PASS: five viewport widths; dark/light persistence; room create/join; PIN validation; live two-client sharing; uploads/downloads; circular timer; search/filter/pagination; clipboard; QR; mocked email settings; leave/close; no horizontal overflow or page errors.')
