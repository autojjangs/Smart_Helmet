"""
스마트 헬멧 통합 진입점 (helmet_app.py)

[역할]
  - 기존 app.py(목적지 검색·확정 웹서버)와 main.py(실시간 내비 루프)를 한 프로세스로 통합한다.
  - 웹에서 목적지를 확정(POST /destination)하는 순간, 사람 개입 없이 내비게이션을 자동 시작한다.
  - destination.json은 그대로 유지(웹이 쓰고, 내비 스레드가 init_route에서 읽음).

[구조: A안 - 단일 프로세스 + 백그라운드 스레드]
  - 메인 스레드        : Flask(app.run) 가 웹 UI를 계속 서비스
  - 내비게이션 스레드  : 별도 스레드에서 asyncio 이벤트 루프를 돌리며 navigation.run() 실행

[실행 모드] 환경변수 HELMET_TEST_MODE
  - 0 (기본): 실제 모드. GPS 수신 + 실제 LED(PWM, root 필요) + 실제 BLE
  - 1       : 파싱 전용. GPS 없이 고정 출발지로 경로만 파싱·출력 후 종료
  - 2       : 이동 시뮬. 가상 위치를 경로 따라 전진시켜 진동/LED 트리거까지 검증(하드웨어 미사용)

[부팅 자동실행]
  - systemd(smart-helmet.service)로 root 실행 → sudo 없이도 GPIO/PWM/시리얼/BLE 권한 충족
"""

import os
import json
import asyncio
import threading

from flask import Flask, render_template, request, jsonify

from services import poi_service, navigation, gps_service

app = Flask(__name__)

# 목적지 좌표를 저장할 파일 (내비 스레드가 init_route에서 읽음)
DESTINATION_FILE = "destination.json"

# ===== 내비게이션 스레드 관리 =====
_nav_thread = None
_nav_stop = None
_nav_lock = threading.Lock()


def _nav_worker(stop_event):
    """별도 스레드에서 새 asyncio 이벤트 루프를 만들어 내비 코루틴을 실행한다."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(navigation.run(stop_event))
    except Exception as e:
        print(f"[NAV] 내비게이션 종료/오류: {e}")
    finally:
        try:
            loop.close()
        except Exception:
            pass
        print("[NAV] 내비게이션 스레드 종료")


def start_navigation(restart=True):
    """
    내비게이션 스레드를 시작한다.
    - 이미 실행 중이고 restart=True 이면, 현재 내비를 멈추고 새 목적지로 다시 시작한다.
    - restart=False 이고 실행 중이면 아무것도 하지 않는다.

    Returns:
        bool: 새로 시작했으면 True
    """
    global _nav_thread, _nav_stop

    with _nav_lock:
        running = _nav_thread is not None and _nav_thread.is_alive()

        if running:
            if not restart:
                return False
            # 기존 내비 정지 신호 → 잠깐 대기(루프가 stop_event를 확인할 시간)
            if _nav_stop:
                _nav_stop.set()
            _nav_thread.join(timeout=4.0)

        _nav_stop = threading.Event()
        _nav_thread = threading.Thread(
            target=_nav_worker, args=(_nav_stop,), daemon=True
        )
        _nav_thread.start()
        return True


def stop_navigation():
    """실행 중인 내비게이션을 정지시킨다."""
    global _nav_thread, _nav_stop
    with _nav_lock:
        if _nav_stop:
            _nav_stop.set()
        _nav_thread = None


# ===== 라우트 =====

@app.route("/")
def index():
    """목적지 검색 화면."""
    return render_template("index.html")


@app.route("/search")
def search():
    """키워드로 POI를 검색하여 후보 목록(최대 5개)을 JSON으로 반환."""
    keyword = request.args.get("keyword", "").strip()
    if not keyword:
        return jsonify({"results": [], "error": "검색어를 입력하세요."})
    try:
        results = poi_service.search_poi(keyword)
        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"results": [], "error": f"검색 실패: {e}"})


@app.route("/destination", methods=["POST"])
def set_destination():
    """선택한 장소를 목적지로 확정 → destination.json 저장 → 내비게이션 자동 시작."""
    data = request.get_json(silent=True) or {}

    name = data.get("name", "도착지")
    lon = data.get("lon")
    lat = data.get("lat")

    if lon is None or lat is None:
        return jsonify({"ok": False, "error": "좌표가 없습니다."})

    destination = {"name": name, "lon": float(lon), "lat": float(lat)}
    with open(DESTINATION_FILE, "w", encoding="utf-8") as f:
        json.dump(destination, f, ensure_ascii=False, indent=2)

    print(f"[WEB] 목적지 확정: {name} ({lat}, {lon}) → {DESTINATION_FILE} 저장")

    # 핵심: 목적지 확정과 동시에 내비게이션 자동 시작(재확정 시 재시작)
    started = start_navigation(restart=True)

    return jsonify({
        "ok": True,
        "nav_started": started,
        "message": f"목적지가 '{name}'(으)로 설정되었습니다. 내비게이션을 자동으로 시작합니다.",
    })


@app.route("/status")
def status():
    """현재 내비 실행 여부 + GPS 상태 + 경로 요약을 JSON으로 반환(웹 폴링용)."""
    running = _nav_thread is not None and _nav_thread.is_alive()
    return jsonify({
        "nav_running": running,
        "gps": gps_service.get_status(),
        "navigation": navigation.status(),
    })


@app.route("/stop", methods=["POST"])
def stop():
    """수동 정지(테스트/디버깅용)."""
    stop_navigation()
    return jsonify({"ok": True, "message": "내비게이션 정지 요청을 보냈습니다."})


if __name__ == "__main__":
    mode = os.getenv("HELMET_TEST_MODE", "0")
    print(f"=== 스마트 헬멧 통합 서버 시작 (HELMET_TEST_MODE={mode}) ===")
    # debug=False, use_reloader=False : 리로더가 프로세스를 2개로 띄워
    # 하드웨어/스레드와 충돌하는 것을 방지
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False, threaded=True)