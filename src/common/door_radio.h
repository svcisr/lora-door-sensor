// SX1262 setup for the DX-LR30 module on the DX-SMART development board.
#pragma once

#include <RadioLib.h>

extern SX1262 radio;

// Resets and configures the radio (frequency, modulation, power, RF switch,
// DC-DC regulator, crystal trim). Returns a RadioLib status code.
int16_t doorRadioBegin();

// Re-applies the crystal trim. The sensor calls this after every wake-up from
// radio sleep, before transmitting, in case the trim was not retained.
int16_t doorRadioApplyTrim();

// Prints "RADIO OK" or "RADIO FAIL (code)".
void doorRadioReport(Print &log, int16_t state);
