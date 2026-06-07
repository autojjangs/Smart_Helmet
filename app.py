import json
from flask import Flask, render_template, request, jsonify

from services import poi_service

app = Flask(__name__)

# 목적지 좌표를 저장할 파일 (main.py가 이 파일을 읽음)
DESTINATION_FILE = "destination.json"


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
    """선택한 장소를 목적지로 확정하여 destination.json에 저장."""
    data = request.get_json(silent=True) or {}

    name = data.get("name", "도착지")
    lon = data.get("lon")
    lat = data.get("lat")

    if lon is None or lat is None:
        return jsonify({"ok": False, "error": "좌표가 없습니다."})

    destination = {
        "name": name,
        "lon": float(lon),
        "lat": float(lat),
    }

    with open(DESTINATION_FILE, "w", encoding="utf-8") as f:
        json.dump(destination, f, ensure_ascii=False, indent=2)

    print(f"[WEB] 목적지 확정: {name} ({lat}, {lon}) → {DESTINATION_FILE} 저장")
    return jsonify({
        "ok": True,
        "message": f"목적지가 '{name}'(으)로 설정되었습니다. 이제 main.py를 실행하세요.",
    })


if __name__ == "__main__":
    # 0.0.0.0 으로 열어야 핫스팟 내 스마트폰에서 접속 가능
    app.run(host="0.0.0.0", port=5000, debug=True)