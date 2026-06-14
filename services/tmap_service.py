"""
TMAP 보행자 경로안내 API 파싱 서비스
- API 호출 → 응답 JSON 파싱 → 경로 안내 정보 제공
"""

import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()  # 프로젝트 루트의 .env 파일 로드

# ===== 사용자 직접 설정 영역 =====
API_KEY = os.getenv("TMAP_API_KEY")
if not API_KEY:
    raise RuntimeError("TMAP_API_KEY가 .env 파일에 설정되어 있지 않습니다.")

# 출발지 (프로토타입: 기본값 / 실제: init_route()에 넘어온 GPS 값으로 덮어씀)
START_X = 126.838571   # 클터 후문 경도 (longitude)
START_Y = 37.296417    # 클터 후문 위도 (latitude)
START_NAME = "출발지"

# 목적지 (웹서버에서 검색·확정하여 destination.json에 저장한 값을 읽어옴)
END_X = None
END_Y = None
END_NAME = "도착지"

DESTINATION_FILE = "destination.json"
# ================================

def load_destination():
    """destination.json에서 목적지 좌표를 읽어 모듈 전역 변수에 설정한다."""
    global END_X, END_Y, END_NAME

    if not os.path.exists(DESTINATION_FILE):
        raise RuntimeError(
            f"{DESTINATION_FILE} 파일이 없습니다. "
            f"먼저 목적지를 검색·설정하세요."
        )

    with open(DESTINATION_FILE, "r", encoding="utf-8") as f:
        dest = json.load(f)

    END_X = dest["lon"]
    END_Y = dest["lat"]
    END_NAME = dest.get("name", "도착지")
    print(f"[TMAP] 목적지 로드 완료: {END_NAME} ({END_Y}, {END_X})")


PEDESTRIAN_URL = "https://apis.openapi.sk.com/tmap/routes/pedestrian?version=1"


