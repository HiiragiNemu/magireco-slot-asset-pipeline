import tempfile
import unittest
from pathlib import Path

from tools.frida_runtime_probe import resolve_ac4903_exhaustive_authority as target


class ResolveAc4903ExhaustiveAuthorityTests(unittest.TestCase):
    def test_editorial_order_places_victory_after_all_entry_variants(self) -> None:
        self.assertEqual(target.EDITORIAL_ORDER[-3:], ("ac4903_016", "ac4903_018", "ac4903_015"))

    def test_resolve_routes_closes_all_twenty_two_rows(self) -> None:
        rows = []
        for index, route in enumerate(target.EXPECTED_ROUTES):
            for event in route:
                rows.append({"kind": "114", "row_index": str(index), "scene_name": event})
        resolved = target.resolve_routes(rows)
        self.assertEqual(len(resolved), 22)
        self.assertEqual(resolved[14]["events"], ["ac4903_001", "ac4903_007", "ac4903_015"])

    def test_resolve_routes_rejects_reordered_route(self) -> None:
        rows = []
        for index, route in enumerate(target.EXPECTED_ROUTES):
            values = list(route)
            if index == 0:
                values.reverse()
            for event in values:
                rows.append({"kind": "114", "row_index": str(index), "scene_name": event})
        with self.assertRaises(target.Ac4903AuthorityError):
            target.resolve_routes(rows)

    def test_renderer_contract_requires_exact_reverse_then_forward_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "libGameProc.so"
            binary.write_bytes(b"slot")
            value = {
                "schema": "magireco-ida-z2d-renderer-order-extract-v1",
                "status": "PASS",
                "input_path": str(binary),
                "targets": [
                    {
                        "label": "RendererImplGL_setBlendMode",
                        "decompile_error": "",
                        "pseudocode": (
                            "glBlendFuncSeparate(770, 1, 1, 1); "
                            "n770 = 770; n768 = 771;"
                        ),
                    },
                    {
                        "label": "CZ2DPlayer_DrawLayer",
                        "decompile_error": "",
                        "pseudocode": "v24 + 8LL * (unsigned int)(v23 - 1); --v23;",
                    },
                    {
                        "label": "CZ2DPlayGlobal_GetNextPrim",
                        "decompile_error": "",
                        "pseudocode": (
                            "*(_DWORD *)(v4 + 440) = v5 + 1; "
                            "*(_QWORD *)(v7 + 8 * v5) = result;"
                        ),
                    },
                    {
                        "label": "CZ2DPlayBufferHandle_Exec_Sort",
                        "decompile_error": "",
                        "pseudocode": "equal depth stable run",
                    },
                    {
                        "label": "CZ2DPlayBufferHandle_Exec_Draw",
                        "decompile_error": "",
                        "pseudocode": "v14 = *(__int64 **)(v12 + 464); ++v14;",
                    },
                ],
            }
            contract = target.validate_renderer_authority(value, binary)
            self.assertEqual(
                contract["renderer_state_3"]["gl_blend_func_separate"],
                [770, 1, 1, 1],
            )
            value["targets"][1]["pseudocode"] = "forward only"
            with self.assertRaises(target.Ac4903AuthorityError):
                target.validate_renderer_authority(value, binary)

    def test_event_manifests_close_exact_4204_frame_editorial_timeline(self) -> None:
        runtime = {event: {"event_code": f"code-{event}"} for event in target.EVENTS}
        visual = {
            event: max(end + 1 for _, _, end, _ in target.PARENT_BINDINGS[event])
            for event in target.EVENTS
        }
        occurrences = []
        for event in target.EVENTS:
            occurrences.append({
                "event": event,
                "parent_composition_order": 0,
                "authored_tag_index": 0,
                "event_end_frame_exclusive": visual[event],
            })
        audio_rows = []
        for event in ("ac4903_007", "ac4903_016", "ac4903_018"):
            audio_rows.append({"event": event, "start_ms": 0, "duration_ms": 5500})
        movie = {"loadable_occurrences": occurrences}
        audio = {
            "retained_audio_rows": audio_rows,
            "excluded_bgm_rows": [],
            "subtitle_cues": [],
        }
        manifests = target.event_manifests(runtime, movie, audio)
        self.assertEqual(sum(row["presentation_frames"] for row in manifests.values()), 4204)
        self.assertEqual(manifests["ac4903_007"]["presentation_frames"], 165)
        self.assertEqual(manifests["ac4903_015"]["visual_frames"], 260)


if __name__ == "__main__":
    unittest.main()
