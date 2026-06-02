from __future__ import annotations

import argparse
import csv
import re
import struct
from collections import defaultdict
from pathlib import Path

from magireco_asset_pipeline import (
    CHUNK_ARCHIVES,
    GDB_PATH,
    ROOT,
    VIDEO_ARCHIVES,
    extract_ac_code,
    load_label_maps,
    natural_key,
    parse_gdb_video_candidates,
    parse_named_gdb_refs,
    parse_sound_id_records,
    read_offsets,
    write_csv,
)


DEFAULT_OUT_DIR = ROOT / "asset_manifests" / "internal_audit"
JADX_SRC_DIR = ROOT / "jadx_audit" / "base_src_only" / "sources"
SMALI_DIR = ROOT / "unpacked_base" / "smali"
LIB_DIR = ROOT / "unpacked_lib" / "lib" / "arm64-v8a"
M_INFO_PATH = ROOT / "unpacked_assets" / "assets" / "m_info.dat"

TEXT_REF_PATTERNS = {
    "cri": re.compile(
        r"\bCriMng\b|\bcri(?:2|3)?(?:_add)?\.bin\b|SetCriFileNames|CRI_FILE_NAMES|CRI_ADDRESS_FILE_NAMES",
        re.IGNORECASE,
    ),
    "z2d": re.compile(r"\bz2d\b|z2d\.bin", re.IGNORECASE),
    "ogg": re.compile(r"\bogg\b|ogg\.bin|ogg_vorbise|OggS", re.IGNORECASE),
    "pcm": re.compile(r"\bpcm\b|pcm\.bin", re.IGNORECASE),
    "gdb": re.compile(r"\bgdb\b|gdb\.bin", re.IGNORECASE),
    "m_info": re.compile(r"m_info|M_INFO", re.IGNORECASE),
    "fusion": re.compile(r"FUSION|MARGE|MARGE_INFO", re.IGNORECASE),
    "sound": re.compile(r"SOUND_ID|SoundPack|SndMng|sound", re.IGNORECASE),
    "debug_prod": re.compile(r"DebugProd|dispatchData|DIR_NAME_TBL|PRODPTN|PRODTRG", re.IGNORECASE),
    "native_offset": re.compile(r"LoadOffset|GetFileOffset|nsysmLoadOffset", re.IGNORECASE),
}

AC_TOKEN_RE = re.compile(r"ac\d{4}[A-Za-z]*(?:_[A-Za-z0-9]+)*", re.IGNORECASE)
AC_WITH_FINAL_NUMBER_RE = re.compile(
    r"^(?P<key>ac\d{4}[A-Za-z]*(?:_[A-Za-z0-9]+)*?)_(?P<number>\d+)$",
    re.IGNORECASE,
)
RESOURCE_EXT_RE = re.compile(
    r"[A-Za-z0-9_./-]+\.(?:bin|dat|z2d|ogg|pcm|adx|usm|mp4|gtb|json|png|jpg|jpeg)",
    re.IGNORECASE,
)
NATIVE_SYMBOL_RE = re.compile(
    r"(?:CBinCtrl|SetCriFileNames|GetCriFileName|GetCriAddressFileName|LoadOffset|"
    r"GetFileOffset|MARGE|FUSION|SOUND_ID|CRI|OGG|PCM|Z2D|dispatchData)[A-Za-z0-9_:+./-]*",
    re.IGNORECASE,
)


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def iter_source_files() -> list[Path]:
    files: list[Path] = []
    for base, suffixes in ((JADX_SRC_DIR, (".java",)), (SMALI_DIR, (".smali",))):
        if not base.exists():
            continue
        for suffix in suffixes:
            files.extend(base.rglob(f"*{suffix}"))
    files.sort(key=lambda p: natural_key(rel(p)))
    return files


