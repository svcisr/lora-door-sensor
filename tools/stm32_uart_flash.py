"""Flash an STM32F1 over its ROM serial bootloader (ST AN3155) through the board's USB-C port.

The DX-PJ26 board has no automatic reset circuit, but BOOT0 follows the CH340's DTR
line: DTR deasserted (or the port closed) = BOOT0 high, so a reset starts the ROM
bootloader; DTR asserted = BOOT0 low, the app starts. Boards running the door
firmware restart into the bootloader on a serial command (--enter). A board with
other firmware must be put into the bootloader first (port open with DTR deasserted,
the default here, then press RST); this tool then picks up the running bootloader.

  info   : read chip id, flash size, unique ID and read protection (no writes), then run the app
  probe  : cycle the DTR/RTS states while the user presses RST, report which one works
  flash  : wait for the bootloader, optionally back up the flash, write a .bin, verify, run

Examples:
  python stm32_uart_flash.py info COM13 --enter
  python stm32_uart_flash.py flash COM13 --enter --write firmware.bin
  python stm32_uart_flash.py flash COM13 --backup factory.bin --write firmware.bin
"""
import argparse
import itertools
import sys
import time

import serial

ACK, NACK = 0x79, 0x1F
FLASH_BASE = 0x08000000
FLASH_SIZE_REG = 0x1FFFF7E0     # F1 flash size in KiB
UNIQUE_ID_REG = 0x1FFFF7E8      # F1 96-bit unique ID
OPTION_BYTES = 0x1FFFF800
STATES = [(False, False), (True, False), (False, True), (True, True)]   # (dtr, rts), True = asserted
BOOTLOADER_COMMAND = b"#DOOR-BOOTLOADER#"   # must match BOOTLOADER_COMMAND in include/config.h


class BootloaderError(Exception):
    pass


def log(msg):
    print(msg, flush=True)


def open_port(port, dtr, rts, baud):
    ser = serial.Serial()
    ser.port = port
    ser.baudrate = baud
    ser.parity = serial.PARITY_EVEN
    ser.timeout = 0.2
    ser.dtr = dtr
    ser.rts = rts
    ser.open()
    return ser


def try_sync(ser):
    ser.reset_input_buffer()
    ser.write(b"\x7f")
    resp = ser.read(1)
    # NACK means the bootloader already locked its baud rate: it is listening
    return resp in (bytes([ACK]), bytes([NACK]))


def wait_ack(ser, timeout=1.0):
    old = ser.timeout
    ser.timeout = timeout
    resp = ser.read(1)
    ser.timeout = old
    if resp != bytes([ACK]):
        raise BootloaderError(f"expected ACK, got {resp!r}")


def command(ser, cmd):
    ser.write(bytes([cmd, cmd ^ 0xFF]))
    wait_ack(ser)


def send_address(ser, addr):
    data = addr.to_bytes(4, "big")
    ser.write(data + bytes([data[0] ^ data[1] ^ data[2] ^ data[3]]))
    wait_ack(ser)


def get_commands(ser):
    command(ser, 0x00)
    n = ser.read(1)[0]
    payload = ser.read(n + 1)
    wait_ack(ser)
    return payload[0], set(payload[1:])


def get_id(ser):
    command(ser, 0x02)
    n = ser.read(1)[0]
    pid = ser.read(n + 1)
    wait_ack(ser)
    return int.from_bytes(pid, "big")


def read_memory(ser, addr, length):
    command(ser, 0x11)
    send_address(ser, addr)
    ser.write(bytes([length - 1, (length - 1) ^ 0xFF]))
    wait_ack(ser)
    data = ser.read(length)
    if len(data) != length:
        raise BootloaderError(f"short read at 0x{addr:08X}")
    return data


def write_memory(ser, addr, data):
    command(ser, 0x31)
    send_address(ser, addr)
    n = len(data) - 1
    checksum = n
    for b in data:
        checksum ^= b
    ser.write(bytes([n]) + data + bytes([checksum]))
    wait_ack(ser, timeout=2.0)


def mass_erase(ser, commands):
    if 0x44 in commands:            # extended erase
        command(ser, 0x44)
        ser.write(b"\xff\xff\x00")
    else:
        command(ser, 0x43)
        ser.write(b"\xff\x00")
    wait_ack(ser, timeout=30.0)


def go(ser, addr):
    command(ser, 0x21)
    send_address(ser, addr)


def read_region(ser, addr, size):
    out = bytearray()
    for offset in range(0, size, 256):
        out += read_memory(ser, addr + offset, min(256, size - offset))
    return bytes(out)


def wait_for_bootloader(ser, seconds):
    end = time.time() + seconds
    while time.time() < end:
        if try_sync(ser):
            return True
        time.sleep(0.05)
    return False


def leave_bootloader(ser):
    """If the bootloader is already running, jump to the application so the next RST is a fresh test."""
    if try_sync(ser):
        go(ser, FLASH_BASE)
        time.sleep(0.5)
        return True
    return False


def cmd_probe(args):
    ser = open_port(args.port, False, False, args.baud)
    if leave_bootloader(ser):
        log("Bootloader was already running: started the application first")
    ser.close()

    log(f"Cycling DTR/RTS states for {args.wait:.0f} s - press RST every few seconds")
    hits = {state: 0 for state in STATES}
    end = time.time() + args.wait
    for dtr, rts in itertools.cycle(STATES):
        if time.time() >= end:
            break
        ser = open_port(args.port, dtr, rts, args.baud)
        state_end = min(end, time.time() + args.dwell)
        while time.time() < state_end:
            if try_sync(ser):
                pid = get_id(ser)
                hits[(dtr, rts)] += 1
                log(f"  bootloader with dtr={int(dtr)} rts={int(rts)} (chip id 0x{pid:03X})")
                go(ser, FLASH_BASE)
                time.sleep(0.3)
            time.sleep(0.05)
        ser.close()

    for (dtr, rts), n in hits.items():
        log(f"dtr={int(dtr)} rts={int(rts)}: {n} hit(s)")
    return 0 if any(hits.values()) else 1


