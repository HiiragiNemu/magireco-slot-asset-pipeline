import json
from pathlib import Path
import tempfile
import unittest

from tools.frida_runtime_probe.resolve_ac0911_exhaustive_authority import (
    EDITORIAL_ORDER,
    EVENTS,
    PRESENTATION_FRAMES,
    ROUTES,
    load_v75_segments,
    runtime_sound_ids,
    visible_motion_frames,
)


class ResolveAc0911ExhaustiveAuthorityTest(unittest.TestCase):
    def test_route_universe_covers_all_events(self):
        self.assertEqual(len(ROUTES), 14)
        self.assertEqual(sorted({event for route in ROUTES for event in route}), EVENTS)

    def test_editorial_order_is_exact_duplicate_free_cover(self):
        self.assertEqual(len(EDITORIAL_ORDER), 17)
        self.assertEqual(len(set(EDITORIAL_ORDER)), 17)
        self.assertEqual(sorted(EDITORIAL_ORDER), EVENTS)
        self.assertEqual(sum(PRESENTATION_FRAMES[event] for event in EDITORIAL_ORDER), 5515)

    def test_visible_motion_frames_uses_z2d_key_when_longer_than_cut(self):
        event = {
            "scenes": [{
                "cuts": [{
                    "cut_end_frame": 99,
                    "nodes": [{
                        "motions": [{
                            "is_z2d_motion": True,
                            "keys": [{"floats": [18, 497, 18, 497]}],
                        }],
                        "children": [],
                    }],
                }],
            }],
        }
        self.assertEqual(visible_motion_frames(event), 498)

    def test_visible_motion_frames_ignores_parallel_empty_cut(self):
        event = {
            "scenes": [
                {"cuts": [{"cut_end_frame": 99, "nodes": []}]},
                {"cuts": [{"cut_end_frame": 77, "nodes": [{
                    "motions": [{
                        "is_z2d_motion": True,
                        "keys": [{"floats": [0, 77]}],
                    }],
                    "children": [],
                }]}]},
            ],
        }
        self.assertEqual(visible_motion_frames(event), 78)

    def test_runtime_sound_ids_reads_nested_forced_sound_payload(self):
        rows = [
            {"message": {"payload": {
                "kind": "forced_sound_play",
                "forced_event_label": "ac0911_014",
                "code_name": "0552 CZ确定",
            }}},
            {"message": {"payload": {"kind": "animation_state_sample"}}},
        ]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "capture.jsonl"
            path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
            observed = runtime_sound_ids(path)
        self.assertEqual(observed["ac0911_014"], [552])

    def test_v75_segment_uses_route_local_not_legacy_master_coordinates(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            route = root / "ac0911" / "routes" / "dirinfo-row-001"
            video = route / "video"
            video.mkdir(parents=True)
            for edition in ("none", "ja", "zh"):
                (video / f"clip__{edition}.mp4").write_bytes(b"fixture")
            manifest = {
                "status": "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED",
                "timeline": [{
                    "event": "ac0911_004",
                    "start_frame": 628,
                    "end_frame": 853,
                    "source_start_frame": 808,
                    "source_end_frame": 1033,
                }],
                "media": {
                    edition: {"path": f"routes/dirinfo-row-001/video/clip__{edition}.mp4"}
                    for edition in ("none", "ja", "zh")
                },
            }
            (route / "ROUTE_MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
            observed = load_v75_segments(root)["ac0911_004"]
        self.assertEqual(observed["route_media_start_frame"], 628)
        self.assertEqual(observed["route_media_end_frame_exclusive"], 853)
        self.assertEqual(observed["legacy_master_start_frame"], 808)


if __name__ == "__main__":
    unittest.main()
