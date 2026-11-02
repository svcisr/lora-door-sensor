#include "door_radio.h"

#include "config.h"

// Kept separately so the trim registers can be written directly (SX126x keeps
// its register access protected).
static Module loraModule(PIN_LORA_NSS, PIN_LORA_DIO1, PIN_LORA_RESET, PIN_LORA_BUSY);
SX1262 radio(&loraModule);

// RF switch: something on the LR30-A drives the RXEN line high, so driving PA1 low
// sinks ~26 mA (measured: 26.8 mA sleep floor with RadioLib's default table, which sets
// both pins low in idle/sleep). RXEN stays high except while transmitting, as in the
// vendor code (RxEn/TxEn in LR_driver/UserConfig.c).
static const uint32_t rfSwitchPins[Module::RFSWITCH_MAX_PINS] = {
    PIN_LORA_RXEN, PIN_LORA_TXEN, RADIOLIB_NC, RADIOLIB_NC, RADIOLIB_NC};
static const Module::RfSwitchMode_t rfSwitchTable[] = {
    {Module::MODE_IDLE, {HIGH, LOW}},
    {Module::MODE_RX, {HIGH, LOW}},
    {Module::MODE_TX, {LOW, HIGH}},
    END_OF_MODE_TABLE,
};

// SX126x crystal trim registers (datasheet table 13-1)
static constexpr uint16_t REG_XTA_TRIM = 0x0911;
static constexpr uint16_t REG_XTB_TRIM = 0x0912;

int16_t doorRadioApplyTrim() {
  // Trim values can only be changed in STDBY_XOSC
  int16_t state = radio.standby(RADIOLIB_SX126X_STANDBY_XOSC);
  if (state != RADIOLIB_ERR_NONE) {
    return state;
  }
  loraModule.SPIwriteRegister(REG_XTA_TRIM, LORA_XTA_TRIM);
  loraModule.SPIwriteRegister(REG_XTB_TRIM, LORA_XTB_TRIM);
  return radio.standby();
}

int16_t doorRadioBegin() {
  SPI.setMOSI(PIN_LORA_MOSI);
  SPI.setMISO(PIN_LORA_MISO);
  SPI.setSCLK(PIN_LORA_SCK);

  // The module uses a crystal (no TCXO on DIO3), the DC-DC regulator, and an
  // external RF switch driven by TXEN/RXEN rather than DIO2.
  radio.tcxoVoltage = 0.0f;
  radio.useRegulatorLDO = false;

  ConfigLoRa_t cfg;
  cfg.frequency = LORA_FREQ_MHZ;
  cfg.bandwidth = LORA_BW_KHZ;
  cfg.spreadingFactor = LORA_SF;
  cfg.codingRate = LORA_CR;
  cfg.syncWord = LORA_SYNC_WORD;
  cfg.power = LORA_TX_POWER_DBM;
  cfg.preambleLength = LORA_PREAMBLE;
  int16_t state = radio.begin(cfg);
  if (state != RADIOLIB_ERR_NONE) {
    return state;
  }
  radio.setRfSwitchTable(rfSwitchPins, rfSwitchTable);

  state = radio.setDio2AsRfSwitch(false);
  if (state != RADIOLIB_ERR_NONE) {
    return state;
  }
  state = radio.setCRC(2);
  if (state != RADIOLIB_ERR_NONE) {
    return state;
  }
  return doorRadioApplyTrim();
}

void doorRadioReport(Print &log, int16_t state) {
  if (state == RADIOLIB_ERR_NONE) {
    log.println(F("RADIO OK"));
  } else {
    log.print(F("RADIO FAIL ("));
    log.print(state);
    log.println(F(")"));
  }
}
