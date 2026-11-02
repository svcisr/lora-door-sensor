#include "sleep_timer.h"

#include <Arduino.h>

extern "C" void SystemClock_Config(void);

// RTC counter tick = LSI / 32, about 0.8 ms at the nominal 40 kHz
static constexpr uint32_t RTC_PRESCALER = 32;
static constexpr uint32_t CALIBRATION_US = 500000;

static float tickHz = 40000.0f / RTC_PRESCALER;

extern "C" void RTC_Alarm_IRQHandler(void) {
  RTC->CRL &= ~RTC_CRL_ALRF;
  EXTI->PR = EXTI_PR_PR17;
}

static void rtcWaitWriteDone() {
  while (!(RTC->CRL & RTC_CRL_RTOFF)) {
  }
}

static void rtcEnterConfig() {
  rtcWaitWriteDone();
  RTC->CRL |= RTC_CRL_CNF;
}

static void rtcExitConfig() {
  RTC->CRL &= ~RTC_CRL_CNF;
  rtcWaitWriteDone();
}

// RTC registers must be resynchronised after reset or STOP before reading
static void rtcSync() {
  RTC->CRL &= ~RTC_CRL_RSF;
  while (!(RTC->CRL & RTC_CRL_RSF)) {
  }
}

static uint32_t rtcCounter() {
  uint32_t high, low;
  do {
    high = RTC->CNTH;
    low = RTC->CNTL;
  } while (high != RTC->CNTH);
  return (high << 16) | low;
}

uint32_t sleepTimerBegin() {
  __HAL_RCC_PWR_CLK_ENABLE();
  __HAL_RCC_BKP_CLK_ENABLE();
  HAL_PWR_EnableBkUpAccess();

  RCC->CSR |= RCC_CSR_LSION;
  while (!(RCC->CSR & RCC_CSR_LSIRDY)) {
  }
  if ((RCC->BDCR & RCC_BDCR_RTCSEL) != RCC_BDCR_RTCSEL_LSI) {
    // The RTC clock source can only be changed after a backup domain reset
    RCC->BDCR |= RCC_BDCR_BDRST;
    RCC->BDCR &= ~RCC_BDCR_BDRST;
    RCC->BDCR |= RCC_BDCR_RTCSEL_LSI;
  }
  RCC->BDCR |= RCC_BDCR_RTCEN;

  rtcSync();
  rtcEnterConfig();
  RTC->PRLH = 0;
  RTC->PRLL = RTC_PRESCALER - 1;
  RTC->CNTH = 0;
  RTC->CNTL = 0;
  RTC->ALRH = 0xFFFF;
  RTC->ALRL = 0xFFFF;
  rtcExitConfig();
  RTC->CRH = RTC_CRH_ALRIE;

  // RTC alarm reaches the CPU through EXTI line 17, which also wakes it from STOP
  EXTI->IMR |= EXTI_IMR_MR17;
  EXTI->RTSR |= EXTI_RTSR_TR17;
  NVIC_SetPriority(RTC_Alarm_IRQn, 2);
  NVIC_EnableIRQ(RTC_Alarm_IRQn);

  return sleepTimerCalibrate();
}

uint32_t sleepTimerCalibrate() {
  rtcSync();
  // Measure between two counter edges to avoid a partial-tick error
  uint32_t start = rtcCounter();
  while (rtcCounter() == start) {
  }
  start = rtcCounter();
  uint32_t t0 = micros();
  while (micros() - t0 < CALIBRATION_US) {
  }
  uint32_t end = rtcCounter();
  while (rtcCounter() == end) {
  }
  uint32_t t1 = micros();
  end = rtcCounter();

  tickHz = (float)(end - start) * 1e6f / (float)(t1 - t0);
  return (uint32_t)(tickHz * RTC_PRESCALER + 0.5f);
}

bool sleepTimerSleep(uint32_t ms, uint32_t *sleptMs) {
  uint32_t ticks = (uint32_t)((float)ms * tickHz / 1000.0f + 0.5f);
  if (ticks < 2) {
    ticks = 2;
  }

  rtcSync();
  uint32_t start = rtcCounter();
  uint32_t alarm = start + ticks;
  rtcEnterConfig();
  RTC->ALRH = alarm >> 16;
  RTC->ALRL = alarm & 0xFFFF;
  rtcExitConfig();
  RTC->CRL &= ~RTC_CRL_ALRF;
  EXTI->PR = EXTI_PR_PR17;

  // SysTick would wake the core immediately; STOP halts all high-speed clocks
  HAL_SuspendTick();
  HAL_PWR_EnterSTOPMode(PWR_LOWPOWERREGULATOR_ON, PWR_STOPENTRY_WFI);
  SystemClock_Config();
  HAL_ResumeTick();

  rtcSync();
  uint32_t now = rtcCounter();
  bool expired = (int32_t)(now - alarm) >= 0;
  if (sleptMs != nullptr) {
    *sleptMs = expired ? ms : (uint32_t)((float)(now - start) * 1000.0f / tickHz);
  }
  return expired;
}
