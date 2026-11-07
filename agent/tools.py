import secrets
from collections.abc import Callable
from datetime import UTC, datetime


def _ok(action: str, detail: str) -> dict:
    return {
        "status": "success",
        "action": action,
        "detail": detail,
        "simulated": True,
        "timestamp": datetime.now(UTC).isoformat(),
    }


def reset_vpn_profile(username: str) -> dict:
    return _ok(
        "reset_vpn_profile",
        f"Ran \\\\IT-TOOLS\\Scripts\\reset-vpn-profile.ps1 for {username}. "
        "SCEP certificate regenerated (~90 s). Gateway confirmed as "
        "vpn-gp.corplabs.internal.",
    )


def restart_print_spooler(floor: str = "unknown") -> dict:
    return _ok(
        "restart_print_spooler",
        f"Print Spooler restarted on PS-PRINT01.corplabs.internal "
        f"(reported floor: {floor}). "
        "Queue cleared. PaperCut sync verified.",
    )


def clear_credential_manager(username: str) -> dict:
    return _ok(
        "clear_credential_manager",
        f"Removed MicrosoftOffice16_Data:* entries from Windows Credential Manager for "
        f"{username}. "
        "Outlook will prompt for re-auth on next launch.",
    )


def clear_teams_cache(username: str) -> dict:
    return _ok(
        "clear_teams_cache",
        f"Cleared %localappdata%\\Packages\\MSTeams_8wekyb3d8bbwe\\LocalCache for "
        f"{username}. "
        "Teams will rebuild cache on next launch.",
    )


def push_wifi_driver_update(device_id: str) -> dict:
    return _ok(
        "push_wifi_driver_update",
        f"Intel Wi-Fi driver update policy (2026-05 baseline) pushed to device "
        f"{device_id} via Intune. "
        "Update will apply on next policy sync (~15 min).",
    )


def remap_drives(username: str, department: str = "") -> dict:
    return _ok(
        "remap_drives",
        f"Executed \\\\IT-TOOLS\\Scripts\\map-drives.bat for {username} "
        f"(dept: {department or 'unspecified'}). Drive mappings restored from central "
        f"config.",
    )


def unlock_ad_account(username: str) -> dict:
    return _ok(
        "unlock_ad_account",
        f"Unlock-ADAccount executed for {username} on CORPLABS domain. "
        "Account active. Okta sync propagates within ~2 min.",
    )


def enable_onedrive_files_on_demand(username: str) -> dict:
    return _ok(
        "enable_onedrive_files_on_demand",
        f"OneDrive Files On-Demand enabled for {username} via Intune policy. "
        "Full local sync will stop accumulating after next OneDrive restart.",
    )


def push_approved_software(username: str, software_name: str) -> dict:
    return _ok(
        "push_approved_software",
        f"Intune 'Required' assignment created: {software_name} → {username}'s device. "
        "Install will trigger within 15 min on next policy sync. Logged in Intune "
        "under device compliance.",
    )


def reinstall_print_driver(queue: str) -> dict:
    return _ok(
        "reinstall_print_driver",
        f"Reinstalled the approved HP Universal Print Driver for {queue} on "
        "PS-PRINT01. Test page printed.",
    )


def reset_mobile_mail_profile(username: str) -> dict:
    return _ok(
        "reset_mobile_mail_profile",
        f"Removed the stale Outlook mobile partnership for {username}. "
        "The phone syncs again after the next sign-in.",
    )


def push_wifi_profile(device_id: str) -> dict:
    return _ok(
        "push_wifi_profile",
        f"Pushed the current CORPLABS-CORP profile and certificate to {device_id} "
        "via Intune. Applies on next policy sync (~15 min).",
    )


def add_user_to_share_group(username: str, group: str) -> dict:
    return _ok(
        "add_user_to_share_group",
        f"Added {username} to {group}. Access applies at next sign-in.",
    )


def force_intune_sync(device_id: str) -> dict:
    return _ok(
        "force_intune_sync",
        f"Forced an Intune sync and compliance evaluation for {device_id}.",
    )


def escrow_bitlocker_key(device_id: str) -> dict:
    return _ok(
        "escrow_bitlocker_key",
        f"Backed up the BitLocker recovery key for {device_id} to the management "
        "service.",
    )


def clean_temp_files(device_id: str) -> dict:
    return _ok(
        "clean_temp_files",
        f"Cleared temporary files on {device_id}. User documents were not touched.",
    )


def create_escalation_ticket(
    queue: str, summary: str, priority: str = "P3-Normal"
) -> dict:
    ticket_num = f"INC{secrets.randbelow(9000000) + 1000000}"
    result = _ok(
        "create_escalation_ticket",
        f"Ticket #{ticket_num} opened in {queue} (priority: {priority}). "
        f"On-call technician notified. SLA clock started.",
    )
    result["ticket_number"] = ticket_num
    result["queue"] = queue
    result["priority"] = priority
    return result


REGISTRY: dict[str, Callable[..., dict]] = {
    "reset_vpn_profile": reset_vpn_profile,
    "restart_print_spooler": restart_print_spooler,
    "clear_credential_manager": clear_credential_manager,
    "clear_teams_cache": clear_teams_cache,
    "push_wifi_driver_update": push_wifi_driver_update,
    "remap_drives": remap_drives,
    "unlock_ad_account": unlock_ad_account,
    "enable_onedrive_files_on_demand": enable_onedrive_files_on_demand,
    "push_approved_software": push_approved_software,
    "reinstall_print_driver": reinstall_print_driver,
    "reset_mobile_mail_profile": reset_mobile_mail_profile,
    "push_wifi_profile": push_wifi_profile,
    "add_user_to_share_group": add_user_to_share_group,
    "force_intune_sync": force_intune_sync,
    "escrow_bitlocker_key": escrow_bitlocker_key,
    "clean_temp_files": clean_temp_files,
    "create_escalation_ticket": create_escalation_ticket,
}


def dispatch(tool_name: str, tool_input: dict) -> dict:
    return REGISTRY[tool_name](**tool_input)
