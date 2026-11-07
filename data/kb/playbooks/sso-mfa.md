---
id: sso-mfa
title: SSO sign-in and MFA loops
family: SML
owner_team: identity
last_reviewed: 2026-11-07
applications: [SSO Portal, Okta, Okta Verify, Azure AD, Salesforce, Workday, Concur, Confluence]
tools: []
---

## Symptoms

Stuck in an MFA prompt loop. Okta Verify keeps asking me to approve. MFA approved, but I land back on the sign-in page. Unable to complete SSO login. Can't reach Salesforce, Confluence, Workday or Concur through the SSO Portal. Several users can't sign in after an identity or policy change.

## Checks

1. `sso-mfa-loop-check`: reproduce the sign-in through the SSO Portal, and note whether the loop comes after the challenge. Healthy: one MFA approval reaches the application.
2. `sso-factor-enrollment-check`: the identity team checks active factors in Okta. Healthy: an active factor with no stale or duplicate enrollment.
3. `sso-policy-assignment-check`: the identity team compares group membership with conditional access and application assignment in Azure AD and Okta. Healthy: the user is in the expected group and policy scope.
4. Note how many people are affected, and whether a group sync or policy change happened recently.

## Error codes

- `MFA_PROMPT_LOOP`: the challenge succeeds, but the session isn't accepted.
- `AUTH_401_MFA_REQUIRED`: the application still wants MFA after the challenge.
- `Okta-ERR-1012`: the enrollment token doesn't match, so the factor record is stale.

## Known causes

- **Stale MFA enrollment.** The most common cause, often after an Azure AD to Okta sync or an authenticator reinstall.
- **Policy or group mismatch.** Conditional access doesn't match current group assignments, or a deprecated policy is still applied.
- **Clock drift.** The phone's time is out of sync, so codes fail. The person can fix this themselves.

## Fix

If only one person is affected and codes are failing, ask them to set their phone's time to automatic, then force a sync in Okta Verify under Settings. Everything else needs the identity team: L1 can't reset factors or change policy.

## When to escalate

Send stale factors and policy or group mismatches to `IAM-ACCESS`, with the person's name, the applications affected and any recent change. If several users are affected at once, say so in the summary and raise the priority.
