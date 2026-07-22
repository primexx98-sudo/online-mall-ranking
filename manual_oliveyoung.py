"""올리브영 자동 수집이 막혔을 때, 캡쳐 이미지로 읽은 TOP10을 그날 xlsx에 주입한다.

python manual_oliveyoung.py <YYYY-MM-DD> <items.json>

items.json 형식:
[
  {"순위": 1, "브랜드": "...", "상품명": "...", "가격": "8500"},
  ...
]

절차 상세는 크롤러_실패시.md 참고.
"""

import json
import sys
from pathlib import Path

import pandas as pd

from crawlers.classifier import classify
from crawlers.config import COLUMNS
from main import build_category_stats

DATA_DIR = Path(__file__).parent / "data" / "daily"


def main() -> None:
    if len(sys.argv) != 3:
        print("사용법: python manual_oliveyoung.py <YYYY-MM-DD> <items.json>")
        sys.exit(1)

    date_str, items_path = sys.argv[1], Path(sys.argv[2])
    xlsx_path = DATA_DIR / date_str[:7] / f"{date_str}.xlsx"
    if not xlsx_path.exists():
        print(f"파일이 없습니다: {xlsx_path} (카카오·다이소가 먼저 수집되어 있어야 함)")
        sys.exit(1)

    items = json.loads(items_path.read_text(encoding="utf-8"))
    rows = []
    for item in items:
        price = str(item.get("가격", "")).replace(",", "").replace("원", "")
        rows.append(
            {
                "카테고리": classify(item["상품명"], item.get("브랜드", "")),
                "순위": item["순위"],
                "상품명": item["상품명"],
                "브랜드": item.get("브랜드", ""),
                "가격": f"{int(price):,}원" if price.isdigit() else item.get("가격", ""),
                "상품URL": "",
            }
        )
    oliveyoung_df = pd.DataFrame(rows, columns=COLUMNS).sort_values("순위")

    xls = pd.ExcelFile(xlsx_path)
    platform_data = {}
    for sheet in xls.sheet_names:
        if sheet == "카테고리통계":
            continue
        if sheet == "올리브영":
            continue
        platform_data[sheet] = pd.read_excel(xlsx_path, sheet_name=sheet).to_dict("records")
    platform_data["올리브영"] = oliveyoung_df.to_dict("records")

    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        for platform, records in platform_data.items():
            pd.DataFrame(records, columns=COLUMNS).to_excel(writer, sheet_name=platform, index=False)
        build_category_stats(platform_data).to_excel(writer, sheet_name="카테고리통계", index=False)

    print(f"올리브영 {len(rows)}건 반영 완료: {xlsx_path}")


if __name__ == "__main__":
    main()
