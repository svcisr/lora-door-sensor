// Receiver: listens for door status packets and drives two outputs.
//   PIN_DOOR_OUT   = last received door state (1 = open), held while the link is down
//   PIN_NOLINK_OUT = 1 when no valid packet arrived for the link timeout
//   PIN_KEY: each press steps the link timeout 20 s -> 65 s -> 370 s (see door_mode.h);
//            set it to match the sensor's heartbeat (5 s / 20 s / 2 min)
#include <Arduino.h>
#include <IWatchdog.h>

#include "config.h"
#include "door_bootloader.h"
#include "door_mode.h"
#include "door_protocol.h"
#include "door_radio.h"

static constexpr uint32_t WATCHDOG_US = 4000000UL;
static constexpr uint32_t RADIO_REINIT_MS = 60000UL;   // while the link is down

static auto &Log = Serial;   // USART1, see platformio.ini

static volatile bool packetFlag = false;
static DoorMode mode = MODE_AT_BOOT;
static bool keyWasDown = false;
static bool linkUp = false;
static bool haveSeq = false;
static uint16_t lastSeq = 0;
static uint32_t lastValidMs = 0;
static uint32_t lastRadioInitMs = 0;
static uint32_t ledOffMs = 0;

static void onDio1() {
  packetFlag = true;
}

static bool startRadio() {
  int16_t state = doorRadioBegin();
  if (state == RADIOLIB_ERR_NONE) {
    radio.setRxBoostedGainMode(true);
    radio.setPacketReceivedAction(onDio1);
    state = radio.startReceive();
  }
  doorRadioReport(Log, state);
  lastRadioInitMs = millis();
  return state == RADIOLIB_ERR_NONE;
}

static void setLink(bool up) {
  if (up == linkUp) {
    return;
  }
  linkUp = up;
  digitalWrite(PIN_NOLINK_OUT, up ? LOW : HIGH);
  Log.println(up ? F("LINK UP") : F("LINK LOST"));
}

static void logLinkTimeout(const __FlashStringHelper *prefix) {
  Log.print(prefix);
  Log.print(modeLinkTimeoutMs(mode) / 1000);
  Log.println(F(" s"));
}

// Polled KEY: one mode step per press (falling edge, debounced)
static void pollKey() {
  bool down = digitalRead(PIN_KEY) == LOW;
  if (down && !keyWasDown) {
    delay(DEBOUNCE_MS);
    if (digitalRead(PIN_KEY) == LOW) {
      mode = modeNext(mode);
      logLinkTimeout(F("KEY: link timeout "));
      IWatchdog.reload();
      modeBlink(mode);
    } else {
      down = false;   // bounce
    }
  }
  keyWasDown = down;
}

static void handlePacket() {
  uint8_t buf[DOOR_PACKET_LEN + 1];
  size_t len = radio.getPacketLength();
  int16_t state = RADIOLIB_ERR_PACKET_TOO_LONG;
  if (len <= sizeof(buf)) {
    state = radio.readData(buf, len);
  }
  float rssi = radio.getRSSI();
  float snr = radio.getSNR();
  // Sensor carrier minus ours: both boards use plain crystals (no TCXO)
  float freqErrorHz = radio.getFrequencyError();
  radio.startReceive();

  DoorStatus status;
  if (state != RADIOLIB_ERR_NONE || !doorDecode(buf, len, NETWORK_ID, status)) {
    Log.print(F("RX ignored (state "));
    Log.print(state);
    Log.print(F(", len "));
    Log.print(len);
    Log.println(F(")"));
    return;
  }

  digitalWrite(PIN_DOOR_OUT, status.door ? HIGH : LOW);
  lastValidMs = millis();
  setLink(true);
  digitalWrite(PIN_LED, LED_ON);
  ledOffMs = lastValidMs + LED_FLASH_MS;

  Log.print(F("RX seq="));
  Log.print(status.seq);
  Log.print(F(" door="));
  Log.print(status.door ? F("OPEN") : F("CLOSED"));
  Log.print(F(" rssi="));
  Log.print(rssi, 1);
  Log.print(F(" snr="));
  Log.print(snr, 1);
  Log.print(F(" ferr="));
  Log.print(freqErrorHz, 0);
  Log.print(F(" vdd="));
  Log.print(status.vddMv / 1000.0f, 2);
  if (haveSeq) {
    uint16_t missed = (uint16_t)(status.seq - lastSeq - 1);
    if (missed != 0 && missed < 1000) {
      Log.print(F(" missed="));
      Log.print(missed);
    }
  }
  Log.println();
  lastSeq = status.seq;
  haveSeq = true;
}

void setup() {
  bootloaderCheckOnBoot();

  // Outputs first: no known door state yet, link down
  pinMode(PIN_DOOR_OUT, OUTPUT);
  digitalWrite(PIN_DOOR_OUT, LOW);
  pinMode(PIN_NOLINK_OUT, OUTPUT);
  digitalWrite(PIN_NOLINK_OUT, HIGH);
  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_LED, LED_OFF);
  pinMode(PIN_KEY, INPUT_PULLUP);

  Log.begin(LOG_BAUD);
  Log.println();
  Log.println(F("Door receiver"));
  bootloaderReportBoot(Log);
  if (IWatchdog.isReset(true)) {
    Log.println(F("(restarted by watchdog)"));
  }
  IWatchdog.begin(WATCHDOG_US);

  logLinkTimeout(F("Link timeout "));
  modeBlink(mode);
  keyWasDown = digitalRead(PIN_KEY) == LOW;

  startRadio();
}

void loop() {
  IWatchdog.reload();
  bootloaderPoll(Log);
  pollKey();

  if (packetFlag) {
    packetFlag = false;
    handlePacket();
  }

  // Read after handlePacket(): lastValidMs must never be later than now
  uint32_t now = millis();
  if (linkUp && now - lastValidMs > modeLinkTimeoutMs(mode)) {
    setLink(false);
  }

  // A wedged radio would look like a lost link: re-initialise it periodically
  if (!linkUp && now - lastRadioInitMs > RADIO_REINIT_MS) {
    Log.println(F("No link, re-initialising radio"));
    startRadio();
  }

  if (ledOffMs != 0 && (int32_t)(now - ledOffMs) >= 0) {
    digitalWrite(PIN_LED, LED_OFF);
    ledOffMs = 0;
  }
}
