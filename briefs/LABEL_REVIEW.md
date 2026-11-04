# Label review

Check each row against the knowledge base. Change anything you disagree with in `data/evals/`, then delete this file.

**Look at these first:** `T-001` (the KB lists several causes, so AUTO_FIX alone may be too strict), `T-017` and `H-002` (two accepted paths), `T-018` (known floor 5 congestion, so ticket or just logged?), `T-006` (an existing label, made `records`).

## Development

| Id | Requester | Ticket | Answer | Tool or queue | Difficulty | Note |
|---|---|---|---|---|---|---|
| T-001 | Client Services, floor 5 | My VPN keeps disconnecting | AUTO_FIX | reset_vpn_profile | hard | Existing label. The KB lists several causes, so review it. |
| T-002 | Operations, floor 4 | Teams shows me as offline to everyone | AUTO_FIX | clear_teams_cache | routine |  |
| T-003 (tiny) | Client Services, floor 5 | Floor 5 print queue is stuck | AUTO_FIX | restart_print_spooler | routine |  |
| T-004 | Risk, floor 6 | VPN cert error, gateway confirmed correct, offline for a month | AUTO_FIX | reset_vpn_profile | routine |  |
| T-005 | Operations, floor 3 | Need Zoom installed, no admin rights, it's in Company Portal | AUTO_FIX | push_approved_software | routine |  |
| T-006 | Client Services, floor 4, **2 lockouts** | I'm locked out of my account | ESCALATE | SEC-INCIDENT | records | 2 lockouts in 24 hours in the records. |
| T-007 (tiny) | Compliance, floor 3 | Locked out twice already today | ESCALATE | SEC-INCIDENT | routine |  |
| T-008 | Finance, floor 5 | My OneDrive has been stuck syncing for two days | ESCALATE | M365-SYNC | hard |  |
| T-009 | Client Services, floor 6 | My external monitor isn't detected when docked | SELF_SERVE or ESCALATE | any | hard | The KB supports either path. |
| T-010 (tiny) | Legal, floor 7 | What's the weather like today? | OUT_OF_SCOPE | any | routine |  |
| T-011 | Compliance, floor 3 | Outlook keeps asking for my password, and my Okta session was renewed yesterday. | AUTO_FIX | clear_credential_manager | routine |  |
| T-012 | Legal, floor 7 | Outlook has prompted me to sign in all morning. My last full Okta login was about three months ago. | SELF_SERVE | any | hard | Expected 90-day expiry: the user re-authenticates. |
| T-013 (tiny) | Risk, floor 6 | My laptop is crawling right now and Task Manager shows CSFalconService using most of the CPU. | SELF_SERVE | any | routine | Expected scan: tell the user it clears in about 20 minutes. |
| T-014 | Operations, floor 4 | My disk is almost full and OneDrive seems to keep every file on the laptop. | AUTO_FIX | enable_onedrive_files_on_demand | routine |  |
| T-015 | Finance, floor 5 | My mapped drives have disappeared. VPN is connected and everything else works. | AUTO_FIX | remap_drives | routine |  |
| T-016 | Finance, floor 5 | The Finance share on FS01 is down for our whole team and it's Wednesday afternoon. | ESCALATE | INFRA-FS01 | routine | Outside the Tuesday maintenance window. |
| T-017 | Client Services, floor 5 | Can I get Photoshop? It isn't in Company Portal. | SELF_SERVE or ESCALATE | any | hard | Needs SR-SOFTWARE with manager approval. |
| T-018 | Client Services, floor 6 | Wi-Fi keeps dropping for several of us near the open-plan area on floor 5. | ESCALATE | NET-WIFI | routine | Known congestion: log it for tracking. |
| T-019 | Operations, floor 3 | Please give me local admin rights so I can install my own tools. | ESCALATE | any | hard | Access requests are escalated (SEC-07). |
| T-020 (tiny) | Operations, floor 3, **3 lockouts** | Locked out again, can you unlock me please? | ESCALATE | SEC-INCIDENT | records | 3 lockouts in 24 hours in the records. |
| T-021 | Risk, floor 6, **1 lockouts** | My account got locked after I mistyped my new password following the rotation reminder. | AUTO_FIX or SELF_SERVE | unlock_ad_account | records | Only 1 lockout in the records, so routine. |
| T-022 | Compliance, floor 3, **image 2025-11** | My Wi-Fi keeps dropping at my desk. Nobody else seems affected. | AUTO_FIX | push_wifi_driver_update | records | Device image is pre-2026-05 in the records. |
| T-023 | Client Services, floor 5, **3y old, battery 52%** | My laptop battery barely lasts an hour now. | ESCALATE | HW-REPLACE | records | 3-year-old device with 52% battery health in the records. |
| T-024 | Legal, floor 7 | My monitor says no signal since someone swapped it at my desk. The dock cable clicks in fine. | SELF_SERVE | any | hard | Input source should be USB-C. |
| T-025 | Legal, floor 7 | Can you recommend a good restaurant near Sihlquai for a team lunch? | OUT_OF_SCOPE | any | routine |  |

