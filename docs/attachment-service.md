# Attachment service contract

The attachment subsystem accepts structured events from explicitly configured
collectors. `TelegramEventCollector` normalizes Telegram Bot API message
dictionaries but does not own credentials or network polling. Callers register
downloaders by `(venue, account_id)` and control worker startup/shutdown through
`AttachmentDownloadManager.start()` and `stop()`.

## Invariants

- Message identity is `(venue, venue_id, venue_message_id)` and native reply
  resolution is scoped to all three coordinates.
- Message, attachment membership, and indexing intent survive reopen.
- Attachment metadata must reference an existing parent with matching venue
  coordinates when it shares a MessageStore database.
- Generated paths remain under the configured root. Caller-supplied external
  paths are rejected.
- Work is claimed with a durable attempt ID and lease. Only the owning attempt
  may publish its result; expired attempts are recoverable.
- Downloaders publish to attempt-specific temporary files. Completion requires
  a real file within the configured size limit, followed by atomic rename.
- New downloaders should accept a `max_bytes` keyword and abort transport when
  the bound is reached. Legacy two-argument implementations are supported but
  are only post-transfer checked and therefore are not qualified for untrusted
  remote content.
- Missing completed files, expired work, and orphan partials are reconciled.

## Deliberate exclusions

Thumbnail generation and content-based MIME inspection are not implemented.
Retention is explicit deletion through `AttachmentStore.delete`; no automatic
age-based policy is enabled. Account credentials, Telegram polling, audience
authorization, disk quotas, and backup policy belong to the integrating
service and must be configured there before production use.
