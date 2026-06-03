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
