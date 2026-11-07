# Label review

The seven open decisions are settled and recorded in the labels. What's left is a read through the causes and the held-out rows. Change anything you disagree with in `data/evals/`, then delete this file.

## Named causes

The counts cover the knowledge base, development and unseen development tickets. Open any development ticket in the Tickets tab to compare its cause with the root cause on record. Tickets take the cause their root cause names first, by rules in `data/evals/causes.json`. Rules are approximate, so a few tickets with mixed causes will sit under the wrong one. A count of 0 means the playbook lists the cause, but no ticket here has it.

| Family | Cause | Tickets | Accepted path | Tool or queue |
|---|---|---|---|---|
| Any | No confirmed cause | 4 | Escalate | any |
| Account lockout and password | Stale phone credentials | 47 | Escalate | `SEC-INCIDENT` |
| Account lockout and password | Expired reset token | 0 | Self-serve or Auto-fix | `unlock_ad_account` |
| Account lockout and password | Standard lockout | 0 | Auto-fix or Self-serve | `unlock_ad_account` |
| SSO and MFA | Clock drift | 2 | Self-serve | any |
| SSO and MFA | Policy or group mismatch | 10 | Escalate | `IAM-ACCESS` |
| SSO and MFA | Stale MFA enrollment | 25 | Escalate | `IAM-ACCESS` |
| VPN access | Stale VPN profile | 2 | Auto-fix | `reset_vpn_profile` |
| VPN access | Expired device certificate | 45 | Auto-fix | `reset_vpn_profile` |
| VPN access | Okta Verify clock drift | 0 | Self-serve | any |
| VPN access | Legacy gateway entry | 0 | Self-serve or Auto-fix | `reset_vpn_profile` |
| Wi-Fi | Expired server certificate | 33 | Escalate | `NET-WIFI` |
| Wi-Fi | Network access policy mismatch | 6 | Escalate | `NET-WIFI` |
| Wi-Fi | Stale profile on one device | 3 | Auto-fix | `push_wifi_profile` |
| Wi-Fi | Old Intel driver | 0 | Auto-fix | `push_wifi_driver_update` |
| Wi-Fi | Access point or controller fault | 1 | Escalate | `NET-WIFI` |
| DNS | Broken conditional forwarder | 10 | Escalate | `NET-DNS` |
| DNS | Stale zone record | 16 | Escalate | `NET-DNS` |
| DNS | Stale resolver cache | 16 | Escalate | `NET-DNS` |
| Shared drive access | Folder permissions | 4 | Escalate | `SD-FILES` |
| Shared drive access | Missing group membership | 31 | Escalate | `SD-FILES` |
| Shared drive access | Stale credentials or token | 1 | Auto-fix | `clear_credential_manager` |
| Shared drive access | Old drive mapping | 1 | Auto-fix | `remap_drives` |
| Printing | Corrupt driver package | 43 | Auto-fix | `reinstall_print_driver` |
| Printing | Hung spooler | 0 | Auto-fix | `restart_print_spooler` |
| Printing | One stuck job | 2 | Self-serve | any |
| Outlook sync | Noncompliant phone | 4 | Self-serve | any |
| Outlook sync | Stale mobile partnership | 14 | Auto-fix | `reset_mobile_mail_profile` |
| Outlook sync | Stale desktop profile | 21 | Self-serve or Escalate | `APP-M365` |
| Outlook sync | Expired Okta session | 0 | Self-serve | any |
| Outlook sync | Stale saved credentials | 0 | Auto-fix | `clear_credential_manager` |
| Software install | Endpoint protection block | 21 | Escalate | `SEC-POLICY` |
| Software install | Missing entitlement | 21 | Escalate | `IAM-ACCESS` |
| Software install | Stale device inventory | 5 | Auto-fix | `force_intune_sync` |
| Device compliance | Encryption isn't on | 3 | Self-serve or Escalate | `DESK-SUPPORT` |
| Device compliance | Mismatch after a policy change | 3 | Auto-fix or Escalate | `force_intune_sync`, `SD-DEVICE` |
| Device compliance | Stale check-in | 31 | Auto-fix | `force_intune_sync` |
| Laptop performance | Low disk space | 1 | Auto-fix | `clean_temp_files` |
| Laptop performance | Startup policy or items | 14 | Self-serve or Escalate | `DESK-SUPPORT` |
| Laptop performance | Scan backlog | 32 | Self-serve | any |
| Disk encryption | Recovery key escrow failed | 8 | Auto-fix | `escrow_bitlocker_key` |
| Disk encryption | TPM protector not initialized | 27 | Escalate | `DESK-SUPPORT` |
| Disk encryption | Encryption policy not delivered | 6 | Auto-fix | `force_intune_sync` |
| API timeouts | Expired API token | 7 | Escalate | `APP-SUPPORT` |
| API timeouts | Downstream rate limit | 2 | Escalate | `APP-SUPPORT` |
| API timeouts | Downstream latency | 15 | Escalate | `APP-SUPPORT` |
| Certificate expiry | Expired TLS certificate | 28 | Escalate | `APP-SUPPORT` |

