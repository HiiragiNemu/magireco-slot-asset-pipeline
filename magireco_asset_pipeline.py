from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import unicodedata
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
EVENT_CN_PATH = ROOT / "unpacked_assets" / "assets" / "EventCn.bin"
DEFAULT_NATIVE_LIB_PATH = ROOT / "unpacked_lib" / "lib" / "arm64-v8a" / "libGameProc.so"
Z2D_NATIVE_NAME_TABLE_OFFSET = 0x1455934
Z2D_NATIVE_NAME_COUNT = 12083
CRI_NATIVE_POINTER_TABLE_VA = 0x44A7088
CRI_NATIVE_NAME_COUNT = 7801
JAPANESE_TEXT_RE = re.compile(
    r"[\u3000-\u30ff\u3400-\u9fff\uff01-\uff60]"
    r"(?:[\u3000-\u30ff\u3400-\u9fff\uff01-\uff60A-Za-z0-9"
    r" \u3000、。！？・…ー〜～,.!?：:「」『』（）()]*)"
)
Z2D_GLYPH_DGI_RE = re.compile(
    rb"JM_([0-9A-Fa-f]{4,6})_[A-Za-z0-9_]+\.dgi"
)
Z2D_SOUND_LABEL_RE = re.compile(
    rb"(?P<sound_id>\d{4,5})_(?P<label_id>\d+)_(?P<speaker>[A-Za-z0-9]+)_"
)
Z2D_DGM_RE = re.compile(rb"([A-Za-z0-9_./-]+\.dgm)", re.IGNORECASE)
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


def read_ordered_offsets(bin_path: Path, add_path: Path) -> list[int]:
    data = add_path.read_bytes()
    if len(data) % 4:
        raise ValueError(f"offset table size is not divisible by 4: {add_path}")
    offsets = list(struct.unpack(f"<{len(data) // 4}I", data))
    if not offsets or offsets[0] != 0:
        raise ValueError(f"offset table does not start at zero: {add_path}")
    if offsets[-1] != bin_path.stat().st_size:
        offsets.append(bin_path.stat().st_size)
    if any(right < left for left, right in zip(offsets, offsets[1:])):
        raise ValueError(f"offset table is not monotonic: {add_path}")
    return offsets


def read_native_relative_name_table(native_lib: Path, table_offset: int, count: int) -> list[str]:
    data = native_lib.read_bytes()
    table_end = table_offset + count * 4
    if table_offset < 0 or table_end > len(data):
        raise ValueError(
            f"native name table 0x{table_offset:x}..0x{table_end:x} is outside {native_lib}"
        )

    names = []
    for index in range(count):
        relative_offset = struct.unpack_from("<i", data, table_offset + index * 4)[0]
        name_offset = table_offset + relative_offset
        if name_offset < 0 or name_offset >= len(data):
            raise ValueError(
                f"native name {index} points outside {native_lib}: 0x{name_offset:x}"
            )
        name_end = data.find(b"\x00", name_offset)
        if name_end < 0:
            raise ValueError(f"native name {index} is not NUL terminated")
        names.append(data[name_offset:name_end].decode("utf-8", errors="strict"))
    return names


def extract_japanese_text_candidates(blob: bytes) -> list[str]:
    candidates = []
    for part in blob.split(b"\x00"):
        decoded = part.decode("utf-8", errors="ignore")
        for match in JAPANESE_TEXT_RE.finditer(decoded):
            text = re.sub(r"[ \u3000]+", " ", match.group()).strip()
            japanese_count = sum(
                1
                for char in text
                if (
                    "\u3000" <= char <= "\u30ff"
                    or "\u3400" <= char <= "\u9fff"
                    or "\uff01" <= char <= "\uff60"
                )
            )
            if japanese_count >= 2 and text not in candidates:
                candidates.append(text)
    return candidates


def japanese_characters(text: str) -> list[str]:
    return [
        char
        for char in text
        if (
            "\u3000" <= char <= "\u30ff"
            or "\u3400" <= char <= "\u9fff"
            or "\uff01" <= char <= "\uff60"
        )
    ]


def select_display_text(
    candidates: list[str],
    glyph_characters: set[str] | None = None,
) -> str:
    if not candidates:
        return ""

    def score(text: str) -> tuple[int, int, int]:
        text_characters = japanese_characters(text)
        text_set = set(text_characters)
        glyph_match = 0
        if glyph_characters:
            if text_set == glyph_characters:
                glyph_match = 2
            elif text_set.issubset(glyph_characters):
                glyph_match = 1
        return glyph_match, len(text_characters), len(text)

    return max(candidates, key=score)


def read_elf64_relocated_pointer_names(
    native_lib: Path,
    table_va: int,
    count: int,
) -> list[str]:
    data = native_lib.read_bytes()
    if data[:4] != b"\x7fELF" or data[4] != 2 or data[5] != 1:
        raise ValueError(f"expected a little-endian ELF64 file: {native_lib}")

    program_offset = struct.unpack_from("<Q", data, 0x20)[0]
    section_offset = struct.unpack_from("<Q", data, 0x28)[0]
    program_entry_size = struct.unpack_from("<H", data, 0x36)[0]
    program_count = struct.unpack_from("<H", data, 0x38)[0]
    section_entry_size = struct.unpack_from("<H", data, 0x3A)[0]
    section_count = struct.unpack_from("<H", data, 0x3C)[0]

    load_segments = []
    for index in range(program_count):
        offset = program_offset + index * program_entry_size
        (
            segment_type,
            _flags,
            file_offset,
            virtual_address,
            _physical_address,
            file_size,
            _memory_size,
            _alignment,
        ) = struct.unpack_from("<IIQQQQQQ", data, offset)
        if segment_type == 1:
            load_segments.append((virtual_address, file_offset, file_size))

    def va_to_file_offset(virtual_address: int) -> int:
        for segment_va, file_offset, file_size in load_segments:
            if segment_va <= virtual_address < segment_va + file_size:
                return file_offset + virtual_address - segment_va
        raise ValueError(f"virtual address 0x{virtual_address:x} is not file-backed")

    relocations: dict[int, int] = {}
    for index in range(section_count):
        offset = section_offset + index * section_entry_size
        (
            _name_offset,
            section_type,
            _flags,
            _address,
            file_offset,
            file_size,
            _link,
            _info,
            _alignment,
            entry_size,
        ) = struct.unpack_from("<IIQQQQIIQQ", data, offset)
        if section_type != 4 or not entry_size:
            continue
        for entry_offset in range(file_offset, file_offset + file_size, entry_size):
            relocation_va, _relocation_info, addend = struct.unpack_from(
                "<QQq",
                data,
                entry_offset,
            )
            if table_va <= relocation_va < table_va + count * 8:
                relocations[relocation_va] = addend

    if len(relocations) != count:
        raise ValueError(
            f"native CRI pointer table has {len(relocations)} relocated entries; expected {count}"
        )

    names = []
    for index in range(count):
        pointer_va = table_va + index * 8
        string_va = relocations[pointer_va]
        string_offset = va_to_file_offset(string_va)
        string_end = data.find(b"\x00", string_offset)
        if string_end < 0:
            raise ValueError(f"CRI name {index} is not NUL terminated")
        names.append(data[string_offset:string_end].decode("utf-8", errors="strict"))
    return names


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


