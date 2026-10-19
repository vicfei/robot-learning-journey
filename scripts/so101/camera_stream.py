"""SO-101 相机 MJPEG 流服务(Windows 侧): USB 相机 -> HTTP MJPEG, 供 WSL 拉流

用法:
  python camera_stream.py --list          # 枚举相机 index(各抓一帧报告分辨率)
  python camera_stream.py 1               # index=1 的相机起流, 端口 8000
WSL 侧拉流: cv2.VideoCapture("http://<WindowsIP>:8000/")
"""
import sys, time, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import cv2
import numpy as np

PORT = 8000
frame_lock = threading.Lock()
latest_jpeg = b""


def list_cams():
    print("枚举相机 index 0-4...")
    for i in range(5):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        ok, frame = cap.read()
        if ok:
            print(f"  index {i}: {frame.shape[1]}x{frame.shape[0]} 抓帧成功")
            cv2.imwrite(rf"C:\Users\chenfei\Desktop\cam_{i}.png", frame)
        else:
            print(f"  index {i}: 无法打开")
        cap.release()
    print("测试帧已存到桌面 (cam_N.png)")


class StreamHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            self._do_get()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass    # 客户端断流属正常

    def _do_get(self):
        if self.path.startswith("/shot"):
            with frame_lock:
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(latest_jpeg)))
            self.end_headers()
            self.wfile.write(latest_jpeg)
            return
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.end_headers()
        while True:
            with frame_lock:
                buf = latest_jpeg
            if buf:
                self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf + b"\r\n")
            time.sleep(1 / 30)

    def log_message(self, *a):
        pass


def main():
    if "--list" in sys.argv:
        list_cams()
        return
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    ok, _ = cap.read()
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)); h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"实际输出分辨率: {w}x{h}")
    if not ok:
        print(f"相机 index {idx} 打开失败, 先跑 --list 探测"); return

    def capture_loop():
        global latest_jpeg
        while True:
            ok, frame = cap.read()
            if ok:
                _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
                with frame_lock:
                    latest_jpeg = buf.tobytes()
            time.sleep(1 / 60)

    threading.Thread(target=capture_loop, daemon=True).start()
    srv = HTTPServer(("0.0.0.0", PORT), StreamHandler)
    print(f"MJPEG 流已启动: http://<本机IP>:{PORT}/  (index={idx})")
    print(f"单帧测试: http://<本机IP>:{PORT}/shot")
    print("Ctrl+C 退出")
    srv.serve_forever()


if __name__ == "__main__":
    main()
