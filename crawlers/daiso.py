"""다이소몰 건강기능식품 판매량순 랭킹 크롤러 (Selenium).

2026-11-22: 다이소몰 개편(2025-10 말 추정)으로 기존 건강식품 카테고리
페이지(CTGR_01020)의 실시간 랭킹 영역(`.nav-rank`)이 사라져 10/24부터 매일
타임아웃으로 실패하던 것을, 건강기능식품 하위 카테고리(CTGR_01031) 상품 목록을
"판매량순"으로 정렬해 수집하는 방식으로 교체했다. 정렬은 URL 파라미터가 없고
버튼 클릭으로만 바뀐다(기본값은 추천순).

목록에는 같은 상품의 "대량주문(12개 묶음)" 버전이 pdNo가 'B'로 시작하는 별도
카드로 바로 뒤에 붙어 나오므로 제외한다(그대로 두면 TOP10의 절반이 중복).
목록 카드에는 브랜드가 없어 TOP N 상세페이지를 추가 방문해 브랜드를 보강한다.
"""

import re
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from crawlers.base import new_driver
from crawlers.classifier import classify
from crawlers.config import PLATFORMS
from crawlers.review import fetch_daiso_review_material

BASE_URL = "https://www.daisomall.co.kr"
CARD_SELECTOR = ".product-card .product-title"
SORT_LABEL = "판매량순"
SORT_BUTTON_XPATH = (
    "//button[contains(@class,'selection-text')]"
    f"[.//span[@class='name' and normalize-space()='{SORT_LABEL}']]"
)
MAX_SCROLLS = 5

_EXTRACT_JS = """
    return Array.from(document.querySelectorAll('.product-card')).map(el => ({
        name: el.querySelector('.product-title')?.innerText?.trim() || '',
        price: el.querySelector('.price-value')?.innerText?.replace(/\\s+/g, '') || '',
        href: el.querySelector('a.detail-link')?.getAttribute('href') || '',
        presale: (el.innerText || '').includes('알림신청'),
    }));
"""

_DETAIL_JS = """
    return {
        brand: document.querySelector('.brand-area .detail-title')?.innerText?.trim() || '',
        image: document.querySelector("meta[property='og:image']")?.content || '',
    };
"""


def _pdno(href: str) -> str:
    m = re.search(r"[?&]pdNo=([^&]+)", href or "")
    return m.group(1) if m else ""


def _collect_items(driver, top_n: int) -> list[dict]:
    """판매량순 목록에서 중복·대량주문·판매예정 카드를 걸러 top_n개를 모은다.
    목록이 가상 스크롤(ds-virtual-product-list)이라 부족하면 스크롤하며 누적."""
    items, seen = [], set()
    for _ in range(MAX_SCROLLS + 1):
        for card in driver.execute_script(_EXTRACT_JS):
            pdno = _pdno(card["href"])
            if not pdno or pdno in seen:
                continue
            seen.add(pdno)
            if pdno.startswith("B") or card["presale"] or not card["name"]:
                continue
            items.append(card)
        if len(items) >= top_n:
            break
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.5)
    return items[:top_n]


def crawl_daiso() -> list[dict]:
    config = PLATFORMS["다이소몰"]
    top_n = config["top_n"]

    with new_driver() as driver:
        driver.get(config["url"])
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, CARD_SELECTOR))
        )
        time.sleep(1.5)

        # 판매량순 정렬 — 정렬이 실제로 적용되지 않으면(버튼 못 찾음/활성화 안 됨)
        # 추천순 목록을 랭킹으로 잘못 저장하지 않도록 예외로 실패 처리(재시도 대상).
        sort_btn = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, SORT_BUTTON_XPATH))
        )
        driver.execute_script("arguments[0].click();", sort_btn)
        WebDriverWait(driver, 10).until(
            lambda d: "is-active" in (sort_btn.get_attribute("class") or "")
        )
        time.sleep(2.5)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, CARD_SELECTOR))
        )

        items = _collect_items(driver, top_n)

        main_window = driver.current_window_handle
        for item in items:
            item["brand"] = ""
            item["image"] = ""

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
        results.append(
            {
                "카테고리": classify(item["name"], item["brand"]),
                "순위": rank,
                "상품명": item["name"],
                "브랜드": item["brand"],
                "가격": item["price"],
                "상품URL": BASE_URL + item["href"],
                "이미지URL": item["image"],
            }
        )

    for item in results:
        item.update(fetch_daiso_review_material(item["상품URL"]))

    return results
