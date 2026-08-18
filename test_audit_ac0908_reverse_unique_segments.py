import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parent
MODULE_PATH = ROOT / "tools" / "frida_runtime_probe" / "audit_ac0908_reverse_unique_segments.py"
SPEC = importlib.util.spec_from_file_location("audit_ac0908_reverse_unique_segments", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class Ac0908ReverseUniquenessTests(unittest.TestCase):
    def fixture(self):
        native, runtime, timeline, dirinfo = [], {}, [], []
        for index, event in enumerate(MODULE.EXPECTED_EVENTS, start=1):
            code = f"0x{index:016x}"
            native.append({"event_info_index": str(index), "code_hex": code, "base_name": "ac0908", "scene_name": event})
            scenes = [event] + (["SHUTTER_HATTEN"] if event in {"ac0908_010", "ac0908_013"} else [])
            runtime[event] = {"code_hex": code, "animations": [{"scenes": scenes}]}
            timeline.append({"root": "ac0908", "primary_animation": event, "audio_timeline_duration_ms": str(index * 100)})
            dirinfo.append({"base_name": "ac0908", "kind": "33", "row_index": str(index), "selector_raw": "1", "scene_name": event})
        dgm = [{
            "event_name": "ac0908_001", "z2d_order": "0", "dgm_order": "0",
            "z2d_name": "z", "dgm_name": "d", "dgm_role": "single_layer_segment",
            "package": "main", "package_index": "1", "official_name": "one",
            "event_start_ms": "0", "event_end_ms": "1000", "media_expected_frames": "30",
            "interval_confidence": "exact_duration_unique", "cri_match": "yes",
        }]
        showcase = {"timeline": [
            {"event": "ac0908_001", "kind": "entry", "start_frame": 0, "end_frame": 30},
            {"event": "ac0908_009", "kind": "entry", "start_frame": 30, "end_frame": 169},
            {"event": "ac0908_009", "kind": "entry", "start_frame": 169, "end_frame": 308},
        ]}
        probes = {"main:1:one": {"source_exists": True, "status": "OPENED", "probe_frame_count": "30"}}
        return native, dirinfo, runtime, timeline, dgm, showcase, probes

    def test_event_count_is_not_a_visible_segment_certificate(self):
        report = MODULE.build_report(*self.fixture())
        self.assertEqual(report["proven_counts"]["event_info_container_count"], 17)
        self.assertEqual(report["not_yet_proven"]["final_unique_human_visible_segment_count"], "UNRESOLVED")
        self.assertEqual(report["final_product_gate"], "BLOCKED_PENDING_CODE_LEVEL_VISIBLE_SEGMENT_AND_DURATION_CLOSURE")

    def test_shared_scene_and_repeated_occurrence_are_explicit(self):
        report = MODULE.build_report(*self.fixture())
        shutter = next(row for row in report["shared_scene_nodes"] if row["scene"] == "SHUTTER_HATTEN")
        self.assertEqual(shutter["reference_count"], 2)
        duplicate = report["current_showcase"]["guaranteed_duplicate_occurrence_groups"][0]
        self.assertEqual((duplicate["event"], duplicate["occurrence_count"]), ("ac0908_009", 2))

    def test_missing_containers_are_fail_closed(self):
        report = MODULE.build_report(*self.fixture())
        self.assertIn("ac0908_010", report["current_showcase"]["missing_event_containers"])
        self.assertEqual(report["current_showcase"]["authority_decision"], "PLAYBACK_APPROVAL_RETAINED_COMPLETE_CLAIM_WITHDRAWN")


if __name__ == "__main__":
    unittest.main()
