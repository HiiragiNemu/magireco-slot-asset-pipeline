import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools.frida_runtime_probe.verify_strict_no_bgm_sound_bus_checkpoint import (
    validate_checkpoint,
)


PLAN = (
    Path(__file__).resolve().parent
    / "tools"
    / "frida_runtime_probe"
    / "series_proposals"
    / "strict_no_bgm_sound_bus_corrections_v69_20260813.json"
)


class StrictNoBgmSoundBusCheckpointTest(unittest.TestCase):
    def setUp(self):
        self.value = json.loads(PLAN.read_text(encoding="utf-8"))

    def test_repository_checkpoint_contract(self):
        self.assertEqual(
            validate_checkpoint(self.value),
            {"products": 3, "media": 9, "inventory_items": 9, "withdrawals": 7},
        )

    def test_rejects_bgm_request_retained(self):
        value = copy.deepcopy(self.value)
        value["products"][0]["retained_request_ids"].append("228")
        with self.assertRaisesRegex(ValueError, "retained request"):
            validate_checkpoint(value)

    def test_rejects_ac1103_merged_voice_loss(self):
        value = copy.deepcopy(self.value)
        value["products"][2]["merged_voice_request_ids"] = ["4058"]
        with self.assertRaisesRegex(ValueError, "merged adjacent voice"):
            validate_checkpoint(value)

    def test_local_artifact_mode_binds_hash(self):
        value = copy.deepcopy(self.value)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            media = root / "sample.mp4"
            media.write_bytes(b"sample")
            import hashlib

            digest = hashlib.sha256(b"sample").hexdigest().upper()
            # The first mismatch must be this deliberately rebound media row.
            value["products"][0]["media"]["none"] = {
                "path": str(media),
                "sha256": digest,
            }
            # Other real D: paths are not required for this focused assertion;
            # mutate the first hash and ensure the verifier catches it first.
            value["products"][0]["media"]["none"]["sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "SHA-256 differs"):
                validate_checkpoint(value, verify_local=True)


if __name__ == "__main__":
    unittest.main()
