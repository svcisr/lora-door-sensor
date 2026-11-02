#include "door_mode.h"

#include <EEPROM.h>

#include "config.h"

// Emulated EEPROM (last flash page): magic byte + mode
static constexpr int EE_MAGIC_ADDR = 0;
static constexpr int EE_MODE_ADDR = 1;
static constexpr uint8_t EE_MAGIC = 0xA8;

static constexpr uint32_t BLINK_ON_MS = 250;
static constexpr uint32_t BLINK_OFF_MS = 250;

DoorMode modeLoad() {
  uint8_t mode = EEPROM.read(EE_MODE_ADDR);
  if (EEPROM.read(EE_MAGIC_ADDR) != EE_MAGIC || mode >= MODE_COUNT) {
    return MODE_NORMAL;
  }
  return (DoorMode)mode;
}

void modeSave(DoorMode mode) {
  EEPROM.update(EE_MAGIC_ADDR, EE_MAGIC);
  EEPROM.update(EE_MODE_ADDR, mode);
}

DoorMode modeNext(DoorMode mode) {
  return (DoorMode)((mode + 1) % MODE_COUNT);
}

void modeBlink(DoorMode mode) {
  for (int i = 0; i <= mode; i++) {
    digitalWrite(PIN_LED, LED_ON);
    delay(BLINK_ON_MS);
    digitalWrite(PIN_LED, LED_OFF);
    delay(BLINK_OFF_MS);
  }
}

uint32_t modeTxPeriodMs(DoorMode mode) {
  static const uint32_t periods[MODE_COUNT] = {TX_PERIOD_FAST_MS, TX_PERIOD_MS, TX_PERIOD_SLOW_MS};
  return periods[mode];
}

uint32_t modeLinkTimeoutMs(DoorMode mode) {
  static const uint32_t timeouts[MODE_COUNT] = {LINK_TIMEOUT_FAST_MS, LINK_TIMEOUT_MS,
                                                LINK_TIMEOUT_SLOW_MS};
  return timeouts[mode];
}
