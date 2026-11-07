---
id: laptop-performance
title: Laptop performance
family: LPD
owner_team: desktop support
last_reviewed: 2026-11-07
applications: [Windows, Task Manager, Microsoft Defender, CrowdStrike Falcon, Outlook, Teams, Chrome]
tools: [clean_temp_files, enable_onedrive_files_on_demand]
---

## Symptoms

Laptop slow after login. Windows laptop very slow. Laptop running slowly. High CPU and a nearly full disk. Applications take a long time to open. Outlook, Teams and Chrome are sluggish on startup. Battery drains fast.

## Checks

1. `laptop-resource-check`: review CPU, memory and disk use during login. Healthy: use returns to normal after startup.
2. `laptop-startup-policy-check`: review recent startup scripts, policies and scheduled scans. Healthy: no heavy startup task or scan backlog.
3. `laptop-disk-space-check`: check free disk space and temporary files. Healthy: enough free space, with no runaway files.

## Error codes

- `MsMpEng.exe`: Microsoft Defender is scanning, which is the most common CPU spike.

## Known causes

- **Scan backlog.** The most common cause. Queued endpoint protection scans run at login.
- **CrowdStrike Falcon scan.** Devices that still run it show `CSFalconService` using CPU. Slowness for about 20 minutes is expected.
- **Startup policy or items.** A heavy startup policy or too many startup apps.
- **Low disk space.** Under about 10% free, everything gets worse. OneDrive full sync can fill the SSD.
- **Ageing battery.** On devices over 2 years old, check battery health.

## Fix

- A scan is running: this is expected. Tell the person it should clear, and there's nothing to fix.
- Low disk space: use `clean_temp_files`. If OneDrive is the cause, use `enable_onedrive_files_on_demand`.
- Too many startup apps: the person turns them off under Task Manager > Startup apps.

## When to escalate

- Send it to `DESK-SUPPORT` if slowness continues, or if a startup policy or scan schedule needs changing.
- If a device is over 2 years old with battery health under 60%, send it to `DESK-HARDWARE`.
