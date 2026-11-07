"""Tool JSON schemas Claude may call. Execution lives in tools.py (REGISTRY)."""

ROUTINE = "routine"  # a person may confirm this for their own account or device
SENSITIVE = "sensitive"  # touches access, security or shared systems: a technician only

# Tools Claude may call for AUTO_FIX paths
TOOLS: list[dict] = [
    {
        "name": "reset_vpn_profile",
        "description": (
            "Reset a user's GlobalProtect VPN profile by running "
            "reset-vpn-profile.ps1. "
            "Regenerates the SCEP certificate. Use when the gateway address is correct "
            "but "
            "the cert may be expired or stale. Safe and reversible."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "description": "AD username; use 'current.user' if not stated in "
                    "the query",
                },
            },
            "required": ["username"],
        },
    },
    {
        "name": "restart_print_spooler",
        "description": (
            "Restart the Print Spooler service on PS-PRINT01.corplabs.internal. "
            "Use only for floor-wide failures after the nightly PaperCut sync job — "
            "not for single-user print queue issues."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "floor": {
                    "type": "string",
                    "description": "Affected floor identifier (e.g. 'floor 3')",
                },
            },
            "required": [],
        },
    },
    {
        "name": "clear_credential_manager",
        "description": (
            "Remove stale MicrosoftOffice16_Data:* entries from Windows Credential "
            "Manager "
            "for a user. Use when Outlook loops on credential prompts and the Okta "
            "session "
            "is known to be fresh. Reversible — user re-authenticates on next Outlook "
            "launch."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "description": "AD username; use 'current.user' if not stated in "
                    "the query",
                },
            },
            "required": ["username"],
        },
    },
    {
        "name": "clear_teams_cache",
        "description": (
            "Clear the Teams LocalCache folder for a user. Use when Teams presence is "
            "stuck "
            "or the client is unresponsive and the user is on an up-to-date build. "
            "Reversible — Teams rebuilds its cache on next launch."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "description": "AD username; use 'current.user' if not stated in "
                    "the query",
                },
            },
            "required": ["username"],
        },
    },
    {
        "name": "push_wifi_driver_update",
        "description": (
            "Push the 2026-05 Intel Wi-Fi driver update to a single device via Intune. "
            "Use when a ThinkPad T14 has persistent Wi-Fi drops and the driver is "
            "pre-2026-05. "
            "Does not modify other device config."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Intune device ID or hostname; use 'current.device' "
                    "if not stated in the query",
                },
            },
            "required": ["device_id"],
        },
    },
    {
        "name": "remap_drives",
        "description": (
            "Re-run map-drives.bat from \\\\IT-TOOLS\\Scripts for a user to restore "
            "mapped "
            "network drives. Use when drives are missing after VPN reconnect or login. "
            "Pulls correct paths per department from central config."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "description": "AD username; use 'current.user' if not stated in "
                    "the query",
                },
                "department": {
                    "type": "string",
                    "description": "User's department (e.g. Finance, Legal)",
                },
            },
            "required": ["username"],
        },
    },
    {
        "name": "unlock_ad_account",
        "description": (
            "Unlock a locked-out Active Directory account. "
            "Use only after verifying user identity via Okta Verify push and "
            "confirming "
            "this is a standard lockout — NOT when 2+ lockouts occurred within 24 h "
            "(that requires escalation to SEC-INCIDENT)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "description": "AD username to unlock; use 'current.user' if not "
                    "stated in the query",
                },
            },
            "required": ["username"],
        },
    },
    {
        "name": "enable_onedrive_files_on_demand",
        "description": (
            "Enable OneDrive Files On-Demand for a user via Intune policy to stop full "
            "local sync from filling the 256 GB SSD. Use when disk space is low and "
            "OneDrive full sync is the confirmed cause."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "description": "AD username; use 'current.user' if not stated in "
                    "the query",
                },
            },
            "required": ["username"],
        },
    },
    {
        "name": "push_approved_software",
        "description": (
            "Push a Company Portal approved software title to a user's device via "
            "Intune "
            "'Required' assignment. Use when the software is confirmed to be in the "
            "approved "
            "catalog (KB-0112) and the user cannot install via the portal UI. "
            "Install completes within ~15 min on next policy sync."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "description": "AD username; use 'current.user' if not stated in "
                    "the query",
                },
                "software_name": {
                    "type": "string",
                    "description": "Exact software name from Company Portal catalog "
                    "(e.g. 'Zoom', 'Visual Studio Code')",
                },
            },
            "required": ["username", "software_name"],
        },
    },
    {
        "name": "reinstall_print_driver",
        "description": (
            "Reinstall the approved HP Universal Print Driver on PS-PRINT01 for one "
            "shared queue. Use when jobs fail with a driver error across a queue. "
            "Queues drop briefly, so it affects everyone using that queue."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "queue": {
                    "type": "string",
                    "description": "Shared print queue name",
                },
            },
            "required": ["queue"],
        },
    },
    {
        "name": "reset_mobile_mail_profile",
        "description": (
            "Remove a stale Outlook mobile partnership for a user so the phone can "
            "sync again. Use when desktop Outlook syncs but Outlook on the phone does "
            "not, and the device is compliant. Reversible: the user signs in again."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "description": "AD username; use 'current.user' if not stated in "
                    "the query",
                },
            },
            "required": ["username"],
        },
    },
    {
        "name": "push_wifi_profile",
        "description": (
            "Push the current corporate Wi-Fi profile and certificate to a device via "
            "Intune. Use when one device can't join CORPLABS-CORP and its profile or "
            "certificate is out of date."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Intune device ID or hostname; use 'current.device' "
                    "if not stated in the query",
                },
            },
            "required": ["device_id"],
        },
    },
    {
        "name": "add_user_to_share_group",
        "description": (
            "Add a user to the AD security group behind a shared drive. Use only when "
            "the data owner or manager has approved it on the ticket, under SEC-11."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {
                    "type": "string",
                    "description": "AD username; use 'current.user' if not stated in "
                    "the query",
                },
                "group": {
                    "type": "string",
                    "description": "AD security group that grants the access",
                },
            },
            "required": ["username", "group"],
        },
    },
    {
        "name": "force_intune_sync",
        "description": (
            "Force an Intune sync and a new compliance evaluation for one device. Use "
            "when a device is out of date or reports noncompliant after its settings "
            "changed. Changes nothing else on the device."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Intune device ID or hostname; use 'current.device' "
                    "if not stated in the query",
                },
            },
            "required": ["device_id"],
        },
    },
    {
        "name": "escrow_bitlocker_key",
        "description": (
            "Back up a device's BitLocker recovery key to the management service. Use "
            "when a device reports noncompliant because its key isn't escrowed, and "
            "TPM and encryption are healthy."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Intune device ID or hostname; use 'current.device' "
                    "if not stated in the query",
                },
            },
            "required": ["device_id"],
        },
    },
    {
        "name": "clean_temp_files",
        "description": (
            "Clear temporary files on one device. Use when a laptop is slow and free "
            "disk space is low. Doesn't touch user documents."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Intune device ID or hostname; use 'current.device' "
                    "if not stated in the query",
                },
            },
            "required": ["device_id"],
        },
    },
    {
        "name": "create_escalation_ticket",
        "description": (
            "Open a ServiceNow escalation ticket when the issue cannot be resolved at "
            "the "
            "desktop support level. Call this whenever the ESCALATE path is chosen — "
            "it captures the queue, diagnostic summary, and priority so the receiving "
            "technician has the context they need."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "queue": {
                    "type": "string",
                    "description": (
                        "ServiceNow queue to route to: SD-PRINT, SD-FILES, SD-DEVICE, "
                        "DESK-SUPPORT, DESK-HARDWARE, NET-VPN, NET-WIFI, NET-DNS, "
                        "IAM-ACCESS, APP-M365, APP-SUPPORT, SEC-POLICY or SEC-INCIDENT"
                    ),
                },
                "summary": {
                    "type": "string",
                    "description": "One-sentence diagnostic summary for the receiving "
                    "technician",
                },
                "priority": {
                    "type": "string",
                    "enum": ["P3-Normal", "P2-High", "P1-Critical"],
                    "description": "Ticket priority based on business impact and "
                    "urgency",
                },
            },
            "required": ["queue", "summary"],
        },
    },
]

