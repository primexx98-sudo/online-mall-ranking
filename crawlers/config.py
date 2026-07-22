"""플랫폼별 수집 대상 URL. URL 변경 시 이 파일만 수정하면 된다."""

PLATFORMS = {
    "카카오선물하기": {
        "categories": [
            {"name": "건강식품·영양제", "url": "https://gift.kakao.com/category/5/subcategory/99"},
            {"name": "다이어트·이너뷰티", "url": "https://gift.kakao.com/category/5/subcategory/100"},
        ],
        "top_n": 10,
    },
    "다이소몰": {
        "url": "https://www.daisomall.co.kr/ds/exhCtgr/C208/CTGR_00022/CTGR_01020",
        "top_n": 10,
    },
    "올리브영": {
        # dispCatNo=전체 판매랭킹 root, fltDispCatNo=건강식품 필터 (2026-07-22 확인 시점 기준)
        "url": "https://www.oliveyoung.co.kr/store/main/getBestList.do?dispCatNo=900000100100001&fltDispCatNo=10000020001",
        "top_n": 10,
    },
}

COLUMNS = ["카테고리", "순위", "상품명", "브랜드", "가격", "상품URL", "이미지URL"]
