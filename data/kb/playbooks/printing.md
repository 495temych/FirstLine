---
id: printing
title: Printing and print queues
family: PDQ
owner_team: service desk
last_reviewed: 2026-11-07
applications: [Print Spooler, Print Management Console, HP Universal Print Driver, PaperCut]
tools: [restart_print_spooler, reinstall_print_driver]
---

## Symptoms

Print jobs stuck on the print server. Print queue is stuck. Multiple users can't print. Printer shows offline. Jobs stay at 0% or keep spooling. Driver unavailable when printing to a shared queue on `PS-PRINT01`.

## Checks

1. Find out whether it's one person or a whole queue or floor. This decides the path.
2. `print-queue-status-check`: check the shared queue. Healthy: it's online and accepts new jobs.
3. `print-driver-version-check`: compare the installed driver with the approved HP Universal Print Driver. Healthy: the current approved driver.
4. `print-spooler-check`: check the Print Spooler and send a test job. Healthy: it's processed with no errors.

## Error codes

- `Driver unavailable`: the queue's driver package can't load.
- `Print jobs queued at 0%`: the spooler isn't processing the queue.
- `EventID 7011`: the Print Spooler service timed out.

## Known causes

- **Corrupt driver package.** The most common cause, usually after a driver update. Restarting the spooler alone won't hold.
- **Hung spooler.** The spooler hangs after the nightly PaperCut sync, so a whole queue stops with no driver error.
- **One stuck job.** Bad print data affects one person only.

## Fix

- Whole queue, no driver error: use `restart_print_spooler`. Don't ask people to restart anything locally.
- `Driver unavailable` across a queue: use `reinstall_print_driver`, then clear the stuck jobs.
- One person: they clear their local queue and add the printer again.

Both tools affect everyone on that queue, so a technician confirms them.

## When to escalate

Send it to `SD-PRINT` if the problem continues 15 minutes after the fix, or if the driver package won't install.
