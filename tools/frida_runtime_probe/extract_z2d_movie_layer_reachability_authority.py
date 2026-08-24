#!/usr/bin/env python3
"""Resolve MovieLayer timing, geometry, blend state, and CRI-name reachability."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Sequence

try:
    from .extract_z2d_movie_layer_blend_authority import (
        BLEND_STATE_TABLE_VA,
        CODE_AUTHORITY,
        SLOT_BINARY_SHA256,
        BlendAuthorityError,
        parse_z2d_header,
        read_filename_table,
        resolve_movie_layer_resources,
        validate_exact_binary,
    )
except ImportError:  # pragma: no cover - direct script execution
    from extract_z2d_movie_layer_blend_authority import (  # type: ignore
        BLEND_STATE_TABLE_VA,
        CODE_AUTHORITY,
        SLOT_BINARY_SHA256,
        BlendAuthorityError,
        parse_z2d_header,
        read_filename_table,
        resolve_movie_layer_resources,
        validate_exact_binary,
    )


SCHEMA = "magireco-z2d-movielayer-reachability-authority-v1"


def build_report(
    *, binary: Path, z2d_manifest: Path, filename_table_csv: Path
) -> dict[str, Any]:
    build_id, blend_states, blend_table_offset = validate_exact_binary(binary)
    manifest = json.loads(z2d_manifest.read_text(encoding="utf-8"))
    if (
        manifest.get("schema") != "magireco-exact-apk-named-z2d-extraction-v1"
        or manifest.get("status") != "passed"
    ):
        raise BlendAuthorityError("named Z2D extraction did not pass")
    compiled_names = read_filename_table(filename_table_csv)
    chunks: list[dict[str, Any]] = []
    for source in manifest.get("chunks", []):
        path = Path(str(source["output_path"]))
        data = path.read_bytes()
        header = parse_z2d_header(data)
        if header["filename"] != f"{source['name']}.z2d":
            raise BlendAuthorityError(f"Z2D filename differs: {source['name']}")
        layers, movie_resource_tables = resolve_movie_layer_resources(
            data,
            blend_state_table=blend_states,
            manifest_dgm_references=source.get("dgm_references", []),
        )
        for layer in layers:
            if (
                int(layer["start_frame"]) < int(header["scene_start_frame"])
                or int(layer["end_frame_inclusive"])
                > int(header["scene_end_frame_inclusive"])
            ):
                raise BlendAuthorityError(
                    f"MovieLayer exceeds parent Z2D frame range: "
                    f"{source['name']}/{layer['authored_layer_reference']}"
                )
            base_name = str(layer["z2d_reference"]).removesuffix(".dgm")
            table_index = compiled_names.get(base_name)
            layer.update(
                {
                    "cri_lookup_base_name": base_name,
                    "compiled_table_present": table_index is not None,
                    "compiled_table_index": table_index,
                    "runtime_load_disposition": (
                        "LOADABLE_BY_EXACT_NAME"
                        if table_index is not None
                        else "UNREACHABLE_LOADUSMFILEBYNAME_RETURNS_FALSE"
                    ),
                }
            )
        chunks.append(
            {
                "name": source["name"],
                "path": str(path.resolve()),
                "chunk_index": int(source["chunk_index"]),
                "chunk_offset": int(source["offset"]),
                "chunk_size": int(source["size"]),
                "header": header,
                "movie_layers": layers,
                "movie_layer_count": len(layers),
                "movie_resource_tables": movie_resource_tables,
            }
        )
    all_layers = [layer for chunk in chunks for layer in chunk["movie_layers"]]
    if not chunks or not all_layers:
        raise BlendAuthorityError("bounded Z2D set has no authored MovieLayer")
    geometry_counts: dict[str, int] = {}
    for layer in all_layers:
        key = (
            f"{layer['layer_width']}x{layer['layer_height']}@"
            f"{layer['position'][0]},{layer['position'][1]}|"
            f"pivot={layer['pivot'][0]},{layer['pivot'][1]}"
        )
        geometry_counts[key] = geometry_counts.get(key, 0) + 1
    loadable = sum(bool(layer["compiled_table_present"]) for layer in all_layers)
    return {
        "schema": SCHEMA,
        "status": "passed",
        "binary": {
            "path": str(binary.resolve()),
            "size": binary.stat().st_size,
            "gnu_build_id": build_id,
            "inherited_sha256": SLOT_BINARY_SHA256,
        },
        "inputs": {
            "named_z2d_manifest": str(z2d_manifest.resolve()),
            "compiled_crivideo_filename_table": str(filename_table_csv.resolve()),
        },
        "blend_state_table": {
            "virtual_address_hex": f"0x{BLEND_STATE_TABLE_VA:x}",
            "file_offset_hex": f"0x{blend_table_offset:x}",
            "entry_count": len(blend_states),
            "renderer_states_by_blend_enum": blend_states,
            "default_renderer_state_for_enum_0_or_outside_table": 1,
        },
        "code_authority": [
            {"address": address, "function": function, "proves": proves}
            for address, function, proves in CODE_AUTHORITY
        ],
        "counts": {
            "z2d_chunks": len(chunks),
            "movie_layers": len(all_layers),
            "loadable_movie_layers": loadable,
            "unreachable_movie_layers": len(all_layers) - loadable,
            "layer_names_differing_from_media_names": sum(
                bool(layer["layer_name_differs_from_movie_media_reference"])
                for layer in all_layers
            ),
            "geometry_contracts": geometry_counts,
        },
        "z2d_chunks": chunks,
        "assertions": {
            "all_movie_layers_bound_to_exact_pubroot_movie_resources": True,
            "all_movie_layers_within_parent_frame_ranges": True,
            "non_fullscreen_components_preserved_without_normalization": True,
            "unreachable_names_not_substituted": True,
            "machine_vision_used_as_authority": False,
            "media_reencoded": False,
        },
    }


def write_outputs(report: dict[str, Any], output_dir: Path) -> None:
    if output_dir.exists():
        raise BlendAuthorityError(f"refusing to overwrite output directory: {output_dir}")
    output_dir.mkdir(parents=True)
    report_path = output_dir / "Z2D_MOVIELAYER_REACHABILITY_AUTHORITY.json"
    rows = []
    for chunk in report["z2d_chunks"]:
        for layer in chunk["movie_layers"]:
            rows.append(
                {
                    "z2d_name": chunk["name"],
                    "z2d_scene_frame_count": chunk["header"]["scene_frame_count"],
                    **layer,
                }
            )
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    csv_path = output_dir / "Z2D_MOVIELAYERS.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    verification = {
        "schema": "magireco-z2d-movielayer-reachability-verification-v1",
        "status": "passed",
        "counts": report["counts"],
        "outputs": [report_path.name, csv_path.name],
        "literal_result": (
            f"PASS z2d={report['counts']['z2d_chunks']} "
            f"movie_layers={report['counts']['movie_layers']} "
            f"loadable={report['counts']['loadable_movie_layers']} "
            f"unreachable={report['counts']['unreachable_movie_layers']}"
        ),
    }
    (output_dir / "VERIFICATION_RECORD.json").write_text(
        json.dumps(verification, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--z2d-manifest", required=True, type=Path)
    parser.add_argument("--filename-table-csv", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(
        binary=args.binary,
        z2d_manifest=args.z2d_manifest,
        filename_table_csv=args.filename_table_csv,
    )
    write_outputs(report, args.output_dir)
    print(
        f"PASS z2d={report['counts']['z2d_chunks']} "
        f"movie_layers={report['counts']['movie_layers']} "
        f"loadable={report['counts']['loadable_movie_layers']} "
        f"unreachable={report['counts']['unreachable_movie_layers']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
