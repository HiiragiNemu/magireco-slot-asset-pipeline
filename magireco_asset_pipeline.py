from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import struct
import subprocess
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path, PureWindowsPath


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
SOUND_REQUEST_TABLE_PATH = ROOT / "unpacked_assets" / "assets" / "zg_snd_request_tbl.bin"
SOUND_HASHREQ_TABLE_PATH = ROOT / "unpacked_assets" / "assets" / "zg_snd_hashreq_tbl.bin"
DEBUG_SMALI_FILES = [
    ROOT / "unpacked_base" / "smali" / "debug" / "sub" / "DebugProd.smali",
    ROOT / "unpacked_base" / "smali" / "debug" / "sub" / "DebugDispNameList.smali",
]

PACK_TO_GDB_FILE_VAL = {"main": 1, "patch": 2}
GDB_FILE_VAL_TO_PACK = {v: k for k, v in PACK_TO_GDB_FILE_VAL.items()}
INVALID_NAME_CHARS = re.compile(r'[\\/*?:"<>|\r\n\t]+')
AC_CODE_RE = re.compile(r"^(ac\d{4})", re.IGNORECASE)
AC_CODE_ANY_RE = re.compile(r"(ac\d{4})", re.IGNORECASE)
AC_WITH_FINAL_NUMBER_RE = re.compile(
    r"^(?P<key>ac\d{4}[A-Za-z]*(?:_[A-Za-z0-9]+)*?)_(?P<number>\d+)$",
    re.IGNORECASE,
)
CANDIDATE_SLICE_RE = re.compile(
    r"^(?P<package>main|patch)_video_(?P<index>\d+)_candidates(?P<candidates>\d+)$",
    re.IGNORECASE,
)


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


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def split_semicolon(value: str) -> list[str]:
    if not value:
        return []
    return [item for item in value.split(";") if item]


def parse_bool(value) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def parse_optional_float(value) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def parse_optional_int(value) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


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


def load_video_candidate_maps(manifest_dir: Path):
    rows = read_csv(manifest_dir / "video_candidates.csv")
    chunk_to_info = {}
    name_to_chunks: dict[str, list[tuple[str, int]]] = defaultdict(list)

    for row in rows:
        pack = row.get("package", "").lower()
        index = parse_optional_int(row.get("index"))
        if not pack or index is None:
            continue
        names = split_semicolon(row.get("candidates", ""))
        key = (pack, index)
        chunk_to_info[key] = {
            "package": pack,
            "index": index,
            "candidate_count": parse_optional_int(row.get("candidate_count")) or len(names),
            "primary_name_if_unique": row.get("primary_name_if_unique", ""),
            "candidates": names,
        }
        for name in names:
            name_to_chunks[name].append(key)

    return chunk_to_info, name_to_chunks


def infer_mp4_chunk_key(row: dict, name_to_chunks: dict[str, list[tuple[str, int]]]) -> tuple[str, int] | None:
    relative_path = row.get("relative_path", "")
    stem = PureWindowsPath(relative_path).stem
    indexed = re.match(r"^(main|patch)_video_(\d+)", stem, re.IGNORECASE)
    if indexed:
        return indexed.group(1).lower(), int(indexed.group(2))

    chunks = name_to_chunks.get(stem, [])
    if len(chunks) == 1:
        return chunks[0]
    return None


def load_mp4_audit_maps(manifest_dir: Path, explicit_path: str, name_to_chunks: dict[str, list[tuple[str, int]]]):
    audit_path = Path(explicit_path) if explicit_path else manifest_dir / "ramdisk_audit" / "mp4_ffprobe_audit.csv"
    rows = read_csv(audit_path)
    chunk_to_mp4 = {}
    unmapped = []

    for row in rows:
        key = infer_mp4_chunk_key(row, name_to_chunks)
        if key is None:
            unmapped.append(row)
            continue
        chunk_to_mp4.setdefault(key, row)

    return audit_path, rows, chunk_to_mp4, unmapped


def sequence_number_from_name(name: str) -> int | None:
    stem = Path(name).stem
    match = re.search(r"_(\d+)$", stem)
    if not match:
        return None
    return int(match.group(1))


def split_sequence_key_from_name(name: str) -> tuple[str, int | None]:
    match = AC_WITH_FINAL_NUMBER_RE.match(Path(name).stem)
    if not match:
        return Path(name).stem.lower(), None
    return match.group("key").lower(), int(match.group("number"))


def build_sequence_name_groups(chunk_to_info: dict[tuple[str, int], dict]) -> dict[str, list[str]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for info in chunk_to_info.values():
        for name in info["candidates"]:
            key, number = split_sequence_key_from_name(name)
            grouped[key].append(
                {
                    "name": name,
                    "number": number,
                }
            )

    result = {}
    for key, items in grouped.items():
        items.sort(key=lambda item: (item["number"] is None, item["number"] or -1, natural_key(item["name"])))
        result[key] = [item["name"] for item in items]
    return result


def path_from_video_root(video_dir: Path, relative_path: str) -> Path:
    return video_dir.joinpath(*PureWindowsPath(relative_path).parts)


def format_seconds(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.3f}"


def probe_mp4(path: Path) -> dict:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=index,codec_type,codec_name,width,height,duration",
        "-of",
        "json",
        str(path),
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        return {"probe_ok": False, "probe_error": result.stderr.strip()}
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        return {"probe_ok": False, "probe_error": f"json decode failed: {exc}"}

    streams = payload.get("streams", [])
    video_streams = [stream for stream in streams if stream.get("codec_type") == "video"]
    audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]
    video = video_streams[0] if video_streams else {}
    audio = audio_streams[0] if audio_streams else {}
    duration = payload.get("format", {}).get("duration") or video.get("duration") or audio.get("duration") or ""
    return {
        "probe_ok": True,
        "probe_error": "",
        "duration_sec": duration,
        "has_video": bool(video_streams),
        "has_audio": bool(audio_streams),
        "video_codec": video.get("codec_name", ""),
        "audio_codec": audio.get("codec_name", ""),
        "width": video.get("width", ""),
        "height": video.get("height", ""),
    }


