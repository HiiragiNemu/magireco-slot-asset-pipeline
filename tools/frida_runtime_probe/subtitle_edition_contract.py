#!/usr/bin/env python3
"""Fail-closed contract for native-resolution audio/subtitle editions.

This module plans editions; it does not translate text and it does not render
media.  The publication target is a 2x3 matrix: verified BGM+voice/SE and
verified no-BGM voice/SE audio masters, each with none/ja/zh subtitle variants.
Legacy manifests with a top-level ``subtitles`` list are interpreted as the
Japanese track only through an explicit compatibility mode.  In the verified
matrix, every retained voice row must have exactly one Japanese cue and one
Chinese cue bound by event, request ID, source hash, and covered voice timing.
Chinese cues must also carry human-approved translation provenance back to the
exact Japanese cue.  Every visible character must be covered by an explicitly
identified per-language font file before a renderer is allowed to run. Japanese
and Chinese may use different audited font files; only implicit fallback is
forbidden.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import unicodedata
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence


EDITION_NONE = "none"
SUBTITLE_LANGUAGES = ("ja", "zh")
SUPPORTED_EDITIONS = (EDITION_NONE, *SUBTITLE_LANGUAGES)
LEGACY_EDITIONS = (EDITION_NONE, "ja")
AUDIO_PROFILE_WITH_BGM = "with_bgm"
AUDIO_PROFILE_NO_BGM = "no_bgm"
AUDIO_PROFILES = (AUDIO_PROFILE_WITH_BGM, AUDIO_PROFILE_NO_BGM)
LEGACY_AUDIO_PROFILE = "legacy_unclassified"
VERIFIED_EVIDENCE_KINDS = ("official_runtime", "verified_static_logic")
FONT_CONFIG_SCHEMA = "magireco-subtitle-fonts-v1"
EDITION_PLAN_SCHEMA = "magireco-subtitle-edition-plan-v2"
AUDIO_MASTER_CONTRACT_SCHEMA = "magireco-audio-master-contract-v1"
SHA256_RE = re.compile(r"^[0-9A-Fa-f]{64}$")
ASS_COLOUR_RE = re.compile(r"^&H[0-9A-Fa-f]{8}$")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def normalize_requested_editions(
    editions: Sequence[str] | None,
    *,
    legacy_compat: bool = False,
) -> list[str]:
    if legacy_compat and editions and list(editions) != list(LEGACY_EDITIONS):
        raise ValueError(
            "legacy two-edition mode is fixed to none+ja"
        )
    requested = list(
        editions or (LEGACY_EDITIONS if legacy_compat else SUPPORTED_EDITIONS)
    )
    if not requested:
        raise ValueError("at least one edition must be requested")
    unknown = [edition for edition in requested if edition not in SUPPORTED_EDITIONS]
    if unknown:
        raise ValueError(f"unsupported edition(s): {unknown}")
    if len(set(requested)) != len(requested):
        raise ValueError(f"duplicate edition request: {requested}")
    if EDITION_NONE not in requested:
        raise ValueError("the none edition is mandatory as the shared base")
    return requested


def normalize_requested_audio_profiles(
    audio_profiles: Sequence[str] | None,
    *,
    legacy_compat: bool = False,
) -> list[str]:
    if legacy_compat:
        if audio_profiles:
            raise ValueError(
                "legacy two-edition mode cannot declare verified audio profiles"
            )
        return [LEGACY_AUDIO_PROFILE]
    requested = list(audio_profiles or AUDIO_PROFILES)
    if not requested:
        raise ValueError("at least one audio profile must be requested")
    unknown = [profile for profile in requested if profile not in AUDIO_PROFILES]
    if unknown:
        raise ValueError(f"unsupported audio profile(s): {unknown}")
    if len(set(requested)) != len(requested):
        raise ValueError(f"duplicate audio profile request: {requested}")
    return requested


def normalize_cues(rows: Iterable[dict[str, Any]], *, language: str) -> list[dict]:
    cues: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        try:
            start_ms = int(row["start_ms"])
            end_ms = int(row["end_ms"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(
                f"{language} cue {index} has invalid start_ms/end_ms"
            ) from error
        text = str(row.get("text", ""))
        if start_ms < 0 or end_ms <= start_ms:
            raise ValueError(
                f"{language} cue {index} has invalid interval "
                f"{start_ms}..{end_ms}"
            )
        if not text.strip():
            raise ValueError(f"{language} cue {index} has blank text")
        cue = {
            "cue_index": index,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "text": text,
        }
        # Binding/provenance are normalized and authenticated later, once the
        # audited voice timeline and the corresponding Japanese cue are known.
        # Preserve them here rather than silently discarding security-critical
        # manifest fields.
        if "voice_binding" in row:
            cue["voice_binding"] = row["voice_binding"]
        if "translation_provenance" in row:
            cue["translation_provenance"] = row["translation_provenance"]
        cues.append(cue)
    return cues


def subtitle_cue_sha256(cue: dict[str, Any]) -> str:
    """Hash the complete Japanese source cue used by a translation record."""

    return canonical_sha256(
        {
            "cue_index": int(cue["cue_index"]),
            "start_ms": int(cue["start_ms"]),
            "end_ms": int(cue["end_ms"]),
            "text": str(cue["text"]),
            "voice_binding": cue["voice_binding"],
        }
    )


def _normalize_voice_binding(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} voice_binding must be an object")
    event = str(value.get("event", "")).strip()
    request_id = str(value.get("request_id", "")).strip()
    source_sha256 = str(value.get("source_sha256", "")).strip().upper()
    if not event or not request_id or not SHA256_RE.fullmatch(source_sha256):
        raise ValueError(
            f"{label} voice_binding requires event, request_id, and full "
            "source_sha256"
        )
    try:
        voice_start_ms = int(value["voice_start_ms"])
        voice_end_ms = int(value["voice_end_ms"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            f"{label} voice_binding requires integer voice_start_ms/voice_end_ms"
        ) from error
    if voice_start_ms < 0 or voice_end_ms <= voice_start_ms:
        raise ValueError(f"{label} voice_binding has invalid voice timing")
    return {
        "event": event,
        "request_id": request_id,
        "source_sha256": source_sha256,
        "voice_start_ms": voice_start_ms,
        "voice_end_ms": voice_end_ms,
    }


def _voice_binding_key(value: dict[str, Any]) -> tuple[str, str, str, int, int]:
    return (
        value["event"],
        value["request_id"],
        value["source_sha256"],
        value["voice_start_ms"],
        value["voice_end_ms"],
    )


def _validate_translation_provenance(
    value: Any,
    *,
    cue: dict[str, Any],
    japanese_cue: dict[str, Any],
) -> dict[str, Any]:
    label = f"zh cue {cue['cue_index']} translation_provenance"
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    try:
        source_cue_index = int(value["source_ja_cue_index"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"{label} requires source_ja_cue_index") from error
    source_cue_sha256 = str(
        value.get("source_ja_cue_sha256", "")
    ).strip().upper()
    expected_sha256 = subtitle_cue_sha256(japanese_cue)
    if source_cue_index != int(japanese_cue["cue_index"]):
        raise ValueError(f"{label} source Japanese cue index mismatch")
    if source_cue_sha256 != expected_sha256:
        raise ValueError(f"{label} source Japanese cue SHA256 mismatch")

    translator = str(value.get("translator", "")).strip()
    raw_method = value.get("translation_method")
    translation_method: dict[str, str] | None = None
    if raw_method not in (None, ""):
        if not isinstance(raw_method, dict):
            raise ValueError(f"{label} translation_method must be an object")
        method = str(raw_method.get("method", "")).strip()
        model = str(raw_method.get("model", "")).strip()
        if not method or not model:
            raise ValueError(
                f"{label} translation_method requires method and model"
            )
        translation_method = {"method": method, "model": model}
    if not translator and translation_method is None:
        raise ValueError(
            f"{label} requires translator or translation_method method/model"
        )
    reviewer = str(value.get("reviewer", "")).strip()
    if not reviewer:
        raise ValueError(f"{label} reviewer is required")
    if value.get("human_approved") is not True:
        raise ValueError(f"{label} human_approved must be true")
    return {
        "source_ja_cue_index": source_cue_index,
        "source_ja_cue_sha256": expected_sha256,
        "translator": translator,
        "translation_method": translation_method,
        "reviewer": reviewer,
        "human_approved": True,
    }


def validate_voice_subtitle_bindings(
    *,
    event: str,
    tracks: dict[str, list[dict[str, Any]]],
    voice_se_timeline: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """Require a strict one-voice-to-one-cue binding in both languages.

    This schema intentionally does not infer many-to-one or one-to-many
    relationships.  A future schema may add those relationships explicitly;
    until then, any split, duplicate, or unbound cue fails closed.
    """

    event = str(event).strip()
    voice_rows = [
        row for row in voice_se_timeline if row.get("audio_role") == "voice"
    ]
    if not voice_rows:
        unbound = [
            f"{language}:{cue['cue_index']}"
            for language in SUBTITLE_LANGUAGES
            for cue in tracks.get(language, [])
        ]
        if unbound:
            raise ValueError(
                "verified subtitle cues have no retained voice rows and are "
                f"therefore unbound: {unbound}"
            )
        return {
            "mode": "one_voice_to_one_cue_per_language",
            "voice_row_count": 0,
            "bound_cue_count": {language: 0 for language in SUBTITLE_LANGUAGES},
            "binding_sha256": canonical_sha256([]),
        }
    if not event:
        raise ValueError("voice subtitle binding requires a non-empty event")
    for language in SUBTITLE_LANGUAGES:
        if language not in tracks or not tracks[language]:
            raise ValueError(
                f"voice rows require a non-empty {language} subtitle track"
            )

    voice_by_key: dict[tuple[str, str, str, int, int], dict[str, Any]] = {}
    for index, row in enumerate(voice_rows):
        request_id = str(row.get("request_id", "")).strip()
        source_sha256 = str(row.get("sha256", "")).strip().upper()
        if not request_id or not SHA256_RE.fullmatch(source_sha256):
            raise ValueError(
                f"voice row {index} requires request_id and full source SHA-256 "
                "for subtitle binding"
            )
        binding = {
            "event": event,
            "request_id": request_id,
            "source_sha256": source_sha256,
            "voice_start_ms": int(row["start_ms"]),
            "voice_end_ms": int(row["start_ms"]) + int(row["duration_ms"]),
        }
        key = _voice_binding_key(binding)
        if key in voice_by_key:
            raise ValueError(
                "duplicate voice identity/timing cannot satisfy the one-to-one "
                f"subtitle contract: {key}"
            )
        voice_by_key[key] = binding

    cues_by_language: dict[
        str, dict[tuple[str, str, str, int, int], dict[str, Any]]
    ] = {}
    for language in SUBTITLE_LANGUAGES:
        bound: dict[tuple[str, str, str, int, int], dict[str, Any]] = {}
        for cue in tracks[language]:
            label = f"{language} cue {cue['cue_index']}"
            binding = _normalize_voice_binding(
                cue.get("voice_binding"), label=label
            )
            key = _voice_binding_key(binding)
            if binding["event"] != event:
                raise ValueError(f"{label} voice_binding event mismatch")
            if key not in voice_by_key:
                raise ValueError(
                    f"{label} voice_binding does not match an audited voice row"
                )
            if key in bound:
                raise ValueError(
                    f"{language} has duplicate cues for one voice row; only "
                    "one-to-one binding is supported"
                )
            if (
                int(cue["start_ms"]) > binding["voice_start_ms"]
                or int(cue["end_ms"]) < binding["voice_end_ms"]
            ):
                raise ValueError(
                    f"{label} timing does not cover the complete bound voice interval"
                )
            cue["voice_binding"] = binding
            bound[key] = cue
        missing = set(voice_by_key) - set(bound)
        if missing:
            raise ValueError(
                f"{language} subtitle track does not bind every voice row: "
                f"missing={len(missing)}"
            )
        if len(bound) != len(voice_by_key):
            raise ValueError(
                f"{language} subtitle track contains unbound or extra cues"
            )
        cues_by_language[language] = bound

    for key, japanese_cue in cues_by_language["ja"].items():
        chinese_cue = cues_by_language["zh"].get(key)
        if chinese_cue is None:
            raise ValueError("Japanese/Chinese subtitle voice binding mismatch")
        if cue_timeline([japanese_cue]) != cue_timeline([chinese_cue]):
            raise ValueError(
                "Japanese/Chinese cues for one voice row must share exact timing"
            )
        chinese_cue["translation_provenance"] = _validate_translation_provenance(
            chinese_cue.get("translation_provenance"),
            cue=chinese_cue,
            japanese_cue=japanese_cue,
        )

    binding_records = [
        {
            "voice_binding": voice_by_key[key],
            "ja_cue_index": cues_by_language["ja"][key]["cue_index"],
            "zh_cue_index": cues_by_language["zh"][key]["cue_index"],
            "ja_cue_sha256": subtitle_cue_sha256(cues_by_language["ja"][key]),
        }
        for key in sorted(voice_by_key)
    ]
    return {
        "mode": "one_voice_to_one_cue_per_language",
        "voice_row_count": len(voice_rows),
        "bound_cue_count": {
            language: len(cues_by_language[language])
            for language in SUBTITLE_LANGUAGES
        },
        "binding_sha256": canonical_sha256(binding_records),
        "bindings": binding_records,
    }


def _track_rows(track: Any, *, language: str) -> list[dict[str, Any]]:
    if isinstance(track, list):
        return track
    if isinstance(track, dict) and isinstance(track.get("cues"), list):
        declared_language = str(track.get("language", language))
        if declared_language != language:
            raise ValueError(
                f"subtitle_tracks.{language} declares language={declared_language!r}"
            )
        return track["cues"]
    raise ValueError(
        f"subtitle_tracks.{language} must be a cue list or an object with cues"
    )


def subtitle_tracks_from_manifest(manifest: dict[str, Any]) -> dict[str, list[dict]]:
    """Normalize legacy and multilingual subtitle tracks without translating."""

    result: dict[str, list[dict]] = {}
    tracks = manifest.get("subtitle_tracks", {})
    if tracks is None:
        tracks = {}
    if not isinstance(tracks, dict):
        raise ValueError("subtitle_tracks must be an object")
    unknown = sorted(set(tracks) - set(SUBTITLE_LANGUAGES))
    if unknown:
        raise ValueError(f"unsupported subtitle track language(s): {unknown}")
    for language, track in tracks.items():
        result[language] = normalize_cues(
            _track_rows(track, language=language), language=language
        )

    if "subtitles" in manifest:
        legacy = manifest["subtitles"]
        if not isinstance(legacy, list):
            raise ValueError("legacy subtitles must be a list")
        legacy_ja = normalize_cues(legacy, language="ja")
        if "ja" in result and result["ja"] != legacy_ja:
            raise ValueError(
                "legacy subtitles and subtitle_tracks.ja disagree; refusing "
                "an ambiguous Japanese track"
            )
        result.setdefault("ja", legacy_ja)
    return result


def cue_timeline(cues: Sequence[dict[str, Any]]) -> list[dict[str, int]]:
    return [
        {"start_ms": int(cue["start_ms"]), "end_ms": int(cue["end_ms"])}
        for cue in cues
    ]


def required_visible_codepoints(cues: Sequence[dict[str, Any]]) -> set[int]:
    """Return visible codepoints that must be supplied by the bound font."""

    required: set[int] = set()
    for cue in cues:
        for character in str(cue["text"]):
            if character.isspace() or unicodedata.category(character).startswith("C"):
                continue
            required.add(ord(character))
    return required


def format_codepoint(codepoint: int) -> str:
    return f"U+{codepoint:04X}"


def inspect_font(path: Path, face_index: int = 0) -> dict[str, Any]:
    """Read names and cmap coverage with fontTools, failing if unavailable."""

    try:
        from fontTools.ttLib import TTFont
    except ImportError as error:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "fontTools is required for fail-closed subtitle glyph coverage"
        ) from error

    try:
        font = TTFont(str(path), fontNumber=face_index, lazy=True)
    except Exception as error:
        raise ValueError(f"unable to inspect font {path}: {error}") from error
    try:
        names: set[str] = set()
        if "name" in font:
            for record in font["name"].names:
                if record.nameID not in {1, 4, 6, 16}:
                    continue
                try:
                    value = record.toUnicode().strip()
                except Exception:
                    continue
                if value:
                    names.add(value)
        codepoints: set[int] = set()
        if "cmap" in font:
            for table in font["cmap"].tables:
                codepoints.update(int(value) for value in table.cmap)
        return {
            "family_names": sorted(names),
            "codepoints": codepoints,
            "face_index": face_index,
        }
    finally:
        font.close()


def load_font_config(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != FONT_CONFIG_SCHEMA:
        raise ValueError(
            f"font config schema must be {FONT_CONFIG_SCHEMA!r}: {path}"
        )
    if not isinstance(payload.get("fonts"), dict):
        raise ValueError("font config must contain a fonts object")
    payload["_config_path"] = str(path.resolve())
    return payload


def _resolve_font_path(spec: dict[str, Any], config_path: str | None) -> Path:
    raw_path = str(spec.get("path", "")).strip()
    if not raw_path:
        raise ValueError("font path is required")
    path = Path(raw_path)
    if not path.is_absolute() and config_path:
        path = Path(config_path).parent / path
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"font file does not exist: {path}")
    return path


def validate_font_binding(
    language: str,
    cues: Sequence[dict[str, Any]],
    font_config: dict[str, Any] | None,
    *,
    inspector: Callable[[Path, int], dict[str, Any]] = inspect_font,
) -> dict[str, Any] | None:
    """Require explicit source, identity, family, and complete cmap coverage."""

    if not cues:
        return None
    if font_config is None:
        raise ValueError(
            f"{language} has subtitle cues but no --font-config; implicit system "
            "font fallback is forbidden"
        )
    fonts = font_config.get("fonts", {})
    spec = fonts.get(language)
    if not isinstance(spec, dict):
        raise ValueError(f"font config has no binding for language {language!r}")
    family = str(spec.get("family", "")).strip()
    if not family:
        raise ValueError(f"{language} font family is required")
    if any(character in family for character in (",", "'", "\n", "\r")):
        raise ValueError(f"{language} font family contains unsafe ASS characters")
    source = spec.get("source")
    if (
        not isinstance(source, dict)
        or not str(source.get("kind", "")).strip()
        or not str(source.get("evidence", "")).strip()
        or not str(source.get("license", "")).strip()
    ):
        raise ValueError(
            f"{language} font source.kind, source.evidence and source.license "
            "are required"
        )

    path = _resolve_font_path(spec, font_config.get("_config_path"))
    actual_sha256 = file_sha256(path)
    expected_sha256 = str(spec.get("sha256", "")).strip().upper()
    if expected_sha256 and expected_sha256 != actual_sha256:
        raise ValueError(
            f"{language} font SHA256 mismatch: expected={expected_sha256}, "
            f"actual={actual_sha256}"
        )
    face_index = int(spec.get("face_index", 0))
    inspection = inspector(path, face_index)
    family_names = set(inspection.get("family_names", []))
    if family not in family_names:
        raise ValueError(
            f"{language} configured family {family!r} not present in font names: "
            f"{sorted(family_names)}"
        )
    supported = {int(value) for value in inspection.get("codepoints", set())}
    required = required_visible_codepoints(cues)
    missing = sorted(required - supported)
    if missing:
        sample = ", ".join(
            f"{format_codepoint(value)} {chr(value)!r}" for value in missing[:24]
        )
        raise ValueError(
            f"{language} font coverage missing {len(missing)} codepoint(s): {sample}"
        )
    return {
        "path": str(path),
        "sha256": actual_sha256,
        "family": family,
        "face_index": face_index,
        "source": source,
        "required_codepoint_count": len(required),
        "supported_codepoint_count": len(supported),
        "coverage_complete": True,
    }


def validate_layout_profile(
    font_config: dict[str, Any] | None,
    *,
    manifest_path: Path | None,
    frame_dimensions: tuple[int, int] | None = None,
) -> dict[str, Any]:
    """Require one evidence-bound placement profile for both subtitle tracks.

    Font identity and cmap coverage are intentionally language-specific and are
    validated by :func:`validate_font_binding`.
    """

    if font_config is None:
        raise ValueError("subtitle layout requires an explicit font config")
    raw = font_config.get("layout_profile")
    if not isinstance(raw, dict):
        raise ValueError("font config has no verified layout_profile")
    profile_id = str(raw.get("id", "")).strip()
    style = raw.get("style")
    if not profile_id or not isinstance(style, dict):
        raise ValueError("layout_profile requires id and style")
    try:
        font_size = float(style["font_size"])
        border_style = int(style["border_style"])
        outline = float(style["outline"])
        shadow = float(style["shadow"])
        margin_v = int(style["margin_v"])
        alignment = int(style["alignment"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("layout_profile style has invalid numeric fields") from error
    if (
        not math.isfinite(font_size)
        or font_size <= 0
        or border_style not in {1, 3}
        or not math.isfinite(outline)
        or outline < 0
        or not math.isfinite(shadow)
        or shadow < 0
        or margin_v < 0
        or not 1 <= alignment <= 9
    ):
        raise ValueError("layout_profile style values are out of range")
    if frame_dimensions is None:
        raise ValueError("subtitle layout requires native frame dimensions")
    frame_width, frame_height = frame_dimensions
    if frame_width <= 0 or frame_height <= 0:
        raise ValueError("subtitle layout has invalid native frame dimensions")
    vertical_extent = margin_v + font_size + 2 * outline + shadow
    if font_size > frame_height / 3 or vertical_extent >= frame_height:
        raise ValueError(
            "layout_profile places subtitle text outside the native-frame safe area"
        )
    primary_colour = str(style.get("primary_colour", "")).strip().upper()
    outline_colour = str(style.get("outline_colour", "")).strip().upper()
    if not ASS_COLOUR_RE.fullmatch(primary_colour) or not ASS_COLOUR_RE.fullmatch(
        outline_colour
    ):
        raise ValueError("layout_profile colours must be ASS &HXXXXXXXX values")
    config_path_value = str(font_config.get("_config_path", "")).strip()
    evidence_base = Path(config_path_value) if config_path_value else manifest_path
    evidence = validate_evidence(
        raw.get("evidence"),
        label="subtitle layout profile",
        fields={"font_size", "colours", "outline", "position"},
        manifest_path=evidence_base,
    )
    return {
        "id": profile_id,
        "style": {
            "font_size": font_size,
            "primary_colour": primary_colour,
            "outline_colour": outline_colour,
            "border_style": border_style,
            "outline": outline,
            "shadow": shadow,
            "margin_v": margin_v,
            "alignment": alignment,
        },
        "evidence": evidence,
    }


def validate_evidence(
    value: Any,
    *,
    label: str,
    fields: set[str],
    manifest_path: Path | None,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} evidence must be an object")
    kind = str(value.get("kind", "")).strip()
    if kind not in VERIFIED_EVIDENCE_KINDS:
        raise ValueError(
            f"{label} evidence.kind must be one of {VERIFIED_EVIDENCE_KINDS}"
        )
    references = value.get("references")
    if not isinstance(references, list) or not references:
        raise ValueError(f"{label} evidence.references must be a non-empty list")
    audited_references = []
    for reference_index, reference in enumerate(references):
        reference_label = f"{label} evidence reference {reference_index}"
        if not isinstance(reference, dict):
            raise ValueError(
                f"{reference_label} must bind path, sha256, and locator"
            )
        path_value = str(reference.get("path", "")).strip()
        expected_sha256 = str(reference.get("sha256", "")).strip().upper()
        locator = str(reference.get("locator", "")).strip()
        if not path_value or not SHA256_RE.fullmatch(expected_sha256) or not locator:
            raise ValueError(
                f"{reference_label} requires path, full sha256, and locator"
            )
        reference_path = _resolve_manifest_asset(path_value, manifest_path)
        actual_sha256 = file_sha256(reference_path)
        if expected_sha256 != actual_sha256:
            raise ValueError(
                f"{reference_label} SHA256 mismatch: expected={expected_sha256}, "
                f"actual={actual_sha256}"
            )
        audited_references.append(
            {
                "path": str(reference_path),
                "sha256": actual_sha256,
                "locator": locator,
            }
        )
    declared_fields = value.get("fields")
    if not isinstance(declared_fields, list):
        raise ValueError(f"{label} evidence.fields must be a list")
    missing_fields = fields - {str(field) for field in declared_fields}
    if missing_fields:
        raise ValueError(
            f"{label} evidence does not cover field(s): {sorted(missing_fields)}"
        )
    return {
        "kind": kind,
        "references": audited_references,
        "fields": sorted({str(field) for field in declared_fields}),
    }


def _resolve_manifest_asset(path_value: str, manifest_path: Path | None) -> Path:
    path = Path(path_value)
    if not path.is_absolute() and manifest_path is not None:
        path = manifest_path.parent / path
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"declared audio asset does not exist: {path}")
    return path


def inspect_audio_asset(path: Path, ffprobe: str = "ffprobe") -> dict[str, Any]:
    """Probe a source layer so bytes with an audio-looking suffix cannot pass."""

    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "stream=codec_name,codec_type,sample_rate,channels,channel_layout,duration:format=duration",
                "-of",
                "json",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        payload = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as error:
        raise ValueError(f"unable to probe declared audio asset {path}: {error}") from error
    audio_streams = [
        row for row in payload.get("streams", []) if row.get("codec_type") == "audio"
    ]
    if len(audio_streams) != 1:
        raise ValueError(f"declared audio asset must have exactly one audio stream: {path}")
    stream = audio_streams[0]
    try:
        sample_rate = int(stream["sample_rate"])
        channels = int(stream["channels"])
        duration_seconds = float(
            stream.get("duration") or payload["format"]["duration"]
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"declared audio asset lacks rate/channels/duration: {path}") from error
    if sample_rate <= 0 or channels <= 0 or duration_seconds <= 0:
        raise ValueError(f"declared audio asset has invalid media parameters: {path}")
    codec_name = str(stream.get("codec_name", "")).strip()
    if not codec_name:
        raise ValueError(f"declared audio asset lacks codec identity: {path}")
    return {
        "codec_name": codec_name,
        "sample_rate": sample_rate,
        "channels": channels,
        "channel_layout": str(stream.get("channel_layout", "")),
        "duration_ms": round(duration_seconds * 1000),
    }


def validate_artifact_reference(
    value: Any, *, label: str, manifest_path: Path | None
) -> dict[str, str] | None:
    if value in (None, ""):
        return None
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    path_value = str(value.get("path", "")).strip()
    sha256 = str(value.get("sha256", "")).strip().upper()
    locator = str(value.get("locator", "")).strip()
    if not path_value or not SHA256_RE.fullmatch(sha256) or not locator:
        raise ValueError(f"{label} requires path, full sha256, and locator")
    path = _resolve_manifest_asset(path_value, manifest_path)
    actual_sha256 = file_sha256(path)
    if actual_sha256 != sha256:
        raise ValueError(
            f"{label} SHA256 mismatch: expected={sha256}, actual={actual_sha256}"
        )
    return {"path": str(path), "sha256": actual_sha256, "locator": locator}


def _validated_volume(value: Any, unit: Any, *, label: str) -> tuple[float, str]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} volume must be numeric")
    volume = float(value)
    if not math.isfinite(volume):
        raise ValueError(f"{label} volume must be finite")
    volume_unit = str(unit).strip()
    if volume_unit not in {"linear", "db", "game_parameter"}:
        raise ValueError(
            f"{label} volume_unit must be linear, db, or game_parameter"
        )
    if volume_unit == "linear" and volume < 0:
        raise ValueError(f"{label} linear volume must be non-negative")
    return volume, volume_unit


def validate_voice_se_row(
    row: Any,
    *,
    index: int,
    manifest_path: Path | None,
    render_duration_ms: int | None,
    media_inspector: Callable[[Path], dict[str, Any]] = inspect_audio_asset,
) -> dict[str, Any]:
    """Bind every retained voice/SE row to bytes, timing, volume, and identity."""

    label = f"voice/SE row {index}"
    if not isinstance(row, dict):
        raise ValueError(f"{label} must be an object")
    path_value = str(row.get("path", "")).strip()
    expected_sha256 = str(
        row.get("sha256", row.get("source_sha256", ""))
    ).strip().upper()
    if not path_value or not SHA256_RE.fullmatch(expected_sha256):
        raise ValueError(f"{label} requires path and full source SHA-256")
    path = _resolve_manifest_asset(path_value, manifest_path)
    actual_sha256 = file_sha256(path)
    if actual_sha256 != expected_sha256:
        raise ValueError(
            f"{label} source SHA256 mismatch: expected={expected_sha256}, "
            f"actual={actual_sha256}"
        )
    audio_role = str(row.get("audio_role", "")).strip()
    if audio_role not in {"voice", "se"}:
        raise ValueError(
            f"{label} audio_role must be voice or se; opaque base_scene_audio "
            "could hide BGM from the no_bgm master"
        )
    identity = str(row.get("identity", "")).strip()
    if not identity:
        raise ValueError(f"{label} identity is required")
    try:
        start_ms = int(row["start_ms"])
        duration_ms = int(row["duration_ms"])
        source_offset_ms = int(row["source_offset_ms"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            f"{label} requires integer start_ms, duration_ms, source_offset_ms"
        ) from error
    if start_ms < 0 or duration_ms <= 0 or source_offset_ms < 0:
        raise ValueError(f"{label} has invalid timing")
    if render_duration_ms is not None and start_ms + duration_ms > render_duration_ms:
        raise ValueError(f"{label} extends beyond render_duration_ms")
    media = media_inspector(path)
    if source_offset_ms + duration_ms > int(media["duration_ms"]) + 20:
        raise ValueError(f"{label} reads beyond the declared source duration")
    volume, volume_unit = _validated_volume(
        row.get("volume"), row.get("volume_unit"), label=label
    )
    evidence = validate_evidence(
        row.get("evidence"),
        label=label,
        fields={"source", "timing", "identity", "volume"},
        manifest_path=manifest_path,
    )
    return {
        "path": str(path),
        "sha256": actual_sha256,
        "audio_role": audio_role,
        "identity": identity,
        "request_id": str(row.get("request_id", "")),
        "code_name": str(row.get("code_name", "")),
        "start_ms": start_ms,
        "duration_ms": duration_ms,
        "source_offset_ms": source_offset_ms,
        "volume": volume,
        "volume_unit": volume_unit,
        "source_media": media,
        "evidence": evidence,
    }


def validate_bgm_layer(
    layer: Any,
    *,
    index: int,
    manifest_path: Path | None,
    media_inspector: Callable[[Path], dict[str, Any]] = inspect_audio_asset,
) -> dict[str, Any]:
    label = f"with_bgm layer {index}"
    if not isinstance(layer, dict):
        raise ValueError(f"{label} must be an object")
    source = layer.get("source")
    if not isinstance(source, dict):
        raise ValueError(f"{label} source must be an object")
    source_path_value = str(source.get("path", "")).strip()
    if not source_path_value:
        raise ValueError(f"{label} source.path is required")
    source_sha256 = str(source.get("sha256", "")).strip().upper()
    if not SHA256_RE.fullmatch(source_sha256):
        raise ValueError(f"{label} source.sha256 must be a full SHA-256")
    source_path = _resolve_manifest_asset(source_path_value, manifest_path)
    actual_sha256 = file_sha256(source_path)
    if source_sha256 != actual_sha256:
        raise ValueError(
            f"{label} source SHA256 mismatch: expected={source_sha256}, "
            f"actual={actual_sha256}"
        )
    try:
        start_ms = int(layer["start_ms"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"{label} start_ms is required") from error
    if start_ms < 0:
        raise ValueError(f"{label} start_ms must be non-negative")
    try:
        end_ms = int(layer["end_ms"])
        source_offset_ms = int(layer["source_offset_ms"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"{label} end_ms/source_offset_ms are required") from error
    if end_ms <= start_ms or source_offset_ms < 0:
        raise ValueError(f"{label} has invalid end_ms/source_offset_ms")
    loop = layer.get("loop")
    if not isinstance(loop, bool):
        raise ValueError(f"{label} loop must be boolean")
    loop_start_ms = layer.get("loop_start_ms")
    loop_end_ms = layer.get("loop_end_ms")
    if loop:
        try:
            loop_start_ms = int(loop_start_ms)
            loop_end_ms = int(loop_end_ms)
        except (TypeError, ValueError) as error:
            raise ValueError(f"{label} loop points must be integers") from error
        if loop_start_ms < 0 or loop_end_ms <= loop_start_ms:
            raise ValueError(f"{label} has invalid loop points")
    elif loop_start_ms not in (None, "") or loop_end_ms not in (None, ""):
        raise ValueError(f"{label} non-loop layer must not declare loop points")
    else:
        loop_start_ms = None
        loop_end_ms = None
    media = media_inspector(source_path)
    source_duration_ms = int(media["duration_ms"])
    if source_offset_ms >= source_duration_ms:
        raise ValueError(f"{label} source_offset_ms is outside the source")
    if loop:
        assert loop_end_ms is not None
        if loop_end_ms > source_duration_ms:
            raise ValueError(f"{label} loop points exceed the source duration")
    elif source_offset_ms + (end_ms - start_ms) > source_duration_ms + 20:
        raise ValueError(f"{label} reads beyond the declared source duration")
    volume, volume_unit = _validated_volume(
        layer.get("volume"), layer.get("volume_unit"), label=label
    )
    raw_transitions = layer.get("volume_transitions")
    if not isinstance(raw_transitions, list) or not raw_transitions:
        raise ValueError(f"{label} volume_transitions must be a non-empty list")
    transitions = []
    previous_at_ms: int | None = None
    for transition_index, transition in enumerate(raw_transitions):
        transition_label = f"{label} transition {transition_index}"
        if not isinstance(transition, dict):
            raise ValueError(f"{transition_label} must be an object")
        try:
            at_ms = int(transition["at_ms"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"{transition_label} at_ms is required") from error
        if at_ms < start_ms or at_ms > end_ms:
            raise ValueError(f"{transition_label} is outside the BGM interval")
        if previous_at_ms is not None and at_ms <= previous_at_ms:
            raise ValueError(f"{label} transitions must be strictly ordered")
        transition_volume, transition_unit = _validated_volume(
            transition.get("volume"),
            transition.get("volume_unit"),
            label=transition_label,
        )
        kind = str(transition.get("kind", "")).strip()
        if kind not in {"initial", "duck", "restore", "fade", "stop"}:
            raise ValueError(f"{transition_label} has unsupported kind")
        transitions.append(
            {
                "at_ms": at_ms,
                "volume": transition_volume,
                "volume_unit": transition_unit,
                "kind": kind,
            }
        )
        previous_at_ms = at_ms
    if transitions[0] != {
        "at_ms": start_ms,
        "volume": volume,
        "volume_unit": volume_unit,
        "kind": "initial",
    }:
        raise ValueError(
            f"{label} first transition must reproduce its initial volume at start_ms"
        )
    evidence = validate_evidence(
        layer.get("evidence"),
        label=label,
        fields={"source", "timing", "volume", "loop_phase", "transitions"},
        manifest_path=manifest_path,
    )
    return {
        "source": {
            "path": str(source_path),
            "sha256": actual_sha256,
            "resource_id": str(source.get("resource_id", "")),
            "media": media,
        },
        "start_ms": start_ms,
        "end_ms": end_ms,
        "source_offset_ms": source_offset_ms,
        "loop": loop,
        "loop_start_ms": loop_start_ms,
        "loop_end_ms": loop_end_ms,
        "volume": volume,
        "volume_unit": volume_unit,
        "volume_transitions": transitions,
        "evidence": evidence,
    }


def validate_audio_master_contract(
    manifest: dict[str, Any],
    *,
    requested_profiles: Sequence[str],
    manifest_path: Path | None = None,
    media_inspector: Callable[[Path], dict[str, Any]] = inspect_audio_asset,
) -> dict[str, Any]:
    """Validate the two audio masters without inferring or synthesizing BGM."""

    contract = manifest.get("audio_master_contract")
    if not isinstance(contract, dict):
        raise ValueError(
            "full edition matrix requires an explicit audio_master_contract; "
            "unclassified existing audio cannot be relabelled as with_bgm/no_bgm"
        )
    if contract.get("schema") != AUDIO_MASTER_CONTRACT_SCHEMA:
        raise ValueError(
            f"audio_master_contract.schema must be {AUDIO_MASTER_CONTRACT_SCHEMA!r}"
        )
    voice_se_timeline = contract.get("voice_se_timeline")
    if not isinstance(voice_se_timeline, list):
        raise ValueError("audio_master_contract.voice_se_timeline must be a list")
    manifest_audio = manifest.get("audio")
    if not isinstance(manifest_audio, list):
        raise ValueError("manifest audio must be a list")
    if canonical_sha256(voice_se_timeline) != canonical_sha256(manifest_audio):
        raise ValueError(
            "audio_master_contract.voice_se_timeline differs from manifest audio"
        )
    render_duration_value = manifest.get("render_duration_ms")
    render_duration_ms = (
        None
        if render_duration_value in (None, "")
        else int(render_duration_value)
    )
    if render_duration_ms is None or render_duration_ms <= 0:
        raise ValueError(
            "verified audio_master_contract requires positive render_duration_ms"
        )
    audited_voice_se_timeline = [
        validate_voice_se_row(
            row,
            index=index,
            manifest_path=manifest_path,
            render_duration_ms=render_duration_ms,
            media_inspector=media_inspector,
        )
        for index, row in enumerate(voice_se_timeline)
    ]
    profiles = contract.get("profiles")
    if not isinstance(profiles, dict):
        raise ValueError("audio_master_contract.profiles must be an object")

    result_profiles: dict[str, Any] = {}
    for profile in requested_profiles:
        raw_profile = profiles.get(profile)
        if not isinstance(raw_profile, dict):
            raise ValueError(f"audio_master_contract has no profile {profile!r}")
        profile_evidence = validate_evidence(
            raw_profile.get("evidence"),
            label=f"audio profile {profile}",
            fields={"voice_se_preserved", "bgm_policy"},
            manifest_path=manifest_path,
        )
        raw_layers = raw_profile.get("bgm_layers")
        if not isinstance(raw_layers, list):
            raise ValueError(f"audio profile {profile} bgm_layers must be a list")
        if profile == AUDIO_PROFILE_NO_BGM:
            if raw_layers:
                raise ValueError("no_bgm profile must have an empty bgm_layers list")
            layers: list[dict[str, Any]] = []
        else:
            if not raw_layers:
                raise ValueError(
                    "with_bgm profile requires at least one evidenced BGM layer"
                )
            layers = [
                validate_bgm_layer(
                    layer,
                    index=index,
                    manifest_path=manifest_path,
                    media_inspector=media_inspector,
                )
                for index, layer in enumerate(raw_layers)
            ]
            if render_duration_ms is not None:
                if any(
                    layer["start_ms"] >= render_duration_ms
                    or layer["end_ms"] > render_duration_ms
                    for layer in layers
                ):
                    raise ValueError(
                        "with_bgm layer is outside render_duration_ms"
                    )
        result_profiles[profile] = {
            "profile": profile,
            "evidence": profile_evidence,
            "bgm_layers": layers,
            "voice_se_timeline_sha256": canonical_sha256(
                audited_voice_se_timeline
            ),
            "audio_timeline_sha256": canonical_sha256(
                {"voice_se": audited_voice_se_timeline, "bgm_layers": layers}
            ),
            "base_master_manifest": validate_artifact_reference(
                raw_profile.get("base_master_manifest"),
                label=f"audio profile {profile} base_master_manifest",
                manifest_path=manifest_path,
            ),
        }
    return {
        "schema": AUDIO_MASTER_CONTRACT_SCHEMA,
        "voice_se_timeline": audited_voice_se_timeline,
        "voice_se_timeline_sha256": canonical_sha256(audited_voice_se_timeline),
        "profiles": result_profiles,
    }


def build_edition_plan(
    manifest: dict[str, Any],
    *,
    editions: Sequence[str] | None = None,
    audio_profiles: Sequence[str] | None = None,
    legacy_compat: bool = False,
    font_config: dict[str, Any] | None = None,
    font_inspector: Callable[[Path, int], dict[str, Any]] = inspect_font,
    manifest_path: Path | None = None,
    audio_media_inspector: Callable[[Path], dict[str, Any]] = inspect_audio_asset,
) -> dict[str, Any]:
    """Validate shared timing plus per-language fonts and return an audit plan."""

    requested = normalize_requested_editions(
        editions, legacy_compat=legacy_compat
    )
    requested_audio_profiles = normalize_requested_audio_profiles(
        audio_profiles, legacy_compat=legacy_compat
    )
    tracks = subtitle_tracks_from_manifest(manifest)
    requested_languages = [value for value in requested if value != EDITION_NONE]
    missing_tracks = [language for language in requested_languages if language not in tracks]
    if missing_tracks:
        raise ValueError(
            "requested subtitle track(s) are absent; this engine does not "
            f"translate: {missing_tracks}"
        )

    timelines = {
        language: cue_timeline(tracks[language]) for language in requested_languages
    }
    if len(timelines) > 1:
        first_language = requested_languages[0]
        expected = timelines[first_language]
        for language in requested_languages[1:]:
            if timelines[language] != expected:
                raise ValueError(
                    f"subtitle timing mismatch: {first_language} and {language} "
                    "must use the same cue timeline"
                )

    duration_ms = manifest.get("render_duration_ms")
    if duration_ms not in (None, ""):
        duration_ms = int(duration_ms)
        for language in requested_languages:
            beyond = [
                cue for cue in tracks[language] if int(cue["end_ms"]) > duration_ms
            ]
            if beyond:
                raise ValueError(
                    f"{language} subtitle cue extends beyond render_duration_ms={duration_ms}"
                )

    track_plan: dict[str, Any] = {}
    for language in requested_languages:
        cues = tracks[language]
        track_plan[language] = {
            "language": language,
            "cue_count": len(cues),
            "timeline_sha256": canonical_sha256(cue_timeline(cues)),
            "text_sha256": canonical_sha256([cue["text"] for cue in cues]),
            "cues": cues,
            "font": validate_font_binding(
                language,
                cues,
                font_config,
                inspector=font_inspector,
            ),
        }

    subtitle_layout = (
        validate_layout_profile(
            font_config,
            manifest_path=manifest_path,
            frame_dimensions=(
                int(manifest.get("native_dimensions", {}).get("width", 0)),
                int(manifest.get("native_dimensions", {}).get("height", 0)),
            ),
        )
        if not legacy_compat
        and any(track_plan[language]["cues"] for language in requested_languages)
        else None
    )

    audio_timeline = manifest.get("audio", [])
    audio_contract = None
    subtitle_voice_binding = None
    if not legacy_compat:
        audio_contract = validate_audio_master_contract(
            manifest,
            requested_profiles=requested_audio_profiles,
            manifest_path=manifest_path,
            media_inspector=audio_media_inspector,
        )
        subtitle_voice_binding = validate_voice_subtitle_bindings(
            event=str(manifest.get("event", "")),
            tracks=tracks,
            voice_se_timeline=audio_contract["voice_se_timeline"],
        )
    edition_matrix = [
        {
            "id": f"{audio_profile}.{subtitle_edition}",
            "audio_profile": audio_profile,
            "subtitle_edition": subtitle_edition,
        }
        for audio_profile in requested_audio_profiles
        for subtitle_edition in requested
    ]
    return {
        "schema": EDITION_PLAN_SCHEMA,
        "event": str(manifest.get("event", "")),
        "requested_editions": requested,
        "requested_audio_profiles": requested_audio_profiles,
        "edition_matrix": edition_matrix,
        "edition_count": len(edition_matrix),
        "legacy_two_edition_compatible": legacy_compat,
        "audio_mode": "legacy_unclassified" if legacy_compat else "verified_matrix",
        "translation_performed": False,
        "shared_base_required": legacy_compat,
        "shared_video_timeline_required": True,
        "one_base_per_audio_profile_required": not legacy_compat,
        "shared_audio_timeline_sha256": canonical_sha256(audio_timeline),
        "shared_voice_se_timeline_sha256": (
            audio_contract["voice_se_timeline_sha256"] if audio_contract else None
        ),
        "audio_master_contract": audio_contract,
        "shared_subtitle_timeline_sha256": (
            canonical_sha256(next(iter(timelines.values()))) if timelines else None
        ),
        "tracks": track_plan,
        "subtitle_layout": subtitle_layout,
        "subtitle_voice_binding": subtitle_voice_binding,
    }


def normalize_render_editions(payload: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Read new edition maps or synthesize them from legacy two-edition keys."""

    raw = payload.get("editions")
    if raw is not None:
        if not isinstance(raw, dict):
            raise ValueError("render manifest editions must be an object")
        result: dict[str, dict[str, str]] = {}
        for edition, row in raw.items():
            if edition not in SUPPORTED_EDITIONS:
                raise ValueError(f"unsupported render edition: {edition}")
            if not isinstance(row, dict):
                raise ValueError(f"render edition {edition} must be an object")
            video = str(row.get("video", "")).strip()
            if not video:
                raise ValueError(f"render edition {edition} has no video")
            declared_language = str(row.get("language", edition)).strip()
            if declared_language != edition:
                raise ValueError(
                    f"render edition {edition} declares language={declared_language!r}"
                )
            subtitles = str(row.get("subtitles", "")).strip()
            if edition == EDITION_NONE and subtitles:
                raise ValueError("render none edition must not declare subtitles")
            result[edition] = {
                "video": video,
                "subtitles": subtitles,
                "language": declared_language,
            }
        if EDITION_NONE not in result:
            raise ValueError("render manifest editions has no none base")
        return result

    without = str(payload.get("without_subtitles", "")).strip()
    with_subtitles = str(payload.get("with_subtitles", "")).strip()
    subtitles = str(payload.get("subtitles", "")).strip()
    if not without:
        raise ValueError("legacy render manifest has no without_subtitles")
    result = {
        EDITION_NONE: {"video": without, "subtitles": "", "language": EDITION_NONE}
    }
    if with_subtitles:
        result["ja"] = {
            "video": with_subtitles,
            "subtitles": subtitles,
            "language": "ja",
        }
    return result


