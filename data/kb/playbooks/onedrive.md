---
id: onedrive
title: OneDrive sync
family: null
owner_team: application
last_reviewed: 2026-11-07
applications: [OneDrive, Microsoft 365]
tools: []
---

## Symptoms

OneDrive sync stuck on Processing changes. Files aren't syncing. A file won't upload. OneDrive says the storage is full. A red cross on Excel files.

## Checks

1. Check the person's quota in the OneDrive usage report, not in the client.
2. Ask which files don't sync, and look for `#` or `%` in names, or paths over 400 characters.
3. Check Microsoft 365 Service Health for active incidents.

## Error codes

None recorded.

## Known causes

- **Unsupported filename.** A `#` or `%` fails silently. This is common in Finance, which uses `#` for report versions.
- **Quota exceeded.** The client can show an old figure.
- **Back-end disruption.** A Microsoft-side incident, with no local fix.

## Fix

The person renames the files, or clears space to get under their quota. Both are safe for them to do alone.

## When to escalate

If quota and filenames are fine and there's no Microsoft incident, send it to `APP-M365`, which can pull back-end sync logs.
