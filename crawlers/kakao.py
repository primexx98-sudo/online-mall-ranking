"""카카오 선물하기 건강기능식품 랭킹 크롤러 (Playwright).

카테고리(서브카테고리)별로 TOP N을 수집해 하나의 리스트로 합친다.
MD추천 등 광고 상품(.area_ad)은 제외한다.
"""

import requests
from bs4 import BeautifulSoup

from crawlers.base import new_page
from crawlers.classifier import classify
from crawlers.config import PLATFORMS

BASE_URL = "https://gift.kakao.com"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


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

    with new_page() as page:
        for category in config["categories"]:
            page.goto(category["url"], timeout=30000)
            page.wait_for_selector("gc-product", timeout=15000)
            page.wait_for_timeout(1500)

            items = page.eval_on_selector_all(
                "gc-product",
                """
                els => els
                    .filter(el => !el.querySelector('.area_ad'))
                    .map(el => ({
                        brand: el.querySelector('span.txt_prdbrand')?.innerText?.trim() || '',
                        name: el.querySelector('strong.txt_prdname')?.innerText?.trim() || '',
                        price: el.querySelector('.txt_price')?.innerText?.trim() || '',
                        href: el.querySelector('a.link_prdunit')?.getAttribute('href') || '',
                    }))
                """,
            )

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
