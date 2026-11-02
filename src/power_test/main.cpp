// Power test: isolates the board's own current. No UART, no radio (unplug the LR30-A
// carrier first), no watchdog: blink the LED, then STOP-mode sleep with a short LED
// flash every POWER_TEST_PERIOD_MS as a marker on the current trace. Every pin except
// the LED and SWD is analog, so whatever remains between flashes is board hardware
// (CH340, POW LED, regulator leakage) plus the MCU's STOP current.
//   pio run -e power_test -t upload --upload-port COMx
// The firmware has no bootloader command: when the flasher asks, press RST
// (BOOT0 follows DTR, which the flasher holds deasserted, so RST starts the bootloader).
#include <Arduino.h>

#include "config.h"
#include "sleep_timer.h"

static constexpr uint32_t POWER_TEST_PERIOD_MS = 10000UL;
static constexpr uint32_t MARKER_FLASH_MS = 20UL;
// Awake this long after reset, blinking: time to attach an ST-LINK if needed
static constexpr int BOOT_BLINKS = 5;
static constexpr uint32_t BOOT_BLINK_MS = 200UL;

static const uint32_t ANALOG_PINS[] = {
    PA0, PA1, PA2, PA3, PA4, PA5, PA6, PA7, PA8, PA9, PA10, PA11, PA12, PA15,
    PB0, PB1, PB2, PB3, PB4, PB5, PB6, PB7, PB8, PB9, PB10, PB12, PB13, PB14, PB15,
    PC13, PC14, PC15,
};

static void flashLed(uint32_t ms) {
  digitalWrite(PIN_LED, LED_ON);
  delay(ms);
  digitalWrite(PIN_LED, LED_OFF);
}

void setup() {
  // Free PA15/PB3/PB4 from JTAG, keep SWD (PA13/PA14) for the ST-LINK
  __HAL_RCC_AFIO_CLK_ENABLE();
  __HAL_AFIO_REMAP_SWJ_NOJTAG();
  for (uint32_t pin : ANALOG_PINS) {
    pinMode(pin, INPUT_ANALOG);
  }
  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_LED, LED_OFF);

  for (int i = 0; i < BOOT_BLINKS; i++) {
    flashLed(BOOT_BLINK_MS);
    delay(BOOT_BLINK_MS);
  }
  sleepTimerBegin();
}

void loop() {
  sleepTimerSleep(POWER_TEST_PERIOD_MS);
  flashLed(MARKER_FLASH_MS);
}
