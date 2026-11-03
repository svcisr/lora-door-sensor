#include "door_mode.h"

#include "config.h"

static constexpr uint32_t BLINK_ON_MS = 250;
static constexpr uint32_t BLINK_OFF_MS = 250;

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
