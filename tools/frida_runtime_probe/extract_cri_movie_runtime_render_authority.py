#!/usr/bin/env python3
"""Bind CRI MovieLayer orientation and embedded-audio behavior to Slot code."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterable

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM
from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection
from elftools.elf.sections import NoteSection


EXPECTED_BINARY_SIZE = 79_683_640
EXPECTED_BUILD_ID = "a1aceffc5be1f2380cdcd9af4d8f9764ac2bf40b"
OFFICIAL_CRI_API_URL = (
    "https://game.criware.jp/manual/native/sofdec2/latest/"
    "group__MDL__MANALIB__PLAYER.html"
)
PREMIA_USMS = ("ac8040_premia_EF", "ac8040_premia_EF_LP")


class CriMovieRuntimeAuthorityError(ValueError):
    """Exact binary or selected media no longer satisfies the contract."""


def _build_id(elf: ELFFile) -> str:
    for section in elf.iter_sections():
        if not isinstance(section, NoteSection):
            continue
        for note in section.iter_notes():
            if note["n_type"] == "NT_GNU_BUILD_ID":
                value = note["n_desc"]
                return value.hex() if isinstance(value, bytes) else str(value).lower()
    raise CriMovieRuntimeAuthorityError("ELF lacks GNU build id")


def _read_va(elf: ELFFile, address: int, size: int) -> bytes:
    for segment in elf.iter_segments():
        if segment["p_type"] != "PT_LOAD":
            continue
        start = int(segment["p_vaddr"])
        end = start + int(segment["p_filesz"])
        if start <= address and address + size <= end:
            elf.stream.seek(int(segment["p_offset"]) + address - start)
            return elf.stream.read(size)
    raise CriMovieRuntimeAuthorityError(f"virtual address is not file-backed: 0x{address:x}")


def _instruction(elf: ELFFile, address: int) -> dict[str, Any]:
    decoder = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    rows = list(decoder.disasm(_read_va(elf, address, 4), address))
    if len(rows) != 1:
        raise CriMovieRuntimeAuthorityError(f"failed to decode instruction at 0x{address:x}")
    row = rows[0]
    return {
        "address": f"0x{address:x}",
        "bytes_hex": bytes(row.bytes).hex(),
        "mnemonic": row.mnemonic,
        "operands": row.op_str,
    }


def _require_instruction(
    row: dict[str, Any], mnemonic: str, operand_fragments: Iterable[str]
) -> None:
    if row["mnemonic"] != mnemonic:
        raise CriMovieRuntimeAuthorityError(
            f"{row['address']} expected {mnemonic}, found {row['mnemonic']}"
        )
    missing = [fragment for fragment in operand_fragments if fragment not in row["operands"]]
    if missing:
        raise CriMovieRuntimeAuthorityError(
            f"{row['address']} operands changed: {row['operands']} lacks {missing}"
        )


def _symbol(elf: ELFFile, name: str) -> dict[str, Any]:
    dynsym = elf.get_section_by_name(".dynsym")
    if dynsym is None:
        raise CriMovieRuntimeAuthorityError("ELF lacks .dynsym")
    matches = [symbol for symbol in dynsym.iter_symbols() if symbol.name == name]
    if len(matches) != 1:
        raise CriMovieRuntimeAuthorityError(f"symbol {name} resolved to {len(matches)} rows")
    symbol = matches[0]
    return {
        "address": int(symbol["st_value"]),
        "defined": symbol["st_shndx"] != "SHN_UNDEF",
    }


def _plt_stub(elf: ELFFile, imported_name: str) -> int:
    plt = elf.get_section_by_name(".plt")
    relocations = elf.get_section_by_name(".rela.plt")
    if plt is None or not isinstance(relocations, RelocationSection):
        raise CriMovieRuntimeAuthorityError("ELF lacks standard .plt/.rela.plt")
    symbols = elf.get_section(relocations["sh_link"])
    rows = list(relocations.iter_relocations())
    indices = [
        index
        for index, relocation in enumerate(rows)
        if symbols.get_symbol(relocation["r_info_sym"]).name == imported_name
    ]
    if len(indices) != 1:
        raise CriMovieRuntimeAuthorityError(
            f"PLT import {imported_name} resolved to {len(indices)} relocations"
        )
    entry_size = 16
    reserved = int(plt["sh_size"]) - len(rows) * entry_size
    if reserved != 32:
        raise CriMovieRuntimeAuthorityError(f"unexpected AArch64 PLT header size: {reserved}")
    return int(plt["sh_addr"]) + reserved + indices[0] * entry_size


def _relocation_symbol(elf: ELFFile, offset: int) -> str:
    matches: list[str] = []
    for section in elf.iter_sections():
        if not isinstance(section, RelocationSection):
            continue
        symbols = elf.get_section(section["sh_link"])
        for relocation in section.iter_relocations():
            if int(relocation["r_offset"]) == offset:
                matches.append(symbols.get_symbol(relocation["r_info_sym"]).name)
    if len(matches) != 1:
        raise CriMovieRuntimeAuthorityError(
            f"relocation 0x{offset:x} resolved to {len(matches)} symbols"
        )
    return matches[0]


def _count_direct_bl_calls(elf: ELFFile, target: int) -> int:
    count = 0
    for segment in elf.iter_segments():
        if segment["p_type"] != "PT_LOAD" or not (int(segment["p_flags"]) & 1):
            continue
        start = int(segment["p_vaddr"])
        data = segment.data()
        for offset in range(0, len(data) - 3, 4):
            word = int.from_bytes(data[offset : offset + 4], "little")
            if word & 0xFC000000 != 0x94000000:
                continue
            immediate = word & 0x03FFFFFF
            if immediate & 0x02000000:
                immediate -= 0x04000000
            if start + offset + immediate * 4 == target:
                count += 1
    return count


def _ffprobe(command: str, path: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            command,
            "-v",
            "error",
            "-show_entries",
            "stream=index,codec_type,codec_name,sample_rate,channels,duration,width,height,r_frame_rate,nb_frames",
            "-show_entries",
            "format=format_name,duration,size",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode:
        raise CriMovieRuntimeAuthorityError(f"ffprobe failed for {path}: {result.stderr.strip()}")
    return json.loads(result.stdout)


def validate_premia_probe(name: str, path: Path, probe: dict[str, Any]) -> dict[str, Any]:
    videos = [row for row in probe.get("streams", []) if row.get("codec_type") == "video"]
    audio = [row for row in probe.get("streams", []) if row.get("codec_type") == "audio"]
    if len(videos) != 2 or len(audio) != 1:
        raise CriMovieRuntimeAuthorityError(
            f"{name} expected two video streams and one embedded audio stream"
        )
    stream = audio[0]
    if (
        stream.get("codec_name") != "adpcm_adx"
        or stream.get("sample_rate") != "48000"
        or int(stream.get("channels", 0)) != 2
    ):
        raise CriMovieRuntimeAuthorityError(f"{name} embedded audio profile changed")
    return {
        "official_name": name,
        "path": str(path.resolve()),
        "video_stream_indices": [int(row["index"]) for row in videos],
        "embedded_audio_stream_index": int(stream["index"]),
        "embedded_audio_codec": stream["codec_name"],
        "embedded_audio_sample_rate": int(stream["sample_rate"]),
        "embedded_audio_channels": int(stream["channels"]),
        "embedded_audio_duration_seconds": float(stream["duration"]),
        "runtime_playback": "DISABLED_BY_CRIMANA_AUDIO_TRACK_OFF",
    }


def validate_movie_layers(authority: dict[str, Any]) -> dict[str, Any]:
    if authority.get("status") != "passed":
        raise CriMovieRuntimeAuthorityError("MovieLayer authority is not passed")
    rows = [
        layer
        for chunk in authority.get("z2d_chunks", [])
        for layer in chunk.get("movie_layers", [])
    ]
    if len(rows) != 13:
        raise CriMovieRuntimeAuthorityError(f"expected 13 selected MovieLayers, found {len(rows)}")
    allowed_layouts = {
        ("0x077e", "flags_0x400_default_blend"),
        ("0x037e", "explicit_uint32_blend_enum"),
    }
    if any(
        (row.get("layer_flags_hex"), row.get("layer_layout")) not in allowed_layouts
        or row.get("position") != [512.0, 288.0]
        or row.get("pivot") != [512.0, 288.0]
        or row.get("layer_width") != 1024
        or row.get("layer_height") != 576
        for row in rows
    ):
        raise CriMovieRuntimeAuthorityError("selected MovieLayer authored transform changed")
    return {
        "selected_movie_layer_count": len(rows),
        "authored_transform": "centered_1024x576_default_scale_rotation_no_flip",
        "blend_layouts": sorted({row["layer_layout"] for row in rows}),
        "authored_horizontal_flip": False,
        "authored_vertical_flip": False,
    }


def build(
    binary_path: Path,
    usm_authority_path: Path,
    movie_authority_path: Path,
    ffprobe: str,
    reference_video: Path | None,
) -> dict[str, Any]:
    if binary_path.stat().st_size != EXPECTED_BINARY_SIZE:
        raise CriMovieRuntimeAuthorityError("exact Slot binary size changed")
    with binary_path.open("rb") as handle:
        elf = ELFFile(handle)
        if elf.get_machine_arch() != "AArch64":
            raise CriMovieRuntimeAuthorityError(f"expected AArch64, found {elf.get_machine_arch()}")
        build_id = _build_id(elf)
        if build_id != EXPECTED_BUILD_ID:
            raise CriMovieRuntimeAuthorityError(f"exact Slot build id changed: {build_id}")

        symbols = {
            name: _symbol(elf, name)
            for name in (
                "_ZN2zg6sprite8Renderer12isTextureYUpEv",
                "_ZN2zg6sprite14RendererImplGL12isTextureYUpEv",
                "_ZTVN2zg6sprite14RendererImplGLE",
                "_ZN2zg6sprite12RendererImpl12createOpenGLEv",
                "_ZN2zg6sprite12RendererImpl13createDirectXEv",
            )
        }
        expected_addresses = {
            "_ZN2zg6sprite8Renderer12isTextureYUpEv": 0x4343980,
            "_ZN2zg6sprite14RendererImplGL12isTextureYUpEv": 0x434B114,
            "_ZTVN2zg6sprite14RendererImplGLE": 0x44BC508,
            "_ZN2zg6sprite12RendererImpl12createOpenGLEv": 0x434D7E8,
            "_ZN2zg6sprite12RendererImpl13createDirectXEv": 0x4347AF4,
        }
        for name, address in expected_addresses.items():
            if symbols[name]["address"] != address or not symbols[name]["defined"]:
                raise CriMovieRuntimeAuthorityError(f"symbol boundary changed for {name}")

        addresses = (
            0x434398C,
            0x4343990,
            0x4343994,
            0x4347AF4,
            0x434B114,
            0x434D800,
            0x43591F4,
            0x4359230,
            0x4359240,
            0x4359250,
            0x43592BC,
            0x43592CC,
            0x43592D0,
            0x425BDB0,
            0x425BDB4,
            0x425D2AC,
        )
        instructions = {address: _instruction(elf, address) for address in addresses}
        requirements = {
            0x434398C: ("ldr", ("x8", "[x0]")),
            0x4343990: ("ldr", ("x1", "[x8, #0x130]")),
            0x4343994: ("br", ("x1",)),
            0x4347AF4: ("mov", ("x0", "xzr")),
            0x434B114: ("mov", ("w0", "#1")),
            0x434D800: ("bl", ("#0x449b5f0",)),
            0x43591F4: ("bl", ("#0x4496fb0",)),
            0x4359230: ("tbz", ("w0", "#0")),
            0x4359240: ("fsub", ("s1", "s2", "s1")),
            0x4359250: ("fsub", ("s1", "s2", "s1")),
            0x43592BC: ("tbz", ("w0", "#0")),
            0x43592CC: ("fsub", ("s1", "s2", "s1")),
            0x43592D0: ("fsub", ("s3", "s2", "s3")),
            0x425BDB0: ("mov", ("w1", "#-1")),
            0x425BDB4: ("bl", ("#0x44934a0",)),
            0x425D2AC: ("bl", ("#0x44930d0",)),
        }
        for address, (mnemonic, fragments) in requirements.items():
            _require_instruction(instructions[address], mnemonic, fragments)

        audio_stub = _plt_stub(elf, "criManaPlayer_SetAudioTrack")
        if audio_stub != 0x44934A0:
            raise CriMovieRuntimeAuthorityError("SetAudioTrack PLT target changed")
        audio_call_count = _count_direct_bl_calls(elf, audio_stub)
        if audio_call_count != 1:
            raise CriMovieRuntimeAuthorityError(
                f"expected one direct SetAudioTrack call, found {audio_call_count}"
            )
        gl_vtable_slot = symbols["_ZTVN2zg6sprite14RendererImplGLE"]["address"] + 16 + 0x130
        gl_vtable_target = _relocation_symbol(elf, gl_vtable_slot)
        if gl_vtable_target != "_ZN2zg6sprite14RendererImplGL12isTextureYUpEv":
            raise CriMovieRuntimeAuthorityError("RendererImplGL Y-up vtable slot changed")

    usm_authority = json.loads(usm_authority_path.read_text(encoding="utf-8"))
    artifacts = {row["official_name"]: Path(row["path"]) for row in usm_authority["artifacts"]}
    premia = []
    for name in PREMIA_USMS:
        if name not in artifacts or not artifacts[name].is_file():
            raise CriMovieRuntimeAuthorityError(f"missing selected USM {name}")
        premia.append(validate_premia_probe(name, artifacts[name], _ffprobe(ffprobe, artifacts[name])))
    movie_authority = json.loads(movie_authority_path.read_text(encoding="utf-8"))
    if movie_authority.get("binary", {}).get("gnu_build_id") != build_id:
        raise CriMovieRuntimeAuthorityError("inherited MovieLayer binary identity changed")
    layer_contract = validate_movie_layers(movie_authority)
    if reference_video is not None and not reference_video.is_file():
        raise CriMovieRuntimeAuthorityError(f"missing local reference video: {reference_video}")

    return {
        "schema": "magireco-cri-movielayer-runtime-render-authority-v1",
        "status": "passed_exact_renderer_orientation_and_embedded_audio_suppression",
        "exact_slot_binary": {
            "path": str(binary_path.resolve()),
            "size": binary_path.stat().st_size,
            "gnu_build_id": build_id,
            "architecture": "AArch64",
            "identity_source": str(movie_authority_path.resolve()),
        },
        "inputs": {
            "cri_usm_authority": str(usm_authority_path.resolve()),
            "movie_layer_authority": str(movie_authority_path.resolve()),
            "local_reference_video": str(reference_video.resolve()) if reference_video else None,
        },
        "code_authority": {
            "renderer_dispatch": {
                "address": "0x4343980",
                "vtable_offset": "0x130",
                "gl_vtable_slot": f"0x{gl_vtable_slot:x}",
                "relocation_target": gl_vtable_target,
            },
            "renderer_backend": {
                "directx_factory_address": "0x4347af4",
                "directx_factory_result": "null",
                "opengl_factory_address": "0x434d7e8",
                "opengl_factory_product": "RendererImplGL",
                "gl_is_texture_y_up_address": "0x434b114",
                "gl_is_texture_y_up_result": True,
            },
            "z2d_movie_texture_coordinates": {
                "function_address": "0x4358f4c",
                "is_texture_y_up_call": "0x43591f4",
                "vertical_coordinate_subtractions": [
                    "0x4359240",
                    "0x4359250",
                    "0x43592cc",
                    "0x43592d0",
                ],
            },
            "cri_embedded_audio": {
                "player_factory_address": "0x425bd68",
                "set_audio_track_argument_address": "0x425bdb0",
                "argument": -1,
                "set_audio_track_call_address": "0x425bdb4",
                "set_audio_track_import": "criManaPlayer_SetAudioTrack",
                "direct_call_count_in_executable_segments": audio_call_count,
                "official_api_macro": "CRIMANA_AUDIO_TRACK_OFF",
                "official_api_value": -1,
                "official_api_url": OFFICIAL_CRI_API_URL,
            },
            "instructions": [instructions[address] for address in addresses],
        },
        "movie_layers": layer_contract,
        "premia_embedded_audio_streams": premia,
        "reconstruction_contract": {
            "color_stream": "apply_vflip_exactly_once_before_alphamerge",
            "alpha_stream": "apply_vflip_exactly_once_before_alphamerge",
            "horizontal_flip": False,
            "embedded_usm_audio": "exclude_runtime_explicitly_disables_it",
            "separate_event_audio": "retain_only_code_verified_voice_and_se",
        },
        "assertions": {
            "orientation_is_code_bound_not_machine_vision_inferred": True,
            "local_reference_is_corroboration_only": reference_video is not None,
            "all_selected_movie_layers_lack_authored_flip": True,
            "renderer_applies_vertical_texture_coordinate_inversion": True,
            "software_reconstruction_requires_vflip_once": True,
            "software_reconstruction_requires_hflip": False,
            "embedded_cri_audio_is_intentionally_silent_in_slot_runtime": True,
            "production_disposition": "READY_FOR_CORRECTED_AC0908_REBUILD",
        },
    }


def write_outputs(result: dict[str, Any], output_root: Path) -> None:
    if output_root.exists():
        raise CriMovieRuntimeAuthorityError(f"immutable output already exists: {output_root}")
    output_root.mkdir(parents=True)
    (output_root / "CRI_MOVIELAYER_RUNTIME_RENDER_AUTHORITY.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    verification = {
        "status": "PASS",
        "literal_result": (
            "PASS exact_slot_binary=true renderer=OpenGL texture_y_up=true "
            "reconstruction=vflip_color_and_alpha_once hflip=false "
            "cri_embedded_audio=CRIMANA_AUDIO_TRACK_OFF premia_usm_audio_streams=2"
        ),
    }
    (output_root / "VERIFICATION_RECORD.json").write_text(
        json.dumps(verification, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_root / "README.md").write_text(
        "# CRI MovieLayer 运行时还原权威\n\n"
        "- exact Slot AArch64 代码证明可用图形后端为 OpenGL，RendererImplGL 报告 texture-Y-up。\n"
        "- Z2D MovieLayer 路径对 V 坐标执行 `1.0-v`；软件还原须对颜色与 alpha 各 `vflip` 一次，再 alphamerge，禁止 hflip。\n"
        "- 所选 13 层均为默认 1024x576 居中变换，没有作者级翻转。\n"
        "- CRI player 创建时唯一一次 SetAudioTrack 参数为 -1，即官方 CRIMANA_AUDIO_TRACK_OFF；USM 内嵌音频不进入游戏播放。\n"
        "- 本地参考画面只作旁证，不参与逻辑判定。\n",
        encoding="utf-8",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--usm-authority", type=Path, required=True)
    parser.add_argument("--movie-authority", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--reference-video", type=Path)
    parser.add_argument("--ffprobe", default="ffprobe")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        result = build(
            args.binary,
            args.usm_authority,
            args.movie_authority,
            args.ffprobe,
            args.reference_video,
        )
        write_outputs(result, args.output_root)
    except Exception as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    print(f"PASS {args.output_root.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
