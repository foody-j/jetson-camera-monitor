#!/bin/bash
set -euo pipefail

# MAX96712 (Deserializer) on i2c-9 @0x6b
BUS=9
DESER=0x6b

sudo i2cdetect -l
sleep 0.01
sudo i2cdetect -r -y "$BUS"
sleep 0.01

# 1) MAX96712/MAX96724 end flag detection
sudo i2ctransfer -f -y "$BUS" w2@"$DESER" 0x00 0x06 r1
sleep 0.01
sudo i2ctransfer -f -y "$BUS" w2@"$DESER" 0x00 0x1a r1
sleep 0.01
sudo i2ctransfer -f -y "$BUS" w2@"$DESER" 0x00 0x0a r1
sleep 0.01
sudo i2ctransfer -f -y "$BUS" w2@"$DESER" 0x00 0x0b r1
sleep 0.01
sudo i2ctransfer -f -y "$BUS" w2@"$DESER" 0x00 0x0c r1
sleep 0.01

# 1.3 VID/PKL/DET status
sudo i2ctransfer -f -y "$BUS" w2@"$DESER" 0x01 0x08 r1
sleep 0.01
sudo i2ctransfer -f -y "$BUS" w2@"$DESER" 0x01 0x1a r1
sleep 0.01
sudo i2ctransfer -f -y "$BUS" w2@"$DESER" 0x01 0x2c r1
sleep 0.01
sudo i2ctransfer -f -y "$BUS" w2@"$DESER" 0x01 0x3E r1
sleep 0.01
sudo i2ctransfer -f -y "$BUS" w2@"$DESER" 0x01 0x50 r1
sleep 0.01
sudo i2ctransfer -f -y "$BUS" w2@"$DESER" 0x01 0x68 r1
sleep 0.01
sudo i2ctransfer -f -y "$BUS" w2@"$DESER" 0x01 0x7a r1
sleep 0.01
sudo i2ctransfer -f -y "$BUS" w2@"$DESER" 0x01 0x8c r1
sleep 0.01

# 1.4 MIPI PHY status (read multiple times)
for _ in {1..5}; do
  sudo i2ctransfer -f -y "$BUS" w2@"$DESER" 0x08 0xD0 r1
  sleep 0.01
done
sudo i2ctransfer -f -y "$BUS" w2@"$DESER" 0x11 0xD0 r1
sleep 0.01
for _ in {1..5}; do
  sudo i2ctransfer -f -y "$BUS" w2@"$DESER" 0x08 0xD1 r1
  sleep 0.01
done
sudo i2ctransfer -f -y "$BUS" w2@"$DESER" 0x11 0xD0 r1
sleep 0.01

# 1.5/1.6 error counters and decoder memory
sudo i2ctransfer -f -y "$BUS" w2@"$DESER" 0x11 0xe1 r1
sleep 0.01
sudo i2ctransfer -f -y "$BUS" w2@"$DESER" 0x11 0xe5 r1
sleep 0.01
sudo i2ctransfer -f -y "$BUS" w2@"$DESER" 0x11 0xe9 r1
sleep 0.01
sudo i2ctransfer -f -y "$BUS" w2@"$DESER" 0x04 0x38 r1
sleep 0.01

# 1.7 decode errors (read-clear)
sudo i2ctransfer -f -y "$BUS" w2@"$DESER" 0x00 0x35 r1
sleep 0.01
sudo i2ctransfer -f -y "$BUS" w2@"$DESER" 0x00 0x36 r1
sleep 0.01
sudo i2ctransfer -f -y "$BUS" w2@"$DESER" 0x00 0x37 r1
sleep 0.01
sudo i2ctransfer -f -y "$BUS" w2@"$DESER" 0x00 0x38 r1
sleep 0.01

# Serializer (MAX9295/MAX96717) -- read all detected serializer addresses
for SER in 0x42 0x44 0x46 0x48; do
  echo "[SER $SER] 0x0102:"
  sudo i2ctransfer -f -y "$BUS" w2@"$SER" 0x01 0x02 r1
  sleep 0.01
  echo "[SER $SER] 0x010a:"
  sudo i2ctransfer -f -y "$BUS" w2@"$SER" 0x01 0x0a r1
  sleep 0.01
  echo "[SER $SER] 0x0112:"
  sudo i2ctransfer -f -y "$BUS" w2@"$SER" 0x01 0x12 r1
  sleep 0.01
  echo "[SER $SER] 0x011a:"
  sudo i2ctransfer -f -y "$BUS" w2@"$SER" 0x01 0x1a r1
  sleep 0.01
  echo "[SER $SER] 0x055d:"
  sudo i2ctransfer -f -y "$BUS" w2@"$SER" 0x05 0x5d r1
  sleep 0.01
  echo "[SER $SER] 0x055e:"
  sudo i2ctransfer -f -y "$BUS" w2@"$SER" 0x05 0x5e r1
  sleep 0.01
  echo "[SER $SER] 0x055f:"
  sudo i2ctransfer -f -y "$BUS" w2@"$SER" 0x05 0x5f r1
  sleep 0.01
  echo "[SER $SER] 0x0560:"
  sudo i2ctransfer -f -y "$BUS" w2@"$SER" 0x05 0x60 r1
  sleep 0.01
done
