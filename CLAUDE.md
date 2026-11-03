# LoRa door sensor: notes for Claude

Four DX-SMART DX-LR30-433M22SP (T1) boards forming two independent pairs (see the board table).
In each pair the **sensor** (battery, reed switch) sends the door state on every heartbeat and on
change, and the **receiver** drives a DOOR output and a NO-LINK output. KEY on each board selects
the mode: sensor heartbeat 5 s / 20 s / 2 min, receiver link timeout 20 s / 65 s / 370 s
(since 2026-11-03; before: 2 s / 10 s / 60 s and 7 s / 33 s / 190 s).
All four are flashed and update over USB-C with one command. Pair 1 is tested end to end; pair 2
was checked for packets arriving on its receiver.
User-facing docs are in [README.md](README.md); this file holds what was learned while building it.

## Hardware (verified on the real boards)

- MCU board **DX-PJ26-V1.1** (silkscreen on the back) with the **LR30-A** radio carrier plugged in
  (SX1262, 433 MHz, crystal, no TCXO). STM32F103C8T6: chip id 0x410, 64 KB flash, ROM bootloader
  v2.2, read protection off.
- The vendor schematic `LR30-SP-PCBA-schematic.pdf` (DX-SMART package) is for a **different board**. Trust
  the table below, not that schematic.
