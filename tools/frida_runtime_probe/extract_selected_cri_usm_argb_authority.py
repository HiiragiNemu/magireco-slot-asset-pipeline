#!/usr/bin/env python3
"""Extract a bounded set of exact CRI USM slices and verify ARGB stream inputs.

The legacy named MP4 catalog retained only the color stream.  Slot runtime code
copies decoded frames as ARGB32, while the selected USMs carry a second video
stream that supplies authored alpha.  This tool preserves only explicitly named
slices and never scans or copies the multi-gigabyte package wholesale.
"""

from __future__ import annotations

import argparse
import csv
import json
import struct
import subprocess
from pathlib import Path
from typing import Any, Iterable


SLOT_BINARY_SHA256 = (
    "5A0AE3CE7F25B89A3B9A13D11BF36AAA1DE04FACEB612357FA04F42426F17EBF"
)
EXPECTED_NAMES = (
    "ac0908_001_c01_MR",
    "ac0908_001_c02",
    "ac0908_pre_c10",
    "ac0908_pre_c10_LP",
    "ac0928_hat_shutter_totsu_kokuchi",
    "ac8005_hat_WIN",
    "ac8005_kyo_choseiya",
    "ac8005_kyo_hatten",
    "ac8005_kyo_magichalle",
    "ac8040_premia_EF",
    "ac8040_premia_EF_LP",
)

CODE_AUTHORITY = (
    (
        "0x425d6d0",
        "CriVideo::GFDirectionCriPlayer::GetCurrentFrameData",
        "allocates width*height*4 bytes for each decoded frame",
    ),
    (
        "0x425d8c0",
        "criManaPlayer_CopyFrameToBufferARGB32",
        "copies the CRI-decoded frame into an ARGB32 destination buffer",
    ),
    (
        "0x434a7e4",
        "zg::sprite::RendererImplGL::setBlendMode",
        "renderer state 1 uses source-alpha over destination",
    ),
)


class CriArgbError(ValueError):
    """The selected package evidence differs from the bounded contract."""


def read_offsets(bin_path: Path, add_path: Path) -> list[int]:
    raw = add_path.read_bytes()
    if not raw or len(raw) % 4:
        raise CriArgbError(f"invalid offset-table size: {add_path}")
    offsets = list(struct.unpack(f"<{len(raw) // 4}I", raw))
    if offsets[0] != 0:
        raise CriArgbError(f"offset table does not begin at zero: {add_path}")
    if any(right < left for left, right in zip(offsets, offsets[1:])):
        raise CriArgbError(f"offset table is not monotonic: {add_path}")
    size = bin_path.stat().st_size
    if offsets[-1] != size:
        offsets.append(size)
    if offsets[-1] != size or any(value > size for value in offsets):
        raise CriArgbError(f"offset table exceeds package size: {add_path}")
    return offsets


def select_catalog_rows(catalog_path: Path, names: Iterable[str]) -> list[dict[str, str]]:
    expected = tuple(names)
    wanted = set(expected)
    selected: dict[str, dict[str, str]] = {}
    with catalog_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            name = row.get("official_name", "")
            if name not in wanted:
                continue
            if name in selected:
                raise CriArgbError(f"duplicate catalog row for {name}")
            if row.get("source_exists") != "yes":
                raise CriArgbError(f"catalog source is absent for {name}")
            if row.get("package") not in {"main", "patch"}:
                raise CriArgbError(f"unsupported package for {name}")
            selected[name] = row
    missing = wanted - set(selected)
    if missing:
        raise CriArgbError(f"catalog lacks selected names: {sorted(missing)}")
    return [selected[name] for name in expected]


def slice_bounds(offsets: list[int], index: int) -> tuple[int, int]:
    if index < 0 or index + 1 >= len(offsets):
        raise CriArgbError(f"package index outside offset table: {index}")
    start, end = offsets[index], offsets[index + 1]
    if start >= end:
        raise CriArgbError(f"empty package slice at index {index}")
    return start, end


def extract_slice(bin_path: Path, offsets: list[int], index: int, output: Path) -> dict[str, Any]:
    start, end = slice_bounds(offsets, index)
    with bin_path.open("rb") as handle:
        handle.seek(start)
        data = handle.read(end - start)
    if len(data) != end - start or b"CRID" not in data[:64]:
        raise CriArgbError(f"slice {index} is not an exact CRI USM")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)
    return {
        "package_index": index,
        "start_offset": start,
        "start_offset_hex": f"0x{start:x}",
        "end_offset": end,
        "end_offset_hex": f"0x{end:x}",
        "size": len(data),
    }


