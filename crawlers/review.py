"""리뷰 원문(평점·건수·리뷰 텍스트 샘플) 수집 — AI 긍정/부정 요약(ai_review_summary.py)의 재료를 만든다.

2026-09-08 라이브 테스트로 확인한 각 플랫폼의 실제 리뷰 API:
- 카카오선물하기: gift.kakao.com 자체 API. Cloudflare 없이 requests만으로 200 응답.
- 다이소몰: fapi.daisomall.co.kr 자체 API. 역시 requests만으로 200 응답.
- 올리브영: m.oliveyoung.co.kr 리뷰 API가 Cloudflare로 보호돼 requests 직접호출은 403 —
  이미 크롤링에 쓰던 Selenium 세션(성능 로그 활성화) 안에서 상세페이지를 열어야만 통과한다.
"""

import json
import re
import time

import requests

from crawlers.base import USER_AGENT

MAX_REVIEWS_PER_PRODUCT = 15
# 2026-09-09: 카카오 sortProperty="SCORE", 다이소 sortCond="RCM"(추천순)으로 가져오던
# 초기 구현이 부정 리뷰를 체계적으로 걸러내고 있었음이 라이브 테스트로 드러남 — 같은
# 상품을 "SCORE"/"RCM"으로 조회하면 별점이 좁은 범위(4~5점)에만 몰리는데, "LATEST"로
# 바꾸면 같은 상품에서 1~2점 리뷰가 그대로 잡힘(사용자가 "부정 리뷰가 너무 없다"고
# 지적해 확인). 그 결과 ai_review_summary.py가 실제로는 존재하는 부정 포인트를 못
# 찾아 "특별한 불만이 발견되지 않았어요"만 계속 뜨는 원인이었음 — 최신순으로 전환.


# ---------------------------------------------------------------- 카카오선물하기 ----

def _kakao_product_id(url: str) -> str | None:
    m = re.search(r"/product/(\d+)", url or "")
    return m.group(1) if m else None


def fetch_kakao_review_material(product_url: str) -> dict:
    product_id = _kakao_product_id(product_url)
    if not product_id:
        return {}
    headers = {"User-Agent": USER_AGENT, "Referer": product_url}
    try:
        stat = requests.get(
            f"https://gift.kakao.com/a/product-detail/v1/review/products/{product_id}/stat",
            headers=headers, timeout=10,
        ).json()
        review_list = requests.get(
            f"https://gift.kakao.com/a/product-detail/v2/review/products/{product_id}",
            params={"page": 0, "sortProperty": "LATEST", "size": MAX_REVIEWS_PER_PRODUCT},
            headers=headers, timeout=10,
        ).json()
    except Exception:
        return {}

    contents = review_list.get("reviewList", {}).get("contents", []) or []
    reviews = [
        {"rating": c.get("product", {}).get("rating"), "text": c.get("content", "").strip()}
        for c in contents if c.get("content")
    ]
    return {
        "리뷰평점": stat.get("averageProductRating"),
        "리뷰건수": stat.get("totalCount"),
        "리뷰샘플": reviews,
    }


# -------------------------------------------------------------------- 다이소몰 ----

def _daiso_pdno(url: str) -> str | None:
    m = re.search(r"[?&]pdNo=(\d+)", url or "")
    return m.group(1) if m else None