def sample_video_luma(path: Path, duration_sec: float | None, samples: int) -> dict:
    if duration_sec is None or duration_sec <= 0:
        sample_times = [0.0]
    else:
        fractions = [0.5] if samples <= 1 else [0.1, 0.5, 0.9][:samples]
        max_seek = max(0.0, duration_sec - 0.05)
        sample_times = sorted({round(min(max_seek, max(0.0, duration_sec * frac)), 3) for frac in fractions})

    means = []
    nonblack_ratios = []
    bright_ratios = []
    failures = 0
    expected = 64 * 64
    for seek_time in sample_times:
        cmd = [
            "ffmpeg",
            "-v",
            "error",
            "-ss",
            f"{seek_time:.3f}",
            "-i",
            str(path),
            "-frames:v",
            "1",
            "-vf",
            "scale=64:64,format=gray",
            "-f",
            "rawvideo",
            "pipe:1",
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        frame = result.stdout
        if result.returncode != 0 or len(frame) < expected:
            failures += 1
            continue
        frame = frame[:expected]
        means.append(sum(frame) / expected)
        nonblack_ratios.append(sum(1 for value in frame if value > 8) / expected)
        bright_ratios.append(sum(1 for value in frame if value > 24) / expected)

    if not means:
        return {
            "avg_mean_luma": "",
            "avg_nonblack_ratio": "",
            "max_nonblack_ratio": "",
            "max_bright_ratio": "",
            "sample_failures": failures,
            "blackish": False,
            "mostly_black": False,
        }

    avg_mean_luma = sum(means) / len(means)
    avg_nonblack_ratio = sum(nonblack_ratios) / len(nonblack_ratios)
    max_nonblack_ratio = max(nonblack_ratios)
    max_bright_ratio = max(bright_ratios)
    return {
        "avg_mean_luma": f"{avg_mean_luma:.3f}",
        "avg_nonblack_ratio": f"{avg_nonblack_ratio:.5f}",
        "max_nonblack_ratio": f"{max_nonblack_ratio:.5f}",
        "max_bright_ratio": f"{max_bright_ratio:.5f}",
        "sample_failures": failures,
        "blackish": avg_mean_luma < 4.0 and max_nonblack_ratio < 0.01,
        "mostly_black": avg_mean_luma < 12.0 and max_nonblack_ratio < 0.08,
    }


def place_review_copy(source: Path, target_dir: Path, mode: str) -> str:
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source.name
    if target.exists():
        return str(target)
    if mode == "hardlink":
        try:
            os.link(source, target)
            return str(target)
        except OSError:
            pass
    shutil.copy2(source, target)
    return str(target)


def review_one_special_video(path: Path, video_dir: Path, out_dir: Path, mode: str, samples: int) -> dict:
    relative_path = str(path.relative_to(video_dir))
    probe = probe_mp4(path)
    row = {
        "relative_path": relative_path,
        "special_class": "",
        "review_path": "",
        "probe_ok": "yes" if probe.get("probe_ok") else "no",
        "probe_error": probe.get("probe_error", ""),
        "duration_sec": probe.get("duration_sec", ""),
        "has_video": "yes" if probe.get("has_video") else "no",
        "has_audio": "yes" if probe.get("has_audio") else "no",
        "video_codec": probe.get("video_codec", ""),
        "audio_codec": probe.get("audio_codec", ""),
        "width": probe.get("width", ""),
        "height": probe.get("height", ""),
        "avg_mean_luma": "",
        "avg_nonblack_ratio": "",
        "max_nonblack_ratio": "",
        "max_bright_ratio": "",
        "sample_failures": "",
    }

    if not probe.get("probe_ok"):
        row["special_class"] = "probe_failed"
        row["review_path"] = place_review_copy(path, out_dir / "probe_failed", mode)
        return row

    has_video = bool(probe.get("has_video"))
    has_audio = bool(probe.get("has_audio"))
    if has_audio and not has_video:
        row["special_class"] = "audio_only"
        row["review_path"] = place_review_copy(path, out_dir / "audio_only", mode)
        return row

    if not has_video:
        row["special_class"] = "no_video_stream"
        row["review_path"] = place_review_copy(path, out_dir / "no_video_stream", mode)
        return row

    duration = parse_optional_float(str(probe.get("duration_sec", "")))
    luma = sample_video_luma(path, duration, samples)
    row.update(
        {
            "avg_mean_luma": luma["avg_mean_luma"],
            "avg_nonblack_ratio": luma["avg_nonblack_ratio"],
            "max_nonblack_ratio": luma["max_nonblack_ratio"],
            "max_bright_ratio": luma["max_bright_ratio"],
            "sample_failures": luma["sample_failures"],
        }
    )

    if luma["blackish"]:
        row["special_class"] = "blackish_video"
        row["review_path"] = place_review_copy(path, out_dir / "blackish_video", mode)
    elif luma["mostly_black"]:
        row["special_class"] = "mostly_black_video"
        row["review_path"] = place_review_copy(path, out_dir / "mostly_black_video", mode)
    return row


def read_text_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    for encoding in ("utf-8", "utf-8-sig", "cp932"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def extract_xml_string(text: str, name: str) -> str:
    match = re.search(rf'<string\s+name="{re.escape(name)}">(?P<value>.*?)</string>', text, re.DOTALL)
    if not match:
        return ""
    value = re.sub(r"\s+", " ", match.group("value")).strip()
    return value.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")


def extract_yaml_scalar(text: str, key: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(key)}:\s*(?P<value>.+?)\s*$", text)
    return match.group("value").strip("'\"") if match else ""


def first_nonempty(*values: str) -> str:
    for value in values:
        if value:
            return value
    return ""


def review_action_for_sequence(
    item_count: int,
    matched_items: int,
    shared_chunk_items: int,
    missing_mapping_items: int,
    missing_mp4_items: int,
    ambiguous_name_items: int,
    resolution_count: int,
    confidence: str,
    coverage_ratio: float,
) -> str:
    if missing_mapping_items or missing_mp4_items or ambiguous_name_items:
        return "needs_missing_mapping_review"
    if shared_chunk_items:
        return "review_shared_chunks_before_merge"
    if resolution_count > 1:
        return "review_resolution_mismatch"
    if item_count < 2 or matched_items < 2:
        return "do_not_merge_single_item"
    if confidence not in {"high", "medium"} or coverage_ratio < 0.9:
        return "do_not_merge_low_confidence"
    return "candidate_for_preview_concat"


def flush_unique_run(
    runs: list[dict],
    current: list[dict],
    min_run: int,
    sequence_key: str,
    concat_dir: Path,
    write_concat_plans: bool,
    max_concat_plans: int,
):
    if len(current) < min_run:
        return

    start = current[0]
    end = current[-1]
    durations = [parse_optional_float(row["duration_sec"]) for row in current]
    total_duration = sum(d for d in durations if d is not None)
    has_audio_count = sum(1 for row in current if parse_bool(row["has_audio"]))
    resolutions = sorted({row["resolution"] for row in current if row["resolution"]}, key=natural_key)
    concat_plan = ""

    if write_concat_plans and len(runs) < max_concat_plans:
        concat_dir.mkdir(parents=True, exist_ok=True)
        plan_name = safe_name(
            f"{sequence_key}_{start['sequence_number'] or start['item_order']:04d}_"
            f"{end['sequence_number'] or end['item_order']:04d}_"
            f"{start['package']}_{start['index']}-{end['index']}",
            max_len=120,
        ) + ".ffconcat.txt"
        concat_path = concat_dir / plan_name
        concat_lines = [ffconcat_path(Path(row["source_path"])) for row in current]
        concat_path.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
        concat_plan = str(concat_path)

    recommendation = "candidate_for_silent_preview_concat" if has_audio_count == 0 else "candidate_for_preview_concat"
    runs.append(
        {
            "sequence_key": sequence_key,
            "start_number": start["sequence_number"],
            "end_number": end["sequence_number"],
            "item_count": len(current),
            "package": start["package"],
            "first_index": start["index"],
            "last_index": end["index"],
            "total_duration_sec": format_seconds(total_duration),
            "has_audio_count": has_audio_count,
            "resolutions": ";".join(resolutions),
            "first_relative_path": start["relative_path"],
            "last_relative_path": end["relative_path"],
            "recommendation": recommendation,
            "concat_plan": concat_plan,
        }
    )


def build_video_review(args):
    manifest_dir = Path(args.manifest_dir)
    video_dir = Path(args.video_dir)
    sequence_csv = Path(args.sequence_csv) if args.sequence_csv else manifest_dir / "internal_audit" / "video_sequence_candidates.csv"
    sequence_rows = read_csv(sequence_csv)
    chunk_to_info, name_to_chunks = load_video_candidate_maps(manifest_dir)
    sequence_name_groups = build_sequence_name_groups(chunk_to_info)
    sequence_meta = {row.get("sequence_key", ""): row for row in sequence_rows if row.get("sequence_key")}
    mp4_audit_path, mp4_rows, chunk_to_mp4, unmapped_mp4_rows = load_mp4_audit_maps(
        manifest_dir,
        args.mp4_audit,
        name_to_chunks,
    )

    review_rows = []
    item_rows = []
    run_rows = []
    concat_dir = manifest_dir / "video_review_concat_plans"

    sequence_keys = sorted(set(sequence_meta) | set(sequence_name_groups), key=natural_key)
    for sequence_key in sequence_keys:
        seq_row = sequence_meta.get(sequence_key, {"sequence_key": sequence_key})
        names = sequence_name_groups.get(sequence_key) or split_semicolon(seq_row.get("names", ""))
        confidence = seq_row.get("confidence", "")
        coverage_ratio = parse_optional_float(seq_row.get("number_coverage_ratio")) or 0.0
        matched_items = 0
        shared_chunk_items = 0
        missing_mapping_items = 0
        missing_mp4_items = 0
        ambiguous_name_items = 0
        duplicate_chunk_items = 0
        has_audio_items = 0
        total_duration = 0.0
        resolutions = set()
        packages = set()
        seen_chunks = set()
        current_run: list[dict] = []

        def close_run():
            flush_unique_run(
                run_rows,
                current_run,
                args.min_run,
                sequence_key,
                concat_dir,
                args.write_concat_plans,
                args.max_concat_plans,
            )
            current_run.clear()

        for item_order, name in enumerate(names, start=1):
            number = sequence_number_from_name(name)
            chunks = name_to_chunks.get(name, [])
            item_status = "ok"
            key = None
            chunk_info = None
            mp4_info = None
            source_path = ""
            source_exists = ""
            duration = None
            width = ""
            height = ""
            resolution = ""
            has_audio = False

            if not chunks:
                item_status = "missing_gdb_mapping"
                missing_mapping_items += 1
            elif len(chunks) > 1:
                item_status = "ambiguous_name_mapping"
                ambiguous_name_items += 1
            else:
                key = chunks[0]
                chunk_info = chunk_to_info.get(key, {})
                mp4_info = chunk_to_mp4.get(key)
                if key in seen_chunks:
                    duplicate_chunk_items += 1
                seen_chunks.add(key)

                if not mp4_info:
                    item_status = "missing_mp4_audit"
                    missing_mp4_items += 1
                else:
                    matched_items += 1
                    duration = parse_optional_float(mp4_info.get("duration_sec"))
                    if duration is not None:
                        total_duration += duration
                    has_audio = parse_bool(mp4_info.get("has_audio"))
                    if has_audio:
                        has_audio_items += 1
                    width = mp4_info.get("width", "")
                    height = mp4_info.get("height", "")
                    resolution = f"{width}x{height}" if width and height else ""
                    if resolution:
                        resolutions.add(resolution)
                    source_path = str(path_from_video_root(video_dir, mp4_info.get("relative_path", "")))
                    source_exists = "yes" if Path(source_path).exists() else "no"

                if chunk_info:
                    packages.add(chunk_info["package"])
                    if int(chunk_info["candidate_count"]) > 1:
                        shared_chunk_items += 1

            item = {
                "sequence_key": sequence_key,
                "item_order": item_order,
                "sequence_number": number if number is not None else "",
                "name": name,
                "status": item_status,
                "package": chunk_info["package"] if chunk_info else "",
                "index": chunk_info["index"] if chunk_info else "",
                "candidate_count": chunk_info["candidate_count"] if chunk_info else "",
                "relative_path": mp4_info.get("relative_path", "") if mp4_info else "",
                "source_path": source_path,
                "source_path_exists": source_exists,
                "duration_sec": format_seconds(duration),
                "has_audio": "yes" if has_audio else "no",
                "resolution": resolution,
                "width": width,
                "height": height,
            }
            item_rows.append(item)

            can_extend_run = (
                item_status == "ok"
                and chunk_info is not None
                and int(chunk_info["candidate_count"]) == 1
                and source_path
                and source_exists == "yes"
            )
            if not can_extend_run:
                close_run()
                continue

            if current_run:
                prev = current_run[-1]
                prev_number = parse_optional_int(prev["sequence_number"])
                prev_index = parse_optional_int(prev["index"])
                current_index = parse_optional_int(item["index"])
                number_is_next = number is None or prev_number is None or number == prev_number + 1
                index_is_next = current_index is not None and prev_index is not None and current_index == prev_index + 1
                same_pack = item["package"] == prev["package"]
                same_resolution = item["resolution"] == prev["resolution"]
                if not (number_is_next and index_is_next and same_pack and same_resolution):
                    close_run()
            current_run.append(item)

        close_run()
        action = review_action_for_sequence(
            item_count=len(names),
            matched_items=matched_items,
            shared_chunk_items=shared_chunk_items,
            missing_mapping_items=missing_mapping_items,
            missing_mp4_items=missing_mp4_items,
            ambiguous_name_items=ambiguous_name_items,
            resolution_count=len(resolutions),
            confidence=confidence,
            coverage_ratio=coverage_ratio,
        )
        review_rows.append(
            {
                "sequence_key": sequence_key,
                "ac_code": seq_row.get("ac_code", ""),
                "debug_labels": seq_row.get("debug_labels", ""),
                "confidence": confidence,
                "source_recommendation": seq_row.get("recommendation", ""),
                "review_action": action,
                "item_count": len(names),
                "matched_items": matched_items,
                "shared_chunk_items": shared_chunk_items,
                "missing_mapping_items": missing_mapping_items,
                "missing_mp4_items": missing_mp4_items,
                "ambiguous_name_items": ambiguous_name_items,
                "duplicate_chunk_items": duplicate_chunk_items,
                "has_audio_items": has_audio_items,
                "total_duration_sec": format_seconds(total_duration),
                "resolutions": ";".join(sorted(resolutions, key=natural_key)),
                "packages": ";".join(sorted(packages)),
                "first_number": seq_row.get("first_number", ""),
                "last_number": seq_row.get("last_number", ""),
                "longest_consecutive_run": seq_row.get("longest_consecutive_run", ""),
                "number_coverage_ratio": seq_row.get("number_coverage_ratio", ""),
                "native_seen": seq_row.get("native_seen", ""),
            }
        )

    review_rows.sort(key=lambda row: (row["review_action"], -int(row["matched_items"]), natural_key(row["sequence_key"])))
    item_rows.sort(key=lambda row: (natural_key(row["sequence_key"]), parse_optional_int(row["item_order"]) or 0))
    run_rows.sort(key=lambda row: (-int(row["item_count"]), natural_key(row["sequence_key"]), parse_optional_int(row["start_number"]) or 0))

    return {
        "sequence_csv": sequence_csv,
        "mp4_audit_path": mp4_audit_path,
        "mp4_rows": mp4_rows,
        "unmapped_mp4_rows": unmapped_mp4_rows,
        "review_rows": review_rows,
        "item_rows": item_rows,
        "run_rows": run_rows,
    }


def command_video_review(args):
    manifest_dir = Path(args.manifest_dir)
    result = build_video_review(args)

    sequence_path = manifest_dir / "video_review_sequences.csv"
    items_path = manifest_dir / "video_review_items.csv"
    runs_path = manifest_dir / "video_review_unique_runs.csv"
    summary_path = manifest_dir / "video_review_summary.md"

    write_csv(
        sequence_path,
        result["review_rows"],
        [
            "sequence_key",
            "ac_code",
            "debug_labels",
            "confidence",
            "source_recommendation",
            "review_action",
            "item_count",
            "matched_items",
            "shared_chunk_items",
            "missing_mapping_items",
            "missing_mp4_items",
            "ambiguous_name_items",
            "duplicate_chunk_items",
            "has_audio_items",
            "total_duration_sec",
            "resolutions",
            "packages",
            "first_number",
            "last_number",
            "longest_consecutive_run",
            "number_coverage_ratio",
            "native_seen",
        ],
    )
    write_csv(
        items_path,
        result["item_rows"],
        [
            "sequence_key",
            "item_order",
            "sequence_number",
            "name",
            "status",
            "package",
            "index",
            "candidate_count",
            "relative_path",
            "source_path",
            "source_path_exists",
            "duration_sec",
            "has_audio",
            "resolution",
            "width",
            "height",
        ],
    )
    write_csv(
        runs_path,
        result["run_rows"],
        [
            "sequence_key",
            "start_number",
            "end_number",
            "item_count",
            "package",
            "first_index",
            "last_index",
            "total_duration_sec",
            "has_audio_count",
            "resolutions",
            "first_relative_path",
            "last_relative_path",
            "recommendation",
            "concat_plan",
        ],
    )

    action_counts = defaultdict(int)
    for row in result["review_rows"]:
        action_counts[row["review_action"]] += 1
    run_recommendation_counts = defaultdict(int)
    for row in result["run_rows"]:
        run_recommendation_counts[row["recommendation"]] += 1

    lines = [
        "# Video Review Summary",
        "",
        f"Video dir: {args.video_dir}",
        f"Sequence CSV: {result['sequence_csv']}",
        f"MP4 audit CSV: {result['mp4_audit_path']}",
        f"MP4 audit rows: {len(result['mp4_rows'])}",
        f"Unmapped MP4 audit rows: {len(result['unmapped_mp4_rows'])}",
        "",
        "## Sequence Review Actions",
    ]
    for action, count in sorted(action_counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {action}: {count}")
    lines.extend(["", "## Unique Continuous Runs"])
    lines.append(f"- minimum run length: {args.min_run}")
    lines.append(f"- run count: {len(result['run_rows'])}")
    for recommendation, count in sorted(run_recommendation_counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {recommendation}: {count}")
    lines.extend(["", "## Outputs"])
    lines.append(f"- {sequence_path}")
    lines.append(f"- {items_path}")
    lines.append(f"- {runs_path}")
    if args.write_concat_plans:
        lines.append(f"- {manifest_dir / 'video_review_concat_plans'}")
    lines.extend(["", "## Notes"])
    lines.append("- This command does not merge, move, or delete MP4 files.")
    lines.append("- `candidate_for_preview_concat` means suitable for preview-list generation, not final proof of game playback order.")
    lines.append("- Shared chunks remain review-only because multiple internal names point to the same CRID slice.")
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[video-review] sequences: {len(result['review_rows'])}")
    print(f"[video-review] sequence items: {len(result['item_rows'])}")
    print(f"[video-review] unique continuous runs: {len(result['run_rows'])}")
    print(f"[video-review] wrote {sequence_path}")
    print(f"[video-review] wrote {items_path}")
    print(f"[video-review] wrote {runs_path}")
    print(f"[video-review] wrote {summary_path}")


SOUND_MEDIA_NAME_RE = re.compile(r"([0-9A-F]{16,}\.(?:smz|pcm))", re.IGNORECASE)


def normalize_sound_table_string(text: str) -> str:
    media_match = SOUND_MEDIA_NAME_RE.search(text)
    if media_match:
        return media_match.group(1)
    return re.sub(r"^[\x00-\x1f]+|[\x00-\x1f]+$", "", text).strip("\x00\r\n\t ")


def decode_table_string(raw: bytes) -> str:
    raw = raw.strip(b"\x00")
    if not raw:
        return ""
    for encoding in ("utf-8", "shift_jis", "cp932"):
        try:
            return normalize_sound_table_string(raw.decode(encoding, errors="strict"))
        except UnicodeDecodeError:
            continue
    return normalize_sound_table_string(raw.decode("utf-8", errors="ignore"))


def is_useful_sound_string(text: str) -> bool:
    if not text:
        return False
    if SOUND_MEDIA_NAME_RE.search(text):
        return True
    if re.match(r"^\d{1,6}(?:_|$)", text):
        return True
    if re.search(r"[ぁ-んァ-ヶ一-龥ー]", text):
        return True
    if re.search(r"(?:BGM|SE|Voice|voice|serihu|kyara|seq|BB|AT|UT)", text):
        return True
    return False


def extract_sound_table_strings(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = path.read_bytes()
    rows = []
    start = 0
    for pos, value in enumerate(data + b"\x00"):
        if value != 0:
            continue
        if pos > start:
            raw = data[start:pos]
            text = decode_table_string(raw)
            if is_useful_sound_string(text):
                rows.append(
                    {
                        "offset": start,
                        "offset_hex": f"0x{start:x}",
                        "text": text,
                    }
                )
        start = pos + 1
    rows.sort(key=lambda row: row["offset"])
    return rows


def classify_sound_table_string(text: str) -> str:
    if SOUND_MEDIA_NAME_RE.search(text):
        return "media"
    if re.match(r"^\d{1,6}(?:_|$)", text):
        return "request"
    return "group_or_label"


def sound_request_id_and_label(text: str) -> tuple[int | None, str]:
    match = re.match(r"^(?P<id>\d{1,6})(?:_(?P<label>.*))?$", text)
    if not match:
        return None, ""
    return int(match.group("id")), match.group("label") or ""


def nearest_text(
    rows: list[dict],
    current_index: int,
    direction: int,
    kinds: set[str],
    max_distance: int,
) -> dict | None:
    current_offset = int(rows[current_index]["offset"])
    index = current_index + direction
    while 0 <= index < len(rows):
        row = rows[index]
        distance = abs(int(row["offset"]) - current_offset)
        if distance > max_distance:
            return None
        if row["kind"] in kinds:
            return row | {"distance": distance}
        index += direction
    return None


def load_ogg_duration_map(path: Path) -> dict[str, str]:
    rows = read_csv(path)
    result = {}
    for row in rows:
        name = Path(row.get("relative_path", "")).name
        if name:
            result[name] = row.get("duration_sec", "")
    return result


def command_sound_request_audit(args):
    manifest_dir = Path(args.manifest_dir)
    table_path = Path(args.table_path)
    rows = extract_sound_table_strings(table_path)
    for row in rows:
        row["kind"] = classify_sound_table_string(row["text"])

    sound_records = {
        int(row["sound_resource_id"]): row
        for row in read_csv(manifest_dir / "sound_id_records.csv")
        if row.get("sound_resource_id", "").isdigit()
    }
    ogg_duration_map = load_ogg_duration_map(Path(args.ogg_audit)) if args.ogg_audit else {}

    request_rows = []
    for index, row in enumerate(rows):
        if row["kind"] != "request":
            continue
        sound_id, label = sound_request_id_and_label(row["text"])
        if sound_id is None:
            continue
        media_before = nearest_text(rows, index, -1, {"media"}, args.context_bytes)
        media_after = nearest_text(rows, index, 1, {"media"}, args.context_bytes)
        group_before = nearest_text(rows, index, -1, {"group_or_label"}, args.context_bytes)
        group_after = nearest_text(rows, index, 1, {"group_or_label"}, args.context_bytes)
        nearest_media = None
        for candidate in (media_before, media_after):
            if candidate and (nearest_media is None or candidate["distance"] < nearest_media["distance"]):
                nearest_media = candidate

        sound_record = sound_records.get(sound_id, {})
        suggested_name = sound_record.get("suggested_name", "")
        request_rows.append(
            {
                "offset_hex": row["offset_hex"],
                "sound_resource_id": sound_id,
                "request_text": row["text"],
                "request_label": label,
                "group_before": group_before["text"] if group_before else "",
                "group_after": group_after["text"] if group_after else "",
                "media_before": media_before["text"] if media_before else "",
                "media_before_distance": media_before["distance"] if media_before else "",
                "media_after": media_after["text"] if media_after else "",
                "media_after_distance": media_after["distance"] if media_after else "",
                "nearest_media": nearest_media["text"] if nearest_media else "",
                "nearest_media_distance": nearest_media["distance"] if nearest_media else "",
                "has_sound_id_record": "yes" if sound_record else "no",
                "ogg_chunk_index": sound_record.get("ogg_chunk_index", ""),
                "sound_bank": sound_record.get("sound_bank", ""),
                "suggested_name": suggested_name,
                "ogg_duration_sec": ogg_duration_map.get(suggested_name, ""),
            }
        )

    request_rows.sort(key=lambda row: (int(row["sound_resource_id"]), natural_key(row["request_text"])))
    output_csv = manifest_dir / "sound_request_audit.csv"
    write_csv(
        output_csv,
        request_rows,
        [
            "offset_hex",
            "sound_resource_id",
            "request_text",
            "request_label",
            "group_before",
            "group_after",
            "media_before",
            "media_before_distance",
            "media_after",
            "media_after_distance",
            "nearest_media",
            "nearest_media_distance",
            "has_sound_id_record",
            "ogg_chunk_index",
            "sound_bank",
            "suggested_name",
            "ogg_duration_sec",
        ],
    )

    linked = sum(1 for row in request_rows if row["has_sound_id_record"] == "yes")
    with_label = sum(1 for row in request_rows if row["request_label"])
    with_media = sum(1 for row in request_rows if row["nearest_media"])
    summary_path = manifest_dir / "sound_request_summary.md"
    lines = [
        "# Sound Request Audit Summary",
        "",
        f"Table: {table_path}",
        f"Extracted useful strings: {len(rows)}",
        f"Request rows: {len(request_rows)}",
        f"Rows linked to sound_id.dat: {linked}",
        f"Rows with descriptive labels: {with_label}",
        f"Rows with nearby media hash/name: {with_media}",
        "",
        "## Notes",
        "- This is a heuristic parser for zg_snd_request_tbl.bin.",
        "- `nearest_media` is proximity-based and should be treated as a candidate until validated.",
        "- `sound_id.dat` remains the reliable mapping from sound_resource_id to OGG chunk index.",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[sound-request-audit] useful strings: {len(rows)}")
    print(f"[sound-request-audit] request rows: {len(request_rows)}")
    print(f"[sound-request-audit] linked to sound_id.dat: {linked}")
    print(f"[sound-request-audit] wrote {output_csv}")
    print(f"[sound-request-audit] wrote {summary_path}")


def decode_fixed_c_string(raw: bytes) -> str:
    return decode_table_string(raw.split(b"\x00", 1)[0])


def parse_sound_request_struct_table(path: Path) -> tuple[tuple[int, ...], list[dict], list[dict]]:
    if not path.exists():
        return tuple(), [], []
    data = path.read_bytes()
    if len(data) < 64:
        return tuple(), [], []
    header = struct.unpack("<16I", data[:64])
    request_count = header[7]
    offset = 64
    request_rows: list[dict] = []
    reqdata_rows: list[dict] = []

    for request_id in range(request_count):
        request_offset = offset
        if offset + 0x48 > len(data):
            break
        request_header = data[offset : offset + 0x48]
        code_name = decode_fixed_c_string(request_header[:0x40])
        reqdata_count, marker_count = struct.unpack_from("<II", request_header, 0x40)
        offset += 0x48

        first_media = ""
        media_count = 0
        for reqdata_index in range(reqdata_count):
            reqdata_offset = offset
            if offset + 0x60 > len(data):
                break
            reqdata = data[offset : offset + 0x60]
            fields = struct.unpack("<24I", reqdata)
            smz_media = decode_fixed_c_string(reqdata[0x28:0x48])
            if smz_media:
                media_count += 1
                if not first_media:
                    first_media = smz_media

            raw_mode_a = struct.unpack_from("<i", reqdata, 0x58)[0]
            raw_mode_b = struct.unpack_from("<i", reqdata, 0x5C)[0]
            mode_a = raw_mode_a % 5
            mode_b = raw_mode_b % 3
            offset += 0x60

            fade_hex = ""
            ducking_hex = ""
            if mode_a != 0:
                fade = data[offset : offset + 0x0C]
                fade_hex = fade.hex().upper()
                offset += 0x0C
            if mode_b == 2:
                ducking = data[offset : offset + 0x28]
                ducking_hex = ducking.hex().upper()
                offset += 0x28

            row = {
                "request_id": request_id,
                "code_name": code_name,
                "request_offset_hex": f"0x{request_offset:x}",
                "reqdata_index": reqdata_index,
                "reqdata_offset_hex": f"0x{reqdata_offset:x}",
                "reqdata_count": reqdata_count,
                "marker_count": marker_count,
                "smz_media": smz_media,
                "reqdata_type": fields[0],
                "reqdata_variant": fields[2],
                "reqdata_group_or_channel": fields[5],
                "reqdata_flag": fields[18],
                "reqdata_ref_id_a": fields[20],
                "reqdata_ref_id_b": fields[21],
                "mode_a_raw": raw_mode_a,
                "mode_a_mod5": mode_a,
                "mode_b_raw": raw_mode_b,
                "mode_b_mod3": mode_b,
                "fade_extra_hex": fade_hex,
                "ducking_extra_hex": ducking_hex,
            }
            for field_index, value in enumerate(fields):
                row[f"u32_{field_index:02d}"] = value
            reqdata_rows.append(row)

        for _ in range(marker_count):
            offset += 0x24

        request_rows.append(
            {
                "request_id": request_id,
                "code_name": code_name,
                "request_offset_hex": f"0x{request_offset:x}",
                "reqdata_count": reqdata_count,
                "marker_count": marker_count,
                "reqdata_media_count": media_count,
                "first_smz_media": first_media,
            }
        )

    return header, request_rows, reqdata_rows


def command_sound_request_struct_audit(args):
    manifest_dir = Path(args.manifest_dir)
    table_path = Path(args.table_path)
    header, request_rows, reqdata_rows = parse_sound_request_struct_table(table_path)

    request_csv = manifest_dir / "sound_request_struct_requests.csv"
    reqdata_csv = manifest_dir / "sound_request_struct_reqdata.csv"
    request_fields = [
        "request_id",
        "code_name",
        "request_offset_hex",
        "reqdata_count",
        "marker_count",
        "reqdata_media_count",
        "first_smz_media",
    ]
    reqdata_fields = [
        "request_id",
        "code_name",
        "request_offset_hex",
        "reqdata_index",
        "reqdata_offset_hex",
        "reqdata_count",
        "marker_count",
        "smz_media",
        "reqdata_type",
        "reqdata_variant",
        "reqdata_group_or_channel",
        "reqdata_flag",
        "reqdata_ref_id_a",
        "reqdata_ref_id_b",
        "mode_a_raw",
        "mode_a_mod5",
        "mode_b_raw",
        "mode_b_mod3",
        "fade_extra_hex",
        "ducking_extra_hex",
    ] + [f"u32_{field_index:02d}" for field_index in range(24)]
    write_csv(request_csv, request_rows, request_fields)
    write_csv(reqdata_csv, reqdata_rows, reqdata_fields)

    code_to_request = {row["code_name"]: row for row in request_rows if row["code_name"]}
    focus_codes = [code.strip() for code in args.focus_codes.split(",") if code.strip()]
    focus_lines = []
    if focus_codes:
        focus_lines.extend(["", "## Focus Codes", "", "| code | request_id | reqdata | markers | first_smz_media |", "| --- | ---: | ---: | ---: | --- |"])
        for code in focus_codes:
            row = code_to_request.get(code)
            if row:
                focus_lines.append(
                    f"| `{code}` | {row['request_id']} | {row['reqdata_count']} | {row['marker_count']} | `{row['first_smz_media']}` |"
                )
            else:
                focus_lines.append(f"| `{code}` |  |  |  |  |")

    unique_media = {row["smz_media"] for row in reqdata_rows if row["smz_media"]}
    no_media = sum(1 for row in request_rows if not row["first_smz_media"])
    summary_path = manifest_dir / "sound_request_struct_summary.md"
    lines = [
        "# Structured Sound Request Table Summary",
        "",
        f"Table: {table_path}",
        f"Header u32: {list(header)}",
        f"Requests parsed: {len(request_rows)}",
        f"ReqData rows parsed: {len(reqdata_rows)}",
        f"Requests without SMZ media: {no_media}",
        f"Unique SMZ media names: {len(unique_media)}",
        "",
        "## Format Notes",
        "- Native loader reads a 0x40 common header.",
        "- Each request starts with a 0x48 header: 0x40-byte code string, u32 reqdata_count, u32 marker_count.",
        "- Each ReqData starts with 0x60 bytes; optional 0x0C fade data follows when signed u32_22 % 5 is nonzero.",
        "- Optional 0x28 ducking data follows when signed u32_23 % 3 equals 2.",
        "- Each marker is 0x24 bytes.",
        "- `RequestCtrl::codeName2ReqId` maps code strings to the parsed request index, not to `sound_id.dat` sound_resource_id.",
    ] + focus_lines
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[sound-request-struct-audit] requests: {len(request_rows)}")
    print(f"[sound-request-struct-audit] reqdata rows: {len(reqdata_rows)}")
    print(f"[sound-request-struct-audit] unique SMZ media: {len(unique_media)}")
    print(f"[sound-request-struct-audit] wrote {request_csv}")
    print(f"[sound-request-struct-audit] wrote {reqdata_csv}")
    print(f"[sound-request-struct-audit] wrote {summary_path}")


def parse_sound_hashreq_records(path: Path) -> tuple[tuple[int, ...], list[dict]]:
    if not path.exists():
        return tuple(), []
    data = path.read_bytes()
    if len(data) < 64:
        return tuple(), []
    header = struct.unpack("<16I", data[:64])
    record_count = header[7] if header[7] and 64 + header[7] * 16 <= len(data) else (len(data) - 64) // 16
    records = []
    for index in range(record_count):
        offset = 64 + index * 16
        record = data[offset : offset + 16]
        if len(record) < 16:
            break
        request_id = struct.unpack_from("<I", record, 8)[0]
        tail = struct.unpack_from("<I", record, 12)[0]
        records.append(
            {
                "record_index": index,
                "offset_hex": f"0x{offset:x}",
                "hash_le_hex": record[:8].hex().upper(),
                "hash_be_hex": record[:8][::-1].hex().upper(),
                "request_id": request_id,
                "tail_u32": tail,
            }
        )
    return header, records


def extract_sound_media_counter(request_rows: list[dict]) -> Counter:
    media = Counter()
    for row in request_rows:
        for field in ("media_before", "media_after", "nearest_media"):
            for match in SOUND_MEDIA_NAME_RE.findall(row.get(field, "")):
                media[match.upper()] += 1
    return media


def parse_smz_chunk_headers(smz_bin: Path, smz_add: Path) -> list[dict]:
    if not smz_bin.exists() or not smz_add.exists():
        return []
    add_data = smz_add.read_bytes()
    if len(add_data) % 4:
        return []
    offsets = list(struct.unpack(f"<{len(add_data) // 4}I", add_data))
    rows = []
    with smz_bin.open("rb") as f:
        for index, (start, end) in enumerate(zip(offsets, offsets[1:])):
            size = end - start
            f.seek(start)
            header = f.read(32)
            if len(header) < 32:
                continue
            fields = struct.unpack("<8I", header)
            if fields[1] == 380:
                channel_guess = 1
            elif fields[1] == 764:
                channel_guess = 2
            else:
                channel_guess = fields[5] if fields[5] in (1, 2) else ""
            rows.append(
                {
                    "chunk_index": index,
                    "offset": start,
                    "offset_hex": f"0x{start:x}",
                    "size": size,
                    "field0": fields[0],
                    "field1": fields[1],
                    "field2": fields[2],
                    "field3": fields[3],
                    "field4": fields[4],
                    "field5": fields[5],
                    "field6": fields[6],
                    "field7": fields[7],
                    "channel_guess": channel_guess,
                }
            )
    return rows


def command_sound_media_audit(args):
    manifest_dir = Path(args.manifest_dir)
    request_rows = read_csv(Path(args.sound_request_audit))
    request_by_id: dict[int, list[dict]] = defaultdict(list)
    for row in request_rows:
        sound_id = parse_optional_int(row.get("sound_resource_id"))
        if sound_id is not None:
            request_by_id[sound_id].append(row)

    media_counter = extract_sound_media_counter(request_rows)
    unique_smz = sum(1 for name in media_counter if name.endswith(".SMZ"))
    unique_pcm = sum(1 for name in media_counter if name.endswith(".PCM"))

    header, hash_records = parse_sound_hashreq_records(Path(args.hashreq_table))
    request_id_counts = Counter(int(row["request_id"]) for row in hash_records)
    linked_hash_rows = sum(count for request_id, count in request_id_counts.items() if request_id in request_by_id)
    linked_request_ids = sum(1 for request_id in request_id_counts if request_id in request_by_id)

    hash_rows = []
    for row in hash_records:
        request_id = int(row["request_id"])
        request_info = request_by_id.get(request_id, [{}])[0]
        hash_rows.append(
            row
            | {
                "request_label": request_info.get("request_label", ""),
                "has_sound_id_record": request_info.get("has_sound_id_record", ""),
                "suggested_name": request_info.get("suggested_name", ""),
                "ogg_duration_sec": request_info.get("ogg_duration_sec", ""),
            }
        )

    hash_csv = manifest_dir / "sound_hashreq_records.csv"
    write_csv(
        hash_csv,
        hash_rows,
        [
            "record_index",
            "offset_hex",
            "hash_le_hex",
            "hash_be_hex",
            "request_id",
            "tail_u32",
            "request_label",
            "has_sound_id_record",
            "suggested_name",
            "ogg_duration_sec",
        ],
    )

    smz_rows = parse_smz_chunk_headers(Path(args.smz_bin), Path(args.smz_add)) if args.smz_bin and args.smz_add else []
    smz_csv = manifest_dir / "smz_chunk_header_audit.csv"
    if smz_rows:
        write_csv(
            smz_csv,
            smz_rows,
            [
                "chunk_index",
                "offset",
                "offset_hex",
                "size",
                "field0",
                "field1",
                "field2",
                "field3",
                "field4",
                "field5",
                "field6",
                "field7",
                "channel_guess",
            ],
        )

    channel_counts = Counter(str(row.get("channel_guess", "")) for row in smz_rows)
    size_values = [int(row["size"]) for row in smz_rows]
    top_hash_requests = []
    for request_id, count in request_id_counts.most_common(20):
        request_info = request_by_id.get(request_id, [{}])[0]
        top_hash_requests.append(
            f"- {request_id}: {count} hash rows; {request_info.get('request_label', '')}; {request_info.get('suggested_name', '')}".rstrip()
        )

    summary_path = manifest_dir / "sound_media_summary.md"
    lines = [
        "# Sound Media Audit Summary",
        "",
        f"Sound request audit: {args.sound_request_audit}",
        f"Hash request table: {args.hashreq_table}",
        "",
        "## Media references from sound request table",
        f"- unique `.smz` media names: {unique_smz}",
        f"- unique `.pcm` media names: {unique_pcm}",
        f"- total media references in proximity fields: {sum(media_counter.values())}",
        "",
        "## zg_snd_hashreq_tbl.bin",
        f"- header_u32: {list(header)}",
        f"- hash request rows: {len(hash_records)}",
        f"- unique request ids: {len(request_id_counts)}",
        f"- hash rows linked to parsed sound request rows: {linked_hash_rows}",
        f"- request ids linked to parsed sound request rows: {linked_request_ids}",
        f"- rows with nonzero tail_u32: {sum(1 for row in hash_records if int(row['tail_u32']))}",
        "",
        "## Top hash request fanout",
        *top_hash_requests,
        "",
        "## SMZ installed pack",
    ]
    if smz_rows:
        lines.extend(
            [
                f"- smz chunks: {len(smz_rows)}",
                f"- chunk size min/max: {min(size_values)} / {max(size_values)}",
                f"- guessed mono chunks: {channel_counts.get('1', 0)}",
                f"- guessed stereo chunks: {channel_counts.get('2', 0)}",
                f"- chunk header CSV: {smz_csv}",
            ]
        )
    else:
        lines.append("- SMZ chunk headers not parsed; pass `--smz-bin` and `--smz-add` to include installed-pack stats.")
    lines.extend(
        [
            "",
            "## Limits",
            "- `zg_snd_hashreq_tbl.bin` maps 8-byte hashes to request ids, but these hashes are not the full 28-hex `.smz` media names.",
            "- `.smz` chunks are not directly accepted by ffprobe; decoding still requires format work or game decoder behavior.",
            "- This audit does not prove video-to-audio timing; it only improves the sound media/request side of the map.",
        ]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[sound-media-audit] unique smz media: {unique_smz}")
    print(f"[sound-media-audit] hash request rows: {len(hash_records)}")
    print(f"[sound-media-audit] wrote {hash_csv}")
    if smz_rows:
        print(f"[sound-media-audit] wrote {smz_csv}")
    print(f"[sound-media-audit] wrote {summary_path}")


def classify_native_sound_video_value(value: str) -> list[str]:
    categories = []
    if re.search(r"\b(?:smz(?:_add)?\.bin|zg_snd_hashreq_tbl\.bin|sound_id\.dat|ogg(?:_add)?\.bin)\b", value, re.IGNORECASE):
        categories.append("sound_media_table")
    if re.search(r"(?:fnSndRequest|nsmSndReq|SndReq|fnRxSndReqApp)", value):
        categories.append("sound_request_symbol")
    if re.search(r"EVT_ac\d{4}", value, re.IGNORECASE):
        categories.append("event_label")
    if re.search(r"(?:C_ac\d{4}.*fnPlayAnm|C_ac\d{4}.*fnPlaySND|C_ac\d{4}.*fnPlayLED)", value, re.IGNORECASE):
        categories.append("ac_play_method")
    return categories


def command_native_sound_video_audit(args):
    manifest_dir = Path(args.manifest_dir)
    native_strings_path = Path(args.native_strings)
    native_rows = read_csv(native_strings_path)
    focus_acs = [item.lower() for item in args.focus_ac.split(",") if item.strip()]

    evidence_rows = []
    for row in native_rows:
        value = row.get("value", "")
        categories = classify_native_sound_video_value(value)
        if not categories:
            continue
        ac_code = extract_ac_code(value)
        egrp_match = re.search(r"EGRP_(ac\d{4})", value, re.IGNORECASE)
        event_match = re.search(r"EVT_(ac\d{4})", value, re.IGNORECASE)
        if egrp_match:
            ac_code = egrp_match.group(1).lower()
        elif event_match:
            ac_code = event_match.group(1).lower()
        evidence_rows.append(
            {
                "category": ";".join(categories),
                "ac_code": ac_code,
                "library": row.get("library", ""),
                "first_offset_hex": row.get("first_offset_hex", ""),
                "tags": row.get("tags", ""),
                "value": value,
            }
        )

    evidence_rows.sort(key=lambda row: (row["category"], natural_key(row["ac_code"]), row["library"], row["first_offset_hex"]))
    evidence_csv = manifest_dir / "native_sound_video_evidence.csv"
    write_csv(
        evidence_csv,
        evidence_rows,
        ["category", "ac_code", "library", "first_offset_hex", "tags", "value"],
    )

    category_counts = Counter()
    ac_counts = Counter()
    focus_counts = {ac: Counter() for ac in focus_acs}
    for row in evidence_rows:
        categories = row["category"].split(";")
        for category in categories:
            category_counts[category] += 1
            if row["ac_code"]:
                focus_counts.setdefault(row["ac_code"], Counter())[category] += 1
        if row["ac_code"]:
            ac_counts[row["ac_code"]] += 1

    bgm_dir_acs = sorted(
        {
            row["ac_code"]
            for row in evidence_rows
            if "sound_request_symbol" in row["category"] and "fnSndRequest_BGM_DIR" in row["value"] and row["ac_code"]
        },
        key=natural_key,
    )
    ac_bgm_methods = sorted(
        {
            row["ac_code"]
            for row in evidence_rows
            if "sound_request_symbol" in row["category"]
            and "fnSndRequest_BGM" in row["value"]
            and "fnSndRequest_BGM_DIR" not in row["value"]
            and row["ac_code"]
        },
        key=natural_key,
    )
    event_acs = sorted(
        {row["ac_code"] for row in evidence_rows if "event_label" in row["category"] and row["ac_code"]},
        key=natural_key,
    )
    direct_media_values = sorted(
        {row["value"] for row in evidence_rows if "sound_media_table" in row["category"]},
        key=natural_key,
    )

    summary_path = manifest_dir / "native_sound_video_summary.md"
    lines = [
        "# Native Sound/Video Evidence Summary",
        "",
        f"Native strings source: {native_strings_path}",
        f"Evidence CSV: {evidence_csv}",
        "",
        "## Category counts",
        *[f"- {category}: {count}" for category, count in sorted(category_counts.items())],
        "",
        "## Direct media/table strings",
        *[f"- {value}" for value in direct_media_values],
        "",
        "## Native sound request evidence",
        f"- `fnSndRequest_BGM` class methods: {', '.join(ac_bgm_methods) if ac_bgm_methods else '(none found)'}",
        f"- `fnSndRequest_BGM_DIR` EGRP groups: {', '.join(bgm_dir_acs) if bgm_dir_acs else '(none found)'}",
        f"- `EVT_ac` groups: {', '.join(event_acs) if event_acs else '(none found)'}",
        "",
        "## Focus AC counts",
    ]
    for ac in focus_acs:
        counts = focus_counts.get(ac, Counter())
        lines.append(
            f"- {ac}: sound_request_symbol={counts.get('sound_request_symbol', 0)}, "
            f"event_label={counts.get('event_label', 0)}, "
            f"ac_play_method={counts.get('ac_play_method', 0)}, "
            f"sound_media_table={counts.get('sound_media_table', 0)}"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "- This is string-level/native-symbol evidence only. It does not prove a playable video-to-audio sync map.",
            "- `smz.bin`, `smz_add.bin`, and `zg_snd_hashreq_tbl.bin` are referenced from `libGameProc.so`, not from Java-level app code.",
            "- `SndMng.nsmSndReq(int)` is the Java/smali entry to native sound requests, but the meaningful request routing is native.",
            "- `ac5406`, `ac5407`, and `ac5408` expose dedicated `fnSndRequest_BGM` symbols plus `EVT_ac` labels.",
            "- `ac1101` through `ac1206` and `ac5209` appear in generic `C_ObjNml::fnSndRequest_BGM_DIR()` evidence.",
            "- No direct string-level `ac0902` sound request evidence was found in this audit.",
        ]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[native-sound-video-audit] evidence rows: {len(evidence_rows)}")
    print(f"[native-sound-video-audit] wrote {evidence_csv}")
    print(f"[native-sound-video-audit] wrote {summary_path}")


def command_review_special_videos(args):
    video_dir = Path(args.video_dir)
    out_dir = Path(args.out_dir) if args.out_dir else video_dir / "_review_special"
    files = sorted(
        [
            path
            for path in video_dir.rglob("*.mp4")
            if out_dir not in path.parents and "_review_special" not in path.parts
        ],
        key=lambda path: natural_key(str(path.relative_to(video_dir))),
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    for class_dir in ("audio_only", "blackish_video", "mostly_black_video", "no_video_stream", "probe_failed"):
        (out_dir / class_dir).mkdir(parents=True, exist_ok=True)
    print(f"[review-special-videos] scanning {len(files)} MP4 files")
    print(f"[review-special-videos] review dir: {out_dir}")

    rows = []
    processed = 0
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [
            executor.submit(review_one_special_video, path, video_dir, out_dir, args.mode, args.samples)
            for path in files
        ]
        for future in as_completed(futures):
            rows.append(future.result())
            processed += 1
            if processed % 250 == 0 or processed == len(files):
                print(f"[review-special-videos] processed {processed}/{len(files)}")

    rows.sort(key=lambda row: natural_key(row["relative_path"]))
    audit_path = out_dir / "special_video_audit.csv"
    write_csv(
        audit_path,
        rows,
        [
            "relative_path",
            "special_class",
            "review_path",
            "probe_ok",
            "probe_error",
            "duration_sec",
            "has_video",
            "has_audio",
            "video_codec",
            "audio_codec",
            "width",
            "height",
            "avg_mean_luma",
            "avg_nonblack_ratio",
            "max_nonblack_ratio",
            "max_bright_ratio",
            "sample_failures",
        ],
    )

    counts = defaultdict(int)
    for row in rows:
        counts[row["special_class"] or "normal"] += 1
    for class_name in ("normal", "audio_only", "blackish_video", "mostly_black_video", "no_video_stream", "probe_failed"):
        counts.setdefault(class_name, 0)
    summary_path = out_dir / "special_video_summary.md"
    lines = [
        "# Special Video Review Summary",
        "",
        f"Video dir: {video_dir}",
        f"Scanned MP4 files: {len(rows)}",
        "",
        "## Classes",
    ]
    for key, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {key}: {count}")
    lines += [
        "",
        "## Notes",
        "- `audio_only` means ffprobe found audio streams but no video stream.",
        "- `blackish_video` and `mostly_black_video` are based on sampled frame luminance.",
        "- Review files are hardlinked when possible, otherwise copied.",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[review-special-videos] wrote {audit_path}")
    print(f"[review-special-videos] wrote {summary_path}")


def command_bili_metadata_audit(args):
    manifest_dir = Path(args.manifest_dir)
    strings_xml = read_text_if_exists(ROOT / "unpacked_base" / "res" / "values" / "strings.xml")
    apktool_yml = read_text_if_exists(ROOT / "unpacked_base" / "apktool.yml")

    ac_labels = {row["code"].lower(): row for row in read_csv(manifest_dir / "ac_code_labels.csv") if row.get("code")}
    image_usage = {
        row["ac_code"].lower(): row
        for row in read_csv(manifest_dir / "internal_audit" / "image_ac_usage.csv")
        if row.get("ac_code")
    }
    native_sequences = {
        row["sequence_key"].lower(): row
        for row in read_csv(manifest_dir / "internal_audit" / "native_sequence_candidates.csv")
        if row.get("sequence_key")
    }

    sequence_rows = {
        row["sequence_key"].lower(): row
        for row in read_csv(manifest_dir / "video_review_sequences.csv")
        if row.get("sequence_key")
    }
    run_groups: dict[str, list[dict]] = defaultdict(list)
    for row in read_csv(manifest_dir / "video_review_unique_runs.csv"):
        key = row.get("sequence_key", "").lower()
        if key:
            run_groups[key].append(row)

    video_rows = []
    for key, sequence in sorted(sequence_rows.items(), key=lambda item: natural_key(item[0])):
        runs = run_groups.get(key, [])
        ac_code = extract_ac_code(key) or key
        label_row = ac_labels.get(ac_code, {})
        image_row = image_usage.get(ac_code, {})
        native_row = native_sequences.get(key, native_sequences.get(ac_code, {}))
        durations = [parse_optional_float(row.get("total_duration_sec", "")) or 0.0 for row in runs]
        item_counts = [parse_optional_int(row.get("item_count", "")) or 0 for row in runs]
        audio_counts = [parse_optional_int(row.get("has_audio_count", "")) or 0 for row in runs]
        longest_run = max(runs, key=lambda row: parse_optional_float(row.get("total_duration_sec", "")) or 0.0) if runs else {}
        display_label = first_nonempty(label_row.get("primary_label", ""), native_row.get("debug_labels", ""), ac_code)
        range_text = first_nonempty(
            f"{longest_run.get('start_number', '')}-{longest_run.get('end_number', '')}".strip("-"),
            f"{sequence.get('first_number', '')}-{sequence.get('last_number', '')}".strip("-"),
        )
        title_candidate = f"{display_label} {range_text}".strip()
        video_rows.append(
            {
                "sequence_key": key,
                "ac_code": ac_code,
                "title_candidate": title_candidate,
                "display_label": display_label,
                "all_labels": label_row.get("all_labels", ""),
                "confidence": sequence.get("confidence", ""),
                "review_action": sequence.get("review_action", ""),
                "sequence_item_count": sequence.get("item_count", ""),
                "sequence_total_duration_sec": sequence.get("total_duration_sec", ""),
                "sequence_has_audio_items": sequence.get("has_audio_items", ""),
                "shared_chunk_items": sequence.get("shared_chunk_items", ""),
                "resolutions": sequence.get("resolutions", ""),
                "run_count": len(runs),
                "total_run_duration_sec": f"{sum(durations):.3f}",
                "longest_run_duration_sec": longest_run.get("total_duration_sec", ""),
                "longest_run_items": longest_run.get("item_count", ""),
                "longest_run_range": f"{longest_run.get('start_number', '')}-{longest_run.get('end_number', '')}".strip("-"),
                "total_items": sum(item_counts),
                "runs_with_embedded_audio": sum(1 for count in audio_counts if count > 0),
                "image_ref_count": image_row.get("image_ref_count", ""),
                "image_examples": image_row.get("examples", ""),
                "native_token_count": native_row.get("native_token_count", ""),
                "native_numbered_count": native_row.get("numbered_count", ""),
            }
        )

    sound_rows = []
    sound_keywords = re.compile(
        r"(?:演出|セリフ|seq|BGM|Voice|voice|WIN|CZ|発展|前兆|激熱|プレミア|"
        r"マギア|まどか|ほむら|杏子|さやか|マミ|いろは|やちよ|レナ|かえで|ももこ|フェリシア|鶴乃)"
    )
    for row in read_csv(manifest_dir / "sound_request_audit.csv"):
        label = row.get("request_label", "")
        if not label or not sound_keywords.search(label):
            continue
        sound_rows.append(
            {
                "sound_resource_id": row.get("sound_resource_id", ""),
                "request_label": label,
                "sound_bank": row.get("sound_bank", ""),
                "suggested_name": row.get("suggested_name", ""),
                "ogg_duration_sec": row.get("ogg_duration_sec", ""),
                "nearest_media": row.get("nearest_media", ""),
            }
        )

    video_csv = manifest_dir / "bilibili_video_metadata_candidates.csv"
    write_csv(
        video_csv,
        video_rows,
        [
            "sequence_key",
            "ac_code",
            "title_candidate",
            "display_label",
            "all_labels",
            "confidence",
            "review_action",
            "sequence_item_count",
            "sequence_total_duration_sec",
            "sequence_has_audio_items",
            "shared_chunk_items",
            "resolutions",
            "run_count",
            "total_run_duration_sec",
            "longest_run_duration_sec",
            "longest_run_items",
            "longest_run_range",
            "total_items",
            "runs_with_embedded_audio",
            "image_ref_count",
            "image_examples",
            "native_token_count",
            "native_numbered_count",
        ],
    )

    sound_csv = manifest_dir / "bilibili_sound_label_candidates.csv"
    write_csv(
        sound_csv,
        sound_rows,
        ["sound_resource_id", "request_label", "sound_bank", "suggested_name", "ogg_duration_sec", "nearest_media"],
    )

    summary_path = manifest_dir / "bilibili_metadata_summary.md"
    lines = [
        "# Bilibili Metadata Audit Summary",
        "",
        "## App",
        f"- app_name: {extract_xml_string(strings_xml, 'app_name')}",
        f"- app_icon_name: {extract_xml_string(strings_xml, 'app_icon_name')}",
        f"- apk_version_name: {extract_yaml_scalar(apktool_yml, 'versionName')}",
        f"- apk_version_code: {extract_yaml_scalar(apktool_yml, 'versionCode')}",
        "",
        "## Useful Local Sources",
        "- `ac_code_labels.csv`: debug/display labels for ac codes, useful for title prefixes.",
        "- `video_review_unique_runs.csv`: continuous unique video runs, useful for deciding upload units.",
        "- `bilibili_video_metadata_candidates.csv`: joined video/title/image/native metadata candidates.",
        "- `sound_request_audit.csv`: sound request labels and OGG mapping candidates.",
        "- `bilibili_sound_label_candidates.csv`: filtered sound labels useful for upload titles/descriptions.",
        "- `image_ac_usage.csv`: image asset names can identify story, character, ending, profile, and UI context.",
        "",
        "## Counts",
        f"- video metadata rows: {len(video_rows)}",
        f"- filtered sound label rows: {len(sound_rows)}",
        "",
        "## Limits",
        "- Sound labels are not yet synchronized to video playback.",
        "- `nearest_media` is a sound-table proximity candidate, not proof of timing.",
        "- Shared video chunks still need manual review before final public upload grouping.",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[bili-metadata-audit] wrote {video_csv}")
    print(f"[bili-metadata-audit] wrote {sound_csv}")
    print(f"[bili-metadata-audit] wrote {summary_path}")


def resolve_candidate_slice_dir(video_dir: Path) -> Path:
    if video_dir.name.lower() == "multicandidate_slices":
        return video_dir
    nested = video_dir / "MultiCandidate_Slices"
    if nested.exists():
        return nested
    return video_dir


def parse_candidate_slice_path(path: Path) -> dict | None:
    match = CANDIDATE_SLICE_RE.match(path.stem)
    if not match:
        return None
    return {
        "package": match.group("package").lower(),
        "index": int(match.group("index")),
        "index_text": match.group("index"),
        "candidates": int(match.group("candidates")),
        "path": path,
    }


def build_candidate_slice_runs(candidate_dir: Path) -> list[list[dict]]:
    items = []
    for path in candidate_dir.glob("*.mp4"):
        info = parse_candidate_slice_path(path)
        if info:
            items.append(info)
    items.sort(key=lambda item: (item["package"], item["index"]))

    runs: list[list[dict]] = []
    current: list[dict] = []
    for item in items:
        if (
            current
            and item["package"] == current[-1]["package"]
            and item["candidates"] == current[-1]["candidates"]
            and item["index"] == current[-1]["index"] + 1
        ):
            current.append(item)
            continue
        if current:
            runs.append(current)
        current = [item]
    if current:
        runs.append(current)
    return runs


def candidate_run_output_name(run: list[dict]) -> str:
    first = run[0]
    last = run[-1]
    if len(run) == 1:
        return first["path"].name
    return (
        f"{first['package']}_video_{first['index']:04d}-{last['index']:04d}"
        f"_candidates{first['candidates']}.mp4"
    )


def collect_run_probe_summary(run: list[dict], probe: bool) -> dict:
    if not probe:
        return {"audio_source_count": "", "duration_sum_sec": ""}

    audio_count = 0
    duration_sum = 0.0
    for item in run:
        info = probe_mp4(item["path"])
        if info.get("has_audio"):
            audio_count += 1
        duration = parse_optional_float(str(info.get("duration_sec", "")))
        if duration is not None:
            duration_sum += duration
    return {
        "audio_source_count": audio_count,
        "duration_sum_sec": f"{duration_sum:.3f}",
    }


def write_candidate_concat_list(run: list[dict], list_path: Path):
    list_path.parent.mkdir(parents=True, exist_ok=True)
    list_path.write_text("\n".join(ffconcat_path(item["path"]) for item in run) + "\n", encoding="utf-8")


def run_ffmpeg_candidate_merge(
    run: list[dict],
    output: Path,
    list_path: Path,
    hflip: bool,
    drop_audio: bool,
    crf: int,
) -> bool:
    output.parent.mkdir(parents=True, exist_ok=True)
    if len(run) == 1:
        cmd = ["ffmpeg", "-y", "-i", str(run[0]["path"])]
    else:
        write_candidate_concat_list(run, list_path)
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_path)]

    video_filters = []
    if hflip:
        video_filters.append("hflip")
    if video_filters:
        cmd.extend(["-vf", ",".join(video_filters)])

    cmd.extend(["-c:v", "libx264", "-crf", str(crf), "-pix_fmt", "yuv420p"])
    if drop_audio:
        cmd.append("-an")
    else:
        cmd.extend(["-c:a", "aac", "-b:a", "192k"])
    cmd.append(str(output))

    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if result.returncode != 0:
        print(f"[merge-candidate-runs] failed: {output.name}", file=sys.stderr)
        print(result.stderr.decode("utf-8", errors="ignore")[-2000:], file=sys.stderr)
        return False
    return True


def command_merge_candidate_runs(args):
    candidate_dir = resolve_candidate_slice_dir(Path(args.video_dir))
    out_dir = Path(args.out_dir)
    output_video_dir = out_dir / candidate_dir.name
    list_dir = out_dir / "concat_lists"
    manifest_path = out_dir / "merge_candidate_runs_manifest.csv"

    runs = build_candidate_slice_runs(candidate_dir)
    rows = []
    executed = 0
    failed = 0
    for run in runs:
        first = run[0]
        last = run[-1]
        output_name = candidate_run_output_name(run)
        status = "merged" if len(run) > 1 else "singleton"
        if args.hflip:
            status += "_hflip"
        if args.drop_audio:
            status += "_video_only"
        output = output_video_dir / output_name
        list_path = list_dir / f"{Path(output_name).stem}.ffconcat.txt"
        probe_summary = collect_run_probe_summary(run, args.probe)
        row = {
            "output": output_name,
            "status": status,
            "source_count": len(run),
            "package": first["package"],
            "start_index": first["index"],
            "end_index": last["index"],
            "candidates": first["candidates"],
            "audio_source_count": probe_summary["audio_source_count"],
            "duration_sum_sec": probe_summary["duration_sum_sec"],
            "list": str(list_path) if len(run) > 1 else "",
        }
        rows.append(row)

        print(
            f"[merge-candidate-runs] {output_name}: {len(run)} source(s), "
            f"candidates={first['candidates']}"
        )
        if not args.execute:
            continue
        if run_ffmpeg_candidate_merge(run, output, list_path, args.hflip, args.drop_audio, args.crf):
            executed += 1
        else:
            failed += 1

    write_csv(
        manifest_path,
        rows,
        [
            "output",
            "status",
            "source_count",
            "package",
            "start_index",
            "end_index",
            "candidates",
            "audio_source_count",
            "duration_sum_sec",
            "list",
        ],
    )
    merged = sum(1 for row in rows if int(row["source_count"]) > 1)
    singletons = len(rows) - merged
    print(f"[merge-candidate-runs] candidate dir: {candidate_dir}")
    print(f"[merge-candidate-runs] wrote {manifest_path}")
    print(f"[merge-candidate-runs] runs: {len(rows)}; merged runs: {merged}; singletons: {singletons}")
    if args.execute:
        print(f"[merge-candidate-runs] executed: {executed}; failed: {failed}")


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

    review = sub.add_parser("video-review", help="review exported MP4s against internal sequence candidates")
    review.add_argument("--video-dir", default=str(ROOT / "final_mp4_videos"))
    review.add_argument("--manifest-dir", default=str(DEFAULT_MANIFEST_DIR))
    review.add_argument("--mp4-audit", default="", help="optional mp4_ffprobe_audit.csv path")
    review.add_argument("--sequence-csv", default="", help="optional video_sequence_candidates.csv path")
    review.add_argument("--min-run", type=int, default=2, help="minimum unique contiguous run length to report")
    review.add_argument("--write-concat-plans", action="store_true", help="write ffconcat text files for unique preview runs")
    review.add_argument("--max-concat-plans", type=int, default=200, help="maximum ffconcat text files to write")
    review.set_defaults(func=command_video_review)

    sound_request = sub.add_parser("sound-request-audit", help="parse sound request table and join sound_id metadata")
    sound_request.add_argument("--manifest-dir", default=str(DEFAULT_MANIFEST_DIR))
    sound_request.add_argument("--table-path", default=str(SOUND_REQUEST_TABLE_PATH))
    sound_request.add_argument("--ogg-audit", default=str(DEFAULT_MANIFEST_DIR / "ramdisk_audit" / "ogg_ffprobe_audit.csv"))
    sound_request.add_argument("--context-bytes", type=int, default=320)
    sound_request.set_defaults(func=command_sound_request_audit)

    sound_request_struct = sub.add_parser(
        "sound-request-struct-audit",
        help="parse zg_snd_request_tbl.bin using the native request/ReqData layout",
    )
    sound_request_struct.add_argument("--manifest-dir", default=str(DEFAULT_MANIFEST_DIR))
    sound_request_struct.add_argument("--table-path", default=str(SOUND_REQUEST_TABLE_PATH))
    sound_request_struct.add_argument(
        "--focus-codes",
        default="9078,296,283,6825,26497,6830,8032,1053,1052,1051,1050,1049",
        help="comma-separated sound code names to summarize",
    )
    sound_request_struct.set_defaults(func=command_sound_request_struct_audit)

    sound_media = sub.add_parser("sound-media-audit", help="audit .smz/.pcm media refs, hash request table, and optional installed SMZ pack")
    sound_media.add_argument("--manifest-dir", default=str(DEFAULT_MANIFEST_DIR))
    sound_media.add_argument("--sound-request-audit", default=str(DEFAULT_MANIFEST_DIR / "sound_request_audit.csv"))
    sound_media.add_argument("--hashreq-table", default=str(SOUND_HASHREQ_TABLE_PATH))
    sound_media.add_argument("--smz-bin", default="")
    sound_media.add_argument("--smz-add", default="")
    sound_media.set_defaults(func=command_sound_media_audit)

    native_sound_video = sub.add_parser("native-sound-video-audit", help="summarize native string evidence for sound/video linkage")
    native_sound_video.add_argument("--manifest-dir", default=str(DEFAULT_MANIFEST_DIR))
    native_sound_video.add_argument("--native-strings", default=str(DEFAULT_MANIFEST_DIR / "internal_audit" / "native_strings.csv"))
    native_sound_video.add_argument(
        "--focus-ac",
        default="ac0902,ac4921,ac0904,ac3409,ac3410,ac5102,ac5406,ac5407,ac5408",
        help="comma-separated AC groups to highlight",
    )
    native_sound_video.set_defaults(func=command_native_sound_video_audit)

    special = sub.add_parser("review-special-videos", help="probe MP4s and collect audio-only or black-screen review cases")
    special.add_argument("--video-dir", required=True)
    special.add_argument("--out-dir", default="")
    special.add_argument("--mode", choices=["copy", "hardlink"], default="hardlink")
    special.add_argument("--workers", type=int, default=4)
    special.add_argument("--samples", type=int, default=3)
    special.set_defaults(func=command_review_special_videos)

    bili = sub.add_parser("bili-metadata-audit", help="build Bilibili-oriented title/label metadata reports")
    bili.add_argument("--manifest-dir", default=str(DEFAULT_MANIFEST_DIR))
    bili.set_defaults(func=command_bili_metadata_audit)

    merge = sub.add_parser("merge-videos", help="merge already named acXXXX mp4 groups; dry-run by default")
    merge.add_argument("--video-dir", default=str(DEFAULT_OUTPUT_DIR / "videos"))
    merge.add_argument("--execute", action="store_true")
    merge.set_defaults(func=command_merge_videos)

    candidate_merge = sub.add_parser(
        "merge-candidate-runs",
        help="merge consecutive main/patch video slices with the same candidatesN suffix; dry-run by default",
    )
    candidate_merge.add_argument(
        "--video-dir",
        default=str(DEFAULT_OUTPUT_DIR / "videos"),
        help="video root containing MultiCandidate_Slices, or the MultiCandidate_Slices folder itself",
    )
    candidate_merge.add_argument("--out-dir", default=str(DEFAULT_OUTPUT_DIR / "merged_candidate_runs"))
    candidate_merge.add_argument("--execute", action="store_true")
    candidate_merge.add_argument("--hflip", action="store_true", help="apply horizontal flip while encoding")
    candidate_merge.add_argument("--drop-audio", action="store_true", help="write video-only output")
    candidate_merge.add_argument("--probe", action="store_true", help="probe source audio count and duration for manifest")
    candidate_merge.add_argument("--crf", type=int, default=16)
    candidate_merge.set_defaults(func=command_merge_candidate_runs)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
