---
id: dns
title: Internal DNS resolution
family: DRF
owner_team: network
last_reviewed: 2026-11-07
applications: [Internal DNS, internal services]
tools: []
---

## Symptoms

Internal hostname fails to resolve. Internal DNS names intermittently fail. NXDOMAIN or SERVFAIL for an internal host. An application can't resolve a host. A name returns an old IP address after a migration. One subnet can't resolve a name that works elsewhere.

## Checks

1. `dns-lookup-check`: query the name against the corporate resolver and the authoritative server. Healthy: both return the same current address.
2. `dns-zone-record-check`: the network team inspects the zone record, TTL and change history. Healthy: the record is current, with the expected TTL.
3. `dns-forwarder-cache-check`: the network team reviews forwarding and cache. Healthy: the zone is forwarded correctly and answers are fresh.
4. Note the client subnet, the name and the time. Failures on one subnet point to one resolver.

## Error codes

- `NXDOMAIN`: the resolver says the name doesn't exist.
- `SERVFAIL`: the resolver couldn't get an answer.
- `DNS query timed out`: no answer arrived in time.

## Known causes

- **Stale resolver cache.** The most common cause. A record changed, but a resolver keeps serving old data, sometimes for a long TTL.
- **Stale zone record.** The record still points to a retired address.
- **Broken conditional forwarder.** One resolver sends the internal zone to the wrong place, so only some subnets fail.

## Fix

There's no L1 fix, because resolvers and zones belong to the network team. Don't ask people to change their DNS settings. Flushing a laptop's own cache only helps if the resolver is already correct.

## When to escalate

Send it to `NET-DNS` with the hostname, the error, the client subnet, whether it's intermittent, and any recent change or migration.
