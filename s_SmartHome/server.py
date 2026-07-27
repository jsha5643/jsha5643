import http.server
import json
import os

# WebRTC 시그널링용 공유 데이터 저장소
signals = {
    "owner": None,
    "dog": None,
    "candidates_to_owner": [],
    "candidates_to_dog": []
}

# Wi-Fi 통신용 공유 데이터 저장소
latest_sensors_data = ""
esp_commands = []

class SignalingHTTPServer(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # CORS 허용 설정 (모바일 접속 및 다중 기기 연동 활성화)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        global signals, latest_sensors_data, esp_commands
        if self.path.startswith("/api/esp/commands"):
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(esp_commands).encode('utf-8'))
            esp_commands.clear()
            return
        elif self.path.startswith("/api/web/sensors"):
            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(latest_sensors_data.encode('utf-8'))
            return
        elif self.path.startswith("/api/get_signal"):
            # 역할에 따른 상대방의 시그널 데이터 및 Candidate 가져오기
            role = self.path.split("role=")[-1]
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            response = {}
            if role == "owner":
                # 주인이 가져갈 데이터 (dog가 보낸 sdp와 candidates)
                response = {
                    "sdp": signals["dog"],
                    "candidates": list(signals["candidates_to_owner"])
                }
                signals["candidates_to_owner"].clear()
            elif role == "dog":
                # 강아지가 가져갈 데이터 (owner가 보낸 sdp와 candidates)
                response = {
                    "sdp": signals["owner"],
                    "candidates": list(signals["candidates_to_dog"])
                }
                signals["candidates_to_dog"].clear()
                
            self.wfile.write(json.dumps(response).encode('utf-8'))
        elif self.path.startswith("/api/reset"):
            # 시그널링 리셋
            signals = {"owner": None, "dog": None, "candidates_to_owner": [], "candidates_to_dog": []}
            latest_sensors_data = ""
            esp_commands.clear()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Reset success")
        else:
            # 기본 정적 파일 서빙
            super().do_GET()

    def do_POST(self):
        global signals, latest_sensors_data, esp_commands
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)

        if self.path == "/api/esp/sensors":
            latest_sensors_data = post_data.decode('utf-8')
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
            return

        if self.path == "/api/web/command":
            try:
                cmd_data = json.loads(post_data.decode('utf-8'))
                cmd = cmd_data.get("command")
            except:
                cmd = post_data.decode('utf-8')
            if cmd:
                esp_commands.append(cmd)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
            return

        # WebRTC 시그널링 기존 로직
        try:
            data = json.loads(post_data.decode('utf-8'))
        except Exception as e:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(f"Invalid JSON: {e}".encode('utf-8'))
            return

        if self.path == "/api/send_sdp":
            role = data.get("role")
            sdp = data.get("sdp")
            if role == "owner":
                signals["owner"] = sdp
            elif role == "dog":
                signals["dog"] = sdp
            
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"SDP received")

        elif self.path == "/api/send_candidate":
            role = data.get("role")
            candidate = data.get("candidate")
            if role == "owner":
                # 주인이 보낸 후보는 강아지에게 릴레이
                signals["candidates_to_dog"].append(candidate)
            elif role == "dog":
                # 강아지가 보낸 후보는 주인에게 릴레이
                signals["candidates_to_owner"].append(candidate)
                
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Candidate received")

if __name__ == '__main__':
    port = 8000
    print(f"Starting WebRTC Signaling & Web Server on port {port}...")
    server = http.server.HTTPServer(('0.0.0.0', port), SignalingHTTPServer)
    server.serve_forever()
