#!/usr/bin/env python3
"""Canonical, non-cyclic contract for an event's visual composition.

The clean-visual render is an input to later audio and subtitle stages.  Those
later stages add their own fields to a bound event-manifest copy, so hashing the
whole manifest would either create a cycle or make unrelated audio changes look
like visual changes.  This module deliberately projects only the fields which
can change the pixels or the native presentation timeline.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from fractions import Fraction
from typing import Any


COMPOSITION_CONTRACT_SCHEMA = "magireco-composition-contract-projection-v1"


def composition_contract_projection(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return the exact visual-composition projection bound by production QA."""

    if not isinstance(manifest, dict):
        raise RuntimeError("event manifest must be a JSON object")
    return {
        "schema": COMPOSITION_CONTRACT_SCHEMA,
        "event": copy.deepcopy(manifest.get("event")),
        "native_dimensions": copy.deepcopy(manifest.get("native_dimensions")),
        "native_frame_rate": copy.deepcopy(manifest.get("native_frame_rate")),
        "video_duration_ms": copy.deepcopy(manifest.get("video_duration_ms")),
        "timeline_content_end_ms": copy.deepcopy(
            manifest.get("timeline_content_end_ms")
        ),
        "raw_render_duration_ms": copy.deepcopy(
            manifest.get("raw_render_duration_ms")
        ),
        "render_frame_count": copy.deepcopy(manifest.get("render_frame_count")),
        "render_duration_ms": copy.deepcopy(manifest.get("render_duration_ms")),
        "render_duration_quantization": copy.deepcopy(
            manifest.get("render_duration_quantization")
        ),
        "video_extension_policy": copy.deepcopy(
            manifest.get("video_extension_policy")
        ),
        "video_composition_model": copy.deepcopy(
            manifest.get("video_composition_model")
        ),
        "composition_plan": copy.deepcopy(manifest.get("composition_plan")),
        "clips": copy.deepcopy(manifest.get("clips")),
    }


def composition_contract_sha256(manifest: dict[str, Any]) -> str:
    projection = composition_contract_projection(manifest)
    encoded = json.dumps(
        projection,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def presentation_sample_count(
    manifest: dict[str, Any], *, sample_rate: int = 48000
) -> int:
    """Return the audio samples needed to cover the exact CFR video tail."""

    if sample_rate <= 0:
        raise RuntimeError("sample_rate must be positive")
    quantization = manifest.get("render_duration_quantization")
    if not isinstance(quantization, dict) or not quantization:
        try:
            duration_ms = int(manifest["render_duration_ms"])
        except (KeyError, TypeError, ValueError) as error:
            raise RuntimeError("event manifest lacks render_duration_ms") from error
        if duration_ms <= 0 or (duration_ms * sample_rate) % 1000:
            raise RuntimeError(
                "legacy render_duration_ms is not exactly representable at the "
                "audio sample rate"
            )
        return duration_ms * sample_rate // 1000

    try:
        rate = Fraction(str(quantization["frame_rate"]))
        manifest_rate = Fraction(str(manifest["native_frame_rate"]))
        frame_count = int(quantization["frame_count"])
        declared_frame_count = int(manifest["render_frame_count"])
        content_end_ms = int(quantization["content_end_ms"])
        duration_ms = int(quantization["duration_ms"])
        declared_duration_ms = int(manifest["render_duration_ms"])
        exact_numerator = int(quantization["exact_duration_ms_numerator"])
        exact_denominator = int(quantization["exact_duration_ms_denominator"])
        declared_sample_rate = int(quantization["audio_sample_rate"])
        declared_sample_count = int(quantization["audio_sample_count"])
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as error:
        raise RuntimeError("render duration quantization is incomplete") from error
    if rate <= 0 or rate != manifest_rate:
        raise RuntimeError("render duration quantization frame rate mismatch")
    if frame_count <= 0 or frame_count != declared_frame_count:
        raise RuntimeError("render duration quantization frame count mismatch")
    exact_duration_ms = Fraction(frame_count * 1000, 1) / rate
    if exact_duration_ms != Fraction(exact_numerator, exact_denominator):
        raise RuntimeError("render duration quantization exact duration mismatch")
    if duration_ms != int(round(exact_duration_ms)) or duration_ms != declared_duration_ms:
        raise RuntimeError("render duration quantization rounded duration mismatch")
    if Fraction(content_end_ms, 1) > exact_duration_ms:
        raise RuntimeError("render duration quantization trims the content tail")
    expected_samples = math.ceil(Fraction(frame_count * sample_rate, 1) / rate)
    if declared_sample_rate != sample_rate or declared_sample_count != expected_samples:
        raise RuntimeError("render duration quantization audio sample count mismatch")
    return expected_samples
