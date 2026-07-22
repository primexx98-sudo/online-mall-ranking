# 온라인몰 건강기능식품 판매순위 크롤러

올리브영 · 다이소몰 · 카카오 선물하기의 건강기능식품 판매순위 TOP10을 매일
자동 수집하고, 월별 평균순위 TOP20을 집계합니다.

자세한 구조와 로직은 [설계서.md](./설계서.md), 진행 경위·의사결정 배경은
[기록.md](./기록.md)를 참고하세요. 올리브영 자동 수집이 막혔을 때는
[크롤러_실패시.md](./크롤러_실패시.md)를 따라 수동 보완합니다.

## 빠른 시작

```bash
pip install -r requirements.txt
playwright install chromium

python main.py               # 오늘 날짜로 수집
streamlit 대시보드는 이번 버전에 없음 — data/ 아래 xlsx 파일을 직접 확인
```
