"""카카오 선물하기 건강기능식품 랭킹 크롤러 (Selenium).

카테고리(서브카테고리)별로 TOP N을 수집해 하나의 리스트로 합친다.
MD추천 등 광고 상품(.area_ad)은 제외한다.
"""

import time

import requests
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from crawlers.base import USER_AGENT, new_driver
from crawlers.classifier import classify
from crawlers.config import PLATFORMS

BASE_URL = "https://gift.kakao.com"
ITEM_SELECTOR = "gc-product"

_EXTRACT_JS = """
    return Array.from(document.querySelectorAll('gc-product'))
        .filter(el => !el.querySelector('.area_ad'))
        .map(el => ({
            brand: el.querySelector('span.txt_prdbrand')?.innerText?.trim() || '',
            name: el.querySelector('strong.txt_prdname')?.innerText?.trim() || '',
            price: el.querySelector('.txt_price')?.innerText?.trim() || '',
            href: el.querySelector('a.link_prdunit')?.getAttribute('href') || '',
        }));
"""


def _fetch_og_image(url: str) -> str:
    """목록 카드의 썸네일은 지연 로딩이라 기본 이미지만 잡혀서, 상세페이지 og:image를 대신 사용한다."""
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        og = soup.find("meta", property="og:image")
        return og["content"] if og else ""
    except Exception:
        return ""


def crawl_kakao() -> list[dict]:
    config = PLATFORMS["카카오선물하기"]
    top_n = config["top_n"]
    results: list[dict] = []

    with new_driver() as driver:
        for category in config["categories"]:
            driver.get(category["url"])
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ITEM_SELECTOR))
            )
            time.sleep(1.5)

            items = driver.execute_script(_EXTRACT_JS)

            for rank, item in enumerate(items[:top_n], start=1):
                if not item["name"]:
                    continue
                product_url = BASE_URL + item["href"] if item["href"] else ""
                results.append(
                    {
                        "카테고리": classify(item["name"], item["brand"]),
                        "순위": rank,
                        "상품명": item["name"],
                        "브랜드": item["brand"],
                        "가격": item["price"],
                        "상품URL": product_url,
                        "이미지URL": _fetch_og_image(product_url) if product_url else "",
                    }
                )

    return results
