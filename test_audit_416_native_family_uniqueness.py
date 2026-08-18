import importlib.util
import json
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parent
PATH = ROOT / "tools" / "frida_runtime_probe" / "audit_416_native_family_uniqueness.py"
SPEC = importlib.util.spec_from_file_location("audit_416_native_family_uniqueness", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class NativeFamilyUniquenessTests(unittest.TestCase):
    def test_manifest_composition_keys_do_not_read_source_snapshots(self):
        payload = {
            "ordered_events": ["ac1000_001"],
            "timeline": [{"event": "ac1000_002"}],
            "source_snapshots": [{"path": "ac1000_999"}],
        }
        self.assertEqual(MODULE.direct_manifest_events(payload), {"ac1000_001", "ac1000_002"})

    def test_native_ledger_stays_fail_closed_and_reports_duration(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = pathlib.Path(directory) / "manifest.json"
            manifest.write_text(json.dumps({"ordered_events": ["ac1000_001"]}), encoding="utf-8")
            inventory = [{
                "family": "ac1000", "resolution": "416x232", "content_type": "clean_story",
                "owner_approved": "True", "event_ids": "[]", "source_manifest": str(manifest),
            }]
            event_info = [
                {"base_name": "ac1000", "scene_name": "ac1000_001", "code_hex": "0x1"},
                {"base_name": "ac1000", "scene_name": "ac1000_002", "code_hex": "0x2"},
            ]
            dirinfo = [
                {"base_name": "ac1000", "scene_name": "ac1000_001", "row_index": "0", "selector_raw": "1"},
                {"base_name": "ac1000", "scene_name": "ac1000_002", "row_index": "0", "selector_raw": "2"},
            ]
            dgm = [{
                "event_name": "ac1000_001", "cri_match": "yes", "package": "main",
                "package_index": "7", "official_name": "clip", "media_duration_sec": "2.0",
                "event_end_ms": "2000",
            }]
            families, events, summary = MODULE.build_ledger(inventory, event_info, dirinfo, dgm)
            self.assertEqual(families[0]["old_manifest_missing_events"], "ac1000_002")
            self.assertEqual(families[0]["sum_unique_bound_dgm_source_duration_sec"], "2.000000")
            self.assertEqual(families[0]["direction_scene_decode_required_events"], "ac1000_002")
            self.assertEqual(summary["certified_exhaustive_family_count"], 0)
            self.assertFalse(summary["machine_vision_used_as_authority"])
            self.assertEqual(len(events), 2)

    def test_review_wrapper_follows_its_declared_manifest_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            child = root / "manifests" / "chapter.json"
            child.parent.mkdir()
            child.write_text(json.dumps({"ordered_events": ["ac1000_003"]}), encoding="utf-8")
            wrapper = root / "ready.json"
            wrapper.write_text(
                json.dumps({"artifacts": {"manifest": {"path": "manifests/chapter.json"}}}),
                encoding="utf-8",
            )
            self.assertEqual(MODULE.manifest_events(wrapper, {}), {"ac1000_003"})

    def test_eventinfo_only_container_remains_in_exhaustive_candidate_universe(self):
        inventory = [{
            "family": "ac1000", "resolution": "416x232", "content_type": "clean_story",
            "owner_approved": "False", "event_ids": "[]", "source_manifest": "",
        }]
        event_info = [
            {"base_name": "ac1000", "scene_name": "ac1000_001", "code_hex": "0x1"},
            {"base_name": "ac1000", "scene_name": "ac1000_002", "code_hex": "0x2"},
        ]
        dirinfo = [
            {"base_name": "ac1000", "scene_name": "ac1000_001", "row_index": "0", "selector_raw": "1"},
        ]
        families, events, _ = MODULE.build_ledger(inventory, event_info, dirinfo, [])
        self.assertEqual({row["event"] for row in events}, {"ac1000_001", "ac1000_002"})
        self.assertEqual(families[0]["old_manifest_missing_event_count"], 2)


if __name__ == "__main__":
    unittest.main()
