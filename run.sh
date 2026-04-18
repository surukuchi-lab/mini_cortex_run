#!/bin/bash

cd "$(dirname "$0")"
python3.7 src/mini_cortex_run.py $1 $2 > /dev/tty