def build_text_refs() -> list[dict]:
    rows = []
    for path in iter_source_files():
        for line_no, line in enumerate(read_text(path).splitlines(), 1):
            tags = [name for name, pattern in TEXT_REF_PATTERNS.items() if pattern.search(line)]
            if not tags:
                continue
            rows.append(
                {
                    "source": "jadx" if path.suffix == ".java" else "smali",
                    "file": rel(path),
                    "line": line_no,
                    "tags": ";".join(tags),
                    "text": line.strip()[:500],
                }
            )
    return rows


def build_native_method_refs() -> list[dict]:
    rows = []
    java_pattern = re.compile(r"\bprivate\s+native\s+[^;{]+")
    smali_pattern = re.compile(r"\.method\s+(?P<flags>.*?\bnative\b.*?)\s+(?P<name>\S+)")

    for path in iter_source_files():
        text = read_text(path)
        if path.suffix == ".java":
            for line_no, line in enumerate(text.splitlines(), 1):
                match = java_pattern.search(line)
                if match:
                    rows.append(
                        {
                            "source": "jadx",
                            "file": rel(path),
                            "line": line_no,
                            "method": match.group(0).strip(),
                        }
                    )
        else:
            for line_no, line in enumerate(text.splitlines(), 1):
                match = smali_pattern.search(line)
                if match:
                    rows.append(
                        {
                            "source": "smali",
                            "file": rel(path),
                            "line": line_no,
                            "method": match.group("name").strip(),
                        }
                    )
    return rows


def extract_ascii_strings(data: bytes, min_len: int = 4):
    pattern = re.compile(rb"[\x20-\x7e]{" + str(min_len).encode("ascii") + rb",}")
    for match in pattern.finditer(data):
        value = match.group(0).decode("ascii", errors="ignore")
        yield match.start(), value


def classify_native_string(value: str) -> list[str]:
    tags = []
    if AC_TOKEN_RE.search(value):
        tags.append("ac_asset")
    if RESOURCE_EXT_RE.search(value):
        tags.append("resource_name")
    if NATIVE_SYMBOL_RE.search(value):
        tags.append("resource_symbol")
    if "jni" in value.lower() or "Java_" in value:
        tags.append("jni_symbol")
    if "debug" in value.lower() or "dispatch" in value.lower():
        tags.append("debug_symbol")
    return tags


def build_native_string_refs() -> tuple[list[dict], list[dict]]:
    string_rows = []
    ac_rows = []
    if not LIB_DIR.exists():
        return string_rows, ac_rows

    for lib_path in sorted(LIB_DIR.glob("*.so"), key=lambda p: natural_key(p.name)):
        data = lib_path.read_bytes()
        seen_values: set[tuple[str, str]] = set()
        seen_ac: set[tuple[str, str]] = set()
        for offset, value in extract_ascii_strings(data):
            tags = classify_native_string(value)
            if not tags:
                continue
            value_key = (lib_path.name, value)
            if value_key not in seen_values:
                seen_values.add(value_key)
                string_rows.append(
                    {
                        "library": lib_path.name,
                        "first_offset_hex": f"0x{offset:x}",
                        "tags": ";".join(tags),
                        "value": value[:500],
                    }
                )
            for token in AC_TOKEN_RE.findall(value):
                token = token.lower()
                ac_key = (lib_path.name, token)
                if ac_key in seen_ac:
                    continue
                seen_ac.add(ac_key)
                ac_rows.append(
                    {
                        "library": lib_path.name,
                        "ac_token": token,
                        "ac_code": extract_ac_code(token),
                        "source_string": value[:500],
                    }
                )
    string_rows.sort(key=lambda row: (row["library"], natural_key(row["value"])))
    ac_rows.sort(key=lambda row: (row["library"], natural_key(row["ac_token"])))
    return string_rows, ac_rows


