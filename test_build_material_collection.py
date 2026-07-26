from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import tools.frida_runtime_probe.build_material_collection as material_module
from tools.frida_runtime_probe.build_material_collection import (
    audio_peak_db,
    build_collection,
    build_named_collection,
    classify_audio_semantic,
    collection_release_gate,
    deduplicate_material_sources_by_av_signature,
    file_sha256,
    material_lane,
    material_semantic_review_gate,
    transcript_gate,
)


VOICE_HASH = "A" * 64
EVIDENCE_PATH = Path(__file__).resolve()
EVIDENCE_HASH = hashlib.sha256(EVIDENCE_PATH.read_bytes()).hexdigest().upper()


def native_mix_fields() -> dict:
    return {
        "duration_ms": 900,
        "native_volume": 50,
        "volume_unit": "game_percent",
        "ducking_contract": {
            "mode": "none",
            "evidence_source": "official_runtime_capture",
            "evidence_path": str(EVIDENCE_PATH),
            "evidence_sha256": EVIDENCE_HASH,
            "evidence_locator": "unit-test ducking contract",
        },
        "mix_contract": {
            "mode": "runtime_additive",
            "evidence_source": "runtime_pre_gate_volume_probe",
            "evidence_path": str(EVIDENCE_PATH),
            "evidence_sha256": EVIDENCE_HASH,
            "evidence_locator": "unit-test mix contract",
        },
    }


def approved_visual_gate(classification: str = "material/effect") -> dict:
    return material_semantic_review_gate(
        {
            "classification": classification,
            "evidence_source": "human_reviewed_semantic_map",
            "evidence_path": str(EVIDENCE_PATH),
            "evidence_sha256": EVIDENCE_HASH,
            "evidence_locator": "unit-test visual semantic row",
            "reviewer": "reviewer@example",
            "human_review_status": "approved",
        }
    )


def role_voice(event: str, request_id: str, start_ms: int = 167) -> dict:
    return {
        "event": event,
        "request_id": request_id,
        "code_name": "25472_kyo_AT_story_001",
        "start_ms": start_ms,
        "source_sha256": VOICE_HASH,
        **native_mix_fields(),
    }


def non_dialogue(event: str = "ac0912_001") -> dict:
    return {
        "event": event,
        "request_id": "800",
        "code_name": "00800_bank01_ogg_00001",
        "start_ms": 0,
        "source_sha256": VOICE_HASH,
        "semantic_review": {
            "semantic": "sound_effect",
            "evidence_source": "verified_static_sound_table",
            "evidence_path": str(EVIDENCE_PATH),
            "source_sha256": EVIDENCE_HASH,
            "evidence_locator": "unit-test static sound row",
        },
        **native_mix_fields(),
    }


def transcript(
    event: str,
    request_id: str,
    source: str,
    voice_start_ms: int = 167,
    *,
    text: str = "見滝原に進路を向けたみたいだね",
) -> dict:
    return {
        "event": event,
        "voice_request_id": request_id,
        "text": text,
        "subtitle_source": source,
        "voice_start_ms": voice_start_ms,
        "voice_end_ms": voice_start_ms + 900,
        "source_sha256": VOICE_HASH,
        "reviewer": "reviewer@example",
        "human_review_status": "approved",
    }


