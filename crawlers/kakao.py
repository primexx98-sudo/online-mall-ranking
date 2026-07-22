"""카카오 선물하기 건강기능식품 랭킹 크롤러 (Playwright).

카테고리(서브카테고리)별로 TOP N을 수집해 하나의 리스트로 합친다.
MD추천 등 광고 상품(.area_ad)은 제외한다.
"""

from crawlers.base import new_page
from crawlers.classifier import classify
from crawlers.config import PLATFORMS

BASE_URL = "https://gift.kakao.com"


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
                results.append(
                    {
                        "카테고리": classify(item["name"], item["brand"]),
                        "순위": rank,
                        "상품명": item["name"],
                        "브랜드": item["brand"],
                        "가격": item["price"],
                        "상품URL": BASE_URL + item["href"] if item["href"] else "",
                    }
                )

    return results
