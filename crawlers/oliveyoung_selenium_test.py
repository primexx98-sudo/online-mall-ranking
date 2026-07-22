"""올리브영 Selenium+sleep 실증 테스트 (2026-07-22).

사용자 제안(Selenium + 충분한 time.sleep())이 Cloudflare Turnstile 차단을
우회할 수 있는지 GitHub Actions에서 직접 확인하기 위한 일회성 테스트 스크립트.
결과가 좋으면 crawlers/oliveyoung.py를 이 방식으로 교체하고, 아니면
이 파일과 관련 워크플로를 삭제한다 (기록.md 참고).
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

from crawlers.config import PLATFORMS

ITEM_SELECTOR = "ul.cate_prd_list > li"


def run_test():
    url = f"{PLATFORMS['올리브영']['url']}&pageIdx=1&rowsPerPage=10"

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=options)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )

    try:
        print(f"GET {url}")
        driver.get(url)

        print("초기 로딩 대기 8초...")
        import time

        time.sleep(8)

        print(f"페이지 타이틀: {driver.title}")
        print(f"현재 URL: {driver.current_url}")

        items = driver.find_elements(By.CSS_SELECTOR, ITEM_SELECTOR)
        print(f"1차 시도 상품 개수: {len(items)}")

        if not items:
            print("상품이 안 보임 - 추가 12초 더 대기 후 재확인...")
            time.sleep(12)
            items = driver.find_elements(By.CSS_SELECTOR, ITEM_SELECTOR)
            print(f"2차 시도 상품 개수: {len(items)}")

        page_source_snippet = driver.page_source[:500]
        has_turnstile = "turnstile" in driver.page_source.lower() or "사람인지" in driver.page_source

        print(f"Turnstile 관련 텍스트 포함 여부: {has_turnstile}")
        print(f"body 스니펫: {page_source_snippet}")

        if items:
            first = items[0]
            print("첫 상품 텍스트:", first.text[:200])
            print("=== 성공: 상품 목록 정상 렌더링 ===")
            return True
        else:
            print("=== 실패: 상품 목록 못 찾음 (차단 추정) ===")
            driver.save_screenshot("oliveyoung_selenium_fail.png")
            return False
    finally:
        driver.quit()


if __name__ == "__main__":
    import sys

    ok = run_test()
    sys.exit(0 if ok else 1)
