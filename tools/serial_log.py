"""Print the serial log of one or more boards at once, with timestamps and port labels.

DTR is asserted (BOOT0 low on the DX-PJ26), so a reset while logging starts the app,
not the ROM bootloader. RTS is released.

Examples:
  python serial_log.py COM14                 sensor only, until Ctrl+C
  python serial_log.py COM13 COM14 -t 60     receiver and sensor side by side for 60 s
"""
import argparse
import sys
import threading
import time

import serial


def listen(port, baud, start, stop, lock):
    ser = serial.Serial()
    ser.port = port
    ser.baudrate = baud
    ser.timeout = 0.1
    ser.dtr = True
    ser.rts = False
    try:
        ser.open()
    except serial.SerialException as e:
        with lock:
            print(f"{port}: cannot open ({e})", flush=True)
        return
    pending = b""
    while not stop.is_set():
        pending += ser.read(256)
        while b"\n" in pending:
            line, pending = pending.split(b"\n", 1)
            # ASCII only: line noise (e.g. at a reset) must not crash a non-UTF-8 console
            text = line.decode("ascii", errors="replace").replace("�", "?").strip()
            if text:
                with lock:
                    print(f"[{time.time() - start:7.1f}s] {port:<6} {text}", flush=True)
    ser.close()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("ports", nargs="+")
    p.add_argument("-b", "--baud", type=int, default=115200)
    p.add_argument("-t", "--seconds", type=float, default=0, help="stop after this long (0 = until Ctrl+C)")
    args = p.parse_args()

    start = time.time()
    stop = threading.Event()
    lock = threading.Lock()
    threads = [threading.Thread(target=listen, args=(port, args.baud, start, stop, lock), daemon=True)
               for port in args.ports]
    for t in threads:
        t.start()
    try:
        while any(t.is_alive() for t in threads):
            if args.seconds and time.time() - start >= args.seconds:
                break
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    stop.set()
    for t in threads:
        t.join(timeout=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
