"""SO-101 串口桥 v3.2: 波特率自动发现 + TCP 桥(Windows 侧)

用法: python serial_bridge.py [COM口]
WSL 侧连接: socket://<Windows主机IP>:9999

v3.2 修复: 读线程 20ms 超时(可退出,句柄干净释放) + COM 打开重试 + 主循环异常全兜
"""
import socket, sys, time

import serial  # pyserial

COM = sys.argv[1] if len(sys.argv) > 1 else "COM3"
TCP_PORT = 9999
BAUD_CANDIDATES = [115200, 1000000, 500000, 921600, 250000, 128000, 57600, 9600]


def ping_once(ser, sid=1):
    ck = (~(sid + 2 + 1)) & 0xFF
    ser.reset_input_buffer()
    ser.write(bytes([0xFF, 0xFF, sid, 0x02, 0x01, ck]))
    time.sleep(0.05)
    return ser.in_waiting > 0


def open_serial(baud, retries=3):
    for i in range(retries):
        try:
            return serial.Serial(COM, baud, bytesize=8, parity="N", stopbits=1,
                                 timeout=0.02)   # 20ms 读超时: 读线程可退出
        except Exception as e:
            print(f"  打开 {COM} 失败({i+1}/{retries}): {e}")
            time.sleep(1)
    return None


def discover_baud():
    print(f"扫描 {COM} 的舵机波特率...")
    for baud in BAUD_CANDIDATES:
        ser = open_serial(baud, retries=1)
        if ser is None:
            continue
        if ping_once(ser):
            hits = [i for i in range(1, 7) if ping_once(ser, i)]
            ser.close()
            if hits:
                print(f"  *** {baud} baud: 舵机回话! 存活 ID={hits} ***")
                return baud
        else:
            ser.close()
        print(f"  {baud}: 无响应")
    return None


def serial_reader(ser, sock):
    try:
        while ser.is_open:
            n = ser.in_waiting
            data = ser.read(n or 1)   # 最多阻塞 20ms, 主循环可 join 到它
            if data:
                sock.sendall(data)
    except Exception:
        pass


def tcp_reader(sock, ser):
    try:
        while True:
            data = sock.recv(4096)
            if not data:
                raise ConnectionError("WSL 侧断开")
            ser.write(data)
    except Exception:
        pass


def main():
    import threading
    baud = discover_baud()
    if baud is None:
        print("!! 所有候选波特率都无响应"); sys.exit(1)
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", TCP_PORT))
    srv.listen(1)
    print(f"桥已启动: TCP 0.0.0.0:{TCP_PORT} <-> {COM} @ {baud} 8N1 (v3.2)")
    print("等待 WSL 连接...(Ctrl+C 退出)")
    while True:
        sock = None
        try:
            sock, addr = srv.accept()
            print(f"[连接] {addr}")
            ser = open_serial(baud)
            if ser is None:
                print("[串口打不开, 拒绝本连接]")
                sock.close()
                continue
            t1 = threading.Thread(target=serial_reader, args=(ser, sock), daemon=True)
            t2 = threading.Thread(target=tcp_reader, args=(sock, ser), daemon=True)
            t1.start(); t2.start()
            t2.join()
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            sock.close()
            t1.join(timeout=3)         # 20ms 读超时保证它退得出
            ser.close()
            print("[断开] 等待重连...")
        except KeyboardInterrupt:
            print("退出")
            break
        except Exception as e:
            print(f"[本轮异常已吞并继续] {e}")
            if sock:
                try: sock.close()
                except OSError: pass


if __name__ == "__main__":
    main()
