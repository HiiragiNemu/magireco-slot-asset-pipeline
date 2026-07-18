from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from reproducibility.scripts.fetch_font_dependencies import (
    DEFAULT_CACHE_DIR,
    DEFAULT_MANIFEST,
    FontDependencyError,
    load_manifest,
    materialize_dependencies,
)
from tools.frida_runtime_probe.subtitle_edition_contract import (
    load_font_config,
    required_visible_codepoints,
    validate_font_binding,
)


ROOT = Path(__file__).resolve().parent
FONT_ID = "noto-sans-cjk-sc-2.004-variable-ttf"
FONT_RELATIVE_PATH = Path("noto-sans-cjk-sc-2.004/NotoSansSC-VF.ttf")
PINNED_FONT_SHA256 = (
    "D68BAFCB48A2707749396AA12BBBD833CB70401F3A9A689FD2902C7E0D295964"
)


def synthetic_manifest(font_payload: bytes, license_payload: bytes) -> dict:
    commit = "1" * 40

    def spec(role: str, path: str, payload: bytes) -> dict:
        return {
            "role": role,
            "path": path,
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest().upper(),
            "url": f"https://example.invalid/{commit}/{path}",
        }

    return {
        "schema": "magireco-font-dependencies-v1",
        "dependencies": {
            "synthetic": {
                "version": "test",
                "upstream": {"commit": commit},
                "license": {
                    "spdx": "OFL-1.1",
                    "file": "synthetic/OFL.txt",
                },
                "files": [
                    spec("font", "synthetic/font.ttf", font_payload),
                    spec("license", "synthetic/OFL.txt", license_payload),
                ],
            }
        },
    }


class FontDependencyCacheTests(unittest.TestCase):
    def test_repository_lock_uses_immutable_official_upstream_and_ofl(self) -> None:
        manifest = load_manifest(DEFAULT_MANIFEST)
        dependency = manifest["dependencies"][FONT_ID]
        self.assertEqual(dependency["version"], "2.004")
        self.assertEqual(dependency["license"]["spdx"], "OFL-1.1")
        self.assertEqual(
            dependency["upstream"]["commit"],
            "523d033d6cb47f4a80c58a35753646f5c3608a78",
        )
        by_role = {row["role"]: row for row in dependency["files"]}
        self.assertEqual(by_role["font"]["bytes"], 17_773_132)
        self.assertEqual(by_role["font"]["sha256"], PINNED_FONT_SHA256)
        self.assertIn(dependency["upstream"]["commit"], by_role["font"]["url"])
        self.assertEqual(by_role["license"]["bytes"], 4_301)
        self.assertEqual(
            by_role["license"]["sha256"],
            "6A73F9541C2DE74158C0E7CF6B0A58EF774F5A780BF191F2D7EC9CC53EFE2BF2",
        )

    def test_offline_mode_reuses_valid_cache_and_rejects_missing_file(self) -> None:
        font = b"synthetic-font"
        license_text = b"synthetic-ofl"
        manifest = synthetic_manifest(font, license_text)
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = Path(temp_dir)
            (cache / "synthetic").mkdir()
            (cache / "synthetic/font.ttf").write_bytes(font)
            license_path = cache / "synthetic/OFL.txt"
            license_path.write_bytes(license_text)

            audit = materialize_dependencies(
                manifest, cache_dir=cache, offline=True
            )
            rows = audit["dependencies"]["synthetic"]["files"]
            self.assertEqual([row["status"] for row in rows], ["cached", "cached"])
            self.assertTrue(all(row["verified"] for row in rows))

            license_path.unlink()
            with self.assertRaisesRegex(FontDependencyError, "missing"):
                materialize_dependencies(manifest, cache_dir=cache, offline=True)

    def test_download_is_hash_checked_and_corrupt_cache_needs_repair(self) -> None:
        font = b"synthetic-font"
        license_text = b"synthetic-ofl"
        manifest = synthetic_manifest(font, license_text)
        payloads = {
            row["url"]: font if row["role"] == "font" else license_text
            for row in manifest["dependencies"]["synthetic"]["files"]
        }
        calls: list[str] = []

        def download(url: str) -> bytes:
            calls.append(url)
            return payloads[url]

        with tempfile.TemporaryDirectory() as temp_dir:
            cache = Path(temp_dir)
            audit = materialize_dependencies(
                manifest, cache_dir=cache, download=download
            )
            self.assertEqual(len(calls), 2)
            self.assertTrue(
                all(
                    row["status"] == "downloaded"
                    for row in audit["dependencies"]["synthetic"]["files"]
                )
            )

            font_path = cache / "synthetic/font.ttf"
            font_path.write_bytes(b"corrupt")
            calls.clear()
            with self.assertRaisesRegex(FontDependencyError, "--repair"):
                materialize_dependencies(
                    manifest, cache_dir=cache, download=download
                )
            self.assertEqual(calls, [])

            repaired = materialize_dependencies(
                manifest, cache_dir=cache, repair=True, download=download
            )
            self.assertEqual(calls, [manifest["dependencies"]["synthetic"]["files"][0]["url"]])
            self.assertEqual(
                repaired["dependencies"]["synthetic"]["files"][0]["status"],
                "repaired",
            )
            self.assertEqual(font_path.read_bytes(), font)

    def test_ac7114_16_candidate_set_is_exactly_34_codepoints_and_unapproved(
        self,
    ) -> None:
        coverage_path = (
            ROOT / "reproducibility/fonts/ac7114_16.zh-candidate-coverage.json"
        )
        coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
        cues = [
            cue
            for event in coverage["events"]
            for cue in event["cues"]
        ]
        actual = required_visible_codepoints(cues)
        expected = {
            int(value.removeprefix("U+"), 16)
            for value in coverage["required_codepoints"]
        }
        self.assertEqual(len(cues), 10)
        self.assertEqual(len(actual), 34)
        self.assertEqual(actual, expected)
        self.assertEqual(coverage["translation_status"], "NOT_HUMAN_APPROVED")
        self.assertFalse(coverage["release_eligible"])

    @unittest.skipUnless(
        (DEFAULT_CACHE_DIR / FONT_RELATIVE_PATH).is_file(),
        "run fetch_font_dependencies.py once to enable real Noto cmap coverage",
    )
    def test_pinned_noto_font_really_covers_all_34_candidate_codepoints(self) -> None:
        coverage = json.loads(
            (
                ROOT
                / "reproducibility/fonts/ac7114_16.zh-candidate-coverage.json"
            ).read_text(encoding="utf-8")
        )
        cues = [
            cue
            for event in coverage["events"]
            for cue in event["cues"]
        ]
        config_path = (
            ROOT / "reproducibility/fonts/ac7114_16.zh-font-config.draft.json"
        )
        config = load_font_config(config_path)
        result = validate_font_binding("zh", cues, config)
        assert result is not None
        self.assertEqual(result["sha256"], PINNED_FONT_SHA256)
        self.assertEqual(result["family"], "Noto Sans SC")
        self.assertEqual(result["required_codepoint_count"], 34)
        self.assertTrue(result["coverage_complete"])
        self.assertEqual(
            result["source"]["kind"], "audited_chinese_fallback"
        )
        self.assertFalse(config["release_eligible"])


if __name__ == "__main__":
    unittest.main()
