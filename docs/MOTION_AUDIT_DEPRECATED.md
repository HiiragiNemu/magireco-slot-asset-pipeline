# Motion Audit Deprecation Notice

The `motion-audit` output is not a reliable static-frame classifier and must not
be used to decide whether a video is useful, whether it should be merged, or
whether it contains meaningful motion.

The old implementation sampled 64x64 grayscale frames and used mean absolute
pixel difference thresholds. That measurement can misclassify blinking,
localized motion, slow camera movement, long ordinary videos, and animated
effects. The folders named `low_motion`, `short_static`, and `static_like` are
diagnostic buckets only. They are not semantic classifications.

Authoritative downstream work now uses:

1. `EventCn.bin` event records for animation-to-sound bindings.
2. GDB event -> Z2D -> DGM -> native CRI mappings for physical video sources.
3. Sound request hashes for request id, SMZ media, and matching OGG resources.
4. Exact `cap*` Z2D dialogue timing for subtitle generation.
5. Manual review only where event labels remain ambiguous.

Existing RAMDISK motion-audit folders are retained to avoid deleting user data,
but they are deprecated and excluded from merge, audio, and subtitle decisions.
