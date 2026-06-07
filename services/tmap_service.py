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

# 목적지 (app.py 웹서버에서 검색·확정하여 destination.json에 저장한 값을 읽어옴)
END_X = None     # 초기값은 None, load_destination()으로 채워진다.
END_Y = None     # 초기값은 None, load_destination()으로 채워진다.
END_NAME = "도착지"

# 웹서버(app.py)가 목적지를 저장하는 파일
DESTINATION_FILE = "destination.json"
# ================================

def load_destination():
    """
    destination.json에서 목적지 좌표를 읽어 모듈 전역 변수에 설정한다.
    app.py에서 목적지를 먼저 확정해 두어야 한다.
    """
    global END_X, END_Y, END_NAME

    if not os.path.exists(DESTINATION_FILE):
        raise RuntimeError(
            f"{DESTINATION_FILE} 파일이 없습니다. "
            f"먼저 app.py를 실행해 목적지를 검색·설정하세요."
        )

    with open(DESTINATION_FILE, "r", encoding="utf-8") as f:
        dest = json.load(f)

    END_X = dest["lon"]
    END_Y = dest["lat"]
    END_NAME = dest.get("name", "도착지")
    print(f"[TMAP] 목적지 로드 완료: {END_NAME} ({END_Y}, {END_X})")


# API 엔드포인트
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
    """
    원본 GeoJSON 응답을 파싱하여 경로 요약 + 안내 지점 리스트를 반환한다.

    Returns:
        dict with keys:
            - total_distance (int): 전체 거리(m)
            - total_time (int): 전체 소요시간(초)
            - guide_points (list[dict]): 안내 지점 목록
              각 항목: {
                  "index": int,          # 순번
                  "coordinates": [경도, 위도],
                  "turn_type": int,      # 회전 코드
                  "description": str,    # 안내 텍스트
                  "point_type": str,     # SP/EP/GP/PP 등
                  "facility_type": str,  # 시설물 코드
                  "name": str,           # 안내 지점 명칭
                  "next_distance": int,  # 다음 구간까지 거리(m)
                  "next_time": int,      # 다음 구간까지 시간(초)
              }
    """
    features = raw_json.get("features", [])

    total_distance = 0
    total_time = 0
    guide_points = []

    # LineString 정보를 임시 보관하여 직전 Point에 거리/시간 매핑
    pending_line = None

    for feat in features:
        geom_type = feat["geometry"]["type"]
        props = feat["properties"]

        if geom_type == "Point":
            # 첫 번째 Point(SP)에서 전체 요약 추출
            if props.get("pointType") == "SP":
                total_distance = props.get("totalDistance", 0)
                total_time = props.get("totalTime", 0)

            # 직전에 대기 중인 LineString이 있으면 이전 Point에 매핑
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
            # LineString은 직전 Point의 '다음 구간' 정보
            pending_line = {
                "distance": props.get("distance", 0),
                "time": props.get("time", 0),
            }
            # 바로 직전 Point에 매핑
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
    target_dir = "response" # 디렉터리명 지정
    os.makedirs(target_dir, exist_ok=True) # response 폴더가 없으면 새로 생성 (이미 있으면 무시)
    file_path = os.path.join(target_dir, filename) # 폴더 경로와 파일 이름을 합쳐서 최종 경로 생성
    
    # 지정한 경로로 파일 저장
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(raw_json, f, ensure_ascii=False, indent=2)
        
    print(f"[TMAP] 원본 응답 저장 완료: {file_path}")


# ===== main.py에서 호출할 인터페이스 =====

# 모듈 레벨 상태 (경로 탐색 후 유지)
_route_data = None    # parse_route() 결과
_current_idx = 0      # 현재 진행 중인 안내 지점 인덱스


def init_route(start_lon, start_lat):
    """
    경로 탐색을 실행하고 파싱 결과를 모듈 내부에 보관한다.
    main.py의 루프 진입 전에 1회 호출한다.
    """
    global _route_data, _current_idx, START_X, START_Y

    START_X = start_lon
    START_Y = start_lat

    load_destination()  # destination.json에서 목적지 좌표를 먼저 읽어옴
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
    """
    현재 안내 지점의 (lon, lat, turn_type, current_index) 를 반환한다.

    수정: 기존에는 (next_distance, turn_type, index) 3개를 반환했으나,
          main.py는 GPS로 실제 거리를 직접 계산하기 위해 '목표 지점 좌표'가 필요하다.
          따라서 현재 안내 지점의 좌표(lon, lat)를 반환하도록 변경했다.

    Returns:
        tuple: (lon, lat, turn_type, current_index)
            - lon: 현재 목표 안내 지점의 경도
            - lat: 현재 목표 안내 지점의 위도
            - turn_type: 회전 코드 (11:직진, 12:좌회전, 13:우회전 등)
            - current_index: 현재 안내 지점 순번

    주의: 프로토타입에서는 GPS 기반 실시간 위치 추적이 없으므로,
         advance_to_next()를 수동 호출하여 다음 지점으로 넘긴다.
    """
    if _route_data is None:
        raise RuntimeError("init_route()를 먼저 호출하세요.")

    points = _route_data["guide_points"]
    if _current_idx >= len(points):
        # 모든 안내 지점 통과 → 목적지 도착 (좌표 없음)
        # 주의: main.py는 이 함수 호출 전에 get_route_summary()로 도착을 먼저 체크하므로
        #       정상 흐름에서는 이 분기에 도달하지 않는다(안전용 반환).
        return (None, None, 201, -1)

    pt = points[_current_idx]
    lon = pt["coordinates"][0]
    lat = pt["coordinates"][1]
    return (lon, lat, pt["turn_type"], _current_idx)


def advance_to_next():
    """
    다음 안내 지점으로 이동한다.
    실제 제품에서는 GPS 위치가 안내 지점 좌표에 근접하면 자동으로 넘어가지만,
    프로토타입에서는 이 함수를 수동 호출하여 시뮬레이션한다.
    """
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