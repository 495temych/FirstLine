"""Tool JSON schemas Claude may call. Execution lives in tools.py (REGISTRY)."""

# Tools Claude may call for AUTO_FIX paths
TOOLS: list[dict] = [
    {
        "name": "reset_vpn_profile",
        "description": (
            "Reset a user's GlobalProtect VPN profile by running reset-vpn-profile.ps1. "
            "Regenerates the SCEP certificate. Use when the gateway address is correct but "
            "the cert may be expired or stale. Safe and reversible."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "AD username; use 'current.user' if not stated in the query"},
            },
            "required": ["username"],
        },
    },
    {
        "name": "restart_print_spooler",
        "description": (
            "Restart the Print Spooler service on PRINT01.limmatica.corp. "
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
            "Remove stale MicrosoftOffice16_Data:* entries from Windows Credential Manager "
            "for a user. Use when Outlook loops on credential prompts and the Okta session "
            "is known to be fresh. Reversible — user re-authenticates on next Outlook launch."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "AD username; use 'current.user' if not stated in the query"},
            },
            "required": ["username"],
        },
    },
    {
        "name": "clear_teams_cache",
        "description": (
            "Clear the Teams LocalCache folder for a user. Use when Teams presence is stuck "
            "or the client is unresponsive and the user is on an up-to-date build. "
            "Reversible — Teams rebuilds its cache on next launch."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "AD username; use 'current.user' if not stated in the query"},
            },
            "required": ["username"],
        },
    },
    {
        "name": "push_wifi_driver_update",
        "description": (
            "Push the 2026-05 Intel Wi-Fi driver update to a single device via Intune. "
            "Use when a ThinkPad T14 has persistent Wi-Fi drops and the driver is pre-2026-05. "
            "Does not modify other device config."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device_id": {
                    "type": "string",
                    "description": "Intune device ID or hostname; use 'current.device' if not stated in the query",
                },
            },
            "required": ["device_id"],
        },
    },
    {
        "name": "remap_drives",
        "description": (
            "Re-run map-drives.bat from \\\\IT-TOOLS\\Scripts for a user to restore mapped "
            "network drives. Use when drives are missing after VPN reconnect or login. "
            "Pulls correct paths per department from central config."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "AD username; use 'current.user' if not stated in the query"},
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
            "Use only after verifying user identity via Okta Verify push and confirming "
            "this is a standard lockout — NOT when 2+ lockouts occurred within 24 h "
            "(that requires escalation to SEC-INCIDENT)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "AD username to unlock; use 'current.user' if not stated in the query"},
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
                "username": {"type": "string", "description": "AD username; use 'current.user' if not stated in the query"},
            },
            "required": ["username"],
        },
    },
    {
        "name": "push_approved_software",
        "description": (
            "Push a Company Portal approved software title to a user's device via Intune "
            "'Required' assignment. Use when the software is confirmed to be in the approved "
            "catalog (KB-0112) and the user cannot install via the portal UI. "
            "Install completes within ~15 min on next policy sync."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "AD username; use 'current.user' if not stated in the query"},
                "software_name": {"type": "string", "description": "Exact software name from Company Portal catalog (e.g. 'Zoom', 'Visual Studio Code')"},
            },
            "required": ["username", "software_name"],
        },
    },
    {
        "name": "create_escalation_ticket",
        "description": (
            "Open a ServiceNow escalation ticket when the issue cannot be resolved at the "
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
                        "ServiceNow queue to route to (e.g. NET-VPN, M365-PROFILE, "
                        "SEC-INCIDENT, INFRA-FS01, NET-PRINT, M365-SYNC, HW-REPLACE, "
                        "DESKTOP-URGENT, M365-TENANT, NET-WIFI)"
                    ),
                },
                "summary": {
                    "type": "string",
                    "description": "One-sentence diagnostic summary for the receiving technician",
                },
                "priority": {
                    "type": "string",
                    "enum": ["P3-Normal", "P2-High", "P1-Critical"],
                    "description": "Ticket priority based on business impact and urgency",
                },
            },
            "required": ["queue", "summary"],
        },
    },
]
