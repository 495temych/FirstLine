# Label review

Review the development labels in the app's Tickets tab. Turn on **Only labels to check** to see the four that need a decision first.

Check the held-out rows below against the knowledge base. Change anything you disagree with in `data/evals/`, then delete this file.

**Look at this first:** `H-002` (two accepted paths).

## Held-out

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
