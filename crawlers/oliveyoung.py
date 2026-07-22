"""올리브영 건강식품 판매랭킹 크롤러 (Playwright).

Cloudflare Turnstile로 GitHub Actions(Azure IP)에서 막힐 수 있음 — 실패 시
manual_oliveyoung.py로 캡쳐 기반 수동 입력 (자세한 배경은 크롤러_실패시.md 참고).
"""

from crawlers.base import new_page
from crawlers.classifier import classify
from crawlers.config import PLATFORMS

ITEM_SELECTOR = "ul.cate_prd_list > li"


def crawl_oliveyoung() -> list[dict]:
    config = PLATFORMS["올리브영"]
    top_n = config["top_n"]
    url = f"{config['url']}&pageIdx=1&rowsPerPage={top_n}"

    with new_page() as page:
        page.goto(url, timeout=30000)
        page.wait_for_selector(ITEM_SELECTOR, timeout=15000)
        page.wait_for_timeout(1500)

        items = page.eval_on_selector_all(
            ITEM_SELECTOR,
            """
            els => els.map(el => ({
                brand: el.querySelector('span.tx_brand')?.innerText?.trim() || '',
                name: el.querySelector('p.tx_name')?.innerText?.trim() || '',
                price: el.querySelector('.tx_cur')?.innerText?.trim().replace(/~$/, '').trim() || '',
                href: el.querySelector('a')?.getAttribute('href') || '',
            }))
            """,
        )

    results = []
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
                "상품URL": item["href"],
            }
        )
    return results
