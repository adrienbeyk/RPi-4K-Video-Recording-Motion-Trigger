#!/bin/bash
sudo killall -9 motion
sudo setpci -s 01:00.0 0xD4.B=0x41
#~/venv/bin/python ./detect.py
# We installed globally this time
python3 ./detect.py
