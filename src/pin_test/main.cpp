// Pin test: finds which radio pin state draws current while asleep. Starts like the
// power test (every pin analog), then adds the sensor firmware's sleep state of one
// radio pin per step, cumulatively, sleeping STEP_SLEEP_MS in STOP after each step.
// At the start of step N the LED blinks N times; read the floor after each group of
// blinks on the current trace:
//   1 = all analog (baseline)   2 = + TXEN low    3 = + RXEN low    4 = + NRESET high
//   5 = + NSS high              6 = + SCK low     7 = + MOSI high   8 = + MISO pull-up
// Then everything goes back to analog and the cycle repeats.
#include <Arduino.h>

#include "config.h"
#include "sleep_timer.h"

static constexpr uint32_t STEP_SLEEP_MS = 10000UL;
static constexpr uint32_t BLINK_MS = 150UL;

struct PinStep {
  uint32_t pin;
  uint32_t mode;
  uint32_t level;
};

// Sleep state of the radio pins in the sensor firmware (read over SWD at STOP entry)
static const PinStep STEPS[] = {
    {PIN_LORA_TXEN, OUTPUT, LOW},
    {PIN_LORA_RXEN, OUTPUT, LOW},
    {PIN_LORA_RESET, OUTPUT, HIGH},
    {PIN_LORA_NSS, OUTPUT, HIGH},
    {PIN_LORA_SCK, OUTPUT, LOW},
    {PIN_LORA_MOSI, OUTPUT, HIGH},
    {PIN_LORA_MISO, INPUT_PULLUP, 0},
};
static constexpr int STEP_COUNT = sizeof(STEPS) / sizeof(STEPS[0]);

static const uint32_t ANALOG_PINS[] = {
    PA0, PA1, PA2, PA3, PA4, PA5, PA6, PA7, PA8, PA9, PA10, PA11, PA12, PA15,
    PB0, PB1, PB2, PB3, PB4, PB5, PB6, PB7, PB8, PB9, PB10, PB12, PB13, PB14, PB15,
    PC13, PC14, PC15,
};

static void allAnalog() {
  for (uint32_t pin : ANALOG_PINS) {
    pinMode(pin, INPUT_ANALOG);
  }
}

static void blink(int count) {
  for (int i = 0; i < count; i++) {
    digitalWrite(PIN_LED, LED_ON);
    delay(BLINK_MS);
    digitalWrite(PIN_LED, LED_OFF);
    delay(BLINK_MS);
  }
}

void setup() {
  // Free PA15/PB3/PB4 from JTAG, keep SWD (PA13/PA14) for the ST-LINK
  __HAL_RCC_AFIO_CLK_ENABLE();
  __HAL_AFIO_REMAP_SWJ_NOJTAG();
  allAnalog();
  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_LED, LED_OFF);
  sleepTimerBegin();
}

void loop() {
  allAnalog();
  blink(1);
  sleepTimerSleep(STEP_SLEEP_MS);
  for (int step = 0; step < STEP_COUNT; step++) {
    const PinStep &s = STEPS[step];
    if (s.mode == OUTPUT) {
      digitalWrite(s.pin, s.level);   // level first, so the pin never glitches
    }
    pinMode(s.pin, s.mode);
    if (s.mode == OUTPUT) {
      digitalWrite(s.pin, s.level);
    }
    blink(step + 2);
    sleepTimerSleep(STEP_SLEEP_MS);
  }
}
