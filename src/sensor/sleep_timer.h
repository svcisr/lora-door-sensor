// STOP-mode sleep with RTC alarm wake-up for the STM32F103.
//
// The board's 32.768 kHz crystal shares PC15 with the radio's DIO1, so the RTC
// runs from the internal LSI oscillator (30..60 kHz, nominal 40 kHz). Its real
// frequency is measured against the CPU clock so sleep durations stay accurate.
#pragma once

#include <stdint.h>

// Starts the RTC from LSI and calibrates it. Call once from setup().
// Returns the measured LSI frequency in Hz.
uint32_t sleepTimerBegin();

// Re-measures the LSI frequency (~0.5 s busy wait). Returns it in Hz.
uint32_t sleepTimerCalibrate();

// Enters STOP mode for ms milliseconds or until any EXTI interrupt (e.g. a
// pin change). Restores the system clock on wake-up.
// Returns true if the timer expired, false if woken early by another source.
// If sleptMs is given, it receives the time actually spent asleep.
bool sleepTimerSleep(uint32_t ms, uint32_t *sleptMs = nullptr);
