# Writer Ownership Inventory — Review Template

> **ARCHIVED / SUPERSEDED:** V1 writer ownership V2 tarafından devralınmaz. Bu tarihsel envanter
> yalnız geçmiş tasarım bağlamıdır ve operasyon talimatı değildir.

Status: offline template only. The real production inventory must be re-captured immediately before any approved cutover.

| Family | RC owner/state | Required cutover evidence |
|---|---|---|
| V1 API mutations | V1, unchanged | endpoint/process inventory and global fence proof |
| V1 collectors/workers | V1, unchanged | unit/process/lock inventory and final checkpoint |
| V1 timers/schedulers | V1, unchanged | installed/enabled/active inventory and mask proof |
| V1 manual/backfill/repair/one-shot commands | V1, unchanged | operator history, process inventory and fence proof |
| V1 media writers | V1, unchanged | volume writer inventory and media high-water checksum |
| Accumulate provisioning outbox | Accumulate → V1 | oldest pending/failed row, emitted/applied watermark and target route |
| Accumulate SSO launch | Accumulate → V1 | fixed target map and current route checksum |
| V2 API | absent from production | no process, credential, route or connection |
| V2 writers/timers | absent/non-runnable draft | no timer/cron/orchestrator; placeholder cannot run |
| V2 TikTok activation/collection | disabled | all four gates off, no secret, sentinel or provider egress |

Inventory must include host, unit/command, executable checksum, database identity, credential role, lock/checkpoint namespace, media path, current state and accountable operator. Unknown entries are a hard stop.
