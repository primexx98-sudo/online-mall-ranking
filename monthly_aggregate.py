"""월별 취합: 일별 데이터를 모아 플랫폼별 월간 TOP20 + 카테고리 통계를 산출한다.

python monthly_aggregate.py            # 지난달 집계
python monthly_aggregate.py YYYY-MM    # 특정 월 집계

점수 공식 (기록.md 2026-07-01 인터뷰에서 확정한 로직을 그대로 사용):
  일별점수 = (11 - 순위) × 0.5              1위=5점 ... 10위=0.5점
  평균점수 = sum(일별점수) / 등장횟수
  등장률   = 등장횟수 / 실제수집일수
  월간점수 = 평균점수×0.7 + (등장률×5)×0.3   순위 질 70% + 꾸준함 30%
  최소등장 = min(3, 실제수집일수), 필터 후 20개 미만이면 2회→1회로 완화
"""

import sys
from datetime import datetime
from pathlib import Path

import openpyxl
import pandas as pd

from crawlers.config import COLUMNS

DAILY_DIR = Path(__file__).parent / "data" / "daily"
MONTHLY_DIR = Path(__file__).parent / "data" / "monthly"

PLATFORM_SHEETS = ["카카오선물하기", "다이소몰", "올리브영"]
TOP_N = 20


def prev_year_month(year_month: str) -> str:
    year, month = map(int, year_month.split("-"))
    if month == 1:
        return f"{year - 1}-12"
    return f"{year}-{month - 1:02d}"


def load_daily_files(year_month: str) -> list[Path]:
    month_dir = DAILY_DIR / year_month
    if not month_dir.exists():
        return []
    return sorted(month_dir.glob("*.xlsx"))


def load_previous_month(year_month: str) -> dict[str, pd.DataFrame]:
    prev_path = MONTHLY_DIR / f"{prev_year_month(year_month)}_월별취합.xlsx"
    if not prev_path.exists():
        return {}
    xls = pd.ExcelFile(prev_path)
    return {sheet: pd.read_excel(prev_path, sheet_name=sheet) for sheet in xls.sheet_names}


def parse_saved_price(price_str) -> float | None:
    if not isinstance(price_str, str):
        return None
    digits = "".join(c for c in price_str if c.isdigit())
    return float(digits) if digits else None


def score_platform(daily_files: list[Path], sheet_name: str) -> pd.DataFrame:
    records = []
    for f in daily_files:
        try:
            df = pd.read_excel(f, sheet_name=sheet_name)
        except ValueError:
            continue
        for _, row in df.iterrows():
            records.append(
                {
                    "상품명": row["상품명"],
                    "브랜드": row["브랜드"],
                    "카테고리": row["카테고리"],
                    "순위": row["순위"],
                    "가격": row["가격"],
                }
            )

    if not records:
        return pd.DataFrame()

    all_df = pd.DataFrame(records)
    all_df["일별점수"] = (11 - all_df["순위"]) * 0.5
    실제수집일수 = len(daily_files)

    grouped = all_df.groupby(["상품명", "브랜드"])
    agg = grouped.agg(
        카테고리=("카테고리", "first"),
        평균순위=("순위", "mean"),
        등장횟수=("일별점수", "count"),
        평균점수=("일별점수", "mean"),
        평균가격=("가격", lambda s: pd.Series([parse_saved_price(x) for x in s]).mean()),
    ).reset_index()

    agg["등장률"] = agg["등장횟수"] / 실제수집일수
    agg["월간점수"] = agg["평균점수"] * 0.7 + (agg["등장률"] * 5) * 0.3

    min_appearance = min(3, 실제수집일수)
    for threshold in [min_appearance, 2, 1]:
        filtered = agg[agg["등장횟수"] >= threshold]
        if len(filtered) >= TOP_N or threshold == 1:
            break

    top = filtered.sort_values("월간점수", ascending=False).head(TOP_N).copy()
    top["평균순위"] = top["평균순위"].round(1)
    top["평균가격"] = top["평균가격"].round(0)
    top = top.reset_index(drop=True)
    top.insert(0, "순위(월평균)", top.index + 1)
    return top[["순위(월평균)", "카테고리", "상품명", "브랜드", "평균가격", "평균순위", "등장횟수"]]


