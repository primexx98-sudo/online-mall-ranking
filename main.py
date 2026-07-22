"""일별 수집 진입점.

python main.py               # 오늘 날짜로 저장
python main.py TEST          # data/daily/TEST/TEST.xlsx 로 저장 (실제 날짜 폴더 오염 없이 테스트)
"""

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from crawlers.config import COLUMNS
from crawlers.daiso import crawl_daiso
from crawlers.kakao import crawl_kakao
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


def save_daily_excel(date_str: str, platform_data: dict[str, list[dict]]) -> Path:
    year_month = date_str[:7] if date_str != "TEST" else "TEST"
    out_dir = DATA_DIR / year_month
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{date_str}.xlsx"

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        for platform, items in platform_data.items():
            df = pd.DataFrame(items, columns=COLUMNS)
            df.to_excel(writer, sheet_name=platform, index=False)
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
        sys.exit(1)

    out_path = save_daily_excel(date_str, platform_data)
    print(f"저장 완료: {out_path}")

    if failed:
        print(f"실패한 플랫폼: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