class MaterialCollectionTranscriptGateTests(unittest.TestCase):
    def test_ac5102_kyo_role_voice_is_detected_without_allowlist(self) -> None:
        result = classify_audio_semantic(
            {"code_name": "25472_kyo_AT_マギアタ上乗せ_はぁっ"}
        )

        self.assertEqual(result["semantic"], "role_voice")
        self.assertEqual(result["status"], "conservative_role_voice")
        self.assertEqual(result["basis"], "static_at_voice_naming_pattern")

    def test_structural_role_voice_cannot_be_overridden_as_se(self) -> None:
        row = non_dialogue()
        row["code_name"] = "25472_kyo_AT_story_001"

        result = classify_audio_semantic(row)

        self.assertEqual(result["semantic"], "role_voice")
        self.assertEqual(result["status"], "conservative_role_voice")

    def test_unrecognized_audio_is_unknown_not_non_dialogue(self) -> None:
        result = classify_audio_semantic(
            {"code_name": "00800_bank01_ogg_00001"}
        )

        self.assertEqual(result["semantic"], "unknown")
        gate = collection_release_gate(
            errors=[],
            role_voice_audio_rows=[],
            transcript_rows=[],
            all_audio_rows=[{"code_name": "00800_bank01_ogg_00001"}],
        )
        self.assertEqual(gate["status"], "review_only")
        self.assertFalse(gate["visual_only_gate"]["release_eligible"])
        self.assertFalse(gate["release_eligible"])

    def test_any_role_voice_requires_transcript_and_is_not_pure_material(self) -> None:
        roles = [role_voice("ac7204_003", "5622")]
        gate = collection_release_gate(
            errors=[],
            role_voice_audio_rows=roles,
            transcript_rows=[],
            all_audio_rows=roles,
        )

        self.assertTrue(gate["transcript_required"])
        self.assertEqual(gate["transcript_status"], "required_not_verified")
        self.assertEqual(gate["status"], "review_only")
        self.assertEqual(gate["publication_status"], "review_only")
        self.assertFalse(gate["release_eligible"])
        self.assertFalse(gate["publishable"])

    def test_release_gate_reclassifies_audio_instead_of_trusting_omitted_list(self) -> None:
        audio = role_voice("ac5102_133", "25472")
        gate = collection_release_gate(
            errors=[],
            role_voice_audio_rows=[],
            transcript_rows=[],
            all_audio_rows=[audio],
            unknown_audio_rows=[],
            material_semantics_release_approved=True,
            visual_semantic_gate=approved_visual_gate(),
        )

        self.assertTrue(gate["transcript_required"])
        self.assertEqual(gate["transcript_status"], "required_not_verified")
        self.assertFalse(gate["visual_only_gate"]["release_eligible"])
        self.assertFalse(gate["release_eligible"])

    def test_every_event_request_pair_must_have_verified_transcript(self) -> None:
        roles = [
            role_voice("ac7204_003", "5622"),
            role_voice("ac7204_004", "5622"),
        ]
        gate = transcript_gate(
            roles,
            [transcript("ac7204_003", "5622", "official_voice_asr_verified")],
        )

        self.assertEqual(gate["transcript_status"], "required_not_verified")
        self.assertEqual(
            gate["missing_transcript_role_voice"],
            [
                {
                    "event": "ac7204_004",
                    "request_id": "5622",
                    "reason": "verified_transcript_missing",
                    "source_sha256": VOICE_HASH,
                    "start_ms": 167,
                }
            ],
        )

    def test_repeated_request_id_at_another_time_needs_its_own_transcript(self) -> None:
        gate = transcript_gate(
            [
                role_voice("ac7204_003", "5622", 167),
                role_voice("ac7204_003", "5622", 2167),
            ],
            [
                transcript(
                    "ac7204_003",
                    "5622",
                    "official_voice_asr_verified",
                    167,
                )
            ],
        )

        self.assertEqual(gate["transcript_status"], "required_not_verified")
        self.assertEqual(gate["missing_transcript_role_voice"][0]["start_ms"], 2167)

    def test_verified_transcript_does_not_reclassify_role_voice_as_material(self) -> None:
        for source in ("official_runtime_capture", "official_voice_asr_verified"):
            with self.subTest(source=source):
                roles = [role_voice("ac7204_003", "5622")]
                gate = collection_release_gate(
                    errors=[],
                    role_voice_audio_rows=roles,
                    transcript_rows=[transcript("ac7204_003", "5622", source)],
                    all_audio_rows=roles,
                )
                self.assertEqual(gate["transcript_status"], "verified")
                self.assertEqual(gate["status"], "review_only")
                self.assertFalse(gate["release_eligible"])

    def test_voice_label_only_is_not_accepted_as_verified_transcript(self) -> None:
        gate = collection_release_gate(
            errors=[],
            role_voice_audio_rows=[role_voice("ac7204_003", "5622")],
            transcript_rows=[
                transcript("ac7204_003", "5622", "official_voice_label")
            ],
        )

        self.assertEqual(gate["transcript_status"], "required_not_verified")
        self.assertEqual(gate["status"], "review_only")

    def test_formal_cue_requires_hash_reviewer_approval_and_end_time(self) -> None:
        cue = transcript(
            "ac7204_003", "5622", "official_voice_asr_verified"
        )
        for missing in (
            "source_sha256",
            "reviewer",
            "human_review_status",
            "voice_end_ms",
        ):
            with self.subTest(missing=missing):
                invalid = dict(cue)
                invalid.pop(missing)
                gate = transcript_gate(
                    [role_voice("ac7204_003", "5622")], [invalid]
                )
                self.assertEqual(
                    gate["transcript_status"], "required_not_verified"
                )
                self.assertTrue(gate["transcript_validation_errors"])

    def test_duplicate_and_conflicting_cues_fail_closed(self) -> None:
        cue = transcript(
            "ac7204_003", "5622", "official_voice_asr_verified"
        )
        for duplicate in (copy.deepcopy(cue), {**cue, "text": "別の台詞"}):
            with self.subTest(text=duplicate["text"]):
                gate = transcript_gate(
                    [role_voice("ac7204_003", "5622")], [cue, duplicate]
                )
                self.assertEqual(
                    gate["transcript_status"], "required_not_verified"
                )
                self.assertTrue(gate["transcript_validation_errors"])

    def test_duplicate_formal_cues_fail_closed_even_without_detected_voice(self) -> None:
        cue = transcript(
            "ac7204_003", "5622", "official_voice_asr_verified"
        )
        gate = transcript_gate([], [cue, copy.deepcopy(cue)])

        self.assertTrue(gate["transcript_required"])
        self.assertEqual(gate["transcript_status"], "required_not_verified")
        self.assertEqual(
            gate["transcript_validation_errors"][0]["reason"],
            "duplicate_transcript_cues",
        )

    def test_existing_manifest_transcript_requirement_remains_fail_closed(self) -> None:
        gate = collection_release_gate(
            errors=[],
            role_voice_audio_rows=[],
            transcript_rows=[],
            transcript_required_hint=True,
        )

        self.assertTrue(gate["transcript_required"])
        self.assertEqual(gate["transcript_status"], "required_not_verified")
        self.assertEqual(gate["status"], "review_only")
        self.assertEqual(
            gate["missing_transcript_role_voice"][0]["reason"],
            "manifest_transcript_requirement_unresolved",
        )

    def test_visual_and_audible_release_gates_are_independent(self) -> None:
        audio = non_dialogue()
        incomplete = dict(audio)
        incomplete.pop("mix_contract")
        gate = collection_release_gate(
            errors=[],
            role_voice_audio_rows=[],
            transcript_rows=[],
            all_audio_rows=[incomplete],
            unknown_audio_rows=[],
            material_semantics_release_approved=True,
            visual_semantic_gate=approved_visual_gate(),
        )

        self.assertTrue(gate["visual_only_gate"]["release_eligible"])
        self.assertFalse(gate["audible_review_gate"]["release_eligible"])
        self.assertFalse(gate["release_eligible"])
        self.assertFalse(gate["publishable"])

        complete = collection_release_gate(
            errors=[],
            role_voice_audio_rows=[],
            transcript_rows=[],
            all_audio_rows=[audio],
            unknown_audio_rows=[],
            material_semantics_release_approved=True,
            visual_semantic_gate=approved_visual_gate(),
        )
        self.assertTrue(complete["visual_only_gate"]["release_eligible"])
        self.assertTrue(complete["audible_review_gate"]["release_eligible"])
        self.assertTrue(complete["release_eligible"])

    def test_named_style_explicit_release_authorization_defaults_closed(self) -> None:
        gate = collection_release_gate(
            errors=[],
            role_voice_audio_rows=[],
            transcript_rows=[],
            explicit_release_authorized=False,
            visual_semantic_gate=approved_visual_gate(),
        )

        self.assertEqual(gate["status"], "review_only")
        self.assertFalse(gate["visual_only_gate"]["release_eligible"])
        self.assertFalse(gate["release_eligible"])

    def test_named_semantic_review_requires_hash_reviewer_and_human_approval(self) -> None:
        incomplete = material_semantic_review_gate(
            {"classification": "material/effect"}
        )
        self.assertFalse(incomplete["verified"])

        complete = material_semantic_review_gate(
            {
                "classification": "material/effect",
                "evidence_source": "human_reviewed_semantic_map",
                "evidence_path": str(EVIDENCE_PATH),
                "source_sha256": EVIDENCE_HASH,
                "evidence_locator": "unit-test reviewed semantic row",
                "reviewer": "reviewer@example",
                "human_review_status": "approved",
            }
        )
        self.assertTrue(complete["verified"])

    def test_visual_semantics_are_not_inferred_from_missing_audio(self) -> None:
        gate = collection_release_gate(
            errors=[],
            role_voice_audio_rows=[],
            transcript_rows=[],
            all_audio_rows=[],
        )

        self.assertEqual(gate["visual_semantic_gate"]["status"], "review_required")
        self.assertFalse(gate["visual_only_gate"]["release_eligible"])
        self.assertEqual(gate["audible_review_gate"]["status"], "not_applicable")
        self.assertFalse(gate["release_eligible"])

    def test_visual_review_must_bind_the_exact_source_hash_set(self) -> None:
        review = {
            "classification": "material/effect",
            "evidence_source": "human_reviewed_semantic_map",
            "evidence_path": str(EVIDENCE_PATH),
            "evidence_sha256": EVIDENCE_HASH,
            "evidence_locator": "unit-test reviewed semantic row",
            "reviewer": "reviewer@example",
            "human_review_status": "approved",
            "reviewed_source_sha256s": ["B" * 64],
        }

        gate = material_semantic_review_gate(
            review, expected_source_sha256s={"C" * 64}
        )

        self.assertFalse(gate["verified"])
        self.assertIn(
            "semantic_reviewed_source_hashes_mismatch", gate["errors"]
        )

    def test_pure_visual_material_without_audio_can_pass(self) -> None:
        expected_lanes = {
            "ac0906": "reviewed_audience_components_not_standalone_animation",
            "ac0912": "pure_gameplay_or_effect_material",
        }
        for series, expected_lane in expected_lanes.items():
            with self.subTest(series=series, expected_lane=expected_lane):
                gate = collection_release_gate(
                    errors=[],
                    role_voice_audio_rows=[],
                    transcript_rows=[],
                    visual_semantic_gate=approved_visual_gate(
                        "gameplay" if series == "ac0912" else "material/effect"
                    ),
                )
                lane = material_lane(
                    role_voice_audio_count=0,
                    gameplay_marker=series == "ac0912",
                    hybrid_slot_story=False,
                )
                self.assertFalse(gate["transcript_required"])
                self.assertEqual(gate["status"], "passed")
                self.assertTrue(gate["release_eligible"])
                self.assertEqual(lane, expected_lane)

    def test_technical_error_stays_failed_even_without_role_voice(self) -> None:
        gate = collection_release_gate(
            errors=["duration_mismatch"],
            role_voice_audio_rows=[],
            transcript_rows=[],
            visual_semantic_gate=approved_visual_gate(),
        )

        self.assertEqual(gate["technical_qa_status"], "failed")
        self.assertEqual(gate["status"], "failed")
        self.assertEqual(gate["publication_status"], "blocked_technical_qa")
        self.assertFalse(gate["release_eligible"])


