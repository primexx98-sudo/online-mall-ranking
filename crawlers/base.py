"""Selenium 공통 유틸. 모든 크롤러가 동일한 브라우저 옵션을 공유한다."""

from contextlib import contextmanager

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


@contextmanager
def new_driver(network_logging: bool = False):
    """network_logging=True는 리뷰 API 응답(JSON)을 CDP 성능 로그로 가로채야 하는
    올리브영 리뷰 수집 전용 — 다른 크롤러는 기본값(False)으로 오버헤드 없이 그대로 쓴다."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--lang=ko-KR")
    options.add_argument(f"user-agent={USER_AGENT}")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    if network_logging:
        options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    driver = webdriver.Chrome(options=options)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )
    try:
        yield driver
    finally:
        driver.quit()