def parse_m_info(group_index_to_label: dict[int, str]) -> tuple[list[dict], list[dict]]:
    if not M_INFO_PATH.exists():
        return [], []

    data = M_INFO_PATH.read_bytes()
    if len(data) < 9:
        return [{"path": rel(M_INFO_PATH), "error": "too short"}], []

    magic, count, data_size = struct.unpack("<BII", data[:9])
    header_rows = [
        {
            "path": rel(M_INFO_PATH),
            "magic": magic,
            "record_count": count,
            "data_size": data_size,
            "file_size": len(data),
            "expected_size": 9 + data_size,
        }
    ]

    rows = []
    pos = 9
    for idx in range(min(count, (len(data) - 9) // 12)):
        record = data[pos : pos + 12]
        pos += 12
        u16 = [struct.unpack("<H", record[i : i + 2])[0] for i in range(0, 12, 2)]
        u32 = [struct.unpack("<I", record[i : i + 4])[0] for i in range(0, 12, 4)]
        label_hits = []
        for field_idx, value in enumerate(u16):
            label = group_index_to_label.get(value)
            if label:
                label_hits.append(f"u16_{field_idx}={label}")
        rows.append(
            {
                "index": idx,
                "u16_0": u16[0],
                "u16_1": u16[1],
                "u16_2": u16[2],
                "u16_3": u16[3],
                "u16_4": u16[4],
                "u16_5": u16[5],
                "u32_0": u32[0],
                "u32_1": u32[1],
                "u32_2": u32[2],
                "debug_label_hits": ";".join(label_hits),
            }
        )
    return header_rows, rows


def build_video_usage_rows(candidates: dict[tuple[str, int], list[str]], code_to_labels: dict[str, list[str]]) -> list[dict]:
    rows = []
    for pack, (bin_path, add_path) in VIDEO_ARCHIVES.items():
        offsets = read_offsets(bin_path, add_path)
        for index, start in enumerate(offsets[:-1]):
            names = candidates.get((pack, index), [])
            code_counts: dict[str, int] = defaultdict(int)
            for name in names:
                code_counts[extract_ac_code(name)] += 1
            major_codes = sorted(code_counts.items(), key=lambda item: (-item[1], natural_key(item[0])))[:10]
            rows.append(
                {
                    "package": pack,
                    "index": index,
                    "offset": start,
                    "size": offsets[index + 1] - start,
                    "candidate_count": len(names),
                    "major_ac_codes": ";".join(f"{code}:{count}" for code, count in major_codes if code),
                    "first_candidates": ";".join(names[:30]),
                    "labels": ";".join(
                        code_to_labels.get(code, [code])[0] for code, _count in major_codes if code
                    ),
                }
            )
    rows.sort(key=lambda row: (-row["candidate_count"], row["package"], row["index"]))
    return rows


def split_sequence_key(name: str) -> tuple[str, int | None]:
    match = AC_WITH_FINAL_NUMBER_RE.match(name)
    if not match:
        return name.lower(), None
    return match.group("key").lower(), int(match.group("number"))


def longest_consecutive_run(numbers: list[int]) -> int:
    if not numbers:
        return 0
    best = current = 1
    for prev, cur in zip(numbers, numbers[1:]):
        if cur == prev + 1:
            current += 1
        elif cur != prev:
            best = max(best, current)
            current = 1
    return max(best, current)


def confidence_for_sequence(item_count: int, coverage_ratio: float, native_seen: bool) -> str:
    if item_count >= 4 and coverage_ratio >= 0.75 and native_seen:
        return "high"
    if item_count >= 3 and coverage_ratio >= 0.6:
        return "medium"
    if item_count >= 2:
        return "low"
    return "single"


def build_video_sequence_candidates(
    candidates: dict[tuple[str, int], list[str]],
    native_ac_tokens: set[str],
    code_to_labels: dict[str, list[str]],
) -> list[dict]:
    by_sequence: dict[str, list[dict]] = defaultdict(list)

    for (pack, index), names in candidates.items():
        for name in names:
            key, number = split_sequence_key(name)
            by_sequence[key].append(
                {
                    "name": name,
                    "number": number,
                    "package": pack,
                    "index": index,
                    "candidate_count": len(names),
                }
            )

    rows = []
    for key, items in by_sequence.items():
        items.sort(key=lambda item: (item["number"] is None, item["number"] or -1, natural_key(item["name"])))
        numbers = sorted({item["number"] for item in items if item["number"] is not None})
        run = longest_consecutive_run(numbers)
        span = (numbers[-1] - numbers[0] + 1) if numbers else 0
        coverage_ratio = (len(numbers) / span) if span else 0.0
        native_seen = any(item["name"].lower() in native_ac_tokens for item in items)
        chunk_refs = [
            f"{item['package']}:{item['index']}"
            for item in items
            if item["package"] not in ("native-only", "") and item["index"] != ""
        ]
        unique_chunk_refs = sorted(set(chunk_refs), key=natural_key)
        ambiguous_refs = [
            f"{item['package']}:{item['index']}({item['candidate_count']})"
            for item in items
            if isinstance(item["candidate_count"], int) and item["candidate_count"] > 1
        ]
        unique_refs = [
            f"{item['package']}:{item['index']}"
            for item in items
            if isinstance(item["candidate_count"], int) and item["candidate_count"] == 1
        ]
        ac_code = extract_ac_code(key)
        confidence = confidence_for_sequence(len(items), coverage_ratio, native_seen)
        if confidence in ("high", "medium") and ambiguous_refs:
            recommendation = "review_before_merge_shared_chunks"
        elif confidence in ("high", "medium"):
            recommendation = "candidate_for_ordered_merge"
        elif len(items) >= 2:
            recommendation = "name_group_only"
        else:
            recommendation = "single_reference"
        rows.append(
            {
                "sequence_key": key,
                "ac_code": ac_code,
                "debug_labels": ";".join(code_to_labels.get(ac_code, [])),
                "item_count": len(items),
                "numbered_count": len(numbers),
                "first_number": numbers[0] if numbers else "",
                "last_number": numbers[-1] if numbers else "",
                "longest_consecutive_run": run,
                "number_coverage_ratio": f"{coverage_ratio:.3f}",
                "native_seen": "yes" if native_seen else "no",
                "chunk_ref_count": len(unique_chunk_refs),
                "unique_chunk_refs": ";".join(unique_refs[:80]),
                "ambiguous_chunk_refs": ";".join(ambiguous_refs[:80]),
                "confidence": confidence,
                "recommendation": recommendation,
                "names": ";".join(item["name"] for item in items[:200]),
            }
        )
    rows.sort(
        key=lambda row: (
            {"high": 0, "medium": 1, "low": 2, "single": 3}.get(row["confidence"], 9),
            -int(row["item_count"]),
            natural_key(row["sequence_key"]),
        )
    )
    return rows


def build_native_sequence_candidates(native_ac_rows: list[dict], code_to_labels: dict[str, list[str]]) -> list[dict]:
    by_sequence: dict[str, set[str]] = defaultdict(set)
    libs_by_sequence: dict[str, set[str]] = defaultdict(set)
    for row in native_ac_rows:
        token = row["ac_token"]
        key, _number = split_sequence_key(token)
        by_sequence[key].add(token)
        libs_by_sequence[key].add(row["library"])

    rows = []
    for key, tokens in by_sequence.items():
        sorted_tokens = sorted(tokens, key=natural_key)
        numbers = sorted({split_sequence_key(token)[1] for token in sorted_tokens if split_sequence_key(token)[1] is not None})
        run = longest_consecutive_run(numbers)
        span = (numbers[-1] - numbers[0] + 1) if numbers else 0
        coverage_ratio = (len(numbers) / span) if span else 0.0
        ac_code = extract_ac_code(key)
        rows.append(
            {
                "sequence_key": key,
                "ac_code": ac_code,
                "debug_labels": ";".join(code_to_labels.get(ac_code, [])),
                "native_token_count": len(sorted_tokens),
                "numbered_count": len(numbers),
                "first_number": numbers[0] if numbers else "",
                "last_number": numbers[-1] if numbers else "",
                "longest_consecutive_run": run,
                "number_coverage_ratio": f"{coverage_ratio:.3f}",
                "libraries": ";".join(sorted(libs_by_sequence[key], key=natural_key)),
                "note": "native resource sequence; not proof of video by itself",
                "tokens": ";".join(sorted_tokens[:200]),
            }
        )
    rows.sort(key=lambda row: (-int(row["native_token_count"]), natural_key(row["sequence_key"])))
    return rows


def build_image_ac_usage_rows(code_to_labels: dict[str, list[str]]) -> list[dict]:
    by_code: dict[str, list[str]] = defaultdict(list)
    for name in parse_named_gdb_refs("z2d"):
        code = extract_ac_code(name)
        if not code:
            code = "unclassified"
        by_code[code].append(name)

    rows = []
    for code, names in sorted(by_code.items(), key=lambda item: natural_key(item[0])):
        rows.append(
            {
                "ac_code": code,
                "debug_labels": ";".join(code_to_labels.get(code, [])),
                "image_ref_count": len(names),
                "examples": ";".join(sorted(names, key=natural_key)[:50]),
            }
        )
    return rows


def build_audio_inventory_rows() -> list[dict]:
    rows = []
    sound_id_count = len(parse_sound_id_records())
    for kind in ("ogg", "pcm"):
        bin_path, add_path, ext = CHUNK_ARCHIVES[kind]
        offsets = read_offsets(bin_path, add_path)
        naming_status = "raw pcm chunks"
        if kind == "ogg":
            naming_status = f"sound_id.dat maps {sound_id_count} records; chunk 0 may be unmapped"
        rows.append(
            {
                "kind": kind,
                "source_bin": rel(bin_path),
                "address_file": rel(add_path),
                "chunk_count": len(offsets) - 1,
                "default_ext": ext,
                "naming_status": naming_status,
            }
        )
    return rows


def write_summary(out_dir: Path, stats: dict[str, int | str]) -> None:
    lines = [
        "Magireco internal asset audit",
        "",
        f"JADX source dir: {rel(JADX_SRC_DIR)}",
        f"Smali dir: {rel(SMALI_DIR)}",
        f"Native lib dir: {rel(LIB_DIR)}",
        "",
        f"Text refs: {stats['text_refs']}",
        f"Native methods: {stats['native_methods']}",
        f"Native relevant strings: {stats['native_strings']}",
        f"Native ac tokens: {stats['native_ac_tokens']}",
        f"Native sequence candidates: {stats['native_sequences']}",
        f"Video chunks: {stats['video_chunks']}",
        f"Video sequence candidates: {stats['video_sequences']}",
        f"High-confidence video sequences: {stats['high_sequences']}",
        f"Image ac groups: {stats['image_groups']}",
        f"Sound ID records: {stats['sound_id_records']}",
        f"m_info records: {stats['m_info_records']}",
        "",
        "Finding:",
        "- Java/smali provides asset package filenames and debug dispatch labels.",
        "- CRI package loading and exact runtime resource selection are native-side.",
        "- sound_id.dat maps named sound resource ids to OGG chunk indices.",
        "- Sequence rows are candidates only; shared chunk refs need review before merging.",
    ]
    (out_dir / "audit_summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def command_run(args) -> None:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    code_to_labels, group_index_to_label = load_label_maps()
    known_counts = {
        pack: len(read_offsets(bin_path, add_path)) - 1
        for pack, (bin_path, add_path) in VIDEO_ARCHIVES.items()
    }
    video_candidates = parse_gdb_video_candidates(known_counts)

    text_refs = build_text_refs()
    native_methods = build_native_method_refs()
    native_strings, native_ac_rows = build_native_string_refs()
    m_info_header, m_info_records = parse_m_info(group_index_to_label)
    video_usage = build_video_usage_rows(video_candidates, code_to_labels)
    native_ac_tokens = {row["ac_token"] for row in native_ac_rows}
    sequences = build_video_sequence_candidates(video_candidates, native_ac_tokens, code_to_labels)
    native_sequences = build_native_sequence_candidates(native_ac_rows, code_to_labels)
    image_usage = build_image_ac_usage_rows(code_to_labels)
    audio_inventory = build_audio_inventory_rows()
    sound_id_rows = parse_sound_id_records()

    write_csv(out_dir / "source_text_refs.csv", text_refs, ["source", "file", "line", "tags", "text"])
    write_csv(out_dir / "native_methods.csv", native_methods, ["source", "file", "line", "method"])
    write_csv(out_dir / "native_strings.csv", native_strings, ["library", "first_offset_hex", "tags", "value"])
    write_csv(out_dir / "native_ac_refs.csv", native_ac_rows, ["library", "ac_token", "ac_code", "source_string"])
    write_csv(out_dir / "m_info_header.csv", m_info_header, ["path", "magic", "record_count", "data_size", "file_size", "expected_size"])
    write_csv(
        out_dir / "m_info_records.csv",
        m_info_records,
        ["index", "u16_0", "u16_1", "u16_2", "u16_3", "u16_4", "u16_5", "u32_0", "u32_1", "u32_2", "debug_label_hits"],
    )
    write_csv(
        out_dir / "video_chunk_usage.csv",
        video_usage,
        ["package", "index", "offset", "size", "candidate_count", "major_ac_codes", "first_candidates", "labels"],
    )
    write_csv(
        out_dir / "video_sequence_candidates.csv",
        sequences,
        [
            "sequence_key",
            "ac_code",
            "debug_labels",
            "item_count",
            "numbered_count",
            "first_number",
            "last_number",
            "longest_consecutive_run",
            "number_coverage_ratio",
            "native_seen",
            "chunk_ref_count",
            "unique_chunk_refs",
            "ambiguous_chunk_refs",
            "confidence",
            "recommendation",
            "names",
        ],
    )
    write_csv(
        out_dir / "native_sequence_candidates.csv",
        native_sequences,
        [
            "sequence_key",
            "ac_code",
            "debug_labels",
            "native_token_count",
            "numbered_count",
            "first_number",
            "last_number",
            "longest_consecutive_run",
            "number_coverage_ratio",
            "libraries",
            "note",
            "tokens",
        ],
    )
    write_csv(out_dir / "image_ac_usage.csv", image_usage, ["ac_code", "debug_labels", "image_ref_count", "examples"])
    write_csv(out_dir / "audio_inventory.csv", audio_inventory, ["kind", "source_bin", "address_file", "chunk_count", "default_ext", "naming_status"])
    write_csv(
        out_dir / "sound_id_records.csv",
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

    stats = {
        "text_refs": len(text_refs),
        "native_methods": len(native_methods),
        "native_strings": len(native_strings),
        "native_ac_tokens": len(native_ac_rows),
        "video_chunks": len(video_usage),
        "video_sequences": len(sequences),
        "native_sequences": len(native_sequences),
        "high_sequences": sum(1 for row in sequences if row["confidence"] == "high"),
        "image_groups": len(image_usage),
        "sound_id_records": len(sound_id_rows),
        "m_info_records": len(m_info_records),
    }
    write_summary(out_dir, stats)

    print(f"[audit] wrote reports to {out_dir}")
    for key, value in stats.items():
        print(f"[audit] {key}: {value}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build read-only Magireco internal audit reports")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.set_defaults(func=command_run)
    return parser


def main(argv=None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
