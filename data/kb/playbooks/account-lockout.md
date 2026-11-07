---
id: account-lockout
title: Account lockout and password reset
family: ALP
owner_team: identity
last_reviewed: 2026-11-07
applications: [Active Directory, SSO Portal, Password Reset Portal, Okta Verify]
tools: [unlock_ad_account]
---

## Symptoms

Account locked. Locked out of my account. Account locked again after a password reset. Repeated failed sign-ins. Can't sign in to the SSO Portal. The Password Reset Portal says the link or token has expired. Password reset completed, but sign-in still fails within minutes. Forgotten or expired password.

## Checks

1. Count this account's lockouts in the last 24 hours. This comes first, because it decides the path under SEC-04.
2. `account-lockout-source-check`: review lockout and failed sign-in logs on the domain controller, such as `DC-EAST-03.corplabs.internal`. Healthy: no device or service still sends old credentials.
3. `account-reset-token-check`: confirm the reset token is current and the new password reached directory services. Healthy: the token is valid and the change has propagated.
4. `account-mobile-cache-check`: ask the person to remove saved credentials from mail and collaboration apps on their phone. Healthy: no new failed sign-ins.

## Error codes

- `Password reset token expired`: request a new token, because the old one no longer works.
- `Account locked`: the lockout policy fired. Check the source before unlocking.

## Known causes

- **Stale phone credentials.** The most common cause. A phone keeps sending the old password after a reset, which locks the account again within minutes. Unlocking alone won't hold.
- **Expired reset token.** The reset started but never finished, so the old password is still being tried.
- **Standard lockout.** Five failed sign-ins in 15 minutes, often on Monday mornings after a forgotten password. Not a security concern on its own.

## Fix

For one lockout in 24 hours, confirm the person with an Okta Verify push, then use `unlock_ad_account`. Security questions are no longer used. Then the person removes saved credentials from their phone and sets a new password at `passwordreset.corplabs.com`.

An unlock with no fix for the source just locks the account again.

## When to escalate

- Two or more lockouts in 24 hours are a possible compromise under SEC-04 §4.2. Don't unlock. Send it to `SEC-INCIDENT`, even if earlier tickets were simply unlocked.
- If the number of lockouts isn't known, escalate and say so, because it decides the path.
- If the source device can't be found, send it to `IAM-ACCESS`.