# Who owns each tool, how risky it is, and the issue families it can fix.
# DRF and SML have no tool, because the network and identity teams own those fixes.
TOOL_POLICY: dict[str, dict] = {
    "reset_vpn_profile": {
        "tier": ROUTINE,
        "owner": "service_desk",
        "families": ["VDA"],
    },
    "restart_print_spooler": {
        "tier": SENSITIVE,
        "owner": "service_desk",
        "families": ["PDQ"],
    },
    "reinstall_print_driver": {
        "tier": SENSITIVE,
        "owner": "service_desk",
        "families": ["PDQ"],
    },
    "clear_credential_manager": {
        "tier": ROUTINE,
        "owner": "service_desk",
        "families": ["OES"],
    },
    "reset_mobile_mail_profile": {
        "tier": ROUTINE,
        "owner": "service_desk",
        "families": ["OES"],
    },
    "clear_teams_cache": {"tier": ROUTINE, "owner": "service_desk", "families": []},
    "push_wifi_driver_update": {
        "tier": ROUTINE,
        "owner": "service_desk",
        "families": ["WCI"],
    },
    "push_wifi_profile": {
        "tier": ROUTINE,
        "owner": "service_desk",
        "families": ["WCI"],
    },
    "remap_drives": {"tier": ROUTINE, "owner": "service_desk", "families": ["SDA"]},
    "add_user_to_share_group": {
        "tier": SENSITIVE,
        "owner": "service_desk",
        "families": ["SDA"],
    },
    "unlock_ad_account": {
        "tier": SENSITIVE,
        "owner": "service_desk",
        "families": ["ALP"],
    },
    "enable_onedrive_files_on_demand": {
        "tier": ROUTINE,
        "owner": "service_desk",
        "families": [],
    },
    "clean_temp_files": {"tier": ROUTINE, "owner": "service_desk", "families": ["LPD"]},
    "push_approved_software": {
        "tier": ROUTINE,
        "owner": "service_desk",
        "families": ["SIB"],
    },
    "force_intune_sync": {
        "tier": ROUTINE,
        "owner": "service_desk",
        "families": ["DCP", "SIB"],
    },
    "escrow_bitlocker_key": {
        "tier": SENSITIVE,
        "owner": "desktop_support",
        "families": ["EDE"],
    },
    "create_escalation_ticket": {
        "tier": ROUTINE,
        "owner": "service_desk",
        "families": [],
    },
}