## Held-out rules set

| Id | Requester | Ticket | Answer | Tool or queue | Difficulty | Note |
|---|---|---|---|---|---|---|
| H-001 | Client Services, floor 5 | VPN says certificate error. The gateway is vpn-gp.corplabs.internal and I've been on leave for two months. | AUTO_FIX | reset_vpn_profile | routine |  |
| H-002 | Operations, floor 4 | GlobalProtect shows vpn.corplabs.internal as my gateway and can't connect. | SELF_SERVE or AUTO_FIX | reset_vpn_profile | hard | Legacy portal entry. |
| H-003 | Risk, floor 6 | VPN still fails. Gateway is right, my cert is valid and I synced Okta Verify. | ESCALATE | NET-VPN | routine |  |
| H-004 | Compliance, floor 3 | VPN rejects me with no error, and I noticed the clock in Okta Verify is a few minutes off. | SELF_SERVE | any | hard |  |
| H-005 (tiny) | Operations, floor 3 | Nobody on floor 4 can print since this morning. | AUTO_FIX | restart_print_spooler | routine |  |
| H-006 (tiny) | Risk, floor 6 | The spooler was restarted 20 minutes ago but floor 6 still can't print. | ESCALATE | SD-PRINT | routine |  |
| H-007 (tiny) | Legal, floor 7 | One document is stuck in my own print queue. Colleagues can print fine. | SELF_SERVE | any | routine |  |
| H-008 | Client Services, floor 6 | Teams shows me as away while I'm working. I'm on the latest build and restarted it. | AUTO_FIX | clear_teams_cache | routine |  |
| H-009 | Legal, floor 7 | Clearing the Teams cache didn't hold, and several colleagues report the same thing today. | ESCALATE | APP-M365 | hard |  |
| H-010 | Finance, floor 5 | Outlook won't stop prompting. Okta session is fresh, Credential Manager was cleared yesterday, and my PST archive is 12 GB. | ESCALATE | APP-M365 | hard |  |
| H-011 | Operations, floor 4 | I need 7-Zip. It's in Company Portal but the Portal won't open. | AUTO_FIX | push_approved_software | routine |  |
| H-012 | Client Services, floor 5 | I have a client demo in one hour and need Tableau. My manager pre-approved it. | ESCALATE | DESK-SUPPORT | hard |  |
| H-013 | Operations, floor 3 | Please add me to the Legal-RW group. | ESCALATE | any | hard | Access requests are escalated. |
| H-014 | Compliance, floor 3 | My laptop is slow and the disk is 97% full. OneDrive seems to store everything locally. | AUTO_FIX | enable_onedrive_files_on_demand | routine |  |
| H-015 | Client Services, floor 6 | My ThinkPad got slow after I added some browser toolbars. Lots of apps start with Windows now. | SELF_SERVE | any | routine |  |
| H-016 | Finance, floor 5 | OneDrive fails only on Q3_Budget#v2.xlsx. Everything else syncs. | SELF_SERVE | any | routine |  |
| H-017 | Legal, floor 7 | All of Legal can't reach the path on FS-CORP-02, and it's Thursday morning. | ESCALATE | SD-FILES | routine |  |
| H-018 | Legal, floor 7 | I can't reach the Legal drive from home. I haven't connected to the VPN yet. | SELF_SERVE | any | routine |  |
| H-019 | Risk, floor 6 | My dock's keyboard and mouse are dead. Device Manager shows nothing, even after reseating the cable and updating firmware. | ESCALATE | DESK-HARDWARE | routine |  |
| H-020 (tiny) | Operations, floor 4, **2 lockouts** | Unlock my account please, it's urgent. | ESCALATE | SEC-INCIDENT | records | 2 lockouts in 24 hours in the records. |
| H-021 | Risk, floor 6, **1 lockouts** | I'm locked out. I forgot my password over the weekend. | AUTO_FIX or SELF_SERVE | unlock_ad_account | records | Only 1 lockout in the records, so routine. |
| H-022 | Legal, floor 7, **CalDigit TS3+** | My external display goes black every time my laptop wakes from sleep. | ESCALATE | DESK-HARDWARE | records | Legacy CalDigit dock in the records. |
| H-023 | Finance, floor 5, **in Fin-Users** | I can't open the Finance share since the group changes in June. | ESCALATE | SD-FILES | records | Still in the deprecated Fin-Users group in the records. |
| H-024 | Client Services, floor 4, **image 2026-03** | Wi-Fi keeps dropping on my laptop. | AUTO_FIX | push_wifi_driver_update | records | Device image is pre-2026-05 in the records. |
| H-025 (tiny) | Client Services, floor 5 | What's a good way to learn Italian before my holiday? | OUT_OF_SCOPE | any | routine |  |
