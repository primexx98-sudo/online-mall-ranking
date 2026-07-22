"""다이소몰 건강식품 실시간 랭킹 크롤러 (Playwright).

목록 카드에는 브랜드가 없어 TOP N 상세페이지를 추가 방문해 브랜드를 보강한다.
"""

from crawlers.base import new_page
from crawlers.classifier import classify
from crawlers.config import PLATFORMS

BASE_URL = "https://www.daisomall.co.kr"
RANK_SELECTOR = ".nav-rank .swiper-slide"


def crawl_daiso() -> list[dict]:
    config = PLATFORMS["다이소몰"]
    top_n = config["top_n"]

    with new_page() as page:
        page.goto(config["url"], timeout=30000)
        page.wait_for_selector(RANK_SELECTOR, timeout=15000)
        page.wait_for_timeout(1500)

        items = page.eval_on_selector_all(
            RANK_SELECTOR,
            """
            els => els.map(el => ({
                name: el.querySelector('.product-title')?.innerText?.trim() || '',
                price: el.querySelector('.price-value')?.innerText?.replace(/\\s+/g, '') || '',
                href: el.querySelector('a.detail-link')?.getAttribute('href') || '',
            }))
            """,
        )
        items = items[:top_n]

        for item in items:
            item["brand"] = ""
            item["image"] = ""
            if not item["href"]:
                continue
            detail_page = page.context.new_page()
            try:
                detail_page.goto(BASE_URL + item["href"], timeout=20000)
                detail_page.wait_for_selector(".brand-area .detail-title", timeout=8000)
                item["brand"] = detail_page.eval_on_selector(
                    ".brand-area .detail-title", "el => el.innerText.trim()"
                )
                item["image"] = detail_page.eval_on_selector(
                    "meta[property='og:image']", "el => el.content"
                ) or ""
            except Exception:
                pass
            finally:
                detail_page.close()

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
