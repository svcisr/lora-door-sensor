// Timing mode selected with the KEY button, shared by sensor and receiver:
//   fast   = sensor heartbeat TX_PERIOD_FAST_MS, receiver timeout LINK_TIMEOUT_FAST_MS
//   normal = TX_PERIOD_MS / LINK_TIMEOUT_MS
//   slow   = TX_PERIOD_SLOW_MS / LINK_TIMEOUT_SLOW_MS (every power-up starts here)
// The LED shows the mode as 1 / 2 / 3 blinks. KEY changes it until the next power-up;
// it is not saved.
#pragma once

#include <Arduino.h>

enum DoorMode : uint8_t { MODE_FAST = 0, MODE_NORMAL = 1, MODE_SLOW = 2, MODE_COUNT = 3 };

constexpr DoorMode MODE_AT_BOOT = MODE_SLOW;

// fast -> normal -> slow -> fast
DoorMode modeNext(DoorMode mode);
// Blinks the LED 1/2/3 times (blocking, ~1.5 s at most).
void modeBlink(DoorMode mode);
uint32_t modeTxPeriodMs(DoorMode mode);
uint32_t modeLinkTimeoutMs(DoorMode mode);
