---
id: software-install
title: Software installation
family: SIB
owner_team: service desk
last_reviewed: 2026-11-07
applications: [Software Center, Company Portal, Intune, Endpoint Protection]
tools: [push_approved_software, force_intune_sync]
---

## Symptoms

Software Center install blocked by Endpoint Protection policy. Application not visible in Software Center. Installation fails. I need software installed, but I don't have admin rights. App isn't listed in Company Portal. Company Portal won't open.

## Checks

1. `software-entitlement-check`: confirm the person or device is in the app's entitlement group. Healthy: the group is present and synchronised.
2. `software-policy-evaluation-check`: review management status and refresh policy and inventory. Healthy: the app is visible and targeted to the device.
3. `software-security-block-check`: check endpoint protection for a block on the installer. Healthy: no active rule blocks it.
4. Check whether the title is in the Company Portal catalog.

## Error codes

- `Installation blocked by policy`: an endpoint protection rule stopped the installer.
- `INSTALL_BLOCKED_POLICY_CHECK`: the same block, from the deployment.
- `Application not visible in Software Center`: the app isn't targeted to this device yet.
- `0x87D00607`: the content isn't available to the client.
- `0x87D1041C`: the deployment couldn't be detected.

## Known causes

- **Endpoint protection block.** The installer's publisher or hash isn't on the allowlist. It's a security decision, not a fault.
- **Stale device inventory.** A missed check-in means the app isn't offered yet.
- **Missing entitlement.** The person isn't in the group that targets the app.
- **Standard account.** No local admin rights under SEC-07. This is expected.
- **Not in the catalog.** It needs a `SR-SOFTWARE` request with manager approval.

## Fix

- Title is in the catalog: the person installs it from Company Portal, which needs no admin rights.
- In the catalog, but they can't reach the portal: use `push_approved_software`.
- Stale inventory, or the app isn't visible: use `force_intune_sync`.
- Not in the catalog: explain the `SR-SOFTWARE` request.

## When to escalate

- An endpoint protection block goes to `SEC-POLICY`. Never work around it.
- A missing entitlement is an access request, so send it to `IAM-ACCESS`.
- An approved title needed urgently goes to `DESK-SUPPORT`, with team lead sign-off under SEC-07.
