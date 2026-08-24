"""일별 수집 진입점.

python main.py               # 오늘 날짜로 저장
python main.py TEST          # data/daily/TEST/TEST.xlsx 로 저장 (실제 날짜 폴더 오염 없이 테스트)
"""

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from crawlers.config import COLUMNS, PLATFORMS
from crawlers.daiso import crawl_daiso
from crawlers.excel_image import insert_card_sheet, insert_image_column
from crawlers.kakao import crawl_kakao
from crawlers.notify import notify_kakao_failure
from crawlers.oliveyoung import crawl_oliveyoung

DATA_DIR = Path(__file__).parent / "data" / "daily"


def build_category_stats(platform_data: dict[str, list[dict]]) -> pd.DataFrame:
    rows = []
    all_categories = set()
    for items in platform_data.values():
        for item in items:
            all_categories.add(item["카테고리"])

    counts = {cat: {p: 0 for p in platform_data} for cat in all_categories}
    for platform, items in platform_data.items():
        for item in items:
            counts[item["카테고리"]][platform] += 1

    total_all = sum(len(items) for items in platform_data.values())
    for cat, per_platform in sorted(counts.items(), key=lambda x: -sum(x[1].values())):
        total = sum(per_platform.values())
        row = {"카테고리": cat, "전체": total, "비율(%)": round(total / total_all * 100, 1) if total_all else 0}
        row.update(per_platform)
        rows.append(row)
    return pd.DataFrame(rows)


def build_card_blocks(platform: str, items: list[dict]) -> list[tuple[str, list[dict]]]:
    """카카오선물하기는 서브카테고리 2개(각 top_n)가 이어붙어 있어 순위가 1위부터 두 번
    반복된다 — 카드형 시트를 한 줄로 펼치면 가로 스크롤이 너무 길어지므로(2026-08-24
    사용자 피드백) 서브카테고리별로 블록을 나눠 세로로 쌓는다. 그 외 플랫폼은 단일 블록."""
    config = PLATFORMS.get(platform, {})
    categories = config.get("categories")
    if not categories:
        return [(platform, items)]

    top_n = config["top_n"]
    blocks = []
    for i, cat in enumerate(categories):
        chunk = items[i * top_n:(i + 1) * top_n]
        if chunk:
            blocks.append((cat["name"], chunk))
    return blocks


def save_daily_excel(date_str: str, platform_data: dict[str, list[dict]]) -> Path:
    year_month = date_str[:7] if date_str != "TEST" else "TEST"
    out_dir = DATA_DIR / year_month
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{date_str}.xlsx"

    image_cache: dict = {}  # 같은 상품이 표 시트(작게)·카드형 시트(크게) 양쪽에 들어가므로
    # 원본 다운로드를 1회로 줄이기 위한 URL→바이트 캐시 (crawlers/excel_image.py 참고)

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        for platform, items in platform_data.items():
            df = pd.DataFrame(items, columns=COLUMNS)
            df.to_excel(writer, sheet_name=platform, index=False)
            insert_image_column(writer.sheets[platform], df["이미지URL"].tolist(), cache=image_cache)
            insert_card_sheet(writer.book, f"{platform}_카드형", build_card_blocks(platform, items), cache=image_cache)
        stats_df = build_category_stats(platform_data)
        stats_df.to_excel(writer, sheet_name="카테고리통계", index=False)

    return out_path


def main() -> None:
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")

    platform_data: dict[str, list[dict]] = {}
    failed: list[str] = []

    for name, crawl_fn in [
        ("카카오선물하기", crawl_kakao),
        ("다이소몰", crawl_daiso),
        ("올리브영", crawl_oliveyoung),
    ]:
        try:
            items = crawl_fn()
            if not items:
                raise RuntimeError("수집 결과 0건")
            platform_data[name] = items
            print(f"[OK] {name}: {len(items)}건")
        except Exception as e:
            print(f"[FAIL] {name}: {e}")
            failed.append(name)

    if not platform_data:
        print("모든 플랫폼 수집 실패 - 저장 생략")
        notify_kakao_failure(failed, date_str)
        sys.exit(1)

    out_path = save_daily_excel(date_str, platform_data)
    print(f"저장 완료: {out_path}")

    if failed:
        print(f"실패한 플랫폼: {', '.join(failed)}")
        notify_kakao_failure(failed, date_str)
        sys.exit(1)


if __name__ == "__main__":
    main()
