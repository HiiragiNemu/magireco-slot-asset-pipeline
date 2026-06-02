from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import struct
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_MANIFEST_DIR = ROOT / "asset_manifests"
DEFAULT_OUTPUT_DIR = ROOT / "organized_assets"

VIDEO_ARCHIVES = {
    "main": (
        ROOT / "downloaded_assets" / "Unpacked_main" / "cri.bin",
        ROOT / "downloaded_assets" / "Unpacked_main" / "cri_add.bin",
    ),
    "patch": (
        ROOT / "downloaded_assets" / "Unpacked_patch" / "cri2.bin",
        ROOT / "downloaded_assets" / "Unpacked_patch" / "cri2_add.bin",
    ),
}

CHUNK_ARCHIVES = {
    "z2d": (
        ROOT / "unpacked_assets" / "assets" / "z2d.bin",
        ROOT / "unpacked_assets" / "assets" / "z2d_add.bin",
        ".z2d",
    ),
    "ogg": (
        ROOT / "unpacked_assets" / "assets" / "ogg.bin",
        ROOT / "unpacked_assets" / "assets" / "ogg_add.bin",
        ".ogg",
    ),
    "pcm": (
        ROOT / "unpacked_assets" / "assets" / "pcm.bin",
        ROOT / "unpacked_assets" / "assets" / "pcm_add.bin",
        ".pcmraw",
    ),
}

GDB_PATH = ROOT / "unpacked_assets" / "assets" / "gdb.bin"
SOUND_ID_PATH = ROOT / "unpacked_assets" / "assets" / "sound_id.dat"
DEBUG_SMALI_FILES = [
    ROOT / "unpacked_base" / "smali" / "debug" / "sub" / "DebugProd.smali",
    ROOT / "unpacked_base" / "smali" / "debug" / "sub" / "DebugDispNameList.smali",
]

PACK_TO_GDB_FILE_VAL = {"main": 1, "patch": 2}
GDB_FILE_VAL_TO_PACK = {v: k for k, v in PACK_TO_GDB_FILE_VAL.items()}
INVALID_NAME_CHARS = re.compile(r'[\\/*?:"<>|\r\n\t]+')
AC_CODE_RE = re.compile(r"^(ac\d{4})", re.IGNORECASE)
AC_CODE_ANY_RE = re.compile(r"(ac\d{4})", re.IGNORECASE)


def safe_name(value: str, fallback: str = "unnamed", max_len: int = 140) -> str:
    value = INVALID_NAME_CHARS.sub("_", value).strip(" ._")
    value = re.sub(r"\s+", " ", value)
    if not value:
        value = fallback
    return value[:max_len].rstrip(" ._") or fallback


def natural_key(value: str):
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)]


def extract_ac_code(value: str) -> str:
    match = AC_CODE_ANY_RE.search(value)
    return match.group(1).lower() if match else ""


def read_offsets(bin_path: Path, add_path: Path) -> list[int]:
    data = add_path.read_bytes()
    offsets = [struct.unpack("<I", data[i : i + 4])[0] for i in range(0, len(data), 4)]
    offsets.append(bin_path.stat().st_size)
    return sorted(set(offsets))


def iter_chunk_rows(kind: str):
    bin_path, add_path, ext = CHUNK_ARCHIVES[kind]
    offsets = read_offsets(bin_path, add_path)
    for idx, start in enumerate(offsets[:-1]):
        end = offsets[idx + 1]
        yield {
            "kind": kind,
            "index": idx,
            "offset": start,
            "size": end - start,
            "source_bin": str(bin_path.relative_to(ROOT)),
            "default_name": f"{kind}_{idx:05d}{ext}",
        }


def decode_smali_string(value: str) -> str:
    try:
        return value.encode("utf-8").decode("unicode_escape")
    except UnicodeError:
        return value


def parse_const_strings(path: Path) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="ignore")
    raw_strings = re.findall(r'const-string(?:/jumbo)?\s+\w+,\s+"((?:\\.|[^"])*)"', text)
    return [decode_smali_string(s) for s in raw_strings]


