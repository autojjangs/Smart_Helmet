"""
GPS 데이터 확인용 Flask 웹 서버
- 라즈베리파이에서 실행 → 같은 핫스팟에 연결된 스마트폰 브라우저로 접속
- gps_service의 최신 좌표를 읽어와 1초마다 실시간으로 보여준다
- RealVNC(화면 전체 미러링) 대신, 필요한 GPS 데이터만 웹페이지로 확인하는 용도

[중요] Flask는 블로킹 방식이라 asyncio 루프를 막는다.
        → start_web_server()로 별도 데몬 스레드에서 실행하여 GPS 루프를 막지 않는다.
"""

import threading
from flask import Flask, jsonify

# main.py와 동일하게 services 패키지 기준으로 import
from services import gps_service

app = Flask(__name__)


# 스마트폰 브라우저에 표시할 HTML
# (자바스크립트가 1초마다 /gps 를 호출해서 화면을 갱신한다)
PAGE_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GPS 수신 테스트</title>
  <style>
    body { font-family: -apple-system, sans-serif; margin: 0; padding: 24px;
           background: #f4f6f8; color: #1a1a1a; }
    h1 { font-size: 20px; margin: 0 0 16px; }
    .status { font-size: 22px; font-weight: 700; padding: 14px 16px;
              border-radius: 12px; margin-bottom: 20px; text-align: center; }
    .wait   { background: #e0e0e0; color: #555; }
    .ok     { background: #d6f5d6; color: #157a15; }
    .stale  { background: #ffe6cc; color: #b35900; }
    .card { background: #fff; border-radius: 12px; padding: 16px;
            box-shadow: 0 1px 4px rgba(0,0,0,.08); margin-bottom: 12px; }
    .label { font-size: 13px; color: #888; }
    .value { font-size: 30px; font-weight: 700; font-family: monospace; }
    a.map { display: block; text-align: center; padding: 14px;
            background: #2563eb; color: #fff; border-radius: 12px;
            text-decoration: none; font-weight: 700; margin-top: 8px; }
    a.map.off { background: #bbb; pointer-events: none; }
  </style>
</head>
<body>
  <h1>📡 GPS 수신 상태</h1>
  <div id="status" class="status wait">신호 대기 중...</div>

  <div class="card">
    <div class="label">위도 (latitude)</div>
    <div class="value" id="lat">-</div>
  </div>
  <div class="card">
    <div class="label">경도 (longitude)</div>
    <div class="value" id="lon">-</div>
  </div>

  <a id="maplink" class="map off" target="_blank">지도에서 위치 확인</a>

<script>
async function update() {
  try {
    const res = await fetch('/gps');
    const d = await res.json();

    const statusEl = document.getElementById('status');
    const mapEl = document.getElementById('maplink');

    if (!d.has_fix) {
      statusEl.className = 'status wait';
      statusEl.textContent = '신호 대기 중...';
      document.getElementById('lat').textContent = '-';
      document.getElementById('lon').textContent = '-';
      mapEl.className = 'map off';
      return;
    }

    document.getElementById('lat').textContent = d.lat.toFixed(6);
    document.getElementById('lon').textContent = d.lon.toFixed(6);
    mapEl.className = 'map';
    mapEl.href = 'https://www.google.com/maps?q=' + d.lat + ',' + d.lon;

    const age = d.age_seconds;
    if (age !== null && age < 5) {
      statusEl.className = 'status ok';
      statusEl.textContent = '수신 중 (' + age.toFixed(1) + '초 전)';
    } else {
      statusEl.className = 'status stale';
      statusEl.textContent = '신호 끊김? (' + (age === null ? '-' : age.toFixed(0)) + '초 전 수신)';
    }
  } catch (e) {
    document.getElementById('status').textContent = '서버 연결 오류';
  }
}
setInterval(update, 1000);
update();
</script>
</body>
</html>"""


@app.route("/")
def index():
    """스마트폰으로 접속하면 보이는 메인 페이지"""
    return PAGE_HTML


@app.route("/gps")
def gps_data():
    """현재 GPS 상태를 JSON으로 반환 (페이지가 1초마다 호출)"""
    return jsonify(gps_service.get_status())


def start_web_server(host="0.0.0.0", port=5000):
    """
    Flask 서버를 별도 데몬 스레드에서 실행한다.
    - host="0.0.0.0": 같은 네트워크(핫스팟)의 스마트폰에서 접속 가능
    - asyncio 루프(GPS 수신)를 막지 않음
    """
    def _run():
        # use_reloader=False: 스레드/asyncio 환경에서 충돌 방지
        app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t