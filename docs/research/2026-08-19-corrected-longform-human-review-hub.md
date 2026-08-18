# Corrected long-form human review hub

The 2026-08-17 flat release remains immutable evidence. It mixed exact event
archives with audience products, so it is no longer the current human entry.

The corrected release has two visible queues:

- `00_APPROVED_CURRENT`: exact owner-approved files whose later composition,
  quarantine, and sound-bus evidence has not withdrawn the product claim.
- `01_TO_REVIEW`: currently limited to language-neutral material archives.
  Unapproved single-event story/routes/effects remain index-only until a
  family long-form composition is proven.

Audience queues remain language-first (`ZH`, `JP`, `NONE`) and then `story`,
`routes`, or `gameplay_effect`. Silent material uses one flat `MATERIAL` lane
and never receives a `__none` suffix.

No source media are moved, deleted, transcoded, or physically copied. The
release requires same-volume NTFS hardlinks and validates media parameters and
source/target file identity. Historical playback approval does not override
later fail-closed evidence: the legacy ac1102 natural-chapter claim and the
ac1103 strict-no-BGM claim remain index-only.

Published checkpoint:

- release: `D:\magia\MyProducts\casino\magireco_corrected_research_20260612\manual_review_hub_v2_flat\releases\longform_authority_corrected_v3_20260819`
- single visible junction: `D:\magia\MyProducts\casino\magireco_corrected_research_20260612\manual_review_hub_v2_flat\CURRENT_REVIEW`
- current exact owner-approved media: 27
- material files awaiting playback: 62
- active hardlinks: 89; index-only records: 318