- USB-serial is a 10-pin CH340 (E/X), powered from the 3.3 V rail (user checked). **BOOT0
  follows DTR** (measured 2026-10-25 with an ST-LINK: reset over SWD in each state):
  DTR deasserted or port closed = BOOT0 high = every reset starts the ROM bootloader; DTR
  asserted = app. RTS does nothing, and nothing drives NRST (no auto-reset). At power-up the app
  starts (the CH340 isn't driving DTR yet). The earlier "DTR/RTS do nothing" was wrong.
  **Risk:** with USB connected and no program holding DTR, or possibly on battery (CH340 still
  powered), a watchdog reset lands in the bootloader and the board stays there until a power
  cycle. Not tested on battery yet; the real fix is to break the DTR-BOOT0 link on the board.
- SWD header next to PA9..PB14, labelled `C D G V` = SWCLK, SWDIO, GND, 3V3 (ST-Link fallback).

| Function | Pin | Notes |
|---|---|---|
| SX1262 SCK/MISO/MOSI/NSS | PA5/PA6/PA7/PA4 | SPI1 |
| SX1262 NRESET / BUSY / DIO1 | PA3 / PA2 / PC15 | PC15 also has the 32 kHz crystal, so LSE is unusable |
| RF switch TXEN / RXEN | PA0 / PA1 | high = that path active (RadioLib `setRfSwitchPins(rx, tx)`) |
| "LED" LED (next to RST) | PB11 | **active high** (found by testing; another project claimed active low) |
| KEY button | PB12 to GND | mode step on both boards (`src/common/door_mode.*`) |
| Sensor reed input | PB13 (header pin 25) | moved off PB12 so KEY is free; wire the reed here on sensor boards 1 and 3 |
| Log UART | PA9 TX / PA10 RX | USART1, 115200 8N1 |
| Receiver outputs | PB13 DOOR, PB14 NO-LINK | 3.3 V push-pull |
| POW LED | always on | power indicator |

Radio init follows the vendor reference code: DC-DC regulator, XTA/XTB trim 0x04/0x2F.

Boards (network IDs here are examples; pick your own):

| Board | Role | Network ID / PlatformIO env |
|---|---|---|
| 1 | pair 1 sensor | 0xA001 / `sensor` |
| 2 | pair 1 receiver | 0xA001 / `receiver` |
| 3 | pair 2 sensor | 0xA002 / `sensor_pair2` |
| 4 | pair 2 receiver | 0xA002 / `receiver_pair2` |

Boards plugged into the same USB socket get the same COM number, so a COM port does not identify
a board. Before uploading, identify it: `stm32_uart_flash.py info <port> --enter` prints the chip's
unique ID (it restarts the app afterwards); note each board's ID once. Flashing the wrong pair's env breaks both links.
Each pair's network ID comes from `-D NETWORK_ID` in platformio.ini (default 0xA001 in config.h).

Check which board is on a port before flashing: `serial_log.py` shows `TX seq=` (sensor) or `RX seq=`
/ quiet (receiver), or run `stm32_uart_flash.py info <port> --enter` and compare the unique ID.

## Toolchain

- PlatformIO Core 6.1.19 is installed but **not on PATH**:
  `%USERPROFILE%\.platformio\penv\Scripts\pio.exe` and `...\penv\Scripts\python.exe` (has pyserial).
  Run scripts with `python.exe -I`.
- Platform `ststm32`, board `genericSTM32F103C8`, framework Arduino = STM32duino core 3.x
  (package `framework-arduinoststm32` 4.30000). RadioLib 7.8.1. No other libraries.
- Build `pio run`; upload `pio run -e sensor -t upload --upload-port COM14`
  (receiver: `-e receiver ... COM13`).
- After a firmware change, refresh the mcuisp exports (built with the example network IDs):
  `arm-none-eabi-objcopy -O ihex .pio/build/<env>/firmware.elf firmware/door_<env>.hex`
  (toolchain in `%USERPROFILE%\.platformio\packages\toolchain-gccarmnoneeabi\bin`).

## Flashing

- **Normal path** (board runs this firmware): the upload command runs
  `tools/stm32_uart_flash.py flash <port> --enter --write firmware.bin`. `--enter` sends `\n`
  (wakes the sleeping sensor through an EXTI on PA10), then `#DOOR-BOOTLOADER#`, **with DTR
  asserted** (BOOT0 low). The firmware sets `BKP->DR1 = 0xB007` and resets;
  `bootloaderCheckOnBoot()` (first line of `setup()`, before the watchdog starts) jumps to the ROM
  bootloader at 0x1FFFF000 only if the flag is set **and** RCC_CSR shows a software reset, then
  clears the reset flags. About 20 s per upload.
- **Hang fixed 2026-10-25:** the flasher used to send the command with DTR deasserted, so the
  reset entered the bootloader through BOOT0 and the flag was never consumed. After the upload,
  Go started the app, which saw the flag and jumped back into the bootloader: no log, and every
  RST also went to the bootloader (BOOT0 high), until a power cycle. Each boot now logs
  `Boot RCC_CSR=... BKP_DR1=... now ...`. Verified on board 1: upload, `info --enter`, and SWD
  reset all come back to the app.
- **ST-LINK (SWD)**: `pio run -e sensor_swd -t upload` (also `receiver_swd`, `*_pair2_swd`).
  OpenOCD resets after programming, so keep the COM port open with DTR asserted (e.g. run
  `serial_log.py`) or the chip boots into the bootloader. A sleeping sensor can't be attached
  (STOP stops the debug clock), and no NRST wire is fitted. Verified 2026-10-25 on board 1 (9.5 s,
  Verified OK, boots): `stm32_uart_flash.py info COM10 --enter --no-run` (parks it in the ROM
  bootloader, awake), `serial_log.py COM10 -t 75` in the background, then the swd upload.
  **Board 1 now has ST-LINK pin 15 (NRST) wired to its RST button**, and `[swd]` passes
  `reset_config srst_only srst_nogate connect_assert_srst`, so `pio run -e sensor_swd -t upload`
  works on the sleeping board with no USB (verified 2026-10-25, Verified OK).
- **Checking a board without UART**: attach without reset and read a RAM counter during the brief
  wake-ups, e.g. `seq` (`arm-none-eabi-nm -C firmware.elf | grep seq`, was 0x200005ac):
  `openocd ... -c init -c halt -c "mdh <addr>" -c resume -c shutdown`, retried until it catches an
  awake window. Board 1 counted 2 -> 3 in ~10 s after the SWD upload. Power-cycle after a
  debug session before measuring sleep current. Wiring (V3SET adapter 20-pin): C->9 SWCLK,
  D->7 SWDIO, G->4 GND, V->1 T_VCC (sense only; the board needs its own power).
- **First flash / board without this firmware**: given BOOT0-follows-DTR, `flash <port> --wait 30
  ...` without `--enter` (holds DTR deasserted) plus one RST press should be enough; untested on a
  factory board. The old method: user opens the vendor's `mcuisp.exe`, COM port,
  "Reset@DTR Low(<-3V),ISP@RTS High", **Read ChipInfo**, presses RST until "Connect Ok", then closes
  mcuisp. The bootloader stays running; then run the flasher **without** `--enter`
  (`flash <port> --wait 5 --backup backup/x.bin --write ...`). Holding DTR/RTS in any state while
  the user pressed RST never worked (tested all four), and PlatformIO's bundled stm32flash 0.4 can't
  do it either; why mcuisp succeeds is unknown.
- Factory firmware (vendor demo V1.2.35: 9600-baud UART-to-LoRa bridge, 433 MHz SF9 CR4/6 CRC
  off): back it up with `flash <port> --backup backup/boardN_factory.bin ...` before the first
  flash; restore with `flash <port> --write backup/boardN_factory.bin`. Not included here.

## Firmware

- `include/config.h`: every pin, radio setting and timing. Both boards must match.
  Current radio settings: **433.5 MHz, SF12, BW 125 kHz, CR 4/5, 22 dBm**, sync word 0x12,
  preamble 8, CRC on (SF8 -> SF10 -> SF12, each at the user's request; SF12 since 2026-11-03:
  ~991 ms airtime, LDRO switched on automatically by RadioLib since the symbol is 32.8 ms).
  Each packet adds ~1.0 s of active time to the heartbeat. Heartbeats changed afterwards to
  5 s / 20 s / 2 min (spacing ~6 / ~21 / ~121 s at SF12) with link timeouts 20 / 65 / 370 s,
  just over 3 spacings so 2 missed packets in a row are tolerated. Measured timings and
  currents elsewhere in this file are SF10 with the old 2 s / 10 s / 60 s heartbeats.
  Verified on pair 1 (2026-11-03): SF12 at 14 dBm and at 22 dBm, every packet 3.0 s apart (fast
  mode), RSSI -12 dBm, SNR ~6 dB on the bench. The receiver logs `ferr=` (sensor carrier minus
  receiver, `getFrequencyError()`): ~2.2 kHz between boards 1 and 2 (~5 ppm), drifting a few Hz
  per packet, far inside SF12's tolerance. A first SF12 test heard nothing; at that time the
  ST-LINK had vanished from the PC with its wires (NRST included) still on board 1, so board 1
  was probably held in reset by the unpowered probe (not proven). Unplug the probe's wires, not
  only its USB, before using a board standalone.
- `LORA_SF`, `LORA_BW_KHZ` and `LORA_TX_POWER_DBM` are `#ifndef`-guarded for test builds:
  `PLATFORMIO_BUILD_FLAGS="-D LORA_SF=10" pio run -e receiver`. Changing that variable makes
  PlatformIO wipe **all** of `.pio/build`, so flash each test build before building the next.
- `src/common/door_protocol.*`: 10-byte packet (magic 0xD5, version, network ID 0xA001, type,
  door, seq, VDD in 20 mV, CRC-8 poly 0x07).
- `src/common/door_radio.*`: RadioLib setup. Keep our own `Module` object: `SX126x::getMod()` and
  `writeRegister()` are protected in RadioLib 7.8. Use `radio.tcxoVoltage = 0` and `begin(ConfigLoRa_t)`.
- `src/common/door_bootloader.*`: serial command to ROM bootloader (see Flashing).
- `src/sensor/sleep_timer.*`: own STOP-mode sleep on the F1 RTC clocked from LSI, prescaler 32,
  LSI calibrated against `micros()` at boot and hourly (measured ~39.5 kHz). Not STM32LowPower:
  its calendar-based alarms break when the prescaler is recalibrated.
- `src/sensor/main.cpp`: reed on PB13, internal pull-up (user chose to keep it over an external
  500k) + EXTI both edges, 30 ms debounce, TX on change and on every heartbeat. KEY (PB12, EXTI
  falling) steps the mode in `src/common/door_mode.*`: fast/normal/slow = `TX_PERIOD_FAST_MS` 5 s /
  `TX_PERIOD_MS` 20 s / `TX_PERIOD_SLOW_MS` 120 s (old 2 / 10 / 60 s measured 2.3 / 10.3 / 60.4 s
  at SF10). Every power-up starts in slow (`MODE_AT_BOOT`, user's choice 2026-11-03) on both
  boards; KEY changes the mode until the next power-up and is no longer saved (the EEPROM
  emulation is gone). LED: 1/2/3 blinks = fast/normal/slow, at boot
  and on each press. IWDG max is ~26 s, so the sensor sleeps in `SLEEP_CHUNK_MS` 15 s chunks and
  `sleepTimerSleep(ms, &sleptMs)` reports real sleep time: early wake-ups (noise, serial) shorten
  `untilHeartbeatMs` instead of restarting it; any packet restarts it. Door edges are not changes: touching the PB13 wire made
  the old build transmit nonstop (mains hum on every edge). Now `readDoorStable()` needs
  `DOOR_STABLE_MS` 10 ms of agreement (gives up after 200 ms = noise), a packet goes out only if
  the state differs from the last one sent, then a `DOOR_HOLDOFF_MS` 500 ms hold-off. Each change
  is sent `DOOR_CHANGE_REPEATS` 3 times, `DOOR_REPEAT_GAP_MS` 1 s apart (1.3 s measured), awake
  in `waitDoorUnchanged()`; a different stable state during the repeats aborts them and is sent
  next (edges ignored for the first 500 ms of each gap). Log reasons: `change`, `repeat`. Verified on
  board 3: finger on the wire sends nothing. Recommended hardware: 100 nF PB13-GND at the board
  (tau ~4 ms with the internal pull-up). Loop skips sleeping while a door/KEY edge is pending,
  so a change during a transmission is no longer delayed to the next heartbeat. LSI recalibration
  counts elapsed heartbeat time, not cycles. Transmit is
  `startTransmit` + poll DIO1 so the LED flash (`SENSOR_LED_FLASH_MS` 20 ms, off when
  `SENSOR_LED_ENABLED` 0) overlaps the airtime instead of lasting the whole ~0.3 s; actual period = sleep + active time (~0.3 s at SF10).
  Link loss can be tested without the user: park the sensor with
  `stm32_uart_flash.py info COM14 --enter --no-run`, restart it with `info COM14` (verified 35.0 s
  with the earlier fixed 35 s timeout). IWDG 20 s (keeps
  running in STOP). Unused pins set to analog. PA10 RX gets a pull-up after `attachInterrupt()`
  so it can't float and wake the MCU via its EXTI if the CH340 is removed. Each TX log line ends
  with `wakes=N awake=Mms` since the previous packet (`millis()` stops in STOP, so it is awake
  time).
- Sleep current, measured 2026-10-25 on the Otii with 3.3 V into the 3V3 pin: **flat 32 mA floor**
  plus TX spikes. Not PB13 noise (same with PB13 shorted to GND). The user confirmed the
  **CH340 is powered from the 3.3 V rail**, so it draws whenever the sensor does. The MCU does
  sleep: on USB the log shows `wakes=0 awake=307ms` per 10.3 s heartbeat. So the floor is board
  hardware (CH340, POW LED, ...), not firmware.
- Board 1 with `power_test`, LR30-A unplugged, Otii 3.3 V on 3V3: **30 mA** floor. The user then
  **removed the CH340 and the POW LED resistor from board 1**: floor **1.7 mA**. Then removed the
  **AMS1117** (back-fed from 3V3 it drew ~1.7 mA): floor **21 uA** = the F103's STOP current
  (2026-10-25). So a battery sensor board needs all three removed: CH340, POW LED resistor,
  AMS1117.
- With the LR30-A plugged in, the sensor firmware slept at **26.8 mA**: RadioLib's default RF
  switch table drives RXEN (PA1) low in idle/sleep, and something on the LR30-A drives that line
  high (~120 Ohm equivalent), so PA1 sank ~26 mA. Found with `pin_test` (floor jumped exactly at
  the "RXEN low" step). Fix in `door_radio.cpp`: custom switch table, RXEN high in idle/RX, low
  only in TX (as the vendor's RxEn/TxEn). After the fix: 369 uA with the ST-LINK attached,
  **15 uA with the ST-LINK disconnected** (measured with `sleep_test`, radio asleep as in the
  sensor). TX is 144 mA for 0.29 s; it still includes ~26 mA of RXEN-low contention during TX
  (vendor behaviour kept; driving RXEN high or floating during TX is untested for range).
- **Measure sleep current with the ST-LINK unplugged** (it adds ~350 uA through SWD/NRST) and
  with DBGMCU_CR = 0: OpenOCD's stm32f1x.cfg writes 0x307 (debug in STOP/STANDBY) on every
  connect and it survives resets. For SWD sessions that must not touch it, add
  `-c "stm32f1x.cpu configure -event examine-end {}"` after the target cfg, or power-cycle.
- Test firmwares (not in default_envs, upload over SWD): `power_test` (LED + STOP, all pins
  analog), `pin_test` (adds one radio pin's sleep state per 10 s step), `sleep_test` (radio asleep
  as in the sensor, releases one pin per step). The LED blinks the step number. **Board 1 can no longer be flashed or powered over USB**:
  ST-LINK (SWD) only, power on 3V3. With the CH340 gone, DTR no longer drives BOOT0, so the
  watchdog-reset-into-bootloader risk should be gone on board 1 (check: RST gives the boot blinks).
- `src/power_test/main.cpp` (env `power_test`, not in default_envs): board current isolation.
  5 boot blinks (~2 s awake, room to attach an ST-LINK), then STOP via `sleep_timer` with a 20 ms
  LED flash every 10 s. No Serial, no radio (carrier unplugged), no IWDG; JTAG off (SWD kept),
  all other pins analog. No bootloader command: uploads to or from it need an RST press, which
  works because the flasher holds DTR deasserted (BOOT0 high). Built, not yet measured.
- `src/receiver/main.cpp`: continuous RX with DIO1 interrupt, boosted RX gain, DOOR holds the last
  state when the link is lost, radio re-initialised every 60 s while down, IWDG 4 s. KEY polled
  in the loop, steps the link timeout `LINK_TIMEOUT_FAST_MS` 20 s / `LINK_TIMEOUT_MS` 65 s /
  `LINK_TIMEOUT_SLOW_MS` 370 s (same `door_mode` module and LED blinks). The user sets sensor and
  receiver to the same mode by hand; a mismatch (e.g. sensor 2 min, receiver 65 s) gives false
  link loss.

## Tools

- `tools/stm32_uart_flash.py`: `info`, `flash`, `probe` (see `--help`).
- `tools/serial_log.py COM13 COM14 -t 30`: both logs side by side, DTR asserted (resets start
  the app), RTS released. `pio device monitor` also asserts DTR (`monitor_dtr = 1`).
- `tools/lora_options.py`: recomputes `docs/lora-options.html` (all SF/BW/power options: airtime,
  battery, range); reads the current setting from `config.h`.
- `mcuisp.exe`: vendor flashing tool from the DX-SMART package (user runs it, not Claude).
- Board photos: `docs/board-photos/dx-pj26-front.webp`, `dx-pj26-back.webp`. Vendor PDFs, datasheets
  and reference code: see `docs/vendor/README.md` (links; the files are not included).

## Gotchas already hit

- The generic F103C8 variant puts `Serial` on USART2 = PA2/PA3 = radio BUSY/NRESET. platformio.ini
  sets `SERIAL_UART_INSTANCE=1`, `PIN_SERIAL_RX=PA10`, `PIN_SERIAL_TX=PA9`. `HardwareSerial(rx, tx)`
  does not compile on core 3.x (abstract class).
- Don't name a project header `bootloader.h`: it shadows the core's SrcWrapper header.
- Don't add `-D RADIOLIB_EXCLUDE_STM32WLX`: RadioLib already defines it on non-WL targets.
- Receiver: read `millis()` **after** handling a packet, or `now - lastValidMs` underflows and the link
  flaps (LINK UP / LINK LOST on every packet). Fixed.
- The built-in browser pane can't screenshot `file://` pages; serve with
  `python -m http.server --bind 127.0.0.1` and open localhost.
- The user is often away from the board: run listeners for minutes, not seconds, when asking them
  to press buttons.

## Battery power (planned, not built yet)

Sensor on one 21700 Li-ion cell: holder -> TP4056 USB-C charger **with protection** (B+/B-, OUT+/OUT-)
-> user-bought **TPS63802 buck-boost module, 3.3 V version** (TI: 1.3-5.5 V in, >1.8 V to start,
2 A at 3.3 V, 11 uA quiescent) -> board **3V3 pin** + GND (never the +5V pin: the AMS1117 needs ~4.4 V).
Charge through the TP4056's USB-C; the sensor can run while charging. User ordered a "TP4056 18650
Lithium Battery Charging Board" (fine for 21700). The listing claims overcharge + over-discharge
protection (so likely the 6-pad DW01A + 8205A version; confirm on arrival) and "5-20 V input",
which is wrong: TP4056 is 4.5-5.5 V operating, 8 V absolute max. Use 5 V USB only (USB-A to C cable
if the board lacks the Type-C CC resistors). If unprotected, add a 1S protection board. Behind the regulator the
packet's `vdd` will always read 3.30 V; measuring the cell needs a divider to a free ADC pin (e.g.
PB0, 2 x 1 MOhm + 100 nF), offered but not done. Estimated ~50 days on 5000 mAh at SF10/22 dBm/10 s.

Enclosure: `enclosure/` (CadQuery source, STEP for Fusion 360, STL for the resin printer). Battery
holder and board stack are in line; the charger stands on edge beside the battery, components and
USB-C toward the wall (USB-C out the end wall; nothing may touch that side: a floor rib there
touched the parts in the first print), held by a back rib and a plate behind its rear edge (board
28.26 mm including rear-corner ears; wire pads are at that edge, so nothing may reach onto the
faces there). The first print's USB hole had to be opened 1.2 mm up (receptacle off-centre; now
`USB_Z_OFF`). The reed board stands on edge beside the board, against the opposite long wall.
Receiver box: `enclosure/receiver_box.py` (board + Shelly UNI 38.5 x 20.7 standing on edge beside
it, two snap tabs + four M3 corner screws, lid holes with short guide cylinders over KEY/RST, push
stick, 3 mm holes over the two perfboard LEDs). Switch and LED positions come from a top photo
(homography on the 4 mounting holes + perfboard height correction, ~+-0.8 mm); check image
`enclosure/receiver_hole_check.png`. The Shelly's parts reach its PCB edges on both faces, so
nothing may grip it: a partition wall between it and the board (open at both ends for wires)
keeps it in its lane. Its lane's end walls are closed (user's choice).
SMA centre 12.5 mm from the PB header edge (user-confirmed); KEY is on that edge, RST on the
PC13 edge. With the component side up and the USB end at low X, the PB edge is at low Y (both
boxes). The sensor's reed slot is on the high-Y (PC13) wall, so its wires cross the board.
The base/lid split is at the SMA centre height. The board sits on printed pins in its mounting
holes (65.5 x 24.5 mm centres, user-measured; PCB 72 x 30), with no nylon standoffs. Run it with a
venv that has `cadquery` (not the PlatformIO penv). SMA centre 12.5 mm from the PB header edge
(user-confirmed), carrier flush with the PCB end. Perfboard overhang and the reed
board size are estimates from photos (see its README).

