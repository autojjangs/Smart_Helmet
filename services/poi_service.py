"""
TMAP POI 통합검색 서비스
- 키워드 → 장소 후보 목록(최대 5개) 반환
- 좌표는 '입구 좌표'(frontLat/frontLon)를 사용
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("TMAP_API_KEY")
if not API_KEY:
    raise RuntimeError("TMAP_API_KEY가 .env 파일에 설정되어 있지 않습니다.")

# POI 통합검색 엔드포인트
POI_URL = "https://apis.openapi.sk.com/tmap/pois?version=1"

# 화면에 표시할 최대 검색 결과 개수
MAX_RESULTS = 5


def search_poi(keyword):
    """
    키워드로 장소를 검색하여 후보 목록을 반환한다.

    Args:
        keyword (str): 검색어 (예: "강남역")

    Returns:
        list[dict]: 최대 5개의 장소 후보. 각 항목:
            {
                "name": str,       # 장소명
                "address": str,    # 주소 (도로명 우선, 없으면 지번)
                "lon": float,      # 입구 경도 (frontLon)
                "lat": float,      # 입구 위도 (frontLat)
            }
    """
    headers = {
        "appKey": API_KEY,
        "Accept": "application/json",
    }
    params = {
        "searchKeyword": keyword,
        "count": MAX_RESULTS,       # 최대 5개
        "searchtypCd": "A",          # A: 통합(가나다순+거리), R: 거리순
        "reqCoordType": "WGS84GEO",
        "resCoordType": "WGS84GEO",
    }

    resp = requests.get(POI_URL, headers=headers, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    return _parse_poi(data)


def _parse_poi(data):
    """POI 통합검색 응답을 파싱하여 후보 목록으로 정리한다."""
    results = []

    # 응답 구조: searchPoiInfo.pois.poi (리스트)
    pois = (
        data.get("searchPoiInfo", {})
            .get("pois", {})
            .get("poi", [])
    )

    for p in pois[:MAX_RESULTS]:
        # 도로명 주소 우선, 없으면 지번 주소 조합
        road_addr = _build_road_address(p)
        jibun_addr = _build_jibun_address(p)
        address = road_addr or jibun_addr

        # 입구 좌표 (frontLat / frontLon)
        try:
            lon = float(p.get("frontLon", ""))
            lat = float(p.get("frontLat", ""))
        except (TypeError, ValueError):
            # 입구 좌표가 비어있으면 중심 좌표로 대체
            try:
                lon = float(p.get("noorLon", ""))
                lat = float(p.get("noorLat", ""))
            except (TypeError, ValueError):
                continue  # 좌표를 못 구하면 후보에서 제외

        results.append({
            "name": p.get("name", ""),
            "address": address,
            "lon": lon,
            "lat": lat,
        })

    return results


def _build_road_address(p):
    """도로명 주소 조합 (없으면 빈 문자열)."""
    parts = [
        p.get("upperAddrName", ""),   # 시/도
        p.get("middleAddrName", ""),  # 시/군/구
        p.get("roadName", ""),        # 도로명
        p.get("buildingNo1", ""),     # 건물본번
    ]
    addr = " ".join(x for x in parts if x).strip()
    return addr if p.get("roadName") else ""


def _build_jibun_address(p):
    """지번 주소 조합."""
    parts = [
        p.get("upperAddrName", ""),
        p.get("middleAddrName", ""),
        p.get("lowerAddrName", ""),
        p.get("detailAddrName", ""),
    ]
    return " ".join(x for x in parts if x).strip()