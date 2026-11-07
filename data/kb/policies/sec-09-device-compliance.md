# SEC-09: Device compliance

**Category:** Policy | **Owner team:** Security | **Last reviewed:** 2026-11-07

**§9.1 Managed devices.** A device that reaches company data must be enrolled in Intune, encrypted with BitLocker on Windows, and on a supported OS patch level.

**§9.2 Recovery keys.** BitLocker recovery keys must be escrowed to the management service. Only a technician may rotate or read one, after confirming the person.

**§9.3 Noncompliant devices.** Conditional access may block a noncompliant device. The fix is to make the device compliant, never to exclude it from the policy.
