// Restart into the STM32 ROM serial bootloader on a command from the USB
// serial port, so tools/stm32_uart_flash.py can flash the board without
// BOOT0 (the DX-PJ26 board has no automatic BOOT0/reset circuit).
//
// The request is stored in a backup register and the MCU is reset, so the
// bootloader starts from a clean state with the watchdog stopped.
#pragma once

#include <Arduino.h>

// Call first in setup(), before the watchdog or any peripheral is started.
// Jumps to the ROM bootloader if a request is pending; otherwise returns.
void bootloaderCheckOnBoot();

// Prints the reset flags and the request register as seen by bootloaderCheckOnBoot(),
// and the register's value now. Call before IWatchdog.isReset(true) clears the flags.
void bootloaderReportBoot(Print &log);

// Feeds received serial bytes; resets into the bootloader when
// BOOTLOADER_COMMAND has been received.
void bootloaderPoll(Stream &serial);
