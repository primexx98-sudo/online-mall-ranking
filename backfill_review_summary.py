"""특정 날짜의 기존 xlsx에 리뷰 긍정/부정 요약만 사후 재수집해 채워 넣는다.
그날 Gemini 호출이 실패해(503/429 등) 긍정1~3/부정1~3이 빈 채로 저장된 경우
대응용 — 순위/가격/평점/건수 등 기존 데이터는 그대로 두고 리뷰 원문만 새로
가져와 재요약한다. 리뷰 원문 자체는 저장하는 컬럼이 없는 구조라(공간 절약),
그날 그 리뷰가 그대로 보존돼 있지 않고 "지금 시점" 리뷰를 다시 가져오는
것이므로 원 상품이 그새 리뷰가 늘거나 리뷰가 아예 삭제된 경우 결과가 100%
동일하지는 않을 수 있다(상품 URL 자체는 순위와 무관하게 고정이라 상품
자체를 잘못 찾아올 위험은 없음).

python backfill_review_summary.py 2026-09-08
"""

import sys

from crawlers.ai_review_summary import attach_review_summaries
from crawlers.base import new_driver
from crawlers.review import (
    fetch_daiso_review_material,
    fetch_kakao_review_material,
    fetch_oliveyoung_review_material,
)
from main import load_existing_platform_data, save_daily_excel

PLATFORM_NAMES = ["카카오선물하기", "다이소몰", "올리브영"]


def _attach_samples_requests(items: list[dict], fetch_fn) -> None:
    for item in items:
        url = item.get("상품URL")
        if not isinstance(url, str) or not url:
            continue
        item["리뷰샘플"] = fetch_fn(url).get("리뷰샘플", [])


def _attach_samples_oliveyoung(items: list[dict]) -> None:
    with new_driver(network_logging=True) as driver:
        driver.get_log("performance")  # 드라이버 기동 중 쌓인 로그 비우기 (oliveyoung.py와 동일 패턴)
        for item in items:
            url = item.get("상품URL")
            if not isinstance(url, str) or not url:
                continue
            item["리뷰샘플"] = fetch_oliveyoung_review_material(driver, url).get("리뷰샘플", [])


def main() -> None:
    if len(sys.argv) < 2:
        print("사용법: python backfill_review_summary.py YYYY-MM-DD")
        sys.exit(1)
    date_str = sys.argv[1]

    platform_data = load_existing_platform_data(date_str, PLATFORM_NAMES)
    if not platform_data:
        print(f"[백필] {date_str} 저장된 데이터 없음")
        sys.exit(1)

    if "카카오선물하기" in platform_data:
        _attach_samples_requests(platform_data["카카오선물하기"], fetch_kakao_review_material)
    if "다이소몰" in platform_data:
        _attach_samples_requests(platform_data["다이소몰"], fetch_daiso_review_material)
    if "올리브영" in platform_data:
        _attach_samples_oliveyoung(platform_data["올리브영"])

    attach_review_summaries(platform_data)
    out_path = save_daily_excel(date_str, platform_data)
    print(f"[백필] 완료: {out_path}")


if __name__ == "__main__":
    main()
