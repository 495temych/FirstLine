# Escalation queues

**Category:** Organizational context | **Owner team:** Service desk | **Last reviewed:** 2026-11-07

Each ticket goes to the team that owns the next step. These are the ServiceNow assignment groups.

| Queue | Team | Owns | Typical SLA |
|---|---|---|---|
| `SD-PRINT` | Service desk | Print server queues, spooler and drivers | 4 business hours |
| `SD-FILES` | Service desk | File servers, shared drives and their access groups | 4 business hours |
| `SD-DEVICE` | Service desk | Intune enrolment, check-in and device compliance | 1 business day |
| `DESK-SUPPORT` | Desktop support | Laptop performance, operating system faults, BitLocker and TPM problems, and urgent installs | 1 business day |
| `DESK-HARDWARE` | Desktop support | Physical repair and replacement | 2 business days |
| `NET-VPN` | Network | VPN gateways and connectivity | 4 business hours |
| `NET-WIFI` | Network | Wireless controllers, access points and RADIUS | 4 business hours |
| `NET-DNS` | Network | Internal DNS resolvers and zones | 4 business hours |
| `IAM-ACCESS` | Identity | SSO, MFA, conditional access, lockout investigations and access requests | 4 business hours |
| `APP-M365` | Application | Outlook profiles, Exchange Online, Teams and OneDrive back ends. Check Microsoft 365 Service Health first | 1 business day |
| `APP-SUPPORT` | Application | Business applications, internal services and their certificates | 4 business hours |
| `SEC-POLICY` | Security | Application control blocks and endpoint protection policy exceptions | 1 business day |
| `SEC-INCIDENT` | Security | Suspected account compromise | Immediate |

If two teams could own a ticket, send it to the team that owns the failing system, not the team that reported it.
