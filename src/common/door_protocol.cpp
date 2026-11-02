#include "door_protocol.h"

static uint8_t crc8(const uint8_t *data, size_t len) {
  uint8_t crc = 0;
  for (size_t i = 0; i < len; i++) {
    crc ^= data[i];
    for (int bit = 0; bit < 8; bit++) {
      crc = (crc & 0x80) ? (uint8_t)((crc << 1) ^ 0x07) : (uint8_t)(crc << 1);
    }
  }
  return crc;
}

void doorEncode(const DoorStatus &status, uint8_t *buf) {
  uint32_t vdd20 = (status.vddMv + 10) / 20;
  if (vdd20 > 255) {
    vdd20 = 255;
  }
  buf[0] = DOOR_MAGIC;
  buf[1] = DOOR_VERSION;
  buf[2] = status.networkId & 0xFF;
  buf[3] = status.networkId >> 8;
  buf[4] = DOOR_MSG_STATUS;
  buf[5] = status.door ? 1 : 0;
  buf[6] = status.seq & 0xFF;
  buf[7] = status.seq >> 8;
  buf[8] = (uint8_t)vdd20;
  buf[9] = crc8(buf, DOOR_PACKET_LEN - 1);
}

bool doorDecode(const uint8_t *buf, size_t len, uint16_t expectedNetworkId, DoorStatus &out) {
  if (len != DOOR_PACKET_LEN || buf[0] != DOOR_MAGIC || buf[1] != DOOR_VERSION ||
      buf[4] != DOOR_MSG_STATUS || buf[5] > 1) {
    return false;
  }
  if (crc8(buf, DOOR_PACKET_LEN - 1) != buf[9]) {
    return false;
  }
  uint16_t networkId = buf[2] | (buf[3] << 8);
  if (networkId != expectedNetworkId) {
    return false;
  }
  out.networkId = networkId;
  out.door = buf[5];
  out.seq = buf[6] | (buf[7] << 8);
  out.vddMv = buf[8] * 20;
  return true;
}
