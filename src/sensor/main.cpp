// Door sensor: sends the reed switch state on every heartbeat and immediately
// on change, sleeping in STOP mode in between (battery operation).
//   PIN_DOOR_IN: contact closed (door closed) = 0, contact open = 1
//   PIN_KEY: each press steps the heartbeat 2 s -> 10 s -> 60 s (see door_mode.h)
#include <Arduino.h>
#include <IWatchdog.h>

#include "config.h"
#include "door_bootloader.h"
#include "door_mode.h"
#include "door_protocol.h"
#include "door_radio.h"
#include "sleep_timer.h"

// IWDG keeps running in STOP mode and cannot exceed ~26 s, so longer heartbeats
// sleep in chunks of SLEEP_CHUNK_MS with a watchdog reload in between.
static constexpr uint32_t WATCHDOG_US = 20000000UL;
static constexpr uint32_t SLEEP_CHUNK_MS = 15000UL;
static constexpr uint32_t KEY_RELEASE_TIMEOUT_MS = 5000UL;

// Header pins not used by this firmware: analog mode avoids leakage from
// floating inputs while sleeping.
static const uint32_t UNUSED_PINS[] = {
    PA8, PA11, PA12, PA15, PB0, PB1, PB3, PB4, PB5, PB6, PB7,
    PB8, PB9, PB10, PB14, PB15, PC13, PC14,
};

static auto &Log = Serial;   // USART1, see platformio.ini

static volatile bool doorEdge = false;
static volatile bool keyEdge = false;
static volatile bool serialWake = false;
static bool radioOk = false;
static DoorMode mode = MODE_NORMAL;
static int lastSentDoor = -1;
static uint16_t seq = 0;
static uint32_t msSinceCal = 0;
// Sleep left before the next heartbeat. Early wake-ups (noise, serial) only
// shorten the remaining time instead of restarting it.
static uint32_t untilHeartbeatMs = 0;
// Logged with each packet: early wake-ups and awake time since the previous one
// (millis() stops in STOP mode, so it only counts awake time).
static uint16_t earlyWakes = 0;
static uint32_t awakeSinceMs = 0;

static void onDoorEdge() {
  doorEdge = true;
}

static void onKeyPress() {
  keyEdge = true;
}

// Returns the door input once it has read the same for DOOR_STABLE_MS, or -1 if it is
// still changing after DOOR_STABLE_TIMEOUT_MS (e.g. noise picked up by the wire).
static int readDoorStable() {
  uint32_t start = millis();
  uint32_t stableSince = start;
  int last = digitalRead(PIN_DOOR_IN);
  while (millis() - start < DOOR_STABLE_TIMEOUT_MS) {
    int now = digitalRead(PIN_DOOR_IN);
    if (now != last) {
      last = now;
      stableSince = millis();
    } else if (millis() - stableSince >= DOOR_STABLE_MS) {
      return now ? 1 : 0;
    }
  }
  return -1;
}

static void logHeartbeat(const __FlashStringHelper *prefix) {
  Log.print(prefix);
  Log.print(modeTxPeriodMs(mode) / 1000);
  Log.println(F(" s"));
}

static void handleKey() {
  delay(DEBOUNCE_MS);
  bool pressed = digitalRead(PIN_KEY) == LOW;
  if (pressed) {
    mode = modeNext(mode);
    modeSave(mode);
    logHeartbeat(F("KEY: heartbeat "));
    modeBlink(mode);
    untilHeartbeatMs = modeTxPeriodMs(mode);
    // One toggle per press: wait for release, then let the contact settle
    uint32_t start = millis();
    while (digitalRead(PIN_KEY) == LOW && millis() - start < KEY_RELEASE_TIMEOUT_MS) {
    }
    delay(DEBOUNCE_MS);
  }
  keyEdge = false;
}

// The UART cannot receive in STOP mode: a falling edge on RX wakes the MCU,
// which then listens for SERIAL_LISTEN_MS (the waking byte itself is lost).
static void onSerialRx() {
  serialWake = true;
}

// With the CH340 removed (battery sensor) RX would float and keep waking the MCU
// through its EXTI line: input with pull-up (CNF = 10, ODR = 1). Call after attachInterrupt().
static void serialRxPullUp() {
  GPIOA->CRH = (GPIOA->CRH & ~(GPIO_CRH_MODE10 | GPIO_CRH_CNF10)) | GPIO_CRH_CNF10_1;
  GPIOA->BSRR = GPIO_BSRR_BS10;
}