class MaterialCollectionAvDedupTests(unittest.TestCase):
    @staticmethod
    def source(event: str, request_id: str, audio_hash: str) -> dict:
        return {
            "event": event,
            "dgm_name": "shared_visual",
            "clip_index": 1,
            "path": "X:/shared_visual.mp4",
            "production_manifest": f"X:/{event}.json",
            "duration_ms": 1000,
            "source_video_packet_sha256": "C" * 64,
            "source_video_signature": {"width": 416, "height": 232},
            "official_audio_evidence": [
                {
                    "request_id": request_id,
                    "source_sha256": audio_hash,
                    "start_ms": 0,
                    "duration_ms": 900,
                }
            ],
            "transcript_evidence": [],
        }

    def test_shared_visual_with_different_audio_is_not_deduplicated(self) -> None:
        sources = [
            self.source("ac5102_133", "25472", "D" * 64),
            self.source("ac5102_156", "99999", "E" * 64),
        ]

        deduplicated = deduplicate_material_sources_by_av_signature(sources)

        self.assertEqual(len(deduplicated), 2)
        self.assertNotEqual(
            deduplicated[0]["av_signature"]["sha256"],
            deduplicated[1]["av_signature"]["sha256"],
        )

    def test_exact_av_duplicate_keeps_every_source_event_alias(self) -> None:
        first = self.source("ac5102_133", "25472", "D" * 64)
        second = self.source("ac5102_156", "25472", "D" * 64)

        deduplicated = deduplicate_material_sources_by_av_signature(
            [first, second]
        )

        self.assertEqual(len(deduplicated), 1)
        self.assertEqual(deduplicated[0]["source_occurrence_count"], 2)
        self.assertEqual(
            [row["event"] for row in deduplicated[0]["source_event_aliases"]],
            ["ac5102_133", "ac5102_156"],
        )

    def test_exact_media_duplicate_ignores_code_name_alias(self) -> None:
        first = self.source("ac0914_004", "", "D" * 64)
        second = self.source("ac0914_005", "", "D" * 64)
        first["official_audio_evidence"][0]["code_name"] = "outcome_a_loop"
        second["official_audio_evidence"][0]["code_name"] = "outcome_b_loop"

        deduplicated = deduplicate_material_sources_by_av_signature(
            [first, second]
        )

        self.assertEqual(len(deduplicated), 1)
        self.assertEqual(deduplicated[0]["source_occurrence_count"], 2)


class MaterialCollectionPromotionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.out = self.root / "out"
        self.out.mkdir()
        self.source = self.root / "external-source.bin"
        self.source.write_bytes(b"immutable-material-source")

    @staticmethod
    def tree_snapshot(root: Path) -> dict[str, bytes | None]:
        snapshot: dict[str, bytes | None] = {}
        for path in sorted(root.rglob("*"), key=lambda value: str(value)):
            relative = path.relative_to(root).as_posix()
            snapshot[relative] = None if path.is_dir() else path.read_bytes()
        return snapshot

    def make_previous(self, name: str) -> Path:
        published = self.out / name
        (published / "audit").mkdir(parents=True)
        (published / "READY.json").write_bytes(
            b'{"status":"READY","generation":"previous"}\n'
        )
        (published / "material_collection_manifest.json").write_bytes(
            b'{"generation":"previous"}\n'
        )
        (published / "old-video.mp4").write_bytes(b"old-video\x00\xff")
        (published / "audit" / "keep.bin").write_bytes(
            bytes(range(32))
        )
        return published

    def make_staged(self, name: str) -> tuple[Path, dict]:
        staged = self.out / f".unit-staging-{name}" / name
        staged.mkdir(parents=True)
        visual = staged / f"{name}__material.mp4"
        labels = staged / f"{name}__material_labels.srt"
        visual.write_bytes(b"new-visual-output")
        labels.write_text(
            "1\n00:00:00,000 --> 00:00:00,400\nnew clip\n",
            encoding="utf-8",
        )
        source_snapshot = material_module.capture_material_source_snapshot(
            {self.source.resolve(): {f"{name}:unit_source"}}
        )
        manifest = {
            "schema": "unit-material-manifest",
            "series": name,
            "status": "passed",
            "technical_qa_status": "passed",
            "publication_status": "review_only",
            "release_eligible": False,
            "visual_only_gate": {"release_eligible": True},
            "audible_review_gate": {"release_eligible": None},
            "output": str(visual.resolve()),
            "labels": str(labels.resolve()),
            "labels_sha256": file_sha256(labels),
            "output_sha256": file_sha256(visual),
            "audible_status": "not_applicable",
            "audible_output": "",
            "audible_labels": "",
            "audible_labels_sha256": "",
            "audible_output_sha256": "",
            "source_snapshot_start": source_snapshot,
            "source_snapshot_end": copy.deepcopy(source_snapshot),
            "source_rehash": material_module._material_source_rehash_contract(
                source_snapshot, source_snapshot
            ),
        }
        (staged / "material_collection_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        summary = {
            "series": name,
            "status": "passed",
            "technical_qa_status": "passed",
            "publication_status": "review_only",
            "release_eligible": False,
            "visual_only_release_eligible": True,
            "audible_review_release_eligible": None,
            "output": str(visual.resolve()),
            "audible_output": "",
        }
        return staged, summary

    def assert_no_promotion_residue(self, name: str) -> None:
        self.assertFalse(list(self.out.glob(f".{name}.previous-*")))
        self.assertFalse(list(self.out.glob(f".{name}.failed-*")))

    def assert_injected_failure_restores_previous(
        self,
        *,
        name: str,
        verifier_name: str,
        inject,
        error_pattern: str,
    ) -> None:
        published = self.make_previous(name)
        previous_snapshot = self.tree_snapshot(published)
        staged, summary = self.make_staged(name)
        verifier = getattr(material_module, verifier_name)

        def injected_verifier(**kwargs):
            inject(kwargs)
            return verifier(**kwargs)

        with mock.patch.object(
            material_module,
            verifier_name,
            side_effect=injected_verifier,
        ):
            with self.assertRaisesRegex(RuntimeError, error_pattern):
                material_module._promote_material_collection(
                    staged_dir=staged,
                    published_dir=published,
                    summary=summary,
                    overwrite=True,
                )

        self.assertEqual(self.tree_snapshot(published), previous_snapshot)
        self.assert_no_promotion_residue(name)

    def test_manifest_hash_failure_after_promotion_restores_previous_tree(
        self,
    ) -> None:
        def corrupt_manifest(kwargs: dict) -> None:
            path = kwargs["published_dir"] / kwargs["manifest_name"]
            path.write_bytes(path.read_bytes() + b" ")

        self.assert_injected_failure_restores_previous(
            name="manifest_hash_failure",
            verifier_name="_verify_published_material_manifest",
            inject=corrupt_manifest,
            error_pattern="manifest hash changed",
        )

    def test_ready_failure_after_promotion_restores_previous_tree(self) -> None:
        def corrupt_ready(kwargs: dict) -> None:
            path = kwargs["published_dir"] / "READY.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["status"] = "CORRUPT"
            path.write_text(json.dumps(payload), encoding="utf-8")

        self.assert_injected_failure_restores_previous(
            name="ready_failure",
            verifier_name="_verify_published_material_ready",
            inject=corrupt_ready,
            error_pattern="READY payload changed",
        )

    def test_output_hash_failure_after_promotion_restores_previous_tree(
        self,
    ) -> None:
        def corrupt_output(kwargs: dict) -> None:
            output = Path(str(kwargs["manifest"]["output"]))
            output.write_bytes(output.read_bytes() + b"corrupt")

        self.assert_injected_failure_restores_previous(
            name="output_hash_failure",
            verifier_name="_verify_published_material_outputs",
            inject=corrupt_output,
            error_pattern="visual output hash mismatch",
        )

    def test_label_hash_failure_after_promotion_restores_previous_tree(
        self,
    ) -> None:
        def corrupt_label(kwargs: dict) -> None:
            labels = Path(str(kwargs["manifest"]["labels"]))
            labels.write_text("corrupted label\n", encoding="utf-8")

        self.assert_injected_failure_restores_previous(
            name="label_hash_failure",
            verifier_name="_verify_published_material_outputs",
            inject=corrupt_label,
            error_pattern="visual labels hash mismatch",
        )

    def test_postpromotion_source_change_restores_previous_tree(self) -> None:
        name = "source_rehash_failure"
        published = self.make_previous(name)
        previous_snapshot = self.tree_snapshot(published)
        staged, summary = self.make_staged(name)
        verifier = material_module._verify_material_source_contract

        def corrupt_postpromotion(manifest: dict, *, stage: str):
            if stage == "post-promotion":
                self.source.write_bytes(b"source changed after promotion")
            return verifier(manifest, stage=stage)

        with mock.patch.object(
            material_module,
            "_verify_material_source_contract",
            side_effect=corrupt_postpromotion,
        ):
            with self.assertRaisesRegex(RuntimeError, "post-promotion"):
                material_module._promote_material_collection(
                    staged_dir=staged,
                    published_dir=published,
                    summary=summary,
                    overwrite=True,
                )

        self.assertEqual(self.tree_snapshot(published), previous_snapshot)
        self.assert_no_promotion_residue(name)

    def test_source_change_before_ready_preserves_previous_tree(self) -> None:
        name = "source_changed_before_ready"
        published = self.make_previous(name)
        previous_snapshot = self.tree_snapshot(published)
        staged, summary = self.make_staged(name)
        self.source.write_bytes(b"source changed before READY")

        with self.assertRaisesRegex(RuntimeError, "pre-READY"):
            material_module._promote_material_collection(
                staged_dir=staged,
                published_dir=published,
                summary=summary,
                overwrite=True,
            )

        self.assertFalse((staged / "READY.json").exists())
        self.assertEqual(self.tree_snapshot(published), previous_snapshot)
        self.assert_no_promotion_residue(name)

    def test_postpromotion_failure_without_previous_leaves_no_ready_tree(
        self,
    ) -> None:
        name = "first_publish_failure"
        published = self.out / name
        staged, summary = self.make_staged(name)
        verifier = material_module._verify_published_material_outputs

        def corrupt_then_verify(**kwargs):
            Path(str(kwargs["manifest"]["output"])).write_bytes(b"corrupt")
            return verifier(**kwargs)

        with mock.patch.object(
            material_module,
            "_verify_published_material_outputs",
            side_effect=corrupt_then_verify,
        ):
            with self.assertRaisesRegex(RuntimeError, "visual output hash mismatch"):
                material_module._promote_material_collection(
                    staged_dir=staged,
                    published_dir=published,
                    summary=summary,
                    overwrite=False,
                )

        self.assertFalse(published.exists())
        self.assert_no_promotion_residue(name)


