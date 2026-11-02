# LoRa door sensor

Two DX-SMART **DX-LR30-433M22SP (T1)** kits: a **DX-PJ26-V1.1** MCU board (STM32F103C8T6, USB-C via
a CH340) with the **LR30-A** radio carrier (Semtech SX1262, 433 MHz) plugged in.

- **Sensor** (battery): reads a reed switch and sends the door state on every heartbeat (2 s, 10 s
  or 1 min, selected with KEY; default 10 s), and immediately when the door changes. Each change
  is sent 3 times, about 1.3 s apart, so one lost packet doesn't matter. Sleeps in STOP mode
  between transmissions.
- **Receiver**: drives a DOOR output (1 = open, 0 = closed) and a NO-LINK output (1 = no valid
  packet for the link timeout: 7 s, 33 s or 190 s, selected with KEY; default 33 s). While the link
  is down, DOOR keeps the last received state.

## Wiring

| Board | Pin | Header pin | Function |
|---|---|---|---|
| Sensor | PB13 | 25 | Reed switch to GND (internal pull-up). Closed = 0 (door closed), open = 1 (door open). Add a **100 nF** ceramic capacitor from PB13 to GND at the board (pins 25 and 23) against noise; twist the reed wires if longer than ~1 m. |
| Both | PB12 | (KEY) | On-board **KEY** button: each press steps to the next mode, fast → normal → slow → fast. Sensor heartbeat **2 s / 10 s / 1 min**, receiver link timeout **7 s / 33 s / 190 s**. The LED confirms with **1 / 2 / 3 blinks** (also at power-up). Set both boards of a pair to the same mode. The setting survives power loss but returns to normal (2 blinks) after a firmware upload. |
| Receiver | PB13 | 25 | DOOR output, 3.3 V push-pull |
| Receiver | PB14 | 26 | NO-LINK output, 3.3 V push-pull |
| Both | GND | 18 / 23 | Ground |

Outputs give 3.3 V and at most ~8 mA. Use a transistor or optocoupler for relays or 5 V inputs.

LEDs: the "LED" LED (PB11, next to RST) gives a short 20 ms flash on every transmission (sensor) and
blinks on every valid packet (receiver; it stays off while the link is down). Set
`SENSOR_LED_ENABLED` to 0 in `include/config.h` to keep the sensor LED off. The red "POW" LED is the
power indicator; on a battery-powered sensor, remove it if it lights (it may draw 0.3-1.5 mA).

**Attach an antenna before powering a board** (either the board SMA or the module U.FL, not both).
Transmitting at 22 dBm without an antenna can damage the radio.

## Tools (all free, no registration)

1. [VS Code](https://code.visualstudio.com/) with the **PlatformIO IDE** extension (VS Code offers it
   when you open this folder).
