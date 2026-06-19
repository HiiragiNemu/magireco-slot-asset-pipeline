# Corrected clean-story production update — 2026-06-20

## ac4903 complete family

Official runtime captures resolved `ac4903_009` through `ac4903_013`. Each capture provides
the exact native video set, three official sound calls, and one complete Touka subtitle.
The clean 416x232 editions use only their c011-c015 main animation and matching LP from the
verified 8000 ms boundary. The separate black-matte
`ac4903_at_magius_monitor_ef_01` AT sparkle layer is excluded from audience editions.
`ac4903_013` also launches the unrelated `ac9901_op` slot opening at 9070 ms; that opening is
excluded as well.

The five exact runtime durations are 8654, 8958, 9661, 9381, and 11610 ms. The first four
end with numeric runtime resource `551`, previously mapped through `sound_id_records.csv` to
the exact 6194 ms OGG. The fifth ends with the 6969 ms official development jingle. No CRI
index is inferred from an event suffix.

The complete ten-event family passes 10/10 QA. Every subtitle/no-subtitle pair has identical
audio essence and non-silent 48 kHz stereo audio. Boundary frame inspection confirms seamless
LP transitions and verifies that neither the AT sparkle layer nor `ac9901_op` appears. The
direct-stream-copy long edition is 416x232 at 30 fps, 78354 ms, and has 14 subtitle cues.

After this batch, production manifests v18 contain 926 events, of which 540 are render-ready
and 644 have resolved video composition. The 67 reviewed audience-component exclusions remain
separate from clean story output.
