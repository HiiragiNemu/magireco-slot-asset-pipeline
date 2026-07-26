import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MODULE_DIR = ROOT / "tools" / "frida_runtime_probe"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

import audit_material_component_coverage as module  # noqa: E402


class AuditMaterialComponentCoverageTest(unittest.TestCase):
    def _write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _fixture(self, root: Path) -> tuple[Path, Path]:
        clip416 = root / "clip416.mp4"
        clip512 = root / "clip512.mp4"
        clip416.write_bytes(b"416")
        clip512.write_bytes(b"512")
        event_manifest = root / "event.json"
        self._write_json(
            event_manifest,
            {
                "event": "ac5102_001",
                "clips": [
                    {"dgm_name": "clip416", "path": str(clip416)},
                    {"dgm_name": "clip512", "path": str(clip512)},
                ],
            },
        )
        ledger = root / "ledger.csv"
        with ledger.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "event_name",
                    "family",
                    "production_state",
                    "disposition",
                    "manifest_path",
                    "manifest_sha256",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "event_name": "ac5102_001",
                    "family": "ac5102",
                    "production_state": "planned_unproduced",
                    "disposition": "gameplay_effect_collection",
                    "manifest_path": str(event_manifest),
                    "manifest_sha256": module.file_sha256(event_manifest),
                }
            )
        catalog_paths = []
        for name, role, clip, dimensions in (
            ("c416", "event_components", clip416, (416, 232)),
            ("c512", "shared_components", clip512, (512, 288)),
        ):
            output = root / f"{name}.mp4"
            output.write_bytes(name.encode("ascii"))
            manifest = root / f"{name}.json"
            value = {
                "technical_qa_status": "passed",
                "output": str(output),
                "output_sha256": module.file_sha256(output),
                "sources": [
                    {
                        "official_name": clip.stem,
                        "path": str(clip),
                        "source_sha256": module.file_sha256(clip),
                        "source_video_signature": {
                            "width": dimensions[0],
                            "height": dimensions[1],
                        },
                    }
                ],
                "component_events": (
                    ["ac5102_001"] if role == "event_components" else []
                ),
                "component_event_clip_map": (
                    {"ac5102_001": ["clip416"]}
                    if role == "event_components"
                    else {}
                ),
            }
            self._write_json(manifest, value)
            catalog_paths.append((name, role, dimensions, manifest))
        plan = root / "plan.json"
        self._write_json(
            plan,
            {
                "schema": module.PLAN_SCHEMA,
                "status": "active_fail_closed",
                "coverage_id": "fixture",
                "family": "ac5102",
                "expected_production_state": "planned_unproduced",
                "expected_disposition": "gameplay_effect_collection",
                "expected_event_count": 1,
                "composition_policy": (
                    "separate_native_size_catalogs_never_concat_or_upscale"
                ),
                "event_ledger": {
                    "path": str(ledger),
                    "sha256": module.file_sha256(ledger),
                },
                "component_catalogs": [
                    {
                        "name": name,
                        "role": role,
                        "native_dimensions": {
                            "width": dimensions[0],
                            "height": dimensions[1],
                        },
                        "manifest": {
                            "path": str(manifest),
                            "sha256": module.file_sha256(manifest),
                        },
                        "allowed_unused_sources": [],
                    }
                    for name, role, dimensions, manifest in catalog_paths
                ],
            },
        )
        return plan, event_manifest

    def test_split_catalogs_cover_exact_event_clips(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            plan, _event_manifest = self._fixture(root)
            output = root / "audit.json"
            module.audit(plan_path=plan, output_path=output)
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "PASSED")
            self.assertEqual(result["covered_events"], ["ac5102_001"])
            self.assertEqual(len(result["component_catalogs"]), 2)
            self.assertEqual(result["families"], ["ac5102"])

    def test_split_catalogs_can_cover_an_explicit_multi_family_event_set(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            plan, first_manifest = self._fixture(root)
            second_manifest = root / "event-ac9053.json"
            second_event = json.loads(first_manifest.read_text(encoding="utf-8"))
            second_event["event"] = "ac9053_001"
            self._write_json(second_manifest, second_event)

            plan_value = json.loads(plan.read_text(encoding="utf-8"))
            ledger = Path(plan_value["event_ledger"]["path"])
            with ledger.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            rows.append(
                {
                    **rows[0],
                    "event_name": "ac9053_001",
                    "family": "ac9053",
                    "manifest_path": str(second_manifest),
                    "manifest_sha256": module.file_sha256(second_manifest),
                }
            )
            with ledger.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)

            component_manifest = Path(
                plan_value["component_catalogs"][0]["manifest"]["path"]
            )
            component = json.loads(
                component_manifest.read_text(encoding="utf-8")
            )
            component["component_events"].append("ac9053_001")
            component["component_event_clip_map"]["ac9053_001"] = [
                "clip416"
            ]
            self._write_json(component_manifest, component)

            plan_value.pop("family")
            plan_value["families"] = ["ac5102", "ac9053"]
            plan_value["expected_event_count"] = 2
            plan_value["expected_events"] = [
                "ac5102_001",
                "ac9053_001",
            ]
            plan_value["event_ledger"]["sha256"] = module.file_sha256(ledger)
            plan_value["component_catalogs"][0]["manifest"]["sha256"] = (
                module.file_sha256(component_manifest)
            )
            self._write_json(plan, plan_value)

            output = root / "multi-family-audit.json"
            module.audit(plan_path=plan, output_path=output)
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["families"], ["ac5102", "ac9053"])
            self.assertEqual(
                result["covered_events"],
                ["ac5102_001", "ac9053_001"],
            )

    def test_missing_component_source_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            plan, event_manifest = self._fixture(root)
            event = json.loads(event_manifest.read_text(encoding="utf-8"))
            event["clips"].append(
                {"dgm_name": "missing", "path": str(root / "missing.mp4")}
            )
            self._write_json(event_manifest, event)
            plan_value = json.loads(plan.read_text(encoding="utf-8"))
            ledger = Path(plan_value["event_ledger"]["path"])
            with ledger.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            rows[0]["manifest_sha256"] = module.file_sha256(event_manifest)
            with ledger.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            plan_value["event_ledger"]["sha256"] = module.file_sha256(ledger)
            self._write_json(plan, plan_value)
            with self.assertRaisesRegex(ValueError, "absent from split catalogs"):
                module.audit(plan_path=plan, output_path=root / "audit.json")

    def test_audience_inventory_can_bind_two_native_component_catalogs(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            plan, _event_manifest = self._fixture(root)
            plan_value = json.loads(plan.read_text(encoding="utf-8"))
            ledger = Path(plan_value["event_ledger"]["path"])
            with ledger.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "event_name",
                        "family",
                        "clip_count",
                        "resolved_clip_count",
                        "classification",
                        "production_state",
                        "disposition",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "event_name": "ac5102_001",
                        "family": "ac5102",
                        "clip_count": 2,
                        "resolved_clip_count": 2,
                        "classification": (
                            "mixed_full_frame_and_components"
                        ),
                        "production_state": "planned_unproduced",
                        "disposition": "gameplay_effect_collection",
                    }
                )
            clip_index = root / "audience-clips.csv"
            with clip_index.open(
                "w", encoding="utf-8", newline=""
            ) as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["event_name", "official_name", "target_mp4"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "event_name": "ac5102_001",
                        "official_name": "clip416",
                        "target_mp4": str(root / "clip416.mp4"),
                    }
                )
                writer.writerow(
                    {
                        "event_name": "ac5102_001",
                        "official_name": "clip512",
                        "target_mp4": str(root / "clip512.mp4"),
                    }
                )
            c512_path = Path(
                plan_value["component_catalogs"][1]["manifest"]["path"]
            )
            c512 = json.loads(c512_path.read_text(encoding="utf-8"))
            c512["component_events"] = ["ac5102_001"]
            c512["component_event_clip_map"] = {
                "ac5102_001": ["clip512"]
            }
            self._write_json(c512_path, c512)
            plan_value["event_ledger"]["sha256"] = module.file_sha256(ledger)
            plan_value["audience_clip_index"] = {
                "path": str(clip_index),
                "sha256": module.file_sha256(clip_index),
            }
            plan_value["expected_events"] = ["ac5102_001"]
            plan_value["expected_classification"] = (
                "mixed_full_frame_and_components"
            )
            plan_value["component_catalogs"][1]["role"] = "event_components"
            plan_value["component_catalogs"][1]["manifest"]["sha256"] = (
                module.file_sha256(c512_path)
            )
            self._write_json(plan, plan_value)
            output = root / "audience-audit.json"
            module.audit(plan_path=plan, output_path=output)
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "PASSED")
            self.assertEqual(
                {
                    row["role"] for row in result["component_catalogs"]
                },
                {"event_components"},
            )


if __name__ == "__main__":
    unittest.main()