def request_bootloader(port, baud):
    """Ask the door firmware (src/common/bootloader.cpp) to restart into the ROM bootloader."""
    ser = serial.Serial()
    ser.port = port
    ser.baudrate = baud
    ser.timeout = 0.2
    # DTR asserted holds BOOT0 low, so the firmware's reset starts the app, which then
    # jumps to the bootloader itself and clears its request. With BOOT0 high the reset
    # would enter the bootloader directly and leave the request set for the next start.
    ser.dtr = True
    ser.rts = False
    ser.open()
    # The sensor sleeps in STOP mode: the first byte only wakes it up
    ser.write(b"\n")
    time.sleep(0.2)
    ser.write(BOOTLOADER_COMMAND + b"\n")
    ser.flush()
    time.sleep(0.5)
    reply = ser.read(256)
    ser.close()
    return b"bootloader" in reply


def connect(args):
    """Open the port and wait for the ROM bootloader; returns the port or None."""
    if args.enter:
        if request_bootloader(args.port, args.baud):
            log("Firmware restarted into the bootloader")
        else:
            log("No reply to the bootloader command (power test or factory firmware?) - "
                "press RST on the board now")
    ser = open_port(args.port, args.dtr, args.rts, args.baud)
    if not args.enter:
        log(f"Holding dtr={int(args.dtr)} rts={int(args.rts)} - press RST on the board now")
    if not wait_for_bootloader(ser, args.wait):
        log("No bootloader response")
        ser.close()
        return None
    return ser


def cmd_info(args):
    ser = connect(args)
    if ser is None:
        return 1
    version, _ = get_commands(ser)
    pid = get_id(ser)
    log(f"Bootloader v{version >> 4}.{version & 0xF}, chip id 0x{pid:03X}")
    flash_kib = int.from_bytes(read_memory(ser, FLASH_SIZE_REG, 2), "little")
    uid = read_memory(ser, UNIQUE_ID_REG, 12)
    rdp = read_memory(ser, OPTION_BYTES, 2)
    log(f"Flash size {flash_kib} KiB")
    log("Unique ID " + "".join(f"{b:02X}" for b in uid))
    log(f"Read protection {'off' if rdp[0] == 0xA5 else 'ON'} (RDP byte 0x{rdp[0]:02X})")
    if args.run:
        go(ser, FLASH_BASE)
        log("Started application")
    ser.close()
    return 0


def cmd_flash(args):
    ser = connect(args)
    if ser is None:
        return 1

    version, commands = get_commands(ser)
    pid = get_id(ser)
    log(f"Bootloader v{version >> 4}.{version & 0xF}, chip id 0x{pid:03X}")
    try:
        flash_kib = int.from_bytes(read_memory(ser, FLASH_SIZE_REG, 2), "little")
    except BootloaderError:
        flash_kib = 64
        log("Could not read flash size (read protection?), assuming 64 KiB")
    log(f"Flash size {flash_kib} KiB")

    if args.backup:
        log(f"Backing up {flash_kib} KiB to {args.backup} ...")
        image = read_region(ser, FLASH_BASE, flash_kib * 1024)
        with open(args.backup, "wb") as f:
            f.write(image)
        log("Backup done")

    if args.write:
        with open(args.write, "rb") as f:
            firmware = f.read()
        if len(firmware) > flash_kib * 1024:
            raise BootloaderError("firmware larger than flash")
        log("Erasing ...")
        mass_erase(ser, commands)
        log(f"Writing {len(firmware)} bytes ...")
        for offset in range(0, len(firmware), 256):
            chunk = firmware[offset:offset + 256]
            if len(chunk) % 4:
                chunk += b"\xff" * (4 - len(chunk) % 4)
            write_memory(ser, FLASH_BASE + offset, chunk)
        log("Verifying ...")
        if read_region(ser, FLASH_BASE, len(firmware)) != firmware:
            raise BootloaderError("verify failed")
        log("Verify OK")

    if args.run:
        go(ser, FLASH_BASE)
        log("Started application")
    ser.close()
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    probe = sub.add_parser("probe")
    probe.add_argument("port")
    probe.add_argument("--wait", type=float, default=60)
    probe.add_argument("--dwell", type=float, default=3.0, help="seconds per DTR/RTS state")
    probe.add_argument("--baud", type=int, default=115200)

    def connection_args(sp):
        sp.add_argument("port")
        sp.add_argument("--dtr", type=int, choices=(0, 1), default=0)
        sp.add_argument("--rts", type=int, choices=(0, 1), default=0)
        sp.add_argument("--enter", action="store_true",
                        help="ask the running door firmware to restart into the bootloader")
        sp.add_argument("--wait", type=float, default=60, help="seconds to wait for the bootloader")
        sp.add_argument("--no-run", dest="run", action="store_false", help="do not start the app")
        sp.add_argument("--baud", type=int, default=115200)

    info = sub.add_parser("info")
    connection_args(info)

    flash = sub.add_parser("flash")
    connection_args(flash)
    flash.add_argument("--backup", help="save the existing flash to this file first")
    flash.add_argument("--write", help=".bin to program at 0x08000000")

    args = p.parse_args()
    try:
        if args.cmd == "probe":
            return cmd_probe(args)
        args.dtr, args.rts = bool(args.dtr), bool(args.rts)
        if args.cmd == "info":
            return cmd_info(args)
        return cmd_flash(args)
    except BootloaderError as e:
        log(f"ERROR: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
