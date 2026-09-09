"""리뷰 원문을 긍정/부정 카테고리 카드로 요약.

Gemini 무료 티어는 하루 20회 호출 한도([[health-trend 프로젝트에서 실측 확인]]:
카드 6개를 개별 호출했다가 곧바로 429 RESOURCE_EXHAUSTED를 맞은 전례가 있음) —
이 프로젝트도 하루 최대 40개 상품(카카오20+다이소10+올리브영10)을 다뤄야 하므로
반드시 전체 상품을 한 번의 프롬프트에 몰아넣는 배치 호출 1회로 처리한다.
상품별/카드별 개별 호출은 절대 추가하지 말 것.
"""

import json
import os
import time

MODEL = "gemini-2.5-flash"
# 2026-09-09: gemini-flash-latest가 5회 연속(09-08 4회 + 09-09 1회) 503 UNAVAILABLE
# 반환 - 별칭이 가리키는 최신 버전이 지속 과부하 상태로 추정되어 안정된 고정 버전으로
# 전환. gemini-2.5-flash는 2026-10-16 지원 종료 예정이므로 그 전에 재점검 필요.
MAX_REVIEWS_PER_PRODUCT_IN_PROMPT = 12
MAX_REVIEW_CHARS = 200

_PROMPT_TEMPLATE = """다음은 여러 건강기능식품 상품의 실제 소비자 리뷰 샘플입니다.
상품마다 리뷰를 분석해서 긍정적인 이유 2~3개, 부정적인 이유 2~3개를 카테고리화해주세요.
각 카테고리는 "title"(6~12자 내외의 짧은 명사구)과 "desc"(리뷰 내용에 실제로 근거한 1문장 설명)로 구성합니다.
리뷰에 실제로 없는 내용은 절대 지어내지 마세요. 부정적인 리뷰가 거의 없으면 negative는 1개 또는 0개로 남겨도 됩니다.

반드시 아래 JSON 형식으로만 답하세요 (다른 설명 문장 없이 JSON 객체만 출력):
{{"products": {{"<상품id>": {{"positive": [{{"title": "...", "desc": "..."}}], "negative": [{{"title": "...", "desc": "..."}}]}}}}}}

상품 목록:
{items_block}
"""


def _build_items_block(items: list[dict]) -> str:
    blocks = []
    for item in items:
        reviews = item.get("리뷰샘플", [])[:MAX_REVIEWS_PER_PRODUCT_IN_PROMPT]
        review_lines = "\n".join(
            f"  - ({r.get('rating', '?')}점) {r['text'][:MAX_REVIEW_CHARS]}"
            for r in reviews if r.get("text")
        )
        hint = ""
        features = item.get("자체AI긍정특징")
        if features:
            hint_lines = "; ".join(f"{f['title']}: {f['desc']}" for f in features if f.get("title"))
            hint = f"\n  (참고: 플랫폼 자체 AI가 뽑은 긍정 특징 - {hint_lines})"
        blocks.append(
            f"[상품id: {item['_review_id']}] {item.get('상품명', '')} ({item.get('브랜드', '')})\n"
            f"{review_lines}{hint}"
        )
    return "\n\n".join(blocks)


def _generate_with_retry(client, prompt: str, max_retries: int = 2) -> str | None:
    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(model=MODEL, contents=prompt)
            return response.text
        except Exception as e:
            msg = str(e)
            if "RESOURCE_EXHAUSTED" in msg:
                print(f"[리뷰요약] Gemini 하루 호출 한도 초과 - 재시도 없이 포기 ({msg[:100]})")
                return None
            if attempt < max_retries:
                wait = 2 * (attempt + 1)
                print(f"[리뷰요약] Gemini 일시 오류, {wait}초 후 재시도 ({msg[:100]})")
                time.sleep(wait)
            else:
                print(f"[리뷰요약] Gemini 호출 최종 실패: {msg[:100]}")
                return None
    return None


def summarize_reviews_batch(items: list[dict]) -> dict:
    """items: 각 dict는 '_review_id'(결과 매칭용 고유키)와 '리뷰샘플'을 포함해야 함.
    반환: {review_id: {"positive": [...], "negative": [...]}} — 실패 시 빈 dict."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[리뷰요약] GEMINI_API_KEY 없음 - AI 요약 생략")
        return {}

    usable = [it for it in items if it.get("리뷰샘플")]
    if not usable:
        print("[리뷰요약] 리뷰 샘플이 있는 상품이 없음 - AI 요약 생략")
        return {}

    try:
        from google import genai
    except ImportError:
        print("[리뷰요약] google-genai 미설치 - AI 요약 생략 (pip install google-genai)")
        return {}

    client = genai.Client(api_key=api_key)
    prompt = _PROMPT_TEMPLATE.format(items_block=_build_items_block(usable))

    response_text = _generate_with_retry(client, prompt)
    if not response_text:
        return {}

    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    try:
        parsed = json.loads(cleaned.strip())
        return parsed.get("products", {})
    except Exception as e:
        print(f"[리뷰요약] 응답 파싱 실패: {e}")
        return {}


def _format_category(cat: dict) -> str:
    title = (cat.get("title") or "").strip()
    desc = (cat.get("desc") or "").strip()
    if title and desc:
        return f"{title} — {desc}"
    return title or desc


def attach_review_summaries(platform_data: dict[str, list[dict]]) -> None:
    """platform_data의 모든 상품에 긍정1~3/부정1~3 컬럼을 채운다(제자리 수정).
    AI 호출이 실패해도 예외를 던지지 않고 빈 문자열로 남긴다 — 순위 수집 자체를 막지 않기 위함."""
    all_items = []
    for platform, items in platform_data.items():
        for idx, item in enumerate(items):
            item["_review_id"] = f"{platform}::{idx}"
            all_items.append(item)

    try:
        results = summarize_reviews_batch(all_items)
    except Exception as e:
        print(f"[리뷰요약] 배치 호출 중 예외 발생, 전체 생략: {e}")
        results = {}

    for item in all_items:
        cats = results.get(item["_review_id"], {})
        positive = cats.get("positive", [])[:3]
        negative = cats.get("negative", [])[:3]
        for i in range(3):
            item[f"긍정{i+1}"] = _format_category(positive[i]) if i < len(positive) else ""
            item[f"부정{i+1}"] = _format_category(negative[i]) if i < len(negative) else ""
