import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


MODULE_PATH = Path(__file__).parent / "tools" / "frida_runtime_probe" / "build_ac0908_exhaustive_authoritative_longform.py"
SPEC = importlib.util.spec_from_file_location("build_ac0908_exhaustive_authoritative_longform", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class BuildAc0908ExhaustiveAuthoritativeLongformTests(unittest.TestCase):
    def test_chapters_cover_all_events_once_or_as_exact_alias(self):
        events = [event for row in MODULE.CHAPTERS for event in row[3]]
        self.assertEqual(sorted(events), [f"ac0908_{index:03d}" for index in range(1, 18)])
        self.assertEqual(events[:2], ["ac0908_001", "ac0908_009"])
        self.assertEqual(len(MODULE.CHAPTERS), 14)
        self.assertEqual(sum(row[2] for row in MODULE.CHAPTERS), 3915)

    def test_chapter_metadata_uses_exact_frame_timebase(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "chapters.ffmeta"
            rows = MODULE._write_chapters(path)
            text = path.read_text(encoding="utf-8")
        self.assertEqual(rows[-1]["end_frame_exclusive"], 3915)
        self.assertEqual(text.count("[CHAPTER]"), 14)
        self.assertIn("TIMEBASE=1/30", text)
        self.assertIn("END=3915", text)

    def test_final_filter_has_fourteen_av_inputs_and_exact_tail(self):
        value = MODULE._final_filter()
        self.assertIn("concat=n=14:v=1:a=1[v][a]", value)
        self.assertIn("atrim=start_sample=0:end_sample=264000", value)
        self.assertIn("atrim=start_sample=0:end_sample=796800", value)

    def test_outcome_contract_excludes_bgm_codes(self):
        retained = {row[1] for row in MODULE.OUTCOMES.values()}
        self.assertEqual(retained, {1004, 1005, 1008, 1010})
        self.assertTrue(retained.isdisjoint({551, 552, 553}))

    def test_argb_reconstruction_vflips_both_streams_once_without_hflip(self):
        value = ";".join(MODULE._argb_filter(3, "x", 60, True))
        self.assertEqual(value.count("vflip"), 2)
        self.assertNotIn("hflip", value)
        self.assertIn("[3:v:0]format=rgb24,vflip", value)
        self.assertIn("[3:v:1]format=gray,vflip", value)
        self.assertLess(value.index("vflip"), value.index("alphamerge"))

    def test_published_path_rewrites_only_staging_members(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            staging = base / "stage"
            output = base / "release"
            inside = staging / "HUMAN_REVIEW" / "ZH" / "story" / "clip.mp4"
            outside = base / "source.mp4"
            self.assertEqual(
                MODULE._published_path(inside, staging, output),
                str(output / "HUMAN_REVIEW" / "ZH" / "story" / "clip.mp4"),
            )
            self.assertEqual(MODULE._published_path(outside, staging, output), str(outside.resolve()))

    def test_v153_checkpoint_covers_all_events_and_demotes_old_showcase(self):
        checkpoint = json.loads(
            (
                Path(__file__).resolve().parent
                / "tools"
                / "frida_runtime_probe"
                / "series_proposals"
                / "ac0908_exhaustive_authoritative_longform_v153_20260824.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(checkpoint["event_container_count"], 17)
        self.assertEqual(checkpoint["canonical_unique_presentation_count"], 14)
        self.assertEqual(checkpoint["exact_duplicate_presentation_surplus_count"], 3)
        self.assertEqual(checkpoint["event_coverage"], [f"ac0908_{i:03d}" for i in range(1, 18)])
        self.assertEqual(checkpoint["presentation_frames"], 3915)
        self.assertEqual(
            checkpoint["ac0908_016_resource_resolution"]["unresolved_missing_media"],
            [],
        )
        self.assertFalse(
            checkpoint["legacy_disposition"]["A0007_ac0908_001_to_009_reference_complete"]
        )
        self.assertTrue(checkpoint["human_playback_required"])
        self.assertFalse(checkpoint["publication_approved"])


if __name__ == "__main__":
    unittest.main()
