"""다이소몰 건강식품 실시간 랭킹 크롤러 (Selenium).

목록 카드에는 브랜드가 없어 TOP N 상세페이지를 추가 방문해 브랜드를 보강한다.
"""

import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from crawlers.base import new_driver
from crawlers.classifier import classify
from crawlers.config import PLATFORMS

BASE_URL = "https://www.daisomall.co.kr"
RANK_SELECTOR = ".nav-rank .swiper-slide"

_EXTRACT_JS = """
    return Array.from(document.querySelectorAll('.nav-rank .swiper-slide')).map(el => ({
        name: el.querySelector('.product-title')?.innerText?.trim() || '',
        price: el.querySelector('.price-value')?.innerText?.replace(/\\s+/g, '') || '',
        href: el.querySelector('a.detail-link')?.getAttribute('href') || '',
    }));
"""

_DETAIL_JS = """
    return {
        brand: document.querySelector('.brand-area .detail-title')?.innerText?.trim() || '',
        image: document.querySelector("meta[property='og:image']")?.content || '',
    };
"""


def crawl_daiso() -> list[dict]:
    config = PLATFORMS["다이소몰"]
    top_n = config["top_n"]

    with new_driver() as driver:
        driver.get(config["url"])
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, RANK_SELECTOR))
        )
        time.sleep(1.5)

        items = driver.execute_script(_EXTRACT_JS)[:top_n]

        main_window = driver.current_window_handle
        for item in items:
            item["brand"] = ""
            item["image"] = ""
            if not item["href"]:
                continue

            driver.switch_to.new_window("tab")
            try:
                driver.get(BASE_URL + item["href"])
                WebDriverWait(driver, 8).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".brand-area .detail-title"))
                )
                detail = driver.execute_script(_DETAIL_JS)
                item["brand"] = detail["brand"]
                item["image"] = detail["image"]
            except Exception:
                pass
            finally:
                driver.close()
                driver.switch_to.window(main_window)

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
                "상품URL": BASE_URL + item["href"] if item["href"] else "",
                "이미지URL": item["image"],
            }
        )
    return results
