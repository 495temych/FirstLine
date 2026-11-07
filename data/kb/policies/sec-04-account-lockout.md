# SEC-04: Account lockout

**Category:** Policy | **Owner team:** Security | **Last reviewed:** 2026-11-07

**§4.1 Lockout.** Five failed sign-ins within 15 minutes lock an account. It unlocks by itself after 30 minutes, or can be unlocked by hand.

**§4.2 Repeat lockouts.** Two or more lockouts in 24 hours are a possible compromise. A routine unlock is forbidden. The ticket must go to `SEC-INCIDENT`, whatever earlier tickets did.

**§4.3 Identity.** Before any unlock, confirm the person with an Okta Verify push.