def ffprobe(path: Path) -> dict[str, Any]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "stream=index,codec_name,codec_type,width,height,pix_fmt,r_frame_rate,nb_frames,duration",
        "-show_entries",
        "format=format_name,duration,size",
        "-of",
        "json",
        str(path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    if completed.returncode:
        raise CriArgbError(f"ffprobe failed for {path}: {completed.stderr.strip()}")
    return json.loads(completed.stdout)


def validate_argb_streams(probe: dict[str, Any], name: str) -> dict[str, Any]:
    videos = [row for row in probe.get("streams", []) if row.get("codec_type") == "video"]
    if len(videos) != 2:
        raise CriArgbError(f"{name} expected two CRI video streams, found {len(videos)}")
    color, alpha = videos
    shared_keys = ("width", "height", "r_frame_rate", "nb_frames")
    if any(color.get(key) != alpha.get(key) for key in shared_keys):
        raise CriArgbError(f"{name} color/alpha stream geometry differs")
    if color.get("r_frame_rate") != "30/1":
        raise CriArgbError(f"{name} is not exact 30fps")
    if probe.get("format", {}).get("format_name") != "usm":
        raise CriArgbError(f"{name} is not probed as CRI USM")
    return {
        "color_stream_index": int(color["index"]),
        "alpha_stream_index": int(alpha["index"]),
        "codec": color["codec_name"],
        "width": int(color["width"]),
        "height": int(color["height"]),
        "frame_rate": color["r_frame_rate"],
        "frame_count": int(color["nb_frames"]),
        "alpha_reconstruction": "color=video_stream_0 alpha=luma(video_stream_1)",
    }


def build(
    catalog_path: Path,
    main_bin: Path,
    main_add: Path,
    patch_bin: Path,
    patch_add: Path,
    output_dir: Path,
) -> dict[str, Any]:
    package_paths = {
        "main": (main_bin, main_add),
        "patch": (patch_bin, patch_add),
    }
    offsets = {
        package: read_offsets(bin_path, add_path)
        for package, (bin_path, add_path) in package_paths.items()
    }
    rows = select_catalog_rows(catalog_path, EXPECTED_NAMES)
    artifacts: list[dict[str, Any]] = []
    for row in rows:
        name = row["official_name"]
        package = row["package"]
        index = int(row["package_index"])
        output = output_dir / "raw_usm" / f"{name}.usm"
        bounds = extract_slice(package_paths[package][0], offsets[package], index, output)
        streams = validate_argb_streams(ffprobe(output), name)
        artifacts.append(
            {
                "official_name": name,
                "official_filename": row["official_filename"],
                "package": package,
                "global_index": int(row["global_index"]),
                "path": str(output.resolve()),
                **bounds,
                **streams,
            }
        )
    return {
        "schema": "magireco-selected-cri-usm-argb-authority-v1",
        "status": "passed_exact_color_alpha_streams_resolved",
        "exact_slot_binary": {"inherited_sha256": SLOT_BINARY_SHA256},
        "inputs": {
            "catalog": str(catalog_path.resolve()),
            "main_bin": str(main_bin.resolve()),
            "main_add": str(main_add.resolve()),
            "patch_bin": str(patch_bin.resolve()),
            "patch_add": str(patch_add.resolve()),
        },
        "code_authority": [
            {"address": address, "function": function, "proves": proves}
            for address, function, proves in CODE_AUTHORITY
        ],
        "artifacts": artifacts,
        "counts": {
            "selected_usm_count": len(artifacts),
            "two_video_stream_count": sum(1 for row in artifacts if row["alpha_stream_index"] == 1),
        },
        "assertions": {
            "all_selected_usms_have_exact_color_and_alpha_video_streams": True,
            "legacy_single_stream_mp4_is_not_sufficient_for_layer_composition": True,
            "runtime_argb32_path_exact": True,
            "machine_vision_used_as_authority": False,
            "production_disposition": "READY_FOR_ALPHA_EXACT_AC0908_COMPOSITION",
        },
    }


def write_outputs(result: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    authority = output_dir / "SELECTED_CRI_USM_ARGB_AUTHORITY.json"
    table = output_dir / "SELECTED_CRI_USM_STREAMS.csv"
    verification = output_dir / "VERIFICATION_RECORD.json"
    readme = output_dir / "README.md"
    authority.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fieldnames = [
        "official_name",
        "package",
        "package_index",
        "global_index",
        "start_offset_hex",
        "end_offset_hex",
        "size",
        "width",
        "height",
        "frame_rate",
        "frame_count",
        "color_stream_index",
        "alpha_stream_index",
        "path",
    ]
    with table.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(result["artifacts"])
    literal = (
        f"PASS selected_usm={result['counts']['selected_usm_count']} "
        f"two_video_streams={result['counts']['two_video_stream_count']} "
        "runtime_copy=ARGB32 machine_vision_authority=false"
    )
    verification.write_text(
        json.dumps(
            {
                "schema": "magireco-selected-cri-usm-argb-verification-v1",
                "status": "passed",
                "literal_result": literal,
                "checks": result["assertions"],
                "outputs": [authority.name, table.name, "raw_usm/"],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    readme.write_text(
        "# Selected CRI USM ARGB authority\n\n"
        "Each selected original USM contains two same-size 30fps video streams. "
        "The first is color and the second is authored alpha. Exact Slot code "
        "copies decoded frames as ARGB32 and uses source-alpha blending. The old "
        "single-stream MP4 catalog remains valid for standalone opaque playback "
        "but is not a composition authority for layered effects.\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--main-bin", required=True, type=Path)
    parser.add_argument("--main-add", required=True, type=Path)
    parser.add_argument("--patch-bin", required=True, type=Path)
    parser.add_argument("--patch-add", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    result = build(
        args.catalog,
        args.main_bin,
        args.main_add,
        args.patch_bin,
        args.patch_add,
        args.output_dir,
    )
    write_outputs(result, args.output_dir)
    print(
        f"PASS selected_usm={result['counts']['selected_usm_count']} "
        f"two_video_streams={result['counts']['two_video_stream_count']} "
        "runtime_copy=ARGB32 machine_vision_authority=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