def load_label_maps():
    code_to_labels: dict[str, list[str]] = defaultdict(list)
    group_index_to_label: dict[int, str] = {}

    for smali_path in DEBUG_SMALI_FILES:
        for value in parse_const_strings(smali_path):
            numbered = re.match(r"^\s*(\d+)\s+(ac\d{4}_.+?)\.?\s*$", value)
            if numbered:
                group_index = int(numbered.group(1))
                label = numbered.group(2).rstrip(".")
                group_index_to_label.setdefault(group_index, label)
                code = label[:6].lower()
                if label not in code_to_labels[code]:
                    code_to_labels[code].append(label)
                continue

            named = re.match(r"^(ac\d{4}[A-Za-z0-9_]*_.+)$", value)
            if named:
                label = named.group(1).rstrip(".")
                code = label[:6].lower()
                if label not in code_to_labels[code]:
                    code_to_labels[code].append(label)

    return code_to_labels, group_index_to_label


def folder_for_asset_name(asset_name: str, code_to_labels: dict[str, list[str]]) -> str:
    code = extract_ac_code(asset_name)
    if not code:
        return "Unclassified"
    label = code_to_labels.get(code, [code])[0]
    return safe_name(label, fallback=code)


def parse_gdb_video_candidates(known_counts: dict[str, int]):
    candidates: dict[tuple[str, int], list[str]] = defaultdict(list)
    if not GDB_PATH.exists():
        return candidates

    data = GDB_PATH.read_bytes()
    pattern = re.compile(rb"(ac\d{4}_[A-Za-z0-9_]+)\x00")
    for match in pattern.finditer(data):
        name = match.group(1).decode("utf-8", errors="ignore")
        chunk = data[match.start() : match.end() + 40]
        gdb_pos = chunk.find(b"GDB")
        if gdb_pos == -1 or gdb_pos < 12:
            continue
        file_val, resource_index, flag = struct.unpack("<III", chunk[gdb_pos - 12 : gdb_pos])
        pack = GDB_FILE_VAL_TO_PACK.get(file_val)
        if not pack or flag != 0:
            continue
        if resource_index >= known_counts.get(pack, 0):
            continue
        key = (pack, resource_index)
        if name not in candidates[key]:
            candidates[key].append(name)

    for names in candidates.values():
        names.sort(key=natural_key)
    return candidates


def parse_named_gdb_refs(extension: str) -> list[str]:
    if not GDB_PATH.exists():
        return []
    data = GDB_PATH.read_bytes()
    pattern = re.compile(rb"([A-Za-z0-9_./-]+\." + re.escape(extension.encode("ascii").lstrip(b".")) + rb")\x00")
    names = {m.group(1).decode("utf-8", errors="ignore") for m in pattern.finditer(data)}
    return sorted(names, key=natural_key)


