---
id: vpn-access
title: VPN access with GlobalProtect
family: VDA
owner_team: network
last_reviewed: 2026-11-07
applications: [GlobalProtect, Okta Verify, Device Certificate Service]
tools: [reset_vpn_profile]
---

## Symptoms

GlobalProtect VPN disconnects immediately after MFA. VPN connects, then drops within seconds. VPN disconnects shortly after login. Certificate error in the VPN client. Can't reach the gateway. Can't reach Confluence, Jira, the intranet or the HR Portal from home.

## Checks

1. `vpn-mfa-approval-check`: confirm the Okta MFA approval succeeds, and whether the tunnel drops after it. Healthy: approval succeeds and the tunnel stays up.
2. `vpn-client-error-check`: collect GlobalProtect client logs and the time of the disconnect. Healthy: a gateway connection with no certificate or policy errors.
3. `vpn-device-cert-check`: check the device certificate's expiry date and enrolled profile. Healthy: the certificate is current and matches the active VPN profile.
4. Confirm the gateway reads `vpn-gp.corplabs.internal`, not the retired `vpn.corplabs.internal`.

## Error codes

- `TLS handshake failed: certificate expired`: the device certificate has expired.
- `TLS_CERT_EXPIRED`: the same failure, as logged by the gateway.
- `certificate validation failed: cert_expired`: the gateway rejected the device certificate.

## Known causes

- **Expired device certificate.** By far the most common cause. A drop right after successful MFA points here. Renewal often fails on a device that's been offline for over 30 days.
- **Stale VPN profile.** A renewed certificate exists, but GlobalProtect still uses the old profile.
- **Legacy gateway entry.** The client still points to the retired portal.
- **Okta Verify clock drift.** Over 60 seconds of drift rejects tokens with no visible error. Force a sync in Okta Verify under Settings.

## Fix

If the gateway is correct and the error names a certificate, or the device has been offline for a long time, use `reset_vpn_profile`. It regenerates the certificate and profile in about 90 seconds. Then the person restarts GlobalProtect and reconnects.

## When to escalate

If gateway, certificate and MFA are all fine and the problem continues, send it to `NET-VPN`, which owns gateways and firewall rules. Many devices failing at once suggests a certificate rotation problem, so send that to `NET-VPN` too and raise the priority.
