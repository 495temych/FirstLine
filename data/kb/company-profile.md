# CorpLabs AG: IT environment reference

**Category:** Organizational context | **Owner team:** Service desk | **Last reviewed:** 2026-11-07

This is the reference other knowledge base articles assume you already know. It's a snapshot of what CorpLabs AG runs, so support decisions stay consistent across tickets.

---

## Company

CorpLabs AG is headquartered in Zürich, on floors 3-7 of its office, with about 630 staff accounts. Other offices are in the US, including Charlotte, Portland, Arlington and Austin, and in Frankfurt, Munich and Milan. Most tickets come from Sales, Finance, Engineering and Marketing. The service desk takes every IT request first and passes what it can't fix to desktop support, the network, identity, application or security teams.

## Core systems

| System | Product | Notes |
|---|---|---|
| Identity | Active Directory (`CORPLABS` domain) with Azure AD and Okta SSO | Sign-in through the SSO Portal at `sso.corplabs.com`. Okta Verify is the MFA app. Domain controllers include `DC-EAST-03.corplabs.internal` |
| Passwords | Password Reset Portal | `passwordreset.corplabs.com` |
| VPN | Palo Alto GlobalProtect | Needs a valid device certificate, and regional gateways such as `gw-emea-01.corplabs.internal` |
| Email and collaboration | Microsoft 365 | Exchange Online, Outlook, Teams, OneDrive and SharePoint Online |
| Device management | Microsoft Intune, with SCCM on older devices | Company Portal and Software Center. Windows 10 is the main desktop OS, and iOS the main mobile OS |
| Endpoint security | Microsoft Defender, with BitLocker for disk encryption | Recovery keys are escrowed to the management service |
| Print | HP printers on `PS-PRINT01.corplabs.internal`, with PaperCut | Uses the approved HP Universal Print Driver |
| File shares | Windows file servers, such as `FS-CORP-02.corplabs.internal`, plus SharePoint | Access comes from AD security groups |
| Wi-Fi | Cisco wireless controllers, with RADIUS 802.1X | The corporate SSID is `CORPLABS-CORP` |
| DNS | Internal resolvers, such as `dns-res-east-02.corplabs.internal` | Internal names end in `corplabs.internal` |
| Business apps | Salesforce, Workday, Concur, Confluence, Jira, the HR Portal and FinanceApp | Owned by the application team |
| Ticketing | ServiceNow | Incident records |

## Naming conventions

- Internal domains: `*.corplabs.internal`. Public ones: `*.corplabs.com`
- Knowledge base article IDs: `KB-0XXX`
- Ticket IDs: `INC-<FAMILY>-0000`
- Escalation queues: `<TEAM>-<AREA>`, such as `NET-VPN` or `SEC-INCIDENT`

## Known organizational quirks

- The Finance team's Excel naming habit (`#` in filenames for report versioning) is the leading cause of OneDrive sync tickets from that department.
- Floor 5's open-plan area in Zürich has a known Wi-Fi congestion issue (over 40 devices on one access point), pending a Q4 2026 upgrade. It can't be fixed per ticket.
- Lockout tickets spike on Monday mornings, because people forget a password changed after the Friday rotation reminder.
- Repeated lockouts after a password reset usually come from a phone that still holds the old password.

---

*If a ticket depends on something this profile and our playbooks don't cover, treat it as unsupported for automated resolution and escalate it.*