2. CH340 USB-serial driver: installed automatically by Windows Update on most PCs; otherwise from
   [WCH](https://www.wch-ic.com/downloads/ch341ser_exe.html).

PlatformIO downloads the ARM GCC toolchain, the STM32 Arduino core, RadioLib and `stm32flash` on the
first build.

## Build

In VS Code: PlatformIO sidebar, then **Build** under `sensor` or `receiver`. From a terminal:

```
pio run
```

## Flash (USB-C)

Uploads use [tools/stm32_uart_flash.py](tools/stm32_uart_flash.py) and the STM32's ROM serial
bootloader. The DX-PJ26 board has no automatic reset circuit, so the door firmware restarts
itself into the bootloader when the tool sends a command over USB. The CH340's DTR line drives
BOOT0: while no program holds DTR asserted (port closed), any reset (RST, watchdog) starts the
ROM bootloader instead of the firmware, until the next power cycle. `tools/serial_log.py` and
`pio device monitor` assert DTR, so resets while logging start the firmware.

**Board already running this firmware** (normal case): no buttons needed.

```
pio run -e sensor -t upload --upload-port COM14
pio run -e receiver -t upload --upload-port COM13
```

**Several pairs:** each sensor/receiver pair needs its own network ID, or each receiver also
accepts the other pair's sensor. Pair 1 uses the `sensor` / `receiver` builds (0xA001), pair 2 uses
`sensor_pair2` / `receiver_pair2` (0xA002). Add more pairs the same way in `platformio.ini`. COM
numbers follow the USB socket, not the board, so check which board you have first:
`python tools/stm32_uart_flash.py info COM14 --enter` prints its unique ID (note each board's ID once).
The network IDs 0xA001 / 0xA002 are examples: pick your own in `platformio.ini`.

Or use **Upload** in the PlatformIO sidebar (set `upload_port` if more than one board is plugged in).

**First flash of a board with the factory firmware** (once per board):

1. Open the vendor tool `mcuisp.exe` (vendor package, `05 Testing Tools\STM32F103 burning tool`),
   select the COM port and "Reset@DTR Low(<-3V),ISP@RTS High", click **Read ChipInfo** and press
   RST on the board until it shows "Connect Ok". Close mcuisp: the bootloader stays running.
2. Back up the factory firmware and flash (the tool picks up the running bootloader):

   ```
   python tools/stm32_uart_flash.py flash COM14 --backup backup/boardN_factory.bin --write .pio/build/sensor/firmware.bin
   ```

   (`python` = `%USERPROFILE%\.platformio\penv\Scripts\python.exe` if Python isn't on your PATH.)
   Alternatively flash the matching `firmware/door_*.hex` (pair 2 files end in `_pair2`; built with the
   example network IDs) with mcuisp itself.

The board also has an SWD header (C = SWCLK, D = SWDIO, G = GND, V = 3.3 V) for an ST-Link.

Label the boards afterwards. Keep the factory firmware backups (`backup/`, not included here).

## Serial log (115200 baud)

```
pio device monitor -e receiver --port COM6
```

The sensor prints `TX seq=… door=… vdd=… (reason) wakes=… awake=…ms` (early wake-ups from
STOP and time spent awake since the previous packet); the receiver prints `RX seq=… door=… rssi=… snr=… vdd=…`
plus `LINK UP` / `LINK LOST`. Both print `RADIO OK` at start-up.

## Test

1. Power both boards. Receiver log shows a packet about every 10 s; NO-LINK (PB14) goes to 0.
2. Connect the sensor's PB13 (header pin 25) to GND: receiver PB13 goes to 0 within a second.
   Remove the wire: back to 1.
3. Press KEY once on the sensor and once on the receiver: 3 blinks each, packets every ~60.3 s.
   Again: 1 blink each, packets every ~2.3 s. Again: 2 blinks each, back to ~10.3 s.
4. Unplug the sensor: one link timeout (33 s in normal mode) after its last packet, receiver PB14
   goes to 1 and PB13 keeps its value.

## Configuration

Everything is in [include/config.h](include/config.h): pins, frequency (433.5 MHz), spreading factor,
TX power, timings and `NETWORK_ID`. Both boards must use the same values. Change `NETWORK_ID` if
another installation of this project is nearby.

**TX power** is 22 dBm. Licence-free 433 MHz use is usually limited to 10 mW (10 dBm); check
your local rules.

## Battery operation (sensor)

- Average current at SF10 / 22 dBm (118 mA radio + ~20 mA MCU for ~289 ms per packet), 5000 mAh
  21700, before board overhead: **2 s** ~17.5 mA, ~12 days; **10 s** ~4 mA, ~50 days;
  **1 min** ~0.7 mA, ~9 months. At 2 s the radio is on air ~12.6% of the time (over the usual
  10% limit). Lower SF or a longer TX interval saves the most; see
  [docs/lora-options.html](docs/lora-options.html) for every option.
- Feed 3.0–3.6 V (2×AA, or a LiFePO4 cell) directly to a **3V3** pin. Do not use the +5V pin
  (the AMS1117 regulator wastes several mA) and do not feed a 4.2 V Li-ion cell to 3V3.
- **Prepare the sensor board for battery use** (measured on board 1 with an Otii, 3.3 V on 3V3):
  stock board ~30 mA asleep; without the CH340 and the POW LED resistor 1.7 mA; also without the
  AMS1117 regulator (back-fed through its output) **21 µA**, the STM32's own STOP current. After
  this the USB-C port neither powers nor programs the board: update it with an ST-LINK on the
  SWD header (`pio run -e sensor_swd -t upload`).
- The reed switch draws ~80 µA through the internal pull-up while the door is closed.

## Board power test

`pio run -e power_test -t upload --upload-port COMx` flashes a test firmware that only blinks
the LED 5 times, then sleeps in STOP mode with a 20 ms LED flash every 10 s. No UART, no radio,
no watchdog, every unused pin analog. Unplug the LR30-A radio carrier first (with power off),
then measure the board on a 3V3 pin: the floor between flashes is the board's own consumption.
The test firmware does not answer the bootloader command, so press RST when the upload asks
(also when going back to `sensor`).

## How it works

- LoRa 433.5 MHz, SF10, 125 kHz, CR 4/5, private sync word, hardware CRC. Packet: 10 bytes with
  network ID, door state, sequence number, supply voltage and a CRC-8; anything else is ignored.
- Radio setup follows the vendor reference code: DC-DC regulator, crystal (no TCXO), crystal trim
  XTA=0x04/XTB=0x2F, RF switch on TXEN (PA0) / RXEN (PA1).
- The board's 32 kHz crystal shares PC15 with the radio's DIO1, so the sensor's sleep timer runs on
  the internal LSI oscillator. Its frequency is measured against the CPU clock at boot and hourly.
- Both boards use the independent watchdog (sensor 20 s, receiver 4 s). The receiver re-initialises
  the radio every 60 s while the link is down.
- Serial command `#DOOR-BOOTLOADER#` (115200 baud) stores a flag in a backup register and resets;
  the next boot jumps to the ROM bootloader before the watchdog starts. The sleeping sensor is woken
  by serial activity and listens for 1.5 s.

## Project layout

```
platformio.ini          build/upload settings for both boards
include/config.h        pins, radio settings, timings
src/common/             packet format, radio setup, bootloader command (shared)
src/sensor/             sensor firmware and STOP-mode sleep timer
src/receiver/           receiver firmware
tools/stm32_uart_flash.py   USB flasher: info / flash / probe (STM32 ROM bootloader protocol)
tools/serial_log.py         serial log of one or more boards side by side
tools/lora_options.py       regenerates docs/lora-options.html from config.h
firmware/               .hex exports for mcuisp
docs/lora-options.html  comparison of all SF / bandwidth / power options
docs/vendor/README.md   where to get the vendor manuals, schematic, datasheets, reference code
docs/board-photos/      front and back of the DX-PJ26 board
enclosure/              3D-printable snap-fit box (CadQuery source, STEP, STL)
CLAUDE.md               engineering notes (hardware facts, flashing, gotchas, open items)
```

## Tools

Run them with PlatformIO's Python (`%USERPROFILE%\.platformio\penv\Scripts\python.exe`) if Python
isn't on your PATH.

```
python tools/serial_log.py COM13 COM14 -t 60
python tools/stm32_uart_flash.py info COM14 --enter
python tools/lora_options.py --print
```

## License

[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) (full text in [LICENSE](LICENSE)):
free to use, share and adapt with attribution, not for commercial use. RadioLib and the STM32duino
core keep their own licenses. Vendor documents and tools are not included; see
[docs/vendor/README.md](docs/vendor/README.md) for where to get them.