static uint16_t readVddMv() {
  // VREFINT is 1.20 V (typ.) measured against VDD
  analogReadResolution(12);
  uint32_t raw = analogRead(AVREF);
  return raw ? (uint16_t)(1200UL * 4095UL / raw) : 0;
}

// Transmits while flashing the LED for SENSOR_LED_FLASH_MS. The flash overlaps the
// transmission, so it neither follows the airtime nor keeps the MCU awake longer.
static int16_t transmitWithFlash(const uint8_t *buf, size_t len) {
  int16_t state = radio.startTransmit(buf, len);
  if (state != RADIOLIB_ERR_NONE) {
    return state;
  }
  uint32_t start = millis();
  uint32_t timeoutMs = (uint32_t)(radio.getTimeOnAir(len) / 1000) * 2 + 100;
  bool ledOn = SENSOR_LED_ENABLED;
  if (ledOn) {
    digitalWrite(PIN_LED, LED_ON);
  }

  // DIO1 goes high on TX done
  while (!digitalRead(PIN_LORA_DIO1)) {
    uint32_t elapsed = millis() - start;
    if (ledOn && elapsed >= SENSOR_LED_FLASH_MS) {
      digitalWrite(PIN_LED, LED_OFF);
      ledOn = false;
    }
    if (elapsed > timeoutMs) {
      digitalWrite(PIN_LED, LED_OFF);
      radio.finishTransmit();
      return RADIOLIB_ERR_TX_TIMEOUT;
    }
  }
  // Airtime shorter than the flash (low SF): finish the flash
  while (ledOn && millis() - start < SENSOR_LED_FLASH_MS) {
  }
  digitalWrite(PIN_LED, LED_OFF);
  return radio.finishTransmit();
}

static void sendStatus(const __FlashStringHelper *reason, int door) {
  if (door < 0) {
    // Input too noisy to read: repeat the last known state
    door = lastSentDoor >= 0 ? lastSentDoor : (digitalRead(PIN_DOOR_IN) ? 1 : 0);
  }
  lastSentDoor = door;

  DoorStatus status;
  status.networkId = NETWORK_ID;
  status.door = (uint8_t)door;
  status.seq = seq;
  status.vddMv = readVddMv();
  uint8_t buf[DOOR_PACKET_LEN];
  doorEncode(status, buf);

  if (!radioOk) {
    radioOk = doorRadioBegin() == RADIOLIB_ERR_NONE;
  }
  // Wakes the radio from sleep and restores the crystal trim
  int16_t state = radioOk ? doorRadioApplyTrim() : RADIOLIB_ERR_CHIP_NOT_FOUND;
  if (state == RADIOLIB_ERR_NONE) {
    state = transmitWithFlash(buf, sizeof(buf));
  }
  if (state == RADIOLIB_ERR_NONE) {
    radio.sleep(true);
  } else {
    radioOk = false;   // re-initialise before the next attempt
  }

  Log.print(F("TX seq="));
  Log.print(seq);
  Log.print(F(" door="));
  Log.print(status.door ? F("OPEN") : F("CLOSED"));
  Log.print(F(" vdd="));
  Log.print(status.vddMv / 1000.0f, 2);
  Log.print(F(" ("));
  Log.print(reason);
  Log.print(F(") wakes="));
  Log.print(earlyWakes);
  Log.print(F(" awake="));
  Log.print(millis() - awakeSinceMs);
  Log.print(F("ms"));
  if (state != RADIOLIB_ERR_NONE) {
    Log.print(F(" FAILED "));
    Log.print(state);
  }
  Log.println();
  seq++;
  earlyWakes = 0;
  awakeSinceMs = millis();
}

// Waits ms (awake) while watching the door. Returns false as soon as the door has
// settled in a state other than `door`; edges are only checked after DOOR_HOLDOFF_MS
// so noise cannot make change packets follow each other closely.
static bool waitDoorUnchanged(int door, uint32_t ms) {
  uint32_t start = millis();
  while (millis() - start < ms) {
    IWatchdog.reload();
    if (doorEdge && millis() - start >= DOOR_HOLDOFF_MS) {
      doorEdge = false;
      delay(DEBOUNCE_MS);
      int now = readDoorStable();
      if (now >= 0 && now != door) {
        doorEdge = true;   // let loop() send the new state
        return false;
      }
    }
  }
  return true;
}

