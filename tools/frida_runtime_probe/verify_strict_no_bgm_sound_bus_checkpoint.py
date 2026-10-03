#!/usr/bin/env python3
"""Validate the bounded v69 IDA sound-bus correction checkpoint."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "magireco-strict-no-bgm-sound-bus-corrections-v1"
SHA256_RE = re.compile(r"^[0-9A-F]{64}$")
EXPECTED_EVENTS = {
    "ac0911_011": ("228", 553, ["424", "8044"]),
    "ac7205_016": ("226", 551, ["10390", "10394", "8314", "419"]),
    "ac1103_013": (
        "229",
        554,
        ["1086", "3549", "3550", "4058", "4059", "3543", "1041"],
    ),
}
FORBIDDEN_EVENTS = {"ac6003", "ac6004", "ac6005"}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _hash(value: Any, *, label: str) -> str:
    result = str(value).strip().upper()
    if not SHA256_RE.fullmatch(result):
        raise ValueError(f"{label} is not an uppercase SHA-256")
    return result


def _artifact(row: Mapping[str, Any], *, label: str, verify_local: bool) -> None:
    if set(row) != {"path", "sha256"}:
        raise ValueError(f"{label} artifact fields differ")
    path = Path(str(row["path"]))
    expected = _hash(row["sha256"], label=f"{label} SHA-256")
    if verify_local:
        if not path.is_file():
            raise FileNotFoundError(f"{label} is missing: {path}")
        if file_sha256(path) != expected:
            raise ValueError(f"{label} SHA-256 differs: {path}")


def validate_checkpoint(value: Mapping[str, Any], *, verify_local: bool = False) -> dict[str, int]:
    if value.get("schema") != SCHEMA or value.get("status") != "AUTOMATED_QA_PASSED_HUMAN_PLAYBACK_REQUIRED":
        raise ValueError("checkpoint identity/status differs")
    authority = value.get("ida_authority")
    if not isinstance(authority, Mapping):
        raise ValueError("checkpoint lacks IDA authority")
    if authority.get("sound_divide_tbl") != {"0": "BGM", "1": "SE", "2": "VOICE"}:
        raise ValueError("SOUND_DIVIDE_TBL mapping differs")
    _hash(authority.get("libgameproc_sha256"), label="libGameProc SHA-256")
    products = value.get("products")
    if not isinstance(products, list) or len(products) != 3:
        raise ValueError("checkpoint must contain exactly three corrected products")
    observed = {}
    media_count = 0
    for index, product in enumerate(products):
        if not isinstance(product, Mapping):
            raise ValueError(f"product {index} is not an object")
        event = str(product.get("changed_event", ""))
        if event in observed or event not in EXPECTED_EVENTS:
            raise ValueError(f"unexpected or duplicate changed event: {event}")
        excluded_request, excluded_sound, retained = EXPECTED_EVENTS[event]
        exclusion = product.get("excluded_bgm_bus_audio")
        if not isinstance(exclusion, Mapping) or (
            str(exclusion.get("request_id")),
            int(exclusion.get("sound_id", -1)),
            int(exclusion.get("volume_kind_value", -1)),
            str(exclusion.get("volume_bus", "")),
        ) != (excluded_request, excluded_sound, 0, "BGM"):
            raise ValueError(f"{event} BGM exclusion differs")
        if product.get("retained_request_ids") != retained:
            raise ValueError(f"{event} retained request set/order differs")
        editions = product.get("media")
        if not isinstance(editions, Mapping) or set(editions) != {"none", "ja", "zh"}:
            raise ValueError(f"{event} edition set differs")
        for edition, artifact in editions.items():
            if not isinstance(artifact, Mapping):
                raise ValueError(f"{event} {edition} artifact is not an object")
            _artifact(artifact, label=f"{event} {edition}", verify_local=verify_local)
            media_count += 1
        roles = product.get("verified_roles")
        if not isinstance(roles, Mapping) or set(roles) != {
            "modified_artifact",
            "patch_diff",
            "verification_record",
            "rollback",
        }:
            raise ValueError(f"{event} verified roles differ")
        for role, artifact in roles.items():
            if role == "modified_artifact":
                if not isinstance(artifact, Mapping) or set(artifact) != {"path"}:
                    raise ValueError(f"{event} modified artifact fields differ")
                if verify_local and not Path(str(artifact["path"])).is_dir():
                    raise FileNotFoundError(f"{event} modified artifact is missing")
                continue
            if not isinstance(artifact, Mapping):
                raise ValueError(f"{event} {role} artifact is not an object")
            _artifact(artifact, label=f"{event} {role}", verify_local=verify_local)
        if event == "ac1103_013" and product.get("merged_voice_request_ids") != ["4058", "4059"]:
            raise ValueError("ac1103 merged adjacent voice binding differs")
        observed[event] = product
    if set(observed) != set(EXPECTED_EVENTS):
        raise ValueError("corrected event coverage differs")
    inventory = value.get("inventory_delta")
    if not isinstance(inventory, Mapping) or inventory.get("items") != 9 or inventory.get("withdrawals") != 7:
        raise ValueError("inventory delta counts differ")
    for name in ("inventory", "supersession", "verification", "sha256sums"):
        artifact = inventory.get(name)
        if not isinstance(artifact, Mapping):
            raise ValueError(f"inventory {name} artifact is missing")
        _artifact(artifact, label=f"inventory {name}", verify_local=verify_local)
    invariants = value.get("fail_closed_invariants")
    if not isinstance(invariants, Mapping) or any(invariants.get(key) is not True for key in (
        "p16_p17_p18_quarantined",
        "child_local_only_not_ready",
        "auto_qa_not_human_approval",
        "native_resolution_no_upscale",
        "source_media_preserved",
        "bilibili_upload_not_performed",
    )):
        raise ValueError("fail-closed invariants differ")
    serialized = json.dumps(value, ensure_ascii=False).lower()
    if any(event in serialized for event in FORBIDDEN_EVENTS):
        # The invariant name may mention P16/P17/P18, but event IDs must not enter
        # any corrected product or inventory artifact.
        raise ValueError("quarantined event leaked into checkpoint paths/data")
    return {"products": 3, "media": media_count, "inventory_items": 9, "withdrawals": 7}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--verify-local-artifacts", action="store_true")
    args = parser.parse_args()
    path = Path(args.plan).resolve()
    value = json.loads(path.read_text(encoding="utf-8"))
    counts = validate_checkpoint(value, verify_local=args.verify_local_artifacts)
    print(json.dumps({"result": "PASS", "plan": str(path), **counts}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
