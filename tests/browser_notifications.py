"""Desktop/mobile invitation checks with mocked Brevo; no real emails sent."""
import os, subprocess, time, sys, tempfile
from urllib.request import urlopen
from playwright.sync_api import sync_playwright, expect
with tempfile.TemporaryDirectory() as storage:
    code = '''from app import config, notifications
from pathlib import Path
from unittest.mock import AsyncMock
import httpx, uvicorn, os
config.UPLOAD_DIR=Path(os.environ['TEST_STORAGE'])
config.BREVO_API_KEY='test-key'
config.BREVO_SENDER_EMAIL='host@example.com'
config.LOCAL_URL='http://192.168.1.5:8000'
notifications.httpx.AsyncClient.post=AsyncMock(return_value=httpx.Response(201,json={'messageId':'test'}))
from app.main import app
uvicorn.run(app,host='127.0.0.1',port=18769)
'''
    process=subprocess.Popen([sys.executable,'-c',code],env={**os.environ,'TEST_STORAGE':storage},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(80):
            if process.poll() is not None:
                raise RuntimeError('Test server failed to start')
            try:
                urlopen('http://127.0.0.1:18769/up',timeout=1).close(); break
            except OSError: time.sleep(.1)
        else:
            raise RuntimeError('Test server did not become ready')
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=p.chromium.executable_path)
            for width in [1280,390]:
                context=browser.new_context(viewport={'width':width,'height':900})
                page=context.new_page(); errors=[]
                page.on('pageerror',lambda error: errors.append(str(error)))
                page.goto('http://127.0.0.1:18769')
                page.locator('#action-create').click()
                page.locator('#room-name').fill('Brevo invitations')
                page.locator('#create-pin').fill('1234')
                page.get_by_role('button',name='Create room',exact=True).click()
                expect(page.locator('#email-invitation')).to_be_visible()
                page.locator('#invite-email').fill('guest@example.com')
                page.get_by_role('button',name='Email invitation',exact=True).click()
                expect(page.locator('#email-result')).to_contain_text('Invitation sent')
                assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
                page.locator('#email-invitation').screenshot(path=f'/tmp/netdrop-brevo-{width}.png')
                page.get_by_role('button',name='Email invitation',exact=True).click()
                expect(page.locator('#email-result')).to_contain_text('Please wait')
                guest_context=browser.new_context(viewport={'width':width,'height':900})
                guest=guest_context.new_page()
                guest.goto('http://127.0.0.1:18769')
                guest.locator('#room-id').fill(page.locator('#active-id').inner_text())
                guest.locator('#join-pin').fill('1234')
                guest.get_by_role('button',name='Join room',exact=True).click()
                expect(guest.locator('#room')).to_be_visible()
                expect(guest.locator('#email-invitation')).to_be_hidden()
                guest_context.close()
                assert not errors, errors
                context.close()
            browser.close()
        print('PASS: desktop and phone invitation form, mocked Brevo acceptance, rate-limit feedback, owner-only visibility, no overflow or JS errors')
    finally:
        process.terminate(); process.wait(timeout=10)
