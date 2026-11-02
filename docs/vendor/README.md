# Vendor documents (not included)

These are other companies' documents, so they are linked rather than copied here.

| Document | Where |
|---|---|
| DX-LR30 development package (board manual, LR30-SP schematic, module manual, Keil/HAL reference code, mcuisp flashing tool, DFU notes) | DX-SMART: https://github.com/DX-SMART/LoRaModule |
| SX1261/SX1262 datasheet | Semtech: https://www.semtech.com/products/wireless-rf/lora-connect/sx1262 |
| STM32F103C8 datasheet | ST: https://www.st.com/en/microcontrollers-microprocessors/stm32f103c8.html |

Notes from using them:

- The board manual shows a different board revision than ours (DX-PJ26-V1.1).
- The "LR30-SP" schematic **does not match DX-PJ26**: it shows a CH340C with DTR/RTS auto-boot
  transistors and the LED on PC13. Our board has a 10-pin CH340, no auto-boot circuit, LED on PB11
  (active high). Radio wiring (PA0-PA7, PC15) does match.
- The reference code (`LR_driver/UserConfig.c`) is the source of the radio pin map, DC-DC mode
  and XTA/XTB trim 0x04/0x2F.
- TX currents used in `docs/lora-options.html` come from the SX1262 datasheet's optimal PA
  settings table.
