#!/usr/bin/env python3
"""Build the native-416 ac0908 exhaustive editorial longform.

The product contains each code-proven distinct presentation once.  It is an
editorial collection, not a claim about one native play session.  Existing
owner-reviewed route editions supply ac0908_009, the six dish branches, and
ac0908_008.  Exact CRI/Z2D evidence supplies the missing entry and five result
presentations.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid


FPS = 30
RATE = 48_000
SAMPLES_PER_FRAME = RATE // FPS
OUTPUT_FRAMES = 3915

CHAPTERS = [
    ("ac0908_001", "饭店外景与侧身炒菜入口", 165, ("ac0908_001",)),
    ("ac0908_009", "强入口", 139, ("ac0908_009",)),
    ("ac0908_002", "桃包", 270, ("ac0908_002",)),
    ("ac0908_003", "中华海蜇", 270, ("ac0908_003",)),
    ("ac0908_004", "天津饭", 270, ("ac0908_004",)),
    ("ac0908_005", "韭菜炒肝", 270, ("ac0908_005",)),
    ("ac0908_006", "麻婆豆腐", 270, ("ac0908_006",)),
    ("ac0908_007", "四千年套餐", 201, ("ac0908_007",)),
    ("ac0908_008", "公共收尾", 241, ("ac0908_008",)),
    ("ac8004_001", "HATTEN结局", 498, ("ac0908_010", "ac0908_013")),
    ("ac8004_003", "CZ结局", 498, ("ac0908_011", "ac0908_014")),
    ("ac8004_004", "WIN结局", 145, ("ac0908_012", "ac0908_015")),
    ("ac0908_016", "PREMIA结局", 180, ("ac0908_016",)),
    ("ac8004_002", "ZENCHOU结局", 498, ("ac0908_017",)),
]

OUTCOMES = {
    "HATTEN": ("ac8005_kyo_hatten", 1005, 498),
    "CZ": ("ac8005_kyo_choseiya", 1008, 498),
    "WIN": ("ac8005_hat_WIN", 1010, 145),
    "ZENCHOU": ("ac8005_kyo_magichalle", 1004, 498),
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _published_path(path: Path, staging: Path, output_root: Path) -> str:
    try:
        relative = path.resolve().relative_to(staging.resolve())
    except ValueError:
        return str(path.resolve())
    return str(output_root / relative)


def _run(command: list[str], log_path: Path) -> None:
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "COMMAND\n" + subprocess.list2cmdline(command) + "\n\nSTDOUT\n" + result.stdout
        + "\nSTDERR\n" + result.stderr + f"\nEXIT_STATUS\n{result.returncode}\n",
        encoding="utf-8",
    )
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}); see {log_path}")


def _find_audio(root: Path, sound_code: int) -> Path:
    matches = sorted(root.glob(f"snd_{sound_code:05d}_*.ogg"))
    if len(matches) != 1:
        raise RuntimeError(f"sound code {sound_code} resolved to {len(matches)} files")
    return matches[0]


def _find_route(root: Path, route: int, edition: str) -> Path:
    matches = sorted((root / "REVIEW_NOW_18_MP4").glob(f"ac0908 路线{route} *选项__{edition}.mp4"))
    if len(matches) != 1:
        raise RuntimeError(f"route {route} edition {edition} resolved to {len(matches)} files")
    return matches[0]


def _argb_filter(input_index: int, label: str, frame_count: int, composite_black: bool) -> list[str]:
    duration = frame_count / FPS
    parts = [
        f"[{input_index}:v:0]format=rgb24,vflip,setpts=PTS-STARTPTS[{label}c]",
        f"[{input_index}:v:1]format=gray,vflip,setpts=PTS-STARTPTS[{label}a]",
        f"[{label}c][{label}a]alphamerge,scale=416:232:flags=lanczos,"
        f"trim=end_frame={frame_count},setpts=PTS-STARTPTS[{label}rgba]",
    ]
    if composite_black:
        parts += [
            f"color=c=black:s=416x232:r=30:d={duration:.9f},format=rgba[{label}bg]",
            f"[{label}bg][{label}rgba]overlay=shortest=1:format=auto,format=yuv420p[{label}]",
        ]
    else:
        parts.append(f"[{label}rgba]format=rgba[{label}]")
    return parts


def _encode_args(crf: int) -> list[str]:
    return [
        "-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p",
        "-r", "30", "-fps_mode", "cfr", "-c:a", "aac", "-b:a", "192k",
        "-ar", "48000", "-ac", "2", "-movflags", "+faststart",
    ]


def _render_entry(ffmpeg: str, usm: dict[str, Path], audio_root: Path, output: Path, log: Path) -> None:
    inputs = [usm["ac0908_001_c01_MR"], usm["ac0908_001_c02"], _find_audio(audio_root, 2650)]
    parts = _argb_filter(0, "e0", 22, True) + _argb_filter(1, "e1", 65, True)
    parts += [
        "[e0][e1]concat=n=2:v=1:a=0,tpad=stop_mode=clone:stop_duration=2.6,"
        "trim=end_frame=165,setpts=PTS-STARTPTS[v]",
        "[2:a]aresample=48000,aformat=sample_rates=48000:channel_layouts=stereo,"
        "apad=whole_len=264000,atrim=end_sample=264000,asetpts=PTS-STARTPTS[a]",
    ]
    command = [ffmpeg, "-nostdin", "-y", "-hide_banner", "-loglevel", "error"]
    for item in inputs:
        command += ["-i", str(item)]
    command += ["-filter_complex", ";".join(parts), "-map", "[v]", "-map", "[a]"]
    command += _encode_args(12) + [str(output)]
    _run(command, log)


def _render_outcome(
    ffmpeg: str,
    usm: dict[str, Path],
    audio_root: Path,
    name: str,
    output: Path,
    log: Path,
) -> None:
    movie_name, result_code, final_frames = OUTCOMES[name]
    movie_frames = 60 if name == "WIN" else 480
    inputs = [
        usm["ac0928_hat_shutter_totsu_kokuchi"], usm[movie_name],
        _find_audio(audio_root, 1035), _find_audio(audio_root, 1036),
        _find_audio(audio_root, result_code),
    ]
    parts = _argb_filter(0, "s", 30, True) + _argb_filter(1, "o0", movie_frames, True)
    outcome_frames = movie_frames - 12
    parts += [
        f"[o0]trim=start_frame=12:end_frame={movie_frames},setpts=PTS-STARTPTS[o]",
        f"[s][o]concat=n=2:v=1:a=0[vbase]",
    ]
    visual_frames = 30 + outcome_frames
    if final_frames > visual_frames:
        hold_seconds = (final_frames - visual_frames) / FPS
        parts.append(
            f"[vbase]tpad=stop_mode=clone:stop_duration={hold_seconds:.9f},"
            f"trim=end_frame={final_frames},setpts=PTS-STARTPTS[v]"
        )
    else:
        parts.append(f"[vbase]trim=end_frame={final_frames},setpts=PTS-STARTPTS[v]")
    parts += [
        "[2:a]aresample=48000,aformat=sample_rates=48000:channel_layouts=stereo,asetpts=PTS-STARTPTS[a0]",
        "[3:a]aresample=48000,aformat=sample_rates=48000:channel_layouts=stereo,adelay=34512S:all=1,asetpts=PTS-STARTPTS[a1]",
        "[4:a]aresample=48000,aformat=sample_rates=48000:channel_layouts=stereo,adelay=34080S:all=1,asetpts=PTS-STARTPTS[a2]",
        f"[a0][a1][a2]amix=inputs=3:duration=longest:normalize=0,apad=whole_len={final_frames * SAMPLES_PER_FRAME},"
        f"atrim=end_sample={final_frames * SAMPLES_PER_FRAME},asetpts=PTS-STARTPTS[a]",
    ]
    command = [ffmpeg, "-nostdin", "-y", "-hide_banner", "-loglevel", "error"]
    for item in inputs:
        command += ["-i", str(item)]
    command += ["-filter_complex", ";".join(parts), "-map", "[v]", "-map", "[a]"]
    command += _encode_args(12) + [str(output)]
    _run(command, log)


def _render_premia(
    ffmpeg: str,
    usm: dict[str, Path],
    audio_root: Path,
    caption: Path,
    output: Path,
    log: Path,
) -> None:
    inputs = [
        usm["ac0908_pre_c10"], usm["ac0908_pre_c10_LP"],
        usm["ac8040_premia_EF"], usm["ac8040_premia_EF_LP"],
    ]
    parts = []
    parts += _argb_filter(0, "p0", 90, True)
    parts += _argb_filter(1, "p1", 90, True)
    parts += _argb_filter(2, "f0", 60, False)
    parts += _argb_filter(3, "f1all", 200, False)
    parts += [
        "[p0][p1]concat=n=2:v=1:a=0[bg]",
        "[f1all]trim=end_frame=120,setpts=PTS-STARTPTS[f1]",
        "[f0][f1]concat=n=2:v=1:a=0[fx]",
        "[bg][fx]overlay=shortest=1:format=auto[base]",
        "[4:v]format=rgba,trim=end_frame=180,setpts=PTS-STARTPTS[cap]",
        "[base][cap]overlay=enable='between(n,6,35)':shortest=1:format=auto,"
        "trim=end_frame=180,setpts=PTS-STARTPTS,format=yuv420p[v]",
        "[5:a]aresample=48000,aformat=sample_rates=48000:channel_layouts=stereo,"
        "apad=whole_len=288000,atrim=end_sample=288000,asetpts=PTS-STARTPTS[a]",
    ]
    command = [ffmpeg, "-nostdin", "-y", "-hide_banner", "-loglevel", "error"]
    for item in inputs:
        command += ["-i", str(item)]
    command += ["-loop", "1", "-framerate", "30", "-i", str(caption)]
    command += ["-i", str(_find_audio(audio_root, 1012))]
    command += ["-filter_complex", ";".join(parts), "-map", "[v]", "-map", "[a]"]
    command += _encode_args(12) + [str(output)]
    _run(command, log)


def _write_chapters(path: Path) -> list[dict]:
    lines = [";FFMETADATA1"]
    rows = []
    cursor = 0
    for cut, title, frames, events in CHAPTERS:
        end = cursor + frames
        lines += ["[CHAPTER]", "TIMEBASE=1/30", f"START={cursor}", f"END={end}", f"title={title} ({cut})"]
        rows.append({
            "timeline_order": len(rows) + 1,
            "cut": cut,
            "title": title,
            "start_frame": cursor,
            "end_frame_exclusive": end,
            "frames": frames,
            "source_events": list(events),
        })
        cursor = end
    if cursor != OUTPUT_FRAMES:
        raise RuntimeError(f"chapter total {cursor} != {OUTPUT_FRAMES}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rows


def _final_filter() -> str:
    clips = []

    def add(input_index: int, start_frame: int, end_frame: int) -> None:
        label = len(clips)
        start_sample = start_frame * SAMPLES_PER_FRAME
        end_sample = end_frame * SAMPLES_PER_FRAME
        clips.append(
            f"[{input_index}:v]trim=start_frame={start_frame}:end_frame={end_frame},setpts=PTS-STARTPTS[v{label}];"
            f"[{input_index}:a]atrim=start_sample={start_sample}:end_sample={end_sample},asetpts=PTS-STARTPTS[a{label}]"
        )

    add(0, 0, 165)
    add(1, 0, 139)
    for source in range(1, 6):
        add(source, 139, 409)
    add(6, 139, 340)
    add(1, 409, 650)
    add(7, 0, 498)
    add(8, 0, 498)
    add(9, 0, 145)
    add(10, 0, 180)
    add(11, 0, 498)
    chain = "".join(f"[v{i}][a{i}]" for i in range(14))
    clips.append(f"{chain}concat=n=14:v=1:a=1[v][a]")
    return ";".join(clips)


def _render_final(
    ffmpeg: str,
    route_root: Path,
    edition: str,
    generated: dict[str, Path],
    metadata: Path,
    output: Path,
    log: Path,
) -> list[Path]:
    inputs = [generated["ENTRY"]]
    inputs += [_find_route(route_root, route, edition) for route in range(52, 58)]
    inputs += [generated[name] for name in ("HATTEN", "CZ", "WIN", "PREMIA", "ZENCHOU")]
    command = [ffmpeg, "-nostdin", "-y", "-hide_banner", "-loglevel", "error"]
    for item in inputs:
        command += ["-i", str(item)]
    command += ["-f", "ffmetadata", "-i", str(metadata)]
    command += [
        "-filter_complex", _final_filter(), "-map", "[v]", "-map", "[a]", "-map_metadata", "12",
    ]
    command += _encode_args(18) + [str(output)]
    _run(command, log)
    return inputs


def _probe(ffprobe: str, media: Path, log: Path) -> dict:
    command = [
        ffprobe, "-v", "error", "-count_frames", "-show_streams", "-show_chapters",
        "-show_format", "-of", "json", str(media),
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    log.write_text(
        "COMMAND\n" + subprocess.list2cmdline(command) + "\n\nSTDOUT\n" + result.stdout
        + "\nSTDERR\n" + result.stderr + f"\nEXIT_STATUS\n{result.returncode}\n",
        encoding="utf-8",
    )
    if result.returncode:
        raise RuntimeError(f"probe failed for {media}")
    return json.loads(result.stdout)


def _validate_probe(probe: dict) -> dict:
    video = [s for s in probe["streams"] if s["codec_type"] == "video"]
    audio = [s for s in probe["streams"] if s["codec_type"] == "audio"]
    checks = {
        "one_video": len(video) == 1,
        "one_audio": len(audio) == 1,
        "video_h264": len(video) == 1 and video[0].get("codec_name") == "h264",
        "canvas_416x232": len(video) == 1 and (video[0].get("width"), video[0].get("height")) == (416, 232),
        "frame_rate_30": len(video) == 1 and video[0].get("avg_frame_rate") == "30/1",
        "frame_count_3915": len(video) == 1 and int(video[0].get("nb_read_frames", -1)) == OUTPUT_FRAMES,
        "audio_aac": len(audio) == 1 and audio[0].get("codec_name") == "aac",
        "audio_48k": len(audio) == 1 and int(audio[0].get("sample_rate", 0)) == RATE,
        "audio_stereo": len(audio) == 1 and int(audio[0].get("channels", 0)) == 2,
        "chapter_count_14": len(probe.get("chapters", [])) == 14,
    }
    if not all(checks.values()):
        raise RuntimeError(f"media QA failed: {checks}")
    return checks


def _assert_authority(
    scene: dict,
    usm_doc: dict,
    movie: dict,
    composition: dict,
    render: dict,
) -> None:
    if scene.get("result") != "RUNTIME_UNIQUE_SCENE_AND_EVENT_AV_ORIGIN_RESOLVED_PRODUCTION_READY":
        raise RuntimeError("scene authority is not production ready")
    if scene.get("counts", {}).get("canonical_unique_visible_scene_count") != 14:
        raise RuntimeError("scene authority does not contain 14 canonical presentations")
    if scene.get("counts", {}).get("event_container_count") != 17:
        raise RuntimeError("scene authority does not cover 17 event containers")
    if len(scene.get("exact_alias_groups", [])) != 3 or scene.get("production_blockers"):
        raise RuntimeError("scene alias/blocker contract changed")
    if usm_doc.get("status") != "passed_exact_color_alpha_streams_resolved":
        raise RuntimeError("CRI color/alpha authority not passed")
    if movie.get("status") != "passed" or not movie.get("assertions", {}).get("all_movie_layers_are_centered_1024x576"):
        raise RuntimeError("MovieLayer geometry authority not passed")
    if composition.get("status") != "passed_code_bound_event_canvas_resolved":
        raise RuntimeError("event composition authority not passed")
    event = composition.get("event", {})
    if event.get("virtual_render_canvas") != [1280, 1024] or event.get("native_output_canvas") != [416, 232]:
        raise RuntimeError("code-bound canvas contract changed")
    if render.get("status") != "passed_exact_renderer_orientation_and_embedded_audio_suppression":
        raise RuntimeError("CRI runtime render authority not passed")
    contract = render.get("reconstruction_contract", {})
    if (
        contract.get("color_stream") != "apply_vflip_exactly_once_before_alphamerge"
        or contract.get("alpha_stream") != "apply_vflip_exactly_once_before_alphamerge"
        or contract.get("horizontal_flip") is not False
        or contract.get("embedded_usm_audio") != "exclude_runtime_explicitly_disables_it"
    ):
        raise RuntimeError("CRI runtime reconstruction contract changed")


def build(args: argparse.Namespace) -> Path:
    output_root = args.output_root.resolve()
    if output_root.exists():
        raise RuntimeError(f"immutable output already exists: {output_root}")
    staging = output_root.with_name(output_root.name + ".staging-" + uuid.uuid4().hex[:12])
    staging.mkdir(parents=True)
    try:
        scene = _load(args.scene_authority)
        usm_doc = _load(args.usm_authority)
        movie = _load(args.movie_authority)
        composition = _load(args.composition_authority)
        render = _load(args.render_authority)
        _assert_authority(scene, usm_doc, movie, composition, render)
        usm = {row["official_name"]: Path(row["path"]) for row in usm_doc["artifacts"]}
        for path in usm.values():
            if not path.is_file():
                raise RuntimeError(f"missing exact CRI source: {path}")
        caption = Path(composition["caption_composition"]["event_overlay_path"])
        if not caption.is_file():
            raise RuntimeError(f"missing caption overlay: {caption}")

        intermediate = staging / "intermediate"
        logs = staging / "verification" / "commands"
        intermediate.mkdir(parents=True)
        generated = {name: intermediate / f"{name.lower()}.mp4" for name in ("ENTRY", "HATTEN", "CZ", "WIN", "PREMIA", "ZENCHOU")}
        _render_entry(args.ffmpeg, usm, args.audio_root, generated["ENTRY"], logs / "entry.txt")
        for name in ("HATTEN", "CZ", "WIN", "ZENCHOU"):
            _render_outcome(args.ffmpeg, usm, args.audio_root, name, generated[name], logs / f"{name.lower()}.txt")
        _render_premia(args.ffmpeg, usm, args.audio_root, caption, generated["PREMIA"], logs / "premia.txt")

        metadata = staging / "manifests" / "chapters.ffmeta"
        metadata.parent.mkdir(parents=True)
        chapter_rows = _write_chapters(metadata)
        editions = {"none": "NONE", "ja": "JP", "zh": "ZH"}
        output_rows = []
        source_rows = {}
        for edition, folder in editions.items():
            target_dir = staging / "HUMAN_REVIEW" / folder / "story"
            target_dir.mkdir(parents=True)
            target = target_dir / f"ac0908_六种菜品与全部结局完整合集_严格无BGM__{edition}.mp4"
            source_inputs = _render_final(
                args.ffmpeg, args.route_root, edition, generated, metadata, target,
                logs / f"final_{edition}.txt",
            )
            probe = _probe(args.ffprobe, target, logs / f"probe_{edition}.txt")
            checks = _validate_probe(probe)
            output_rows.append({
                "edition": edition,
                "path": _published_path(target, staging, output_root),
                "bytes": target.stat().st_size,
                "human_status": "HUMAN_PLAYBACK_REQUIRED",
                "automatic_qa": checks,
            })
            source_rows[edition] = [_published_path(path, staging, output_root) for path in source_inputs]

        manifest = {
            "schema": "ac0908_exhaustive_authoritative_longform_v2",
            "status": "AUTOMATED_QA_PASS_HUMAN_PLAYBACK_REQUIRED",
            "product_semantics": "editorial_exhaustive_collection_not_native_single_session",
            "audio_profile": "strict_no_bgm_retains_verified_se_and_voice",
            "canvas": [416, 232],
            "frame_rate": 30,
            "frames": OUTPUT_FRAMES,
            "duration_seconds": OUTPUT_FRAMES / FPS,
            "canonical_presentation_count": 14,
            "event_container_count": 17,
            "exact_duplicate_surplus_count": 3,
            "chapters": chapter_rows,
            "authority_inputs": {
                "scene": str(args.scene_authority),
                "cri_argb": str(args.usm_authority),
                "movie_geometry": str(args.movie_authority),
                "event_composition": str(args.composition_authority),
                "cri_runtime_render": str(args.render_authority),
            },
            "edition_source_inputs": source_rows,
            "outputs": output_rows,
            "excluded": {
                "bgm_sound_codes": [551, 552, 553],
                "duplicate_event_aliases": ["ac0908_013", "ac0908_014", "ac0908_015"],
                "reason": "aliases are retained in event coverage but their identical media presentations occur once",
            },
        }
        _write_json(staging / "manifests" / "PRODUCTION_MANIFEST.json", manifest)
        _write_json(staging / "verification" / "VERIFICATION_RECORD.json", {
            "status": "PASS",
            "output_count": 3,
            "content_group_count": 1,
            "checks_per_output": list(output_rows[0]["automatic_qa"]),
            "literal_result": "PASS outputs=3 content_groups=1 frames_each=3915 chapters_each=14 canvas=416x232 fps=30 audio=aac_48000_stereo",
        })
        (staging / "00_START_HERE.md").write_text(
            "# ac0908 权威穷尽长片人工验收\n\n"
            "这是一个内容组，none/JP/ZH 三个版本只需按需检查。\n\n"
            "- 共 14 个代码级独特呈现，覆盖 ac0908_001–017。\n"
            "- ac0908_013/014/015 是 010/011/012 的精确重复别名，只保留事件记录，不重复媒体。\n"
            "- 总长 130.5 秒，原生 416×232、30fps、AAC 48kHz stereo。\n"
            "- 颜色与 alpha 均按 Slot OpenGL 渲染器规则各 vflip 一次；禁止 hflip。\n"
            "- CRI 内嵌音频被游戏以 CRIMANA_AUDIO_TRACK_OFF 关闭，成片只保留独立验证的对白与 SE。\n"
            "- 明确排除 BGM 551/552/553，保留已验证对白与 SE。\n"
            "- 自动 QA 通过仍不等于人工播放批准。\n",
            encoding="utf-8",
        )
        (staging / "ROLLBACK.ps1").write_text(
            "$ErrorActionPreference='Stop'\n"
            "$root=Split-Path -Parent $MyInvocation.MyCommand.Path\n"
            "$stamp=Get-Date -Format 'yyyyMMdd_HHmmss'\n"
            "Move-Item -LiteralPath $root -Destination ($root+'.withdrawn_'+$stamp)\n",
            encoding="utf-8",
        )
        (staging / "READY").write_text("AUTOMATED_QA_PASS_HUMAN_PLAYBACK_REQUIRED\n", encoding="utf-8")
        os.replace(staging, output_root)
        return output_root
    except Exception:
        (staging / "FAILED_BUILD.txt").write_text("Build failed; retained for diagnosis.\n", encoding="utf-8")
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene-authority", type=Path, required=True)
    parser.add_argument("--usm-authority", type=Path, required=True)
    parser.add_argument("--movie-authority", type=Path, required=True)
    parser.add_argument("--composition-authority", type=Path, required=True)
    parser.add_argument("--render-authority", type=Path, required=True)
    parser.add_argument("--route-root", type=Path, required=True)
    parser.add_argument("--audio-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--ffprobe", default="ffprobe")
    return parser


def main() -> int:
    try:
        result = build(_parser().parse_args())
    except Exception as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    print(f"PASS {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
