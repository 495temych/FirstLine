---
id: outlook
title: Outlook and mailbox sync
family: OES
owner_team: application
last_reviewed: 2026-11-07
applications: [Outlook, Outlook Mobile, Exchange Online, Intune]
tools: [clear_credential_manager, reset_mobile_mail_profile]
---

## Symptoms

Outlook not syncing. Outlook mobile not syncing on my iPhone. Outlook shows Disconnected. Mail stopped updating. Last synced hours ago. Outlook keeps asking for my password. Mobile email blocked by device compliance.

## Checks

1. `outlook-connection-state-check`: check Outlook's connection state. Healthy: connected, and folders update without delay.
2. `outlook-mobile-partnership-check`: review mobile sync partnerships and the phone's compliance state. Healthy: a compliant device with a healthy partnership.
3. `outlook-profile-health-check`: test with a clean profile. Healthy: a clean profile syncs without errors.
4. Note whether desktop, mobile or both are affected. Only one failing narrows the cause. If Outlook keeps asking for a password, check how old the Okta session is.

## Error codes

- `Outlook status: Disconnected`: the client has lost its Exchange Online connection.
- `Mobile sync failed - 403 (device compliance blocked)`: the phone is noncompliant in Intune.

## Known causes

- **Noncompliant phone.** Intune marks the phone noncompliant, often after an OS baseline change, and Exchange Online blocks it.
- **Stale mobile partnership.** Desktop works, and the phone doesn't, often after an iOS update.
- **Stale desktop profile.** Corrupt profile or OST data leaves Outlook disconnected.
- **Expired Okta session.** Sessions end after 90 days, which causes repeated password prompts. It's expected, and signing in again fixes it.
- **Stale saved credentials.** A fresh session, but prompts continue.

## Fix

- Noncompliant phone: the person updates the phone, then syncs Company Portal.
- Phone is compliant, but mobile mail fails: use `reset_mobile_mail_profile`.
- Password prompts with a fresh Okta session: use `clear_credential_manager`, then restart Outlook.
- Desktop profile: the person creates a new profile under Control Panel > Mail > Show Profiles, if credentials are ruled out.

## When to escalate

Send it to `APP-M365` if a profile rebuild doesn't help, if the person has PST archives over 5 GB, or if several mailboxes fail at once. Check Microsoft 365 Service Health first.