def parse_sound_id_records() -> list[dict]:
    if not SOUND_ID_PATH.exists():
        return []
    data = SOUND_ID_PATH.read_bytes()
    header_size = 7
    record_size = 12
    if len(data) < header_size or (len(data) - header_size) % record_size != 0:
        return []

    rows = []
    count = (len(data) - header_size) // record_size
    for record_index in range(count):
        pos = header_size + record_index * record_size
        record = data[pos : pos + record_size]
        sound_resource_id = struct.unpack_from("<H", record, 0)[0]
        ogg_chunk_index = struct.unpack_from("<H", record, 2)[0]
        unknown_param = struct.unpack_from("<i", record, 4)[0]
        sound_bank = struct.unpack_from("<H", record, 8)[0]
        marker = struct.unpack_from(">H", record, 10)[0]
        rows.append(
            {
                "record_index": record_index,
                "sound_resource_id": sound_resource_id,
                "ogg_chunk_index": ogg_chunk_index,
                "unknown_param": unknown_param,
                "sound_bank": sound_bank,
                "marker": marker,
                "suggested_name": f"snd_{sound_resource_id:05d}_bank{sound_bank:02d}_ogg_{ogg_chunk_index:05d}.ogg",
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_video_manifest_rows(candidates, code_to_labels):
    rows = []
    for pack, (bin_path, add_path) in VIDEO_ARCHIVES.items():
        offsets = read_offsets(bin_path, add_path)
        for idx, start in enumerate(offsets[:-1]):
            names = candidates.get((pack, idx), [])
            primary = names[0] if len(names) == 1 else ""
            folder = folder_for_asset_name(primary, code_to_labels) if primary else ""
            rows.append(
                {
                    "package": pack,
                    "index": idx,
                    "offset": start,
                    "size": offsets[idx + 1] - start,
                    "default_mp4": f"{pack}_video_{idx:04d}.mp4",
                    "candidate_count": len(names),
                    "primary_name_if_unique": primary,
                    "folder_if_unique": folder,
                    "candidates": ";".join(names),
                }
            )
    return rows


def build_video_audio_scan_rows(candidates):
    markers = [b"CRID", b"@SFV", b"@SFA", b"@ALP", b"@CUE", b"@SBT"]
    rows = []
    for pack, (bin_path, add_path) in VIDEO_ARCHIVES.items():
        offsets = read_offsets(bin_path, add_path)
        with bin_path.open("rb") as src:
            for idx, start in enumerate(offsets[:-1]):
                end = offsets[idx + 1]
                src.seek(start)
                data = src.read(end - start)
                names = candidates.get((pack, idx), [])
                counts = {marker.decode("ascii"): data.count(marker) for marker in markers}
                rows.append(
                    {
                        "package": pack,
                        "index": idx,
                        "offset": start,
                        "size": end - start,
                        "crid_count": counts["CRID"],
                        "sfv_count": counts["@SFV"],
                        "sfa_count": counts["@SFA"],
                        "alp_count": counts["@ALP"],
                        "cue_count": counts["@CUE"],
                        "sbt_count": counts["@SBT"],
                        "has_embedded_audio": "yes" if counts["@SFA"] else "no",
                        "candidate_count": len(names),
                        "primary_name_if_unique": names[0] if len(names) == 1 else "",
                        "candidates": ";".join(names),
                    }
                )
    return rows


def command_video_audio_scan(args):
    manifest_dir = Path(args.manifest_dir)
    known_counts = {pack: len(read_offsets(bin_path, add_path)) - 1 for pack, (bin_path, add_path) in VIDEO_ARCHIVES.items()}
    candidates = parse_gdb_video_candidates(known_counts)
    rows = build_video_audio_scan_rows(candidates)
    write_csv(
        manifest_dir / "video_audio_scan.csv",
        rows,
        [
            "package",
            "index",
            "offset",
            "size",
            "crid_count",
            "sfv_count",
            "sfa_count",
            "alp_count",
            "cue_count",
            "sbt_count",
            "has_embedded_audio",
            "candidate_count",
            "primary_name_if_unique",
            "candidates",
        ],
    )
    embedded = sum(1 for row in rows if row["has_embedded_audio"] == "yes")
    print(f"[video-audio-scan] wrote {len(rows)} rows to {manifest_dir / 'video_audio_scan.csv'}")
    print(f"[video-audio-scan] slices with embedded @SFA audio: {embedded}")


def command_manifest(args):
    manifest_dir = Path(args.manifest_dir)
    code_to_labels, group_index_to_label = load_label_maps()
    known_counts = {pack: len(read_offsets(bin_path, add_path)) - 1 for pack, (bin_path, add_path) in VIDEO_ARCHIVES.items()}
    candidates = parse_gdb_video_candidates(known_counts)

    video_rows = build_video_manifest_rows(candidates, code_to_labels)
    write_csv(
        manifest_dir / "video_candidates.csv",
        video_rows,
        [
            "package",
            "index",
            "offset",
            "size",
            "default_mp4",
            "candidate_count",
            "primary_name_if_unique",
            "folder_if_unique",
            "candidates",
        ],
    )

    label_rows = []
    for code, labels in sorted(code_to_labels.items()):
        label_rows.append({"code": code, "primary_label": labels[0], "all_labels": ";".join(labels)})
    write_csv(manifest_dir / "ac_code_labels.csv", label_rows, ["code", "primary_label", "all_labels"])

    group_rows = [
        {"group_index": idx, "label": label}
        for idx, label in sorted(group_index_to_label.items())
    ]
    write_csv(manifest_dir / "m_info_group_labels.csv", group_rows, ["group_index", "label"])

    for kind in ["z2d", "ogg", "pcm"]:
        rows = list(iter_chunk_rows(kind))
        write_csv(
            manifest_dir / f"{kind}_chunks.csv",
            rows,
            ["kind", "index", "offset", "size", "source_bin", "default_name"],
        )

    z2d_names = [{"name": name, "folder": folder_for_asset_name(name, code_to_labels)} for name in parse_named_gdb_refs(".z2d")]
    write_csv(manifest_dir / "z2d_name_candidates.csv", z2d_names, ["name", "folder"])

    ogg_names = [{"name": name} for name in parse_named_gdb_refs(".ogg")]
    write_csv(manifest_dir / "ogg_name_candidates.csv", ogg_names, ["name"])

    sound_id_rows = parse_sound_id_records()
    write_csv(
        manifest_dir / "sound_id_records.csv",
        sound_id_rows,
        [
            "record_index",
            "sound_resource_id",
            "ogg_chunk_index",
            "unknown_param",
            "sound_bank",
            "marker",
            "suggested_name",
        ],
    )

    unique_video = sum(1 for row in video_rows if row["candidate_count"] == 1)
    multi_video = sum(1 for row in video_rows if row["candidate_count"] > 1)
    print(f"[manifest] wrote manifests to {manifest_dir}")
    print(f"[manifest] video chunks: {len(video_rows)}, unique-name: {unique_video}, multi-candidate: {multi_video}")
    print(f"[manifest] z2d chunks: {sum(1 for _ in iter_chunk_rows('z2d'))}, z2d name refs: {len(z2d_names)}")
    print(f"[manifest] ogg chunks: {sum(1 for _ in iter_chunk_rows('ogg'))}, pcm chunks: {sum(1 for _ in iter_chunk_rows('pcm'))}")
    print(f"[manifest] sound_id records: {len(sound_id_rows)}")


def export_chunks(kind: str, output_dir: Path, execute: bool, limit: int | None, sound_id_names: bool = False):
    bin_path, _add_path, ext = CHUNK_ARCHIVES[kind]
    rows = list(iter_chunk_rows(kind))
    if kind == "ogg" and sound_id_names:
        sound_names = {int(row["ogg_chunk_index"]): row["suggested_name"] for row in parse_sound_id_records()}
        for row in rows:
            row["export_name"] = sound_names.get(int(row["index"]), row["default_name"])
    else:
        for row in rows:
            row["export_name"] = row["default_name"]

    if limit is not None:
        rows = rows[:limit]

    target_dir = output_dir / ("images" if kind == "z2d" else "audio") / f"{kind}_raw"
    print(f"[{kind}] {'exporting' if execute else 'dry-run'} {len(rows)} chunks to {target_dir}")
    if not execute:
        for row in rows[:10]:
            print(f"  {row['export_name']} ({row['size']} bytes)")
        return

    target_dir.mkdir(parents=True, exist_ok=True)
    with bin_path.open("rb") as src:
        for row in rows:
            src.seek(int(row["offset"]))
            data = src.read(int(row["size"]))
            (target_dir / row["export_name"]).write_bytes(data)


def command_export_audio(args):
    out_dir = Path(args.out_dir)
    export_chunks("ogg", out_dir, args.execute, args.limit, args.sound_id_names)
    export_chunks("pcm", out_dir, args.execute, args.limit)


def command_export_images(args):
    out_dir = Path(args.out_dir)
    export_chunks("z2d", out_dir, args.execute, args.limit)


def find_existing_videos(video_dir: Path) -> list[Path]:
    if not video_dir.exists():
        return []
    return sorted(
        [
            p
            for p in video_dir.rglob("*.mp4")
            if not p.name.lower().endswith("_merged.mp4") and "完整合集" not in p.name
        ],
        key=lambda p: natural_key(str(p.relative_to(video_dir))),
    )


def classify_video_path(path: Path, candidates, code_to_labels):
    name = path.stem
    indexed = re.match(r"^(main|patch)_video_(\d+)$", name, re.IGNORECASE)
    if indexed:
        pack = indexed.group(1).lower()
        idx = int(indexed.group(2))
        names = candidates.get((pack, idx), [])
        if len(names) == 1:
            asset_name = names[0]
            return {
                "status": "unique_candidate",
                "folder": folder_for_asset_name(asset_name, code_to_labels),
                "target_name": safe_name(asset_name) + ".mp4",
                "package": pack,
                "index": idx,
                "candidates": names,
            }
        if len(names) > 1:
            shared_code = ""
            codes = {extract_ac_code(n) for n in names if extract_ac_code(n)}
            if len(codes) == 1:
                shared_code = next(iter(codes))
            folder = folder_for_asset_name(shared_code, code_to_labels) if shared_code else "Uncertain_multi_candidate"
            return {
                "status": "multi_candidate",
                "folder": folder,
                "target_name": path.name,
                "package": pack,
                "index": idx,
                "candidates": names,
            }
        return {
            "status": "unclassified_index",
            "folder": "Unclassified_indexed",
            "target_name": path.name,
            "package": pack,
            "index": idx,
            "candidates": [],
        }

    if AC_CODE_RE.match(name):
        return {
            "status": "already_named",
            "folder": folder_for_asset_name(name, code_to_labels),
            "target_name": safe_name(name) + ".mp4",
            "package": "",
            "index": "",
            "candidates": [name],
        }

    return {
        "status": "unclassified_name",
        "folder": "Unclassified_name",
        "target_name": path.name,
        "package": "",
        "index": "",
        "candidates": [],
    }


def unique_target(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    for idx in range(2, 10000):
        candidate = path.with_name(f"{stem}_{idx:02d}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"too many duplicate targets for {path}")


def materialize_file(src: Path, dst: Path, mode: str):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() == dst.resolve():
        return
    if mode == "move":
        shutil.move(str(src), str(dst))
    elif mode == "hardlink":
        try:
            os.link(src, dst)
        except OSError:
            shutil.copy2(src, dst)
    else:
        shutil.copy2(src, dst)


def command_organize_videos(args):
    video_dir = Path(args.video_dir)
    out_dir = Path(args.out_dir) / "videos"
    manifest_dir = Path(args.manifest_dir)
    code_to_labels, _group_index_to_label = load_label_maps()
    known_counts = {pack: len(read_offsets(bin_path, add_path)) - 1 for pack, (bin_path, add_path) in VIDEO_ARCHIVES.items()}
    candidates = parse_gdb_video_candidates(known_counts)
    files = find_existing_videos(video_dir)
    rows = []

    print(f"[videos] found {len(files)} mp4 files under {video_dir}")
    for src in files:
        info = classify_video_path(src, candidates, code_to_labels)
        dst = unique_target(out_dir / info["folder"] / info["target_name"])
        rows.append(
            {
                "source": str(src),
                "target": str(dst),
                "action": args.mode if args.execute else "dry-run",
                "status": info["status"],
                "package": info["package"],
                "index": info["index"],
                "candidate_count": len(info["candidates"]),
                "candidates": ";".join(info["candidates"]),
            }
        )
        if args.execute:
            materialize_file(src, dst, args.mode)

    write_csv(
        manifest_dir / "video_organize_plan.csv",
        rows,
        ["source", "target", "action", "status", "package", "index", "candidate_count", "candidates"],
    )
    for row in rows[:20]:
        print(f"  [{row['status']}] {Path(row['source']).name} -> {Path(row['target']).parent.name}/{Path(row['target']).name}")
    print(f"[videos] wrote plan to {manifest_dir / 'video_organize_plan.csv'}")

    if args.merge:
        merge_source = out_dir if args.execute else video_dir
        merge_videos(merge_source, execute=args.execute)


def ffconcat_path(path: Path) -> str:
    value = str(path.resolve()).replace("\\", "/").replace("'", "'\\''")
    return f"file '{value}'"


def merge_videos(video_dir: Path, execute: bool):
    files = find_existing_videos(video_dir)
    groups: dict[str, list[Path]] = defaultdict(list)
    for path in files:
        code = extract_ac_code(path.stem)
        if code:
            groups[code].append(path)

    merge_dir = video_dir / "_merged"
    planned = 0
    for code, group_files in sorted(groups.items()):
        group_files.sort(key=lambda p: natural_key(p.name))
        if len(group_files) <= 1:
            continue
        planned += 1
        output = merge_dir / f"{code}_merged.mp4"
        print(f"[merge] {code}: {len(group_files)} files -> {output}")
        if not execute:
            continue

        merge_dir.mkdir(parents=True, exist_ok=True)
        list_file = merge_dir / f"{code}_concat.txt"
        list_file.write_text("\n".join(ffconcat_path(p) for p in group_files) + "\n", encoding="utf-8")
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(output)]
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if result.returncode != 0:
            cmd = [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file),
                "-c:v",
                "libx264",
                "-crf",
                "16",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                str(output),
            ]
            result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        list_file.unlink(missing_ok=True)
        if result.returncode != 0:
            print(f"[merge] failed: {code}", file=sys.stderr)

    print(f"[merge] {'executed' if execute else 'planned'} {planned} merge groups")


def command_merge_videos(args):
    merge_videos(Path(args.video_dir), execute=args.execute)


def build_parser():
    parser = argparse.ArgumentParser(description="Magireco slot asset classification/export pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    manifest = sub.add_parser("manifest", help="write CSV manifests for video/image/audio assets")
    manifest.add_argument("--manifest-dir", default=str(DEFAULT_MANIFEST_DIR))
    manifest.set_defaults(func=command_manifest)

    video_audio = sub.add_parser("video-audio-scan", help="scan CRID slices for embedded @SFA audio")
    video_audio.add_argument("--manifest-dir", default=str(DEFAULT_MANIFEST_DIR))
    video_audio.set_defaults(func=command_video_audio_scan)

    export_audio = sub.add_parser("export-audio", help="export ogg/pcm chunks; dry-run by default")
    export_audio.add_argument("--out-dir", default=str(DEFAULT_OUTPUT_DIR))
    export_audio.add_argument("--execute", action="store_true")
    export_audio.add_argument("--limit", type=int)
    export_audio.add_argument("--sound-id-names", action="store_true", help="name OGG chunks using sound_id.dat")
    export_audio.set_defaults(func=command_export_audio)

    export_images = sub.add_parser("export-images", help="export z2d chunks; dry-run by default")
    export_images.add_argument("--out-dir", default=str(DEFAULT_OUTPUT_DIR))
    export_images.add_argument("--execute", action="store_true")
    export_images.add_argument("--limit", type=int)
    export_images.set_defaults(func=command_export_images)

    organize = sub.add_parser("organize-videos", help="organize extracted mp4 files; dry-run by default")
    organize.add_argument("--video-dir", default=str(ROOT / "final_mp4_videos"))
    organize.add_argument("--out-dir", default=str(DEFAULT_OUTPUT_DIR))
    organize.add_argument("--manifest-dir", default=str(DEFAULT_MANIFEST_DIR))
    organize.add_argument("--mode", choices=["copy", "move", "hardlink"], default="copy")
    organize.add_argument("--execute", action="store_true")
    organize.add_argument("--merge", action="store_true")
    organize.set_defaults(func=command_organize_videos)

    merge = sub.add_parser("merge-videos", help="merge already named acXXXX mp4 groups; dry-run by default")
    merge.add_argument("--video-dir", default=str(DEFAULT_OUTPUT_DIR / "videos"))
    merge.add_argument("--execute", action="store_true")
    merge.set_defaults(func=command_merge_videos)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
