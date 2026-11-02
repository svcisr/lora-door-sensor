#include "door_bootloader.h"

#include "config.h"

static constexpr uint32_t SYSTEM_MEMORY = 0x1FFFF000;   // F1 ROM bootloader
static constexpr uint16_t REQUEST_MAGIC = 0xB007;

static void backupDomainAccess() {
  __HAL_RCC_PWR_CLK_ENABLE();
  __HAL_RCC_BKP_CLK_ENABLE();
  HAL_PWR_EnableBkUpAccess();
}

static void jumpToSystemMemory() {
  HAL_RCC_DeInit();
  SysTick->CTRL = 0;
  SysTick->LOAD = 0;
  SysTick->VAL = 0;

  __disable_irq();
  for (unsigned i = 0; i < sizeof(NVIC->ICER) / sizeof(NVIC->ICER[0]); i++) {
    NVIC->ICER[i] = 0xFFFFFFFF;
    NVIC->ICPR[i] = 0xFFFFFFFF;
  }
  __enable_irq();

  uint32_t stack = *(volatile uint32_t *)SYSTEM_MEMORY;
  void (*entry)(void) = (void (*)(void))(*(volatile uint32_t *)(SYSTEM_MEMORY + 4));
  __set_MSP(stack);
  entry();
  while (true) {
  }
}

static uint32_t bootCsr = 0;
static uint16_t bootRequest = 0;

void bootloaderCheckOnBoot() {
  backupDomainAccess();
  bootCsr = RCC->CSR;
  bootRequest = (uint16_t)BKP->DR1;
  // Only the software reset from bootloaderPoll() counts. The flag survives other resets,
  // so a leftover one would otherwise send every RST press and every start by the ROM
  // bootloader's Go command (no reset, flags unchanged) back into the bootloader.
  bool requested = bootRequest == REQUEST_MAGIC && (bootCsr & RCC_CSR_SFTRSTF);
  BKP->DR1 = 0;
  if (!requested) {
    return;
  }
  __HAL_RCC_CLEAR_RESET_FLAGS();
  jumpToSystemMemory();
}

void bootloaderReportBoot(Print &log) {
  log.print(F("Boot RCC_CSR=0x"));
  log.print(bootCsr, HEX);
  log.print(F(" BKP_DR1=0x"));
  log.print(bootRequest, HEX);
  log.print(F(" now 0x"));
  log.println((uint16_t)BKP->DR1, HEX);
}

void bootloaderPoll(Stream &serial) {
  static const char command[] = BOOTLOADER_COMMAND;
  static size_t matched = 0;

  while (serial.available()) {
    char c = (char)serial.read();
    if (c == command[matched]) {
      matched++;
    } else {
      matched = (c == command[0]) ? 1 : 0;
    }
    if (matched == sizeof(command) - 1) {
      serial.println(F("Restarting into bootloader"));
      serial.flush();
      backupDomainAccess();
      BKP->DR1 = REQUEST_MAGIC;
      NVIC_SystemReset();
    }
  }
}