def request_route():
    """TMAP 보행자 경로안내 API를 호출하여 원본 JSON 응답을 반환한다."""
    headers = {
        "appKey": API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body = {
        "startX": START_X,
        "startY": START_Y,
        "endX": END_X,
        "endY": END_Y,
        "startName": START_NAME,
        "endName": END_NAME,
        "reqCoordType": "WGS84GEO",
        "resCoordType": "WGS84GEO",
        "searchOption": "0",
        "sort": "index",
    }

    resp = requests.post(PEDESTRIAN_URL, headers=headers, json=body, timeout=10)
    resp.raise_for_status()
    return resp.json()


def parse_route(raw_json):
    """원본 GeoJSON 응답을 파싱하여 경로 요약 + 안내 지점 리스트를 반환한다."""
    features = raw_json.get("features", [])

    total_distance = 0
    total_time = 0
    guide_points = []

    pending_line = None

    for feat in features:
        geom_type = feat["geometry"]["type"]
        props = feat["properties"]

        if geom_type == "Point":
            if props.get("pointType") == "SP":
                total_distance = props.get("totalDistance", 0)
                total_time = props.get("totalTime", 0)

            if pending_line and guide_points:
                guide_points[-1]["next_distance"] = pending_line["distance"]
                guide_points[-1]["next_time"] = pending_line["time"]
                pending_line = None

            point = {
                "index": props.get("index", 0),
                "coordinates": feat["geometry"]["coordinates"],
                "turn_type": props.get("turnType", 0),
                "description": props.get("description", ""),
                "point_type": props.get("pointType", ""),
                "facility_type": props.get("facilityType", ""),
                "name": props.get("name", ""),
                "next_distance": 0,
                "next_time": 0,
            }
            guide_points.append(point)

        elif geom_type == "LineString":
            pending_line = {
                "distance": props.get("distance", 0),
                "time": props.get("time", 0),
            }
            if guide_points:
                guide_points[-1]["next_distance"] = pending_line["distance"]
                guide_points[-1]["next_time"] = pending_line["time"]
                pending_line = None

    return {
        "total_distance": total_distance,
        "total_time": total_time,
        "guide_points": guide_points,
    }


def save_raw_json(raw_json, filename="tmap_response.json"):
    """디버깅용: 원본 응답을 response 디렉터리 안에 파일로 저장한다."""
    target_dir = "response"
    os.makedirs(target_dir, exist_ok=True)
    file_path = os.path.join(target_dir, filename)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(raw_json, f, ensure_ascii=False, indent=2)
    print(f"[TMAP] 원본 응답 저장 완료: {file_path}")


# ===== 내비게이션에서 호출할 인터페이스 =====

_route_data = None
_current_idx = 0

# turn types that count as actual direction-change maneuvers
_TURN_TYPE_SET = {12, 13, 14, 16, 17, 18, 19}


def init_route(start_lon, start_lat):
    """경로 탐색을 실행하고 파싱 결과를 모듈 내부에 보관한다."""
    global _route_data, _current_idx, START_X, START_Y

    START_X = start_lon
    START_Y = start_lat

    load_destination()
    print("[TMAP] 경로 탐색 요청 중...")
    raw = request_route()
    save_raw_json(raw)
    _route_data = parse_route(raw)
    _current_idx = 0

    td = _route_data["total_distance"]
    tt = _route_data["total_time"]
    n = len(_route_data["guide_points"])
    print(f"[TMAP] 경로 수신 완료 - 총 거리: {td}m, 총 시간: {tt}초, 안내 지점: {n}개")


def get_current_info():
    """현재 안내 지점의 (lon, lat, turn_type, current_index) 를 반환한다."""
    if _route_data is None:
        raise RuntimeError("init_route()를 먼저 호출하세요.")

    points = _route_data["guide_points"]
    if _current_idx >= len(points):
        return (None, None, 201, -1)

    pt = points[_current_idx]
    lon = pt["coordinates"][0]
    lat = pt["coordinates"][1]
    return (lon, lat, pt["turn_type"], _current_idx)


def advance_to_next():
    """다음 안내 지점으로 이동한다."""
    global _current_idx
    if _route_data and _current_idx < len(_route_data["guide_points"]):
        _current_idx += 1
        remaining = len(_route_data["guide_points"]) - _current_idx
        print(f"[TMAP] 다음 안내 지점으로 이동 (남은 안내 지점: {remaining}개)")


def get_route_summary():
    """경로 전체 요약 정보를 반환한다."""
    if _route_data is None:
        return None
    return {
        "total_distance": _route_data["total_distance"],
        "total_time": _route_data["total_time"],
        "total_points": len(_route_data["guide_points"]),
        "current_index": _current_idx,
    }


def get_current_guide():
    """Return the current target guide point dict, or None."""
    if _route_data is None:
        return None
    pts = _route_data["guide_points"]
    if _current_idx >= len(pts):
        return None
    return pts[_current_idx]


def count_remaining_turns():
    """Number of remaining turn maneuvers from the current index onward."""
    if _route_data is None:
        return 0
    pts = _route_data["guide_points"]
    return sum(
        1 for i in range(_current_idx, len(pts))
        if pts[i]["turn_type"] in _TURN_TYPE_SET
    )


def get_turn_label(turn_type):
    """Public wrapper to convert a turnType code into a human label."""
    return _get_turn_label(turn_type)


def print_all_guide_points():
    """디버깅용: 전체 안내 지점을 콘솔에 출력한다."""
    if _route_data is None:
        print("[TMAP] 경로 데이터 없음")
        return

    print("\n===== 전체 안내 지점 목록 =====")
    for pt in _route_data["guide_points"]:
        turn_label = _get_turn_label(pt["turn_type"])
        print(
            f"  [{pt['index']}] {turn_label} | "
            f"{pt['description']} | "
            f"다음 구간: {pt['next_distance']}m/{pt['next_time']}초"
        )
    print("===============================\n")


def _get_turn_label(turn_type):
    """turnType 코드를 사람이 읽을 수 있는 라벨로 변환한다."""
    labels = {
        11: "직진",
        12: "좌회전",
        13: "우회전",
        14: "U턴",
        16: "8시방향 좌회전",
        17: "10시방향 좌회전",
        18: "2시방향 우회전",
        19: "4시방향 우회전",
        125: "육교",
        126: "지하보도",
        127: "계단",
        128: "경사로",
        200: "출발",
        201: "도착",
        211: "횡단보도",
        212: "좌측 횡단보도",
        213: "우측 횡단보도",
    }
    return labels.get(turn_type, f"코드:{turn_type}")
