#!/bin/bash
set -euo pipefail

v=0x39
while true; do
  echo "Set rate = $v (press Enter to apply, or Ctrl+C to stop)"
  read -r
  sudo i2ctransfer -f -y 9 w3@0x6b 0x04 0x18 "$v"
  sudo i2ctransfer -f -y 9 w3@0x6b 0x04 0x1B "$v"

  if [ "$v" = "0x20" ]; then
    echo "Reached 0x20, stopping."
    break
  fi
  v=$(printf "0x%02X" $((16#${v#0x} - 1)))
done
