#!/bin/bash

# code from https://github.com/phillipdavidstearns/simcom_wwan-setup

MODULE="simcom_wwan"
IFACE="wwan0"
DEV="ttyUSB2"

if [ "$EUID" -ne 0 ]
  then echo "[!] Please run as root"
  exit 1
fi

# Check for kernel module
if (lsmod | grep "$MODULE" >/dev/null 2>&1); then
	# Check for interface
	if (ifconfig -a | grep "$IFACE" >/dev/null 2>&1); then
		# Bring interface up
		if (ifconfig "$IFACE" up >/dev/null 2>&1); then
			# Check for simcom tty device
			if (ls /dev | grep "$DEV" >/dev/null 2>&1); then
				# Connect NIC to network
				if (echo -e 'AT$QCRMCALL=1,1\r' > /dev/$DEV); then
					sleep 5
					echo "[+] $IFACE at /dev/$DEV is ready for an IP Address"
					exit 0
				else
					echo "[!] Failed to activate connection on $DEV"
					exit 1
				fi
			else
				echo "[!] /dev/$DEV not found"
				ifconfig "$IFACE" down
				exit 1
			fi
		else
			echo "[!] Could not bring up $IFACE."
			exit 1
		fi
	else
		echo "[!] interface $IFACE not found"
		exit 1
	fi
else
	echo "[!] $MODULE module not found"
	exit 1
fi
