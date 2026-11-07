---
id: teams
title: Microsoft Teams
family: null
owner_team: application
last_reviewed: 2026-11-07
applications: [Microsoft Teams]
tools: [clear_teams_cache]
---

## Symptoms

Teams shows me as offline to everyone. Presence is stuck. Teams is unresponsive or frozen. Teams isn't updating after the laptop wakes.

## Checks

1. Check the Teams build under Settings > About.
2. Check how many people are affected.
3. Check Microsoft 365 Service Health.

## Error codes

None recorded.

## Known causes

- **Corrupt local cache.** The most common cause.
- **Stale session after sleep.** Teams doesn't refresh after the laptop wakes.
- **Old build.** Build 26189 had a presence bug, since patched.

## Fix

If the build is current, use `clear_teams_cache`. The person fully quits Teams first. Presence should recover within 2 minutes of relaunch.

## When to escalate

If clearing the cache doesn't hold, or several people are affected at once, check Service Health and send it to `APP-M365`.
