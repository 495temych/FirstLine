---
id: wifi
title: Corporate Wi-Fi
family: WCI
owner_team: network
last_reviewed: 2026-11-07
applications: [Corporate Wi-Fi, RADIUS, Cisco ISE, Cisco wireless controllers]
tools: [push_wifi_profile, push_wifi_driver_update]
---

## Symptoms

Cannot connect to Corporate Wi-Fi. Multiple users can't connect to `CORPLABS-CORP`. Wi-Fi authentication fails. Joined the wireless network but there's no network access. Wi-Fi keeps dropping. 802.1X or EAP-TLS certificate errors on the laptop.

## Checks

1. Find out whether it's one device or many people in the same place. This decides the path.
2. `wifi-profile-check`: confirm the device has the current Wi-Fi profile and a valid wireless certificate. Healthy: both are current.
3. `wifi-nac-policy-check`: the network team checks access control and RADIUS logs. Healthy: the device authenticates and gets the right policy.
4. `wifi-controller-health-check`: the network team reviews controller logs. Healthy: stable association with no repeated disconnects.

## Error codes

- `802.1X authentication failed`: the wireless sign-in was rejected. Check the certificate first.
- `EAP-TLS certificate expired`: a certificate in the authentication chain has expired.
- `802.1X authentication failed: certificate expired`: the same failure, shown on the device.

## Known causes

- **Expired server certificate.** The most common cause. A RADIUS or wireless controller certificate expires, and many users fail at once. Nothing can be fixed on the device.
- **Network access policy mismatch.** A bad group mapping places valid users in a quarantine role.
- **Stale profile on one device.** Certificate or profile entries are out of date, often after a re-image.
- **Old Intel driver.** ThinkPad T14 devices on a driver older than 2026-05 drop connections.
- **Floor 5 in Zürich.** A known access point congestion issue, pending an upgrade in Q4 2026. Don't troubleshoot it per ticket.

## Fix

- One device with an old profile or certificate: use `push_wifi_profile`.
- One ThinkPad T14 with a driver older than 2026-05: use `push_wifi_driver_update`.

## When to escalate

Send it to `NET-WIFI` if several people are affected, or if the logs point to RADIUS, a certificate, a controller or access policy. For floor 5 congestion, log it under `NET-WIFI` for tracking and reference `NET-WIFI-FLOOR5-KNOWN`.