def fetch_daiso_review_material(product_url: str) -> dict:
    pdno = _daiso_pdno(product_url)
    if not pdno:
        return {}
    headers = {
        "User-Agent": USER_AGENT,
        "Referer": product_url,
        "Content-Type": "application/json",
        "Origin": "https://www.daisomall.co.kr",
    }
    try:
        attr = requests.post(
            "https://fapi.daisomall.co.kr/pd/pds/revw/selRevwAttr",
            headers=headers, json={"pdNo": pdno}, timeout=10,
        ).json()
        review_list = requests.post(
            "https://fapi.daisomall.co.kr/pd/pds/revw/selRevwList",
            headers=headers,
            json={
                "pdNo": pdno, "pageSize": MAX_REVIEWS_PER_PRODUCT, "currentPage": 1,
                "filter": "ALL", "sortCond": "LATEST", "useCommonPaging": False,
                "cttsOnlyYn": "N", "onldPdNoList": [],
            },
            timeout=10,
        ).json()
    except Exception:
        return {}

    pd_revw = (attr.get("data") or {}).get("pdRevw", {}) if attr.get("success") else {}
    items = (review_list.get("data") or {}).get("pdRevwList", []) if review_list.get("success") else []
    reviews = [
        {"rating": it.get("stscVal"), "text": (it.get("revwCn") or "").replace("&nbsp;", " ").strip()}
        for it in items if it.get("revwCn")
    ]
    # 다이소 API는 revwAvg를 숫자가 아니라 문자열("4.8")로 내려줘서, 그대로 저장하면
    # 소비 측(health-trend 등)에서 f"{rating:.1f}" 같은 숫자 포맷팅이 깨진다.
    raw_avg = pd_revw.get("revwAvg")
    try:
        avg_score = float(raw_avg) if raw_avg not in (None, "") else None
    except (TypeError, ValueError):
        avg_score = None
    return {
        "리뷰평점": avg_score,
        "리뷰건수": pd_revw.get("revwCnt"),
        "긍정비율": pd_revw.get("revwPositive"),
        "리뷰샘플": reviews,
    }


# -------------------------------------------------------------------- 올리브영 ----
# Cloudflare 때문에 requests 직접호출이 불가 — 반드시 network_logging=True로 연 Selenium
# 세션(oliveyoung.py가 크롤링에 쓰던 것과 동일 드라이버) 안에서만 호출해야 한다.

def fetch_oliveyoung_review_material(driver, product_url: str) -> dict:
    review_url = product_url + ("&tab=review" if "?" in product_url else "?tab=review")
    try:
        driver.get(review_url)
        time.sleep(6)
        driver.execute_script("window.scrollBy(0, 1200);")
        time.sleep(2)
    except Exception:
        return {}

    summary_body = None
    stat_body = None
    review_texts: list[dict] = []

    try:
        logs = driver.get_log("performance")
    except Exception:
        logs = []

    for entry in logs:
        try:
            msg = json.loads(entry["message"])["message"]
        except Exception:
            continue
        if msg.get("method") != "Network.responseReceived":
            continue
        params = msg["params"]
        url = params.get("response", {}).get("url", "")
        request_id = params.get("requestId")
        if "/review/api/v1/reviews/" in url and url.endswith("/summary"):
            summary_body = _get_json_body(driver, request_id)
        elif "/review/api/v2/reviews/" in url and url.endswith("/stats"):
            stat_body = _get_json_body(driver, request_id)
        elif "/review/api/v2/post/" in url and url.endswith("/list"):
            body = _get_json_body(driver, request_id)
            if body:
                for post in body.get("data", []) or []:
                    content = (post.get("content") or "").strip()
                    if content:
                        review_texts.append({"rating": None, "text": content})

    result: dict = {"리뷰샘플": review_texts[:MAX_REVIEWS_PER_PRODUCT]}
    if stat_body and stat_body.get("data"):
        stat_data = stat_body["data"]
        result["리뷰평점"] = (stat_data.get("ratingDistribution") or {}).get("averageRating")
        result["리뷰건수"] = stat_data.get("reviewCount")
    if summary_body and summary_body.get("data"):
        data = summary_body["data"]
        result["긍정비율"] = data.get("positiveRatio")
        result["부정비율"] = data.get("negativeRatio")
        result["자체AI긍정특징"] = [
            {"title": data.get(f"feature{i}Title"), "desc": data.get(f"feature{i}Description")}
            for i in (1, 2, 3) if data.get(f"feature{i}Title")
        ]
    return result


def _get_json_body(driver, request_id: str) -> dict | None:
    if not request_id:
        return None
    try:
        body = driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": request_id})
        return json.loads(body.get("body", "{}"))
    except Exception:
        return None
