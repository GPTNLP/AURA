#!/bin/bash
set -e

export DISPLAY=:0
export XAUTHORITY=/home/$USER/.Xauthority

sleep 5

# Rotate screen 90 degrees to the right
xrandr -o right || true

# Hide mouse cursor when idle
unclutter -idle 0.5 -root &

# Open local app in kiosk mode
chromium-browser \
  --noerrdialogs \
  --disable-infobars \
  --kiosk \
  --app=http://127.0.0.1:8000 \
  --start-fullscreen \
  --overscroll-history-navigation=0 \
  --disable-pinch \
  --check-for-update-interval=31536000