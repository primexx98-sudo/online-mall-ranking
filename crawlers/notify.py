"""실패 알림 - 카카오톡 나에게 보내기.

REST_API_KEY·REFRESH_TOKEN은 GitHub Secrets(KAKAO_REST_API_KEY,
KAKAO_REFRESH_TOKEN)로 주입된다. 로컬 실행 시엔 동일한 이름의 환경변수를
설정해야 동작하며, 둘 중 하나라도 없으면 알림만 건너뛰고 크롤링/저장은
그대로 진행한다(크롤러_실패시.md 참고).
"""

import json
import os

import requests

TOKEN_URL = "https://kauth.kakao.com/oauth/token"
SEND_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
ACTIONS_URL = "https://github.com/primexx98-sudo/online-mall-ranking/actions"


def _get_access_token() -> str | None:
    rest_api_key = os.environ.get("KAKAO_REST_API_KEY")
    refresh_token = os.environ.get("KAKAO_REFRESH_TOKEN")
    if not rest_api_key or not refresh_token:
        return None

    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "client_id": rest_api_key,
            "refresh_token": refresh_token,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def notify_kakao_failure(failed: list[str], date_str: str) -> None:
    """실패한 플랫폼이 있을 때 카카오톡으로 알림을 보낸다.

    알림 자체의 실패(토큰 미설정, API 오류 등)는 예외를 삼키고 print만
    남긴다 — 알림 실패가 크롤링/저장 실패로 번지면 안 됨.
    """
    try:
        access_token = _get_access_token()
        if not access_token:
            print("[알림 생략] KAKAO_REST_API_KEY/KAKAO_REFRESH_TOKEN 미설정")
            return

        text = (
            f"[온라인몰 랭킹] {date_str} 수집 실패: {', '.join(failed)}\n"
            "크롤러_실패시.md 절차 참고"
        )
        template_object = {
            "object_type": "text",
            "text": text,
            "link": {"web_url": ACTIONS_URL, "mobile_web_url": ACTIONS_URL},
        }
        resp = requests.post(
            SEND_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            data={"template_object": json.dumps(template_object, ensure_ascii=False)},
            timeout=10,
        )
        resp.raise_for_status()
        print("[알림 발송] 카카오톡 실패 알림 전송 완료")
    except Exception as e:
        print(f"[알림 실패] 카카오톡 전송 중 오류: {e}")
