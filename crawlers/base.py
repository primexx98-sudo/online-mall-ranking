"""Playwright 공통 유틸. 모든 크롤러가 동일한 브라우저 컨텍스트 설정을 공유한다."""

from contextlib import contextmanager

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


@contextmanager
def new_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT, locale="ko-KR")
        Stealth().apply_stealth_sync(context)
        page = context.new_page()
        try:
            yield page
        finally:
            browser.close()