@unittest.skipUnless(
    shutil.which("ffmpeg") and shutil.which("ffprobe"),
    "real-media material tests require ffmpeg and ffprobe",
)
class MaterialCollectionRealMediaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.media = self.root / "media"
        self.manifests = self.root / "manifests"
        self.out = self.root / "out"
        self.media.mkdir()
        self.manifests.mkdir()
        self.evidence = self.root / "visual-review.txt"
        self.evidence.write_text(
            "human reviewed visual semantics and runtime mix evidence\n",
            encoding="utf-8",
        )
        self.evidence_hash = file_sha256(self.evidence)

    @staticmethod
    def tree_snapshot(root: Path) -> dict[str, bytes | None]:
        return {
            path.relative_to(root).as_posix(): (
                None if path.is_dir() else path.read_bytes()
            )
            for path in sorted(root.rglob("*"), key=lambda value: str(value))
        }

    def make_video(
        self, name: str, color: str, size: str = "96x64"
    ) -> Path:
        path = self.media / name
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                f"color=c={color}:s={size}:r=30:d=0.4",
                "-an",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-video_track_timescale",
                "15360",
                str(path),
            ],
            check=True,
        )
        return path

    def make_audio(
        self, name: str = "source.wav", *, leading_silence_ms: int = 0
    ) -> Path:
        path = self.media / name
        command = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000:duration=2:sample_rate=48000",
        ]
        if leading_silence_ms:
            command.extend(
                [
                    "-af",
                    f"volume=0:enable='lt(t,{leading_silence_ms / 1000:.6f})'",
                ]
            )
        command.extend(
            [
                "-ac",
                "2",
                "-c:a",
                "pcm_s16le",
                str(path),
            ]
        )
        subprocess.run(command, check=True)
        return path

    def make_av_video(self, name: str, color: str) -> Path:
        path = self.media / name
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                f"color=c={color}:s=96x64:r=30:d=0.4",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=1000:duration=0.4:sample_rate=48000",
                "-shortest",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-ac",
                "2",
                str(path),
            ],
            check=True,
        )
        return path

    def visual_review(self, video: Path, classification: str) -> dict:
        return {
            "classification": classification,
            "evidence_source": "human_reviewed_semantic_map",
            "evidence_path": str(self.evidence),
            "evidence_sha256": self.evidence_hash,
            "evidence_locator": f"review row for {video.name}",
            "reviewer": "human@example",
            "human_review_status": "approved",
            "reviewed_source_sha256s": [file_sha256(video)],
        }

    def audio_row(
        self,
        audio: Path,
        *,
        source_offset_ms: int = 900,
        duration_ms: int = 500,
        native_volume: int = 50,
        duck_gain_db: float | None = None,
    ) -> dict:
        evidence = {
            "evidence_source": "official_runtime_capture",
            "evidence_path": str(self.evidence),
            "evidence_sha256": self.evidence_hash,
            "evidence_locator": "runtime audio mix row",
        }
        ducking_contract = {
            "mode": "none" if duck_gain_db is None else "fixed_gain",
            **evidence,
        }
        if duck_gain_db is not None:
            ducking_contract["gain_db"] = duck_gain_db
        return {
            "path": str(audio),
            "source_sha256": file_sha256(audio),
            "request_id": "835",
            "code_name": "00835_BGM_DIR_01",
            "start_ms": 0,
            "source_offset_ms": source_offset_ms,
            "duration_ms": duration_ms,
            "native_volume": native_volume,
            "volume_unit": "game_percent",
            "semantic_review": {
                "semantic": "bgm",
                "source_sha256": self.evidence_hash,
                **evidence,
            },
            "ducking_contract": ducking_contract,
            "mix_contract": {"mode": "runtime_additive", **evidence},
        }

    def write_event(
        self,
        series: str,
        suffix: int,
        video: Path,
        *,
        classification: str,
        audio: list[dict] | None = None,
    ) -> Path:
        event = f"{series}_{suffix:03d}"
        payload = {
            "event": event,
            "audience_exclusion_reason": "reviewed component route",
            "quality_gates": {"errors": ["audience_component_only"]},
            "clips": [{"path": str(video), "dgm_name": video.stem}],
            "audio": list(audio or []),
            "subtitles": [],
            "visual_semantic_review": self.visual_review(
                video, classification
            ),
        }
        path = self.manifests / f"{event}.json"
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return path

    def build_pair(
        self,
        series: str,
        classification: str,
        *,
        first_audio: list[dict] | None = None,
    ) -> dict:
        first = self.make_video(f"{series}_red.mp4", "red")
        second = self.make_video(f"{series}_blue.mp4", "blue")
        self.write_event(
            series,
            1,
            first,
            classification=classification,
            audio=first_audio,
        )
        self.write_event(
            series, 2, second, classification=classification
        )
        return build_collection(
            series,
            self.manifests,
            self.out,
            "ffmpeg",
            "ffprobe",
            False,
        )

    def test_pure_visual_collection_has_no_fake_audible_edition(self) -> None:
        row = self.build_pair("ac9000", "material/effect")
        manifest = json.loads(Path(row["manifest"]).read_text(encoding="utf-8"))
        ready = json.loads(
            (self.out / "ac9000" / "READY.json").read_text(encoding="utf-8")
        )

        self.assertEqual(row["status"], "passed")
        self.assertTrue(Path(row["output"]).is_file())
        self.assertEqual(row["audible_output"], "")
        self.assertEqual(manifest["audible_status"], "not_applicable")
        self.assertEqual(
            manifest["audible_review_gate"]["status"], "not_applicable"
        )
        self.assertIsNone(
            manifest["audible_review_gate"]["release_eligible"]
        )
        self.assertEqual(ready["status"], "READY")
        self.assertEqual(ready["manifest_sha256"], file_sha256(Path(row["manifest"])))
        labels = Path(manifest["labels"])
        self.assertEqual(manifest["labels_sha256"], file_sha256(labels))
        self.assertEqual(ready["visual_labels"], str(labels.resolve()))
        self.assertEqual(
            ready["visual_labels_sha256"], manifest["labels_sha256"]
        )
        self.assertEqual(
            manifest["source_snapshot_start"],
            manifest["source_snapshot_end"],
        )
        self.assertEqual(ready["source_rehash"], manifest["source_rehash"])
        source_rows = manifest["source_snapshot_end"]["sources"]
        self.assertEqual(len(source_rows), 4)
        self.assertEqual(
            {Path(item["path"]) for item in source_rows},
            {
                *(path.resolve() for path in self.manifests.glob("ac9000_*.json")),
                (self.media / "ac9000_red.mp4").resolve(),
                (self.media / "ac9000_blue.mp4").resolve(),
            },
        )
        self.assertFalse(list(self.out.glob(".material-staging-*")))

    def test_bgm_only_story_is_not_inferred_to_be_material(self) -> None:
        audio = self.make_audio()
        row = self.build_pair(
            "ac9001",
            "story_animation",
            first_audio=[self.audio_row(audio)],
        )
        manifest = json.loads(Path(row["manifest"]).read_text(encoding="utf-8"))

        self.assertEqual(manifest["classification"], "story_animation")
        self.assertEqual(manifest["role_voice_audio_count"], 0)
        self.assertFalse(manifest["pure_material"])
        self.assertFalse(manifest["visual_only_release_eligible"])
        self.assertEqual(manifest["publication_status"], "review_only")
        self.assertTrue(Path(manifest["audible_output"]).is_file())
        self.assertEqual(manifest["audible_status"], "rendered")

    def test_audible_trim_gain_pcm_boundaries_and_single_aac_encode(self) -> None:
        # The first 900 ms is near-silent.  A renderer that ignores
        # source_offset_ms would therefore produce near-silence and fail the
        # peak comparison below.
        audio = self.make_audio(leading_silence_ms=900)
        row = self.build_pair(
            "ac9002",
            "material/effect",
            first_audio=[self.audio_row(audio, duck_gain_db=-3.0)],
        )
        manifest = json.loads(Path(row["manifest"]).read_text(encoding="utf-8"))
        audible = Path(manifest["audible_output"])
        first_segment = manifest["audible_event_sources"][0]["audible_segment"]
        segment_audio = next(
            stream
            for stream in first_segment["probe"]["streams"]
            if stream.get("codec_type") == "audio"
        )

        self.assertEqual(manifest["audible_status"], "rendered")
        self.assertTrue(manifest["audible_review_release_eligible"])
        ready = json.loads(
            (self.out / "ac9002" / "READY.json").read_text(encoding="utf-8")
        )
        audible_labels = Path(manifest["audible_labels"])
        self.assertEqual(
            manifest["audible_labels_sha256"], file_sha256(audible_labels)
        )
        self.assertEqual(
            ready["audible_labels_sha256"],
            manifest["audible_labels_sha256"],
        )
        source_rows = manifest["source_snapshot_end"]["sources"]
        audio_source_row = next(
            item for item in source_rows if Path(item["path"]) == audio.resolve()
        )
        self.assertTrue(
            any("audio_input" in role for role in audio_source_row["roles"])
        )
        self.assertEqual(
            first_segment["applied_audio_rows"][0]["source_offset_ms"], 900
        )
        self.assertEqual(
            first_segment["applied_audio_rows"][0]["duration_ms"], 500
        )
        self.assertAlmostEqual(
            first_segment["applied_audio_rows"][0]["native_gain"][
                "linear_gain"
            ],
            0.5,
        )
        self.assertEqual(
            first_segment["applied_audio_rows"][0]["ducking"]["mode"],
            "fixed_gain",
        )
        self.assertEqual(segment_audio["codec_name"], "pcm_s16le")
        self.assertEqual(manifest["audible_encoding"]["final_aac_encode_count"], 1)
        self.assertFalse(
            manifest["audible_encoding"]["aac_segment_packet_copy"]
        )
        self.assertFalse(
            manifest["audible_encoding"]["unproven_limiter_applied"]
        )
        self.assertLessEqual(abs(manifest["audible_duration_ms"] - 900), 100)
        source_peak = audio_peak_db(audio, "ffmpeg")
        output_peak = audio_peak_db(audible, "ffmpeg")
        self.assertIsNotNone(source_peak)
        self.assertIsNotNone(output_peak)
        self.assertAlmostEqual(output_peak - source_peak, -9.02, delta=1.5)

    def test_unverified_audio_contract_does_not_destroy_visual_review(self) -> None:
        audio = self.make_audio()
        incomplete = self.audio_row(audio)
        incomplete.pop("ducking_contract")
        row = self.build_pair(
            "ac9004",
            "material/effect",
            first_audio=[incomplete],
        )
        manifest = json.loads(Path(row["manifest"]).read_text(encoding="utf-8"))

        self.assertTrue(Path(manifest["output"]).is_file())
        self.assertTrue(manifest["visual_only_release_eligible"])
        self.assertEqual(manifest["audible_status"], "blocked_contract")
        self.assertEqual(manifest["audible_output"], "")
        self.assertFalse(manifest["audible_review_release_eligible"])
        self.assertEqual(row["status"], "review_only")
        self.assertTrue((self.out / "ac9004" / "READY.json").is_file())

    def test_failed_overwrite_preserves_previous_ready_collection(self) -> None:
        row = self.build_pair("ac9003", "gameplay")
        collection = self.out / "ac9003"
        ready_before = (collection / "READY.json").read_bytes()
        manifest_before = Path(row["manifest"]).read_bytes()
        broken = self.manifests / "ac9003_002.json"
        payload = json.loads(broken.read_text(encoding="utf-8"))
        payload["clips"][0]["path"] = str(self.media / "missing.mp4")
        broken.write_text(json.dumps(payload), encoding="utf-8")

        with self.assertRaises(FileNotFoundError):
            build_collection(
                "ac9003",
                self.manifests,
                self.out,
                "ffmpeg",
                "ffprobe",
                True,
            )

        self.assertEqual((collection / "READY.json").read_bytes(), ready_before)
        self.assertEqual(Path(row["manifest"]).read_bytes(), manifest_before)
        self.assertFalse(list(self.out.glob(".material-staging-*")))

    def test_direct_build_time_source_mutations_preserve_previous_ready(
        self,
    ) -> None:
        for index, source_kind in enumerate(
            ("production_manifest", "visual_input", "audio_input"),
            start=10,
        ):
            with self.subTest(source_kind=source_kind):
                series = f"ac91{index:02d}"
                audio = self.make_audio(f"{series}.wav")
                row = self.build_pair(
                    series,
                    "material/effect",
                    first_audio=[self.audio_row(audio)],
                )
                published = self.out / series
                previous_snapshot = self.tree_snapshot(published)
                if source_kind == "production_manifest":
                    target = self.manifests / f"{series}_001.json"
                elif source_kind == "visual_input":
                    target = self.media / f"{series}_red.mp4"
                else:
                    target = audio
                original = target.read_bytes()
                capture = material_module.capture_material_source_snapshot
                calls = 0

                def mutate_before_end_snapshot(paths):
                    nonlocal calls
                    calls += 1
                    if calls == 2:
                        target.write_bytes(original + b"\nTOCTOU")
                    return capture(paths)

                with mock.patch.object(
                    material_module,
                    "capture_material_source_snapshot",
                    side_effect=mutate_before_end_snapshot,
                ):
                    with self.assertRaisesRegex(
                        RuntimeError, "source changed during build"
                    ):
                        build_collection(
                            series,
                            self.manifests,
                            self.out,
                            "ffmpeg",
                            "ffprobe",
                            True,
                        )

                self.assertEqual(
                    self.tree_snapshot(published), previous_snapshot
                )
                self.assertFalse(list(self.out.glob(".material-staging-*")))
                self.assertEqual(row["manifest"], str(
                    (published / "material_collection_manifest.json").resolve()
                ))

    def test_named_build_time_plan_mutation_preserves_previous_ready(self) -> None:
        first = self.make_video("named-gate-red.mp4", "red")
        second = self.make_video("named-gate-blue.mp4", "blue")
        plan = {
            "collection": "named_gate",
            "clips": [
                {"official_name": "gate_red", "label": "red"},
                {"official_name": "gate_blue", "label": "blue"},
            ],
            "visual_semantic_review": {
                "classification": "material/effect",
                "evidence_source": "human_reviewed_semantic_map",
                "evidence_path": str(self.evidence),
                "evidence_sha256": self.evidence_hash,
                "evidence_locator": "named source rehash gate",
                "reviewer": "human@example",
                "human_review_status": "approved",
                "reviewed_source_sha256s": [
                    file_sha256(first),
                    file_sha256(second),
                ],
            },
        }
        plan_path = self.root / "named-gate-plan.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        video_map = {
            "gate_red": {"target_mp4": str(first)},
            "gate_blue": {"target_mp4": str(second)},
        }
        build_named_collection(
            plan_path,
            video_map,
            self.out,
            "ffmpeg",
            "ffprobe",
            False,
        )
        published = self.out / "named_gate"
        previous_snapshot = self.tree_snapshot(published)
        original = plan_path.read_bytes()
        capture = material_module.capture_material_source_snapshot
        calls = 0

        def mutate_before_end_snapshot(paths):
            nonlocal calls
            calls += 1
            if calls == 2:
                plan_path.write_bytes(original + b"\n")
            return capture(paths)

        with mock.patch.object(
            material_module,
            "capture_material_source_snapshot",
            side_effect=mutate_before_end_snapshot,
        ):
            with self.assertRaisesRegex(
                RuntimeError, "source changed during build"
            ):
                build_named_collection(
                    plan_path,
                    video_map,
                    self.out,
                    "ffmpeg",
                    "ffprobe",
                    True,
                )

        self.assertEqual(self.tree_snapshot(published), previous_snapshot)
        self.assertFalse(list(self.out.glob(".material-staging-*")))

    def test_named_material_route_drops_uncontracted_embedded_aac(self) -> None:
        first = self.make_av_video("named-red.mp4", "red")
        second = self.make_av_video("named-blue.mp4", "blue")
        plan = {
            "collection": "named_material",
            "clips": [
                {"official_name": "named_red", "label": "red"},
                {"official_name": "named_blue", "label": "blue"},
            ],
            "visual_semantic_review": {
                "classification": "material/effect",
                "evidence_source": "human_reviewed_semantic_map",
                "evidence_path": str(self.evidence),
                "evidence_sha256": self.evidence_hash,
                "evidence_locator": "named material visual review",
                "reviewer": "human@example",
                "human_review_status": "approved",
                "reviewed_source_sha256s": [
                    file_sha256(first),
                    file_sha256(second),
                ],
            },
        }
        plan_path = self.root / "named-plan.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        video_map = {
            "named_red": {"target_mp4": str(first)},
            "named_blue": {"target_mp4": str(second)},
        }

        row = build_named_collection(
            plan_path,
            video_map,
            self.out,
            "ffmpeg",
            "ffprobe",
            False,
        )
        manifest = json.loads(Path(row["manifest"]).read_text(encoding="utf-8"))
        probe_payload = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "json",
                row["output"],
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        output_streams = json.loads(probe_payload.stdout)["streams"]

        self.assertTrue(manifest["embedded_audio_dropped"])
        self.assertFalse(
            any(stream["codec_type"] == "audio" for stream in output_streams)
        )
        self.assertFalse(manifest["aac_segment_packet_copy"])
        self.assertEqual(manifest["audible_status"], "blocked_contract")
        ready_path = self.out / "named_material" / "READY.json"
        self.assertTrue(ready_path.is_file())
        ready = json.loads(ready_path.read_text(encoding="utf-8"))
        self.assertEqual(
            ready["visual_labels_sha256"], manifest["labels_sha256"]
        )
        source_paths = {
            Path(item["path"])
            for item in manifest["source_snapshot_end"]["sources"]
        }
        self.assertEqual(
            source_paths,
            {plan_path.resolve(), first.resolve(), second.resolve()},
        )

    def test_named_visual_collection_allows_mixed_dropped_source_audio(
        self,
    ) -> None:
        silent = self.make_video("named-mixed-silent.mp4", "red")
        audible = self.make_av_video("named-mixed-audible.mp4", "blue")
        plan = {
            "collection": "named_mixed_source_audio",
            "clips": [
                {"official_name": "mixed_silent", "label": "silent"},
                {"official_name": "mixed_audible", "label": "audible"},
            ],
        }
        plan_path = self.root / "named-mixed-source-audio-plan.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        video_map = {
            "mixed_silent": {"target_mp4": str(silent)},
            "mixed_audible": {"target_mp4": str(audible)},
        }

        row = build_named_collection(
            plan_path,
            video_map,
            self.out,
            "ffmpeg",
            "ffprobe",
            False,
        )
        manifest = json.loads(Path(row["manifest"]).read_text(encoding="utf-8"))
        self.assertTrue(manifest["embedded_audio_dropped"])
        self.assertEqual(len(manifest["embedded_audio_signatures"]), 1)
        self.assertEqual(
            [bool(item["source_audio_signature"].get("codec_name"))
             for item in manifest["sources"]],
            [False, True],
        )
        probe_payload = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "json",
                row["output"],
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertFalse(
            any(
                stream["codec_type"] == "audio"
                for stream in json.loads(probe_payload.stdout)["streams"]
            )
        )

    def test_named_material_hash_binds_declared_evidence_sources(self) -> None:
        first = self.make_video("evidence-red.mp4", "red")
        second = self.make_video("evidence-blue.mp4", "blue")
        evidence = self.root / "event-production.json"
        evidence.write_text(
            '{"schema":"magireco-event-production-v3",'
            '"event":"ac0001_001"}\n',
            encoding="utf-8",
        )
        plan = {
            "collection": "named_evidence",
            "covered_events": ["ac0001_001"],
            "clips": [
                {"official_name": "evidence_red", "label": "red"},
                {"official_name": "evidence_blue", "label": "blue"},
            ],
            "evidence_sources": [
                {
                    "label": "event production manifest",
                    "path": str(evidence),
                    "sha256": file_sha256(evidence),
                }
            ],
        }
        plan_path = self.root / "named-evidence-plan.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        video_map = {
            "evidence_red": {"target_mp4": str(first)},
            "evidence_blue": {"target_mp4": str(second)},
        }

        row = build_named_collection(
            plan_path,
            video_map,
            self.out,
            "ffmpeg",
            "ffprobe",
            False,
        )
        manifest = json.loads(Path(row["manifest"]).read_text(encoding="utf-8"))
        self.assertEqual(
            manifest["evidence_sources"],
            [
                {
                    "label": "event production manifest",
                    "path": str(evidence.resolve()),
                    "sha256": file_sha256(evidence),
                }
            ],
        )
        self.assertEqual(manifest["covered_events"], ["ac0001_001"])
        source_paths = {
            Path(item["path"])
            for item in manifest["source_snapshot_end"]["sources"]
        }
        self.assertEqual(
            source_paths,
            {
                plan_path.resolve(),
                evidence.resolve(),
                first.resolve(),
                second.resolve(),
            },
        )

    def test_named_material_resolves_event_manifests_from_bound_ledger(
        self,
    ) -> None:
        first = self.make_video("ledger-red.mp4", "red")
        second = self.make_video("ledger-blue.mp4", "blue")
        events = ["ac0001_001", "ac6101_2_01"]
        manifests = []
        for event in events:
            path = self.root / f"{event}.json"
            path.write_text(
                json.dumps(
                    {
                        "schema": "magireco-event-production-v3",
                        "event": event,
                        "clips": [
                            {
                                "dgm_name": "ledger-red",
                                "path": str(first),
                            },
                            {
                                "dgm_name": "ledger-blue",
                                "path": str(second),
                            },
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            manifests.append(path)
        ledger = self.root / "production-event-ledger.csv"
        ledger.write_text(
            "event_name,native_dimensions,disposition,production_state,"
            "manifest_path,manifest_sha256\n"
            + "\n".join(
                f"{event},512x288,gameplay_effect_collection,"
                f"planned_unproduced,{path},{file_sha256(path)}"
                for event, path in zip(events, manifests)
            )
            + "\n",
            encoding="utf-8",
        )
        plan = {
            "collection": "named_ledger_evidence",
            "covered_events": events,
            "derive_clips_from_covered_event_manifests": True,
            "covered_event_index": {
                "path": str(ledger),
                "sha256": file_sha256(ledger),
                "production_state": "planned_unproduced",
                "disposition": "gameplay_effect_collection",
                "native_dimensions": "512x288",
            },
        }
        plan_path = self.root / "named-ledger-plan.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        row = build_named_collection(
            plan_path,
            {
                "ledger-red": {"target_mp4": str(first)},
                "ledger-blue": {"target_mp4": str(second)},
            },
            self.out,
            "ffmpeg",
            "ffprobe",
            False,
        )
        manifest = json.loads(Path(row["manifest"]).read_text(encoding="utf-8"))
        self.assertEqual(manifest["covered_events"], events)
        evidence_paths = {
            Path(item["path"]) for item in manifest["evidence_sources"]
        }
        self.assertEqual(
            evidence_paths,
            {ledger.resolve(), *(path.resolve() for path in manifests)},
        )

    def test_named_component_material_filters_derived_clips_by_native_size(
        self,
    ) -> None:
        first = self.make_video("component-red.mp4", "red")
        second = self.make_video("component-blue.mp4", "blue")
        excluded = self.make_video(
            "component-green.mp4", "green", "64x48"
        )
        event = "ac5102_004"
        manifest_path = self.root / f"{event}.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "schema": "magireco-event-production-v3",
                    "event": event,
                    "clips": [
                        {"dgm_name": path.stem, "path": str(path)}
                        for path in (first, second, excluded)
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        ledger = self.root / "component-ledger.csv"
        ledger.write_text(
            "event_name,native_dimensions,disposition,production_state,"
            "manifest_path,manifest_sha256\n"
            f"{event},x,gameplay_effect_collection,planned_unproduced,"
            f"{manifest_path},{file_sha256(manifest_path)}\n",
            encoding="utf-8",
        )
        plan = {
            "collection": "named_component_evidence",
            "component_events": [event],
            "component_native_dimensions": {"width": 96, "height": 64},
            "derive_clips_from_covered_event_manifests": True,
            "covered_event_index": {
                "path": str(ledger),
                "sha256": file_sha256(ledger),
                "production_state": "planned_unproduced",
                "disposition": "gameplay_effect_collection",
                "native_dimensions": "x",
            },
        }
        plan_path = self.root / "named-component-plan.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        row = build_named_collection(
            plan_path,
            {
                path.stem: {"target_mp4": str(path)}
                for path in (first, second, excluded)
            },
            self.out,
            "ffmpeg",
            "ffprobe",
            False,
        )
        manifest = json.loads(Path(row["manifest"]).read_text(encoding="utf-8"))
        self.assertEqual(manifest["covered_events"], [])
        self.assertEqual(manifest["component_events"], [event])
        self.assertEqual(
            manifest["component_native_dimensions"],
            {"width": 96, "height": 64},
        )
        self.assertEqual(
            manifest["component_event_clip_map"][event],
            [first.stem, second.stem],
        )
        self.assertEqual(manifest["clip_count"], 2)

    def test_named_component_material_derives_from_audience_inventory(
        self,
    ) -> None:
        first = self.make_video("audience-red.mp4", "red")
        second = self.make_video("audience-blue.mp4", "blue")
        event = "ac4921_027"
        ledger = self.root / "audience-ledger.csv"
        ledger.write_text(
            "event_name,code_hex,clip_count,resolved_clip_count,"
            "classification,production_state,disposition\n"
            f"{event},0x01,2,2,mixed_full_frame_and_components,"
            "planned_unproduced,gameplay_effect_collection\n",
            encoding="utf-8",
        )
        clips = self.root / "audience-clips.csv"
        clips.write_text(
            "event_name,z2d_order,dgm_order,official_name,target_mp4,"
            "interval_confidence\n"
            f"{event},1,0,{first.stem},{first},exact_duration_unique\n"
            f"{event},1,1,{second.stem},{second},exact_duration_unique\n",
            encoding="utf-8",
        )
        plan = {
            "collection": "named_audience_component_evidence",
            "component_events": [event],
            "component_native_dimensions": {"width": 96, "height": 64},
            "derive_clips_from_audience_event_catalog": True,
            "audience_event_index": {
                "path": str(ledger),
                "sha256": file_sha256(ledger),
                "production_state": "planned_unproduced",
                "disposition": "gameplay_effect_collection",
                "classification": "mixed_full_frame_and_components",
            },
            "audience_clip_index": {
                "path": str(clips),
                "sha256": file_sha256(clips),
            },
        }
        plan_path = self.root / "named-audience-component-plan.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        row = build_named_collection(
            plan_path,
            {
                first.stem: {"target_mp4": str(first)},
                second.stem: {"target_mp4": str(second)},
            },
            self.out,
            "ffmpeg",
            "ffprobe",
            False,
        )
        manifest = json.loads(Path(row["manifest"]).read_text(encoding="utf-8"))
        self.assertEqual(manifest["component_events"], [event])
        self.assertEqual(
            manifest["component_event_clip_map"][event],
            [first.stem, second.stem],
        )
        evidence_paths = {
            Path(value["path"]).resolve()
            for value in manifest["evidence_sources"]
        }
        self.assertEqual(evidence_paths, {ledger.resolve(), clips.resolve()})

    def test_named_material_rejects_evidence_source_hash_mismatch(self) -> None:
        first = self.make_video("mismatch-red.mp4", "red")
        second = self.make_video("mismatch-blue.mp4", "blue")
        evidence = self.root / "mismatch-production.json"
        evidence.write_text('{"event":"ac0001_001"}\n', encoding="utf-8")
        plan = {
            "collection": "named_evidence_mismatch",
            "clips": [
                {"official_name": "mismatch_red", "label": "red"},
                {"official_name": "mismatch_blue", "label": "blue"},
            ],
            "evidence_sources": [
                {
                    "label": "event production manifest",
                    "path": str(evidence),
                    "sha256": "A" * 64,
                }
            ],
        }
        plan_path = self.root / "named-evidence-mismatch-plan.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        video_map = {
            "mismatch_red": {"target_mp4": str(first)},
            "mismatch_blue": {"target_mp4": str(second)},
        }

        with self.assertRaisesRegex(
            ValueError, "named material evidence SHA-256 mismatch"
        ):
            build_named_collection(
                plan_path,
                video_map,
                self.out,
                "ffmpeg",
                "ffprobe",
                False,
            )

    def test_named_material_rejects_unbound_covered_event(self) -> None:
        first = self.make_video("covered-red.mp4", "red")
        second = self.make_video("covered-blue.mp4", "blue")
        evidence = self.root / "covered-production.json"
        evidence.write_text(
            '{"schema":"magireco-event-production-v3",'
            '"event":"ac0001_001"}\n',
            encoding="utf-8",
        )
        plan = {
            "collection": "named_covered_event_mismatch",
            "covered_events": ["ac0001_002"],
            "clips": [
                {"official_name": "covered_red", "label": "red"},
                {"official_name": "covered_blue", "label": "blue"},
            ],
            "evidence_sources": [
                {
                    "label": "event production manifest",
                    "path": str(evidence),
                    "sha256": file_sha256(evidence),
                }
            ],
        }
        plan_path = self.root / "named-covered-mismatch-plan.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        video_map = {
            "covered_red": {"target_mp4": str(first)},
            "covered_blue": {"target_mp4": str(second)},
        }

        with self.assertRaisesRegex(
            ValueError, "covered_events do not match bound event production"
        ):
            build_named_collection(
                plan_path,
                video_map,
                self.out,
                "ffmpeg",
                "ffprobe",
                False,
            )

    def test_named_material_applies_explicit_durable_source_root_override(
        self,
    ) -> None:
        old_root = self.root / "old-root"
        durable_root = self.root / "durable-root"
        old_media = old_root / "official"
        durable_media = durable_root / "official"
        old_media.mkdir(parents=True)
        durable_media.mkdir(parents=True)
        first = self.make_video("override-red-source.mp4", "red")
        second = self.make_video("override-blue-source.mp4", "blue")
        durable_first = durable_media / "red.mp4"
        durable_second = durable_media / "blue.mp4"
        shutil.copy2(first, durable_first)
        shutil.copy2(second, durable_second)
        plan = {
            "collection": "named_durable_override",
            "source_root_overrides": [
                {"from": str(old_root), "to": str(durable_root)}
            ],
            "clips": [
                {"official_name": "override_red", "label": "red"},
                {"official_name": "override_blue", "label": "blue"},
            ],
        }
        plan_path = self.root / "named-durable-override-plan.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        video_map = {
            "override_red": {"target_mp4": str(old_media / "red.mp4")},
            "override_blue": {"target_mp4": str(old_media / "blue.mp4")},
        }

        row = build_named_collection(
            plan_path,
            video_map,
            self.out,
            "ffmpeg",
            "ffprobe",
            False,
        )
        manifest = json.loads(Path(row["manifest"]).read_text(encoding="utf-8"))
        self.assertEqual(
            [Path(item["path"]) for item in manifest["sources"]],
            [durable_first.resolve(), durable_second.resolve()],
        )
        self.assertEqual(
            manifest["source_root_overrides"],
            [{"from": str(old_root), "to": str(durable_root.resolve())}],
        )


if __name__ == "__main__":
    unittest.main()
