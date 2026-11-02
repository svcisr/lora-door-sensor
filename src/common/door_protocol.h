// Over-the-air packet shared by sensor and receiver.
//
// Layout (10 bytes, little endian):
//   0     magic 0xD5
//   1     protocol version
//   2..3  network ID
//   4     message type (1 = door status)
//   5     door state (0 = closed, 1 = open)
//   6..7  sequence number
//   8     sensor supply voltage in 20 mV steps
//   9     CRC-8 (poly 0x07) over bytes 0..8
#pragma once

#include <stddef.h>
#include <stdint.h>

constexpr uint8_t DOOR_MAGIC = 0xD5;
constexpr uint8_t DOOR_VERSION = 1;
constexpr uint8_t DOOR_MSG_STATUS = 1;
constexpr size_t DOOR_PACKET_LEN = 10;

struct DoorStatus {
  uint16_t networkId;
  uint8_t door;
  uint16_t seq;
  uint16_t vddMv;
};

// Writes DOOR_PACKET_LEN bytes into buf.
void doorEncode(const DoorStatus &status, uint8_t *buf);

// Returns true only for a well-formed status packet carrying expectedNetworkId.
bool doorDecode(const uint8_t *buf, size_t len, uint16_t expectedNetworkId, DoorStatus &out);
