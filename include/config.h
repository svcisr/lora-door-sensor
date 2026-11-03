// Project configuration shared by the sensor and the receiver.
// Both boards must be built with the same radio settings and NETWORK_ID.
#pragma once

#include <Arduino.h>

// ---------------------------------------------------------------------------
// Board wiring: DX-PJ26-V1.1 MCU board + LR30-A radio carrier
// (radio pins from the vendor reference code LR_driver/UserConfig.h)
// ---------------------------------------------------------------------------
#define PIN_LORA_NSS    PA4
#define PIN_LORA_SCK    PA5
#define PIN_LORA_MISO   PA6
#define PIN_LORA_MOSI   PA7
#define PIN_LORA_RESET  PA3
#define PIN_LORA_BUSY   PA2
#define PIN_LORA_DIO1   PC15   // shares the pin with the 32.768 kHz crystal: LSE unusable
#define PIN_LORA_TXEN   PA0    // RF switch, high while transmitting
#define PIN_LORA_RXEN   PA1    // RF switch, high while receiving

#define PIN_LED         PB11   // user LED ("LED", next to RST)
#define LED_ON          HIGH   // active high
#define LED_OFF         LOW
// Log output: Serial = USART1 on PA9/PA10 -> CH340C -> USB-C (set in platformio.ini)

// ---------------------------------------------------------------------------
// Application I/O
// ---------------------------------------------------------------------------
// Sensor: reed switch between PB13 (header pin 25) and GND (internal pull-up).
// Contact closed (magnet near, door closed) = 0, contact open = 1.
#define PIN_DOOR_IN     PB13

// On-board KEY button (PB12 to GND), on both boards. Each press steps to the next
// mode: fast -> normal -> slow -> fast (sensor heartbeat / receiver link timeout).
#define PIN_KEY         PB12

// Receiver: 3.3 V push-pull outputs, max ~8 mA each.
#define PIN_DOOR_OUT    PB13   // 1 = door open, 0 = door closed
#define PIN_NOLINK_OUT  PB14   // 1 = no valid packet for LINK_TIMEOUT_MS

// ---------------------------------------------------------------------------
// Radio
// ---------------------------------------------------------------------------
#define LORA_FREQ_MHZ       433.5f
#ifndef LORA_BW_KHZ
#define LORA_BW_KHZ         125.0f
#endif
#ifndef LORA_SF                     // tests can override it: PLATFORMIO_BUILD_FLAGS="-D LORA_SF=10"
#define LORA_SF             12      // ~991 ms per packet, LDRO on (see docs/lora-options.html)
#endif
#define LORA_CR             5       // coding rate 4/5
#define LORA_SYNC_WORD      0x12    // private network
#ifndef LORA_TX_POWER_DBM
#define LORA_TX_POWER_DBM   22      // check your local 433 MHz limits (often 10 dBm)
#endif
#define LORA_PREAMBLE       8

// Crystal load trimming used by the vendor firmware for this module.
#define LORA_XTA_TRIM       0x04
#define LORA_XTB_TRIM       0x2F

// Packets with a different ID are ignored, so each sensor/receiver pair needs its own ID.
// Pair 1 uses this default; other pairs set it from platformio.ini (e.g. env:sensor_pair2).
#ifndef NETWORK_ID
#define NETWORK_ID          0xA001
#endif

// ---------------------------------------------------------------------------
// Timing
// ---------------------------------------------------------------------------
// Modes selected with KEY; every power-up starts in slow (MODE_AT_BOOT, not saved).
// Sensor heartbeat; actual spacing = period + ~1.0 s airtime at SF12.
#define TX_PERIOD_FAST_MS   5000UL
#define TX_PERIOD_MS        20000UL  // normal
#define TX_PERIOD_SLOW_MS   120000UL // slow (at power-up)
// Receiver: NO-LINK after this long without a valid packet. Set the receiver to the
// same mode as its sensor. Just over 3 packet spacings (~6 / ~21 / ~121 s at SF12), so up
// to 2 missed packets in a row are tolerated.
#define LINK_TIMEOUT_FAST_MS 20000UL
#define LINK_TIMEOUT_MS     65000UL  // normal
#define LINK_TIMEOUT_SLOW_MS 370000UL // slow (at power-up)
#define DEBOUNCE_MS         30UL
#define DOOR_STABLE_MS      10UL    // sensor: input must read the same this long to count
#define DOOR_STABLE_TIMEOUT_MS 200UL  // sensor: still changing after this = noise, ignored
#define DOOR_HOLDOFF_MS     500UL   // sensor: minimum gap between two door-change packets
#define DOOR_CHANGE_REPEATS 3       // sensor: each door change is sent this many times...
#define DOOR_REPEAT_GAP_MS  1000UL  // ...this far apart (stops early if the door changes again)
#define LED_FLASH_MS        50UL    // receiver: blink per valid packet
#define SENSOR_LED_ENABLED  1       // sensor: 0 = never light the LED (saves battery)
#define SENSOR_LED_FLASH_MS 20UL    // sensor: flash per transmission, independent of airtime
#define LSI_RECAL_PERIOD_MS 3600000UL   // sensor: re-measure the sleep clock hourly

#define LOG_BAUD            115200

// Sent over the USB serial port by tools/stm32_uart_flash.py to restart the
// board into the STM32 ROM bootloader for flashing (no BOOT0 button needed).
#define BOOTLOADER_COMMAND  "#DOOR-BOOTLOADER#"
#define SERIAL_LISTEN_MS    1500UL   // sensor: stay awake this long after serial activity
