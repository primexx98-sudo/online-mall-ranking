"""올리브영 건강식품 판매랭킹 크롤러 (Selenium).

Playwright로는 GitHub Actions(Azure IP)에서 Cloudflare Turnstile에 막혔으나,
Selenium + 충분한 sleep 방식은 동일 환경에서 4회 연속 통과 검증됨(기록.md
2026-07-22 "Selenium 실증 테스트 결과" 참고). 그래도 재차단 시엔
manual_oliveyoung.py로 캡쳐 기반 수동 입력 (크롤러_실패시.md 참고).
"""

import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

from crawlers.classifier import classify
from crawlers.config import PLATFORMS

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
ITEM_SELECTOR = "ul.cate_prd_list > li"


def _new_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(f"user-agent={USER_AGENT}")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=options)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )
    return driver


def crawl_oliveyoung() -> list[dict]:
    config = PLATFORMS["올리브영"]
    top_n = config["top_n"]
    url = f"{config['url']}&pageIdx=1&rowsPerPage={top_n}"

    driver = _new_driver()
    try:
        driver.get(url)
        time.sleep(8)

        elements = driver.find_elements(By.CSS_SELECTOR, ITEM_SELECTOR)
        if not elements:
            time.sleep(12)
            elements = driver.find_elements(By.CSS_SELECTOR, ITEM_SELECTOR)

        items = []
        for el in elements[:top_n]:
            def text_of(selector: str) -> str:
                try:
                    return el.find_element(By.CSS_SELECTOR, selector).text.strip()
                except Exception:
                    return ""

            try:
                href = el.find_element(By.CSS_SELECTOR, "a").get_attribute("href") or ""
            except Exception:
                href = ""

            items.append(
                {
                    "brand": text_of("span.tx_brand"),
                    "name": text_of("p.tx_name"),
                    "price": text_of(".tx_cur").rstrip("~").strip(),
                    "href": href,
                }
            )
    finally:
        driver.quit()

    results = []
    for rank, item in enumerate(items, start=1):
        if not item["name"]:
            continue
        results.append(
            {
                "카테고리": classify(item["name"], item["brand"]),
                "순위": rank,
                "상품명": item["name"],
                "브랜드": item["brand"],
                "가격": item["price"],
                "상품URL": item["href"],
            }
        )
    return results
