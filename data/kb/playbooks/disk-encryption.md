---
id: disk-encryption
title: Disk encryption with BitLocker
family: EDE
owner_team: desktop support
last_reviewed: 2026-11-07
applications: [BitLocker, manage-bde, TPM, Intune, Endpoint Manager]
tools: [escrow_bitlocker_key, force_intune_sync]
---

## Symptoms

BitLocker not enabled. BitLocker not enabling on my laptop. Recovery key not escrowed. TPM not initialized. Device noncompliant for BitLocker, and Intune shows conflicting state. Encryption didn't start after a re-image. BitLocker protection is off or suspended.

## Checks

1. `encryption-tpm-check`: confirm the TPM is ready and a protector exists. Healthy: a ready TPM and a valid protector.
2. `encryption-policy-check`: confirm the disk encryption policy is assigned and delivered. Healthy: the device receives the active policy with no errors.
3. `encryption-key-escrow-check`: confirm the recovery key is escrowed. Healthy: the current key is visible to support.

## Error codes

- `TPM protector not initialized`: BitLocker has no hardware protector, so encryption can't start.
- `BitLocker: Protection Off`: the volume isn't protected.
- `manage-bde: Protection Suspended`: protection is paused.
- `Recovery key not escrowed`: the key hasn't reached the management service.
- `KeyBackupError 0x87D1FDE8`: key backup failed during enrolment.

## Known causes

- **TPM protector not initialized.** The most common cause, often after a re-image or provisioning failure.
- **Recovery key escrow failed.** Encryption is healthy, but the key never reached Intune or Azure AD.
- **Encryption policy not delivered.** A missed sync or deprecated policy reference.

## Fix

- TPM and encryption are healthy, but the key isn't escrowed: a technician uses `escrow_bitlocker_key`.
- Policy hasn't reached the device: use `force_intune_sync`.

Recovery keys are sensitive under SEC-09, so never send one in a ticket or message.

## When to escalate

TPM and protector work needs hands-on access, so send it to `DESK-SUPPORT`. That includes initializing the TPM, adding a protector and starting encryption.