def parse_gdb_direction_z2d_timeline(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = path.read_bytes()
    marker_positions = []
    offset = 0
    while True:
        offset = data.find(b"GDB", offset)
        if offset < 0:
            break
        if offset + 8 <= len(data):
            marker_positions.append(offset)
        offset += 3

    event_rows = []
    event_name_re = re.compile(rb"(ac\d{4}[A-Za-z0-9_]*|next_\d+)\x00")
    z2d_re = re.compile(rb"([A-Za-z0-9_./ -]+\.z2d)\x00")
    negative_one_float = struct.pack("<f", -1.0)
    for marker_index, marker_offset in enumerate(marker_positions):
        record_type = data[marker_offset + 3]
        if record_type != 3:
            continue
        record_size = struct.unpack_from("<I", data, marker_offset + 4)[0]
        body_start = marker_offset + 8
        body_end = body_start + record_size
        if body_end > len(data):
            continue
        body = data[body_start:body_end]
        event_match = event_name_re.search(body)
        if not event_match:
            continue
        event_name = event_match.group(1).decode("ascii")
        resource_matches = list(z2d_re.finditer(body))
        for resource_order, resource_match in enumerate(resource_matches):
            resource_name = resource_match.group(1).decode("ascii").strip()
            window_end = (
                resource_matches[resource_order + 1].start()
                if resource_order + 1 < len(resource_matches)
                else len(body)
            )
            window = body[resource_match.end():window_end]
            sentinel_offset = window.rfind(negative_one_float)
            timeline_values = []
            if sentinel_offset >= 24:
                candidate_values = struct.unpack_from(
                    "<6f",
                    window,
                    sentinel_offset - 24,
                )
                if all(math.isfinite(value) for value in candidate_values):
                    timeline_values = list(candidate_values)

            start_frame = ""
            end_frame = ""
            key_start_frame = ""
            key_end_frame = ""
            if (
                len(timeline_values) == 6
                and timeline_values[0] >= 0
                and timeline_values[1] >= timeline_values[0]
            ):
                start_frame = timeline_values[0]
                end_frame = timeline_values[1]
                key_start_frame = timeline_values[2]
                key_end_frame = timeline_values[3]

            event_rows.append(
                {
                    "gdb_record_index": marker_index,
                    "gdb_record_offset_hex": f"0x{marker_offset:x}",
                    "event_name": event_name,
                    "z2d_order": resource_order,
                    "z2d_name": Path(resource_name).stem,
                    "z2d_filename": resource_name,
                    "start_frame": start_frame,
                    "end_frame": end_frame,
                    "key_start_frame": key_start_frame,
                    "key_end_frame": key_end_frame,
                }
            )
    return event_rows


def extract_z2d_dgm_names(blob: bytes) -> list[str]:
    names = []
    for match in Z2D_DGM_RE.finditer(blob):
        name = match.group(1).decode("ascii")[:-4]
        if name not in names:
            names.append(name)
    return names


def align4(value: int) -> int:
    return (value + 3) & ~3


def extract_z2d_canvas(blob: bytes) -> tuple[int | None, int | None]:
    match = re.search(rb"[A-Za-z0-9_./-]+\.z2d\x00", blob, re.IGNORECASE)
    if not match:
        return None, None
    offset = align4(match.end())
    for candidate_offset in (offset, offset + 4):
        if candidate_offset + 8 > len(blob):
            continue
        width, height = struct.unpack_from("<II", blob, candidate_offset)
        if 64 <= width <= 4096 and 64 <= height <= 4096:
            return width, height
    return None, None


def parse_z2d_layer_after_string(
    blob: bytes,
    string_start: int,
) -> dict | None:
    string_end = blob.find(b"\x00", string_start)
    if string_end < 0:
        return None
    layer_offset = align4(string_end + 1)
    if layer_offset + 4 > len(blob):
        return None

    layer_id, flags = struct.unpack_from("<HH", blob, layer_offset)
    if flags > 0x07FF:
        return None
    offset = layer_offset + 4

    def take(fmt: str):
        nonlocal offset
        size = struct.calcsize(fmt)
        if offset + size > len(blob):
            raise ValueError("truncated Z2D layer")
        values = struct.unpack_from(fmt, blob, offset)
        offset += size
        return values

    try:
        layer_kind = 0
        if not flags & 0x0400:
            layer_kind = take("<B")[0]
            offset = align4(offset)
        color = 0 if flags & 0x0008 else take("<I")[0]
        if flags & 0x0100:
            start_frame, end_frame = take("<hh")
        else:
            start_frame, end_frame = take("<ii")
        pos_x, pos_y = take("<ff")
        pos_z = take("<f")[0] if flags & 0x0001 else 0.0
        if flags & 0x0004:
            scale_x = scale_y = scale_z = 1.0
        else:
            scale_x, scale_y = take("<ff")
            scale_z = take("<f")[0] if flags & 0x0001 else 1.0
        if flags & 0x0040:
            rot_x = rot_y = rot_z = 0.0
        else:
            rot_x, rot_y = take("<ff")
            rot_z = take("<f")[0] if flags & 0x0001 else 0.0
        opacity = 1.0 if flags & 0x0020 else take("<f")[0]
        center_x, center_y = take("<ff")
        center_z = take("<f")[0] if flags & 0x0001 else 0.0
        if flags & 0x0200:
            width, height = take("<hh")
            width = float(width)
            height = float(height)
        else:
            width, height = take("<ff")
        pixel_ratio = 1.0 if flags & 0x0010 else take("<f")[0]
    except (ValueError, struct.error):
        return None

    numeric_values = [
        pos_x,
        pos_y,
        pos_z,
        scale_x,
        scale_y,
        scale_z,
        rot_x,
        rot_y,
        rot_z,
        opacity,
        center_x,
        center_y,
        center_z,
        width,
        height,
        pixel_ratio,
    ]
    if (
        end_frame < start_frame
        or not all(math.isfinite(value) for value in numeric_values)
        or width <= 0
        or height <= 0
        or width > 16384
        or height > 16384
    ):
        return None

    return {
        "layer_offset": layer_offset,
        "layer_end_offset": offset,
        "layer_id": layer_id,
        "layer_flags": flags,
        "layer_kind": layer_kind,
        "layer_color": color,
        "start_frame": start_frame,
        "end_frame": end_frame,
        "pos_x": pos_x,
        "pos_y": pos_y,
        "pos_z": pos_z,
        "scale_x": scale_x,
        "scale_y": scale_y,
        "scale_z": scale_z,
        "rot_x": rot_x,
        "rot_y": rot_y,
        "rot_z": rot_z,
        "opacity": opacity,
        "center_x": center_x,
        "center_y": center_y,
        "center_z": center_z,
        "width": width,
        "height": height,
        "pixel_ratio": pixel_ratio,
    }


def extract_z2d_dgm_layers(blob: bytes) -> dict[str, dict]:
    parent_layers = []
    ascii_string_re = re.compile(rb"[A-Za-z0-9_./-]{3,}\x00")
    for match in ascii_string_re.finditer(blob):
        raw_name = match.group(0)[:-1]
        if raw_name.lower().endswith(b".dgm"):
            continue
        try:
            name = raw_name.decode("ascii")
        except UnicodeDecodeError:
            continue
        layer = parse_z2d_layer_after_string(blob, match.start())
        if layer and (
            name.lower().endswith("_null")
            or name.lower().endswith("_root")
        ):
            parent_layers.append(
                {
                    **layer,
                    "layer_name": name,
                    "string_start": match.start(),
                }
            )

    layers = {}
    movie_re = re.compile(rb"\[([A-Za-z0-9_./-]+\.dgm)\]\x00", re.IGNORECASE)
    for match in movie_re.finditer(blob):
        layer = parse_z2d_layer_after_string(blob, match.start())
        if not layer:
            continue
        dgm_name = Path(match.group(1).decode("ascii")).stem
        parent = None
        preceding = [
            candidate
            for candidate in parent_layers
            if candidate["layer_end_offset"] <= match.start()
            and match.start() - candidate["layer_end_offset"] <= 32
        ]
        if preceding:
            parent = max(preceding, key=lambda item: item["layer_end_offset"])

        width = layer["width"] * layer["scale_x"]
        height = layer["height"] * layer["scale_y"]
        x = layer["pos_x"] - layer["center_x"] * layer["scale_x"]
        y = layer["pos_y"] - layer["center_y"] * layer["scale_y"]
        if parent:
            x = (
                parent["pos_x"]
                - parent["center_x"] * parent["scale_x"]
                + x * parent["scale_x"]
            )
            y = (
                parent["pos_y"]
                - parent["center_y"] * parent["scale_y"]
                + y * parent["scale_y"]
            )
            width *= parent["scale_x"]
            height *= parent["scale_y"]

        layers[dgm_name.lower()] = {
            **layer,
            "dgm_name": dgm_name,
            "parent_name": parent["layer_name"] if parent else "",
            "canvas_x": x,
            "canvas_y": y,
            "canvas_width": width,
            "canvas_height": height,
        }
    for key, layer in list(layers.items()):
        if not key.endswith("_lp"):
            continue
        base = layers.get(key[:-3])
        if base and base.get("parent_name") and not layer.get("parent_name"):
            for field in (
                "parent_name",
                "canvas_x",
                "canvas_y",
                "canvas_width",
                "canvas_height",
            ):
                layer[field] = base[field]
    return layers


def find_z2d_dgm_frame_interval(
    blob: bytes,
    dgm_name: str,
    expected_frames: int | None,
    z2d_end_frame: int | None,
) -> tuple[int | None, int | None, str]:
    if expected_frames is None or expected_frames <= 0:
        return None, None, "missing_media_duration"

    needle = f"{dgm_name}.dgm".encode("ascii")
    occurrence_offsets = []
    offset = 0
    while True:
        offset = blob.find(needle, offset)
        if offset < 0:
            break
        occurrence_offsets.append(offset)
        offset += len(needle)

    candidates = []
    for occurrence_offset in occurrence_offsets:
        string_end = blob.find(b"\x00", occurrence_offset)
        if string_end < 0:
            continue
        search_start = string_end + 1
        search_end = min(len(blob) - 3, search_start + 72)
        for pair_offset in range(search_start, search_end):
            start_frame, end_frame = struct.unpack_from("<HH", blob, pair_offset)
            if end_frame < start_frame:
                continue
            frame_count = end_frame - start_frame + 1
            frame_error = abs(frame_count - expected_frames)
            if frame_error > 1:
                continue
            if z2d_end_frame is not None and end_frame > z2d_end_frame:
                continue
            bracket_penalty = 0 if occurrence_offset and blob[occurrence_offset - 1] == ord("[") else 1
            candidates.append(
                (
                    frame_error,
                    bracket_penalty,
                    pair_offset - search_start,
                    start_frame,
                    end_frame,
                )
            )

    if not candidates:
        return None, None, "duration_interval_not_found"
    candidates.sort()
    best = candidates[0]
    equally_ranked = [
        item
        for item in candidates
        if item[:3] == best[:3]
    ]
    confidence = (
        "exact_duration_unique"
        if best[0] == 0 and len(equally_ranked) == 1
        else "near_duration_unique"
        if len(equally_ranked) == 1
        else "duration_interval_ambiguous"
    )
    return best[3], best[4], confidence


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
    temp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temp_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    temp_path.replace(path)


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


def parse_canvas_selector(value) -> tuple[int, int] | None:
    if value is None or value == "":
        return None
    if isinstance(value, tuple) and len(value) == 2:
        return int(value[0]), int(value[1])
    match = re.fullmatch(r"\s*(\d+)\s*[xX]\s*(\d+)\s*", str(value))
    if not match:
        raise ValueError(
            f"invalid canvas selector {value!r}; expected WIDTHxHEIGHT"
        )
    return int(match.group(1)), int(match.group(2))


def event_rows_duration_sec(rows: list[dict], frame_rate: float) -> float:
    timed_duration = max(
        (
            (parse_optional_float(row.get("end_frame")) + 1) / frame_rate
            if parse_optional_float(row.get("end_frame")) is not None
            else (parse_optional_float(row.get("relation_end_ms")) or 0.0)
            / 1000
        )
        for row in rows
    )
    if timed_duration > 0:
        return timed_duration
    return max(
        parse_optional_float(row.get("media_duration_sec")) or 0.0
        for row in rows
    )


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


def command_z2d_name_map(args):
    native_lib = Path(args.native_lib)
    z2d_bin = Path(args.z2d_bin)
    z2d_add = Path(args.z2d_add)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    names = read_native_relative_name_table(
        native_lib,
        args.name_table_offset,
        args.name_count,
    )
    offsets = read_ordered_offsets(z2d_bin, z2d_add)
    chunk_count = len(offsets) - 1
    if len(names) != chunk_count:
        raise ValueError(
            f"native Z2D names ({len(names)}) do not match physical chunks ({chunk_count})"
        )
    if len(set(names)) != len(names):
        raise ValueError("native Z2D name table contains duplicate names")

    gdb_refs = Counter(
        Path(name).stem.lower()
        for name in parse_named_gdb_refs(".z2d")
    )
    code_to_labels, _ = load_label_maps()
    focus_prefixes = [
        item.strip().lower()
        for item in args.focus_prefix.split(",")
        if item.strip()
    ]

    rows = []
    focus_rows = []
    for index, name in enumerate(names):
        start = offsets[index]
        end = offsets[index + 1]
        name_key = name.lower()
        row = {
            "chunk_index": index,
            "name": name,
            "filename": f"{name}.z2d",
            "offset": start,
            "size": end - start,
            "source_bin": str(z2d_bin),
            "native_table_offset_hex": f"0x{args.name_table_offset:x}",
            "native_name_count": len(names),
            "gdb_reference_count": gdb_refs.get(name_key, 0),
            "referenced_in_gdb": "yes" if gdb_refs.get(name_key, 0) else "no",
            "folder": folder_for_asset_name(name, code_to_labels),
        }
        rows.append(row)
        if not focus_prefixes or any(name_key.startswith(prefix) for prefix in focus_prefixes):
            focus_rows.append(row)

    fieldnames = [
        "chunk_index",
        "name",
        "filename",
        "offset",
        "size",
        "source_bin",
        "native_table_offset_hex",
        "native_name_count",
        "gdb_reference_count",
        "referenced_in_gdb",
        "folder",
    ]
    map_path = out_dir / "z2d_name_chunk_map.csv"
    focus_path = out_dir / "z2d_focus_name_chunk_map.csv"
    write_csv(map_path, rows, fieldnames)
    write_csv(focus_path, focus_rows, fieldnames)

    extracted = 0
    if args.extract:
        extract_dir = out_dir / "extracted"
        with z2d_bin.open("rb") as src:
            for row in focus_rows:
                target = extract_dir / safe_name(row["folder"]) / row["filename"]
                if target.exists() and not args.overwrite:
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                src.seek(int(row["offset"]))
                target.write_bytes(src.read(int(row["size"])))
                extracted += 1

    referenced = sum(row["referenced_in_gdb"] == "yes" for row in rows)
    focus_referenced = sum(row["referenced_in_gdb"] == "yes" for row in focus_rows)
    summary_path = out_dir / "z2d_name_chunk_map_summary.md"
    summary_path.write_text(
        "\n".join(
            [
                "# Z2D Native Name-to-Chunk Map",
                "",
                f"Native library: `{native_lib}`",
                f"Native relative-name table file offset: `0x{args.name_table_offset:x}`",
                f"Native table names: {len(names)}",
                f"Physical Z2D chunks: {chunk_count}",
                f"Unique native names: {len(set(names))}",
                f"Names referenced by parsed GDB resources: {referenced}",
                f"Names not referenced by parsed GDB resources: {len(rows) - referenced}",
                f"Focus prefixes: {', '.join(focus_prefixes) if focus_prefixes else '(all)'}",
                f"Focus rows: {len(focus_rows)}",
                f"Focus rows referenced by GDB: {focus_referenced}",
                f"Extracted this run: {extracted}",
                "",
                "## Native evidence",
                "",
                "- `CGFHardSystem::OpenFile` compares the requested Z2D basename against this table.",
                "- The native loop bound is 12083 and exactly matches the physical `z2d_add.bin` chunk count.",
                "- The matched name index is used directly to read adjacent offsets from `z2d_add.bin` and slice `z2d.bin`.",
                "- Therefore this CSV is an exact runtime name-to-physical-chunk mapping for this game build.",
                "",
                "## Subtitle note",
                "",
                "- `ac0902_serifu_*` entries are graphical Z2D dialogue/subtitle resources.",
                "- They are not plain SRT text. Rendering requires the Z2D scene, image dependencies, and timing/layer state.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"[z2d-name-map] native names: {len(names)}")
    print(f"[z2d-name-map] physical chunks: {chunk_count}")
    print(f"[z2d-name-map] focus rows: {len(focus_rows)}")
    print(f"[z2d-name-map] extracted this run: {extracted}")
    print(f"[z2d-name-map] wrote {map_path}")
    print(f"[z2d-name-map] wrote {summary_path}")


def command_subtitle_z2d_catalog(args):
    native_lib = Path(args.native_lib)
    z2d_bin = Path(args.z2d_bin)
    z2d_add = Path(args.z2d_add)
    ogg_dir = Path(args.ogg_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    names = read_native_relative_name_table(
        native_lib,
        args.name_table_offset,
        args.name_count,
    )
    offsets = read_ordered_offsets(z2d_bin, z2d_add)
    if len(names) != len(offsets) - 1:
        raise ValueError(
            f"native Z2D names ({len(names)}) do not match physical chunks ({len(offsets) - 1})"
        )

    _, request_rows, _, _ = parse_sound_request_struct_table(
        Path(args.sound_request_table)
    )
    _, hash_rows = parse_sound_hashreq_records(Path(args.sound_hashreq_table))
    hash_by_request_id = {
        int(row["request_id"]): row
        for row in hash_rows
    }
    requests_by_sound_id: dict[int, list[dict]] = defaultdict(list)
    for row in request_rows:
        match = re.match(r"^(\d{1,5})(?:_|$)", row["code_name"])
        if match:
            requests_by_sound_id[int(match.group(1))].append(row)

    sound_id_rows = parse_sound_id_records()
    sound_by_resource_id: dict[int, dict] = {}
    for row in sound_id_rows:
        sound_by_resource_id.setdefault(int(row["sound_resource_id"]), row)

    gdb_refs = Counter(
        Path(name).stem.lower()
        for name in parse_named_gdb_refs(".z2d")
    )
    focus_prefixes = [
        item.strip().lower()
        for item in args.focus_prefix.split(",")
        if item.strip()
    ]

    rows = []
    source = z2d_bin.open("rb")
    try:
        for index, name in enumerate(names):
            start = offsets[index]
            size = offsets[index + 1] - start
            source.seek(start)
            blob = source.read(size)

            glyph_matches = list(Z2D_GLYPH_DGI_RE.finditer(blob))
            glyph_character_set = {
                chr(int(match.group(1), 16))
                for match in glyph_matches
            }
            text_candidates = extract_japanese_text_candidates(blob)
            display_text = select_display_text(
                text_candidates,
                glyph_character_set,
            )
            sound_match = Z2D_SOUND_LABEL_RE.search(blob)
            if not display_text and not glyph_matches:
                continue

            sound_resource_id = (
                int(sound_match.group("sound_id"))
                if sound_match
                else None
            )
            sound_label_id = (
                int(sound_match.group("label_id"))
                if sound_match
                else None
            )
            speaker = (
                sound_match.group("speaker").decode("ascii", errors="ignore")
                if sound_match
                else ""
            )
            matching_requests = requests_by_sound_id.get(sound_resource_id, [])
            request_row = matching_requests[0] if len(matching_requests) == 1 else None
            request_id = int(request_row["request_id"]) if request_row else None
            hash_row = hash_by_request_id.get(request_id) if request_id is not None else None
            sound_row = sound_by_resource_id.get(sound_resource_id)
            ogg_name = sound_row["suggested_name"] if sound_row else ""
            ogg_path = ogg_dir / ogg_name if ogg_name else None
            duration_ms = int(hash_row["duration_ms_u32"]) if hash_row else 0
            focus_match = not focus_prefixes or any(
                name.lower().startswith(prefix)
                for prefix in focus_prefixes
            )

            glyph_names = []
            glyph_characters = []
            for match in glyph_matches:
                full_name = match.group(0).decode("ascii")
                if full_name not in glyph_names:
                    glyph_names.append(full_name)
                character = chr(int(match.group(1), 16))
                if character not in glyph_characters:
                    glyph_characters.append(character)

            material_dir = out_dir / "materialized" / safe_name(name, max_len=180)
            target_z2d = material_dir / f"{safe_name(name, max_len=180)}.z2d"
            target_ogg = material_dir / ogg_name if ogg_name else None
            target_srt = material_dir / f"{safe_name(name, max_len=180)}.srt"
            row = {
                "z2d_index": index,
                "z2d_name": name,
                "z2d_offset": start,
                "z2d_size": size,
                "gdb_reference_count": gdb_refs.get(name.lower(), 0),
                "display_text": display_text,
                "display_text_lines": display_text.replace(" ", " | "),
                "text_candidates": " || ".join(text_candidates),
                "glyph_dependency_count": len(glyph_names),
                "glyph_characters_unique": "".join(glyph_characters),
                "glyph_dgi_names": ";".join(glyph_names),
                "sound_resource_id": sound_resource_id if sound_resource_id is not None else "",
                "sound_label_id": sound_label_id if sound_label_id is not None else "",
                "speaker_code": speaker,
                "sound_request_match_count": len(matching_requests),
                "sound_request_id": request_id if request_id is not None else "",
                "sound_request_code_name": request_row["code_name"] if request_row else "",
                "sound_duration_ms": duration_ms,
                "sound_duration_sec": f"{duration_ms / 1000:.6f}" if duration_ms else "",
                "smz_media": request_row["first_smz_media"] if request_row else "",
                "ogg_name": ogg_name,
                "ogg_path": str(ogg_path) if ogg_path else "",
                "ogg_exists": "yes" if ogg_path and ogg_path.exists() else "no",
                "focus_match": "yes" if focus_match else "no",
                "target_z2d": str(target_z2d),
                "target_ogg": str(target_ogg) if target_ogg else "",
                "target_srt": str(target_srt),
            }
            rows.append(row)

            if args.execute and focus_match:
                material_dir.mkdir(parents=True, exist_ok=True)
                if args.overwrite or not target_z2d.exists():
                    target_z2d.write_bytes(blob)
                if ogg_path and ogg_path.exists() and target_ogg:
                    if target_ogg.exists() and args.overwrite:
                        target_ogg.unlink()
                    if not target_ogg.exists():
                        if args.link_mode == "hardlink":
                            os.link(ogg_path, target_ogg)
                        else:
                            shutil.copy2(ogg_path, target_ogg)
                if display_text and duration_ms:
                    subtitle_text = display_text.replace(" ", "\n")
                    target_srt.write_text(
                        "\n".join(
                            [
                                "1",
                                f"{srt_timestamp(0)} --> {srt_timestamp(duration_ms)}",
                                subtitle_text,
                                "",
                            ]
                        ),
                        encoding="utf-8-sig",
                    )
    finally:
        source.close()

    rows.sort(
        key=lambda row: (
            0 if row["display_text"] else 1,
            natural_key(row["z2d_name"]),
        )
    )
    fields = [
        "z2d_index",
        "z2d_name",
        "z2d_offset",
        "z2d_size",
        "gdb_reference_count",
        "display_text",
        "display_text_lines",
        "text_candidates",
        "glyph_dependency_count",
        "glyph_characters_unique",
        "glyph_dgi_names",
        "sound_resource_id",
        "sound_label_id",
        "speaker_code",
        "sound_request_match_count",
        "sound_request_id",
        "sound_request_code_name",
        "sound_duration_ms",
        "sound_duration_sec",
        "smz_media",
        "ogg_name",
        "ogg_path",
        "ogg_exists",
        "focus_match",
        "target_z2d",
        "target_ogg",
        "target_srt",
    ]
    catalog_path = out_dir / "subtitle_z2d_catalog.csv"
    focus_path = out_dir / "subtitle_z2d_focus.csv"
    write_csv(catalog_path, rows, fields)
    write_csv(
        focus_path,
        [row for row in rows if row["focus_match"] == "yes"],
        fields,
    )

    catalog_by_name = {
        row["z2d_name"].lower(): row
        for row in rows
    }
    event_timeline_rows = read_csv(Path(args.event_timeline_csv)) if args.event_timeline_csv else []
    event_rows_by_name: dict[str, list[dict]] = defaultdict(list)
    for event_row in event_timeline_rows:
        event_name = event_row.get("primary_animation", "").lower()
        if event_name:
            event_rows_by_name[event_name].append(event_row)

    subtitle_event_rows = []
    for relation in parse_gdb_direction_z2d_timeline(Path(args.gdb_path)):
        subtitle_row = catalog_by_name.get(relation["z2d_name"].lower())
        if not subtitle_row:
            continue
        start_frame = parse_optional_float(relation["start_frame"])
        end_frame = parse_optional_float(relation["end_frame"])
        start_ms = (
            round(start_frame * 1000 / args.frame_rate)
            if start_frame is not None
            else None
        )
        visual_end_ms = (
            round((end_frame + 1) * 1000 / args.frame_rate)
            if end_frame is not None
            else None
        )
        audio_duration_ms = parse_optional_int(subtitle_row["sound_duration_ms"]) or 0
        audio_end_ms = (
            start_ms + audio_duration_ms
            if start_ms is not None and audio_duration_ms
            else None
        )
        effective_end_ms = max(
            value
            for value in (visual_end_ms, audio_end_ms, start_ms)
            if value is not None
        ) if start_ms is not None else None

        matching_event_rows = event_rows_by_name.get(relation["event_name"].lower()) or [{}]
        for event_row in matching_event_rows:
            subtitle_event_rows.append(
                {
                    **relation,
                    "frame_rate": args.frame_rate,
                    "start_ms": start_ms if start_ms is not None else "",
                    "visual_end_ms": visual_end_ms if visual_end_ms is not None else "",
                    "audio_end_ms": audio_end_ms if audio_end_ms is not None else "",
                    "effective_end_ms": effective_end_ms if effective_end_ms is not None else "",
                    "display_text": subtitle_row["display_text"],
                    "srt_text": subtitle_row["display_text"].replace(" ", "\\n"),
                    "sound_resource_id": subtitle_row["sound_resource_id"],
                    "sound_request_id": subtitle_row["sound_request_id"],
                    "sound_duration_ms": subtitle_row["sound_duration_ms"],
                    "ogg_name": subtitle_row["ogg_name"],
                    "ogg_path": subtitle_row["ogg_path"],
                    "ogg_exists": subtitle_row["ogg_exists"],
                    "event_index": event_row.get("event_index", ""),
                    "event_root": event_row.get("root", ""),
                    "video_package": event_row.get("video_package", ""),
                    "video_index": event_row.get("video_index", ""),
                    "video_source_path": event_row.get("video_source_path", ""),
                    "video_mapping": event_row.get("video_mapping", ""),
                    "event_base_ogg_names": event_row.get("ogg_names", ""),
                    "timeline_confidence": (
                        "exact_gdb_frame_and_official_ogg"
                        if start_ms is not None and subtitle_row["ogg_exists"] == "yes"
                        else "exact_gdb_frame_only"
                        if start_ms is not None
                        else "gdb_relation_without_decoded_frame"
                    ),
                }
            )

    subtitle_event_rows.sort(
        key=lambda row: (
            natural_key(row["event_name"]),
            parse_optional_int(row["start_ms"]) or 0,
            parse_optional_int(row["z2d_order"]) or 0,
        )
    )
    event_fields = [
        "gdb_record_index",
        "gdb_record_offset_hex",
        "event_name",
        "z2d_order",
        "z2d_name",
        "z2d_filename",
        "start_frame",
        "end_frame",
        "key_start_frame",
        "key_end_frame",
        "frame_rate",
        "start_ms",
        "visual_end_ms",
        "audio_end_ms",
        "effective_end_ms",
        "display_text",
        "srt_text",
        "sound_resource_id",
        "sound_request_id",
        "sound_duration_ms",
        "ogg_name",
        "ogg_path",
        "ogg_exists",
        "event_index",
        "event_root",
        "video_package",
        "video_index",
        "video_source_path",
        "video_mapping",
        "event_base_ogg_names",
        "timeline_confidence",
    ]
    subtitle_event_path = out_dir / "subtitle_event_timeline.csv"
    write_csv(subtitle_event_path, subtitle_event_rows, event_fields)

    if args.execute:
        srt_dir = out_dir / "event_srt"
        if args.overwrite and srt_dir.exists():
            shutil.rmtree(srt_dir)
        grouped_event_rows: dict[str, list[dict]] = defaultdict(list)
        for row in subtitle_event_rows:
            if (
                row["display_text"]
                and row["start_ms"] != ""
                and row["timeline_confidence"] == "exact_gdb_frame_and_official_ogg"
                and row["z2d_name"].lower().startswith("cap")
            ):
                grouped_event_rows[row["event_name"]].append(row)
        for event_name, grouped_rows in grouped_event_rows.items():
            lines = []
            for cue_index, row in enumerate(grouped_rows, start=1):
                start_ms = int(row["start_ms"])
                end_ms = int(row["effective_end_ms"] or start_ms + 1000)
                if cue_index < len(grouped_rows):
                    next_start_ms = int(grouped_rows[cue_index]["start_ms"])
                    if next_start_ms > start_ms:
                        end_ms = min(end_ms, next_start_ms)
                if end_ms <= start_ms:
                    end_ms = start_ms + 1000
                lines.extend(
                    [
                        str(cue_index),
                        f"{srt_timestamp(start_ms)} --> {srt_timestamp(end_ms)}",
                        row["display_text"].replace(" ", "\n"),
                        "",
                    ]
                )
            srt_path = srt_dir / f"{safe_name(event_name)}.srt"
            srt_path.parent.mkdir(parents=True, exist_ok=True)
            srt_path.write_text("\n".join(lines), encoding="utf-8-sig")

    with_text = sum(bool(row["display_text"]) for row in rows)
    with_audio = sum(row["ogg_exists"] == "yes" for row in rows)
    unique_text = len({row["display_text"] for row in rows if row["display_text"]})
    timeline_with_audio = sum(
        row["timeline_confidence"] == "exact_gdb_frame_and_official_ogg"
        for row in subtitle_event_rows
    )
    timeline_events = len({row["event_name"] for row in subtitle_event_rows})
    summary_path = out_dir / "subtitle_z2d_catalog_summary.md"
    summary_path.write_text(
        "\n".join(
            [
                "# Z2D Subtitle Catalogue",
                "",
                f"Z2D chunks scanned: {len(names)}",
                f"Subtitle/glyph candidate Z2Ds: {len(rows)}",
                f"Rows with decoded Japanese display text: {with_text}",
                f"Unique decoded display texts: {unique_text}",
                f"Rows linked to an existing official OGG: {with_audio}",
                f"GDB subtitle/event timeline rows: {len(subtitle_event_rows)}",
                f"GDB events with subtitle relations: {timeline_events}",
                f"Timeline rows with exact frame and official OGG: {timeline_with_audio}",
                f"Focus prefixes: {', '.join(focus_prefixes) if focus_prefixes else '(all)'}",
                "",
                "## Proven mapping",
                "",
                "- Japanese display text is stored directly in Z2D scene data.",
                "- `JM_<Unicode code point>_*.dgi` dependencies are per-character graphical glyphs.",
                "- Numeric Z2D sound labels map to `sound_id.dat`, which gives the official OGG chunk.",
                "- Sound request rows provide the request ID, SMZ media name, and official duration.",
                f"- GDB frame positions are converted at the direction engine rate of {args.frame_rate:g} fps.",
                "- Spaces in `display_text` are preserved as graphical line separators; generated SRT files convert them to line breaks.",
                "",
                "## Limitation",
                "",
                "- `subtitle_event_timeline.csv` joins decoded text and OGG to the GDB event and exact start/end frames.",
                "- Some GDB events use shared or generic base video candidates and are primarily rendered from Z2D/image layers.",
                "- A video mapping does not prove that the raw USM alone contains the complete rendered scene.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"[subtitle-z2d-catalog] Z2D scanned: {len(names)}")
    print(f"[subtitle-z2d-catalog] candidate rows: {len(rows)}")
    print(f"[subtitle-z2d-catalog] rows with text: {with_text}")
    print(f"[subtitle-z2d-catalog] rows with official OGG: {with_audio}")
    print(f"[subtitle-z2d-catalog] GDB timeline rows: {len(subtitle_event_rows)}")
    print(f"[subtitle-z2d-catalog] exact frame + OGG rows: {timeline_with_audio}")
    print(f"[subtitle-z2d-catalog] wrote {catalog_path}")
    print(f"[subtitle-z2d-catalog] wrote {subtitle_event_path}")
    print(f"[subtitle-z2d-catalog] wrote {summary_path}")


def physical_video_key(
    path: Path,
    unique_name_to_key: dict[str, tuple[str, int]] | None = None,
) -> tuple[str, int] | None:
    match = re.match(
        r"^(main|patch)_video_(\d+)(?:_candidates\d+)?$",
        path.stem,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).lower(), int(match.group(2))

    if unique_name_to_key:
        key = unique_name_to_key.get(path.stem.lower())
        if key is not None:
            return key
    return None


def official_video_group(name: str) -> str:
    ac_code = extract_ac_code(name)
    if ac_code:
        return ac_code
    prefix = name.split("_", 1)[0]
    return safe_name(prefix, fallback="Other")


def command_cri_video_name_map(args):
    native_lib = Path(args.native_lib)
    video_dir = Path(args.video_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    names = read_elf64_relocated_pointer_names(
        native_lib,
        args.name_table_va,
        args.name_count,
    )
    if len(set(names)) != len(names):
        raise ValueError("native CRI filename table contains duplicate names")

    package_counts = {}
    for package, (bin_path, add_path) in VIDEO_ARCHIVES.items():
        package_counts[package] = len(read_ordered_offsets(bin_path, add_path)) - 1
    expected_count = sum(package_counts.values())
    if len(names) != expected_count:
        raise ValueError(
            f"native CRI names ({len(names)}) do not match physical chunks ({expected_count})"
        )

    gdb_candidates = parse_gdb_video_candidates(package_counts)
    unique_name_to_key: dict[str, tuple[str, int]] = {}
    ambiguous_unique_names = set()
    for key, candidate_names in gdb_candidates.items():
        if len(candidate_names) != 1:
            continue
        name_key = candidate_names[0].lower()
        if name_key in unique_name_to_key:
            ambiguous_unique_names.add(name_key)
        else:
            unique_name_to_key[name_key] = key
    for name_key in ambiguous_unique_names:
        unique_name_to_key.pop(name_key, None)

    source_by_key: dict[tuple[str, int], Path] = {}
    duplicate_keys: dict[tuple[str, int], list[Path]] = defaultdict(list)
    for path in find_existing_videos(video_dir):
        key = physical_video_key(path, unique_name_to_key)
        if key is None:
            continue
        if key in source_by_key:
            duplicate_keys[key].extend([source_by_key[key], path])
            continue
        source_by_key[key] = path
    if duplicate_keys:
        examples = ", ".join(
            f"{package}:{index}"
            for package, index in sorted(duplicate_keys)[:10]
        )
        raise ValueError(f"duplicate physical MP4 keys in {video_dir}: {examples}")

    focus_prefixes = [
        item.strip().lower()
        for item in args.focus_prefix.split(",")
        if item.strip()
    ]
    rows = []
    linked = 0
    global_index = 0
    used_target_keys = set()
    for package in ("main", "patch"):
        for package_index in range(package_counts[package]):
            name = names[global_index]
            source_path = source_by_key.get((package, package_index))
            group = official_video_group(name)
            is_focus = not focus_prefixes or any(
                name.lower().startswith(prefix)
                for prefix in focus_prefixes
            )
            target_stem = safe_name(name, max_len=180)
            target_path = (
                out_dir
                / "official_named_videos"
                / package
                / group
                / f"{target_stem}.mp4"
            )
            target_key = str(target_path).lower()
            if target_key in used_target_keys:
                target_path = target_path.with_name(
                    f"{target_stem}__idx{global_index:04d}.mp4"
                )
                target_key = str(target_path).lower()
            used_target_keys.add(target_key)
            row = {
                "global_index": global_index,
                "package": package,
                "package_index": package_index,
                "official_name": name,
                "official_filename": f"{name}.usm",
                "group": group,
                "is_serifu_resource": "yes" if "_serifu_" in name.lower() else "no",
                "source_mp4": str(source_path) if source_path else "",
                "source_exists": "yes" if source_path else "no",
                "target_mp4": str(target_path),
                "focus_match": "yes" if is_focus else "no",
                "native_pointer_table_va_hex": f"0x{args.name_table_va:x}",
            }
            rows.append(row)

            if args.execute and is_focus and source_path:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                if target_path.exists():
                    if not args.overwrite:
                        global_index += 1
                        continue
                    target_path.unlink()
                if args.link_mode == "hardlink":
                    os.link(source_path, target_path)
                else:
                    shutil.copy2(source_path, target_path)
                linked += 1
            global_index += 1

    fieldnames = [
        "global_index",
        "package",
        "package_index",
        "official_name",
        "official_filename",
        "group",
        "is_serifu_resource",
        "source_mp4",
        "source_exists",
        "target_mp4",
        "focus_match",
        "native_pointer_table_va_hex",
    ]
    map_path = out_dir / "cri_official_name_video_map.csv"
    focus_path = out_dir / "cri_official_name_video_focus.csv"
    write_csv(map_path, rows, fieldnames)
    write_csv(
        focus_path,
        [row for row in rows if row["focus_match"] == "yes"],
        fieldnames,
    )

    missing = [row for row in rows if row["source_exists"] == "no"]
    serifu_rows = [row for row in rows if row["is_serifu_resource"] == "yes"]
    summary_path = out_dir / "cri_official_name_video_map_summary.md"
    summary_path.write_text(
        "\n".join(
            [
                "# CRI Official Name-to-Video Map",
                "",
                f"Native library: `{native_lib}`",
                f"Native pointer table VA: `0x{args.name_table_va:x}`",
                f"Native official names: {len(names)}",
                f"Unique official names: {len(set(names))}",
                f"Main physical chunks: {package_counts['main']}",
                f"Patch physical chunks: {package_counts['patch']}",
                f"Source MP4 files matched: {len(rows) - len(missing)}",
                f"Source MP4 files missing: {len(missing)}",
                f"`*_serifu_*` CRI resources: {len(serifu_rows)}",
                f"Focus prefixes: {', '.join(focus_prefixes) if focus_prefixes else '(all)'}",
                f"Files linked/copied this run: {linked}",
                "",
                "## Exact native behavior",
                "",
                "- `CriResourceManager::BuildFileNameTable()` copies 7801 names from this pointer table.",
                "- `CriResourceManager::LoadUSMFileByName()` finds the name index and passes it directly to `LoadUSMFile(index)`.",
                "- `LoadUSMFile(index)` maps indices 0..5201 to `cri.bin` and indices 5202..7800 to `cri2.bin`.",
                "- The package-local index is therefore exact: main uses the same index; patch uses `global_index - 5202`.",
                "- This mapping supersedes heuristic GDB candidate names for physical video identification.",
                "",
                "## Safety",
                "",
                f"- Output mode: `{args.link_mode}`.",
                "- Source videos are never moved or modified.",
                "- Hard links share file data on the same volume but preserve independent directory entries.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"[cri-video-name-map] official names: {len(names)}")
    print(
        "[cri-video-name-map] physical chunks: "
        f"main={package_counts['main']} patch={package_counts['patch']}"
    )
    print(f"[cri-video-name-map] source MP4 matched: {len(rows) - len(missing)}")
    print(f"[cri-video-name-map] source MP4 missing: {len(missing)}")
    print(f"[cri-video-name-map] linked/copied this run: {linked}")
    print(f"[cri-video-name-map] wrote {map_path}")
    print(f"[cri-video-name-map] wrote {summary_path}")


def command_z2d_dgm_event_map(args):
    native_lib = Path(args.native_lib)
    z2d_bin = Path(args.z2d_bin)
    z2d_add = Path(args.z2d_add)
    cri_map_csv = Path(args.cri_map_csv)
    video_metadata_csv = Path(args.video_metadata_csv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    z2d_names = read_native_relative_name_table(
        native_lib,
        args.name_table_offset,
        args.name_count,
    )
    offsets = read_ordered_offsets(z2d_bin, z2d_add)
    if len(z2d_names) != len(offsets) - 1:
        raise ValueError(
            f"native Z2D names ({len(z2d_names)}) do not match physical chunks ({len(offsets) - 1})"
        )

    cri_rows = read_csv(cri_map_csv)
    cri_by_name = {
        row["official_name"].lower(): row
        for row in cri_rows
    }
    duration_by_key: dict[tuple[str, int], float] = {}
    if video_metadata_csv.exists():
        for row in read_csv(video_metadata_csv):
            package = row.get("package", "").lower()
            package_index = parse_optional_int(
                row.get("index") or row.get("package_index")
            )
            duration_sec = parse_optional_float(row.get("duration_sec"))
            if package and package_index is not None and duration_sec is not None:
                duration_by_key.setdefault((package, package_index), duration_sec)
    probe_cache_path = out_dir / "cri_video_probe_cache.csv"
    probe_rows = read_csv(probe_cache_path) if probe_cache_path.exists() else []
    for row in probe_rows:
        package = row.get("package", "").lower()
        package_index = parse_optional_int(row.get("package_index"))
        duration_sec = parse_optional_float(row.get("duration_sec"))
        if package and package_index is not None and duration_sec is not None:
            duration_by_key.setdefault((package, package_index), duration_sec)
    if args.probe_missing:
        missing_cri_rows = []
        for row in cri_rows:
            package = row.get("package", "").lower()
            package_index = parse_optional_int(row.get("package_index"))
            source_mp4 = Path(row["source_mp4"]) if row.get("source_mp4") else None
            if (
                package
                and package_index is not None
                and (package, package_index) not in duration_by_key
                and source_mp4
                and source_mp4.exists()
            ):
                missing_cri_rows.append((package, package_index, source_mp4))
        print(
            "[z2d-dgm-event-map] probing missing physical video durations: "
            f"{len(missing_cri_rows)}"
        )
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
            futures = {
                executor.submit(probe_mp4, source_mp4): (
                    package,
                    package_index,
                    source_mp4,
                )
                for package, package_index, source_mp4 in missing_cri_rows
            }
            for processed, future in enumerate(as_completed(futures), start=1):
                package, package_index, source_mp4 = futures[future]
                probe = future.result()
                duration_sec = parse_optional_float(probe.get("duration_sec"))
                if duration_sec is not None:
                    duration_by_key[(package, package_index)] = duration_sec
                probe_rows.append(
                    {
                        "package": package,
                        "package_index": package_index,
                        "source_mp4": str(source_mp4),
                        "duration_sec": (
                            f"{duration_sec:.6f}"
                            if duration_sec is not None
                            else ""
                        ),
                        "width": probe.get("width", ""),
                        "height": probe.get("height", ""),
                        "frame_rate": probe.get("frame_rate", ""),
                        "probe_ok": "yes" if probe.get("probe_ok") else "no",
                        "probe_error": probe.get("probe_error", ""),
                    }
                )
                if processed % 500 == 0 or processed == len(futures):
                    print(
                        "[z2d-dgm-event-map] probed "
                        f"{processed}/{len(futures)}"
                    )
        write_csv(
            probe_cache_path,
            sorted(
                probe_rows,
                key=lambda row: (row["package"], int(row["package_index"])),
            ),
            [
                "package",
                "package_index",
                "source_mp4",
                "duration_sec",
                "width",
                "height",
                "frame_rate",
                "probe_ok",
                "probe_error",
            ],
        )

    dependency_rows = []
    dependencies_by_z2d: dict[str, list[dict]] = defaultdict(list)
    with z2d_bin.open("rb") as source:
        for z2d_index, z2d_name in enumerate(z2d_names):
            source.seek(offsets[z2d_index])
            blob = source.read(offsets[z2d_index + 1] - offsets[z2d_index])
            dgm_names = extract_z2d_dgm_names(blob)
            if not dgm_names:
                continue
            z2d_end_frame = (
                struct.unpack_from("<I", blob, 0x0C)[0]
                if len(blob) >= 0x10
                else None
            )
            z2d_loop_point = (
                struct.unpack_from("<I", blob, 0x10)[0]
                if len(blob) >= 0x14
                else None
            )
            z2d_frame_rate = (
                struct.unpack_from("<f", blob, 0x14)[0]
                if len(blob) >= 0x18
                else args.frame_rate
            )
            if (
                not math.isfinite(z2d_frame_rate)
                or z2d_frame_rate <= 0
                or z2d_frame_rate > 240
            ):
                z2d_frame_rate = args.frame_rate

            dgm_layers = extract_z2d_dgm_layers(blob)
            z2d_canvas_width, z2d_canvas_height = extract_z2d_canvas(blob)
            dgm_name_set = {name.lower() for name in dgm_names}
            for dgm_order, dgm_name in enumerate(dgm_names):
                cri_row = cri_by_name.get(dgm_name.lower(), {})
                layer = dgm_layers.get(dgm_name.lower(), {})
                package = cri_row.get("package", "")
                package_index = parse_optional_int(cri_row.get("package_index"))
                duration_sec = (
                    duration_by_key.get((package, package_index))
                    if package and package_index is not None
                    else None
                )
                expected_frames = (
                    int(round(duration_sec * z2d_frame_rate))
                    if duration_sec is not None
                    else None
                )
                internal_start_frame, internal_end_frame, interval_confidence = (
                    find_z2d_dgm_frame_interval(
                        blob,
                        dgm_name,
                        expected_frames,
                        z2d_end_frame,
                    )
                )

                is_loop = dgm_name.lower().endswith("_lp")
                base_name = dgm_name[:-3] if is_loop else dgm_name
                has_loop_companion = (
                    not is_loop and f"{dgm_name.lower()}_lp" in dgm_name_set
                )
                role = (
                    "loop_cycle"
                    if is_loop and base_name.lower() in dgm_name_set
                    else "intro_before_loop"
                    if has_loop_companion
                    else "orphan_loop_cycle"
                    if is_loop
                    else "single_layer_segment"
                )
                row = {
                    "z2d_index": z2d_index,
                    "z2d_name": z2d_name,
                    "z2d_end_frame": z2d_end_frame if z2d_end_frame is not None else "",
                    "z2d_loop_point": (
                        z2d_loop_point
                        if z2d_loop_point is not None
                        else ""
                    ),
                    "z2d_frame_rate": f"{z2d_frame_rate:.6f}",
                    "z2d_canvas_width": (
                        z2d_canvas_width
                        if z2d_canvas_width is not None
                        else ""
                    ),
                    "z2d_canvas_height": (
                        z2d_canvas_height
                        if z2d_canvas_height is not None
                        else ""
                    ),
                    "dgm_order": dgm_order,
                    "dgm_name": dgm_name,
                    "dgm_role": role,
                    "dgm_base_name": base_name,
                    "internal_start_frame": (
                        internal_start_frame
                        if internal_start_frame is not None
                        else ""
                    ),
                    "internal_end_frame": (
                        internal_end_frame
                        if internal_end_frame is not None
                        else ""
                    ),
                    "interval_confidence": interval_confidence,
                    "media_duration_sec": (
                        f"{duration_sec:.6f}"
                        if duration_sec is not None
                        else ""
                    ),
                    "media_expected_frames": (
                        expected_frames
                        if expected_frames is not None
                        else ""
                    ),
                    "cri_match": "yes" if cri_row else "no",
                    "cri_global_index": cri_row.get("global_index", ""),
                    "package": package,
                    "package_index": (
                        package_index
                        if package_index is not None
                        else ""
                    ),
                    "official_name": cri_row.get("official_name", ""),
                    "source_mp4": cri_row.get("source_mp4", ""),
                    "target_mp4": cri_row.get("target_mp4", ""),
                    "layer_parent_name": layer.get("parent_name", ""),
                    "layer_canvas_x": (
                        f"{layer['canvas_x']:.6f}"
                        if layer
                        else ""
                    ),
                    "layer_canvas_y": (
                        f"{layer['canvas_y']:.6f}"
                        if layer
                        else ""
                    ),
                    "layer_canvas_width": (
                        f"{layer['canvas_width']:.6f}"
                        if layer
                        else ""
                    ),
                    "layer_canvas_height": (
                        f"{layer['canvas_height']:.6f}"
                        if layer
                        else ""
                    ),
                    "layer_opacity": (
                        f"{layer['opacity']:.6f}"
                        if layer
                        else ""
                    ),
                    "layer_flags_hex": (
                        f"0x{layer['layer_flags']:04x}"
                        if layer
                        else ""
                    ),
                }
                dependency_rows.append(row)
                dependencies_by_z2d[z2d_name.lower()].append(row)

    dependency_fields = [
        "z2d_index",
        "z2d_name",
        "z2d_end_frame",
        "z2d_loop_point",
        "z2d_frame_rate",
        "z2d_canvas_width",
        "z2d_canvas_height",
        "dgm_order",
        "dgm_name",
        "dgm_role",
        "dgm_base_name",
        "internal_start_frame",
        "internal_end_frame",
        "interval_confidence",
        "media_duration_sec",
        "media_expected_frames",
        "cri_match",
        "cri_global_index",
        "package",
        "package_index",
        "official_name",
        "source_mp4",
        "target_mp4",
        "layer_parent_name",
        "layer_canvas_x",
        "layer_canvas_y",
        "layer_canvas_width",
        "layer_canvas_height",
        "layer_opacity",
        "layer_flags_hex",
    ]
    dependency_path = out_dir / "z2d_dgm_dependencies.csv"
    write_csv(dependency_path, dependency_rows, dependency_fields)

    relation_rows = parse_gdb_direction_z2d_timeline(Path(args.gdb_path))
    event_rows = []
    for relation in relation_rows:
        relation_start_frame = parse_optional_float(relation.get("start_frame"))
        relation_end_frame = parse_optional_float(relation.get("end_frame"))
        dependencies = dependencies_by_z2d.get(
            relation["z2d_name"].lower(),
            [],
        )
        if not dependencies:
            continue
        for dependency in dependencies:
            internal_start_frame = parse_optional_int(
                dependency.get("internal_start_frame")
            )
            internal_end_frame = parse_optional_int(
                dependency.get("internal_end_frame")
            )
            event_start_frame = (
                relation_start_frame + internal_start_frame
                if relation_start_frame is not None
                and internal_start_frame is not None
                else relation_start_frame
            )
            event_end_frame = (
                relation_start_frame + internal_end_frame
                if relation_start_frame is not None
                and internal_end_frame is not None
                else relation_end_frame
            )
            event_rows.append(
                {
                    **relation,
                    "relation_start_ms": (
                        round(relation_start_frame * 1000 / args.frame_rate)
                        if relation_start_frame is not None
                        else ""
                    ),
                    "relation_end_ms": (
                        round(
                            (relation_end_frame + 1)
                            * 1000
                            / args.frame_rate
                        )
                        if relation_end_frame is not None
                        else ""
                    ),
                    "dgm_order": dependency["dgm_order"],
                    "dgm_name": dependency["dgm_name"],
                    "dgm_role": dependency["dgm_role"],
                    "dgm_base_name": dependency["dgm_base_name"],
                    "internal_start_frame": dependency["internal_start_frame"],
                    "internal_end_frame": dependency["internal_end_frame"],
                    "event_start_frame": (
                        f"{event_start_frame:.6f}"
                        if event_start_frame is not None
                        else ""
                    ),
                    "event_end_frame": (
                        f"{event_end_frame:.6f}"
                        if event_end_frame is not None
                        else ""
                    ),
                    "event_start_ms": (
                        round(event_start_frame * 1000 / args.frame_rate)
                        if event_start_frame is not None
                        else ""
                    ),
                    "event_end_ms": (
                        round(
                            (event_end_frame + 1)
                            * 1000
                            / args.frame_rate
                        )
                        if event_end_frame is not None
                        else ""
                    ),
                    "interval_confidence": dependency["interval_confidence"],
                    "media_duration_sec": dependency["media_duration_sec"],
                    "media_expected_frames": dependency["media_expected_frames"],
                    "cri_match": dependency["cri_match"],
                    "cri_global_index": dependency["cri_global_index"],
                    "package": dependency["package"],
                    "package_index": dependency["package_index"],
                    "official_name": dependency["official_name"],
                    "source_mp4": dependency["source_mp4"],
                    "target_mp4": dependency["target_mp4"],
                    "z2d_loop_point": dependency["z2d_loop_point"],
                    "z2d_canvas_width": dependency["z2d_canvas_width"],
                    "z2d_canvas_height": dependency["z2d_canvas_height"],
                    "layer_parent_name": dependency["layer_parent_name"],
                    "layer_canvas_x": dependency["layer_canvas_x"],
                    "layer_canvas_y": dependency["layer_canvas_y"],
                    "layer_canvas_width": dependency["layer_canvas_width"],
                    "layer_canvas_height": dependency["layer_canvas_height"],
                    "layer_opacity": dependency["layer_opacity"],
                    "layer_flags_hex": dependency["layer_flags_hex"],
                }
            )

    event_fields = [
        "gdb_record_index",
        "gdb_record_offset_hex",
        "event_name",
        "z2d_order",
        "z2d_name",
        "z2d_filename",
        "z2d_loop_point",
        "z2d_canvas_width",
        "z2d_canvas_height",
        "start_frame",
        "end_frame",
        "key_start_frame",
        "key_end_frame",
        "relation_start_ms",
        "relation_end_ms",
        "dgm_order",
        "dgm_name",
        "dgm_role",
        "dgm_base_name",
        "internal_start_frame",
        "internal_end_frame",
        "event_start_frame",
        "event_end_frame",
        "event_start_ms",
        "event_end_ms",
        "interval_confidence",
        "media_duration_sec",
        "media_expected_frames",
        "cri_match",
        "cri_global_index",
        "package",
        "package_index",
        "official_name",
        "source_mp4",
        "target_mp4",
        "layer_parent_name",
        "layer_canvas_x",
        "layer_canvas_y",
        "layer_canvas_width",
        "layer_canvas_height",
        "layer_opacity",
        "layer_flags_hex",
    ]
    event_path = out_dir / "gdb_event_dgm_video_timeline.csv"
    write_csv(event_path, event_rows, event_fields)

    dependency_counts = Counter(row["cri_match"] for row in dependency_rows)
    interval_counts = Counter(row["interval_confidence"] for row in dependency_rows)
    role_counts = Counter(row["dgm_role"] for row in dependency_rows)
    event_match_counts = Counter(row["cri_match"] for row in event_rows)
    contiguous_pairs = 0
    pair_candidates = 0
    rows_by_z2d_and_base: dict[tuple[str, str], dict[str, dict]] = defaultdict(dict)
    for row in dependency_rows:
        rows_by_z2d_and_base[
            (row["z2d_name"].lower(), row["dgm_base_name"].lower())
        ][row["dgm_role"]] = row
    for pair in rows_by_z2d_and_base.values():
        intro = pair.get("intro_before_loop")
        loop = pair.get("loop_cycle")
        if not intro or not loop:
            continue
        pair_candidates += 1
        intro_end = parse_optional_int(intro["internal_end_frame"])
        loop_start = parse_optional_int(loop["internal_start_frame"])
        if (
            intro_end is not None
            and loop_start is not None
            and intro_end + 1 == loop_start
        ):
            contiguous_pairs += 1

    summary_path = out_dir / "z2d_dgm_event_map_summary.md"
    lines = [
        "# GDB Event to Z2D to DGM to CRI Map",
        "",
        f"Z2D chunks scanned: {len(z2d_names)}",
        f"Z2D chunks with DGM dependencies: {len(dependencies_by_z2d)}",
        f"DGM dependency rows: {len(dependency_rows)}",
        f"GDB Z2D relations: {len(relation_rows)}",
        f"Event-to-DGM rows: {len(event_rows)}",
        f"Intro/loop pair candidates: {pair_candidates}",
        f"Frame-contiguous intro/loop pairs: {contiguous_pairs}",
        "",
        "## CRI matches",
    ]
    for key, value in sorted(dependency_counts.items()):
        lines.append(f"- dependency {key}: {value}")
    for key, value in sorted(event_match_counts.items()):
        lines.append(f"- event relation {key}: {value}")
    lines.extend(["", "## DGM roles"])
    for key, value in sorted(role_counts.items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Frame interval recovery"])
    for key, value in sorted(interval_counts.items()):
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- The authoritative chain is GDB event -> Z2D resource -> embedded DGM dependency -> native CRI name/index.",
            "- Numeric GDB candidate suffixes are not used here and must not be treated as physical video indices.",
            "- DGM entries whose `_LP` companion starts on the next frame form an official intro plus repeating loop cycle.",
            "- Different DGM entries with overlapping frame ranges are simultaneous render layers, not concatenation candidates.",
            "- Z2D layer coordinates are decoded onto the native 1024x576 event canvas.",
            "- DGI image/text rendering remains separate reconstruction work.",
        ]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[z2d-dgm-event-map] DGM dependencies: {len(dependency_rows)}")
    print(f"[z2d-dgm-event-map] event-to-DGM rows: {len(event_rows)}")
    print(
        "[z2d-dgm-event-map] matched dependencies: "
        f"{dependency_counts.get('yes', 0)} / {len(dependency_rows)}"
    )
    print(
        "[z2d-dgm-event-map] contiguous intro/loop pairs: "
        f"{contiguous_pairs} / {pair_candidates}"
    )
    print(f"[z2d-dgm-event-map] wrote {dependency_path}")
    print(f"[z2d-dgm-event-map] wrote {event_path}")
    print(f"[z2d-dgm-event-map] wrote {summary_path}")


def command_build_event_dgm_layers(args):
    event_map_csv = Path(args.event_map_csv)
    out_dir = Path(args.out_dir)
    work_dir = out_dir / "work"
    layer_dir = out_dir / "layers"
    canvas_select = parse_canvas_selector(getattr(args, "canvas_select", ""))
    selected = [
        row
        for row in read_csv(event_map_csv)
        if row.get("event_name", "").lower() == args.event_name.lower()
        and row.get("cri_match") == "yes"
        and row.get("target_mp4")
        and parse_optional_int(row.get("internal_start_frame")) is not None
        and parse_optional_int(row.get("internal_end_frame")) is not None
        and (
            canvas_select is None
            or (
                parse_optional_int(row.get("z2d_canvas_width")),
                parse_optional_int(row.get("z2d_canvas_height")),
            )
            == canvas_select
        )
    ]
    if not selected:
        raise ValueError(
            f"no exact DGM video rows found for event {args.event_name}"
        )
    event_duration_sec = event_rows_duration_sec(selected, args.frame_rate)
    event_duration_sec = max(
        event_duration_sec,
        parse_optional_float(getattr(args, "target_duration_sec", 0)) or 0.0,
    )

    grouped: dict[tuple[int, str], list[dict]] = defaultdict(list)
    for row in selected:
        grouped[
            (
                parse_optional_int(row.get("z2d_order")) or 0,
                row.get("z2d_name", ""),
            )
        ].append(row)

    track_specs = []
    for (z2d_order, z2d_name), rows in sorted(grouped.items()):
        rows.sort(
            key=lambda row: (
                parse_optional_int(row.get("internal_start_frame")) or 0,
                parse_optional_int(row.get("internal_end_frame")) or 0,
                parse_optional_int(row.get("dgm_order")) or 0,
            )
        )
        tracks: list[list[dict]] = []
        for row in rows:
            start_frame = int(row["internal_start_frame"])
            contiguous_track = None
            for track_index, track in enumerate(tracks):
                last_end_frame = int(track[-1]["internal_end_frame"])
                if start_frame == last_end_frame + 1:
                    contiguous_track = track_index
                    break
            if contiguous_track is None:
                tracks.append([row])
            else:
                tracks[contiguous_track].append(row)
        for track_index, track_rows in enumerate(tracks):
            track_specs.append(
                {
                    "z2d_order": z2d_order,
                    "z2d_name": z2d_name,
                    "track_index": track_index,
                    "rows": track_rows,
                }
            )

    manifest_rows = []
    for spec in track_specs:
        rows = spec["rows"]
        source_paths = [Path(row["target_mp4"]) for row in rows]
        missing_sources = [path for path in source_paths if not path.exists()]
        first_frame = int(rows[0]["internal_start_frame"])
        last_frame = int(rows[-1]["internal_end_frame"])
        frame_count = sum(
            int(row["internal_end_frame"])
            - int(row["internal_start_frame"])
            + 1
            for row in rows
        )
        single_cycle_duration_sec = frame_count / args.frame_rate
        expected_duration_sec = single_cycle_duration_sec
        loop_repeat_count = 1
        concat_source_paths = list(source_paths)
        loop_row_index = next(
            (
                index
                for index, row in enumerate(rows)
                if row.get("dgm_role")
                in {"loop_cycle", "loop_continuation", "orphan_loop_cycle", "orphan_loop"}
            ),
            None,
        )
        relation_start_sec = (
            parse_optional_float(rows[0].get("relation_start_ms")) or 0.0
        ) / 1000
        target_track_duration_sec = max(
            single_cycle_duration_sec,
            event_duration_sec - relation_start_sec,
        )
        if (
            loop_row_index is not None
            and target_track_duration_sec
            > single_cycle_duration_sec + (0.5 / args.frame_rate)
        ):
            loop_row = rows[loop_row_index]
            loop_duration_sec = (
                int(loop_row["internal_end_frame"])
                - int(loop_row["internal_start_frame"])
                + 1
            ) / args.frame_rate
            intro_duration_sec = sum(
                (
                    int(row["internal_end_frame"])
                    - int(row["internal_start_frame"])
                    + 1
                )
                / args.frame_rate
                for row in rows[:loop_row_index]
            )
            loop_repeat_count = max(
                1,
                math.ceil(
                    max(0.0, target_track_duration_sec - intro_duration_sec)
                    / loop_duration_sec
                ),
            )
            concat_source_paths = (
                source_paths[:loop_row_index]
                + [source_paths[loop_row_index]] * loop_repeat_count
            )
            expected_duration_sec = target_track_duration_sec
        output_name = (
            f"{int(spec['z2d_order']):02d}_"
            f"{safe_name(spec['z2d_name'], max_len=140)}_"
            f"track{int(spec['track_index']):02d}.mp4"
        )
        output_path = layer_dir / output_name
        concat_path = work_dir / output_name.replace(".mp4", ".ffconcat")
        status = "planned"
        error = ""
        output_probe = {}
        cmd = []

        if missing_sources:
            status = "missing_source"
            error = "; ".join(str(path) for path in missing_sources)
        else:
            work_dir.mkdir(parents=True, exist_ok=True)
            concat_path.write_text(
                "ffconcat version 1.0\n"
                + "\n".join(
                    concat_file_line(path)
                    for path in concat_source_paths
                )
                + "\n",
                encoding="utf-8",
            )
            cmd = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y" if args.overwrite else "-n",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_path),
                "-map",
                "0:v:0",
                "-an",
            ]
            if args.video_mode == "copy":
                cmd.extend(["-c:v", "copy"])
            elif args.encoder == "h264_nvenc":
                cmd.extend(
                    ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", str(args.cq)]
                )
            else:
                cmd.extend(
                    ["-c:v", "libx264", "-preset", "medium", "-crf", str(args.crf)]
                )
            cmd.extend(
                [
                    "-t",
                    f"{expected_duration_sec:.6f}",
                    "-movflags",
                    "+faststart",
                    str(output_path),
                ]
            )
            if args.execute:
                layer_dir.mkdir(parents=True, exist_ok=True)
                if output_path.exists() and not args.overwrite:
                    status = "exists"
                    output_probe = probe_mp4(output_path)
                else:
                    result = subprocess.run(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    if result.returncode == 0:
                        status = "ok"
                        output_probe = probe_mp4(output_path)
                    else:
                        status = "ffmpeg_failed"
                        error = result.stderr.strip()[-2000:]

        manifest_rows.append(
            {
                "event_name": args.event_name,
                "z2d_canvas_width": rows[0].get("z2d_canvas_width", ""),
                "z2d_canvas_height": rows[0].get("z2d_canvas_height", ""),
                "z2d_order": spec["z2d_order"],
                "z2d_name": spec["z2d_name"],
                "track_index": spec["track_index"],
                "segment_count": len(rows),
                "dgm_names": ";".join(row["dgm_name"] for row in rows),
                "dgm_roles": ";".join(row["dgm_role"] for row in rows),
                "source_mp4s": ";".join(str(path) for path in source_paths),
                "first_internal_frame": first_frame,
                "last_internal_frame": last_frame,
                "frame_count": frame_count,
                "single_cycle_duration_sec": f"{single_cycle_duration_sec:.6f}",
                "expected_duration_sec": f"{expected_duration_sec:.6f}",
                "event_duration_sec": f"{event_duration_sec:.6f}",
                "loop_repeat_count": loop_repeat_count,
                "event_start_frame": rows[0].get("event_start_frame", ""),
                "event_end_frame": rows[-1].get("event_end_frame", ""),
                "output_path": str(output_path),
                "output_duration_sec": output_probe.get("duration_sec", ""),
                "status": status,
                "error": error,
                "ffmpeg_command": subprocess.list2cmdline(cmd) if cmd else "",
            }
        )

    manifest_path = out_dir / "event_dgm_layer_build.csv"
    write_csv(
        manifest_path,
        manifest_rows,
        [
            "event_name",
            "z2d_canvas_width",
            "z2d_canvas_height",
            "z2d_order",
            "z2d_name",
            "track_index",
            "segment_count",
            "dgm_names",
            "dgm_roles",
            "source_mp4s",
            "first_internal_frame",
            "last_internal_frame",
            "frame_count",
            "single_cycle_duration_sec",
            "expected_duration_sec",
            "event_duration_sec",
            "loop_repeat_count",
            "event_start_frame",
            "event_end_frame",
            "output_path",
            "output_duration_sec",
            "status",
            "error",
            "ffmpeg_command",
        ],
    )
    counts = Counter(row["status"] for row in manifest_rows)
    summary_path = out_dir / "event_dgm_layer_build_summary.md"
    lines = [
        "# Event DGM Layer Build",
        "",
        f"Event: {args.event_name}",
        (
            f"Canvas selection: {canvas_select[0]}x{canvas_select[1]}"
            if canvas_select
            else "Canvas selection: all"
        ),
        f"Mapped DGM rows: {len(selected)}",
        f"Target event duration: {event_duration_sec:.6f} sec",
        f"Output layer tracks: {len(manifest_rows)}",
        f"Execute: {'yes' if args.execute else 'no'}",
        "",
        "## Status",
    ]
    for key, value in sorted(counts.items()):
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## Meaning",
            "",
            "- Segments are concatenated only when their recovered Z2D frame intervals are directly adjacent.",
            "- `intro_before_loop` is followed by a repeating `_LP` loop cycle until the event duration is filled.",
            "- Simultaneous/overlapping DGM resources are emitted as separate tracks and are not concatenated.",
            "- These outputs are source render layers. They are not yet a final composited game frame.",
        ]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[build-event-dgm-layers] event: {args.event_name}")
    print(f"[build-event-dgm-layers] layer tracks: {len(manifest_rows)}")
    print(f"[build-event-dgm-layers] status: {dict(counts)}")
    print(f"[build-event-dgm-layers] wrote {manifest_path}")
    print(f"[build-event-dgm-layers] wrote {summary_path}")


def command_build_event_dgm_composite(args):
    event_map_csv = Path(args.event_map_csv)
    subtitle_timeline_csv = Path(args.subtitle_timeline_csv)
    event_audio_components_csv = (
        Path(args.event_audio_components_csv)
        if args.event_audio_components_csv
        else None
    )
    audio_signal_audit = load_audio_signal_audit(
        Path(args.audio_signal_audit_csv)
        if getattr(args, "audio_signal_audit_csv", "")
        else None
    )
    out_dir = Path(args.out_dir)
    all_event_rows = [
        row
        for row in read_csv(event_map_csv)
        if row.get("event_name", "").lower() == args.event_name.lower()
        and row.get("cri_match") == "yes"
    ]
    if not all_event_rows:
        raise ValueError(f"event is not present in DGM map: {args.event_name}")
    canvas_groups = sorted(
        {
            (
                parse_optional_int(row.get("z2d_canvas_width")),
                parse_optional_int(row.get("z2d_canvas_height")),
            )
            for row in all_event_rows
            if parse_optional_int(row.get("z2d_canvas_width")) is not None
            and parse_optional_int(row.get("z2d_canvas_height")) is not None
        }
    )
    requested_canvas = parse_canvas_selector(args.canvas_select)
    if requested_canvas is None:
        if len(canvas_groups) > 1:
            options = ", ".join(f"{width}x{height}" for width, height in canvas_groups)
            raise ValueError(
                f"event {args.event_name} has multiple Z2D canvases ({options}); "
                "select one with --canvas-select WIDTHxHEIGHT"
            )
        selected_canvas = canvas_groups[0] if canvas_groups else None
    else:
        if canvas_groups and requested_canvas not in canvas_groups:
            options = ", ".join(f"{width}x{height}" for width, height in canvas_groups)
            raise ValueError(
                f"canvas {requested_canvas[0]}x{requested_canvas[1]} is not present "
                f"for {args.event_name}; available: {options}"
            )
        selected_canvas = requested_canvas
    event_rows = [
        row
        for row in all_event_rows
        if selected_canvas is None
        or (
            parse_optional_int(row.get("z2d_canvas_width")),
            parse_optional_int(row.get("z2d_canvas_height")),
        )
        == selected_canvas
    ]
    canvas_tag = (
        f"{selected_canvas[0]}x{selected_canvas[1]}"
        if selected_canvas
        else "unknown_canvas"
    )
    layer_out_dir = out_dir / f"official_dgm_layers_{canvas_tag}"
    layer_args = argparse.Namespace(
        event_map_csv=str(event_map_csv),
        event_name=args.event_name,
        out_dir=str(layer_out_dir),
        canvas_select=canvas_tag if selected_canvas else "",
        frame_rate=args.frame_rate,
        target_duration_sec=0.0,
        video_mode="copy",
        encoder=args.encoder,
        crf=args.crf,
        cq=args.cq,
        execute=args.execute,
        overwrite=args.overwrite,
    )
    event_duration_sec = event_rows_duration_sec(event_rows, args.frame_rate)

    placement_by_z2d = {}
    for row in event_rows:
        z2d_name = row.get("z2d_name", "")
        if z2d_name in placement_by_z2d:
            continue
        values = [
            parse_optional_float(row.get("layer_canvas_x")),
            parse_optional_float(row.get("layer_canvas_y")),
            parse_optional_float(row.get("layer_canvas_width")),
            parse_optional_float(row.get("layer_canvas_height")),
        ]
        if all(value is not None for value in values):
            placement_by_z2d[z2d_name] = {
                "x": values[0],
                "y": values[1],
                "width": values[2],
                "height": values[3],
                "relation_start_sec": (
                    parse_optional_float(row.get("relation_start_ms")) or 0.0
                )
                / 1000,
                "parent_name": row.get("layer_parent_name", ""),
                "canvas_width": parse_optional_int(
                    row.get("z2d_canvas_width")
                ),
                "canvas_height": parse_optional_int(
                    row.get("z2d_canvas_height")
                ),
            }

    canvas_placements = list(placement_by_z2d.values())
    if not canvas_placements:
        raise ValueError("no decoded Z2D layer placement for event")
    canvas_width = args.canvas_width
    canvas_height = args.canvas_height
    decoded_canvas_widths = [
        parse_optional_int(row.get("z2d_canvas_width"))
        for row in event_rows
        if parse_optional_int(row.get("z2d_canvas_width")) is not None
    ]
    decoded_canvas_heights = [
        parse_optional_int(row.get("z2d_canvas_height"))
        for row in event_rows
        if parse_optional_int(row.get("z2d_canvas_height")) is not None
    ]
    if canvas_width <= 0:
        canvas_width = (
            max(decoded_canvas_widths)
            if decoded_canvas_widths
            else max(
                2,
                max(
                    int(math.ceil(placement["x"] + placement["width"]))
                    for placement in canvas_placements
                ),
            )
        )
    if canvas_height <= 0:
        canvas_height = (
            max(decoded_canvas_heights)
            if decoded_canvas_heights
            else max(
                2,
                max(
                    int(math.ceil(placement["y"] + placement["height"]))
                    for placement in canvas_placements
                ),
            )
        )
    canvas_width += canvas_width % 2
    canvas_height += canvas_height % 2
    effective_encoder = args.encoder
    if (
        effective_encoder == "h264_nvenc"
        and (canvas_width < 145 or canvas_height < 145)
    ):
        effective_encoder = "libx264"

    subtitle_rows = []
    if subtitle_timeline_csv.exists():
        subtitle_rows = [
            row
            for row in read_csv(subtitle_timeline_csv)
            if row.get("event_name", "").lower() == args.event_name.lower()
            and row.get("timeline_confidence")
            == "exact_gdb_frame_and_official_ogg"
            and row.get("z2d_name", "").lower().startswith("cap")
            and row.get("ogg_exists") == "yes"
            and row.get("ogg_path")
            and Path(row["ogg_path"]).exists()
            and audio_path_is_audible(row["ogg_path"], audio_signal_audit)
        ]
        subtitle_rows.sort(
            key=lambda row: (
                parse_optional_int(row.get("start_ms")) or 0,
                parse_optional_int(row.get("z2d_order")) or 0,
            )
        )
    audio_rows = []
    seen_audio = set()
    for row in subtitle_rows:
        key = (str(Path(row["ogg_path"]).resolve()).lower(), int(row.get("start_ms") or 0))
        if key in seen_audio:
            continue
        seen_audio.add(key)
        audio_rows.append(
            {
                "source_kind": "z2d_dialogue",
                "start_ms": parse_optional_int(row.get("start_ms")) or 0,
                "duration_ms": parse_optional_int(row.get("sound_duration_ms")) or 0,
                "ogg_path": row["ogg_path"],
                "ogg_name": row.get("ogg_name", ""),
                "label": row.get("display_text", ""),
                "request_id": row.get("sound_request_id", ""),
                "resource_id": row.get("sound_resource_id", ""),
                "duration_match": "exact_gdb_frame_and_official_ogg",
            }
        )
    if event_audio_components_csv and event_audio_components_csv.exists():
        for row in read_csv(event_audio_components_csv):
            if (
                row.get("primary_animation", "").lower()
                != args.event_name.lower()
                or row.get("ogg_duration_match") != "yes"
                or not row.get("ogg_path")
                or not Path(row["ogg_path"]).exists()
                or not audio_path_is_audible(
                    row["ogg_path"], audio_signal_audit
                )
            ):
                continue
            start_ms = parse_optional_int(row.get("start_ms")) or 0
            key = (str(Path(row["ogg_path"]).resolve()).lower(), start_ms)
            if key in seen_audio:
                continue
            seen_audio.add(key)
            audio_rows.append(
                {
                    "source_kind": "eventcn",
                    "start_ms": start_ms,
                    "duration_ms": parse_optional_int(row.get("duration_ms")) or 0,
                    "ogg_path": row["ogg_path"],
                    "ogg_name": row.get("ogg_name", ""),
                    "label": row.get("leaf_label", ""),
                    "request_id": row.get("leaf_request_id", ""),
                    "resource_id": row.get("leaf_sound_code", ""),
                    "duration_match": row.get("ogg_duration_match", ""),
                }
            )
    audio_rows.sort(
        key=lambda row: (
            int(row["start_ms"]),
            row["source_kind"],
            row["ogg_name"],
        )
    )
    audio_manifest_path = out_dir / "official_audio_mix_manifest.csv"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(
        audio_manifest_path,
        audio_rows,
        [
            "source_kind",
            "start_ms",
            "duration_ms",
            "ogg_name",
            "ogg_path",
            "request_id",
            "resource_id",
            "duration_match",
            "label",
        ],
    )
    if audio_rows:
        event_duration_sec = max(
            event_duration_sec,
            max(
                (int(row["start_ms"]) + int(row["duration_ms"])) / 1000
                for row in audio_rows
            ),
        )

    layer_args.target_duration_sec = event_duration_sec
    command_build_event_dgm_layers(layer_args)
    layer_manifest = read_csv(layer_out_dir / "event_dgm_layer_build.csv")
    usable_layers = []
    for row in layer_manifest:
        output_path = Path(row.get("output_path", ""))
        placement = placement_by_z2d.get(row.get("z2d_name", ""))
        if (
            placement
            and (
                output_path.exists()
                or (not args.execute and row.get("status") == "planned")
            )
            and row.get("status") in {"ok", "exists", "planned"}
        ):
            usable_layers.append((row, placement, output_path))
    if args.execute and not usable_layers:
        raise ValueError("no built DGM layers with decoded Z2D placement")

    output_stem = safe_name(args.event_name)
    if len(canvas_groups) > 1:
        output_stem += f"__{canvas_tag}"
    subtitle_path = out_dir / f"{output_stem}.srt"
    if subtitle_rows:
        srt_lines = []
        for cue_index, row in enumerate(subtitle_rows, start=1):
            start_ms = parse_optional_int(row.get("start_ms")) or 0
            end_ms = parse_optional_int(row.get("effective_end_ms")) or start_ms + 1
            end_ms = min(end_ms, int(round(event_duration_sec * 1000)))
            text = row.get("srt_text") or row.get("display_text") or ""
            text = text.replace("\\n", "\n")
            srt_lines.extend(
                [
                    str(cue_index),
                    f"{srt_timestamp(start_ms)} --> {srt_timestamp(end_ms)}",
                    text,
                    "",
                ]
            )
        subtitle_path.write_text("\n".join(srt_lines), encoding="utf-8-sig")
    elif subtitle_path.exists() and args.overwrite:
        subtitle_path.unlink()

    no_subtitles_path = out_dir / f"{output_stem}__no_subtitles.mp4"
    subtitles_path = out_dir / f"{output_stem}__subtitles_burned.mp4"
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y" if args.overwrite else "-n",
        "-f",
        "lavfi",
        "-i",
        (
            f"color=c=black:s={canvas_width}x{canvas_height}:"
            f"r={args.frame_rate}:d={event_duration_sec:.6f}"
        ),
    ]
    for _, _, layer_path in usable_layers:
        cmd.extend(["-i", str(layer_path)])
    for row in audio_rows:
        cmd.extend(["-i", row["ogg_path"]])

    filters = []
    current_video = "0:v"
    for layer_index, (_, placement, _) in enumerate(usable_layers, start=1):
        layer_label = f"layer{layer_index}"
        output_label = f"v{layer_index}"
        width = max(2, int(round(placement["width"] / 2) * 2))
        height = max(2, int(round(placement["height"] / 2) * 2))
        x = int(round(placement["x"]))
        y = int(round(placement["y"]))
        start_sec = placement["relation_start_sec"]
        filters.append(
            f"[{layer_index}:v]"
            f"scale={width}:{height}:flags=lanczos,"
            f"format=rgba,colorkey=0x000000:"
            f"{args.black_similarity:.4f}:{args.black_blend:.4f},"
            f"setpts=PTS+{start_sec:.6f}/TB"
            f"[{layer_label}]"
        )
        hold_last = args.layer_eof_policy == "hold-all" or (
            args.layer_eof_policy == "hold-base"
            and layer_index == 1
            and not placement.get("parent_name")
        )
        eof_action = "repeat" if hold_last else "pass"
        filters.append(
            f"[{current_video}][{layer_label}]"
            f"overlay={x}:{y}:eof_action={eof_action}:"
            f"repeatlast={1 if hold_last else 0}:shortest=0"
            f"[{output_label}]"
        )
        current_video = output_label

    audio_input_start = 1 + len(usable_layers)
    audio_labels = []
    for audio_index, row in enumerate(audio_rows):
        input_index = audio_input_start + audio_index
        start_ms = parse_optional_int(row.get("start_ms")) or 0
        label = f"a{audio_index}"
        filters.append(
            f"[{input_index}:a]"
            f"adelay={start_ms}|{start_ms},"
            "aresample=48000,"
            "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo"
            f"[{label}]"
        )
        audio_labels.append(label)
    if audio_labels:
        if len(audio_labels) == 1:
            audio_output = audio_labels[0]
        else:
            audio_output = "amixout"
            filters.append(
                "".join(f"[{label}]" for label in audio_labels)
                + f"amix=inputs={len(audio_labels)}:"
                "duration=longest:normalize=0:dropout_transition=0"
                f"[{audio_output}]"
            )
        filters.append(
            f"[{audio_output}]"
            "alimiter=limit=0.85:level=disabled:attack=5:release=50,"
            "volume=-3dB,"
            f"apad=whole_dur={event_duration_sec:.6f}"
            "[afinal]"
        )
        audio_output = "afinal"
    else:
        filters.append(
            f"anullsrc=r=48000:cl=stereo:d={event_duration_sec:.6f}[asilence]"
        )
        audio_output = "asilence"

    filter_script_path = out_dir / "composite_filter_complex.txt"
    filter_script_path.write_text(
        ";\n".join(filters) + "\n",
        encoding="utf-8",
    )
    cmd.extend(["-filter_complex_script", str(filter_script_path)])
    cmd.extend(["-map", f"[{current_video}]", "-map", f"[{audio_output}]"])
    if effective_encoder == "h264_nvenc":
        cmd.extend(["-c:v", "h264_nvenc", "-preset", "p4", "-cq", str(args.cq)])
    else:
        cmd.extend(["-c:v", "libx264", "-preset", "medium", "-crf", str(args.crf)])
    cmd.extend(
        [
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "256k",
            "-t",
            f"{event_duration_sec:.6f}",
            "-movflags",
            "+faststart",
            str(no_subtitles_path),
        ]
    )
    (out_dir / "composite_ffmpeg_command.txt").write_text(
        subprocess.list2cmdline(cmd) + "\n",
        encoding="utf-8",
    )

    status = "planned"
    error = ""
    if args.execute:
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode == 0:
            status = "ok"
        else:
            status = "ffmpeg_failed"
            error = result.stderr.strip()[-3000:]
            if no_subtitles_path.exists():
                no_subtitles_path.unlink()

    burned_status = "not_requested"
    burned_error = ""
    burned_cmd = []
    if args.burn_subtitles and subtitle_path.exists() and no_subtitles_path.exists():
        subtitle_filter = (
            f"subtitles=filename='{subtitle_path.name}':"
            + "force_style='"
            + f"FontName={args.subtitle_font_name},"
            + f"FontSize={args.subtitle_font_size},"
            + "PrimaryColour=&H00101010,"
            + "OutlineColour=&H00FFFFFF,"
            + "BorderStyle=1,Outline=1,Shadow=0,"
            + f"MarginV={args.subtitle_margin_v},Alignment=2'"
        )
        burned_cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y" if args.overwrite else "-n",
            "-i",
            str(no_subtitles_path),
            "-vf",
            subtitle_filter,
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
        ]
        if effective_encoder == "h264_nvenc":
            burned_cmd.extend(
                ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", str(args.cq)]
            )
        else:
            burned_cmd.extend(
                ["-c:v", "libx264", "-preset", "medium", "-crf", str(args.crf)]
            )
        burned_cmd.extend(
            [
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "copy",
                "-movflags",
                "+faststart",
                str(subtitles_path),
            ]
        )
        (out_dir / "subtitles_ffmpeg_command.txt").write_text(
            subprocess.list2cmdline(burned_cmd) + "\n",
            encoding="utf-8",
        )
        if args.execute:
            result = subprocess.run(
                burned_cmd,
                cwd=out_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
            if result.returncode == 0:
                burned_status = "ok"
            else:
                burned_status = "ffmpeg_failed"
                burned_error = result.stderr.strip()[-3000:]
        else:
            burned_status = "planned"

    summary_path = out_dir / "event_dgm_composite_summary.md"
    lines = [
        "# Event DGM Composite",
        "",
        f"Event: {args.event_name}",
        f"Canvas group: {canvas_tag}",
        f"Available canvas groups: {', '.join(f'{width}x{height}' for width, height in canvas_groups) or '(unknown)'}",
        f"Canvas: {canvas_width}x{canvas_height}",
        f"Video encoder: {effective_encoder}",
        f"Layer EOF policy: {args.layer_eof_policy}",
        f"Duration: {event_duration_sec:.6f} sec",
        f"Placed DGM layer tracks: {len(usable_layers)}",
        f"Official audio tracks: {len(audio_rows)}",
        f"Z2D dialogue tracks: {sum(row['source_kind'] == 'z2d_dialogue' for row in audio_rows)}",
        f"EventCn tracks: {sum(row['source_kind'] == 'eventcn' for row in audio_rows)}",
        f"No-subtitle status: {status}",
        f"Burned-subtitle status: {burned_status}",
        f"No-subtitle output: {no_subtitles_path}",
        f"Burned-subtitle output: {subtitles_path if subtitle_path.exists() else '(none)'}",
        f"Audio source manifest: {audio_manifest_path}",
        "",
        "## Reconstruction status",
        "",
        "- Video identity, intro/loop timing, layer dimensions, centers, positions, and parent offsets come from GDB/Z2D/DGM/CRI data.",
        "- `_LP` media is repeated as the Z2D loop cycle until the event duration is filled.",
        "- Black movie matte is removed with the tested colorkey path.",
        "- DGI image layers, shader effects, and nameplate rendering are not yet reproduced in this offline composite.",
    ]
    if error:
        lines.extend(["", f"No-subtitle error: {error}"])
    if burned_error:
        lines.extend(["", f"Burned-subtitle error: {burned_error}"])
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[build-event-dgm-composite] event: {args.event_name}")
    print(f"[build-event-dgm-composite] layers: {len(usable_layers)}")
    print(f"[build-event-dgm-composite] audio tracks: {len(audio_rows)}")
    print(f"[build-event-dgm-composite] status: {status}")
    print(f"[build-event-dgm-composite] burned subtitles: {burned_status}")
    print(f"[build-event-dgm-composite] wrote {summary_path}")
    return {
        "status": status,
        "burned_status": burned_status,
        "no_subtitles_path": str(no_subtitles_path) if no_subtitles_path.exists() else "",
        "subtitles_path": str(subtitles_path) if subtitles_path.exists() else "",
        "error": error or burned_error,
        "encoder": effective_encoder,
    }


def command_event_production_plan(args):
    event_map_csv = Path(args.event_map_csv)
    subtitle_timeline_csv = Path(args.subtitle_timeline_csv)
    event_audio_components_csv = Path(args.event_audio_components_csv)
    audio_signal_audit = load_audio_signal_audit(
        Path(args.audio_signal_audit_csv)
        if args.audio_signal_audit_csv
        else None
    )
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    exact_rows = [
        row
        for row in read_csv(event_map_csv)
        if row.get("cri_match") == "yes"
        and row.get("event_name")
        and row.get("target_mp4")
    ]
    rows_by_event_canvas: dict[tuple[str, int, int], list[dict]] = defaultdict(list)
    canvases_by_event: dict[str, set[tuple[int, int]]] = defaultdict(set)
    for row in exact_rows:
        width = parse_optional_int(row.get("z2d_canvas_width"))
        height = parse_optional_int(row.get("z2d_canvas_height"))
        if width is None or height is None:
            continue
        event_name = row["event_name"]
        canvas = (width, height)
        rows_by_event_canvas[(event_name, width, height)].append(row)
        canvases_by_event[event_name].add(canvas)

    dialogue_by_event: dict[str, list[dict]] = defaultdict(list)
    if subtitle_timeline_csv.exists():
        for row in read_csv(subtitle_timeline_csv):
            if (
                row.get("timeline_confidence")
                != "exact_gdb_frame_and_official_ogg"
                or not row.get("z2d_name", "").lower().startswith("cap")
                or row.get("ogg_exists") != "yes"
                or not row.get("ogg_path")
                or not Path(row["ogg_path"]).exists()
                or not audio_path_is_audible(
                    row["ogg_path"], audio_signal_audit
                )
            ):
                continue
            dialogue_by_event[row.get("event_name", "")].append(row)

    eventcn_by_event: dict[str, list[dict]] = defaultdict(list)
    if event_audio_components_csv.exists():
        for row in read_csv(event_audio_components_csv):
            if (
                row.get("ogg_duration_match") != "yes"
                or not row.get("ogg_path")
                or not Path(row["ogg_path"]).exists()
                or not audio_path_is_audible(
                    row["ogg_path"], audio_signal_audit
                )
            ):
                continue
            eventcn_by_event[row.get("primary_animation", "")].append(row)

    plan_rows = []
    for (event_name, width, height), rows in sorted(
        rows_by_event_canvas.items(),
        key=lambda item: (
            natural_key(item[0][0]),
            item[0][1],
            item[0][2],
        ),
    ):
        event_duration_sec = event_rows_duration_sec(rows, args.frame_rate)
        dialogue_rows = dialogue_by_event.get(event_name, [])
        eventcn_rows = eventcn_by_event.get(event_name, [])
        audio_keys = {
            (
                str(Path(row["ogg_path"]).resolve()).lower(),
                parse_optional_int(row.get("start_ms")) or 0,
            )
            for row in dialogue_rows + eventcn_rows
        }
        audio_end_sec = max(
            [
                (
                    (parse_optional_int(row.get("start_ms")) or 0)
                    + (
                        parse_optional_int(row.get("sound_duration_ms"))
                        or parse_optional_int(row.get("duration_ms"))
                        or 0
                    )
                )
                / 1000
                for row in dialogue_rows + eventcn_rows
            ]
            or [0.0]
        )
        output_duration_sec = max(event_duration_sec, audio_end_sec)
        has_loop_cycle = any(
            row.get("dgm_role") in {"loop_cycle", "orphan_loop_cycle"}
            for row in rows
        )
        layer_coverages = []
        full_canvas_layer = False
        for row in rows:
            layer_x = parse_optional_float(row.get("layer_canvas_x"))
            layer_y = parse_optional_float(row.get("layer_canvas_y"))
            layer_width = parse_optional_float(row.get("layer_canvas_width"))
            layer_height = parse_optional_float(row.get("layer_canvas_height"))
            if None in {layer_x, layer_y, layer_width, layer_height}:
                continue
            coverage = max(
                0.0,
                min(1.0, (layer_width * layer_height) / (width * height)),
            )
            layer_coverages.append(coverage)
            if (
                abs(layer_x) <= 1.0
                and abs(layer_y) <= 1.0
                and layer_width >= width * 0.95
                and layer_height >= height * 0.95
            ):
                full_canvas_layer = True
        canvas_count = len(canvases_by_event[event_name])
        subtitle_count = sum(
            bool(row.get("display_text") or row.get("srt_text"))
            for row in dialogue_rows
        )
        if audio_keys and subtitle_count:
            category = "audible_with_subtitles"
            recommendation = "render_no_subtitles_and_burned_subtitles"
        elif audio_keys:
            category = "audible_no_subtitles"
            recommendation = "render_no_subtitles"
        else:
            category = "silent_video"
            recommendation = "render_for_visual_archive"
        if canvas_count > 1:
            recommendation += "_per_canvas_review"
        plan_rows.append(
            {
                "event_name": event_name,
                "event_root": event_name.rsplit("_", 1)[0],
                "canvas_width": width,
                "canvas_height": height,
                "canvas": f"{width}x{height}",
                "canvas_group_count": canvas_count,
                "mixed_canvas_event": "yes" if canvas_count > 1 else "no",
                "event_duration_sec": f"{event_duration_sec:.6f}",
                "audio_end_sec": f"{audio_end_sec:.6f}",
                "audio_tail_sec": f"{max(0.0, audio_end_sec - event_duration_sec):.6f}",
                "output_duration_sec": f"{output_duration_sec:.6f}",
                "has_official_loop_cycle": "yes" if has_loop_cycle else "no",
                "max_layer_canvas_coverage": (
                    f"{max(layer_coverages):.6f}" if layer_coverages else ""
                ),
                "full_canvas_dgm_layer": "yes" if full_canvas_layer else "no",
                "z2d_layer_count": len(
                    {
                        (
                            parse_optional_int(row.get("z2d_order")) or 0,
                            row.get("z2d_name", ""),
                        )
                        for row in rows
                    }
                ),
                "dgm_segment_count": len(
                    {row.get("dgm_name", "") for row in rows}
                ),
                "source_mp4_count": len(
                    {row.get("target_mp4", "") for row in rows}
                ),
                "eventcn_audio_count": len(eventcn_rows),
                "z2d_dialogue_count": len(dialogue_rows),
                "official_audio_track_count": len(audio_keys),
                "subtitle_count": subtitle_count,
                "category": category,
                "recommendation": recommendation,
            }
        )

    plan_path = out_dir / "event_canvas_production_plan.csv"
    fields = [
        "event_name",
        "event_root",
        "canvas_width",
        "canvas_height",
        "canvas",
        "canvas_group_count",
        "mixed_canvas_event",
        "event_duration_sec",
        "audio_end_sec",
        "audio_tail_sec",
        "output_duration_sec",
        "has_official_loop_cycle",
        "max_layer_canvas_coverage",
        "full_canvas_dgm_layer",
        "z2d_layer_count",
        "dgm_segment_count",
        "source_mp4_count",
        "eventcn_audio_count",
        "z2d_dialogue_count",
        "official_audio_track_count",
        "subtitle_count",
        "category",
        "recommendation",
    ]
    write_csv(plan_path, plan_rows, fields)

    category_counts = Counter(row["category"] for row in plan_rows)
    unique_events = {row["event_name"] for row in plan_rows}
    total_duration_sec = sum(
        float(row["output_duration_sec"]) for row in plan_rows
    )
    summary_path = out_dir / "event_canvas_production_plan_summary.md"
    lines = [
        "# Event Canvas Production Plan",
        "",
        f"Exact event/canvas outputs: {len(plan_rows)}",
        f"Unique exact events: {len(unique_events)}",
        f"Mixed-canvas events: {sum(len(canvases) > 1 for canvases in canvases_by_event.values())}",
        f"Total event/canvas duration: {total_duration_sec / 3600:.3f} hours",
        "",
        "## Categories",
    ]
    for key, value in sorted(category_counts.items()):
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## Rules",
            "",
            "- Every row is one official event and one decoded Z2D root canvas.",
            "- Mixed-canvas events are kept as separate outputs and are never composited together implicitly.",
            "- EventCn audio is accepted only when the decoded OGG duration matches the official SMZ request duration.",
            "- Z2D dialogue uses exact GDB frame timing and the official OGG request.",
            "- Subtitle and no-subtitle recommendations are derived from recovered dialogue text, not visual motion heuristics.",
        ]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[event-production-plan] outputs: {len(plan_rows)}")
    print(f"[event-production-plan] unique events: {len(unique_events)}")
    print(f"[event-production-plan] categories: {dict(category_counts)}")
    print(f"[event-production-plan] wrote {plan_path}")
    print(f"[event-production-plan] wrote {summary_path}")


def meaningful_event_label(value: str) -> bool:
    if not value:
        return False
    return not re.search(
        r"(?:PP用|停止|消音|無音|ボタン音|PUSH|レバーON|Vibe|"
        r"(?:^|[_-])SE(?:[_-]|$)|(?:^|[_-])Voice(?:[_-]|$)|"
        r"(?:^|[_-])BGM(?:[_-]|$)|処理共通)",
        value,
        re.IGNORECASE,
    )


def command_bilibili_part_plan(args):
    production_rows = read_csv(Path(args.production_plan_csv))
    event_timeline_rows = read_csv(Path(args.event_timeline_events_csv))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    event_meta = {
        row.get("primary_animation", "").lower(): row
        for row in event_timeline_rows
        if row.get("primary_animation")
    }
    labels_by_root: dict[str, Counter] = defaultdict(Counter)
    for row in event_timeline_rows:
        root = row.get("root", "")
        for label in split_semicolon(row.get("sound_labels", "")):
            label = label.strip()
            if meaningful_event_label(label):
                labels_by_root[root][label] += 1

    selected_categories = set(args.category or [])
    selected = []
    for row in production_rows:
        if selected_categories and row.get("category") not in selected_categories:
            continue
        if args.audible_only and (
            parse_optional_int(row.get("official_audio_track_count")) or 0
        ) <= 0:
            continue
        selected.append(row)

    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in selected:
        grouped[(row.get("event_root", ""), row.get("canvas", ""))].append(row)

    root_label_rows = []
    for root in sorted({row.get("event_root", "") for row in selected}, key=natural_key):
        ranked = labels_by_root.get(root, Counter()).most_common()
        root_label_rows.append(
            {
                "event_root": root,
                "primary_label_candidate": ranked[0][0] if ranked else "",
                "label_candidates": ";".join(label for label, _ in ranked[:10]),
                "label_counts": ";".join(
                    f"{label}:{count}" for label, count in ranked[:10]
                ),
                "confidence": (
                    "eventcn_sound_label_candidate" if ranked else "code_only"
                ),
            }
        )
    label_by_root = {
        row["event_root"]: row["primary_label_candidate"]
        for row in root_label_rows
    }

    group_chunks = []
    for (root, canvas), rows in sorted(
        grouped.items(),
        key=lambda item: (natural_key(item[0][0]), natural_key(item[0][1])),
    ):
        rows.sort(
            key=lambda row: (
                parse_optional_int(
                    event_meta.get(row.get("event_name", "").lower(), {}).get(
                        "event_index"
                    )
                )
                if parse_optional_int(
                    event_meta.get(row.get("event_name", "").lower(), {}).get(
                        "event_index"
                    )
                )
                is not None
                else 10**9,
                natural_key(row.get("event_name", "")),
            )
        )
        chunks = []
        current = []
        current_duration = 0.0
        for row in rows:
            duration = parse_optional_float(row.get("output_duration_sec")) or 0.0
            addition = duration + (args.spacer_sec if current else 0.0)
            if current and (
                current_duration + addition > args.target_part_sec
                or len(current) >= args.max_events_per_part
            ):
                chunks.append(current)
                current = []
                current_duration = 0.0
                addition = duration
            current.append(row)
            current_duration += addition
        if current:
            chunks.append(current)
        group_chunks.append((root, canvas, chunks))

    event_output_root = (
        Path(args.event_output_root) if args.event_output_root else Path()
    )
    event_tree_root = (
        event_output_root
        if event_output_root.name.lower() == "events"
        else event_output_root / "events"
    )
    sequence_rows = []
    part_rows = []
    global_part_number = 0
    for root, canvas, chunks in group_chunks:
        root_label = label_by_root.get(root, "")
        for root_part_index, chunk in enumerate(chunks, start=1):
            global_part_number += 1
            part_key = f"P{global_part_number:03d}_{root}_{canvas}_{root_part_index:02d}"
            title_label = f" {root_label}" if root_label else ""
            part_title = (
                f"{root}{title_label} [{canvas}] "
                f"{root_part_index}/{len(chunks)}"
            )
            cursor_sec = 0.0
            audible_events = 0
            subtitle_events = 0
            for event_order, row in enumerate(chunk, start=1):
                event_name = row["event_name"]
                event_dir = (
                    event_tree_root
                    / safe_name(root)
                    / f"{safe_name(event_name)}__{safe_name(canvas)}"
                )
                no_subtitles_path = (
                    event_dir / f"{safe_name(event_name)}__no_subtitles.mp4"
                )
                subtitles_path = (
                    event_dir / f"{safe_name(event_name)}__subtitles_burned.mp4"
                )
                duration = parse_optional_float(row.get("output_duration_sec")) or 0.0
                audio_count = (
                    parse_optional_int(row.get("official_audio_track_count")) or 0
                )
                subtitle_count = parse_optional_int(row.get("subtitle_count")) or 0
                audible_events += audio_count > 0
                subtitle_events += subtitle_count > 0
                meta = event_meta.get(event_name.lower(), {})
                sequence_rows.append(
                    {
                        "global_part_number": global_part_number,
                        "part_key": part_key,
                        "part_title": part_title,
                        "event_order_in_part": event_order,
                        "event_index": meta.get("event_index", ""),
                        "event_name": event_name,
                        "event_root": root,
                        "canvas": canvas,
                        "timeline_start_sec": f"{cursor_sec:.3f}",
                        "event_duration_sec": f"{duration:.6f}",
                        "timeline_end_sec": f"{cursor_sec + duration:.3f}",
                        "spacer_after_sec": (
                            f"{args.spacer_sec:.3f}"
                            if event_order < len(chunk)
                            else "0.000"
                        ),
                        "category": row.get("category", ""),
                        "official_audio_track_count": audio_count,
                        "subtitle_count": subtitle_count,
                        "has_official_loop_cycle": row.get(
                            "has_official_loop_cycle", ""
                        ),
                        "audio_tail_sec": row.get("audio_tail_sec", ""),
                        "full_canvas_dgm_layer": row.get(
                            "full_canvas_dgm_layer", ""
                        ),
                        "no_subtitles_input": str(no_subtitles_path),
                        "subtitle_edition_input": str(
                            subtitles_path if subtitle_count > 0 else no_subtitles_path
                        ),
                        "subtitle_edition_source": (
                            "burned_subtitles" if subtitle_count > 0 else "no_dialogue"
                        ),
                    }
                )
                cursor_sec += duration
                if event_order < len(chunk):
                    cursor_sec += args.spacer_sec
            part_rows.append(
                {
                    "global_part_number": global_part_number,
                    "part_key": part_key,
                    "part_title": part_title,
                    "event_root": root,
                    "root_label_candidate": root_label,
                    "label_confidence": (
                        "eventcn_sound_label_candidate"
                        if root_label
                        else "code_only"
                    ),
                    "canvas": canvas,
                    "root_part_index": root_part_index,
                    "root_part_count": len(chunks),
                    "event_count": len(chunk),
                    "audible_event_count": audible_events,
                    "subtitle_event_count": subtitle_events,
                    "duration_sec": f"{cursor_sec:.3f}",
                    "duration_min": f"{cursor_sec / 60:.3f}",
                    "first_event": chunk[0]["event_name"],
                    "last_event": chunk[-1]["event_name"],
                    "upload_canvas": args.upload_canvas,
                    "no_subtitles_output_name": f"{part_key}__no_subtitles.mp4",
                    "subtitle_output_name": f"{part_key}__subtitles.mp4",
                }
            )

    sequence_path = out_dir / "bilibili_event_sequence.csv"
    part_path = out_dir / "bilibili_parts.csv"
    label_path = out_dir / "bilibili_root_label_candidates.csv"
    write_csv(
        sequence_path,
        sequence_rows,
        [
            "global_part_number",
            "part_key",
            "part_title",
            "event_order_in_part",
            "event_index",
            "event_name",
            "event_root",
            "canvas",
            "timeline_start_sec",
            "event_duration_sec",
            "timeline_end_sec",
            "spacer_after_sec",
            "category",
            "official_audio_track_count",
            "subtitle_count",
            "has_official_loop_cycle",
            "audio_tail_sec",
            "full_canvas_dgm_layer",
            "no_subtitles_input",
            "subtitle_edition_input",
            "subtitle_edition_source",
        ],
    )
    write_csv(
        part_path,
        part_rows,
        [
            "global_part_number",
            "part_key",
            "part_title",
            "event_root",
            "root_label_candidate",
            "label_confidence",
            "canvas",
            "root_part_index",
            "root_part_count",
            "event_count",
            "audible_event_count",
            "subtitle_event_count",
            "duration_sec",
            "duration_min",
            "first_event",
            "last_event",
            "upload_canvas",
            "no_subtitles_output_name",
            "subtitle_output_name",
        ],
    )
    write_csv(
        label_path,
        root_label_rows,
        [
            "event_root",
            "primary_label_candidate",
            "label_candidates",
            "label_counts",
            "confidence",
        ],
    )
    summary_path = out_dir / "bilibili_part_plan_summary.md"
    total_duration = sum(
        parse_optional_float(row.get("duration_sec")) or 0.0 for row in part_rows
    )
    lines = [
        "# Bilibili Part Plan",
        "",
        f"Event/canvas rows: {len(selected)}",
        f"Official event roots: {len(grouped)} root/canvas groups",
        f"Parts: {len(part_rows)}",
        f"Total duration: {total_duration / 3600:.3f} hours",
        f"Target part duration: {args.target_part_sec / 60:.1f} minutes",
        f"Maximum events per part: {args.max_events_per_part}",
        f"Spacer: {args.spacer_sec:.3f} sec",
        f"Upload canvas: {args.upload_canvas}",
        "",
        "## Grouping rules",
        "",
        "- Event order follows EventCn event_index, then the natural event name.",
        "- Events are never merged across an official acXXXX root or decoded Z2D canvas.",
        "- Long root/canvas groups are split by target duration and event-count limits.",
        "- Subtitle edition uses the burned-subtitle event only when exact dialogue exists; other events reuse the no-dialogue source.",
        "- Root title labels are EventCn sound-label candidates and remain explicitly marked for human review.",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[bilibili-part-plan] parts: {len(part_rows)}")
    print(f"[bilibili-part-plan] sequence rows: {len(sequence_rows)}")
    print(f"[bilibili-part-plan] wrote {sequence_path}")
    print(f"[bilibili-part-plan] wrote {part_path}")
    print(f"[bilibili-part-plan] wrote {label_path}")
    print(f"[bilibili-part-plan] wrote {summary_path}")


def command_bilibili_upload_review(args):
    part_rows = read_csv(Path(args.parts_csv))
    root_rows = read_csv(Path(args.root_labels_csv))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    root_meta = {
        row.get("event_root", ""): row
        for row in root_rows
        if row.get("event_root")
    }
    review_rows = []
    for part in part_rows:
        root = part.get("event_root", "")
        meta = root_meta.get(root, {})
        primary_label = meta.get("primary_label_candidate", "")
        primary_label_display = unicodedata.normalize("NFKC", primary_label)
        label_candidates = split_semicolon(meta.get("label_candidates", ""))
        label_candidates_display = ";".join(
            unicodedata.normalize("NFKC", value)
            for value in label_candidates
        )
        review_reasons = []
        if not primary_label:
            review_reasons.append("missing_eventcn_label")
        if len(label_candidates) > args.label_diversity_threshold:
            review_reasons.append("high_label_diversity")
        if re.match(r"^(?:seq_|SE_|BGM_|Voice_)", primary_label, re.IGNORECASE):
            review_reasons.append("technical_prefix")
        if re.search(r"(?:_001|_002|_003|【|】|CD\d)", primary_label):
            review_reasons.append("internal_variant_marker")

        root_part_index = parse_optional_int(part.get("root_part_index")) or 1
        root_part_count = parse_optional_int(part.get("root_part_count")) or 1
        title_label = primary_label_display or "演出集"
        part_suffix = (
            f" {root_part_index}/{root_part_count}"
            if root_part_count > 1
            else ""
        )
        title_candidate = (
            f"スマスロ マギアレコード {root} {title_label} "
            f"[{part.get('canvas', '')}]{part_suffix}"
        )
        title_candidate = title_candidate[: args.max_title_length].rstrip()
        event_count = parse_optional_int(part.get("event_count")) or 0
        audible_event_count = (
            parse_optional_int(part.get("audible_event_count")) or 0
        )
        silent_event_count = max(0, event_count - audible_event_count)
        description_candidate = (
            f"公式イベントコード: {root}\n"
            f"収録範囲: {part.get('first_event', '')} - "
            f"{part.get('last_event', '')}\n"
            f"イベント数: {event_count}\n"
            f"音声付きイベント数: {audible_event_count}\n"
            f"無音映像イベント数: {silent_event_count}\n"
            f"字幕対象イベント数: {part.get('subtitle_event_count', '')}\n"
            "GDB -> Z2D -> DGM -> CRI の公式参照関係に基づく再構成。"
        )
        review_rows.append(
            {
                "global_part_number": part.get("global_part_number", ""),
                "part_key": part.get("part_key", ""),
                "event_root": root,
                "canvas": part.get("canvas", ""),
                "event_count": part.get("event_count", ""),
                "subtitle_event_count": part.get("subtitle_event_count", ""),
                "duration_min": part.get("duration_min", ""),
                "first_event": part.get("first_event", ""),
                "last_event": part.get("last_event", ""),
                "audible_event_count": audible_event_count,
                "silent_event_count": silent_event_count,
                "eventcn_primary_label": primary_label,
                "eventcn_primary_label_display": primary_label_display,
                "eventcn_label_candidates": meta.get("label_candidates", ""),
                "eventcn_label_candidates_display": (
                    label_candidates_display
                ),
                "eventcn_label_candidate_count": len(label_candidates),
                "title_candidate": title_candidate,
                "description_candidate": description_candidate,
                "manual_review_required": "yes",
                "review_reasons": ";".join(review_reasons)
                or "eventcn_label_is_still_candidate",
                "no_subtitles_output_name": part.get(
                    "no_subtitles_output_name", ""
                ),
                "subtitle_output_name": part.get("subtitle_output_name", ""),
                "review_status": "",
                "approved_title": "",
                "review_notes": "",
            }
        )
    fields = list(review_rows[0].keys()) if review_rows else []
    review_path = out_dir / "bilibili_upload_review.csv"
    write_csv(review_path, review_rows, fields)
    reason_counts = Counter()
    for row in review_rows:
        for reason in split_semicolon(row["review_reasons"]):
            reason_counts[reason] += 1
    summary_path = out_dir / "bilibili_upload_review_summary.md"
    summary_path.write_text(
        "\n".join(
            [
                "# Bilibili Upload Review",
                "",
                f"Parts: {len(review_rows)}",
                "All titles require human approval before upload.",
                "",
                "## Review flags",
                *[
                    f"- {reason}: {count}"
                    for reason, count in sorted(reason_counts.items())
                ],
                "",
                "Debug/smali ac-code labels are intentionally excluded because the table contains labels from unrelated residual game content.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"[bilibili-upload-review] wrote {review_path}")
    print(f"[bilibili-upload-review] wrote {summary_path}")


def audit_event_output(row: dict, source_field: str, threshold_db: float) -> dict:
    source = Path(row.get(source_field, ""))
    expected_audible = (
        parse_optional_int(row.get("official_audio_track_count")) or 0
    ) > 0
    result = {
        "global_part_number": row.get("global_part_number", ""),
        "part_key": row.get("part_key", ""),
        "event_order_in_part": row.get("event_order_in_part", ""),
        "event_name": row.get("event_name", ""),
        "canvas": row.get("canvas", ""),
        "category": row.get("category", ""),
        "planned_duration_sec": row.get("event_duration_sec", ""),
        "source": str(source),
        "source_exists": "yes" if source.exists() else "no",
        "probe_ok": "no",
        "probe_error": "",
        "actual_duration_sec": "",
        "duration_delta_sec": "",
        "has_video": "no",
        "has_audio": "no",
        "video_codec": "",
        "audio_codec": "",
        "width": "",
        "height": "",
        "frame_rate": "",
        "audio_volume_ok": "no",
        "mean_volume_db": "",
        "max_volume_db": "",
        "expected_audible": "yes" if expected_audible else "no",
        "audible_audio": "no",
        "audio_expectation_ok": "no",
    }
    if not source.exists():
        result["probe_error"] = "source missing"
        return result

    probe = probe_mp4(source)
    result.update(
        {
            "probe_ok": "yes" if probe.get("probe_ok") else "no",
            "probe_error": probe.get("probe_error", ""),
            "actual_duration_sec": probe.get("duration_sec", ""),
            "has_video": "yes" if probe.get("has_video") else "no",
            "has_audio": "yes" if probe.get("has_audio") else "no",
            "video_codec": probe.get("video_codec", ""),
            "audio_codec": probe.get("audio_codec", ""),
            "width": probe.get("width", ""),
            "height": probe.get("height", ""),
            "frame_rate": probe.get("frame_rate", ""),
        }
    )
    planned_duration = parse_optional_float(row.get("event_duration_sec"))
    actual_duration = parse_optional_float(probe.get("duration_sec"))
    if planned_duration is not None and actual_duration is not None:
        result["duration_delta_sec"] = f"{actual_duration - planned_duration:.6f}"
    if probe.get("has_audio"):
        volume = probe_audio_volume(source)
        max_volume = volume.pop("max_volume_value")
        actual_audible = max_volume is not None and max_volume > threshold_db
        result.update(
            {
                "audio_volume_ok": "yes" if volume["audio_volume_ok"] else "no",
                "mean_volume_db": volume["mean_volume_db"],
                "max_volume_db": volume["max_volume_db"],
                "audible_audio": "yes" if actual_audible else "no",
                "audio_expectation_ok": (
                    "yes" if actual_audible == expected_audible else "no"
                ),
            }
        )
        if volume["audio_volume_error"]:
            result["probe_error"] = volume["audio_volume_error"][-4000:]
    return result


def command_event_output_audit(args):
    sequence_rows = read_csv(Path(args.sequence_csv))
    source_field = (
        "no_subtitles_input"
        if args.edition == "no-subtitles"
        else "subtitle_edition_input"
    )
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / f"event_output_audit_{args.edition}.csv"

    rows = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = [
            executor.submit(
                audit_event_output,
                row,
                source_field,
                args.threshold_db,
            )
            for row in sequence_rows
        ]
        for completed, future in enumerate(as_completed(futures), start=1):
            rows.append(future.result())
            if completed % 250 == 0 or completed == len(futures):
                checkpoint_rows = sorted(
                    rows,
                    key=lambda row: (
                        parse_optional_int(row.get("global_part_number")) or 0,
                        parse_optional_int(row.get("event_order_in_part")) or 0,
                    ),
                )
                write_csv(
                    manifest_path,
                    checkpoint_rows,
                    list(checkpoint_rows[0].keys()) if checkpoint_rows else [],
                )
                print(
                    f"[event-output-audit] processed {completed}/{len(futures)}"
                )
    rows.sort(
        key=lambda row: (
            parse_optional_int(row.get("global_part_number")) or 0,
            parse_optional_int(row.get("event_order_in_part")) or 0,
        )
    )
    fields = list(rows[0].keys()) if rows else []
    write_csv(manifest_path, rows, fields)

    missing = sum(row["source_exists"] != "yes" for row in rows)
    invalid = sum(
        row["probe_ok"] != "yes"
        or row["has_video"] != "yes"
        or row["has_audio"] != "yes"
        for row in rows
    )
    audio_expectation_mismatch = sum(
        row["audio_expectation_ok"] != "yes" for row in rows
    )
    duration_mismatch = sum(
        abs(parse_optional_float(row.get("duration_delta_sec")) or 0.0)
        > args.duration_tolerance_sec
        for row in rows
    )
    summary_path = out_dir / f"event_output_audit_{args.edition}_summary.md"
    summary_path.write_text(
        "\n".join(
            [
                "# Event Output Audit",
                "",
                f"Edition: {args.edition}",
                f"Rows: {len(rows)}",
                f"Missing sources: {missing}",
                f"Invalid video/audio streams: {invalid}",
                (
                    "Audio expectation mismatches at "
                    f"{args.threshold_db:.1f} dBFS: "
                    f"{audio_expectation_mismatch}"
                ),
                (
                    "Duration mismatches above "
                    f"{args.duration_tolerance_sec:.3f} sec: {duration_mismatch}"
                ),
                "",
                "Audio is classified from decoded samples and compared with the production plan expectation.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"[event-output-audit] wrote {manifest_path}")
    print(f"[event-output-audit] wrote {summary_path}")


def event_part_video_args(args) -> list[str]:
    if args.encoder == "h264_nvenc":
        return [
            "-c:v",
            "h264_nvenc",
            "-preset",
            "p6",
            "-rc",
            "vbr",
            "-cq",
            str(args.cq),
            "-b:v",
            "0",
        ]
    return [
        "-c:v",
        "libx264",
        "-preset",
        "slow",
        "-crf",
        str(args.crf),
    ]


def normalize_bilibili_segment(
    source: Path,
    output: Path,
    width: int,
    height: int,
    fps: int,
    spacer_sec: float,
    args,
) -> dict:
    probe = probe_mp4(source)
    if (
        not probe.get("probe_ok")
        or not probe.get("has_video")
        or not probe.get("has_audio")
    ):
        raise RuntimeError(f"invalid source streams: {source}")
    duration = parse_optional_float(probe.get("duration_sec"))
    if duration is None or duration <= 0:
        raise RuntimeError(f"invalid source duration: {source}")
    target_duration = duration + max(0.0, spacer_sec)
    video_filter = (
        f"scale=w={width}:h={height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
        f"setsar=1,fps={fps},format=yuv420p"
    )
    if spacer_sec > 0:
        video_filter += (
            f",tpad=stop_mode=add:stop_duration={spacer_sec:.6f}:color=black"
        )
    audio_filter = (
        "aresample=48000,"
        "aformat=sample_rates=48000:channel_layouts=stereo,apad"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-nostats",
        "-v",
        "error",
        "-i",
        str(source),
        "-vf",
        video_filter,
        "-af",
        audio_filter,
        "-t",
        f"{target_duration:.6f}",
        *event_part_video_args(args),
        "-c:a",
        "flac",
        "-ar",
        "48000",
        "-ac",
        "2",
        str(output),
    ]
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip()[-4000:])
    return {
        "source_duration_sec": duration,
        "segment_duration_sec": target_duration,
        "command": subprocess.list2cmdline(cmd),
    }


def bilibili_part_sequence_signature(rows: list[dict]) -> tuple:
    return tuple(
        (
            row.get("event_name", ""),
            row.get("canvas", ""),
            row.get("event_duration_sec", ""),
            row.get("spacer_after_sec", ""),
            row.get("no_subtitles_input", ""),
            row.get("subtitle_edition_input", ""),
        )
        for row in rows
    )


def command_build_bilibili_part(args):
    sequence_rows = read_csv(Path(args.sequence_csv))
    part_rows = read_csv(Path(args.parts_csv))
    selected_numbers = set(args.part_number or [])
    selected_keys = set(args.part_key or [])
    if not args.all_parts and not selected_numbers and not selected_keys:
        raise ValueError(
            "select --part-number/--part-key, or pass --all-parts explicitly"
        )
    selected_parts = [
        row
        for row in part_rows
        if args.all_parts
        or (parse_optional_int(row.get("global_part_number")) in selected_numbers)
        or row.get("part_key") in selected_keys
    ]
    if not selected_parts:
        raise ValueError("no Bilibili parts matched the requested selection")

    editions = (
        ["no-subtitles", "subtitles"]
        if args.edition == "both"
        else [args.edition]
    )
    upload_canvas = parse_canvas_selector(args.upload_canvas)
    if upload_canvas is None:
        raise ValueError("upload canvas is required")
    width, height = upload_canvas
    out_dir = Path(args.out_dir).resolve()
    work_root = (out_dir / "_work").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    sequence_by_part: dict[int, list[dict]] = defaultdict(list)
    for row in sequence_rows:
        number = parse_optional_int(row.get("global_part_number"))
        if number is not None:
            sequence_by_part[number].append(row)
    for rows in sequence_by_part.values():
        rows.sort(
            key=lambda row: parse_optional_int(row.get("event_order_in_part")) or 0
        )

    reuse_values = (
        args.reuse_sequence_csv,
        args.reuse_parts_csv,
        args.reuse_output_dir,
    )
    if any(reuse_values) and not all(reuse_values):
        raise ValueError(
            "reuse requires --reuse-sequence-csv, --reuse-parts-csv, "
            "and --reuse-output-dir together"
        )
    reuse_by_signature = {}
    reuse_output_dir = (
        Path(args.reuse_output_dir).resolve()
        if args.reuse_output_dir
        else None
    )
    if reuse_output_dir is not None:
        reuse_sequence_rows = read_csv(Path(args.reuse_sequence_csv))
        reuse_part_rows = read_csv(Path(args.reuse_parts_csv))
        reuse_parts_by_number = {
            parse_optional_int(row.get("global_part_number")): row
            for row in reuse_part_rows
        }
        reuse_sequence_by_part: dict[int, list[dict]] = defaultdict(list)
        for row in reuse_sequence_rows:
            number = parse_optional_int(row.get("global_part_number"))
            if number is not None:
                reuse_sequence_by_part[number].append(row)
        for number, rows in reuse_sequence_by_part.items():
            rows.sort(
                key=lambda row: (
                    parse_optional_int(row.get("event_order_in_part")) or 0
                )
            )
            reuse_part = reuse_parts_by_number.get(number)
            if reuse_part is not None:
                reuse_by_signature[
                    bilibili_part_sequence_signature(rows)
                ] = reuse_part

    manifest_rows = []
    for part in selected_parts:
        part_number = parse_optional_int(part.get("global_part_number"))
        if part_number is None:
            continue
        events = sequence_by_part.get(part_number, [])
        if not events:
            continue
        reuse_part = reuse_by_signature.get(
            bilibili_part_sequence_signature(events)
        )
        for edition in editions:
            source_field = (
                "no_subtitles_input"
                if edition == "no-subtitles"
                else "subtitle_edition_input"
            )
            output_name = (
                part["no_subtitles_output_name"]
                if edition == "no-subtitles"
                else part["subtitle_output_name"]
            )
            output_path = (out_dir / output_name).resolve()
            no_subtitles_part_path = (
                out_dir / part["no_subtitles_output_name"]
            ).resolve()
            work_dir = (
                work_root / safe_name(part["part_key"]) / safe_name(edition)
            ).resolve()
            if not output_path.is_relative_to(out_dir) or not work_dir.is_relative_to(
                work_root
            ):
                raise ValueError("resolved Bilibili output escaped its output root")
            row = {
                "global_part_number": part_number,
                "part_key": part["part_key"],
                "edition": edition,
                "event_count": len(events),
                "output": str(output_path),
                "status": "planned",
                "duration_sec": "",
                "has_video": "",
                "has_audio": "",
                "audible_audio": "",
                "output_size_bytes": "",
                "error": "",
            }
            subtitle_event_count = (
                parse_optional_int(part.get("subtitle_event_count")) or 0
            )
            if output_path.exists() and not args.overwrite:
                row["status"] = "exists"
                manifest_rows.append(row)
                continue
            reuse_source = None
            if reuse_part is not None and reuse_output_dir is not None:
                reuse_name_field = (
                    "no_subtitles_output_name"
                    if edition == "no-subtitles"
                    else "subtitle_output_name"
                )
                reuse_source = (
                    reuse_output_dir / reuse_part.get(reuse_name_field, "")
                ).resolve()
                if not reuse_source.is_relative_to(reuse_output_dir):
                    raise ValueError(
                        "resolved reusable Bilibili source escaped its root"
                    )
            if reuse_source is not None and reuse_source.exists():
                if not args.execute:
                    row["status"] = "would_reuse_part"
                else:
                    if output_path.exists():
                        output_path.unlink()
                    try:
                        os.link(reuse_source, output_path)
                        row["status"] = "linked_reused_part"
                    except OSError:
                        shutil.copy2(reuse_source, output_path)
                        row["status"] = "copied_reused_part"
                    reused_probe = probe_mp4(output_path)
                    reused_volume = probe_audio_volume(output_path)
                    reused_max_volume = reused_volume.pop("max_volume_value")
                    row.update(
                        {
                            "duration_sec": reused_probe.get(
                                "duration_sec", ""
                            ),
                            "has_video": (
                                "yes" if reused_probe.get("has_video") else "no"
                            ),
                            "has_audio": (
                                "yes" if reused_probe.get("has_audio") else "no"
                            ),
                            "audible_audio": (
                                "yes"
                                if reused_max_volume is not None
                                and reused_max_volume > args.threshold_db
                                else "no"
                            ),
                            "output_size_bytes": output_path.stat().st_size,
                        }
                    )
                manifest_rows.append(row)
                continue
            if (
                edition == "subtitles"
                and subtitle_event_count == 0
                and no_subtitles_part_path.exists()
            ):
                if not args.execute:
                    row["status"] = "would_link_no_subtitles"
                else:
                    if output_path.exists():
                        output_path.unlink()
                    try:
                        os.link(no_subtitles_part_path, output_path)
                        row["status"] = "linked_no_subtitles"
                    except OSError:
                        shutil.copy2(no_subtitles_part_path, output_path)
                        row["status"] = "copied_no_subtitles"
                    linked_probe = probe_mp4(output_path)
                    row.update(
                        {
                            "duration_sec": linked_probe.get("duration_sec", ""),
                            "has_video": (
                                "yes" if linked_probe.get("has_video") else "no"
                            ),
                            "has_audio": (
                                "yes" if linked_probe.get("has_audio") else "no"
                            ),
                            "audible_audio": "yes",
                            "output_size_bytes": output_path.stat().st_size,
                        }
                    )
                manifest_rows.append(row)
                continue
            if not args.execute:
                missing = [
                    event[source_field]
                    for event in events
                    if not Path(event[source_field]).exists()
                ]
                row["status"] = "dry_run" if not missing else "missing_sources"
                row["error"] = "; ".join(missing[:10])
                manifest_rows.append(row)
                continue

            try:
                work_dir.mkdir(parents=True, exist_ok=True)
                segment_rows = []
                segment_paths = []
                for index, event in enumerate(events, start=1):
                    source = Path(event[source_field])
                    if not source.exists():
                        raise FileNotFoundError(source)
                    spacer_sec = (
                        parse_optional_float(event.get("spacer_after_sec")) or 0.0
                    )
                    segment_path = work_dir / f"segment_{index:04d}.mkv"
                    segment_info = normalize_bilibili_segment(
                        source,
                        segment_path,
                        width,
                        height,
                        args.fps,
                        spacer_sec,
                        args,
                    )
                    segment_paths.append(segment_path)
                    segment_rows.append(
                        {
                            "event_order": index,
                            "event_name": event.get("event_name", ""),
                            "source": str(source),
                            "segment": str(segment_path),
                            "spacer_after_sec": f"{spacer_sec:.6f}",
                            **segment_info,
                        }
                    )
                    print(
                        f"[build-bilibili-part] {part['part_key']} {edition} "
                        f"segment {index}/{len(events)}"
                    )
                segment_manifest = work_dir / "segments.csv"
                write_csv(
                    segment_manifest,
                    segment_rows,
                    list(segment_rows[0].keys()),
                )
                concat_path = work_dir / "concat.txt"
                concat_lines = []
                for path in segment_paths:
                    escaped = path.resolve().as_posix().replace("'", "'\\''")
                    concat_lines.append(f"file '{escaped}'")
                concat_path.write_text(
                    "\n".join(concat_lines) + "\n",
                    encoding="utf-8",
                )
                concat_output = work_dir / "part_concat.mkv"
                concat_cmd = [
                    "ffmpeg",
                    "-y",
                    "-hide_banner",
                    "-nostats",
                    "-v",
                    "error",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(concat_path),
                    "-c",
                    "copy",
                    str(concat_output),
                ]
                concat_result = subprocess.run(
                    concat_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                if concat_result.returncode != 0:
                    raise RuntimeError(
                        (concat_result.stderr or concat_result.stdout).strip()[-4000:]
                    )
                final_cmd = [
                    "ffmpeg",
                    "-y",
                    "-hide_banner",
                    "-nostats",
                    "-v",
                    "error",
                    "-i",
                    str(concat_output),
                    "-map",
                    "0:v:0",
                    "-map",
                    "0:a:0",
                    "-c:v",
                    "copy",
                    "-af",
                    (
                        f"loudnorm=I={args.loudness_i:.3f}:"
                        f"LRA=11:TP={args.true_peak_db:.3f}"
                    ),
                    "-c:a",
                    "aac",
                    "-b:a",
                    args.audio_bitrate,
                    "-ar",
                    "48000",
                    "-ac",
                    "2",
                    "-movflags",
                    "+faststart",
                    str(output_path),
                ]
                final_result = subprocess.run(
                    final_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                if final_result.returncode != 0:
                    raise RuntimeError(
                        (final_result.stderr or final_result.stdout).strip()[-4000:]
                    )
                output_probe = probe_mp4(output_path)
                output_volume = probe_audio_volume(output_path)
                max_volume = output_volume.pop("max_volume_value")
                row.update(
                    {
                        "status": "ok",
                        "duration_sec": output_probe.get("duration_sec", ""),
                        "has_video": (
                            "yes" if output_probe.get("has_video") else "no"
                        ),
                        "has_audio": (
                            "yes" if output_probe.get("has_audio") else "no"
                        ),
                        "audible_audio": (
                            "yes"
                            if max_volume is not None
                            and max_volume > args.threshold_db
                            else "no"
                        ),
                        "output_size_bytes": output_path.stat().st_size,
                    }
                )
                if args.cleanup_work and work_dir.is_relative_to(work_root):
                    shutil.rmtree(work_dir)
            except Exception as exc:
                row["status"] = "failed"
                row["error"] = str(exc)
            manifest_rows.append(row)

    manifest_path = out_dir / "bilibili_part_build.csv"
    fields = list(manifest_rows[0].keys()) if manifest_rows else []
    write_csv(manifest_path, manifest_rows, fields)
    counts = Counter(row["status"] for row in manifest_rows)
    summary_path = out_dir / "bilibili_part_build_summary.md"
    summary_path.write_text(
        "\n".join(
            [
                "# Bilibili Part Build",
                "",
                f"Selected parts: {len(selected_parts)}",
                f"Editions: {', '.join(editions)}",
                f"Upload canvas: {width}x{height}",
                f"Final loudness target: {args.loudness_i:.1f} LUFS",
                f"Final true-peak target: {args.true_peak_db:.1f} dBTP",
                f"Execute: {'yes' if args.execute else 'no'}",
                "",
                "## Status",
                *[f"- {key}: {value}" for key, value in sorted(counts.items())],
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"[build-bilibili-part] status: {dict(counts)}")
    print(f"[build-bilibili-part] wrote {manifest_path}")
    print(f"[build-bilibili-part] wrote {summary_path}")


def parse_frame_rate(value: str) -> float | None:
    if not value:
        return None
    if "/" in value:
        numerator, denominator = value.split("/", 1)
        denominator_value = parse_optional_float(denominator)
        if denominator_value in (None, 0.0):
            return None
        numerator_value = parse_optional_float(numerator)
        return (
            numerator_value / denominator_value
            if numerator_value is not None
            else None
        )
    return parse_optional_float(value)


def physical_file_key(path: Path) -> tuple:
    stat = path.stat()
    return (stat.st_dev, stat.st_ino, stat.st_size)


def audit_bilibili_media(path: Path, threshold_db: float) -> dict:
    result = {
        "source_exists": "yes" if path.exists() else "no",
        "probe_ok": "no",
        "probe_error": "",
        "actual_duration_sec": "",
        "has_video": "no",
        "has_audio": "no",
        "video_codec": "",
        "audio_codec": "",
        "width": "",
        "height": "",
        "frame_rate": "",
        "average_frame_rate": "",
        "audio_sample_rate": "",
        "audio_channels": "",
        "audio_volume_ok": "no",
        "mean_volume_db": "",
        "max_volume_db": "",
        "audible_audio": "no",
        "output_size_bytes": "",
    }
    if not path.exists():
        result["probe_error"] = "source missing"
        return result
    result["output_size_bytes"] = path.stat().st_size
    probe = probe_mp4(path)
    result.update(
        {
            "probe_ok": "yes" if probe.get("probe_ok") else "no",
            "probe_error": probe.get("probe_error", ""),
            "actual_duration_sec": probe.get("duration_sec", ""),
            "has_video": "yes" if probe.get("has_video") else "no",
            "has_audio": "yes" if probe.get("has_audio") else "no",
            "video_codec": probe.get("video_codec", ""),
            "audio_codec": probe.get("audio_codec", ""),
            "width": probe.get("width", ""),
            "height": probe.get("height", ""),
            "frame_rate": probe.get("frame_rate", ""),
            "average_frame_rate": probe.get("average_frame_rate", ""),
            "audio_sample_rate": probe.get("audio_sample_rate", ""),
            "audio_channels": probe.get("audio_channels", ""),
        }
    )
    if probe.get("has_audio"):
        volume = probe_audio_volume(path)
        max_volume = volume.pop("max_volume_value")
        result.update(
            {
                "audio_volume_ok": (
                    "yes" if volume["audio_volume_ok"] else "no"
                ),
                "mean_volume_db": volume["mean_volume_db"],
                "max_volume_db": volume["max_volume_db"],
                "audible_audio": (
                    "yes"
                    if max_volume is not None and max_volume > threshold_db
                    else "no"
                ),
            }
        )
        if volume["audio_volume_error"]:
            result["probe_error"] = volume["audio_volume_error"][-4000:]
    return result


def command_bilibili_part_output_audit(args):
    part_rows = read_csv(Path(args.parts_csv))
    output_dir = Path(args.output_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    audit_path = out_dir / "bilibili_part_output_audit.csv"

    jobs = []
    for part in part_rows:
        for edition, name_field in (
            ("no-subtitles", "no_subtitles_output_name"),
            ("subtitles", "subtitle_output_name"),
        ):
            jobs.append(
                {
                    "part": part,
                    "edition": edition,
                    "path": output_dir / part.get(name_field, ""),
                }
            )

    unique_paths = {}
    path_keys = {}
    for job in jobs:
        path = job["path"]
        key = ("missing", str(path).lower())
        if path.exists():
            try:
                key = physical_file_key(path)
            except OSError:
                key = ("path", str(path.resolve()).lower())
        path_keys[str(path)] = key
        unique_paths.setdefault(key, path)

    media_by_key = {}
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(
                audit_bilibili_media,
                path,
                args.threshold_db,
            ): key
            for key, path in unique_paths.items()
        }
        for completed, future in enumerate(as_completed(futures), start=1):
            media_by_key[futures[future]] = future.result()
            if completed % 25 == 0 or completed == len(futures):
                print(
                    "[bilibili-part-output-audit] decoded "
                    f"{completed}/{len(futures)} physical files"
                )

    rows = []
    for job in jobs:
        part = job["part"]
        path = job["path"]
        media = media_by_key[path_keys[str(path)]]
        planned_duration = parse_optional_float(part.get("duration_sec"))
        actual_duration = parse_optional_float(media.get("actual_duration_sec"))
        duration_delta = (
            actual_duration - planned_duration
            if actual_duration is not None and planned_duration is not None
            else None
        )
        expected_canvas = parse_canvas_selector(
            part.get("upload_canvas") or args.upload_canvas
        )
        width = parse_optional_int(media.get("width"))
        height = parse_optional_int(media.get("height"))
        actual_fps = parse_frame_rate(
            media.get("average_frame_rate", "")
            or media.get("frame_rate", "")
        )
        event_count = parse_optional_int(part.get("event_count")) or 0
        duration_tolerance = (
            args.duration_tolerance_sec
            + event_count / max(args.fps, 1.0)
        )
        expected_audible = (
            parse_optional_int(part.get("audible_event_count")) or 0
        ) > 0
        actual_audible = media.get("audible_audio") == "yes"
        max_volume = parse_optional_float(media.get("max_volume_db"))
        stream_contract_ok = (
            media.get("probe_ok") == "yes"
            and media.get("has_video") == "yes"
            and media.get("has_audio") == "yes"
            and media.get("video_codec") == args.video_codec
            and media.get("audio_codec") == args.audio_codec
            and expected_canvas == (width, height)
            and actual_fps is not None
            and abs(actual_fps - args.fps) <= args.fps_tolerance
            and parse_optional_int(media.get("audio_sample_rate"))
            == args.audio_sample_rate
            and parse_optional_int(media.get("audio_channels"))
            == args.audio_channels
        )
        duration_ok = (
            duration_delta is not None
            and abs(duration_delta) <= duration_tolerance
        )
        audio_expectation_ok = actual_audible == expected_audible
        peak_safe = (
            max_volume is not None and max_volume <= args.max_peak_db
        )
        row = {
            "global_part_number": part.get("global_part_number", ""),
            "part_key": part.get("part_key", ""),
            "edition": job["edition"],
            "output": str(path),
            "source_exists": media["source_exists"],
            "probe_ok": media["probe_ok"],
            "probe_error": media["probe_error"],
            "planned_duration_sec": part.get("duration_sec", ""),
            "actual_duration_sec": media["actual_duration_sec"],
            "duration_delta_sec": (
                f"{duration_delta:.6f}" if duration_delta is not None else ""
            ),
            "duration_tolerance_sec": f"{duration_tolerance:.6f}",
            "duration_ok": "yes" if duration_ok else "no",
            "has_video": media["has_video"],
            "has_audio": media["has_audio"],
            "video_codec": media["video_codec"],
            "audio_codec": media["audio_codec"],
            "width": media["width"],
            "height": media["height"],
            "frame_rate": media["frame_rate"],
            "average_frame_rate": media["average_frame_rate"],
            "audio_sample_rate": media["audio_sample_rate"],
            "audio_channels": media["audio_channels"],
            "stream_contract_ok": "yes" if stream_contract_ok else "no",
            "expected_audible": "yes" if expected_audible else "no",
            "audible_audio": media["audible_audio"],
            "audio_expectation_ok": (
                "yes" if audio_expectation_ok else "no"
            ),
            "mean_volume_db": media["mean_volume_db"],
            "max_volume_db": media["max_volume_db"],
            "peak_safe": "yes" if peak_safe else "no",
            "output_size_bytes": media["output_size_bytes"],
            "overall_ok": (
                "yes"
                if stream_contract_ok
                and duration_ok
                and audio_expectation_ok
                and peak_safe
                else "no"
            ),
        }
        rows.append(row)

    rows.sort(
        key=lambda row: (
            parse_optional_int(row.get("global_part_number")) or 0,
            row.get("edition", ""),
        )
    )
    fields = list(rows[0].keys()) if rows else []
    write_csv(audit_path, rows, fields)

    part_by_number = {
        parse_optional_int(row.get("global_part_number")): row
        for row in part_rows
    }
    storage_rows = []
    for part_number, part in sorted(
        part_by_number.items(),
        key=lambda item: item[0] or 0,
    ):
        no_subtitles = output_dir / part.get("no_subtitles_output_name", "")
        subtitles = output_dir / part.get("subtitle_output_name", "")
        subtitle_count = parse_optional_int(part.get("subtitle_event_count")) or 0
        same_physical_file = False
        outputs_exist = no_subtitles.exists() and subtitles.exists()
        if outputs_exist:
            try:
                same_physical_file = os.path.samefile(no_subtitles, subtitles)
            except OSError:
                same_physical_file = False
        expected_hardlink = subtitle_count == 0
        storage_rows.append(
            {
                "global_part_number": part_number or "",
                "part_key": part.get("part_key", ""),
                "subtitle_event_count": subtitle_count,
                "outputs_exist": "yes" if outputs_exist else "no",
                "expected_shared_physical_file": (
                    "yes" if expected_hardlink else "no"
                ),
                "same_physical_file": (
                    "yes" if same_physical_file else "no"
                ),
                "storage_relation_ok": (
                    "yes"
                    if outputs_exist
                    and same_physical_file == expected_hardlink
                    else ("no" if outputs_exist else "")
                ),
                "no_subtitles_output": str(no_subtitles),
                "subtitle_output": str(subtitles),
            }
        )
    storage_path = out_dir / "bilibili_part_storage_audit.csv"
    write_csv(
        storage_path,
        storage_rows,
        list(storage_rows[0].keys()) if storage_rows else [],
    )

    missing = sum(row["source_exists"] != "yes" for row in rows)
    stream_failures = sum(row["stream_contract_ok"] != "yes" for row in rows)
    duration_failures = sum(row["duration_ok"] != "yes" for row in rows)
    audio_failures = sum(
        row["audio_expectation_ok"] != "yes" for row in rows
    )
    peak_failures = sum(row["peak_safe"] != "yes" for row in rows)
    overall_failures = sum(row["overall_ok"] != "yes" for row in rows)
    storage_failures = sum(
        row["outputs_exist"] == "yes"
        and row["storage_relation_ok"] != "yes"
        for row in storage_rows
    )
    summary_path = out_dir / "bilibili_part_output_audit_summary.md"
    summary_path.write_text(
        "\n".join(
            [
                "# Bilibili Part Output Audit",
                "",
                f"Logical output rows: {len(rows)}",
                f"Unique physical media files decoded: {len(unique_paths)}",
                f"Missing outputs: {missing}",
                f"Stream contract failures: {stream_failures}",
                f"Duration failures: {duration_failures}",
                f"Audio expectation failures: {audio_failures}",
                f"Peak safety failures: {peak_failures}",
                f"Overall failures: {overall_failures}",
                f"Storage relation failures: {storage_failures}",
                "",
                (
                    "Required stream contract: "
                    f"{args.video_codec}/{args.audio_codec}, "
                    f"{args.upload_canvas}, average {args.fps:g} fps, "
                    f"{args.audio_sample_rate} Hz, "
                    f"{args.audio_channels} channels."
                ),
                (
                    "Duration tolerance is the configured base plus one "
                    "frame per normalized event to cover timestamp rounding."
                ),
                (
                    "Audio audibility is measured from decoded samples; "
                    "subtitle aliases without dialogue are checked as hard links."
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"[bilibili-part-output-audit] wrote {audit_path}")
    print(f"[bilibili-part-output-audit] wrote {storage_path}")
    print(f"[bilibili-part-output-audit] wrote {summary_path}")


SRT_CUE_RE = re.compile(
    r"(?P<start_h>\d{2}):(?P<start_m>\d{2}):(?P<start_s>\d{2}),"
    r"(?P<start_ms>\d{3})\s+-->\s+"
    r"(?P<end_h>\d{2}):(?P<end_m>\d{2}):(?P<end_s>\d{2}),"
    r"(?P<end_ms>\d{3})"
)


def srt_cue_midpoints(path: Path) -> list[float]:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    midpoints = []
    for match in SRT_CUE_RE.finditer(text):
        start = (
            int(match.group("start_h")) * 3600
            + int(match.group("start_m")) * 60
            + int(match.group("start_s"))
            + int(match.group("start_ms")) / 1000
        )
        end = (
            int(match.group("end_h")) * 3600
            + int(match.group("end_m")) * 60
            + int(match.group("end_s"))
            + int(match.group("end_ms")) / 1000
        )
        if end > start:
            midpoints.append((start + end) / 2)
    return midpoints


def evenly_sample(values: list[float], count: int) -> list[float]:
    if count <= 0 or len(values) <= count:
        return values
    if count == 1:
        return [values[len(values) // 2]]
    indices = {
        round(index * (len(values) - 1) / (count - 1))
        for index in range(count)
    }
    return [values[index] for index in sorted(indices)]


def subtitle_frame_difference(
    no_subtitles: Path,
    subtitles: Path,
    timestamp_sec: float,
) -> tuple[float | None, str]:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-v",
        "error",
        "-ss",
        f"{timestamp_sec:.6f}",
        "-i",
        str(no_subtitles),
        "-ss",
        f"{timestamp_sec:.6f}",
        "-i",
        str(subtitles),
        "-filter_complex",
        (
            "[0:v][1:v]blend=all_mode=difference,"
            "format=gray,signalstats,metadata=print:file=-"
        ),
        "-frames:v",
        "1",
        "-f",
        "null",
        os.devnull,
    ]
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    output = "\n".join(part for part in (result.stdout, result.stderr) if part)
    matches = re.findall(r"lavfi\.signalstats\.YAVG=([0-9.]+)", output)
    if result.returncode != 0 or not matches:
        return None, (result.stderr or result.stdout).strip()[-4000:]
    return max(float(value) for value in matches), ""


def audit_subtitle_burn_row(
    row: dict,
    max_samples: int,
    difference_threshold: float,
) -> dict:
    no_subtitles = Path(row.get("no_subtitles_input", ""))
    subtitles = Path(row.get("subtitle_edition_input", ""))
    event_dir = subtitles.parent
    srt_candidates = sorted(event_dir.glob("*.srt"))
    result = {
        "event_name": row.get("event_name", ""),
        "canvas": row.get("canvas", ""),
        "no_subtitles_input": str(no_subtitles),
        "subtitle_input": str(subtitles),
        "srt_path": str(srt_candidates[0]) if srt_candidates else "",
        "cue_count": 0,
        "sample_count": 0,
        "sample_times_sec": "",
        "sample_yavg_differences": "",
        "max_yavg_difference": "",
        "difference_threshold": f"{difference_threshold:.6f}",
        "subtitle_visual_change_ok": "no",
        "error": "",
    }
    if not no_subtitles.exists() or not subtitles.exists():
        result["error"] = "video input missing"
        return result
    if not srt_candidates:
        result["error"] = "SRT missing"
        return result
    try:
        midpoints = srt_cue_midpoints(srt_candidates[0])
    except OSError as exc:
        result["error"] = str(exc)
        return result
    result["cue_count"] = len(midpoints)
    samples = evenly_sample(midpoints, max_samples)
    result["sample_count"] = len(samples)
    result["sample_times_sec"] = ";".join(f"{value:.6f}" for value in samples)
    if not samples:
        result["error"] = "no valid SRT cues"
        return result

    differences = []
    errors = []
    for timestamp in samples:
        difference, error = subtitle_frame_difference(
            no_subtitles,
            subtitles,
            timestamp,
        )
        if difference is not None:
            differences.append(difference)
        if error:
            errors.append(error)
    result["sample_yavg_differences"] = ";".join(
        f"{value:.6f}" for value in differences
    )
    if differences:
        maximum = max(differences)
        result["max_yavg_difference"] = f"{maximum:.6f}"
        result["subtitle_visual_change_ok"] = (
            "yes" if maximum >= difference_threshold else "no"
        )
    if errors:
        result["error"] = " | ".join(errors)[-4000:]
    return result


def command_subtitle_burn_audit(args):
    sequence_rows = [
        row
        for row in read_csv(Path(args.sequence_csv))
        if (parse_optional_int(row.get("subtitle_count")) or 0) > 0
    ]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = [
            executor.submit(
                audit_subtitle_burn_row,
                row,
                args.max_samples,
                args.difference_threshold,
            )
            for row in sequence_rows
        ]
        for completed, future in enumerate(as_completed(futures), start=1):
            rows.append(future.result())
            if completed % 25 == 0 or completed == len(futures):
                print(
                    f"[subtitle-burn-audit] processed "
                    f"{completed}/{len(futures)}"
                )
    rows.sort(
        key=lambda row: (
            natural_key(row.get("event_name", "")),
            natural_key(row.get("canvas", "")),
        )
    )
    audit_path = out_dir / "subtitle_burn_audit.csv"
    write_csv(
        audit_path,
        rows,
        list(rows[0].keys()) if rows else [],
    )
    failures = sum(
        row["subtitle_visual_change_ok"] != "yes" for row in rows
    )
    errors = sum(bool(row["error"]) for row in rows)
    values = [
        parse_optional_float(row.get("max_yavg_difference"))
        for row in rows
    ]
    values = [value for value in values if value is not None]
    summary_path = out_dir / "subtitle_burn_audit_summary.md"
    summary_path.write_text(
        "\n".join(
            [
                "# Subtitle Burn Audit",
                "",
                f"Subtitle event/canvas rows: {len(rows)}",
                f"Visual-change failures: {failures}",
                f"Probe errors: {errors}",
                (
                    "Minimum maximum cue-frame difference: "
                    f"{min(values):.6f}"
                    if values
                    else "Minimum maximum cue-frame difference: unavailable"
                ),
                (
                    "Maximum maximum cue-frame difference: "
                    f"{max(values):.6f}"
                    if values
                    else "Maximum maximum cue-frame difference: unavailable"
                ),
                f"Acceptance threshold: {args.difference_threshold:.6f}",
                "",
                (
                    "Frames are compared at evenly selected SRT cue midpoints. "
                    "The metric is the mean luma value of the absolute "
                    "subtitle/no-subtitle frame difference."
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"[subtitle-burn-audit] wrote {audit_path}")
    print(f"[subtitle-burn-audit] wrote {summary_path}")


def rebuild_official_audio_for_video(job: dict, args) -> dict:
    source = Path(job["source"])
    output = Path(job["output"])
    audio_manifest = source.parent / "official_audio_mix_manifest.csv"
    row = {
        **job,
        "audio_manifest": str(audio_manifest),
        "audio_track_count": 0,
        "status": "",
        "duration_sec": "",
        "max_volume_db": "",
        "peak_safe": "",
        "output_size_bytes": "",
        "error": "",
    }
    if output.exists() and not args.overwrite:
        row["status"] = "exists"
        return row
    if not source.exists():
        row["status"] = "missing_source"
        row["error"] = str(source)
        return row
    audio_rows = [
        audio_row
        for audio_row in read_csv(audio_manifest)
        if audio_row.get("ogg_path")
        and Path(audio_row["ogg_path"]).exists()
    ]
    row["audio_track_count"] = len(audio_rows)
    if not audio_rows:
        row["status"] = "missing_official_audio"
        row["error"] = str(audio_manifest)
        return row
    if not args.execute:
        row["status"] = "dry_run"
        return row

    probe = probe_mp4(source)
    duration = parse_optional_float(probe.get("duration_sec"))
    if (
        not probe.get("probe_ok")
        or not probe.get("has_video")
        or duration is None
        or duration <= 0
    ):
        row["status"] = "invalid_source"
        row["error"] = probe.get("probe_error", "invalid source streams")
        return row

    output.parent.mkdir(parents=True, exist_ok=True)
    temp_output = output.with_name(f"{output.stem}__audio_rebuild_tmp.mp4")
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-nostats",
        "-v",
        "error",
        "-i",
        str(source),
    ]
    for audio_row in audio_rows:
        cmd.extend(["-i", audio_row["ogg_path"]])
    filters = []
    labels = []
    for index, audio_row in enumerate(audio_rows, start=1):
        start_ms = parse_optional_int(audio_row.get("start_ms")) or 0
        label = f"a{index}"
        filters.append(
            f"[{index}:a]adelay={start_ms}|{start_ms},"
            "aresample=48000,"
            "aformat=sample_fmts=fltp:sample_rates=48000:"
            f"channel_layouts=stereo[{label}]"
        )
        labels.append(label)
    if len(labels) == 1:
        mixed_label = labels[0]
    else:
        mixed_label = "amixout"
        filters.append(
            "".join(f"[{label}]" for label in labels)
            + f"amix=inputs={len(labels)}:duration=longest:"
            "normalize=0:dropout_transition=0[amixout]"
        )
    filters.append(
        f"[{mixed_label}]"
        f"alimiter=limit={args.limiter_limit:.6f}:"
        "level=disabled:attack=5:release=50,"
        f"volume={args.output_gain_db:.3f}dB,"
        f"apad=whole_dur={duration:.6f}[afinal]"
    )
    cmd.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "0:v:0",
            "-map",
            "[afinal]",
            "-map_metadata",
            "0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            args.audio_bitrate,
            "-ar",
            "48000",
            "-ac",
            "2",
            "-t",
            f"{duration:.6f}",
            "-movflags",
            "+faststart",
            str(temp_output),
        ]
    )
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        row["status"] = "failed"
        row["error"] = (result.stderr or result.stdout).strip()[-4000:]
        if temp_output.exists():
            temp_output.unlink()
        return row
    temp_output.replace(output)
    volume = probe_audio_volume(output)
    max_volume = volume.pop("max_volume_value")
    output_probe = probe_mp4(output)
    row.update(
        {
            "status": (
                "ok"
                if output_probe.get("probe_ok")
                and output_probe.get("has_video")
                and output_probe.get("has_audio")
                else "invalid_output"
            ),
            "duration_sec": output_probe.get("duration_sec", ""),
            "max_volume_db": volume.get("max_volume_db", ""),
            "peak_safe": (
                "yes"
                if max_volume is not None and max_volume <= args.max_peak_db
                else "no"
            ),
            "output_size_bytes": output.stat().st_size,
            "error": volume.get("audio_volume_error", "")[-4000:],
        }
    )
    return row


def command_rebuild_event_audio(args):
    sequence_rows = read_csv(Path(args.sequence_csv))
    out_dir = Path(args.out_dir).resolve()
    event_tree_root = (out_dir / "events").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    editions = (
        ["no-subtitles", "subtitles"]
        if args.edition == "both"
        else [args.edition]
    )
    jobs_by_output = {}
    for sequence_row in sequence_rows:
        event_name = sequence_row.get("event_name", "")
        event_root = sequence_row.get("event_root", "")
        canvas = sequence_row.get("canvas", "")
        event_dir = (
            event_tree_root
            / safe_name(event_root)
            / f"{safe_name(event_name)}__{safe_name(canvas)}"
        ).resolve()
        if not event_dir.is_relative_to(event_tree_root):
            raise ValueError("resolved audio rebuild output escaped output root")
        for edition in editions:
            source_field = (
                "no_subtitles_input"
                if edition == "no-subtitles"
                else "subtitle_edition_input"
            )
            source = Path(sequence_row.get(source_field, ""))
            output = event_dir / source.name
            jobs_by_output[str(output).lower()] = {
                "event_name": event_name,
                "event_root": event_root,
                "canvas": canvas,
                "edition": edition,
                "source": str(source),
                "output": str(output),
            }
    jobs = sorted(
        jobs_by_output.values(),
        key=lambda job: (
            natural_key(job["event_root"]),
            natural_key(job["event_name"]),
            natural_key(job["canvas"]),
            job["edition"],
        ),
    )
    if args.limit > 0:
        jobs = jobs[: args.limit]
    print(f"[rebuild-event-audio] jobs: {len(jobs)}")

    rows = []
    manifest_path = out_dir / "event_audio_rebuild.csv"
    fields = [
        "event_name",
        "event_root",
        "canvas",
        "edition",
        "source",
        "output",
        "audio_manifest",
        "audio_track_count",
        "status",
        "duration_sec",
        "max_volume_db",
        "peak_safe",
        "output_size_bytes",
        "error",
    ]
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = [
            executor.submit(rebuild_official_audio_for_video, job, args)
            for job in jobs
        ]
        for completed, future in enumerate(as_completed(futures), start=1):
            rows.append(future.result())
            if completed % 100 == 0 or completed == len(futures):
                write_csv(manifest_path, rows, fields)
                print(
                    f"[rebuild-event-audio] processed {completed}/{len(futures)}"
                )
    rows.sort(
        key=lambda row: (
            natural_key(row["event_root"]),
            natural_key(row["event_name"]),
            natural_key(row["canvas"]),
            row["edition"],
        )
    )
    write_csv(manifest_path, rows, fields)
    counts = Counter(row["status"] for row in rows)
    unsafe = sum(
        row["status"] in {"ok", "exists"} and row["peak_safe"] == "no"
        for row in rows
    )
    summary_path = out_dir / "event_audio_rebuild_summary.md"
    summary_path.write_text(
        "\n".join(
            [
                "# Event Audio Rebuild",
                "",
                f"Jobs: {len(rows)}",
                f"Editions: {', '.join(editions)}",
                f"Limiter ceiling: {args.limiter_limit:.6f}",
                f"Post-limiter output gain: {args.output_gain_db:.3f} dB",
                f"Maximum accepted decoded peak: {args.max_peak_db:.2f} dBFS",
                f"Unsafe decoded peaks: {unsafe}",
                f"Execute: {'yes' if args.execute else 'no'}",
                "",
                "## Status",
                *[f"- {key}: {value}" for key, value in sorted(counts.items())],
                "",
                "Video streams are copied without re-encoding. Audio is rebuilt from the official OGG manifest.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"[rebuild-event-audio] status: {dict(counts)}")
    print(f"[rebuild-event-audio] wrote {manifest_path}")
    print(f"[rebuild-event-audio] wrote {summary_path}")


def command_build_event_dgm_batch(args):
    production_plan_csv = Path(args.production_plan_csv)
    event_map_csv = Path(args.event_map_csv)
    subtitle_timeline_csv = Path(args.subtitle_timeline_csv)
    event_audio_components_csv = Path(args.event_audio_components_csv)
    audio_signal_audit = load_audio_signal_audit(
        Path(args.audio_signal_audit_csv)
        if args.audio_signal_audit_csv
        else None
    )
    out_dir = Path(args.out_dir).resolve()
    event_out_root = out_dir / "events"
    input_root = out_dir / "batch_inputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    plan_rows = read_csv(production_plan_csv)
    selected = []
    selected_categories = set(args.category or [])
    selected_roots = {value.lower() for value in args.event_root or []}
    selected_events = {value.lower() for value in args.event_name or []}
    selected_canvases = {value.lower() for value in args.canvas or []}
    for row in plan_rows:
        if selected_categories and row.get("category") not in selected_categories:
            continue
        if selected_roots and row.get("event_root", "").lower() not in selected_roots:
            continue
        if selected_events and row.get("event_name", "").lower() not in selected_events:
            continue
        if selected_canvases and row.get("canvas", "").lower() not in selected_canvases:
            continue
        if args.require_audio and parse_optional_int(
            row.get("official_audio_track_count")
        ) in {None, 0}:
            continue
        if args.only_subtitles and parse_optional_int(row.get("subtitle_count")) in {
            None,
            0,
        }:
            continue
        if args.skip_mixed_canvas and row.get("mixed_canvas_event") == "yes":
            continue
        selected.append(row)
    selected.sort(
        key=lambda row: (
            natural_key(row.get("event_root", "")),
            natural_key(row.get("event_name", "")),
            parse_optional_int(row.get("canvas_width")) or 0,
            parse_optional_int(row.get("canvas_height")) or 0,
        )
    )
    start_index = max(0, args.start_index)
    selected = selected[start_index:]
    if args.limit > 0:
        selected = selected[: args.limit]

    all_event_rows = read_csv(event_map_csv)
    event_fields = list(all_event_rows[0].keys()) if all_event_rows else []
    event_rows_by_name_canvas: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in all_event_rows:
        if row.get("cri_match") != "yes":
            continue
        width = parse_optional_int(row.get("z2d_canvas_width"))
        height = parse_optional_int(row.get("z2d_canvas_height"))
        if width is None or height is None:
            continue
        event_rows_by_name_canvas[
            (row.get("event_name", "").lower(), f"{width}x{height}")
        ].append(row)

    all_subtitle_rows = read_csv(subtitle_timeline_csv)
    subtitle_fields = (
        list(all_subtitle_rows[0].keys()) if all_subtitle_rows else []
    )
    subtitle_rows_by_event: dict[str, list[dict]] = defaultdict(list)
    for row in all_subtitle_rows:
        if row.get("ogg_path") and not audio_path_is_audible(
            row["ogg_path"], audio_signal_audit
        ):
            continue
        subtitle_rows_by_event[row.get("event_name", "").lower()].append(row)

    all_audio_rows = read_csv(event_audio_components_csv)
    audio_fields = list(all_audio_rows[0].keys()) if all_audio_rows else []
    audio_rows_by_event: dict[str, list[dict]] = defaultdict(list)
    for row in all_audio_rows:
        if row.get("ogg_path") and not audio_path_is_audible(
            row["ogg_path"], audio_signal_audit
        ):
            continue
        audio_rows_by_event[row.get("primary_animation", "").lower()].append(row)

    manifest_rows = []
    manifest_path = out_dir / "event_batch_build.csv"
    manifest_fields = [
        "batch_index",
        "event_name",
        "event_root",
        "canvas",
        "category",
        "output_duration_sec",
        "official_audio_track_count",
        "subtitle_count",
        "output_dir",
        "no_subtitles_path",
        "subtitles_burned_path",
        "status",
        "output_size_bytes",
        "error",
    ]
    for batch_index, plan_row in enumerate(selected, start=start_index):
        event_name = plan_row["event_name"]
        event_key = event_name.lower()
        canvas = plan_row["canvas"].lower()
        source_event_rows = event_rows_by_name_canvas.get((event_key, canvas), [])
        event_root = plan_row.get("event_root") or event_name.rsplit("_", 1)[0]
        event_dir_name = f"{safe_name(event_name)}__{safe_name(canvas)}"
        output_dir = (event_out_root / safe_name(event_root) / event_dir_name).resolve()
        input_dir = (input_root / safe_name(event_root) / event_dir_name).resolve()
        if not output_dir.is_relative_to(out_dir) or not input_dir.is_relative_to(
            out_dir
        ):
            raise ValueError("resolved batch output escaped the requested output root")
        output_dir.mkdir(parents=True, exist_ok=True)
        input_dir.mkdir(parents=True, exist_ok=True)

        no_subtitles_candidates = sorted(output_dir.glob("*__no_subtitles.mp4"))
        subtitles_candidates = sorted(output_dir.glob("*__subtitles_burned.mp4"))
        status = "planned"
        error = ""
        if no_subtitles_candidates and not args.overwrite:
            status = "exists"
        elif not source_event_rows:
            status = "missing_event_canvas_rows"
            error = f"no exact event rows for {event_name} {canvas}"
        else:
            event_input = input_dir / "event_map.csv"
            subtitle_input = input_dir / "subtitle_timeline.csv"
            audio_input = input_dir / "event_audio_components.csv"
            write_csv(event_input, source_event_rows, event_fields)
            write_csv(
                subtitle_input,
                subtitle_rows_by_event.get(event_key, []),
                subtitle_fields,
            )
            write_csv(
                audio_input,
                audio_rows_by_event.get(event_key, []),
                audio_fields,
            )
            composite_args = argparse.Namespace(
                event_map_csv=str(event_input),
                subtitle_timeline_csv=str(subtitle_input),
                event_audio_components_csv=str(audio_input),
                audio_signal_audit_csv="",
                event_name=event_name,
                out_dir=str(output_dir),
                canvas_select=canvas,
                frame_rate=args.frame_rate,
                canvas_width=0,
                canvas_height=0,
                black_similarity=args.black_similarity,
                black_blend=args.black_blend,
                layer_eof_policy=args.layer_eof_policy,
                encoder=args.encoder,
                crf=args.crf,
                cq=args.cq,
                burn_subtitles=(
                    args.burn_subtitles
                    and (parse_optional_int(plan_row.get("subtitle_count")) or 0) > 0
                ),
                subtitle_font_name=args.subtitle_font_name,
                subtitle_font_size=args.subtitle_font_size,
                subtitle_margin_v=args.subtitle_margin_v,
                execute=args.execute,
                overwrite=args.overwrite,
            )
            try:
                composite_result = command_build_event_dgm_composite(composite_args)
                no_subtitles_candidates = sorted(
                    output_dir.glob("*__no_subtitles.mp4")
                )
                subtitles_candidates = sorted(
                    output_dir.glob("*__subtitles_burned.mp4")
                )
                if args.execute:
                    status = composite_result["status"]
                    error = composite_result.get("error", "")
                    if status == "ok" and not no_subtitles_candidates:
                        status = "missing_output"
                        error = "compositor reported success without an output file"
                else:
                    status = "planned"
                if (
                    status == "ok"
                    and args.cleanup_layers
                    and no_subtitles_candidates
                ):
                    for layer_dir in output_dir.glob("official_dgm_layers_*"):
                        resolved_layer_dir = layer_dir.resolve()
                        if (
                            resolved_layer_dir.is_dir()
                            and resolved_layer_dir.is_relative_to(output_dir)
                        ):
                            shutil.rmtree(resolved_layer_dir)
            except Exception as exc:
                status = "failed"
                error = str(exc)

        no_subtitles_path = (
            str(no_subtitles_candidates[0]) if no_subtitles_candidates else ""
        )
        subtitles_path = (
            str(subtitles_candidates[0]) if subtitles_candidates else ""
        )
        output_size_bytes = sum(
            path.stat().st_size
            for path in no_subtitles_candidates + subtitles_candidates
            if path.exists()
        )
        manifest_rows.append(
            {
                "batch_index": batch_index,
                "event_name": event_name,
                "event_root": event_root,
                "canvas": canvas,
                "category": plan_row.get("category", ""),
                "output_duration_sec": plan_row.get("output_duration_sec", ""),
                "official_audio_track_count": plan_row.get(
                    "official_audio_track_count", ""
                ),
                "subtitle_count": plan_row.get("subtitle_count", ""),
                "output_dir": str(output_dir),
                "no_subtitles_path": no_subtitles_path,
                "subtitles_burned_path": subtitles_path,
                "status": status,
                "output_size_bytes": output_size_bytes,
                "error": error,
            }
        )
        write_csv(manifest_path, manifest_rows, manifest_fields)
        print(
            f"[build-event-dgm-batch] {len(manifest_rows)}/{len(selected)} "
            f"{event_name} {canvas}: {status}"
        )

    counts = Counter(row["status"] for row in manifest_rows)
    summary_path = out_dir / "event_batch_build_summary.md"
    lines = [
        "# Event DGM Batch Build",
        "",
        f"Selected event/canvas rows: {len(selected)}",
        f"Execute: {'yes' if args.execute else 'no'}",
        f"Burn subtitles when available: {'yes' if args.burn_subtitles else 'no'}",
        f"Cleanup generated layer intermediates: {'yes' if args.cleanup_layers else 'no'}",
        f"Output bytes: {sum(int(row['output_size_bytes']) for row in manifest_rows)}",
        "",
        "## Status",
    ]
    for key, value in sorted(counts.items()):
        lines.append(f"- {key}: {value}")
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[build-event-dgm-batch] status: {dict(counts)}")
    print(f"[build-event-dgm-batch] wrote {manifest_path}")
    print(f"[build-event-dgm-batch] wrote {summary_path}")


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
        (
            "format=duration:"
            "stream=index,codec_type,codec_name,width,height,duration,"
            "r_frame_rate,avg_frame_rate,sample_rate,channels"
        ),
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
        "frame_rate": video.get("r_frame_rate", ""),
        "average_frame_rate": video.get("avg_frame_rate", ""),
        "audio_sample_rate": audio.get("sample_rate", ""),
        "audio_channels": audio.get("channels", ""),
    }


def probe_audio_volume(path: Path) -> dict:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-v",
        "info",
        "-i",
        str(path),
        "-vn",
        "-af",
        "volumedetect",
        "-f",
        "null",
        os.devnull,
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    output = "\n".join(part for part in (result.stdout, result.stderr) if part)
    mean_match = re.search(r"mean_volume:\s*(-?(?:inf|\d+(?:\.\d+)?))\s*dB", output, re.IGNORECASE)
    max_match = re.search(r"max_volume:\s*(-?(?:inf|\d+(?:\.\d+)?))\s*dB", output, re.IGNORECASE)

    def parse_db(match: re.Match | None) -> float | None:
        if not match:
            return None
        value = match.group(1).lower()
        if value == "-inf":
            return float("-inf")
        if value == "inf":
            return float("inf")
        return float(value)

    mean_volume = parse_db(mean_match)
    max_volume = parse_db(max_match)
    return {
        "audio_volume_ok": result.returncode == 0 and max_volume is not None,
        "audio_volume_error": "" if result.returncode == 0 else (result.stderr or result.stdout).strip(),
        "mean_volume_db": "" if mean_volume is None else f"{mean_volume:.1f}",
        "max_volume_db": "" if max_volume is None else f"{max_volume:.1f}",
        "max_volume_value": max_volume,
    }


def load_audio_signal_audit(path: Path | None) -> dict[str, dict]:
    if path is None or not path.exists():
        return {}
    result = {}
    for row in read_csv(path):
        keys = {
            Path(row.get("path", "")).name.lower(),
            Path(row.get("relative_path", "")).name.lower(),
        }
        for key in keys:
            if key:
                result[key] = row
    return result


def audio_path_is_audible(path: str | Path, audit_by_name: dict[str, dict]) -> bool:
    if not audit_by_name:
        return True
    row = audit_by_name.get(Path(path).name.lower())
    return bool(row and row.get("audible") == "yes")


def command_audio_signal_audit(args):
    input_dir = Path(args.input_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    audit_path = out_dir / "audio_signal_audit.csv"
    extensions = {
        value.lower() if value.startswith(".") else f".{value.lower()}"
        for value in args.extension
    }
    paths = sorted(
        [
            path
            for path in input_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in extensions
        ],
        key=lambda path: natural_key(str(path.relative_to(input_dir))),
    )
    existing = {
        row.get("relative_path", "").lower(): row
        for row in read_csv(audit_path)
        if row.get("relative_path")
    }
    rows_by_relative: dict[str, dict] = {}
    pending = []
    for path in paths:
        relative = str(path.relative_to(input_dir))
        stat = path.stat()
        cached = existing.get(relative.lower())
        if (
            cached
            and parse_optional_int(cached.get("size_bytes")) == stat.st_size
            and parse_optional_int(cached.get("mtime_ns")) == stat.st_mtime_ns
            and cached.get("status") == "ok"
        ):
            rows_by_relative[relative.lower()] = cached
        else:
            pending.append(path)

    fields = [
        "path",
        "relative_path",
        "size_bytes",
        "mtime_ns",
        "probe_ok",
        "codec",
        "sample_rate",
        "channels",
        "duration_sec",
        "mean_volume_db",
        "max_volume_db",
        "audible",
        "classification",
        "threshold_db",
        "status",
        "error",
    ]

    def inspect(path: Path) -> dict:
        relative = str(path.relative_to(input_dir))
        stat = path.stat()
        stream = probe_audio_stream(path)
        volume = probe_audio_volume(path)
        max_volume = volume.pop("max_volume_value")
        ok = stream.get("probe_ok") == "yes" and volume["audio_volume_ok"]
        audible = bool(max_volume is not None and max_volume > args.threshold_db)
        return {
            "path": str(path),
            "relative_path": relative,
            "size_bytes": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "probe_ok": stream.get("probe_ok", ""),
            "codec": stream.get("codec", ""),
            "sample_rate": stream.get("sample_rate", ""),
            "channels": stream.get("channels", ""),
            "duration_sec": stream.get("duration_sec", ""),
            "mean_volume_db": volume.get("mean_volume_db", ""),
            "max_volume_db": volume.get("max_volume_db", ""),
            "audible": "yes" if ok and audible else "no",
            "classification": (
                "audible"
                if ok and audible
                else "silent_or_control"
                if ok
                else "probe_failed"
            ),
            "threshold_db": args.threshold_db,
            "status": "ok" if ok else "failed",
            "error": first_nonempty(
                stream.get("probe_error", ""),
                volume.get("audio_volume_error", ""),
            ),
        }

    completed = 0
    if pending:
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
            future_map = {executor.submit(inspect, path): path for path in pending}
            for future in as_completed(future_map):
                path = future_map[future]
                relative = str(path.relative_to(input_dir))
                try:
                    row = future.result()
                except Exception as exc:
                    stat = path.stat()
                    row = {
                        "path": str(path),
                        "relative_path": relative,
                        "size_bytes": stat.st_size,
                        "mtime_ns": stat.st_mtime_ns,
                        "probe_ok": "no",
                        "codec": "",
                        "sample_rate": "",
                        "channels": "",
                        "duration_sec": "",
                        "mean_volume_db": "",
                        "max_volume_db": "",
                        "audible": "no",
                        "classification": "probe_failed",
                        "threshold_db": args.threshold_db,
                        "status": "failed",
                        "error": str(exc),
                    }
                rows_by_relative[relative.lower()] = row
                completed += 1
                if completed % 250 == 0:
                    current_rows = sorted(
                        rows_by_relative.values(),
                        key=lambda row: natural_key(row["relative_path"]),
                    )
                    write_csv(audit_path, current_rows, fields)
                    print(
                        f"[audio-signal-audit] {completed}/{len(pending)} "
                        f"new files; {len(current_rows)}/{len(paths)} total cached"
                    )

    rows = sorted(
        rows_by_relative.values(),
        key=lambda row: natural_key(row["relative_path"]),
    )
    write_csv(audit_path, rows, fields)
    counts = Counter(row["classification"] for row in rows)
    summary_path = out_dir / "audio_signal_audit_summary.md"
    lines = [
        "# Audio Signal Audit",
        "",
        f"Input: {input_dir}",
        f"Files: {len(paths)}",
        f"Reused cached rows: {len(paths) - len(pending)}",
        f"Peak audibility threshold: {args.threshold_db:.1f} dBFS",
        "",
        "## Classification",
    ]
    for key, value in sorted(counts.items()):
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## Meaning",
            "",
            "- `audible` means decoded peak level is above the configured threshold.",
            "- `silent_or_control` remains in the audit but must not be counted as an audible event soundtrack.",
            "- Matching an EventCn/SMZ request and OGG duration proves identity, not that the resource contains audible samples.",
        ]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[audio-signal-audit] classification: {dict(counts)}")
    print(f"[audio-signal-audit] wrote {audit_path}")
    print(f"[audio-signal-audit] wrote {summary_path}")


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


def sample_video_motion(path: Path, sample_fps: float, max_frames: int) -> dict:
    expected = 64 * 64
    cmd = [
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(path),
        "-vf",
        f"fps={sample_fps},scale=64:64,format=gray",
        "-frames:v",
        str(max_frames),
        "-f",
        "rawvideo",
        "pipe:1",
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        return {
            "motion_ok": False,
            "motion_error": result.stderr.decode("utf-8", errors="ignore").strip(),
            "sampled_frames": 0,
            "avg_frame_diff": "",
            "max_frame_diff": "",
        }

    data = result.stdout
    frame_count = len(data) // expected
    if frame_count <= 0:
        return {
            "motion_ok": False,
            "motion_error": "no sampled frames",
            "sampled_frames": 0,
            "avg_frame_diff": "",
            "max_frame_diff": "",
        }
    frames = [memoryview(data[index * expected : (index + 1) * expected]) for index in range(frame_count)]
    diffs = []
    for before, after in zip(frames, frames[1:]):
        total = 0
        for left, right in zip(before, after):
            total += abs(left - right)
        diffs.append(total / expected)

    if not diffs:
        avg_diff = 0.0
        max_diff = 0.0
    else:
        avg_diff = sum(diffs) / len(diffs)
        max_diff = max(diffs)
    return {
        "motion_ok": True,
        "motion_error": "",
        "sampled_frames": frame_count,
        "avg_frame_diff": f"{avg_diff:.4f}",
        "max_frame_diff": f"{max_diff:.4f}",
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


def review_one_special_video(
    path: Path,
    video_dir: Path,
    out_dir: Path,
    mode: str,
    samples: int,
    audio_volume: bool,
    silent_threshold_db: float,
) -> dict:
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
        "audio_volume_ok": "",
        "audio_volume_error": "",
        "mean_volume_db": "",
        "max_volume_db": "",
        "audible_audio": "",
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
    audible_audio = None
    if audio_volume and has_audio:
        volume = probe_audio_volume(path)
        max_volume = volume.pop("max_volume_value")
        audible_audio = max_volume is not None and max_volume > silent_threshold_db
        row.update(
            {
                **volume,
                "audible_audio": "yes" if audible_audio else "no",
            }
        )

    if has_audio and not has_video:
        row["special_class"] = "audio_only"
        row["review_path"] = place_review_copy(path, out_dir / "audio_only", mode)
        return row

    if not has_video:
        row["special_class"] = "no_video_stream"
        row["review_path"] = place_review_copy(path, out_dir / "no_video_stream", mode)
        return row

    if has_audio and audible_audio is False:
        row["special_class"] = "silent_audio_track"
        row["review_path"] = place_review_copy(path, out_dir / "silent_audio_track", mode)
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


def parse_sound_request_struct_table(
    path: Path,
) -> tuple[tuple[int, ...], list[dict], list[dict], list[dict]]:
    if not path.exists():
        return tuple(), [], [], []
    data = path.read_bytes()
    if len(data) < 64:
        return tuple(), [], [], []
    header = struct.unpack("<16I", data[:64])
    request_count = header[7]
    offset = 64
    request_rows: list[dict] = []
    reqdata_rows: list[dict] = []
    marker_rows: list[dict] = []

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

        for marker_index in range(marker_count):
            marker = data[offset : offset + 0x24]
            marker_time_ms = struct.unpack_from("<I", marker, 0)[0]
            marker_name = decode_fixed_c_string(marker[4:])
            marker_rows.append(
                {
                    "request_id": request_id,
                    "code_name": code_name,
                    "request_offset_hex": f"0x{request_offset:x}",
                    "marker_index": marker_index,
                    "marker_offset_hex": f"0x{offset:x}",
                    "marker_time_ms": marker_time_ms,
                    "marker_name": marker_name,
                    "marker_raw_hex": marker.hex().upper(),
                }
            )
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

    return header, request_rows, reqdata_rows, marker_rows


def command_sound_request_struct_audit(args):
    manifest_dir = Path(args.manifest_dir)
    table_path = Path(args.table_path)
    header, request_rows, reqdata_rows, marker_rows = parse_sound_request_struct_table(table_path)

    request_csv = manifest_dir / "sound_request_struct_requests.csv"
    reqdata_csv = manifest_dir / "sound_request_struct_reqdata.csv"
    marker_csv = manifest_dir / "sound_request_struct_markers.csv"
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
    write_csv(
        marker_csv,
        marker_rows,
        [
            "request_id",
            "code_name",
            "request_offset_hex",
            "marker_index",
            "marker_offset_hex",
            "marker_time_ms",
            "marker_name",
            "marker_raw_hex",
        ],
    )

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
        f"Marker rows parsed: {len(marker_rows)}",
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
    print(f"[sound-request-struct-audit] marker rows: {len(marker_rows)}")
    print(f"[sound-request-struct-audit] unique SMZ media: {len(unique_media)}")
    print(f"[sound-request-struct-audit] wrote {request_csv}")
    print(f"[sound-request-struct-audit] wrote {reqdata_csv}")
    print(f"[sound-request-struct-audit] wrote {marker_csv}")
    print(f"[sound-request-struct-audit] wrote {summary_path}")


def parse_sound_hashreq_records(path: Path) -> tuple[tuple[int, ...], list[dict]]:
    if not path.exists():
        return tuple(), []
    data = path.read_bytes()
    if len(data) < 64:
        return tuple(), []
    header = struct.unpack("<16I", data[:64])
    header_count = header[7]
    if header_count and len(data) >= 64 + header_count * 16:
        record_count = header_count
        record_size = 16
    elif header_count and len(data) >= 64 + header_count * 8:
        record_count = header_count
        record_size = 8
    else:
        record_size = 16 if (len(data) - 64) % 16 == 0 else 8
        record_count = (len(data) - 64) // record_size
    records = []
    for index in range(record_count):
        offset = 64 + index * record_size
        record = data[offset : offset + record_size]
        if len(record) < record_size:
            break
        hash_u64 = struct.unpack_from("<Q", record, 0)[0]
        duration_ms = struct.unpack_from("<I", record, 8)[0] if record_size >= 12 else 0
        tail = struct.unpack_from("<I", record, 12)[0] if record_size >= 16 else 0
        duration_sec = f"{duration_ms / 1000:.6f}" if duration_ms else ""
        records.append(
            {
                "record_index": index,
                "offset_hex": f"0x{offset:x}",
                "record_format_bytes": record_size,
                "hash_le_hex": record[:8].hex().upper(),
                "hash_be_hex": record[:8][::-1].hex().upper(),
                "hash_value_hex": f"0x{hash_u64:016X}",
                "request_id": index,
                "duration_ms_u32": duration_ms,
                "duration_sec": duration_sec,
                # Retained for compatibility with manifests generated before the field was identified.
                "sample_count_u32": duration_ms,
                "duration_sec_at_header_rate": "",
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


def normalize_media_key(value: str) -> str:
    value = value.strip().upper()
    value = re.sub(r"\.(?:SMZ|PCM)$", "", value)
    return value


def c_string_from_blob(blob: bytes, offset: int) -> str:
    if offset < 0 or offset >= len(blob):
        return ""
    end = blob.find(b"\x00", offset)
    if end < 0:
        end = len(blob)
    return blob[offset:end].decode("utf-8", errors="ignore")


def parse_elf_relocated_string_table(lib_path: Path, symbol_name: str) -> list[dict]:
    if not lib_path.exists():
        return []
    data = lib_path.read_bytes()
    if data[:4] != b"\x7fELF" or data[4] != 2 or data[5] != 1:
        return []

    section_offset = struct.unpack_from("<Q", data, 0x28)[0]
    section_entry_size = struct.unpack_from("<H", data, 0x3A)[0]
    section_count = struct.unpack_from("<H", data, 0x3C)[0]
    section_string_index = struct.unpack_from("<H", data, 0x3E)[0]
    sections = []
    for index in range(section_count):
        offset = section_offset + index * section_entry_size
        sh = struct.unpack_from("<IIQQQQIIQQ", data, offset)
        sections.append(
            {
                "index": index,
                "name_offset": sh[0],
                "type": sh[1],
                "addr": sh[3],
                "offset": sh[4],
                "size": sh[5],
                "link": sh[6],
                "entry_size": sh[9],
            }
        )

    section_strings = sections[section_string_index]
    section_string_blob = data[section_strings["offset"] : section_strings["offset"] + section_strings["size"]]
    for section in sections:
        section["name"] = c_string_from_blob(section_string_blob, int(section["name_offset"]))

    def va_to_file_offset(va: int) -> int | None:
        for section in sections:
            if section["type"] == 8:
                continue
            start = int(section["addr"])
            end = start + int(section["size"])
            if start <= va < end:
                return int(section["offset"]) + (va - start)
        program_offset = struct.unpack_from("<Q", data, 0x20)[0]
        program_entry_size = struct.unpack_from("<H", data, 0x36)[0]
        program_count = struct.unpack_from("<H", data, 0x38)[0]
        for index in range(program_count):
            offset = program_offset + index * program_entry_size
            p_type, _flags, p_offset, p_vaddr, _p_paddr, p_filesz, _p_memsz, _align = struct.unpack_from(
                "<IIQQQQQQ", data, offset
            )
            if p_type == 1 and p_vaddr <= va < p_vaddr + p_filesz:
                return p_offset + (va - p_vaddr)
        return None

    dynsym = next((section for section in sections if section.get("name") == ".dynsym"), None)
    rela_dyn = next((section for section in sections if section.get("name") == ".rela.dyn"), None)
    if not dynsym or not rela_dyn or not dynsym["entry_size"] or not rela_dyn["entry_size"]:
        return []
    dynstr = sections[int(dynsym["link"])]
    dynstr_blob = data[dynstr["offset"] : dynstr["offset"] + dynstr["size"]]

    target = None
    for index in range(int(dynsym["size"]) // int(dynsym["entry_size"])):
        offset = int(dynsym["offset"]) + index * int(dynsym["entry_size"])
        st_name, _st_info, _st_other, _st_shndx, st_value, st_size = struct.unpack_from("<IBBHQQ", data, offset)
        if st_name and c_string_from_blob(dynstr_blob, st_name) == symbol_name:
            target = {"value": st_value, "size": st_size}
            break
    if not target:
        return []

    base = int(target["value"])
    size = int(target["size"])
    rows = []
    for _index in range(int(rela_dyn["size"]) // int(rela_dyn["entry_size"])):
        offset = int(rela_dyn["offset"]) + _index * int(rela_dyn["entry_size"])
        r_offset, r_info, r_addend = struct.unpack_from("<QQq", data, offset)
        if not (base <= r_offset < base + size):
            continue
        slot_index = (r_offset - base) // 8
        string_offset = va_to_file_offset(r_addend)
        name = c_string_from_blob(data, string_offset) if string_offset is not None else ""
        rows.append(
            {
                "slot_index": slot_index,
                "reloc_offset_hex": f"0x{r_offset:x}",
                "reloc_type": r_info & 0xFFFFFFFF,
                "name_key": normalize_media_key(name),
                "name_raw": name,
                "string_va_hex": f"0x{r_addend:x}",
            }
        )
    rows.sort(key=lambda row: int(row["slot_index"]))
    return rows


def build_structured_media_counters(reqdata_rows: list[dict]) -> tuple[Counter, Counter, dict[str, list[str]]]:
    smz_counter = Counter()
    pcm_counter = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    for row in reqdata_rows:
        media = row.get("smz_media", "")
        if not media:
            continue
        key = normalize_media_key(media)
        if media.upper().endswith(".PCM"):
            pcm_counter[key] += 1
        else:
            smz_counter[key] += 1
        if len(examples[key]) < 5:
            examples[key].append(f"{row.get('request_id', '')}:{row.get('code_name', '')}")
    return smz_counter, pcm_counter, examples


def build_media_name_chunk_rows(name_rows: list[dict], chunk_rows: list[dict], request_counter: Counter) -> list[dict]:
    rows = []
    for row in name_rows:
        chunk_index = int(row["slot_index"])
        chunk = chunk_rows[chunk_index] if chunk_index < len(chunk_rows) else {}
        key = row["name_key"]
        rows.append(
            {
                "chunk_index": chunk_index,
                "media_name": row["name_raw"],
                "name_key": key,
                "request_ref_count": request_counter.get(key, 0),
                "present_in_request_table": "yes" if key in request_counter else "no",
                "offset": chunk.get("offset", ""),
                "offset_hex": chunk.get("offset_hex", ""),
                "size": chunk.get("size", ""),
                "field0": chunk.get("field0", ""),
                "field1": chunk.get("field1", ""),
                "field2": chunk.get("field2", ""),
                "field3": chunk.get("field3", ""),
                "field4": chunk.get("field4", ""),
                "field5": chunk.get("field5", ""),
                "field6": chunk.get("field6", ""),
                "field7": chunk.get("field7", ""),
                "channel_guess": chunk.get("channel_guess", ""),
                "string_va_hex": row.get("string_va_hex", ""),
                "reloc_offset_hex": row.get("reloc_offset_hex", ""),
            }
        )
    return rows


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
    structured_request_rows = read_csv(Path(args.sound_request_struct_requests))
    structured_reqdata_rows = read_csv(Path(args.sound_request_struct_reqdata))
    request_by_id: dict[int, list[dict]] = defaultdict(list)
    for row in structured_request_rows:
        request_id = parse_optional_int(row.get("request_id"))
        if request_id is not None:
            request_by_id[request_id].append(row)

    smz_counter, pcm_counter, media_examples = build_structured_media_counters(structured_reqdata_rows)

    header, hash_records = parse_sound_hashreq_records(Path(args.hashreq_table))
    linked_hash_rows = sum(1 for row in hash_records if int(row["request_id"]) in request_by_id)

    hash_rows = []
    for row in hash_records:
        request_id = int(row["request_id"])
        request_info = request_by_id.get(request_id, [{}])[0]
        hash_rows.append(
            row
            | {
                "code_name": request_info.get("code_name", ""),
                "first_smz_media": request_info.get("first_smz_media", ""),
                "reqdata_count": request_info.get("reqdata_count", ""),
                "marker_count": request_info.get("marker_count", ""),
            }
        )

    hash_csv = manifest_dir / "sound_hashreq_records.csv"
    write_csv(
        hash_csv,
        hash_rows,
        [
            "record_index",
            "offset_hex",
            "record_format_bytes",
            "hash_le_hex",
            "hash_be_hex",
            "hash_value_hex",
            "request_id",
            "duration_ms_u32",
            "duration_sec",
            "sample_count_u32",
            "duration_sec_at_header_rate",
            "tail_u32",
            "code_name",
            "first_smz_media",
            "reqdata_count",
            "marker_count",
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

    native_lib = Path(args.native_lib)
    smz_name_rows = parse_elf_relocated_string_table(native_lib, "loadFileSmz")
    pcm_name_rows = parse_elf_relocated_string_table(native_lib, "loadFilePcm")
    smz_name_chunk_rows = build_media_name_chunk_rows(smz_name_rows, smz_rows, smz_counter)
    smz_name_chunk_csv = manifest_dir / "smz_name_chunk_map.csv"
    write_csv(
        smz_name_chunk_csv,
        smz_name_chunk_rows,
        [
            "chunk_index",
            "media_name",
            "name_key",
            "request_ref_count",
            "present_in_request_table",
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
            "string_va_hex",
            "reloc_offset_hex",
        ],
    )
    pcm_name_csv = manifest_dir / "pcm_name_table.csv"
    pcm_name_table_rows = build_media_name_chunk_rows(pcm_name_rows, [], pcm_counter)
    write_csv(
        pcm_name_csv,
        pcm_name_table_rows,
        [
            "chunk_index",
            "media_name",
            "name_key",
            "request_ref_count",
            "present_in_request_table",
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
            "string_va_hex",
            "reloc_offset_hex",
        ],
    )

    smz_name_keys = {row["name_key"] for row in smz_name_rows}
    pcm_name_keys = {row["name_key"] for row in pcm_name_rows}
    request_smz_keys = set(smz_counter)
    request_pcm_keys = set(pcm_counter)
    request_only_keys = sorted(request_smz_keys - smz_name_keys)
    installed_only_keys = sorted(smz_name_keys - request_smz_keys)
    missing_rows = [
        {
            "smz_media": f"{key}.smz",
            "request_ref_count": smz_counter[key],
            "request_examples": ";".join(media_examples.get(key, [])),
        }
        for key in request_only_keys
    ]
    missing_csv = manifest_dir / "smz_request_missing_from_installed_pack.csv"
    write_csv(missing_csv, missing_rows, ["smz_media", "request_ref_count", "request_examples"])

    channel_counts = Counter(str(row.get("channel_guess", "")) for row in smz_rows)
    size_values = [int(row["size"]) for row in smz_rows]
    sample_counts = [int(row["sample_count_u32"]) for row in hash_rows if str(row.get("sample_count_u32", "")).isdigit()]

    summary_path = manifest_dir / "sound_media_summary.md"
    lines = [
        "# Sound Media Audit Summary",
        "",
        f"Structured request table: {args.sound_request_struct_requests}",
        f"Structured ReqData table: {args.sound_request_struct_reqdata}",
        f"Hash request table: {args.hashreq_table}",
        f"Native library: {native_lib}",
        "",
        "## Structured request media references",
        f"- unique SMZ names in ReqData: {len(smz_counter)}",
        f"- total SMZ references in ReqData: {sum(smz_counter.values())}",
        f"- unique PCM names in ReqData: {len(pcm_counter)}",
        f"- total PCM references in ReqData: {sum(pcm_counter.values())}",
        "",
        "## zg_snd_hashreq_tbl.bin",
        f"- header_u32: {list(header)}",
        f"- hash request rows: {len(hash_records)}",
        f"- hash rows linked by record index to structured requests: {linked_hash_rows}",
        f"- record format bytes: {hash_records[0]['record_format_bytes'] if hash_records else ''}",
        f"- rows with nonzero sample_count_u32: {sum(1 for row in hash_rows if int(row['sample_count_u32']))}",
        f"- rows with nonzero tail_u32: {sum(1 for row in hash_records if int(row['tail_u32']))}",
    ]
    if sample_counts:
        lines.append(f"- sample_count_u32 min/max: {min(sample_counts)} / {max(sample_counts)}")
    lines.extend(["", "## SMZ installed pack"])
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
            "## Runtime media name tables",
            f"- loadFileSmz relocated names: {len(smz_name_rows)}",
            f"- loadFilePcm relocated names: {len(pcm_name_rows)}",
            f"- SMZ request names present in installed runtime table: {len(request_smz_keys & smz_name_keys)}",
            f"- SMZ request names missing from installed runtime table: {len(request_only_keys)}",
            f"- SMZ runtime names not referenced by structured ReqData: {len(installed_only_keys)}",
            f"- PCM request names present in runtime table: {len(request_pcm_keys & pcm_name_keys)}",
            f"- PCM request names missing from runtime table: {len(request_pcm_keys - pcm_name_keys)}",
            f"- SMZ name/chunk CSV: {smz_name_chunk_csv}",
            f"- SMZ request-only CSV: {missing_csv}",
            f"- PCM name table CSV: {pcm_name_csv}",
        ]
    )
    lines.extend(
        [
            "",
            "## Limits",
            "- `zg_snd_hashreq_tbl.bin` records are aligned by request index; the third u32 is not a request id.",
            "- `loadFileSmz` proves the official name-to-chunk order for installed SMZ assets, but it does not decode audio by itself.",
            "- `.smz` chunks are not directly accepted by ffprobe; decoding still requires format work or game decoder behavior.",
            "- This audit does not prove video-to-audio timing; it only improves the sound media/request side of the map.",
        ]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[sound-media-audit] structured smz media: {len(smz_counter)}")
    print(f"[sound-media-audit] structured pcm media: {len(pcm_counter)}")
    print(f"[sound-media-audit] hash request rows: {len(hash_records)}")
    print(f"[sound-media-audit] wrote {hash_csv}")
    if smz_rows:
        print(f"[sound-media-audit] wrote {smz_csv}")
    print(f"[sound-media-audit] wrote {smz_name_chunk_csv}")
    print(f"[sound-media-audit] wrote {missing_csv}")
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
    for class_dir in (
        "audio_only",
        "silent_audio_track",
        "blackish_video",
        "mostly_black_video",
        "no_video_stream",
        "probe_failed",
    ):
        (out_dir / class_dir).mkdir(parents=True, exist_ok=True)
    print(f"[review-special-videos] scanning {len(files)} MP4 files")
    print(f"[review-special-videos] review dir: {out_dir}")

    rows = []
    processed = 0
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [
            executor.submit(
                review_one_special_video,
                path,
                video_dir,
                out_dir,
                args.mode,
                args.samples,
                args.audio_volume,
                args.silent_threshold_db,
            )
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
            "audio_volume_ok",
            "audio_volume_error",
            "mean_volume_db",
            "max_volume_db",
            "audible_audio",
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
    for class_name in (
        "normal",
        "audio_only",
        "silent_audio_track",
        "blackish_video",
        "mostly_black_video",
        "no_video_stream",
        "probe_failed",
    ):
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
        "- `silent_audio_track` means an audio stream exists but `volumedetect` max volume is at or below the configured threshold.",
        "- `blackish_video` and `mostly_black_video` are based on sampled frame luminance.",
        "- Review files are hardlinked when possible, otherwise copied.",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[review-special-videos] wrote {audit_path}")
    print(f"[review-special-videos] wrote {summary_path}")


def classify_motion_video(row: dict, args) -> str:
    if row.get("probe_ok") != "yes":
        return "probe_failed"
    if row.get("has_video") != "yes":
        return "no_video_stream"

    duration = parse_optional_float(row.get("duration_sec"))
    avg_diff = parse_optional_float(row.get("avg_frame_diff"))
    if duration is not None and duration <= args.very_short_threshold_sec:
        return "very_short"
    if avg_diff is None:
        return "motion_probe_failed"
    if duration is not None and duration <= args.short_threshold_sec and avg_diff <= args.static_threshold:
        return "short_static"
    if duration is not None and duration <= args.short_threshold_sec:
        return "short"
    if avg_diff <= args.static_threshold:
        return "static_like"
    if avg_diff <= args.low_motion_threshold:
        return "low_motion"
    return "normal_motion"


def motion_audit_one(path: Path, video_dir: Path, out_dir: Path, args) -> dict:
    relative_path = str(path.relative_to(video_dir))
    probe = probe_mp4(path)
    row = {
        "relative_path": relative_path,
        "motion_class": "",
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
        "audio_volume_ok": "",
        "audio_volume_error": "",
        "mean_volume_db": "",
        "max_volume_db": "",
        "audible_audio": "",
        "motion_ok": "",
        "motion_error": "",
        "sampled_frames": "",
        "avg_frame_diff": "",
        "max_frame_diff": "",
    }

    if probe.get("probe_ok") and probe.get("has_audio") and args.audio_volume:
        volume = probe_audio_volume(path)
        max_volume = volume.pop("max_volume_value")
        audible_audio = max_volume is not None and max_volume > args.silent_threshold_db
        row.update(
            {
                **volume,
                "audible_audio": "yes" if audible_audio else "no",
            }
        )

    if probe.get("probe_ok") and probe.get("has_video"):
        motion = sample_video_motion(path, args.sample_fps, args.max_frames)
        row.update(
            {
                "motion_ok": "yes" if motion.get("motion_ok") else "no",
                "motion_error": motion.get("motion_error", ""),
                "sampled_frames": motion.get("sampled_frames", ""),
                "avg_frame_diff": motion.get("avg_frame_diff", ""),
                "max_frame_diff": motion.get("max_frame_diff", ""),
            }
        )

    row["motion_class"] = classify_motion_video(row, args)
    if args.collect_review and row["motion_class"] in {
        "very_short",
        "short_static",
        "static_like",
        "low_motion",
        "motion_probe_failed",
        "probe_failed",
        "no_video_stream",
    }:
        target_dir = out_dir / "review" / row["motion_class"] / path.parent.name
        row["review_path"] = place_review_copy(path, target_dir, args.mode)
    return row


def command_motion_audit(args):
    print(
        "[motion-audit] WARNING: deprecated coarse pixel-difference diagnostic; "
        "do not use its folders as static/motion or merge decisions.",
        file=sys.stderr,
    )
    video_dir = Path(args.video_dir)
    out_dir = Path(args.out_dir) if args.out_dir else video_dir / "_motion_audit"
    files = sorted(
        [
            path
            for path in video_dir.rglob("*.mp4")
            if out_dir not in path.parents and "_motion_audit" not in path.parts
        ],
        key=lambda path: natural_key(str(path.relative_to(video_dir))),
    )
    if args.limit:
        files = files[: args.limit]
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[motion-audit] scanning {len(files)} MP4 files")
    print(f"[motion-audit] video dir: {video_dir}")
    print(f"[motion-audit] output dir: {out_dir}")

    rows = []
    processed = 0
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(motion_audit_one, path, video_dir, out_dir, args) for path in files]
        for future in as_completed(futures):
            rows.append(future.result())
            processed += 1
            if processed % 250 == 0 or processed == len(files):
                print(f"[motion-audit] processed {processed}/{len(files)}")

    rows.sort(key=lambda row: natural_key(row["relative_path"]))
    fieldnames = [
        "relative_path",
        "motion_class",
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
        "audio_volume_ok",
        "audio_volume_error",
        "mean_volume_db",
        "max_volume_db",
        "audible_audio",
        "motion_ok",
        "motion_error",
        "sampled_frames",
        "avg_frame_diff",
        "max_frame_diff",
    ]
    audit_path = out_dir / "motion_audit.csv"
    write_csv(audit_path, rows, fieldnames)

    counts = Counter(row["motion_class"] for row in rows)
    resolutions = Counter(f'{row.get("width", "")}x{row.get("height", "")}' for row in rows)
    audio_counts = Counter(row.get("audible_audio", "") or row.get("has_audio", "") for row in rows)
    longest = sorted(
        rows,
        key=lambda row: parse_optional_float(row.get("duration_sec")) or 0.0,
        reverse=True,
    )[:15]
    static_examples = [
        row
        for row in rows
        if row["motion_class"] in {"very_short", "short_static", "static_like", "low_motion"}
    ][:30]

    summary_path = out_dir / "motion_audit_summary.md"
    lines = [
        "# Motion Audit Summary",
        "",
        f"Video dir: {video_dir}",
        f"Scanned MP4 files: {len(rows)}",
        f"Sample FPS: {args.sample_fps}",
        f"Max sampled frames: {args.max_frames}",
        "",
        "## Motion Classes",
    ]
    for key, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {key}: {count}")
    lines.extend(["", "## Resolutions"])
    for key, count in sorted(resolutions.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {key}: {count}")
    lines.extend(["", "## Audio Column Summary"])
    for key, count in sorted(audio_counts.items(), key=lambda item: (item[0], item[1])):
        lines.append(f"- {key or '(not checked)'}: {count}")
    lines.extend(["", "## Longest Files"])
    for row in longest:
        lines.append(
            f"- {row['relative_path']}: {format_seconds(parse_optional_float(row.get('duration_sec')))}s, "
            f"{row.get('width')}x{row.get('height')}, class={row['motion_class']}, "
            f"avg_diff={row.get('avg_frame_diff')}, max_diff={row.get('max_frame_diff')}"
        )
    lines.extend(["", "## Review Examples"])
    for row in static_examples:
        lines.append(
            f"- {row['relative_path']}: {format_seconds(parse_optional_float(row.get('duration_sec')))}s, "
            f"class={row['motion_class']}, avg_diff={row.get('avg_frame_diff')}, "
            f"max_diff={row.get('max_frame_diff')}, audio={row.get('audible_audio') or row.get('has_audio')}"
        )
    lines.extend(
        [
            "",
            "## Class Definitions",
            f"- `very_short`: duration <= {args.very_short_threshold_sec}s.",
            f"- `short_static`: duration <= {args.short_threshold_sec}s and average frame diff <= {args.static_threshold}.",
            f"- `static_like`: longer than short threshold but average frame diff <= {args.static_threshold}.",
            f"- `low_motion`: average frame diff <= {args.low_motion_threshold}.",
            "- `normal_motion`: no short/static/low-motion rule matched.",
            "- Review files are hardlinked when possible, otherwise copied. Source files are not moved.",
        ]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[motion-audit] wrote {audit_path}")
    print(f"[motion-audit] wrote {summary_path}")


def parse_code_name_label(code_name: str) -> dict:
    match = re.match(r"^(?P<code>\d+)(?:_|\s+)?(?P<label>.*)$", code_name or "")
    if not match:
        return {"code": "", "label": code_name or "", "speaker_hint": "", "subtitle_text": ""}

    label = match.group("label")
    speaker_hint = ""
    subtitle_text = ""
    for marker in ("イヴセリフ_", "セリフ_", "台詞_"):
        if marker in label:
            before, after = label.split(marker, 1)
            speaker_hint = before.strip("_")
            subtitle_text = after.strip("_-")
            break
    return {
        "code": str(int(match.group("code"))),
        "label": label,
        "speaker_hint": speaker_hint,
        "subtitle_text": subtitle_text,
    }


def parse_event_cn(path: Path) -> tuple[dict, list[dict]]:
    data = path.read_bytes()
    if len(data) < 0x30 or data[:4] != b"GBHD" or data[0x10:0x14] != b"JMPT":
        raise ValueError(f"unsupported EventCn header: {path}")

    evlt_offset = struct.unpack_from("<I", data, 0x1C)[0]
    if data[evlt_offset : evlt_offset + 4] != b"EVLT":
        raise ValueError(f"EVLT not found at 0x{evlt_offset:x}")
    evlt_size, event_count = struct.unpack_from("<II", data, evlt_offset + 4)
    event_index_offset = evlt_offset + 12
    event_data_offset = event_index_offset + event_count * 12
    stbk_offset = evlt_offset + evlt_size
    if data[stbk_offset : stbk_offset + 4] != b"STBK":
        raise ValueError(f"STBK not found at 0x{stbk_offset:x}")

    stbk_size, string_count = struct.unpack_from("<II", data, stbk_offset + 4)
    string_offsets = struct.unpack_from(f"<{string_count}I", data, stbk_offset + 12)
    strings = []
    for offset in string_offsets:
        end = data.find(b"\x00", offset)
        if end < 0:
            end = len(data)
        strings.append(data[offset:end].decode("utf-8", errors="replace"))

    events = []
    for event_index in range(event_count):
        index_pos = event_index_offset + event_index * 12
        event_key = data[index_pos : index_pos + 8].decode("ascii", errors="replace")
        event_offset = struct.unpack_from("<I", data, index_pos + 8)[0]
        if data[event_offset : event_offset + 4] != b"EVT_":
            raise ValueError(f"EVT_ missing for event {event_index} at 0x{event_offset:x}")
        event_size, subrecord_count = struct.unpack_from("<II", data, event_offset + 4)
        pos = event_offset + 12
        subrecords = []
        for _ in range(subrecord_count):
            tag = data[pos : pos + 4].decode("ascii", errors="replace")
            size = struct.unpack_from("<I", data, pos + 4)[0]
            if size < 8 or pos + size > event_offset + event_size:
                raise ValueError(f"invalid {tag} subrecord at 0x{pos:x}")
            value_count = (size - 8) // 4
            values = struct.unpack_from(f"<{value_count}I", data, pos + 8) if value_count else tuple()
            subrecords.append({"tag": tag, "values": values, "offset": pos, "size": size})
            pos += size
        if pos != event_offset + event_size:
            raise ValueError(f"event {event_index} size mismatch at 0x{event_offset:x}")

        anim = next((item for item in subrecords if item["tag"] == "ANIM"), None)
        if not anim or len(anim["values"]) < 3:
            raise ValueError(f"event {event_index} has no valid ANIM record")
        values = anim["values"]
        root_index = values[0]
        main_count = values[1]
        main_indexes = list(values[2 : 2 + main_count])
        cursor = 2 + main_count
        overlay_count = values[cursor] if cursor < len(values) else 0
        cursor += 1
        overlays = []
        for overlay_index in range(overlay_count):
            pair = cursor + overlay_index * 2
            if pair + 1 >= len(values):
                break
            string_index, parameter = values[pair], values[pair + 1]
            overlays.append(
                {
                    "name": strings[string_index] if string_index < len(strings) else f"#{string_index}",
                    "parameter": parameter,
                }
            )

        controls = []
        for item in subrecords:
            if item["tag"] != "CTRL":
                continue
            controls.append(
                {
                    "values": list(item["values"]),
                    "strings": [strings[value] for value in item["values"] if value < len(strings)],
                }
            )

        events.append(
            {
                "event_index": event_index,
                "event_key": event_key,
                "event_offset": event_offset,
                "event_size": event_size,
                "root": strings[root_index] if root_index < len(strings) else f"#{root_index}",
                "main_animations": [
                    strings[index] if index < len(strings) else f"#{index}" for index in main_indexes
                ],
                "overlays": overlays,
                "controls": controls,
                "sounds": [item for item in subrecords if item["tag"] == "SND_"],
            }
        )

    return (
        {
            "file_size": len(data),
            "evlt_offset": evlt_offset,
            "evlt_size": evlt_size,
            "event_count": event_count,
            "event_data_offset": event_data_offset,
            "stbk_offset": stbk_offset,
            "stbk_size": stbk_size,
            "string_count": string_count,
        },
        events,
    )


def index_video_sources(video_dir: Path) -> tuple[dict[str, Path], dict[tuple[str, int], Path]]:
    by_stem: dict[str, Path] = {}
    by_slice: dict[tuple[str, int], Path] = {}
    if not video_dir.exists():
        return by_stem, by_slice
    slice_re = re.compile(r"^(main|patch)_video_(\d+)(?:_|$)", re.IGNORECASE)
    for path in video_dir.rglob("*.mp4"):
        by_stem.setdefault(path.stem.lower(), path)
        match = slice_re.match(path.stem)
        if match:
            by_slice.setdefault((match.group(1).lower(), int(match.group(2))), path)
    return by_stem, by_slice


def command_event_timeline_audit(args):
    manifest_dir = Path(args.manifest_dir)
    out_dir = Path(args.out_dir) if args.out_dir else manifest_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    metadata, events = parse_event_cn(Path(args.event_cn))
    hash_by_value = {
        row.get("hash_le_hex", "").upper(): row
        for row in read_csv(manifest_dir / "sound_hashreq_records.csv")
        if row.get("hash_le_hex")
    }
    hash_by_id = {
        parse_optional_int(row.get("request_id")): row
        for row in hash_by_value.values()
        if parse_optional_int(row.get("request_id")) is not None
    }
    sound_by_code = {
        row.get("sound_resource_id", ""): row
        for row in read_csv(manifest_dir / "sound_request_audit.csv")
        if row.get("sound_resource_id")
    }
    sound_id_by_code = {
        str(parse_optional_int(row.get("sound_resource_id"))): row
        for row in read_csv(manifest_dir / "sound_id_records.csv")
        if parse_optional_int(row.get("sound_resource_id")) is not None
    }
    ogg_duration_by_name = {
        Path(row.get("relative_path", "")).name.lower(): row.get("duration_sec", "")
        for row in read_csv(manifest_dir / "ramdisk_audit" / "ogg_ffprobe_audit.csv")
        if row.get("relative_path")
    }

    def resolve_ogg_metadata(code: str) -> dict:
        request_meta = sound_by_code.get(code, {})
        sound_id_meta = sound_id_by_code.get(code, {})
        suggested_name = first_nonempty(
            request_meta.get("suggested_name", ""),
            sound_id_meta.get("suggested_name", ""),
        )
        duration = first_nonempty(
            request_meta.get("ogg_duration_sec", ""),
            ogg_duration_by_name.get(suggested_name.lower(), "") if suggested_name else "",
        )
        return request_meta | {"suggested_name": suggested_name, "ogg_duration_sec": duration}
    smz_by_name = {
        row.get("name_key", "").lower(): row
        for row in read_csv(manifest_dir / "smz_name_chunk_map.csv")
        if row.get("name_key")
    }
    reqdata_by_request: dict[int, list[dict]] = defaultdict(list)
    for row in read_csv(manifest_dir / "sound_request_struct_reqdata.csv"):
        request_id = parse_optional_int(row.get("request_id"))
        if request_id is not None:
            reqdata_by_request[request_id].append(row)
    markers_by_request: dict[int, list[dict]] = defaultdict(list)
    for row in read_csv(manifest_dir / "sound_request_struct_markers.csv"):
        request_id = parse_optional_int(row.get("request_id"))
        if request_id is not None:
            markers_by_request[request_id].append(row)

    candidate_by_name: dict[str, list[dict]] = defaultdict(list)
    for row in read_csv(manifest_dir / "video_candidates.csv"):
        for candidate in split_semicolon(row.get("candidates", "")):
            candidate_by_name[candidate.lower()].append(row)

    video_dir = Path(args.video_dir) if args.video_dir else Path()
    video_by_stem, video_by_slice = index_video_sources(video_dir)
    ogg_dir = Path(args.ogg_dir) if args.ogg_dir else Path()
    ogg_by_name = (
        {path.name.lower(): path for path in ogg_dir.rglob("*.ogg")} if args.ogg_dir and ogg_dir.exists() else {}
    )

    event_rows = []
    sound_rows = []
    component_rows = []
    event_marker_rows = []
    for event in events:
        root = event["root"]
        main_animations = event["main_animations"]
        root_prefix = root.lower() + "_"
        primary = next(
            (name for name in main_animations if name.lower().startswith(root_prefix)),
            main_animations[0] if main_animations else "",
        )
        candidate_rows = candidate_by_name.get(primary.lower(), [])
        candidate = candidate_rows[0] if candidate_rows else {}
        package = candidate.get("package", "")
        slice_index = parse_optional_int(candidate.get("index"))
        source_path = video_by_stem.get(primary.lower())
        if not source_path and package and slice_index is not None:
            source_path = video_by_slice.get((package.lower(), slice_index))

        event_sound_rows = []
        event_component_rows = []
        event_markers = []
        for sound_order, sound in enumerate(event["sounds"]):
            values = sound["values"]
            hash_le = struct.pack("<II", values[0], values[1]).hex().upper()
            request = hash_by_value.get(hash_le, {})
            code_name = request.get("code_name", "")
            parsed = parse_code_name_label(code_name)
            sound_meta = resolve_ogg_metadata(parsed["code"])
            smz_media = request.get("first_smz_media", "")
            smz = smz_by_name.get(smz_media.removesuffix(".smz").lower(), {})
            duration_ms = parse_optional_int(
                first_nonempty(request.get("duration_ms_u32", ""), request.get("sample_count_u32", ""))
            )
            duration_sec = duration_ms / 1000 if duration_ms is not None else None
            ogg_duration = parse_optional_float(sound_meta.get("ogg_duration_sec"))
            duration_error = (
                abs(ogg_duration - duration_sec)
                if duration_sec is not None and ogg_duration is not None
                else None
            )
            ogg_name = sound_meta.get("suggested_name", "")
            ogg_path = ogg_by_name.get(ogg_name.lower()) if ogg_name else None
            row = {
                "event_index": event["event_index"],
                "event_key": event["event_key"],
                "root": root,
                "primary_animation": primary,
                "sound_order": sound_order,
                "hash_le_hex": hash_le,
                "request_id": request.get("request_id", ""),
                "sound_code": parsed["code"],
                "code_name": code_name,
                "label": parsed["label"],
                "speaker_hint": parsed["speaker_hint"],
                "subtitle_text": parsed["subtitle_text"],
                "duration_ms": duration_ms if duration_ms is not None else "",
                "duration_sec": f"{duration_sec:.6f}" if duration_sec is not None else "",
                "smz_media": smz_media,
                "smz_chunk_index": smz.get("chunk_index", ""),
                "ogg_name": ogg_name,
                "ogg_duration_sec": sound_meta.get("ogg_duration_sec", ""),
                "ogg_duration_error_sec": f"{duration_error:.6f}" if duration_error is not None else "",
                "ogg_duration_match": "yes" if duration_error is not None and duration_error <= 0.005 else "no",
                "ogg_path": str(ogg_path) if ogg_path else "",
                "snd_values": ";".join(str(value) for value in values),
            }
            sound_rows.append(row)
            event_sound_rows.append(row)

            parent_request_id = parse_optional_int(row["request_id"])
            if parent_request_id is None:
                continue
            for reqdata in reqdata_by_request.get(parent_request_id, []):
                media = reqdata.get("smz_media", "")
                if not media:
                    continue
                leaf_request_id = parse_optional_int(reqdata.get("reqdata_ref_id_a"))
                leaf = hash_by_id.get(leaf_request_id, {}) if leaf_request_id is not None else {}
                leaf_parsed = parse_code_name_label(leaf.get("code_name", ""))
                leaf_sound_meta = resolve_ogg_metadata(leaf_parsed["code"])
                leaf_duration_ms = parse_optional_int(
                    first_nonempty(leaf.get("duration_ms_u32", ""), leaf.get("sample_count_u32", ""))
                )
                leaf_duration_sec = leaf_duration_ms / 1000 if leaf_duration_ms is not None else None
                leaf_ogg_duration = parse_optional_float(leaf_sound_meta.get("ogg_duration_sec"))
                leaf_duration_error = (
                    abs(leaf_ogg_duration - leaf_duration_sec)
                    if leaf_duration_sec is not None and leaf_ogg_duration is not None
                    else None
                )
                leaf_ogg_name = leaf_sound_meta.get("suggested_name", "")
                leaf_ogg_path = ogg_by_name.get(leaf_ogg_name.lower()) if leaf_ogg_name else None
                component = {
                    "event_index": event["event_index"],
                    "event_key": event["event_key"],
                    "root": root,
                    "primary_animation": primary,
                    "parent_sound_order": sound_order,
                    "parent_request_id": parent_request_id,
                    "parent_code_name": code_name,
                    "reqdata_index": reqdata.get("reqdata_index", ""),
                    "start_ms": reqdata.get("u32_03", ""),
                    "leaf_request_id": leaf_request_id if leaf_request_id is not None else "",
                    "leaf_sound_code": leaf_parsed["code"],
                    "leaf_code_name": leaf.get("code_name", ""),
                    "leaf_label": leaf_parsed["label"],
                    "speaker_hint": leaf_parsed["speaker_hint"],
                    "subtitle_text": leaf_parsed["subtitle_text"],
                    "duration_ms": leaf_duration_ms if leaf_duration_ms is not None else "",
                    "duration_sec": f"{leaf_duration_sec:.6f}" if leaf_duration_sec is not None else "",
                    "smz_media": media,
                    "smz_matches_leaf_request": (
                        "yes" if media.lower() == leaf.get("first_smz_media", "").lower() else "no"
                    ),
                    "ogg_name": leaf_ogg_name,
                    "ogg_duration_sec": leaf_sound_meta.get("ogg_duration_sec", ""),
                    "ogg_duration_error_sec": (
                        f"{leaf_duration_error:.6f}" if leaf_duration_error is not None else ""
                    ),
                    "ogg_duration_match": (
                        "yes"
                        if leaf_duration_error is not None and leaf_duration_error <= 0.005
                        else "no"
                    ),
                    "ogg_path": str(leaf_ogg_path) if leaf_ogg_path else "",
                    "reqdata_type": reqdata.get("reqdata_type", ""),
                    "reqdata_group_or_channel": reqdata.get("reqdata_group_or_channel", ""),
                    "reqdata_flag": reqdata.get("reqdata_flag", ""),
                }
                component_rows.append(component)
                event_component_rows.append(component)

            for marker in markers_by_request.get(parent_request_id, []):
                event_marker = {
                    "event_index": event["event_index"],
                    "event_key": event["event_key"],
                    "root": root,
                    "primary_animation": primary,
                    "parent_sound_order": sound_order,
                    "parent_request_id": parent_request_id,
                    "parent_code_name": code_name,
                    "marker_index": marker.get("marker_index", ""),
                    "marker_time_ms": marker.get("marker_time_ms", ""),
                    "marker_name": marker.get("marker_name", ""),
                }
                event_marker_rows.append(event_marker)
                event_markers.append(event_marker)

        subtitles = [
            row["subtitle_text"] for row in event_component_rows if row["subtitle_text"]
        ]
        component_ends = []
        for row in event_component_rows:
            start_ms = parse_optional_int(row.get("start_ms")) or 0
            duration_ms = parse_optional_int(row.get("duration_ms")) or 0
            component_ends.append(start_ms + duration_ms)
        event_rows.append(
            {
                "event_index": event["event_index"],
                "event_key": event["event_key"],
                "event_offset_hex": f"0x{event['event_offset']:x}",
                "root": root,
                "primary_animation": primary,
                "main_animation_count": len(main_animations),
                "main_animations": ";".join(main_animations),
                "overlay_count": len(event["overlays"]),
                "overlays": ";".join(
                    f"{item['name']}:{item['parameter']}" for item in event["overlays"]
                ),
                "control_commands": json.dumps(event["controls"], ensure_ascii=False, separators=(",", ":")),
                "sound_count": len(event_sound_rows),
                "sound_request_ids": ";".join(str(row["request_id"]) for row in event_sound_rows),
                "sound_codes": ";".join(row["sound_code"] for row in event_sound_rows),
                "sound_labels": ";".join(row["label"] for row in event_sound_rows),
                "audio_component_count": len(event_component_rows),
                "audio_component_ogg_count": sum(bool(row["ogg_name"]) for row in event_component_rows),
                "audio_timeline_duration_ms": max(component_ends) if component_ends else "",
                "subtitle_texts": " / ".join(subtitles),
                "marker_count": len(event_markers),
                "markers": ";".join(
                    f"{row['marker_time_ms']}:{row['marker_name']}" for row in event_markers
                ),
                "smz_media": ";".join(row["smz_media"] for row in event_sound_rows),
                "ogg_names": ";".join(row["ogg_name"] for row in event_sound_rows),
                "all_ogg_duration_match": (
                    "yes"
                    if event_sound_rows and all(row["ogg_duration_match"] == "yes" for row in event_sound_rows)
                    else "no"
                ),
                "video_package": package,
                "video_index": slice_index if slice_index is not None else "",
                "video_candidate_count": candidate.get("candidate_count", ""),
                "video_default_mp4": candidate.get("default_mp4", ""),
                "video_source_path": str(source_path) if source_path else "",
                "video_mapping": (
                    "exact_unique"
                    if candidate and candidate.get("candidate_count") == "1"
                    else "exact_context_candidate"
                    if candidate
                    else "missing"
                ),
            }
        )

    event_csv = out_dir / "event_timeline_events.csv"
    sound_csv = out_dir / "event_timeline_sounds.csv"
    component_csv = out_dir / "event_audio_components.csv"
    marker_csv = out_dir / "event_timeline_markers.csv"
    write_csv(event_csv, event_rows, list(event_rows[0].keys()))
    write_csv(sound_csv, sound_rows, list(sound_rows[0].keys()))
    write_csv(component_csv, component_rows, list(component_rows[0].keys()))
    if event_marker_rows:
        write_csv(marker_csv, event_marker_rows, list(event_marker_rows[0].keys()))

    counts = Counter(row["video_mapping"] for row in event_rows)
    events_with_sound = sum(bool(row["sound_count"]) for row in event_rows)
    exact_ogg = sum(row["ogg_duration_match"] == "yes" for row in sound_rows)
    exact_component_ogg = sum(row["ogg_duration_match"] == "yes" for row in component_rows)
    dialogue_events = sum(bool(row["subtitle_texts"]) for row in event_rows)
    summary_path = out_dir / "event_timeline_summary.md"
    summary_lines = [
        "# Event Timeline Audit",
        "",
        f"Source: {args.event_cn}",
        f"Events: {len(event_rows)}",
        f"Strings: {metadata['string_count']}",
        f"Events with SND records: {events_with_sound}",
        f"SND records: {len(sound_rows)}",
        f"SND hashes matched to requests: {sum(bool(row['request_id'] != '') for row in sound_rows)}",
        f"SND records with OGG duration match within 5 ms: {exact_ogg}",
        f"Expanded audible components: {len(component_rows)}",
        f"Expanded components with OGG duration match within 5 ms: {exact_component_ogg}",
        f"Event marker callbacks: {len(event_marker_rows)}",
        f"Events with parsed dialogue text: {dialogue_events}",
        "",
        "## Video Mapping",
    ]
    for key, value in sorted(counts.items()):
        summary_lines.append(f"- {key}: {value}")
    summary_lines.extend(
        [
            "",
            "## Interpretation",
            "- Each EVT_ record binds one root animation event to zero or more SND_ request hashes.",
            "- The primary animation is the main ANIM name prefixed by the event root.",
            "- GDB candidate names map that animation to a physical main/patch CRI slice.",
            "- A multi-candidate physical slice is reusable in multiple named event contexts; the event root disambiguates the context.",
            "- Additional ANIM names are overlays or controls, not evidence that the referenced videos should be concatenated.",
            "- SND request duration u32 values are milliseconds. Matching sound-code OGG files agree within 5 ms for nearly all ordinary requests.",
            "- Composite/seq requests are expanded through ReqData ref ids. Every media-bearing ReqData row points to a leaf request with the same SMZ name.",
            "- ReqData u32_03 is exported as the component start offset in milliseconds; marker records are exported separately as timed callback names.",
            "- SND records are event-start bindings. Cross-event continuation and final upload grouping remain separate sequencing decisions.",
        ]
    )
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    print(f"[event-timeline-audit] events: {len(event_rows)}")
    print(f"[event-timeline-audit] sounds: {len(sound_rows)}")
    print(f"[event-timeline-audit] wrote {event_csv}")
    print(f"[event-timeline-audit] wrote {sound_csv}")
    print(f"[event-timeline-audit] wrote {component_csv}")
    if event_marker_rows:
        print(f"[event-timeline-audit] wrote {marker_csv}")
    print(f"[event-timeline-audit] wrote {summary_path}")


def srt_timestamp(milliseconds: int) -> str:
    milliseconds = max(0, milliseconds)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def build_event_video_one(
    event: dict,
    components: list[dict],
    out_dir: Path,
    execute: bool,
    overwrite: bool,
    encoder: str,
    max_tail_sec: float,
) -> dict:
    source = Path(event["video_source_path"])
    root_dir = out_dir / "no_subtitles" / safe_name(event["root"])
    output_name = f"{safe_name(event['primary_animation'])}__event{int(event['event_index']):04d}.mp4"
    output = root_dir / output_name
    subtitle_path = out_dir / "subtitles_srt" / safe_name(event["root"]) / output_name.replace(".mp4", ".srt")
    row = {
        "event_index": event["event_index"],
        "root": event["root"],
        "primary_animation": event["primary_animation"],
        "source_path": str(source),
        "output_path": str(output),
        "component_count": len(components),
        "subtitle_path": "",
        "video_duration_sec": "",
        "audio_end_sec": "",
        "output_duration_sec": "",
        "audio_tail_truncated": "no",
        "video_mode": "",
        "status": "planned",
        "error": "",
    }
    if not source.exists():
        row["status"] = "missing_video"
        return row

    subtitle_components = [item for item in components if item.get("subtitle_text")]
    if subtitle_components:
        subtitle_path.parent.mkdir(parents=True, exist_ok=True)
        lines = []
        for index, item in enumerate(subtitle_components, start=1):
            start_ms = parse_optional_int(item.get("start_ms")) or 0
            duration_ms = parse_optional_int(item.get("duration_ms")) or 1000
            end_ms = max(start_ms + duration_ms, start_ms + 500)
            text = item["subtitle_text"]
            if item.get("speaker_hint"):
                text = f"{item['speaker_hint']}: {text}"
            lines.extend(
                [
                    str(index),
                    f"{srt_timestamp(start_ms)} --> {srt_timestamp(end_ms)}",
                    text,
                    "",
                ]
            )
        if execute:
            subtitle_path.write_text("\n".join(lines), encoding="utf-8-sig")
        row["subtitle_path"] = str(subtitle_path)

    if not components:
        row["video_mode"] = "hardlink_source"
        if not execute:
            return row
        root_dir.mkdir(parents=True, exist_ok=True)
        if output.exists():
            row["status"] = "exists" if not overwrite else "replacing"
            if not overwrite:
                return row
            output.unlink()
        try:
            os.link(source, output)
        except OSError:
            shutil.copy2(source, output)
            row["video_mode"] = "copy_source"
        row["status"] = "ok"
        return row

    probe = probe_mp4(source)
    video_duration = parse_optional_float(probe.get("duration_sec"))
    if not probe.get("probe_ok") or video_duration is None:
        row["status"] = "probe_failed"
        row["error"] = probe.get("probe_error", "missing duration")
        return row
    row["video_duration_sec"] = f"{video_duration:.6f}"

    usable_components = [item for item in components if item.get("ogg_path") and Path(item["ogg_path"]).exists()]
    if not usable_components:
        row["status"] = "missing_audio"
        return row
    audio_end = max(
        (parse_optional_int(item.get("start_ms")) or 0) / 1000
        + (parse_optional_float(item.get("ogg_duration_sec")) or parse_optional_float(item.get("duration_sec")) or 0)
        for item in usable_components
    )
    output_duration = max(video_duration, min(audio_end, video_duration + max_tail_sec))
    row["audio_end_sec"] = f"{audio_end:.6f}"
    row["output_duration_sec"] = f"{output_duration:.6f}"
    row["audio_tail_truncated"] = "yes" if audio_end > output_duration + 0.01 else "no"
    extends_video = output_duration > video_duration + 0.01
    row["video_mode"] = "extend_last_frame" if extends_video else "copy_h264"

    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y" if overwrite else "-n", "-i", str(source)]
    for item in usable_components:
        cmd.extend(["-i", item["ogg_path"]])

    filters = []
    audio_labels = []
    for index, item in enumerate(usable_components):
        delay_ms = parse_optional_int(item.get("start_ms")) or 0
        label = f"a{index}"
        filters.append(f"[{index + 1}:a]adelay={delay_ms}:all=1[{label}]")
        audio_labels.append(f"[{label}]")
    if len(audio_labels) == 1:
        filters.append(f"{audio_labels[0]}apad=pad_dur={output_duration:.6f}[aout]")
    else:
        filters.append(
            "".join(audio_labels)
            + f"amix=inputs={len(audio_labels)}:duration=longest:dropout_transition=0:normalize=0,"
            + f"alimiter=limit=0.95,apad=pad_dur={output_duration:.6f}[aout]"
        )

    if extends_video:
        filters.insert(
            0,
            f"[0:v]tpad=stop_mode=clone:stop_duration={output_duration - video_duration:.6f}[vout]",
        )
        cmd.extend(["-filter_complex", ";".join(filters), "-map", "[vout]", "-map", "[aout]"])
        if encoder == "h264_nvenc":
            cmd.extend(["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "19"])
        else:
            cmd.extend(["-c:v", "libx264", "-crf", "16", "-preset", "medium"])
        cmd.extend(["-pix_fmt", "yuv420p"])
    else:
        cmd.extend(["-filter_complex", ";".join(filters), "-map", "0:v:0", "-map", "[aout]", "-c:v", "copy"])
    cmd.extend(
        [
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-t",
            f"{output_duration:.6f}",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )

    if not execute:
        row["ffmpeg_command"] = subprocess.list2cmdline(cmd)
        return row
    root_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if result.returncode == 0:
        row["status"] = "ok"
    else:
        row["status"] = "ffmpeg_failed"
        row["error"] = result.stderr.strip()[-1000:]
    return row


def command_build_event_videos(args):
    timeline_dir = Path(args.timeline_dir)
    out_dir = Path(args.out_dir)
    events = read_csv(timeline_dir / "event_timeline_events.csv")
    components_by_event: dict[str, list[dict]] = defaultdict(list)
    for row in read_csv(timeline_dir / "event_audio_components.csv"):
        components_by_event[row["event_index"]].append(row)

    focus_roots = {item.strip().lower() for item in args.focus_root.split(",") if item.strip()}
    selected = []
    for event in events:
        event_index = parse_optional_int(event.get("event_index"))
        if event_index is None:
            continue
        if args.event_start is not None and event_index < args.event_start:
            continue
        if args.event_end is not None and event_index > args.event_end:
            continue
        if focus_roots and event.get("root", "").lower() not in focus_roots:
            continue
        if not event.get("video_source_path"):
            continue
        if args.audible_only and not components_by_event.get(event["event_index"]):
            continue
        selected.append(event)
    if args.limit:
        selected = selected[: args.limit]

    print(f"[build-event-videos] selected events: {len(selected)}")
    print(f"[build-event-videos] output: {out_dir}")
    rows = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(
                build_event_video_one,
                event,
                components_by_event.get(event["event_index"], []),
                out_dir,
                args.execute,
                args.overwrite,
                args.encoder,
                args.max_tail_sec,
            ): event
            for event in selected
        }
        for processed, future in enumerate(as_completed(futures), start=1):
            try:
                rows.append(future.result())
            except Exception as exc:
                event = futures[future]
                rows.append(
                    {
                        "event_index": event["event_index"],
                        "root": event.get("root", ""),
                        "primary_animation": event.get("primary_animation", ""),
                        "source_path": event.get("video_source_path", ""),
                        "output_path": "",
                        "component_count": len(components_by_event.get(event["event_index"], [])),
                        "subtitle_path": "",
                        "video_duration_sec": "",
                        "audio_end_sec": "",
                        "output_duration_sec": "",
                        "audio_tail_truncated": "",
                        "video_mode": "",
                        "status": "exception",
                        "error": str(exc),
                    }
                )
            if processed % 100 == 0 or processed == len(selected):
                print(f"[build-event-videos] processed {processed}/{len(selected)}")

    rows.sort(key=lambda row: parse_optional_int(row.get("event_index")) or 0)
    manifest_path = out_dir / "event_video_build.csv"
    fields = [
        "event_index",
        "root",
        "primary_animation",
        "source_path",
        "output_path",
        "component_count",
        "subtitle_path",
        "video_duration_sec",
        "audio_end_sec",
        "output_duration_sec",
        "audio_tail_truncated",
        "video_mode",
        "status",
        "error",
    ]
    if not args.execute:
        fields.append("ffmpeg_command")
    write_csv(manifest_path, rows, fields)
    counts = Counter(row["status"] for row in rows)
    summary_path = out_dir / "event_video_build_summary.md"
    lines = [
        "# Event Video Build Summary",
        "",
        f"Selected events: {len(selected)}",
        f"Execute: {'yes' if args.execute else 'no'}",
        f"Focus roots: {', '.join(sorted(focus_roots)) if focus_roots else '(all)'}",
        f"Event index range: {args.event_start if args.event_start is not None else '(first)'}.."
        f"{args.event_end if args.event_end is not None else '(last)'}",
        f"Max last-frame audio tail: {args.max_tail_sec:.3f}s",
        "",
        "## Status",
    ]
    for key, value in sorted(counts.items()):
        lines.append(f"- {key}: {value}")
    lines.extend(
        [
            "",
            "## Output Policy",
            "- Existing embedded audio is discarded.",
            "- Event audio is rebuilt from EventCn SND -> ReqData leaf request -> matching OGG.",
            "- ReqData u32_03 is applied as the OGG start delay.",
            "- Video is stream-copied when no tail extension is required.",
            "- A short final frame extension preserves ordinary effect/voice tails.",
            "- Long-running audio is truncated and flagged for later sequence-level merging.",
            "- Events without audible components are hardlinked when possible; source files are never moved.",
        ]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[build-event-videos] wrote {manifest_path}")
    print(f"[build-event-videos] wrote {summary_path}")


def concat_file_line(path: Path) -> str:
    escaped = str(path.resolve()).replace("\\", "/").replace("'", "'\\''")
    return f"file '{escaped}'"


def command_build_event_sequence(args):
    timeline_dir = Path(args.timeline_dir)
    out_dir = Path(args.out_dir)
    events = read_csv(timeline_dir / "event_timeline_events.csv")
    components_by_event: dict[str, list[dict]] = defaultdict(list)
    for row in read_csv(timeline_dir / "event_audio_components.csv"):
        components_by_event[row["event_index"]].append(row)
    subtitle_rows_by_event: dict[str, list[dict]] = defaultdict(list)
    if args.subtitle_timeline_csv:
        subtitle_timeline_path = Path(args.subtitle_timeline_csv)
        if not subtitle_timeline_path.exists():
            raise FileNotFoundError(
                f"subtitle event timeline does not exist: {subtitle_timeline_path}"
            )
        for row in read_csv(subtitle_timeline_path):
            if (
                row.get("timeline_confidence") != "exact_gdb_frame_and_official_ogg"
                or row.get("ogg_exists") != "yes"
                or not row.get("display_text")
                or not row.get("ogg_path")
                or not row.get("z2d_name", "").lower().startswith("cap")
            ):
                continue
            subtitle_rows_by_event[row.get("event_name", "").lower()].append(row)

    focus_roots = {item.strip().lower() for item in args.focus_root.split(",") if item.strip()}
    selected = []
    for event in events:
        event_index = parse_optional_int(event.get("event_index"))
        if event_index is None:
            continue
        if args.event_start is not None and event_index < args.event_start:
            continue
        if args.event_end is not None and event_index > args.event_end:
            continue
        if focus_roots and event.get("root", "").lower() not in focus_roots:
            continue
        if not event.get("video_source_path"):
            continue
        selected.append(event)
    selected.sort(key=lambda row: parse_optional_int(row.get("event_index")) or -1)
    if args.limit:
        selected = selected[: args.limit]
    if not selected:
        raise ValueError("no mapped video events selected")

    roots = {event.get("root", "") for event in selected}
    if len(roots) != 1 and not args.allow_mixed_roots:
        raise ValueError(
            "selected events span multiple roots; use --focus-root or explicitly pass --allow-mixed-roots"
        )

    indexes = [parse_optional_int(event.get("event_index")) for event in selected]
    gaps = [
        (left, right)
        for left, right in zip(indexes, indexes[1:])
        if left is not None and right is not None and right != left + 1
    ]
    if gaps and not args.allow_event_gaps:
        preview = ", ".join(f"{left}->{right}" for left, right in gaps[:8])
        raise ValueError(f"selected event range has gaps ({preview}); pass --allow-event-gaps to accept them")

    sequence_label = args.sequence_name.strip()
    if not sequence_label:
        root_label = next(iter(roots)) if len(roots) == 1 else "mixed"
        sequence_label = f"{root_label}_event{indexes[0]:04d}-{indexes[-1]:04d}"
    sequence_label = safe_name(sequence_label)
    no_subtitles_dir = out_dir / "no_subtitles"
    subtitle_dir = out_dir / "subtitles_srt"
    burned_subtitle_dir = out_dir / "subtitles_burned"
    work_dir = out_dir / "work"
    output_path = no_subtitles_dir / f"{sequence_label}.mp4"
    subtitle_path = subtitle_dir / f"{sequence_label}.srt"
    burned_output_path = burned_subtitle_dir / f"{sequence_label}.mp4"
    concat_path = work_dir / f"{sequence_label}.ffconcat"

    segment_rows = []
    audio_rows = []
    subtitle_rows = []
    audio_seen: set[tuple[str, int]] = set()
    current_ms = 0
    compatibility = set()
    for sequence_order, event in enumerate(selected):
        source = Path(event["video_source_path"])
        if not source.exists():
            raise FileNotFoundError(f"missing source video: {source}")
        probe = probe_mp4(source)
        if not probe.get("probe_ok") or not probe.get("has_video"):
            raise ValueError(f"cannot probe video source: {source}: {probe.get('probe_error', '')}")
        duration_sec = parse_optional_float(probe.get("duration_sec"))
        if duration_sec is None or duration_sec <= 0:
            raise ValueError(f"invalid source duration: {source}")
        duration_ms = int(round(duration_sec * 1000))
        event_index = event["event_index"]
        event_components = components_by_event.get(event_index, [])
        segment_rows.append(
            {
                "sequence_order": sequence_order,
                "event_index": event_index,
                "root": event.get("root", ""),
                "primary_animation": event.get("primary_animation", ""),
                "source_path": str(source),
                "start_ms": current_ms,
                "duration_ms": duration_ms,
                "end_ms": current_ms + duration_ms,
                "width": probe.get("width", ""),
                "height": probe.get("height", ""),
                "video_codec": probe.get("video_codec", ""),
                "frame_rate": probe.get("frame_rate", ""),
                "official_audio_component_count": len(event_components),
            }
        )
        compatibility.add(
            (
                probe.get("video_codec", ""),
                probe.get("width", ""),
                probe.get("height", ""),
                probe.get("frame_rate", ""),
            )
        )
        for component in event_components:
            ogg_path = Path(component["ogg_path"]) if component.get("ogg_path") else None
            if not ogg_path or not ogg_path.exists():
                continue
            component_start_ms = parse_optional_int(component.get("start_ms")) or 0
            duration_ms_value = parse_optional_int(component.get("duration_ms"))
            if duration_ms_value is None:
                duration_sec_value = parse_optional_float(component.get("ogg_duration_sec")) or 0
                duration_ms_value = int(round(duration_sec_value * 1000))
            sequence_start_ms = current_ms + component_start_ms
            audio_key = (str(ogg_path.resolve()).lower(), sequence_start_ms)
            if audio_key in audio_seen:
                continue
            audio_seen.add(audio_key)
            audio_row = {
                "audio_order": len(audio_rows),
                "source_kind": "EventCn",
                "event_index": event_index,
                "event_name": event.get("primary_animation", ""),
                "primary_animation": event.get("primary_animation", ""),
                "event_start_ms": current_ms,
                "component_start_ms": component_start_ms,
                "sequence_start_ms": sequence_start_ms,
                "sequence_end_ms": sequence_start_ms + duration_ms_value,
                "parent_code_name": component.get("parent_code_name", ""),
                "leaf_code_name": component.get("leaf_code_name", ""),
                "ogg_name": component.get("ogg_name", ""),
                "ogg_path": str(ogg_path),
                "ogg_duration_sec": component.get("ogg_duration_sec", ""),
                "speaker_hint": component.get("speaker_hint", ""),
                "subtitle_text": component.get("subtitle_text", ""),
                "z2d_name": "",
                "visual_start_ms": "",
                "visual_end_ms": "",
            }
            audio_rows.append(audio_row)

        event_name = event.get("primary_animation", "").lower()
        for subtitle_component in subtitle_rows_by_event.get(event_name, []):
            ogg_path = Path(subtitle_component["ogg_path"])
            if not ogg_path.exists():
                continue
            component_start_ms = parse_optional_int(subtitle_component.get("start_ms")) or 0
            duration_ms_value = (
                parse_optional_int(subtitle_component.get("sound_duration_ms"))
                or 0
            )
            sequence_start_ms = current_ms + component_start_ms
            audio_key = (str(ogg_path.resolve()).lower(), sequence_start_ms)
            if audio_key not in audio_seen:
                audio_seen.add(audio_key)
                audio_rows.append(
                    {
                        "audio_order": len(audio_rows),
                        "source_kind": "Z2D_dialogue",
                        "event_index": event_index,
                        "event_name": subtitle_component.get("event_name", ""),
                        "primary_animation": event.get("primary_animation", ""),
                        "event_start_ms": current_ms,
                        "component_start_ms": component_start_ms,
                        "sequence_start_ms": sequence_start_ms,
                        "sequence_end_ms": sequence_start_ms + duration_ms_value,
                        "parent_code_name": "",
                        "leaf_code_name": subtitle_component.get(
                            "sound_request_id",
                            "",
                        ),
                        "ogg_name": subtitle_component.get("ogg_name", ""),
                        "ogg_path": str(ogg_path),
                        "ogg_duration_sec": (
                            duration_ms_value / 1000
                            if duration_ms_value
                            else ""
                        ),
                        "speaker_hint": "",
                        "subtitle_text": subtitle_component.get("display_text", ""),
                        "z2d_name": subtitle_component.get("z2d_name", ""),
                        "visual_start_ms": subtitle_component.get("start_ms", ""),
                        "visual_end_ms": subtitle_component.get(
                            "visual_end_ms",
                            "",
                        ),
                    }
                )

            visual_end_ms = parse_optional_int(
                subtitle_component.get("visual_end_ms")
            )
            if visual_end_ms is None:
                visual_end_ms = component_start_ms + max(duration_ms_value, 1000)
            audio_end_ms = component_start_ms + duration_ms_value
            subtitle_rows.append(
                {
                    "event_index": event_index,
                    "event_name": subtitle_component.get("event_name", ""),
                    "z2d_name": subtitle_component.get("z2d_name", ""),
                    "sequence_start_ms": sequence_start_ms,
                    "sequence_visual_end_ms": current_ms + visual_end_ms,
                    "sequence_audio_end_ms": current_ms + audio_end_ms,
                    "sequence_end_ms": current_ms
                    + max(visual_end_ms, audio_end_ms),
                    "display_text": subtitle_component.get("display_text", ""),
                    "ogg_name": subtitle_component.get("ogg_name", ""),
                }
            )
        current_ms += duration_ms

    total_duration_sec = current_ms / 1000
    stream_copy_compatible = len(compatibility) == 1
    if not stream_copy_compatible and args.video_mode == "copy":
        raise ValueError(
            "source video codec/resolution/frame-rate values differ; use --video-mode encode"
        )

    if subtitle_rows:
        subtitle_rows.sort(
            key=lambda row: (
                int(row["sequence_start_ms"]),
                str(row["event_name"]),
                str(row["z2d_name"]),
            )
        )
        subtitle_lines = []
        for subtitle_index, row in enumerate(subtitle_rows, start=1):
            start_ms = int(row["sequence_start_ms"])
            end_ms = int(row["sequence_end_ms"])
            if subtitle_index < len(subtitle_rows):
                next_start_ms = int(
                    subtitle_rows[subtitle_index]["sequence_start_ms"]
                )
                if next_start_ms > start_ms:
                    end_ms = min(end_ms, next_start_ms)
            end_ms = max(end_ms, start_ms + 100)
            row["sequence_end_ms"] = end_ms
            text = row["display_text"].replace(" ", "\n")
            subtitle_lines.extend(
                [
                    str(subtitle_index),
                    f"{srt_timestamp(start_ms)} --> {srt_timestamp(end_ms)}",
                    text,
                    "",
                ]
            )
        if args.execute:
            subtitle_dir.mkdir(parents=True, exist_ok=True)
            subtitle_path.write_text("\n".join(subtitle_lines), encoding="utf-8-sig")
    write_csv(
        out_dir / "sequence_subtitle_timeline.csv",
        subtitle_rows,
        [
            "event_index",
            "event_name",
            "z2d_name",
            "sequence_start_ms",
            "sequence_visual_end_ms",
            "sequence_audio_end_ms",
            "sequence_end_ms",
            "display_text",
            "ogg_name",
        ],
    )

    work_dir.mkdir(parents=True, exist_ok=True)
    concat_path.write_text(
        "ffconcat version 1.0\n"
        + "\n".join(concat_file_line(Path(row["source_path"])) for row in segment_rows)
        + "\n",
        encoding="utf-8",
    )
    write_csv(
        out_dir / "sequence_segments.csv",
        segment_rows,
        [
            "sequence_order",
            "event_index",
            "root",
            "primary_animation",
            "source_path",
            "start_ms",
            "duration_ms",
            "end_ms",
            "width",
            "height",
            "video_codec",
            "frame_rate",
            "official_audio_component_count",
        ],
    )
    write_csv(
        out_dir / "sequence_audio_timeline.csv",
        audio_rows,
        [
            "audio_order",
            "source_kind",
            "event_index",
            "event_name",
            "primary_animation",
            "event_start_ms",
            "component_start_ms",
            "sequence_start_ms",
            "sequence_end_ms",
            "parent_code_name",
            "leaf_code_name",
            "ogg_name",
            "ogg_path",
            "ogg_duration_sec",
            "speaker_hint",
            "subtitle_text",
            "z2d_name",
            "visual_start_ms",
            "visual_end_ms",
        ],
    )

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y" if args.overwrite else "-n",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_path),
    ]
    for row in audio_rows:
        cmd.extend(["-i", row["ogg_path"]])

    filters = []
    audio_labels = []
    if audio_rows:
        for audio_index, row in enumerate(audio_rows, start=1):
            delay_ms = int(row["sequence_start_ms"])
            label = f"a{audio_index}"
            filters.append(f"[{audio_index}:a]adelay={delay_ms}:all=1[{label}]")
            audio_labels.append(f"[{label}]")
        if len(audio_labels) == 1:
            filters.append(
                f"{audio_labels[0]}apad=pad_dur={total_duration_sec:.6f}[aout]"
            )
        else:
            filters.append(
                "".join(audio_labels)
                + f"amix=inputs={len(audio_labels)}:duration=longest:"
                + "dropout_transition=0:normalize=0,"
                + f"alimiter=limit=0.95,apad=pad_dur={total_duration_sec:.6f}[aout]"
            )
    else:
        filters.append(
            f"anullsrc=r=48000:cl=stereo,atrim=duration={total_duration_sec:.6f}[aout]"
        )

    cmd.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "0:v:0",
            "-map",
            "[aout]",
        ]
    )
    if args.video_mode == "copy":
        cmd.extend(["-c:v", "copy"])
    elif args.encoder == "h264_nvenc":
        cmd.extend(["-c:v", "h264_nvenc", "-preset", "p4", "-cq", str(args.cq)])
    else:
        cmd.extend(["-c:v", "libx264", "-preset", "medium", "-crf", str(args.crf)])
    cmd.extend(
        [
            "-c:a",
            "aac",
            "-b:a",
            "256k",
            "-t",
            f"{total_duration_sec:.6f}",
            "-movflags",
            "+faststart",
            "-map_metadata",
            "-1",
            str(output_path),
        ]
    )
    command_path = out_dir / "sequence_ffmpeg_command.txt"
    command_path.write_text(subprocess.list2cmdline(cmd) + "\n", encoding="utf-8")

    status = "planned"
    error = ""
    output_probe = {}
    if args.execute:
        no_subtitles_dir.mkdir(parents=True, exist_ok=True)
        if output_path.exists() and not args.overwrite:
            status = "exists"
        else:
            result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            if result.returncode == 0:
                status = "ok"
                output_probe = probe_mp4(output_path)
            else:
                status = "ffmpeg_failed"
                error = result.stderr.strip()[-2000:]

    burned_status = "not_requested"
    burned_error = ""
    burned_probe = {}
    burned_command = []
    if args.burn_subtitles:
        if not subtitle_rows:
            burned_status = "no_verified_subtitles"
        else:
            subtitle_filter = (
                f"subtitles=filename='{subtitle_path.name}':"
                + "force_style='"
                + f"FontName={args.subtitle_font_name},"
                + f"FontSize={args.subtitle_font_size},"
                + "PrimaryColour=&H00FFFFFF,"
                + "OutlineColour=&H00101010,"
                + "BorderStyle=1,Outline=2,Shadow=0,"
                + f"MarginV={args.subtitle_margin_v},Alignment=2'"
            )
            burned_command = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y" if args.overwrite else "-n",
                "-i",
                str(output_path),
                "-vf",
                subtitle_filter,
                "-map",
                "0:v:0",
                "-map",
                "0:a:0?",
            ]
            if args.encoder == "h264_nvenc":
                burned_command.extend(
                    ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", str(args.cq)]
                )
            else:
                burned_command.extend(
                    ["-c:v", "libx264", "-preset", "medium", "-crf", str(args.crf)]
                )
            burned_command.extend(
                [
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "copy",
                    "-movflags",
                    "+faststart",
                    str(burned_output_path),
                ]
            )
            (out_dir / "subtitle_burn_ffmpeg_command.txt").write_text(
                subprocess.list2cmdline(burned_command) + "\n",
                encoding="utf-8",
            )
            burned_status = "planned"
            if args.execute and status in {"ok", "exists"}:
                burned_subtitle_dir.mkdir(parents=True, exist_ok=True)
                if burned_output_path.exists() and not args.overwrite:
                    burned_status = "exists"
                    burned_probe = probe_mp4(burned_output_path)
                else:
                    burned_result = subprocess.run(
                        burned_command,
                        cwd=subtitle_dir,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    if burned_result.returncode == 0:
                        burned_status = "ok"
                        burned_probe = probe_mp4(burned_output_path)
                    else:
                        burned_status = "ffmpeg_failed"
                        burned_error = burned_result.stderr.strip()[-2000:]

    summary_path = out_dir / "sequence_build_summary.md"
    summary_lines = [
        "# Event Sequence Build",
        "",
        f"Sequence: {sequence_label}",
        f"Grouping authority: user-selected research range, not a proven official cdir chain",
        f"Events: {len(segment_rows)}",
        f"Event range: {indexes[0]}..{indexes[-1]}",
        f"Roots: {', '.join(sorted(roots))}",
        f"Source video duration: {total_duration_sec:.6f}s",
        f"Official OGG components: {len(audio_rows)}",
        f"EventCn OGG components: {sum(row['source_kind'] == 'EventCn' for row in audio_rows)}",
        f"Z2D dialogue OGG components: {sum(row['source_kind'] == 'Z2D_dialogue' for row in audio_rows)}",
        f"Verified Z2D subtitle rows: {len(subtitle_rows)}",
        f"Video compatibility sets: {len(compatibility)}",
        f"Video mode: {args.video_mode}",
        f"Status: {status}",
        f"Output: {output_path}",
        f"Subtitle file: {subtitle_path if subtitle_rows else '(none: no verified text in selected events)'}",
        f"Burned subtitle status: {burned_status}",
        f"Burned subtitle output: {burned_output_path if subtitle_rows and args.burn_subtitles else '(not generated)'}",
        "",
        "## Timing Policy",
        "- Each source video keeps its original duration; no per-event frozen-frame extension is used.",
        "- Event start time is the cumulative duration of all prior selected video segments.",
        "- Each official OGG starts at event start plus EventCn/ReqData component start_ms.",
        "- Z2D dialogue OGG and subtitle cues use exact GDB resource start/end frames at 30 fps.",
        "- Generated subtitle cues use the graphical layer end frame, not the longer voice tail.",
        "- Audio may continue naturally across following video segment boundaries.",
        "- Existing embedded MP4 audio is ignored.",
        "",
        "## Verification",
        f"- ffprobe_ok: {output_probe.get('probe_ok', '')}",
        f"- output_duration_sec: {output_probe.get('duration_sec', '')}",
        f"- output_video_codec: {output_probe.get('video_codec', '')}",
        f"- output_audio_codec: {output_probe.get('audio_codec', '')}",
        f"- burned_ffprobe_ok: {burned_probe.get('probe_ok', '')}",
        f"- burned_output_duration_sec: {burned_probe.get('duration_sec', '')}",
    ]
    if error:
        summary_lines.extend(["", "## Error", error])
    if burned_error:
        summary_lines.extend(["", "## Burned Subtitle Error", burned_error])
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    print(f"[build-event-sequence] events: {len(segment_rows)}")
    print(f"[build-event-sequence] duration: {total_duration_sec:.3f}s")
    print(f"[build-event-sequence] official OGG components: {len(audio_rows)}")
    print(f"[build-event-sequence] verified subtitles: {len(subtitle_rows)}")
    print(f"[build-event-sequence] status: {status}")
    print(f"[build-event-sequence] burned subtitle status: {burned_status}")
    print(f"[build-event-sequence] output: {output_path}")
    print(f"[build-event-sequence] wrote {summary_path}")


def command_subtitle_candidates(args):
    manifest_dir = Path(args.manifest_dir)
    hash_rows = read_csv(manifest_dir / "sound_hashreq_records.csv")
    sound_rows = {
        row.get("sound_resource_id", ""): row
        for row in read_csv(manifest_dir / "sound_request_audit.csv")
        if row.get("sound_resource_id")
    }
    smz_rows = {
        row.get("name_key", "").lower(): row
        for row in read_csv(manifest_dir / "smz_name_chunk_map.csv")
        if row.get("name_key")
    }

    rows = []
    for row in hash_rows:
        code_name = row.get("code_name", "")
        strict_dialogue = bool(re.search(r"セリフ|台詞", code_name))
        voice_label = bool(re.search(r"Voice|ボイス", code_name, re.IGNORECASE))
        if not strict_dialogue and not (args.include_voice and voice_label):
            continue
        if not args.include_control and re.search(r"停止|消音|ミュート|mute|stop", code_name, re.IGNORECASE):
            continue

        parsed = parse_code_name_label(code_name)
        sound = sound_rows.get(parsed["code"], {})
        media = row.get("first_smz_media", "")
        media_key = media.removesuffix(".smz").lower()
        smz = smz_rows.get(media_key, {})
        label_type = "dialogue" if strict_dialogue else "voice_label"
        rows.append(
            {
                "request_id": row.get("request_id", ""),
                "sound_code": parsed["code"],
                "label_type": label_type,
                "code_name": code_name,
                "label": parsed["label"],
                "speaker_hint": parsed["speaker_hint"],
                "subtitle_text": parsed["subtitle_text"],
                "sample_count_u32": row.get("sample_count_u32", ""),
                "duration_sec_at_header_rate": row.get("duration_sec_at_header_rate", ""),
                "first_smz_media": media,
                "smz_chunk_index": smz.get("chunk_index", ""),
                "smz_chunk_size": smz.get("size", ""),
                "smz_channel_guess": smz.get("channel_guess", ""),
                "has_runtime_smz": "yes" if smz else "no",
                "request_label": sound.get("request_label", ""),
                "suggested_ogg_name": sound.get("suggested_name", ""),
                "ogg_duration_sec": sound.get("ogg_duration_sec", ""),
                "nearest_media": sound.get("nearest_media", ""),
            }
        )

    rows.sort(key=lambda item: (parse_optional_int(item.get("sound_code")) or 0, parse_optional_int(item.get("request_id")) or 0))
    out_csv = manifest_dir / "subtitle_dialogue_candidates.csv"
    write_csv(
        out_csv,
        rows,
        [
            "request_id",
            "sound_code",
            "label_type",
            "code_name",
            "label",
            "speaker_hint",
            "subtitle_text",
            "sample_count_u32",
            "duration_sec_at_header_rate",
            "first_smz_media",
            "smz_chunk_index",
            "smz_chunk_size",
            "smz_channel_guess",
            "has_runtime_smz",
            "request_label",
            "suggested_ogg_name",
            "ogg_duration_sec",
            "nearest_media",
        ],
    )

    label_counts = Counter(row["label_type"] for row in rows)
    speaker_counts = Counter(row["speaker_hint"] or "(none)" for row in rows)
    has_smz = Counter(row["has_runtime_smz"] for row in rows)
    has_ogg = Counter("yes" if row["suggested_ogg_name"] else "no" for row in rows)

    summary_path = manifest_dir / "subtitle_dialogue_candidates_summary.md"
    lines = [
        "# Subtitle Dialogue Candidate Summary",
        "",
        f"Rows: {len(rows)}",
        f"Include voice labels: {'yes' if args.include_voice else 'no'}",
        f"Include control labels: {'yes' if args.include_control else 'no'}",
        "",
        "## Label Types",
    ]
    for key, count in sorted(label_counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {key}: {count}")
    lines.extend(["", "## Runtime SMZ"])
    for key, count in sorted(has_smz.items()):
        lines.append(f"- {key}: {count}")
    lines.extend(["", "## OGG Name Mapping"])
    for key, count in sorted(has_ogg.items()):
        lines.append(f"- {key}: {count}")
    lines.extend(["", "## Speaker Hints"])
    for key, count in speaker_counts.most_common(30):
        lines.append(f"- {key}: {count}")
    lines.extend(["", "## Examples"])
    for row in rows[:30]:
        lines.append(
            f"- code {row['sound_code']} request {row['request_id']}: "
            f"{row['speaker_hint']} / {row['subtitle_text'] or row['label']}"
        )
    lines.extend(
        [
            "",
            "## Limits",
            "- These rows are dialogue/voice text candidates, not timed subtitles.",
            "- Timing still requires an event timeline, decoded SMZ duration, or manual alignment to merged video.",
            "- `subtitle_text` is parsed from sound labels and may be abbreviated by the original table.",
        ]
    )
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[subtitle-candidates] wrote {out_csv}")
    print(f"[subtitle-candidates] wrote {summary_path}")


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


def run_single_hflip_video(source: Path, output: Path, encoder: str, crf: int, cq: int, overwrite: bool) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and not overwrite:
        return {
            "source": str(source),
            "output": str(output),
            "status": "skipped_exists",
            "returncode": "",
            "error": "",
        }

    cmd = ["ffmpeg", "-y", "-i", str(source), "-map", "0", "-vf", "hflip"]
    if encoder == "h264_nvenc":
        cmd.extend(["-c:v", "h264_nvenc", "-preset", "p6", "-cq", str(cq), "-pix_fmt", "yuv420p"])
    else:
        cmd.extend(["-c:v", "libx264", "-crf", str(crf), "-pix_fmt", "yuv420p"])
    cmd.extend(["-c:a", "copy", "-c:s", "copy", str(output)])
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return {
        "source": str(source),
        "output": str(output),
        "status": "ok" if result.returncode == 0 else "failed",
        "returncode": result.returncode,
        "error": "" if result.returncode == 0 else result.stderr.strip()[-4000:],
    }


def command_hflip_videos(args):
    input_dir = Path(args.input_dir)
    out_dir = Path(args.out_dir)
    files = sorted(input_dir.rglob("*.mp4"), key=lambda path: natural_key(str(path.relative_to(input_dir))))
    if args.limit:
        files = files[: args.limit]
    rows = []
    manifest_path = out_dir / "hflip_manifest.csv"

    print(f"[hflip-videos] input: {input_dir}")
    print(f"[hflip-videos] output: {out_dir}")
    print(f"[hflip-videos] files: {len(files)}")
    if not args.execute:
        for source in files:
            output = out_dir / source.relative_to(input_dir)
            rows.append(
                {
                    "source": str(source),
                    "output": str(output),
                    "status": "dry_run",
                    "returncode": "",
                    "error": "",
                }
            )
        write_csv(manifest_path, rows, ["source", "output", "status", "returncode", "error"])
        print(f"[hflip-videos] dry-run wrote {manifest_path}")
        return

    processed = 0
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = []
        for source in files:
            output = out_dir / source.relative_to(input_dir)
            futures.append(executor.submit(run_single_hflip_video, source, output, args.encoder, args.crf, args.cq, args.overwrite))
        for future in as_completed(futures):
            rows.append(future.result())
            processed += 1
            if processed % 250 == 0 or processed == len(files):
                print(f"[hflip-videos] processed {processed}/{len(files)}")

    rows.sort(key=lambda row: natural_key(row["source"]))
    write_csv(manifest_path, rows, ["source", "output", "status", "returncode", "error"])
    counts = Counter(row["status"] for row in rows)
    summary_path = out_dir / "hflip_summary.md"
    lines = [
        "# HFlip Video Summary",
        "",
        f"Input: {input_dir}",
        f"Output: {out_dir}",
        f"Files: {len(rows)}",
        f"Encoder: {args.encoder}",
        "",
        "## Status",
        *[f"- {key}: {count}" for key, count in sorted(counts.items())],
        "",
        "## Notes",
        "- Output preserves the source directory layout.",
        "- Video is horizontally flipped and re-encoded; audio streams are copied without re-encoding.",
        "- The source tree is not modified.",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[hflip-videos] wrote {manifest_path}")
    print(f"[hflip-videos] wrote {summary_path}")


def inspect_pcmraw(path: Path, header_bytes: int) -> dict:
    raw_size = path.stat().st_size
    with path.open("rb") as handle:
        header = handle.read(header_bytes)
    words = []
    if len(header) >= 4:
        for offset in range(0, min(len(header), 32), 4):
            if offset + 4 <= len(header):
                words.append(struct.unpack_from("<I", header, offset)[0])
    payload_size = max(0, raw_size - header_bytes)
    return {
        "raw_size": raw_size,
        "payload_size": payload_size,
        "header_words_hex": " ".join(f"0x{word:08x}" for word in words),
        "header0_payload_match": "yes" if words and words[0] == payload_size else "no",
    }


def probe_audio_stream(path: Path) -> dict:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "stream=codec_name,sample_rate,channels,duration",
        "-of",
        "json",
        str(path),
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        return {
            "probe_ok": "no",
            "probe_error": result.stderr.strip(),
            "codec": "",
            "sample_rate": "",
            "channels": "",
            "duration_sec": "",
        }
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        return {
            "probe_ok": "no",
            "probe_error": str(exc),
            "codec": "",
            "sample_rate": "",
            "channels": "",
            "duration_sec": "",
        }
    streams = payload.get("streams") or []
    if not streams:
        return {
            "probe_ok": "no",
            "probe_error": "no streams",
            "codec": "",
            "sample_rate": "",
            "channels": "",
            "duration_sec": "",
        }
    stream = streams[0]
    return {
        "probe_ok": "yes",
        "probe_error": "",
        "codec": stream.get("codec_name", ""),
        "sample_rate": stream.get("sample_rate", ""),
        "channels": stream.get("channels", ""),
        "duration_sec": stream.get("duration", ""),
    }


def convert_one_pcmraw_to_wav(source: Path, output: Path, args) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    info = inspect_pcmraw(source, args.skip_header_bytes)
    row = {
        "source": str(source),
        "output": str(output),
        "status": "",
        "returncode": "",
        "error": "",
        **info,
        "codec": "",
        "sample_rate": "",
        "channels": "",
        "duration_sec": "",
        "audio_volume_ok": "",
        "mean_volume_db": "",
        "max_volume_db": "",
        "audible_audio": "",
    }

    if output.exists() and not args.overwrite:
        row["status"] = "skipped_exists"
    else:
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-nostats",
            "-f",
            "s16le",
            "-ar",
            str(args.sample_rate),
            "-ac",
            str(args.channels),
            "-skip_initial_bytes",
            str(args.skip_header_bytes),
            "-i",
            str(source),
            str(output),
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        row["status"] = "ok" if result.returncode == 0 else "failed"
        row["returncode"] = result.returncode
        row["error"] = "" if result.returncode == 0 else (result.stderr or result.stdout).strip()[-4000:]

    if output.exists() and row["status"] != "failed":
        probe = probe_audio_stream(output)
        row.update(
            {
                "codec": probe["codec"],
                "sample_rate": probe["sample_rate"],
                "channels": probe["channels"],
                "duration_sec": probe["duration_sec"],
            }
        )
        if args.audio_volume:
            volume = probe_audio_volume(output)
            max_volume = volume.pop("max_volume_value")
            row.update(
                {
                    "audio_volume_ok": "yes" if volume["audio_volume_ok"] else "no",
                    "mean_volume_db": volume["mean_volume_db"],
                    "max_volume_db": volume["max_volume_db"],
                    "audible_audio": "yes" if max_volume is not None and max_volume > args.silent_threshold_db else "no",
                }
            )
            if volume["audio_volume_error"]:
                row["error"] = volume["audio_volume_error"][-4000:]
    return row


def command_convert_pcm_wav(args):
    input_dir = Path(args.input_dir)
    out_dir = Path(args.out_dir)
    files = sorted(input_dir.rglob("*.pcmraw"), key=lambda path: natural_key(str(path.relative_to(input_dir))))
    if args.limit:
        files = files[: args.limit]
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[convert-pcm-wav] input: {input_dir}")
    print(f"[convert-pcm-wav] output: {out_dir}")
    print(f"[convert-pcm-wav] files: {len(files)}")
    print(
        f"[convert-pcm-wav] format: s16le, {args.sample_rate} Hz, "
        f"{args.channels} ch, skip {args.skip_header_bytes} bytes"
    )

    rows = []
    if not args.execute:
        for source in files:
            output = out_dir / source.relative_to(input_dir).with_suffix(".wav")
            rows.append(
                {
                    "source": str(source),
                    "output": str(output),
                    "status": "dry_run",
                    "returncode": "",
                    "error": "",
                    **inspect_pcmraw(source, args.skip_header_bytes),
                    "codec": "",
                    "sample_rate": "",
                    "channels": "",
                    "duration_sec": "",
                    "audio_volume_ok": "",
                    "mean_volume_db": "",
                    "max_volume_db": "",
                    "audible_audio": "",
                }
            )
    else:
        processed = 0
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = []
            for source in files:
                output = out_dir / source.relative_to(input_dir).with_suffix(".wav")
                futures.append(executor.submit(convert_one_pcmraw_to_wav, source, output, args))
            for future in as_completed(futures):
                rows.append(future.result())
                processed += 1
                if processed % 25 == 0 or processed == len(files):
                    print(f"[convert-pcm-wav] processed {processed}/{len(files)}")

    rows.sort(key=lambda row: natural_key(row["source"]))
    fields = [
        "source",
        "output",
        "status",
        "returncode",
        "error",
        "raw_size",
        "payload_size",
        "header_words_hex",
        "header0_payload_match",
        "codec",
        "sample_rate",
        "channels",
        "duration_sec",
        "audio_volume_ok",
        "mean_volume_db",
        "max_volume_db",
        "audible_audio",
    ]
    manifest_path = out_dir / "pcm_wav_manifest.csv"
    write_csv(manifest_path, rows, fields)
    counts = Counter(row["status"] for row in rows)
    audible_counts = Counter(row["audible_audio"] or "not_checked" for row in rows)
    summary_path = out_dir / "pcm_wav_summary.md"
    lines = [
        "# PCM WAV Conversion Summary",
        "",
        f"Input: {input_dir}",
        f"Output: {out_dir}",
        f"Files: {len(rows)}",
        f"Format: s16le, {args.sample_rate} Hz, {args.channels} ch",
        f"Skipped header bytes: {args.skip_header_bytes}",
        "",
        "## Status",
        *[f"- {key}: {count}" for key, count in sorted(counts.items())],
        "",
        "## Audio volume",
        *[f"- {key}: {count}" for key, count in sorted(audible_counts.items())],
        "",
        "## Notes",
        "- Source `.pcmraw` files are not modified.",
        "- The observed Magia Record slot PCM chunks use a 32-byte custom header before raw PCM payload.",
        "- The default 48 kHz stereo output matches the dominant OGG resource sample rate and the observed PCM header channel field.",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[convert-pcm-wav] wrote {manifest_path}")
    print(f"[convert-pcm-wav] wrote {summary_path}")


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

    pcm_wav = sub.add_parser("convert-pcm-wav", help="wrap exported .pcmraw chunks as playable WAV files; dry-run by default")
    pcm_wav.add_argument("--input-dir", required=True)
    pcm_wav.add_argument("--out-dir", required=True)
    pcm_wav.add_argument("--execute", action="store_true")
    pcm_wav.add_argument("--overwrite", action="store_true")
    pcm_wav.add_argument("--workers", type=int, default=4)
    pcm_wav.add_argument("--limit", type=int, default=0)
    pcm_wav.add_argument("--sample-rate", type=int, default=48000)
    pcm_wav.add_argument("--channels", type=int, default=2)
    pcm_wav.add_argument("--skip-header-bytes", type=int, default=32)
    pcm_wav.add_argument("--audio-volume", action="store_true", help="run ffmpeg volumedetect on generated WAV files")
    pcm_wav.add_argument("--silent-threshold-db", type=float, default=-60.0)
    pcm_wav.set_defaults(func=command_convert_pcm_wav)

    export_images = sub.add_parser("export-images", help="export z2d chunks; dry-run by default")
    export_images.add_argument("--out-dir", default=str(DEFAULT_OUTPUT_DIR))
    export_images.add_argument("--execute", action="store_true")
    export_images.add_argument("--limit", type=int)
    export_images.set_defaults(func=command_export_images)

    z2d_map = sub.add_parser(
        "z2d-name-map",
        help="map native Z2D names exactly to z2d.bin chunks and optionally extract a focused prefix",
    )
    z2d_map.add_argument("--native-lib", default=str(DEFAULT_NATIVE_LIB_PATH))
    z2d_map.add_argument("--z2d-bin", default=str(CHUNK_ARCHIVES["z2d"][0]))
    z2d_map.add_argument("--z2d-add", default=str(CHUNK_ARCHIVES["z2d"][1]))
    z2d_map.add_argument("--out-dir", required=True)
    z2d_map.add_argument(
        "--name-table-offset",
        type=lambda value: int(value, 0),
        default=Z2D_NATIVE_NAME_TABLE_OFFSET,
    )
    z2d_map.add_argument("--name-count", type=int, default=Z2D_NATIVE_NAME_COUNT)
    z2d_map.add_argument("--focus-prefix", default="")
    z2d_map.add_argument("--extract", action="store_true")
    z2d_map.add_argument("--overwrite", action="store_true")
    z2d_map.set_defaults(func=command_z2d_name_map)

    subtitle_z2d = sub.add_parser(
        "subtitle-z2d-catalog",
        help="decode graphical Z2D subtitle text and join it to official OGG audio",
    )
    subtitle_z2d.add_argument("--native-lib", default=str(DEFAULT_NATIVE_LIB_PATH))
    subtitle_z2d.add_argument("--z2d-bin", default=str(CHUNK_ARCHIVES["z2d"][0]))
    subtitle_z2d.add_argument("--z2d-add", default=str(CHUNK_ARCHIVES["z2d"][1]))
    subtitle_z2d.add_argument("--sound-request-table", default=str(SOUND_REQUEST_TABLE_PATH))
    subtitle_z2d.add_argument("--sound-hashreq-table", default=str(SOUND_HASHREQ_TABLE_PATH))
    subtitle_z2d.add_argument("--gdb-path", default=str(GDB_PATH))
    subtitle_z2d.add_argument("--event-timeline-csv", default="")
    subtitle_z2d.add_argument("--frame-rate", type=float, default=30.0)
    subtitle_z2d.add_argument("--ogg-dir", required=True)
    subtitle_z2d.add_argument("--out-dir", required=True)
    subtitle_z2d.add_argument(
        "--name-table-offset",
        type=lambda value: int(value, 0),
        default=Z2D_NATIVE_NAME_TABLE_OFFSET,
    )
    subtitle_z2d.add_argument("--name-count", type=int, default=Z2D_NATIVE_NAME_COUNT)
    subtitle_z2d.add_argument("--focus-prefix", default="")
    subtitle_z2d.add_argument("--link-mode", choices=["hardlink", "copy"], default="hardlink")
    subtitle_z2d.add_argument("--execute", action="store_true")
    subtitle_z2d.add_argument("--overwrite", action="store_true")
    subtitle_z2d.set_defaults(func=command_subtitle_z2d_catalog)

    cri_video_map = sub.add_parser(
        "cri-video-name-map",
        help="map the native 7801 CRI resource names exactly to main/patch MP4 slices",
    )
    cri_video_map.add_argument("--native-lib", default=str(DEFAULT_NATIVE_LIB_PATH))
    cri_video_map.add_argument("--video-dir", required=True)
    cri_video_map.add_argument("--out-dir", required=True)
    cri_video_map.add_argument(
        "--name-table-va",
        type=lambda value: int(value, 0),
        default=CRI_NATIVE_POINTER_TABLE_VA,
    )
    cri_video_map.add_argument("--name-count", type=int, default=CRI_NATIVE_NAME_COUNT)
    cri_video_map.add_argument("--focus-prefix", default="")
    cri_video_map.add_argument("--link-mode", choices=["hardlink", "copy"], default="hardlink")
    cri_video_map.add_argument("--execute", action="store_true")
    cri_video_map.add_argument("--overwrite", action="store_true")
    cri_video_map.set_defaults(func=command_cri_video_name_map)

    z2d_dgm_map = sub.add_parser(
        "z2d-dgm-event-map",
        help="map GDB events through Z2D DGM dependencies to exact native CRI videos",
    )
    z2d_dgm_map.add_argument("--native-lib", default=str(DEFAULT_NATIVE_LIB_PATH))
    z2d_dgm_map.add_argument("--z2d-bin", default=str(CHUNK_ARCHIVES["z2d"][0]))
    z2d_dgm_map.add_argument("--z2d-add", default=str(CHUNK_ARCHIVES["z2d"][1]))
    z2d_dgm_map.add_argument("--gdb-path", default=str(GDB_PATH))
    z2d_dgm_map.add_argument("--cri-map-csv", required=True)
    z2d_dgm_map.add_argument(
        "--video-metadata-csv",
        default=str(DEFAULT_MANIFEST_DIR / "video_review_items.csv"),
    )
    z2d_dgm_map.add_argument("--out-dir", required=True)
    z2d_dgm_map.add_argument(
        "--name-table-offset",
        type=lambda value: int(value, 0),
        default=Z2D_NATIVE_NAME_TABLE_OFFSET,
    )
    z2d_dgm_map.add_argument("--name-count", type=int, default=Z2D_NATIVE_NAME_COUNT)
    z2d_dgm_map.add_argument("--frame-rate", type=float, default=30.0)
    z2d_dgm_map.add_argument("--probe-missing", action="store_true")
    z2d_dgm_map.add_argument("--workers", type=int, default=16)
    z2d_dgm_map.set_defaults(func=command_z2d_dgm_event_map)

    build_dgm_layers = sub.add_parser(
        "build-event-dgm-layers",
        help="build official contiguous DGM layer tracks for one GDB event",
    )
    build_dgm_layers.add_argument("--event-map-csv", required=True)
    build_dgm_layers.add_argument("--event-name", required=True)
    build_dgm_layers.add_argument("--out-dir", required=True)
    build_dgm_layers.add_argument(
        "--canvas-select",
        default="",
        help="optional Z2D root canvas filter in WIDTHxHEIGHT form",
    )
    build_dgm_layers.add_argument("--frame-rate", type=float, default=30.0)
    build_dgm_layers.add_argument(
        "--target-duration-sec",
        type=float,
        default=0.0,
        help="optional final duration used when repeating an official _LP cycle",
    )
    build_dgm_layers.add_argument(
        "--video-mode",
        choices=["copy", "encode"],
        default="copy",
    )
    build_dgm_layers.add_argument(
        "--encoder",
        choices=["libx264", "h264_nvenc"],
        default="h264_nvenc",
    )
    build_dgm_layers.add_argument("--crf", type=int, default=16)
    build_dgm_layers.add_argument("--cq", type=int, default=19)
    build_dgm_layers.add_argument("--execute", action="store_true")
    build_dgm_layers.add_argument("--overwrite", action="store_true")
    build_dgm_layers.set_defaults(func=command_build_event_dgm_layers)

    build_dgm_composite = sub.add_parser(
        "build-event-dgm-composite",
        help="compose exact GDB/Z2D/DGM/CRI layers with official Z2D OGG and subtitles",
    )
    build_dgm_composite.add_argument("--event-map-csv", required=True)
    build_dgm_composite.add_argument("--subtitle-timeline-csv", required=True)
    build_dgm_composite.add_argument(
        "--event-audio-components-csv",
        default="",
        help="optional EventCn event_audio_components.csv for official event sound tracks",
    )
    build_dgm_composite.add_argument(
        "--audio-signal-audit-csv",
        default="",
        help="optional signal audit; only rows with audible=yes are mixed",
    )
    build_dgm_composite.add_argument("--event-name", required=True)
    build_dgm_composite.add_argument("--out-dir", required=True)
    build_dgm_composite.add_argument(
        "--canvas-select",
        default="",
        help="required for mixed-canvas events; selects one Z2D root canvas",
    )
    build_dgm_composite.add_argument("--frame-rate", type=float, default=30.0)
    build_dgm_composite.add_argument(
        "--canvas-width",
        type=int,
        default=0,
        help="output width; 0 derives it from decoded Z2D layer extents",
    )
    build_dgm_composite.add_argument(
        "--canvas-height",
        type=int,
        default=0,
        help="output height; 0 derives it from decoded Z2D layer extents",
    )
    build_dgm_composite.add_argument("--black-similarity", type=float, default=0.08)
    build_dgm_composite.add_argument("--black-blend", type=float, default=0.12)
    build_dgm_composite.add_argument(
        "--layer-eof-policy",
        choices=["pass", "hold-base", "hold-all"],
        default="hold-base",
        help="what to do after a DGM layer ends; hold-base is intended for watchable output",
    )
    build_dgm_composite.add_argument(
        "--encoder",
        choices=["libx264", "h264_nvenc"],
        default="h264_nvenc",
    )
    build_dgm_composite.add_argument("--crf", type=int, default=16)
    build_dgm_composite.add_argument("--cq", type=int, default=19)
    build_dgm_composite.add_argument("--burn-subtitles", action="store_true")
    build_dgm_composite.add_argument("--subtitle-font-name", default="Yu Gothic")
    build_dgm_composite.add_argument("--subtitle-font-size", type=int, default=26)
    build_dgm_composite.add_argument("--subtitle-margin-v", type=int, default=64)
    build_dgm_composite.add_argument("--execute", action="store_true")
    build_dgm_composite.add_argument("--overwrite", action="store_true")
    build_dgm_composite.set_defaults(func=command_build_event_dgm_composite)

    production_plan = sub.add_parser(
        "event-production-plan",
        help="build one authoritative production row per exact event and Z2D canvas",
    )
    production_plan.add_argument("--event-map-csv", required=True)
    production_plan.add_argument("--subtitle-timeline-csv", required=True)
    production_plan.add_argument("--event-audio-components-csv", required=True)
    production_plan.add_argument("--audio-signal-audit-csv", default="")
    production_plan.add_argument("--out-dir", required=True)
    production_plan.add_argument("--frame-rate", type=float, default=30.0)
    production_plan.set_defaults(func=command_event_production_plan)

    bilibili_plan = sub.add_parser(
        "bilibili-part-plan",
        help="group authoritative event/canvas outputs into reviewable upload parts",
    )
    bilibili_plan.add_argument("--production-plan-csv", required=True)
    bilibili_plan.add_argument("--event-timeline-events-csv", required=True)
    bilibili_plan.add_argument("--out-dir", required=True)
    bilibili_plan.add_argument("--event-output-root", default="")
    bilibili_plan.add_argument("--category", action="append")
    bilibili_plan.add_argument("--audible-only", action="store_true")
    bilibili_plan.add_argument("--target-part-sec", type=float, default=1200.0)
    bilibili_plan.add_argument("--max-events-per-part", type=int, default=100)
    bilibili_plan.add_argument("--spacer-sec", type=float, default=0.25)
    bilibili_plan.add_argument("--upload-canvas", default="1920x1080")
    bilibili_plan.set_defaults(func=command_bilibili_part_plan)

    bilibili_upload_review = sub.add_parser(
        "bilibili-upload-review",
        help="build a human-review table for part titles and upload descriptions",
    )
    bilibili_upload_review.add_argument("--parts-csv", required=True)
    bilibili_upload_review.add_argument("--root-labels-csv", required=True)
    bilibili_upload_review.add_argument("--out-dir", required=True)
    bilibili_upload_review.add_argument(
        "--label-diversity-threshold",
        type=int,
        default=8,
    )
    bilibili_upload_review.add_argument("--max-title-length", type=int, default=80)
    bilibili_upload_review.set_defaults(func=command_bilibili_upload_review)

    event_output_audit = sub.add_parser(
        "event-output-audit",
        help="verify event MP4 streams, durations, and actual decoded audio levels",
    )
    event_output_audit.add_argument("--sequence-csv", required=True)
    event_output_audit.add_argument("--out-dir", required=True)
    event_output_audit.add_argument(
        "--edition",
        choices=["no-subtitles", "subtitles"],
        default="no-subtitles",
    )
    event_output_audit.add_argument("--threshold-db", type=float, default=-80.0)
    event_output_audit.add_argument(
        "--duration-tolerance-sec",
        type=float,
        default=0.12,
    )
    event_output_audit.add_argument("--workers", type=int, default=16)
    event_output_audit.set_defaults(func=command_event_output_audit)

    build_bilibili_part = sub.add_parser(
        "build-bilibili-part",
        help="normalize and concatenate planned event outputs into upload parts",
    )
    build_bilibili_part.add_argument("--sequence-csv", required=True)
    build_bilibili_part.add_argument("--parts-csv", required=True)
    build_bilibili_part.add_argument("--out-dir", required=True)
    build_bilibili_part.add_argument("--reuse-sequence-csv", default="")
    build_bilibili_part.add_argument("--reuse-parts-csv", default="")
    build_bilibili_part.add_argument("--reuse-output-dir", default="")
    build_bilibili_part.add_argument("--part-number", type=int, action="append")
    build_bilibili_part.add_argument("--part-key", action="append")
    build_bilibili_part.add_argument("--all-parts", action="store_true")
    build_bilibili_part.add_argument(
        "--edition",
        choices=["no-subtitles", "subtitles", "both"],
        default="both",
    )
    build_bilibili_part.add_argument("--upload-canvas", default="1920x1080")
    build_bilibili_part.add_argument("--fps", type=int, default=30)
    build_bilibili_part.add_argument(
        "--encoder",
        choices=["libx264", "h264_nvenc"],
        default="h264_nvenc",
    )
    build_bilibili_part.add_argument("--crf", type=int, default=16)
    build_bilibili_part.add_argument("--cq", type=int, default=19)
    build_bilibili_part.add_argument("--audio-bitrate", default="192k")
    build_bilibili_part.add_argument("--loudness-i", type=float, default=-16.0)
    build_bilibili_part.add_argument("--true-peak-db", type=float, default=-3.0)
    build_bilibili_part.add_argument("--threshold-db", type=float, default=-80.0)
    build_bilibili_part.add_argument("--cleanup-work", action="store_true")
    build_bilibili_part.add_argument("--execute", action="store_true")
    build_bilibili_part.add_argument("--overwrite", action="store_true")
    build_bilibili_part.set_defaults(func=command_build_bilibili_part)

    bilibili_part_output_audit = sub.add_parser(
        "bilibili-part-output-audit",
        help="verify completed upload parts and subtitle storage relations",
    )
    bilibili_part_output_audit.add_argument("--parts-csv", required=True)
    bilibili_part_output_audit.add_argument("--output-dir", required=True)
    bilibili_part_output_audit.add_argument("--out-dir", required=True)
    bilibili_part_output_audit.add_argument(
        "--upload-canvas",
        default="1920x1080",
    )
    bilibili_part_output_audit.add_argument("--fps", type=float, default=30.0)
    bilibili_part_output_audit.add_argument(
        "--fps-tolerance",
        type=float,
        default=0.05,
    )
    bilibili_part_output_audit.add_argument(
        "--video-codec",
        default="h264",
    )
    bilibili_part_output_audit.add_argument(
        "--audio-codec",
        default="aac",
    )
    bilibili_part_output_audit.add_argument(
        "--audio-sample-rate",
        type=int,
        default=48000,
    )
    bilibili_part_output_audit.add_argument(
        "--audio-channels",
        type=int,
        default=2,
    )
    bilibili_part_output_audit.add_argument(
        "--threshold-db",
        type=float,
        default=-80.0,
    )
    bilibili_part_output_audit.add_argument(
        "--max-peak-db",
        type=float,
        default=-0.5,
    )
    bilibili_part_output_audit.add_argument(
        "--duration-tolerance-sec",
        type=float,
        default=0.20,
    )
    bilibili_part_output_audit.add_argument("--workers", type=int, default=4)
    bilibili_part_output_audit.set_defaults(
        func=command_bilibili_part_output_audit
    )

    subtitle_burn_audit = sub.add_parser(
        "subtitle-burn-audit",
        help="verify that burned-subtitle frames differ at actual SRT cue times",
    )
    subtitle_burn_audit.add_argument("--sequence-csv", required=True)
    subtitle_burn_audit.add_argument("--out-dir", required=True)
    subtitle_burn_audit.add_argument("--max-samples", type=int, default=3)
    subtitle_burn_audit.add_argument(
        "--difference-threshold",
        type=float,
        default=0.5,
    )
    subtitle_burn_audit.add_argument("--workers", type=int, default=4)
    subtitle_burn_audit.set_defaults(func=command_subtitle_burn_audit)

    rebuild_event_audio = sub.add_parser(
        "rebuild-event-audio",
        help="copy event video streams and rebuild limited audio from official OGG manifests",
    )
    rebuild_event_audio.add_argument("--sequence-csv", required=True)
    rebuild_event_audio.add_argument("--out-dir", required=True)
    rebuild_event_audio.add_argument(
        "--edition",
        choices=["no-subtitles", "subtitles", "both"],
        default="both",
    )
    rebuild_event_audio.add_argument("--audio-bitrate", default="256k")
    rebuild_event_audio.add_argument("--limiter-limit", type=float, default=0.85)
    rebuild_event_audio.add_argument("--output-gain-db", type=float, default=-3.0)
    rebuild_event_audio.add_argument("--max-peak-db", type=float, default=-0.5)
    rebuild_event_audio.add_argument("--workers", type=int, default=8)
    rebuild_event_audio.add_argument("--limit", type=int, default=0)
    rebuild_event_audio.add_argument("--execute", action="store_true")
    rebuild_event_audio.add_argument("--overwrite", action="store_true")
    rebuild_event_audio.set_defaults(func=command_rebuild_event_audio)

    build_dgm_batch = sub.add_parser(
        "build-event-dgm-batch",
        help="build a recoverable batch of exact event/canvas composites",
    )
    build_dgm_batch.add_argument("--production-plan-csv", required=True)
    build_dgm_batch.add_argument("--event-map-csv", required=True)
    build_dgm_batch.add_argument("--subtitle-timeline-csv", required=True)
    build_dgm_batch.add_argument("--event-audio-components-csv", required=True)
    build_dgm_batch.add_argument("--audio-signal-audit-csv", default="")
    build_dgm_batch.add_argument("--out-dir", required=True)
    build_dgm_batch.add_argument("--category", action="append")
    build_dgm_batch.add_argument("--event-root", action="append")
    build_dgm_batch.add_argument("--event-name", action="append")
    build_dgm_batch.add_argument("--canvas", action="append")
    build_dgm_batch.add_argument("--require-audio", action="store_true")
    build_dgm_batch.add_argument("--only-subtitles", action="store_true")
    build_dgm_batch.add_argument("--skip-mixed-canvas", action="store_true")
    build_dgm_batch.add_argument("--start-index", type=int, default=0)
    build_dgm_batch.add_argument("--limit", type=int, default=0)
    build_dgm_batch.add_argument("--frame-rate", type=float, default=30.0)
    build_dgm_batch.add_argument("--black-similarity", type=float, default=0.08)
    build_dgm_batch.add_argument("--black-blend", type=float, default=0.12)
    build_dgm_batch.add_argument(
        "--layer-eof-policy",
        choices=["pass", "hold-base", "hold-all"],
        default="hold-base",
    )
    build_dgm_batch.add_argument(
        "--encoder",
        choices=["libx264", "h264_nvenc"],
        default="h264_nvenc",
    )
    build_dgm_batch.add_argument("--crf", type=int, default=16)
    build_dgm_batch.add_argument("--cq", type=int, default=19)
    build_dgm_batch.add_argument("--burn-subtitles", action="store_true")
    build_dgm_batch.add_argument("--subtitle-font-name", default="Yu Gothic")
    build_dgm_batch.add_argument("--subtitle-font-size", type=int, default=26)
    build_dgm_batch.add_argument("--subtitle-margin-v", type=int, default=64)
    build_dgm_batch.add_argument("--cleanup-layers", action="store_true")
    build_dgm_batch.add_argument("--execute", action="store_true")
    build_dgm_batch.add_argument("--overwrite", action="store_true")
    build_dgm_batch.set_defaults(func=command_build_event_dgm_batch)

    audio_signal = sub.add_parser(
        "audio-signal-audit",
        help="measure actual decoded audio levels and separate silent control resources",
    )
    audio_signal.add_argument("--input-dir", required=True)
    audio_signal.add_argument("--out-dir", required=True)
    audio_signal.add_argument(
        "--extension",
        action="append",
        default=[".ogg"],
        help="file extension to scan; repeat for multiple extensions",
    )
    audio_signal.add_argument("--threshold-db", type=float, default=-80.0)
    audio_signal.add_argument("--workers", type=int, default=16)
    audio_signal.set_defaults(func=command_audio_signal_audit)

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
    sound_media.add_argument("--sound-request-struct-requests", default=str(DEFAULT_MANIFEST_DIR / "sound_request_struct_requests.csv"))
    sound_media.add_argument("--sound-request-struct-reqdata", default=str(DEFAULT_MANIFEST_DIR / "sound_request_struct_reqdata.csv"))
    sound_media.add_argument("--hashreq-table", default=str(SOUND_HASHREQ_TABLE_PATH))
    sound_media.add_argument("--native-lib", default=str(DEFAULT_NATIVE_LIB_PATH))
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
    special.add_argument("--audio-volume", action="store_true", help="run ffmpeg volumedetect for MP4s with audio streams")
    special.add_argument(
        "--silent-threshold-db",
        type=float,
        default=-60.0,
        help="max_volume threshold used to classify silent audio tracks when --audio-volume is set",
    )
    special.set_defaults(func=command_review_special_videos)

    motion = sub.add_parser("motion-audit", help="probe MP4 motion/static traits and collect review cases")
    motion.add_argument("--video-dir", required=True)
    motion.add_argument("--out-dir", default="")
    motion.add_argument("--mode", choices=["copy", "hardlink"], default="hardlink")
    motion.add_argument("--workers", type=int, default=4)
    motion.add_argument("--limit", type=int, default=0)
    motion.add_argument("--sample-fps", type=float, default=5.0)
    motion.add_argument("--max-frames", type=int, default=180)
    motion.add_argument("--very-short-threshold-sec", type=float, default=1.0)
    motion.add_argument("--short-threshold-sec", type=float, default=2.0)
    motion.add_argument("--static-threshold", type=float, default=0.5)
    motion.add_argument("--low-motion-threshold", type=float, default=3.0)
    motion.add_argument("--audio-volume", action="store_true", help="run ffmpeg volumedetect for MP4s with audio streams")
    motion.add_argument("--silent-threshold-db", type=float, default=-60.0)
    motion.add_argument("--collect-review", action="store_true", help="hardlink/copy non-normal classes into review folders")
    motion.set_defaults(func=command_motion_audit)

    subtitles = sub.add_parser("subtitle-candidates", help="export dialogue/voice label candidates for later subtitle work")
    subtitles.add_argument("--manifest-dir", default=str(DEFAULT_MANIFEST_DIR))
    subtitles.add_argument("--include-voice", action="store_true", help="include non-dialogue Voice/ボイス labels")
    subtitles.add_argument("--include-control", action="store_true", help="include stop/mute/control labels")
    subtitles.set_defaults(func=command_subtitle_candidates)

    event_timeline = sub.add_parser(
        "event-timeline-audit",
        help="parse EventCn animation events and join official SND requests, video slices, SMZ, and OGG",
    )
    event_timeline.add_argument("--event-cn", default=str(EVENT_CN_PATH))
    event_timeline.add_argument("--manifest-dir", default=str(DEFAULT_MANIFEST_DIR))
    event_timeline.add_argument("--out-dir", default="")
    event_timeline.add_argument("--video-dir", default="")
    event_timeline.add_argument("--ogg-dir", default="")
    event_timeline.set_defaults(func=command_event_timeline_audit)

    build_event = sub.add_parser(
        "build-event-videos",
        help="rebuild event MP4 audio from the official EventCn/request/OGG timeline",
    )
    build_event.add_argument("--timeline-dir", required=True)
    build_event.add_argument("--out-dir", required=True)
    build_event.add_argument(
        "--focus-root",
        default="",
        help="optional comma-separated exact EventCn roots such as ac0902",
    )
    build_event.add_argument("--event-start", type=int, default=None, help="inclusive EventCn event index")
    build_event.add_argument("--event-end", type=int, default=None, help="inclusive EventCn event index")
    build_event.add_argument("--audible-only", action="store_true")
    build_event.add_argument("--execute", action="store_true")
    build_event.add_argument("--overwrite", action="store_true")
    build_event.add_argument("--workers", type=int, default=2)
    build_event.add_argument("--encoder", choices=["libx264", "h264_nvenc"], default="h264_nvenc")
    build_event.add_argument(
        "--max-tail-sec",
        type=float,
        default=3.0,
        help="maximum last-frame extension used to preserve an event audio tail",
    )
    build_event.add_argument("--limit", type=int, default=0)
    build_event.set_defaults(func=command_build_event_videos)

    build_sequence = sub.add_parser(
        "build-event-sequence",
        help="concatenate a selected event range and mix official OGG on one cumulative timeline",
    )
    build_sequence.add_argument("--timeline-dir", required=True)
    build_sequence.add_argument("--out-dir", required=True)
    build_sequence.add_argument(
        "--subtitle-timeline-csv",
        default="",
        help="optional subtitle_event_timeline.csv with exact GDB frame timing and official OGG",
    )
    build_sequence.add_argument("--focus-root", default="")
    build_sequence.add_argument("--event-start", type=int, default=None)
    build_sequence.add_argument("--event-end", type=int, default=None)
    build_sequence.add_argument("--sequence-name", default="")
    build_sequence.add_argument("--limit", type=int, default=0)
    build_sequence.add_argument("--allow-event-gaps", action="store_true")
    build_sequence.add_argument("--allow-mixed-roots", action="store_true")
    build_sequence.add_argument("--video-mode", choices=["copy", "encode"], default="copy")
    build_sequence.add_argument("--encoder", choices=["libx264", "h264_nvenc"], default="h264_nvenc")
    build_sequence.add_argument("--crf", type=int, default=16)
    build_sequence.add_argument("--cq", type=int, default=19)
    build_sequence.add_argument("--burn-subtitles", action="store_true")
    build_sequence.add_argument("--subtitle-font-name", default="Yu Gothic")
    build_sequence.add_argument("--subtitle-font-size", type=int, default=18)
    build_sequence.add_argument("--subtitle-margin-v", type=int, default=14)
    build_sequence.add_argument("--execute", action="store_true")
    build_sequence.add_argument("--overwrite", action="store_true")
    build_sequence.set_defaults(func=command_build_event_sequence)

    bili = sub.add_parser("bili-metadata-audit", help="build Bilibili-oriented title/label metadata reports")
    bili.add_argument("--manifest-dir", default=str(DEFAULT_MANIFEST_DIR))
    bili.set_defaults(func=command_bili_metadata_audit)

    hflip = sub.add_parser("hflip-videos", help="horizontally flip MP4s into a new tree; dry-run by default")
    hflip.add_argument("--input-dir", required=True)
    hflip.add_argument("--out-dir", required=True)
    hflip.add_argument("--execute", action="store_true")
    hflip.add_argument("--overwrite", action="store_true")
    hflip.add_argument("--workers", type=int, default=2)
    hflip.add_argument("--limit", type=int, default=0)
    hflip.add_argument("--encoder", choices=["libx264", "h264_nvenc"], default="libx264")
    hflip.add_argument("--crf", type=int, default=16)
    hflip.add_argument("--cq", type=int, default=19)
    hflip.set_defaults(func=command_hflip_videos)

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