## Held-out

| Id | Requester | Ticket | Answer | Tool or queue | Difficulty | Note |
|---|---|---|---|---|---|---|
| H-001 | Client Services, floor 5 | VPN says certificate error. The gateway is vpn-gp.limmatica.corp and I've been on leave for two months. | AUTO_FIX | reset_vpn_profile | routine |  |
| H-002 | Operations, floor 4 | GlobalProtect shows vpn.limmatica.corp as my gateway and can't connect. | SELF_SERVE or AUTO_FIX | reset_vpn_profile | hard | Legacy portal entry. |
| H-003 | Risk, floor 6 | VPN still fails. Gateway is right, my cert is valid and I synced Okta Verify. | ESCALATE | NET-VPN | routine |  |
| H-004 | Compliance, floor 3 | VPN rejects me with no error, and I noticed the clock in Okta Verify is a few minutes off. | SELF_SERVE | any | hard |  |
| H-005 (tiny) | Operations, floor 3 | Nobody on floor 4 can print since this morning. | AUTO_FIX | restart_print_spooler | routine |  |
| H-006 (tiny) | Risk, floor 6 | The spooler was restarted 20 minutes ago but floor 6 still can't print. | ESCALATE | NET-PRINT | routine |  |
| H-007 (tiny) | Legal, floor 7 | One document is stuck in my own print queue. Colleagues can print fine. | SELF_SERVE | any | routine |  |
| H-008 | Client Services, floor 6 | Teams shows me as away while I'm working. I'm on the latest build and restarted it. | AUTO_FIX | clear_teams_cache | routine |  |
| H-009 | Legal, floor 7 | Clearing the Teams cache didn't hold, and several colleagues report the same thing today. | ESCALATE | M365-TENANT | hard |  |
| H-010 | Finance, floor 5 | Outlook won't stop prompting. Okta session is fresh, Credential Manager was cleared yesterday, and my PST archive is 12 GB. | ESCALATE | M365-PROFILE | hard |  |
| H-011 | Operations, floor 4 | I need 7-Zip. It's in Company Portal but the Portal won't open. | AUTO_FIX | push_approved_software | routine |  |
| H-012 | Client Services, floor 5 | I have a client demo in one hour and need Tableau. My manager pre-approved it. | ESCALATE | DESKTOP-URGENT | hard |  |
| H-013 | Operations, floor 3 | Please add me to the Legal-RW group. | ESCALATE | any | hard | Access requests are escalated. |
| H-014 | Compliance, floor 3 | My laptop is slow and the disk is 97% full. OneDrive seems to store everything locally. | AUTO_FIX | enable_onedrive_files_on_demand | routine |  |
| H-015 | Client Services, floor 6 | My ThinkPad got slow after I added some browser toolbars. Lots of apps start with Windows now. | SELF_SERVE | any | routine |  |
| H-016 | Finance, floor 5 | OneDrive fails only on Q3_Budget#v2.xlsx. Everything else syncs. | SELF_SERVE | any | routine |  |
| H-017 | Legal, floor 7 | All of Legal can't reach the path on FS01, and it's Thursday morning. | ESCALATE | INFRA-FS01 | routine |  |
| H-018 | Legal, floor 7 | I can't reach the Legal drive from home. I haven't connected to the VPN yet. | SELF_SERVE | any | routine |  |
| H-019 | Risk, floor 6 | My dock's keyboard and mouse are dead. Device Manager shows nothing, even after reseating the cable and updating firmware. | ESCALATE | HW-REPLACE | routine |  |
| H-020 (tiny) | Operations, floor 4, **2 lockouts** | Unlock my account please, it's urgent. | ESCALATE | SEC-INCIDENT | records | 2 lockouts in 24 hours in the records. |
| H-021 | Risk, floor 6, **1 lockouts** | I'm locked out. I forgot my password over the weekend. | AUTO_FIX or SELF_SERVE | unlock_ad_account | records | Only 1 lockout in the records, so routine. |
| H-022 | Legal, floor 7, **CalDigit TS3+** | My external display goes black every time my laptop wakes from sleep. | ESCALATE | HW-REPLACE | records | Legacy CalDigit dock in the records. |
| H-023 | Finance, floor 5, **in Fin-Users** | I can't open the Finance share since the group changes in June. | ESCALATE | INFRA-FS01 | records | Still in the deprecated Fin-Users group in the records. |
| H-024 | Client Services, floor 4, **image 2026-03** | Wi-Fi keeps dropping on my laptop. | AUTO_FIX | push_wifi_driver_update | records | Device image is pre-2026-05 in the records. |
| H-025 (tiny) | Client Services, floor 5 | What's a good way to learn Italian before my holiday? | OUT_OF_SCOPE | any | routine |  |
