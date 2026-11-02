// Sleep test: finds what still draws current while the sensor sleeps. Sets up the radio
// exactly like the sensor (door_radio), transmits once, puts it to sleep, and recreates
// the sensor's sleep pin state. Then it releases one pin per step to analog, cumulatively,
// sleeping STEP_SLEEP_MS in STOP after each. At the start of step N the LED blinks N times:
//    1 = sensor sleep state      2 = MISO analog      3 = MOSI analog     4 = SCK analog
//    5 = RXEN analog             6 = TXEN analog      7 = DIO1 analog     8 = BUSY analog
//    9 = NRESET analog          10 = NSS analog      11 = UART pins analog
//   12 = KEY and PB13 analog
// Then the radio is set up again and the cycle repeats.
#include <Arduino.h>

#include "config.h"
#include "door_protocol.h"
#include "door_radio.h"
#include "sleep_timer.h"

static constexpr uint32_t STEP_SLEEP_MS = 10000UL;
static constexpr uint32_t BLINK_MS = 150UL;

// Released in this order (steps 2..10)
static const uint32_t RADIO_PINS[] = {
    PIN_LORA_MISO, PIN_LORA_MOSI, PIN_LORA_SCK, PIN_LORA_RXEN, PIN_LORA_TXEN,
    PIN_LORA_DIO1, PIN_LORA_BUSY, PIN_LORA_RESET, PIN_LORA_NSS,
};

// Same list as the sensor firmware
static const uint32_t UNUSED_PINS[] = {
    PA8, PA11, PA12, PA15, PB0, PB1, PB3, PB4, PB5, PB6, PB7,
    PB8, PB9, PB10, PB14, PB15, PC13, PC14,
};

static void blink(int count) {
  for (int i = 0; i < count; i++) {
    digitalWrite(PIN_LED, LED_ON);
    delay(BLINK_MS);
    digitalWrite(PIN_LED, LED_OFF);
    delay(BLINK_MS);
  }
}

static void step(int number) {
  blink(number);
  Serial.flush();
  sleepTimerSleep(STEP_SLEEP_MS);
}

// Sensor sleep state: radio set up, one packet sent, radio asleep (as in sendStatus)
static void sensorState() {
  Serial.begin(LOG_BAUD);
  pinMode(PIN_DOOR_IN, INPUT_PULLUP);
  pinMode(PIN_KEY, INPUT_PULLUP);
  // PA10 with pull-up, as serialRxPullUp() in the sensor
  GPIOA->CRH = (GPIOA->CRH & ~(GPIO_CRH_MODE10 | GPIO_CRH_CNF10)) | GPIO_CRH_CNF10_1;
  GPIOA->BSRR = GPIO_BSRR_BS10;

  if (doorRadioBegin() == RADIOLIB_ERR_NONE) {
    DoorStatus status = {NETWORK_ID, 0, 0, 3300};
    uint8_t buf[DOOR_PACKET_LEN];
    doorEncode(status, buf);
    radio.transmit(buf, sizeof(buf));
    radio.sleep(true);
  } else {
    blink(20);   // radio failed: long blink burst
  }
}

void setup() {
  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_LED, LED_OFF);
  for (uint32_t pin : UNUSED_PINS) {
    pinMode(pin, INPUT_ANALOG);
  }
  sleepTimerBegin();
}

void loop() {
  sensorState();
  step(1);
  int number = 2;
  for (uint32_t pin : RADIO_PINS) {
    pinMode(pin, INPUT_ANALOG);
    step(number++);
  }
  Serial.end();
  pinMode(PA9, INPUT_ANALOG);
  pinMode(PA10, INPUT_ANALOG);
  step(number++);
  pinMode(PIN_KEY, INPUT_ANALOG);
  pinMode(PIN_DOOR_IN, INPUT_ANALOG);
  step(number++);
}