def normalize_render_edition_matrix(
    payload: dict[str, Any],
    *,
    allow_legacy: bool = False,
) -> dict[str, dict[str, Any]]:
    """Normalize a verified audio/subtitle matrix or an explicit legacy input."""

    raw_matrix = payload.get("edition_matrix")
    if raw_matrix is None:
        if not allow_legacy:
            raise ValueError(
                "render manifest has no verified edition_matrix; pass explicit "
                "legacy compatibility instead of guessing an audio profile"
            )
        return {
            LEGACY_AUDIO_PROFILE: {
                "audio_profile": LEGACY_AUDIO_PROFILE,
                "audio_sha256": str(payload.get("shared_audio_sha256", "")),
                "editions": normalize_render_editions(payload),
            }
        }
    if not isinstance(raw_matrix, dict):
        raise ValueError("render manifest edition_matrix must be an object")
    unknown_profiles = sorted(set(raw_matrix) - set(AUDIO_PROFILES))
    if unknown_profiles:
        raise ValueError(
            f"render manifest has unsupported audio profile(s): {unknown_profiles}"
        )
    result: dict[str, dict[str, Any]] = {}
    for profile, raw_profile in raw_matrix.items():
        if not isinstance(raw_profile, dict):
            raise ValueError(f"render audio profile {profile} must be an object")
        declared_profile = str(raw_profile.get("audio_profile", profile)).strip()
        if declared_profile != profile:
            raise ValueError(
                f"render audio profile {profile} declares {declared_profile!r}"
            )
        editions_raw = raw_profile.get("editions")
        editions = normalize_render_editions({"editions": editions_raw})
        if set(editions) != set(SUPPORTED_EDITIONS):
            raise ValueError(
                f"render audio profile {profile} must contain none, ja, and zh"
            )
        audio_hashes = {
            str(row.get("audio_sha256", "")).strip().upper()
            for row in editions_raw.values()
            if isinstance(row, dict)
        }
        if (
            "" in audio_hashes
            or len(audio_hashes) != 1
            or not SHA256_RE.fullmatch(next(iter(audio_hashes), ""))
        ):
            raise ValueError(
                f"render audio profile {profile} editions do not share one audio hash"
            )
        audio_sha256 = next(iter(audio_hashes))
        declared_audio_sha256 = str(
            raw_profile.get("audio_sha256", audio_sha256)
        ).strip().upper()
        if declared_audio_sha256 != audio_sha256:
            raise ValueError(
                f"render audio profile {profile} audio hash declaration mismatch"
            )
        result[profile] = {
            "audio_profile": profile,
            "audio_sha256": audio_sha256,
            "editions": editions,
            "audio_master": raw_profile.get("audio_master", {}),
        }
    if set(result) != set(AUDIO_PROFILES):
        raise ValueError(
            "verified edition_matrix must contain both with_bgm and no_bgm profiles"
        )
    if len({row["audio_sha256"] for row in result.values()}) != 2:
        raise ValueError(
            "verified with_bgm and no_bgm profiles must have different audio hashes"
        )
    return result