// Sends a door change DOOR_CHANGE_REPEATS times, DOOR_REPEAT_GAP_MS apart, so a single
// lost packet does not leave the receiver showing the old state until the next heartbeat.
static void sendDoorChange(int door) {
  for (int i = 0; i < DOOR_CHANGE_REPEATS; i++) {
    if (i > 0 && !waitDoorUnchanged(door, DOOR_REPEAT_GAP_MS)) {
      return;
    }
    sendStatus(i == 0 ? F("change") : F("repeat"), door);
  }
  waitDoorUnchanged(door, DOOR_HOLDOFF_MS);
}

void setup() {
  bootloaderCheckOnBoot();

  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_LED, LED_OFF);
  pinMode(PIN_DOOR_IN, INPUT_PULLUP);
  pinMode(PIN_KEY, INPUT_PULLUP);
  for (uint32_t pin : UNUSED_PINS) {
    pinMode(pin, INPUT_ANALOG);
  }

  Log.begin(LOG_BAUD);
  Log.println();
  Log.println(F("Door sensor"));
  bootloaderReportBoot(Log);
  if (IWatchdog.isReset(true)) {
    Log.println(F("(restarted by watchdog)"));
  }
  IWatchdog.begin(WATCHDOG_US);

  uint32_t lsiHz = sleepTimerBegin();
  Log.print(F("LSI "));
  Log.print(lsiHz);
  Log.println(F(" Hz"));

  int16_t state = doorRadioBegin();
  doorRadioReport(Log, state);
  radioOk = state == RADIOLIB_ERR_NONE;

  mode = modeLoad();
  logHeartbeat(F("Heartbeat "));
  modeBlink(mode);

  attachInterrupt(digitalPinToInterrupt(PIN_DOOR_IN), onDoorEdge, CHANGE);
  attachInterrupt(digitalPinToInterrupt(PIN_KEY), onKeyPress, FALLING);
  attachInterrupt(digitalPinToInterrupt(PIN_SERIAL_RX), onSerialRx, FALLING);
  serialRxPullUp();
  sendStatus(F("boot"), readDoorStable());
  untilHeartbeatMs = modeTxPeriodMs(mode);
}

void loop() {
  Log.flush();
  // A door or KEY edge that arrived while awake (e.g. during a transmission) is
  // handled now instead of after the next heartbeat.
  bool timerExpired = false;
  if (!doorEdge && !keyEdge) {
    uint32_t chunk = untilHeartbeatMs < SLEEP_CHUNK_MS ? untilHeartbeatMs : SLEEP_CHUNK_MS;
    uint32_t slept = 0;
    if (!sleepTimerSleep(chunk, &slept)) {
      earlyWakes++;
    }
    untilHeartbeatMs -= slept < untilHeartbeatMs ? slept : untilHeartbeatMs;
    msSinceCal += slept;
    timerExpired = untilHeartbeatMs == 0;
  }
  IWatchdog.reload();

  if (keyEdge) {
    handleKey();
  }

  bool sent = false;
  if (doorEdge) {
    delay(DEBOUNCE_MS);
    // Edges up to here are covered by the stable read below
    doorEdge = false;
    int door = readDoorStable();
    // Edges alone are not changes: noise on the wire produces many of them
    if (door >= 0 && door != lastSentDoor) {
      // A further change during the repeats leaves doorEdge set for the next pass
      sendDoorChange(door);
      sent = true;
    }
  }
  if (timerExpired && !sent) {
    sendStatus(F("periodic"), readDoorStable());
  }
  // Any packet (change or periodic) starts the next heartbeat period
  if (sent || timerExpired) {
    untilHeartbeatMs = modeTxPeriodMs(mode);
  }

  if (serialWake) {
    uint32_t start = millis();
    while (millis() - start < SERIAL_LISTEN_MS) {
      bootloaderPoll(Log);
    }
    serialWake = false;
  }

  if (msSinceCal >= LSI_RECAL_PERIOD_MS) {
    msSinceCal = 0;
    sleepTimerCalibrate();
  }
}