def add_previous_comparison(top: pd.DataFrame, prev_df: pd.DataFrame | None) -> pd.DataFrame:
    top = top.copy()
    top["전월가격"] = None
    top["가격변동"] = None
    top["전월순위"] = None
    top["순위변동"] = "🆕"

    if prev_df is None or prev_df.empty:
        return top

    prev_lookup = {(row["상품명"], row["브랜드"]): row for _, row in prev_df.iterrows()}

    for i, row in top.iterrows():
        key = (row["상품명"], row["브랜드"])
        prev = prev_lookup.get(key)
        if prev is None:
            continue
        prev_price = prev.get("평균가격")
        prev_rank = prev.get("순위(월평균)")
        if pd.notna(prev_price):
            top.at[i, "전월가격"] = prev_price
            diff = row["평균가격"] - prev_price
            top.at[i, "가격변동"] = f"▲{diff:,.0f}원" if diff > 0 else (f"▼{abs(diff):,.0f}원" if diff < 0 else "-")
        if pd.notna(prev_rank):
            top.at[i, "전월순위"] = prev_rank
            diff = prev_rank - row["순위(월평균)"]
            top.at[i, "순위변동"] = f"▲{diff:.0f}" if diff > 0 else (f"▼{abs(diff):.0f}" if diff < 0 else "-")

    return top


def build_category_stats(platform_tops: dict[str, pd.DataFrame], prev_stats: pd.DataFrame | None) -> pd.DataFrame:
    counts: dict[str, dict[str, int]] = {}
    for platform, df in platform_tops.items():
        if df.empty:
            continue
        for cat, cnt in df["카테고리"].value_counts().items():
            counts.setdefault(cat, {p: 0 for p in platform_tops})[platform] = cnt

    total_all = sum(sum(v.values()) for v in counts.values())
    rows = []
    for cat, per_platform in counts.items():
        total = sum(per_platform.values())
        row = {"카테고리": cat, "전체": total, "비율(%)": round(total / total_all * 100, 1) if total_all else 0}
        row.update(per_platform)
        rows.append(row)
    stats_df = pd.DataFrame(rows).sort_values("전체", ascending=False).reset_index(drop=True)

    stats_df["전월비율(%)"] = None
    stats_df["증감(%p)"] = None
    if prev_stats is not None and not prev_stats.empty:
        prev_lookup = dict(zip(prev_stats["카테고리"], prev_stats["비율(%)"]))
        for i, row in stats_df.iterrows():
            prev_ratio = prev_lookup.get(row["카테고리"])
            if prev_ratio is not None:
                stats_df.at[i, "전월비율(%)"] = prev_ratio
                stats_df.at[i, "증감(%p)"] = round(row["비율(%)"] - prev_ratio, 1)

    return stats_df


def run(year_month: str) -> Path:
    daily_files = load_daily_files(year_month)
    if not daily_files:
        raise SystemExit(f"{year_month} 일별 데이터가 없습니다: {DAILY_DIR / year_month}")

    prev_sheets = load_previous_month(year_month)

    platform_tops = {}
    for sheet in PLATFORM_SHEETS:
        top = score_platform(daily_files, sheet)
        if top.empty:
            platform_tops[sheet] = top
            continue
        platform_tops[sheet] = add_previous_comparison(top, prev_sheets.get(sheet))

    category_stats = build_category_stats(
        {k: v for k, v in platform_tops.items()}, prev_sheets.get("카테고리통계")
    )

    MONTHLY_DIR.mkdir(parents=True, exist_ok=True)
    out_path = MONTHLY_DIR / f"{year_month}_월별취합.xlsx"
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        for sheet, df in platform_tops.items():
            (df if not df.empty else pd.DataFrame(columns=["안내"])).to_excel(
                writer, sheet_name=sheet, index=False
            )
        category_stats.to_excel(writer, sheet_name="카테고리통계", index=False)

    return out_path


def main():
    if len(sys.argv) > 1:
        year_month = sys.argv[1]
    else:
        today = datetime.now()
        year_month = prev_year_month(today.strftime("%Y-%m"))

    out_path = run(year_month)
    print(f"저장 완료: {out_path}")


if __name__ == "__main__":
    main()