## Open items

- Firmware per board (2026-10-25): all four run commit 9a74d9d (RXEN fix, wake log, bootloader
  fix). Verified on the bench: board 2 receives board 1 (13/13 packets, RSSI -6..-9 dBm), board 4
  receives board 3 (every packet, RSSI 0 dBm) and logs `RX ignored` for board 1, so two pairs
  side by side work. Board 4 once heard nothing from board 3 for ~75 s while board 3's LED
  flashed; it worked after board 3 was re-powered (cause not found: power source or antenna?).
  Pair 2 has every feature tested on hardware; pair 1 only its normal-mode link (10.3 s). Board 1's
  reed wire must be on PB13. Not yet tested: mode persistence across a power cycle, link-loss
  timing at 7 s / 190 s, and both pairs powered together (`RX ignored` for the other pair).
- At 2 s the sensor transmits ~12.6% of the time at SF10 (over the usual 10% limit) and uses ~4x
  the battery of 10 s mode. Option: send the sensor's mode in the packet so the receiver follows
  it automatically (not done; the user chose a KEY on each board).
- PB13/PB14 output voltages not measured with a meter (logic verified in the log only).
- Sleep floor measured: 15 uA on board 1 with the radio asleep (CH340, POW LED resistor and
  AMS1117 removed, RXEN fix, see Firmware). Average is dominated by TX (144 mA x 0.29 s): ~4.1 mA
  at SF10 / 22 dBm / 10 s (~51 days on 5000 mAh), ~0.7 mA at 60 s (~10 months). Confirmed with
  the final `sensor` firmware, ST-LINK unplugged, power-cycled: **15.6 uA** floor, TX 145 mA for
  0.29 s (fast mode: 21.5 mA average over 6 s). Normal mode, one 10.31 s period: **4.09 mA
  average, 11.7 uAh per period**, i.e. ~42 mAs per packet of which 99.6% is the transmission.
  Behind the TPS63802 (user's module), Otii at **3.7 V** into its input = battery current:
  **31 uA sleep** (TPS63802 ~11 uA quiescent + conversion loss at 15.5 uA load), **140 mA TX**
  (145 mA at 3.3 V x 3.3/3.7 / ~92% efficiency). `tools/lora_options.py` uses SLEEP_UA = 31 and
  writes it into the page (spec strip, method note, JS constant); page republished 2026-10-25. The reed's internal pull-up (~80 uA while the door is
  closed) is now 4x the sleep floor: an external 1 MOhm pull-up would cut it to ~3 uA.
- 22 dBm exceeds the usual 10 mW licence-free limit at 433 MHz; the user chose it.
