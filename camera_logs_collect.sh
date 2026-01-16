#!/bin/bash
set -euo pipefail

USER_HOME="${HOME:-/home/yjk}"
LOG_DIR="${USER_HOME}/camera_logs"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_DIR="${LOG_DIR}/${STAMP}"

mkdir -p "${OUT_DIR}"

# 1) Live dmesg log (if service is running)
if [ -f /var/log/dmesg_live.log ]; then
  sudo cp /var/log/dmesg_live.log "${OUT_DIR}/dmesg_live.log"
fi

# 2) Previous boot kernel log (if persistent journald is enabled)
sudo journalctl -k -b -1 > "${OUT_DIR}/kernel_prev_boot.log" || true

# 3) Pstore (kernel panic traces)
if [ -d /sys/fs/pstore ]; then
  sudo cp /sys/fs/pstore/* "${OUT_DIR}/" 2>/dev/null || true
fi

cat <<EOF > "${OUT_DIR}/README.txt"
camera_logs collected at ${STAMP}
- dmesg_live.log: live kernel log (if enabled)
- kernel_prev_boot.log: previous boot kernel log (needs journald persistent)
- pstore files: kernel panic traces (if present)
EOF

echo "Saved logs to ${OUT_DIR}"
