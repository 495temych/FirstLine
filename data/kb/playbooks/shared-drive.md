---
id: shared-drive
title: Shared drive access
family: SDA
owner_team: service desk
last_reviewed: 2026-11-07
applications: [Windows file shares, Windows Explorer, SMB, AD security groups]
tools: [remap_drives, add_user_to_share_group, clear_credential_manager]
---

## Symptoms

Access denied to the Finance shared drive. Denied access to a department share. A mapped drive repeatedly prompts for credentials. Shared drive or network path unreachable. A mapped drive is missing after login or VPN. New starter can't open the team folder.

## Checks

1. If the person is remote, confirm the VPN is connected.
2. `shared-drive-group-check`: compare the person's AD group membership with the share's permissions. Healthy: they're in the group that grants access.
3. `shared-drive-token-check`: have them sign out and in, then try again. Healthy: the new token includes the access.
4. `shared-drive-path-check`: confirm they're using the current path, not an old shortcut. Healthy: the current path opens.

## Error codes

- `Access is denied`: the share refused this person.
- `0x80070005`: the Windows code for access denied.
- `NT_STATUS_ACCESS_DENIED`: the same refusal, from the file server.
- `Mapped drive repeatedly prompts for credentials`: usually stale saved credentials, or no access at all.

## Known causes

- **Missing group membership.** The most common cause, often after onboarding or a group cleanup.
- **Stale credentials or token.** Membership is right, but the session predates the change.
- **Folder permissions.** Broken inheritance or an explicit deny entry overrides the group. This is a server-side fault.
- **Old drive mapping.** The path is out of date, or the drive letter clashes.
- **Maintenance.** `FS-CORP-02` has a window on Tuesdays, 22:00 to 23:00 CET.

## Fix

- Missing or wrong drive mapping: use `remap_drives`.
- Membership is right, but credentials are stale: use `clear_credential_manager`, then sign out and in.
- Missing group: under SEC-11, a technician uses `add_user_to_share_group`, only with the data owner's or manager's approval on the ticket.

## When to escalate

Send it to `SD-FILES` if permissions look wrong on the folder, if several people lose the same path outside the Tuesday window, or if access has no recorded approval. Requests for new access are escalated, never declined.
