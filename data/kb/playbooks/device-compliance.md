---
id: device-compliance
title: Device compliance
family: DCP
owner_team: service desk
last_reviewed: 2026-11-07
applications: [Intune, Company Portal, Conditional Access, Exchange Online, SharePoint Online]
tools: [force_intune_sync]
---

## Symptoms

Device marked noncompliant in Intune. Company Portal says my device is noncompliant. Conditional Access blocks sign-in to email or SharePoint. Intune shows the device as NonCompliant after a policy change. Device hasn't checked in. Missing encryption compliance signal.

## Checks

1. `compliance-checkin-check`: confirm the device's last Intune check-in. Healthy: the timestamp is current and evaluation has run.
2. `compliance-signal-check`: find the failing signal, usually encryption. Healthy: required signals report healthy values.
3. `compliance-policy-scope-check`: compare the assigned policy with the device's intended group. Healthy: in scope, with no stale assignment.

## Error codes

- `Compliance state: NonCompliant`: Intune's evaluation failed or is out of date.
- `Conditional Access blocked sign-in to Exchange Online`: the block that follows noncompliance.
- `Conditional Access blocked access to SharePoint`: the same block, for SharePoint.

## Known causes

- **Stale check-in.** The most common cause. The device hasn't reported, so Intune holds an old or missing encryption signal.
- **Encryption isn't on.** BitLocker or FileVault really is off, so see the `disk-encryption` playbook.
- **Mismatch after a policy change.** Intune says compliant, but Conditional Access still holds the old state until a new sign-in.

## Fix

Use `force_intune_sync`. Then the person restarts the device, opens Company Portal and chooses Check status. If the signal then shows encryption is off, the person turns it on, or see the `disk-encryption` playbook.

Under SEC-09, the fix is to make the device compliant, never to exclude it from the policy.

## When to escalate

Send it to `SD-DEVICE` if the device stays noncompliant after a sync and restart, or the policy assignment looks wrong. If BitLocker or TPM is faulty, send it to `DESK-SUPPORT`.
