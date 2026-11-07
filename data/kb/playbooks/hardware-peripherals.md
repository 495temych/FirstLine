---
id: hardware-peripherals
title: Docks, monitors and peripherals
family: null
owner_team: desktop support
last_reviewed: 2026-11-07
applications: [Dell WD22TB4, Dell U2723QE, Dell Peripheral Manager, CalDigit TS3+]
tools: []
---

## Symptoms

External monitor not detected. My dock isn't working. Monitor says no signal. Keyboard or mouse stopped working on the dock. Display drops after sleep.

## Checks

1. Confirm the dock model on its underside: WD22TB4, or a legacy CalDigit TS3+.
2. Check the firmware in Dell Peripheral Manager.
3. Plug the peripheral straight into the laptop, to separate a dock fault from a device fault.

## Error codes

None recorded.

## Known causes

- **Thunderbolt cable not fully seated.** The most common cause. It should click.
- **Old dock firmware.** Version 5.2 and below has a cold-boot detection bug, fixed in 5.4.
- **Wrong monitor input.** The U2723QE should be set to USB-C, not DP.
- **Legacy CalDigit TS3+.** It drops displays after sleep, and has no fix.

## Fix

The person reseats the cable until it clicks, updates firmware to 5.4 or later, and sets the monitor's input to USB-C.

## When to escalate

- Legacy CalDigit docks that drop displays go to `DESK-HARDWARE`, for replacement.
- If nothing is detected after checking the cable and firmware, it's a hardware fault. Send it to `DESK-HARDWARE`, with a spare WD22TB4 for a swap test.
