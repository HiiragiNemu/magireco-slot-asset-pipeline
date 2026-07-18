#!/usr/bin/env python3
"""State-driven natural SP-story capture with strict runtime evidence gates.

The default mode is a read-only dry run: it verifies foreground/PID identity,
attaches one ARM64 Gadget session, loads the existing probes, and writes only a
small journal.  ADB input is possible only with explicit ``--execute``.

During an executed hunt, no coordinate is trusted by itself.  MAX BET and the
lever advance only when the same Gadget session observes their exact non-zero
``CSlotBody::process`` input bit.  A stop additionally requires the game's
``state+0x64`` progress mask to advance; an input bit alone only proves that the
tap reached ``process`` and can still be rejected by the reel logic.  Heavy
probe messages stay in memory for each attempt.  A non-target attempt writes
only one compact journal row; observer JSONL, hashes, and a manifest are written
only after a real dispatch batch contains both ID19 raw[1] == 8 and a legal
ID24 stage/selector pair.
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import queue
import struct
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

import frida

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.frida_runtime_probe.summarize_lightweight_spin_probe import (
    DispatchBatchTracker,
)


PACKAGE = "com.universal777.magireco"
ACTIVITY = ".SlotMainActivity"
EXPECTED_INPUT_BITS = {
    "max_bet": 1048576,
    "lever": 524288,
    "left_stop": 2,
    "middle_stop": 4,
    "right_stop": 8,
}
STOP_PROGRESS_MASKS = {
    "left_stop": 0x00200000,
    "middle_stop": 0x00600000,
    "right_stop": 0x00E00000,
}
TARGETS_BY_STAGE_SELECTOR = {
    (11, 1): {
        "event": "ac7114_001",
        "event_code_hex": "0x4f71466b3d723041",
        "scene_key": "A0r=kFqO",
    },
    (11, 2): {
        "event": "ac7114_001",
        "event_code_hex": "0x4f71466b3d723041",
        "scene_key": "A0r=kFqO",
    },
    (12, 1): {
        "event": "ac7115_001",
        "event_code_hex": "0x5773382374447854",
        "scene_key": "TxDt#8sW",
    },
    (12, 2): {
        "event": "ac7115_001",
        "event_code_hex": "0x5773382374447854",
        "scene_key": "TxDt#8sW",
    },
    (12, 3): {
        "event": "ac7115_001",
        "event_code_hex": "0x5773382374447854",
        "scene_key": "TxDt#8sW",
    },
    (12, 4): {
        "event": "ac7115_001",
        "event_code_hex": "0x5773382374447854",
        "scene_key": "TxDt#8sW",
    },
    (13, 1): {
        "event": "ac7116_001",
        "event_code_hex": "0x2476304366614152",
        "scene_key": "RAafC0v$",
    },
    (13, 2): {
        "event": "ac7116_001",
        "event_code_hex": "0x2476304366614152",
        "scene_key": "RAafC0v$",
    },
}
PROBE_FILES = {
    "slot_gate": "slot_state_gate_probe.js",
    "dispatch": "sp_story_dispatch_hunt_probe.js",
    "sound_logic": "sound_logic_chain_probe.js",
}
READY_KINDS = {
    "slot_gate": "slot_gate_probe_ready",
    "dispatch": "sp_story_dispatch_hunt_probe_ready",
    "sound_logic": "sound_logic_probe_ready",
}
SOUND_REQUEST_TRACE_KINDS = frozenset(
    {
        "sound_logic_code_name_to_request_id",
        "sound_logic_zg_snd_req_id",
        "sound_logic_request_ctrl_get_request",
        "sound_logic_request_ctrl_set_request_list",
        "sound_logic_player_perform_request",
        "sound_logic_sound_mng_snd_play_req_enter",
        "sound_logic_sound_mng_snd_play_req_leave",
        "sound_logic_csl_mng_snd_req_enqueue",
        "sound_logic_csl_mng_play_start",
        "sound_logic_bgm_upstream_kndcal_cc_dir_end",
        "sound_logic_bgm_upstream_kndcal_rl_start",
        "sound_logic_bgm_upstream_update_gm_data_commit",
        "sound_logic_bgm_upstream_data_set_dir_commit",
        "sound_logic_bgm_upstream_bgm_dir_request",
        "sound_logic_bgm_upstream_trace_overflow",
    }
)
MAX_SOUND_REQUEST_TRACE_EVENTS = 2048
SOUND_REQUEST_TRACE_FIELDS = (
    "thread_id",
    "call_count_for_kind",
    "code_string",
    "code_text_error",
    "code_pointer",
    "request_id_i32",
    "request_arg1_i32",
    "request_arg2_i32",
    "get_request_success_i32",
    "derived_request_ids",
    "request_id_association_basis",
    "context_id",
    "context_code",
    "request_ctrl_pointer",
    "perform_invocation_id",
    "perform_arg3_bool",
    "order_request_id_u32",
    "order_code",
    "order_association_basis",
    "play_request_call_id",
    "sound_mng_pointer",
    "sound_resource_id_i32",
    "play_index_or_bank_i32",
    "request_arg3_i32",
    "perform_order_request_id_u32",
    "perform_order_code",
    "perform_function_type_name",
    "perform_player_channel_i32",
    "perform_association_basis",
    "return_i32",
    "csl_enqueue_id",
    "csl_mng_pointer",
    "requested_sound_resource_id_i32",
    "request_mode_i32",
    "callback_remap_possible",
    "request_table_valid",
    "request_table_error",
    "request_table_begin_pointer",
    "request_table_end_pointer",
    "request_table_byte_length",
    "request_table_row_count",
    "request_table_row_index",
    "request_table_entry_sound_resource_id_u16",
    "request_table_entry_slot_index_u16",
    "sound_data_pointer",
    "active_slot_pointer",
    "pending_sound_data_pointer_after_request",
    "enqueue_committed",
    "pending_enqueue_key",
    "replaced_pending_csl_enqueue_id",
    "play_index_i32",
    "causal_csl_enqueue_id",
    "causal_play_request_call_id",
    "causal_sound_resource_id_i32",
    "causal_perform_invocation_id",
    "causal_perform_order_request_id_u32",
    "causal_perform_order_code",
    "causal_request_table_row_index",
    "causal_association_basis",
    "request",
    "order",
    "sound",
    "bgm_upstream_hook",
    "bgm_upstream_call_id",
    "bgm_upstream_window_label",
    "bgm_upstream_window_epoch",
    "bgm_upstream_window_event_index",
    "bgm_upstream_state_partition",
    "emission_reason",
    "sdgm_pointer_entry",
    "sdgm_pointer_leave",
    "mstcomcbk_pointer",
    "obj_nml_pointer",
    "entry",
    "leave",
    "committed",
    "changed_fields",
    "maximum_emitted_events",
    "dropped_event_count",
    "overflow_policy",
    "return_address",
    "return_module",
    "return_module_offset",
    "return_symbol",
)
SOUND_PACK_REFERENCE_KEYS = {
    0: 67,
    1: 171,
    60: 778,
    67: 786,
    119: 863,
    151: 6103,
    169: 9070,
    170: 9071,
    171: 16716,
    181: 38009,
    219: 41030,
    220: 41031,
    221: 41032,
}
EXPECTED_SOUND_CAPTURE_SCOPE = {
    "code_lookups": "all",
    "request_ids": "all",
    "request_metadata": "all_bounded_to_8_reqdata_rows",
    "perform_orders": "all",
    "sound_play_requests": "all_metadata_only",
    "sound_pack_pre_gate_volume": "gate_table_members_only_read_only_reconstruction",
    "csl_request_enqueue": "bounded_named_table_and_pending_slot_fields_only",
    "csl_play_start": "all_metadata_only",
    "target_bgm_upstream": "named_fields_only_explicit_attempt_window",
    "temporal_context_is_causal": False,
    "synchronous_nested_invocation_ids_are_causal": True,
}
EXPECTED_SOUND_HOOKS = {
    "codeName2ReqId": (
        "_ZN2zg3snd11RequestCtrl14codeName2ReqIdEPKc",
        "0x4288b28",
    ),
    "zgSndReqId": ("zgSndReqId", "0x4272e28"),
    "getRequest": (
        "_ZN2zg3snd11RequestCtrl10getRequestEjRNS0_7RequestE",
        "0x42891a4",
    ),
    "setRequestList": (
        "_ZN2zg3snd11RequestCtrl14setRequestListERKNS0_7RequestE",
        "0x428927c",
    ),
    "performRequest": (
        "_ZN2zg3snd10PlayerImpl14performRequestERNS0_11RequestCtrlERNS0_8ReqOrderEb",
        "0x4282a3c",
    ),
    "soundMngSndPlayReq": ("_ZN8SoundMng10sndPlayReqEiii", "0x425fbdc"),
    "cslMngSndReq": ("_ZN6CSLMng6SndReqEii", "0x130124"),
    "cslMngPlayStart": ("_ZN6CSLMng9PlayStartEP11SSound_Datai", "0x12fa9c"),
    "kndCalLotCcDirEnd": ("fnKndCalLot_CcDirEnd", "0x4445e3c"),
    "kndCalLotRlStart": ("fnKndCalLot_RlStart", "0x444466c"),
    "mstComCbkUpdateGmData": (
        "_ZN11C_MstComCbk14fnUpDateGmDataEv",
        "0x4399a4c",
    ),
    "anmBaseDataSetDir": ("_ZN9C_AnmBase16fnDataSetDir_DIREv", "0x4387f90"),
    "objNmlSndRequestBgmDir": (
        "_ZN8C_ObjNml20fnSndRequest_BGM_DIREv",
        "0x43a86b0",
    ),
}
EXPECTED_GAME_PROC_SHA256 = (
    "5A0AE3CE7F25B89A3B9A13D11BF36AAA1DE04FACEB612357FA04F42426F17EBF"
)
EXPECTED_GAME_PROC_SIZE_BYTES = 79683640
EXPECTED_ARM64_SPLIT_SHA256 = (
    "89ACC81D02FF63697603FCE2E5F4281850C092FA833FD8CF3E636B44AB624E24"
)
EXPECTED_ARM64_SPLIT_SIZE_BYTES = 83710748
EXPECTED_ARM64_SPLIT_BASENAME = "split_config.arm64_v8a.apk"
EXPECTED_GAME_PROC_APK_ENTRY = "lib/arm64-v8a/libGameProc.so"
EXPECTED_GAME_PROC_APK_LOCAL_HEADER_OFFSET = 2469872
EXPECTED_GAME_PROC_APK_DATA_OFFSET = 2473984
EXPECTED_GAME_PROC_APK_COMPRESSION_METHOD = 0
EXPECTED_GAME_PROC_APK_CRC32 = "BBB59DED"
EXPECTED_BGM_UPSTREAM_FIELD_SCHEMA = {
    "schema": "magireco-target-bgm-upstream-field-schema-v1",
    "sdgm_snapshot_fields": {
        "current_kind_u16_at_0x13da": {"offset": "0x13da", "type": "u16"},
        "next_kind_u16_at_0x13dc": {"offset": "0x13dc", "type": "u16"},
        "current_no_u16_at_0x13de": {"offset": "0x13de", "type": "u16"},
        "next_no_u16_at_0x13e0": {"offset": "0x13e0", "type": "u16"},
        "restore_state_u16_at_0x1472": {"offset": "0x1472", "type": "u16"},
        "saved_kind_u16_at_0x1474": {"offset": "0x1474", "type": "u16"},
        "saved_no_u16_at_0x149a": {"offset": "0x149a", "type": "u16"},
    },
    "mstcomcbk_commit_fields": {
        "committed_kind_u16_at_0x0a72": {"offset": "0xa72", "type": "u16"},
        "committed_no_u16_at_0x0a76": {"offset": "0xa76", "type": "u16"},
    },
    "obj_nml_snapshot_fields": {
        "direction_kind_u16_at_0x00ca": {"offset": "0xca", "type": "u16"},
        "direction_no_u16_at_0x011a": {"offset": "0x11a", "type": "u16"},
        "cached_code_pointer_at_0x0800": {"offset": "0x800", "type": "pointer"},
        "cached_code_string_at_0x0800": {
            "offset": "0x800",
            "type": "nul_terminated_utf8",
            "maximum_bytes": 64,
        },
        "cached_code_text_error_at_0x0800": {
            "offset": "0x800",
            "type": "bounded_read_diagnostic_string",
        },
    },
    "event_kinds": {
        "knd_cal_lot_cc_dir_end": "sound_logic_bgm_upstream_kndcal_cc_dir_end",
        "knd_cal_lot_rl_start": "sound_logic_bgm_upstream_kndcal_rl_start",
        "update_gm_data_commit": "sound_logic_bgm_upstream_update_gm_data_commit",
        "data_set_dir_commit": "sound_logic_bgm_upstream_data_set_dir_commit",
        "bgm_dir_request": "sound_logic_bgm_upstream_bgm_dir_request",
        "trace_overflow": "sound_logic_bgm_upstream_trace_overflow",
    },
    "emission_policy": {
        "window_control": "explicit_rpc_begin_end",
        "lottery_hooks": "every_entry_leave_pair_within_window",
        "high_frequency_hooks": "first_observation_or_state_change_within_window",
        "maximum_emitted_events_per_window": 1024,
        "overflow_policy": "emit_overflow_once_and_fail_attempt",
        "read_only_observer": True,
    },
}
EXPECTED_BGM_UPSTREAM_HOOK_KEYS = frozenset(
    {
        "kndCalLotCcDirEnd",
        "kndCalLotRlStart",
        "mstComCbkUpdateGmData",
        "anmBaseDataSetDir",
        "objNmlSndRequestBgmDir",
    }
)


class HuntError(RuntimeError):
    """A safety/evidence invariant failed."""


def compact_sound_request_event(
    payload: dict[str, Any],
    *,
    sequence: int,
    host_unix_ms: Any,
) -> dict[str, Any]:
    """Retain the bounded metadata needed to join one native sound call chain."""

    row: dict[str, Any] = {
        "sequence": sequence,
        "host_unix_ms": host_unix_ms,
        "source_unix_ms": payload.get("unix_ms"),
        "kind": str(payload.get("kind") or ""),
    }
    for key in SOUND_REQUEST_TRACE_FIELDS:
        if key in payload:
            row[key] = copy.deepcopy(payload[key])
    return row


def validate_bgm_upstream_window_contract(
    payload: Any,
    *,
    expected_active: bool,
    expected_epoch: int | None = None,
) -> dict[str, Any]:
    """Validate one exact, read-only attempt-window response from the probe."""

    if not isinstance(payload, dict):
        raise HuntError(f"BGM upstream window response is not an object: {payload!r}")
    if payload.get("schema") != "magireco-target-bgm-upstream-window-v1":
        raise HuntError("BGM upstream window response has an unexpected schema")
    if payload.get("active") is not expected_active:
        raise HuntError("BGM upstream window response has the wrong active state")
    if payload.get("read_only_observer") is not True:
        raise HuntError("BGM upstream window is not declared read-only")
    try:
        epoch = int(payload["epoch"])
        emitted = int(payload["emitted_event_count"])
        dropped = int(payload["dropped_event_count"])
        maximum = int(payload["maximum_emitted_events"])
    except (KeyError, TypeError, ValueError) as error:
        raise HuntError("BGM upstream window response has invalid counters") from error
    if epoch <= 0 or emitted < 0 or dropped < 0 or maximum != 1024:
        raise HuntError("BGM upstream window response counters violate the bounded contract")
    if expected_epoch is not None and epoch != expected_epoch:
        raise HuntError(
            f"BGM upstream window epoch changed unexpectedly: {expected_epoch} -> {epoch}"
        )
    if dropped != 0:
        raise HuntError("BGM upstream window dropped events")
    return copy.deepcopy(payload)


def validate_probe_ready_contracts(
    ready_payloads: dict[str, dict[str, Any]],
    *,
    installed_split_identity: dict[str, Any],
) -> None:
    """Fail before ADB input if any evidence hook is weaker than this hunter needs."""

    slot_gate = ready_payloads.get("slot_gate")
    if not isinstance(slot_gate, dict):
        raise HuntError("slot-gate ready payload is missing")
    for key in ("installed", "process_hook_installed", "reel_stop_hook_installed"):
        if slot_gate.get(key) is not True:
            raise HuntError(f"slot-gate ready contract requires {key}=true")

    dispatch = ready_payloads.get("dispatch")
    if not isinstance(dispatch, dict):
        raise HuntError("dispatch ready payload is missing")
    for key in (
        "installed",
        "required_hooks_installed",
        "optional_sound_event_hook_installed",
        "optional_lottery_hook_installed",
    ):
        if dispatch.get(key) is not True:
            raise HuntError(f"dispatch ready contract requires {key}=true")

    sound_logic = ready_payloads.get("sound_logic")
    if not isinstance(sound_logic, dict):
        raise HuntError("sound-logic ready payload is missing")
    if int(sound_logic.get("installed_hook_event_count") or 0) != len(
        EXPECTED_SOUND_HOOKS
    ):
        raise HuntError("sound-logic ready contract requires every primary hook")
    for key in ("unavailable_hook_event_count", "attach_error_event_count"):
        if int(sound_logic.get(key) or 0) != 0:
            raise HuntError(f"sound-logic ready contract requires {key}=0")
    hook_status = sound_logic.get("hook_status")
    if not isinstance(hook_status, dict) or set(hook_status) != set(
        EXPECTED_SOUND_HOOKS
    ):
        raise HuntError("sound-logic hook status does not name exactly every primary hook")
    for key, (expected_symbol, expected_offset) in EXPECTED_SOUND_HOOKS.items():
        status = hook_status.get(key)
        if not isinstance(status, dict):
            raise HuntError(f"sound-logic hook {key} status is not an object")
        if (
            status.get("status") != "installed"
            or status.get("symbol") != expected_symbol
            or str(status.get("actual_module_offset") or "").lower()
            != expected_offset
            or str(status.get("expected_module_offset") or "").lower()
            != expected_offset
            or status.get("module_offset_matches_static_reference") is not True
            or not status.get("module")
            or not status.get("module_path")
        ):
            raise HuntError(f"sound-logic hook {key} is not version-checked installed")

    host_split_identity = validate_installed_arm64_split_identity(
        installed_split_identity
    )
    game_proc_identity = sound_logic.get("game_proc_identity_status")
    if not isinstance(game_proc_identity, dict):
        raise HuntError("libGameProc identity status is missing")
    if (
        game_proc_identity.get("status") != "ready"
        or game_proc_identity.get("mapping_kind")
        != "apk_backed_uncompressed_elf"
        or game_proc_identity.get("logical_library_name") != "libGameProc.so"
        or game_proc_identity.get("container_module")
        != EXPECTED_ARM64_SPLIT_BASENAME
        or game_proc_identity.get("container_path")
        != host_split_identity["device_apk_path"]
        or game_proc_identity.get("expected_container_module")
        != EXPECTED_ARM64_SPLIT_BASENAME
        or game_proc_identity.get("container_name_matches") is not True
        or game_proc_identity.get("container_path_matches") is not True
        or not game_proc_identity.get("derived_elf_base")
        or game_proc_identity.get("reported_base_matches_derived") is not True
        or game_proc_identity.get("anchor_symbol") != "fnGetAddrSdGmData"
        or str(game_proc_identity.get("actual_anchor_derived_elf_offset") or "").lower()
        != "0x424d474"
        or str(game_proc_identity.get("expected_anchor_offset") or "").lower()
        != "0x424d474"
        or str(game_proc_identity.get("reported_anchor_module_offset") or "").lower()
        != "0x424d474"
        or game_proc_identity.get("anchor_offset_matches") is not True
        or game_proc_identity.get("elf_header_matches_aarch64") is not True
        or game_proc_identity.get("all_export_checks_match") is not True
        or game_proc_identity.get("installed_container_identity_required_from_host")
        is not True
        or str(game_proc_identity.get("expected_container_sha256") or "").upper()
        != EXPECTED_ARM64_SPLIT_SHA256
        or int(game_proc_identity.get("expected_container_size_bytes") or -1)
        != EXPECTED_ARM64_SPLIT_SIZE_BYTES
        or game_proc_identity.get("read_only_verification") is not True
    ):
        raise HuntError("APK-backed libGameProc runtime mapping identity is not exact")
    elf_header = game_proc_identity.get("elf_header")
    if elf_header != {
        "magic_u32_le_at_0x00": 0x464C457F,
        "class_u8_at_0x04": 2,
        "data_encoding_u8_at_0x05": 1,
        "machine_u16_at_0x12": 183,
    }:
        raise HuntError("APK-backed libGameProc ELF header contract mismatch")
    bound_entry = game_proc_identity.get("bound_apk_entry")
    if bound_entry != {
        "path": EXPECTED_GAME_PROC_APK_ENTRY,
        "compression_method": EXPECTED_GAME_PROC_APK_COMPRESSION_METHOD,
        "crc32": EXPECTED_GAME_PROC_APK_CRC32,
        "local_header_offset": EXPECTED_GAME_PROC_APK_LOCAL_HEADER_OFFSET,
        "data_offset": EXPECTED_GAME_PROC_APK_DATA_OFFSET,
        "compressed_size_bytes": EXPECTED_GAME_PROC_SIZE_BYTES,
        "uncompressed_size_bytes": EXPECTED_GAME_PROC_SIZE_BYTES,
        "expected_uncompressed_sha256": EXPECTED_GAME_PROC_SHA256,
    }:
        raise HuntError("APK-backed libGameProc entry binding contract mismatch")
    export_checks = game_proc_identity.get("export_checks")
    if not isinstance(export_checks, list) or len(export_checks) != len(
        EXPECTED_BGM_UPSTREAM_HOOK_KEYS
    ):
        raise HuntError("APK-backed libGameProc export checks are incomplete")
    checks_by_key = {
        str(row.get("hook_key") or ""): row
        for row in export_checks
        if isinstance(row, dict)
    }
    if set(checks_by_key) != set(EXPECTED_BGM_UPSTREAM_HOOK_KEYS):
        raise HuntError("APK-backed libGameProc export check keys are incomplete")
    for key in EXPECTED_BGM_UPSTREAM_HOOK_KEYS:
        row = checks_by_key[key]
        expected_symbol, expected_offset = EXPECTED_SOUND_HOOKS[key]
        if (
            row.get("symbol") != expected_symbol
            or row.get("container_module") != EXPECTED_ARM64_SPLIT_BASENAME
            or row.get("container_path") != host_split_identity["device_apk_path"]
            or str(row.get("actual_derived_elf_offset") or "").lower()
            != expected_offset
            or str(row.get("expected_elf_offset") or "").lower()
            != expected_offset
            or row.get("offset_matches") is not True
            or row.get("same_apk_container") is not True
        ):
            raise HuntError(f"APK-backed libGameProc export check failed for {key}")
    for key in EXPECTED_BGM_UPSTREAM_HOOK_KEYS:
        status = hook_status[key]
        if (
            status.get("module") != EXPECTED_ARM64_SPLIT_BASENAME
            or status.get("module_path") != host_split_identity["device_apk_path"]
            or status.get("derived_elf_base")
            != game_proc_identity.get("derived_elf_base")
            or status.get("offset_basis")
            != "known_export_minus_derived_game_proc_elf_base"
            or status.get("module_identity_matches_static_reference") is not True
        ):
            raise HuntError(f"BGM upstream hook {key} is not bound to verified split/ELF")

    accessor_status = sound_logic.get("bgm_upstream_sdgm_accessor_status")
    if not isinstance(accessor_status, dict):
        raise HuntError("BGM upstream SdGmData accessor status is missing")
    if (
        accessor_status.get("status") != "ready"
        or accessor_status.get("symbol") != "fnGetAddrSdGmData"
        or accessor_status.get("module") != EXPECTED_ARM64_SPLIT_BASENAME
        or accessor_status.get("module_path") != host_split_identity["device_apk_path"]
        or accessor_status.get("derived_elf_base")
        != game_proc_identity.get("derived_elf_base")
        or str(accessor_status.get("actual_module_offset") or "").lower()
        != "0x424d474"
        or str(accessor_status.get("expected_module_offset") or "").lower()
        != "0x424d474"
        or accessor_status.get("module_offset_matches_static_reference") is not True
        or accessor_status.get("read_only_accessor") is not True
    ):
        raise HuntError("BGM upstream SdGmData accessor is not version-checked read-only")

    if sound_logic.get("bgm_upstream_field_schema") != EXPECTED_BGM_UPSTREAM_FIELD_SCHEMA:
        raise HuntError("BGM upstream field schema does not match the named static contract")
    window_rpc = sound_logic.get("bgm_upstream_window_rpc")
    if window_rpc != {
        "schema": "magireco-target-bgm-upstream-window-v1",
        "begin_export": "beginbgmupstreamattempt",
        "end_export": "endbgmupstreamattempt",
        "status_export": "bgmupstreamstatus",
        "read_only_observer": True,
    }:
        raise HuntError("BGM upstream attempt-window RPC contract is incomplete")
    if sound_logic.get("outer_bgm_snapshot_accessors_ready") is not True:
        raise HuntError("all active-sound snapshot accessors must be ready")
    accessor_status = sound_logic.get("outer_bgm_snapshot_accessor_status")
    if not isinstance(accessor_status, dict) or len(accessor_status) != 8:
        raise HuntError("active-sound accessor status must contain exactly eight accessors")
    for name, status in accessor_status.items():
        if not isinstance(status, dict):
            raise HuntError(f"active-sound accessor {name} status is not an object")
        if status.get("status") != "ready" or status.get(
            "module_offset_matches_static_reference"
        ) is not True:
            raise HuntError(f"active-sound accessor {name} is not version-checked ready")

    calc_status = sound_logic.get("outer_bgm_snapshot_calc_entry_status")
    if not isinstance(calc_status, dict):
        raise HuntError("CSLMng::Calc snapshot entry status is missing")
    if calc_status.get("status") != "ready" or calc_status.get(
        "module_offset_matches_static_reference"
    ) is not True:
        raise HuntError("CSLMng::Calc snapshot entry is not version-checked ready")

    capture_scope = sound_logic.get("capture_scope")
    if capture_scope != EXPECTED_SOUND_CAPTURE_SCOPE:
        raise HuntError(
            "sound-logic capture scope does not provide the exact synchronous metadata contract"
        )

    gate_status = sound_logic.get("sound_pack_pre_gate_status")
    if not isinstance(gate_status, dict):
        raise HuntError("sound-pack pre-gate status is missing")
    required_gate_fields = {
        "status": "ready",
        "module_offset_matches_static_reference": True,
        "gate_table_entry_count": 222,
        "gate_table_strictly_increasing_unique": True,
        "read_only_observer": True,
        "repeated_unchanged_volume_control_calls_suppressed": True,
    }
    for key, expected in required_gate_fields.items():
        if gate_status.get(key) != expected:
            raise HuntError(f"sound-pack pre-gate contract mismatch for {key}")
    key_checks = gate_status.get("gate_table_key_checks")
    if not isinstance(key_checks, list):
        raise HuntError("sound-pack gate key checks are missing")
    observed: dict[int, int] = {}
    for row in key_checks:
        if not isinstance(row, dict) or row.get("matches") is not True:
            raise HuntError("sound-pack gate key check is invalid")
        try:
            index = int(row["index"])
            expected = int(row["expected"])
            actual = int(row["actual"])
        except (KeyError, TypeError, ValueError) as error:
            raise HuntError("sound-pack gate key check has invalid numeric fields") from error
        if index in observed or expected != actual:
            raise HuntError("sound-pack gate key checks contain a duplicate or mismatch")
        observed[index] = actual
    if observed != SOUND_PACK_REFERENCE_KEYS:
        raise HuntError("sound-pack gate key checks do not have full static extractor parity")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_coordinate(value: str) -> tuple[int, int]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("coordinate must be X,Y")
    try:
        x, y = (int(part, 0) for part in parts)
    except ValueError as error:
        raise argparse.ArgumentTypeError("coordinate must contain integers") from error
    if x < 0 or y < 0:
        raise argparse.ArgumentTypeError("coordinate must be non-negative")
    return x, y


def parse_args() -> argparse.Namespace:
    probe_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--device", default="emulator-5554")
    parser.add_argument("--host", default="127.0.0.1:27043")
    parser.add_argument(
        "--expected-pid",
        type=int,
        default=0,
        help="fail closed unless the current game PID matches; 0 accepts the inspected PID",
    )
    parser.add_argument("--package", default=PACKAGE)
    parser.add_argument("--activity", default=ACTIVITY)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="allow verified ADB taps; without this flag the tool is read-only",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=0,
        help="0 means continue until a target batch; ignored in dry-run mode",
    )
    parser.add_argument("--dry-run-seconds", type=float, default=3.0)
    parser.add_argument("--probe-ready-timeout", type=float, default=15.0)
    # Three simultaneous observers can stretch the game's real 2/2 START
    # phase well past 30 host seconds; the logical snapshot, not elapsed time,
    # still decides when a stop is allowed.
    parser.add_argument("--ready-state-timeout", type=float, default=120.0)
    parser.add_argument(
        "--spin-settle-steps",
        type=int,
        default=17,
        help=(
            "minimum body state steps after entering 3/3 before the first stop; "
            "the stop progress mask remains authoritative"
        ),
    )
    parser.add_argument(
        "--inter-stop-settle-steps",
        type=int,
        default=1,
        help="minimum additional body state steps after each accepted stop",
    )
    # Three simultaneous observers can stretch one logical reel/update frame
    # to several host seconds.  This timeout sends no additional input; it only
    # waits for updateReel/setStopAngle progress after the single gesture.
    parser.add_argument("--stop-progress-timeout", type=float, default=120.0)
    parser.add_argument(
        "--press-duration-ms",
        type=int,
        default=500,
        help=(
            "single stationary swipe duration for every control; this produces "
            "one bounded press that spans multiple render frames under probes"
        ),
    )
    parser.add_argument("--input-confirm-timeout", type=float, default=0.8)
    parser.add_argument("--input-overall-timeout", type=float, default=180.0)
    parser.add_argument("--input-retry-wait", type=float, default=0.12)
    parser.add_argument("--queue-catch-up-timeout", type=float, default=5.0)
    parser.add_argument("--round-timeout", type=float, default=90.0)
    parser.add_argument("--post-hit-seconds", type=float, default=60.0)
    parser.add_argument("--foreground-check-interval", type=float, default=1.0)
    parser.add_argument("--max-buffer-mib", type=float, default=128.0)
    parser.add_argument("--max-bet", type=parse_coordinate, default=(250, 2150))
    parser.add_argument("--lever", type=parse_coordinate, default=(330, 2720))
    parser.add_argument("--left-stop", type=parse_coordinate, default=(820, 2680))
    parser.add_argument("--middle-stop", type=parse_coordinate, default=(1080, 2680))
    parser.add_argument("--right-stop", type=parse_coordinate, default=(1330, 2680))
    parser.add_argument(
        "--slot-gate-script",
        type=Path,
        default=probe_dir / PROBE_FILES["slot_gate"],
    )
    parser.add_argument(
        "--dispatch-script",
        type=Path,
        default=probe_dir / PROBE_FILES["dispatch"],
    )
    parser.add_argument(
        "--sound-logic-script",
        type=Path,
        default=probe_dir / PROBE_FILES["sound_logic"],
    )
    return parser.parse_args()


def run_command(argv: list[str], *, timeout: float = 20.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=timeout,
    )


def adb_command(args: argparse.Namespace, *parts: str) -> list[str]:
    return [args.adb, "-s", args.device, *parts]


def parse_bound_game_proc_local_header(raw: bytes) -> dict[str, Any]:
    """Parse only the fixed local ZIP header bound by the exact split digest."""

    expected_length = (
        EXPECTED_GAME_PROC_APK_DATA_OFFSET
        - EXPECTED_GAME_PROC_APK_LOCAL_HEADER_OFFSET
    )
    if len(raw) != expected_length or len(raw) < 30:
        raise HuntError(
            f"bound GameProc local header span mismatch: {len(raw)} != {expected_length}"
        )
    (
        signature,
        version_needed,
        flag_bits,
        compression_method,
        mod_time,
        mod_date,
        crc32,
        compressed_size,
        uncompressed_size,
        filename_length,
        extra_length,
    ) = struct.unpack("<IHHHHHIIIHH", raw[:30])
    filename_end = 30 + filename_length
    extra_end = filename_end + extra_length
    try:
        filename = raw[30:filename_end].decode("utf-8")
    except UnicodeDecodeError as error:
        raise HuntError("bound GameProc ZIP filename is not UTF-8") from error
    result = {
        "signature_u32_le": f"0x{signature:08X}",
        "version_needed_u16": version_needed,
        "flag_bits_u16": flag_bits,
        "compression_method_u16": compression_method,
        "mod_time_u16": mod_time,
        "mod_date_u16": mod_date,
        "crc32": f"{crc32:08X}",
        "compressed_size_bytes": compressed_size,
        "uncompressed_size_bytes": uncompressed_size,
        "filename_length": filename_length,
        "extra_length": extra_length,
        "filename": filename,
        "local_header_offset": EXPECTED_GAME_PROC_APK_LOCAL_HEADER_OFFSET,
        "data_offset": EXPECTED_GAME_PROC_APK_LOCAL_HEADER_OFFSET + extra_end,
    }
    if (
        signature != 0x04034B50
        or flag_bits != 0
        or compression_method != EXPECTED_GAME_PROC_APK_COMPRESSION_METHOD
        or result["crc32"] != EXPECTED_GAME_PROC_APK_CRC32
        or compressed_size != EXPECTED_GAME_PROC_SIZE_BYTES
        or uncompressed_size != EXPECTED_GAME_PROC_SIZE_BYTES
        or filename != EXPECTED_GAME_PROC_APK_ENTRY
        or result["data_offset"] != EXPECTED_GAME_PROC_APK_DATA_OFFSET
        or extra_end != len(raw)
    ):
        raise HuntError("installed split GameProc local ZIP entry contract mismatch")
    return result


def validate_installed_arm64_split_identity(payload: Any) -> dict[str, Any]:
    """Fail closed unless outer APK and its live uncompressed GameProc bytes match."""

    if not isinstance(payload, dict):
        raise HuntError("installed ARM64 split identity is not an object")
    required = {
        "schema": "magireco-installed-arm64-split-identity-v1",
        "split_basename": EXPECTED_ARM64_SPLIT_BASENAME,
        "verification_method": (
            "host_sha256_over_adb_exec_out_cat_with_fixed_uncompressed_entry_range"
        ),
        "actual_apk_size_bytes": EXPECTED_ARM64_SPLIT_SIZE_BYTES,
        "expected_apk_size_bytes": EXPECTED_ARM64_SPLIT_SIZE_BYTES,
        "actual_apk_sha256": EXPECTED_ARM64_SPLIT_SHA256,
        "expected_apk_sha256": EXPECTED_ARM64_SPLIT_SHA256,
        "apk_size_matches": True,
        "apk_sha256_matches": True,
        "entry_path": EXPECTED_GAME_PROC_APK_ENTRY,
        "entry_compression_method": EXPECTED_GAME_PROC_APK_COMPRESSION_METHOD,
        "entry_crc32": EXPECTED_GAME_PROC_APK_CRC32,
        "entry_data_offset": EXPECTED_GAME_PROC_APK_DATA_OFFSET,
        "actual_entry_bytes_hashed": EXPECTED_GAME_PROC_SIZE_BYTES,
        "expected_entry_bytes": EXPECTED_GAME_PROC_SIZE_BYTES,
        "actual_entry_sha256": EXPECTED_GAME_PROC_SHA256,
        "expected_entry_sha256": EXPECTED_GAME_PROC_SHA256,
        "entry_sha256_matches": True,
        "entry_elf_header_matches_aarch64": True,
        "outer_digest_binds_local_header_layout": True,
        "read_only_adb_stream": True,
        "gameplay_input_sent": False,
        "device_state_modified": False,
    }
    for key, expected in required.items():
        actual = payload.get(key)
        if isinstance(expected, str) and key.endswith("sha256"):
            actual = str(actual or "").upper()
        if actual != expected:
            raise HuntError(f"installed ARM64 split identity mismatch for {key}")
    path = str(payload.get("device_apk_path") or "")
    if not path.endswith("/" + EXPECTED_ARM64_SPLIT_BASENAME):
        raise HuntError("installed ARM64 split path is not the exact expected split")
    local_header = payload.get("entry_local_header")
    if not isinstance(local_header, dict):
        raise HuntError("installed ARM64 split lacks parsed GameProc local header")
    if (
        local_header.get("signature_u32_le") != "0x04034B50"
        or local_header.get("flag_bits_u16") != 0
        or local_header.get("compression_method_u16")
        != EXPECTED_GAME_PROC_APK_COMPRESSION_METHOD
        or local_header.get("crc32") != EXPECTED_GAME_PROC_APK_CRC32
        or local_header.get("filename") != EXPECTED_GAME_PROC_APK_ENTRY
        or local_header.get("local_header_offset")
        != EXPECTED_GAME_PROC_APK_LOCAL_HEADER_OFFSET
        or local_header.get("data_offset") != EXPECTED_GAME_PROC_APK_DATA_OFFSET
        or local_header.get("compressed_size_bytes") != EXPECTED_GAME_PROC_SIZE_BYTES
        or local_header.get("uncompressed_size_bytes") != EXPECTED_GAME_PROC_SIZE_BYTES
    ):
        raise HuntError("installed ARM64 split parsed GameProc header is inconsistent")
    return copy.deepcopy(payload)


def stream_installed_arm64_split_identity(
    args: argparse.Namespace,
    device_apk_path: str,
) -> dict[str, Any]:
    """Hash the installed split and fixed uncompressed ELF range in one ADB stream."""

    argv = adb_command(args, "exec-out", "cat", device_apk_path)
    process = subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.stdout is None or process.stderr is None:
        process.kill()
        raise HuntError("ADB split stream did not expose stdout/stderr pipes")
    outer_digest = hashlib.sha256()
    inner_digest = hashlib.sha256()
    header_bytes = bytearray()
    inner_prefix = bytearray()
    total_bytes = 0
    inner_bytes = 0
    header_start = EXPECTED_GAME_PROC_APK_LOCAL_HEADER_OFFSET
    header_end = EXPECTED_GAME_PROC_APK_DATA_OFFSET
    inner_start = EXPECTED_GAME_PROC_APK_DATA_OFFSET
    inner_end = inner_start + EXPECTED_GAME_PROC_SIZE_BYTES
    try:
        while True:
            chunk = process.stdout.read(1024 * 1024)
            if not chunk:
                break
            chunk_start = total_bytes
            chunk_end = chunk_start + len(chunk)
            outer_digest.update(chunk)

            overlap_start = max(chunk_start, header_start)
            overlap_end = min(chunk_end, header_end)
            if overlap_start < overlap_end:
                header_bytes.extend(
                    chunk[overlap_start - chunk_start : overlap_end - chunk_start]
                )

            overlap_start = max(chunk_start, inner_start)
            overlap_end = min(chunk_end, inner_end)
            if overlap_start < overlap_end:
                inner_chunk = chunk[
                    overlap_start - chunk_start : overlap_end - chunk_start
                ]
                inner_digest.update(inner_chunk)
                inner_bytes += len(inner_chunk)
                if len(inner_prefix) < 64:
                    inner_prefix.extend(inner_chunk[: 64 - len(inner_prefix)])
            total_bytes = chunk_end
        stderr = process.stderr.read().decode("utf-8", errors="replace")
        return_code = process.wait(timeout=10.0)
    except Exception:
        process.kill()
        process.wait(timeout=5.0)
        raise
    if return_code != 0:
        raise HuntError(
            f"ADB installed split stream failed: rc={return_code} stderr={stderr!r}"
        )

    local_header = parse_bound_game_proc_local_header(bytes(header_bytes))
    prefix = bytes(inner_prefix)
    elf_header_matches = (
        len(prefix) >= 20
        and prefix[:4] == b"\x7fELF"
        and prefix[4] == 2
        and prefix[5] == 1
        and int.from_bytes(prefix[18:20], "little") == 183
    )
    payload = {
        "schema": "magireco-installed-arm64-split-identity-v1",
        "device": args.device,
        "package": args.package,
        "device_apk_path": device_apk_path,
        "split_basename": device_apk_path.rsplit("/", 1)[-1],
        "verification_method": (
            "host_sha256_over_adb_exec_out_cat_with_fixed_uncompressed_entry_range"
        ),
        "actual_apk_size_bytes": total_bytes,
        "expected_apk_size_bytes": EXPECTED_ARM64_SPLIT_SIZE_BYTES,
        "actual_apk_sha256": outer_digest.hexdigest().upper(),
        "expected_apk_sha256": EXPECTED_ARM64_SPLIT_SHA256,
        "apk_size_matches": total_bytes == EXPECTED_ARM64_SPLIT_SIZE_BYTES,
        "apk_sha256_matches": outer_digest.hexdigest().upper()
        == EXPECTED_ARM64_SPLIT_SHA256,
        "entry_path": EXPECTED_GAME_PROC_APK_ENTRY,
        "entry_compression_method": EXPECTED_GAME_PROC_APK_COMPRESSION_METHOD,
        "entry_crc32": EXPECTED_GAME_PROC_APK_CRC32,
        "entry_local_header": local_header,
        "entry_data_offset": EXPECTED_GAME_PROC_APK_DATA_OFFSET,
        "actual_entry_bytes_hashed": inner_bytes,
        "expected_entry_bytes": EXPECTED_GAME_PROC_SIZE_BYTES,
        "actual_entry_sha256": inner_digest.hexdigest().upper(),
        "expected_entry_sha256": EXPECTED_GAME_PROC_SHA256,
        "entry_sha256_matches": inner_digest.hexdigest().upper()
        == EXPECTED_GAME_PROC_SHA256,
        "entry_elf_prefix_hex": prefix.hex().upper(),
        "entry_elf_header_matches_aarch64": elf_header_matches,
        "outer_digest_binds_local_header_layout": True,
        "read_only_adb_stream": True,
        "gameplay_input_sent": False,
        "device_state_modified": False,
    }
    return validate_installed_arm64_split_identity(payload)


def inspect_installed_arm64_split(args: argparse.Namespace) -> dict[str, Any]:
    paths = run_command(adb_command(args, "shell", "pm", "path", args.package))
    if paths.returncode != 0:
        raise HuntError(f"pm path failed: {paths.stderr!r}")
    candidates = []
    for raw_line in paths.stdout.splitlines():
        line = raw_line.strip()
        if line.startswith("package:"):
            line = line[len("package:") :]
        if line.endswith("/" + EXPECTED_ARM64_SPLIT_BASENAME):
            candidates.append(line)
    if len(candidates) != 1:
        raise HuntError(
            f"expected one installed {EXPECTED_ARM64_SPLIT_BASENAME}, observed {candidates!r}"
        )
    return stream_installed_arm64_split_identity(args, candidates[0])


def normalized_component(package: str, activity: str) -> str:
    if "/" in activity:
        return activity
    return f"{package}/{activity}"


def inspect_foreground(args: argparse.Namespace) -> dict[str, Any]:
    state = run_command(adb_command(args, "get-state"))
    if state.returncode != 0 or state.stdout.strip() != "device":
        raise HuntError(
            f"ADB device is not online: rc={state.returncode} stdout={state.stdout!r} "
            f"stderr={state.stderr!r}"
        )
    pidof = run_command(adb_command(args, "shell", "pidof", args.package))
    pids = [token for token in pidof.stdout.split() if token.isdigit()]
    if pidof.returncode != 0 or len(pids) != 1:
        raise HuntError(f"expected one {args.package} PID, observed {pids!r}")
    activities = run_command(
        adb_command(args, "shell", "dumpsys", "activity", "activities"),
        timeout=30.0,
    )
    if activities.returncode != 0:
        raise HuntError(f"dumpsys activity failed: {activities.stderr!r}")
    focus_lines = [
        line.strip()
        for line in activities.stdout.splitlines()
        if "mResumedActivity" in line or "topResumedActivity" in line
    ]
    component = normalized_component(args.package, args.activity)
    focused = any(component in line for line in focus_lines)
    if not focused:
        raise HuntError(
            f"game activity is not foreground; expected {component!r}, observed {focus_lines!r}"
        )
    return {
        "device": args.device,
        "package": args.package,
        "activity_component": component,
        "pid": int(pids[0]),
        "focus_lines": focus_lines,
    }


def require_same_runtime(args: argparse.Namespace, expected_pid: int) -> dict[str, Any]:
    current = inspect_foreground(args)
    if current["pid"] != expected_pid:
        raise HuntError(
            f"game PID changed during the single-session capture: "
            f"{expected_pid} -> {current['pid']}"
        )
    return current


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def probe_source_provenance(script_paths: dict[str, Path]) -> dict[str, dict[str, Any]]:
    """Hash the exact observer sources loaded into the shared Gadget session."""

    result: dict[str, dict[str, Any]] = {}
    for name, raw_path in script_paths.items():
        path = raw_path.resolve()
        result[name] = {
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    return result


def payload_for(record: dict[str, Any]) -> dict[str, Any]:
    message = record.get("message")
    if isinstance(message, dict) and isinstance(message.get("payload"), dict):
        return message["payload"]
    return {}


class LiveCapture:
    """Own one Gadget session and route three existing probes in memory."""

    def __init__(
        self,
        *,
        host: str,
        expected_pid: int,
        script_paths: dict[str, Path],
        max_buffer_bytes: int,
    ) -> None:
        self.host = host
        self.expected_pid = expected_pid
        self.script_paths = {name: path.resolve() for name, path in script_paths.items()}
        self.max_buffer_bytes = max_buffer_bytes
        self.events: queue.Queue[tuple[str, dict[str, Any], str]] = queue.Queue()
        self.messages_enqueued = 0
        self.messages_processed = 0
        self.device: Any = None
        self.session: Any = None
        self.scripts: dict[str, Any] = {}
        self.loaded_probe_source_bytes: dict[str, bytes] = {}
        self.loaded_probe_sources: dict[str, dict[str, Any]] = {}
        self.detached_reason = ""
        self.ready: set[str] = set()
        self.ready_payloads: dict[str, dict[str, Any]] = {}
        self.probe_errors: list[dict[str, Any]] = []
        self.attempt_probe_errors: list[dict[str, Any]] = []
        self.sequence = 0
        self.latest_gate_state: dict[str, Any] | None = None
        self.latest_gate_event_count = 0
        self.latest_sdgm_state: dict[str, Any] = {}
        self.input_events: list[dict[str, Any]] = []
        self.reel_stop_events: list[dict[str, Any]] = []
        self.session_records: dict[str, list[str]] = {name: [] for name in script_paths}
        self.capture_session_headers = True
        self.attempt_active = False
        self.attempt_records: dict[str, list[str]] = {name: [] for name in script_paths}
        self.attempt_bytes = 0
        self.buffer_overflow = False
        self.dispatch_tracker = DispatchBatchTracker(strict=True)
        self.complete_candidates: list[dict[str, Any]] = []
        self.lever_eligible_after_sequence: int | None = None
        self.lever_eligible_after_host_unix_ms: int | None = None
        self.selection_candidate: dict[str, Any] | None = None
        self.observed_event_codes: list[dict[str, Any]] = []
        self.sound_pack_pre_gate_events: list[dict[str, Any]] = []
        self.sound_pack_pre_gate_last_state: dict[
            tuple[Any, ...], tuple[tuple[Any, ...], int]
        ] = {}
        self.max_sound_request_trace_events = MAX_SOUND_REQUEST_TRACE_EVENTS
        self.sound_request_trace_events: list[dict[str, Any]] = []
        self.sound_request_trace_event_count_by_kind: dict[str, int] = {}
        self.sound_request_trace_dropped_count = 0
        self.target_batch: dict[str, Any] | None = None
        self.outer_bgm_snapshots: list[dict[str, Any]] = []
        self.bgm_upstream_window: dict[str, Any] | None = None
        self.bgm_upstream_attempt_serial = 0
        self.installed_split_identity: dict[str, Any] | None = None

    def _callback(self, probe_name: str) -> Callable[[dict[str, Any], bytes | None], None]:
        def on_message(message: dict[str, Any], data: bytes | None) -> None:
            self.messages_enqueued += 1
            record: dict[str, Any] = {
                "host_unix_ms": int(time.time() * 1000),
                "callback_message_index": self.messages_enqueued,
                "probe": probe_name,
                "message": message,
            }
            if data:
                record["data_base64"] = base64.b64encode(data).decode("ascii")
            line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
            self.events.put((probe_name, record, line))

        return on_message

    def attach(self) -> None:
        manager = frida.get_device_manager()
        self.device = manager.add_remote_device(self.host)
        processes = self.device.enumerate_processes()
        targets = [process for process in processes if int(process.pid) == self.expected_pid]
        if len(targets) != 1:
            visible = [(int(process.pid), process.name) for process in processes]
            raise HuntError(
                f"Gadget did not expose expected PID {self.expected_pid}; visible={visible!r}"
            )
        self.session = self.device.attach(self.expected_pid)
        try:
            self.session.on("detached", self._on_detached)
        except Exception:
            pass
        for name, path in self.script_paths.items():
            source_bytes = path.read_bytes()
            try:
                source = source_bytes.decode("utf-8")
            except UnicodeDecodeError as error:
                raise HuntError(f"probe {name} source is not valid UTF-8: {path}") from error
            self.loaded_probe_source_bytes[name] = source_bytes
            self.loaded_probe_sources[name] = {
                "path_at_load": str(path),
                "bytes": len(source_bytes),
                "sha256": hashlib.sha256(source_bytes).hexdigest().upper(),
                "provenance_basis": "exact_utf8_bytes_passed_to_create_script",
            }
            script = self.session.create_script(source)
            script.on("message", self._callback(name))
            self.scripts[name] = script
            script.load()

    def _on_detached(self, reason: str, _crash: Any = None) -> None:
        self.detached_reason = str(reason)

    def close(self) -> None:
        for script in reversed(list(self.scripts.values())):
            try:
                script.unload()
            except Exception:
                pass
        if self.session is not None:
            try:
                self.session.detach()
            except Exception:
                pass

    def refresh_gate_snapshot(self) -> dict[str, Any] | None:
        """Read the bounded logical slot state without waiting for an event.

        The gate's change-only messages prove accepted inputs, but a passive
        transition can occur between calls that emit a message.  Its RPC reads
        the same named fields from the last observed CSlotBody pointer; it does
        not capture media or arbitrary memory.
        """

        script = self.scripts.get("slot_gate")
        if script is None:
            return self.latest_gate_state
        try:
            snapshot = script.exports_sync.snapshot()
        except Exception as error:
            raise HuntError(f"slot-gate logical snapshot failed: {error}") from error
        if not isinstance(snapshot, dict):
            raise HuntError(f"slot-gate logical snapshot is not an object: {snapshot!r}")
        if snapshot.get("installed") is False:
            raise HuntError("slot-gate logical snapshot reports hook not installed")
        state = snapshot.get("state")
        if isinstance(state, dict) and state.get("slot_body_pointer") not in {None, "0x0"}:
            self.latest_gate_state = state
        return self.latest_gate_state

    def record_outer_bgm_snapshot(self, label: str) -> dict[str, Any]:
        """Record one bounded CSL active-sound RPC result.

        The probe deliberately labels channel-zero rows as candidates only;
        this method preserves that native metadata and never upgrades it to a
        semantic BGM classification.  RPC failure is retained as evidence and
        does not hide an otherwise valid natural-spin attempt.
        """

        host_unix_ms = int(time.time() * 1000)
        waterline_before = {
            "sequence": self.sequence,
            "messages_enqueued": self.messages_enqueued,
            "messages_processed": self.messages_processed,
            "sound_request_trace_event_count": len(self.sound_request_trace_events),
        }
        script = self.scripts.get("sound_logic")
        if script is None:
            snapshot: dict[str, Any] = {
                "schema": "magireco-csl-active-sound-snapshot-v1",
                "label": label,
                "captured_host_unix_ms": host_unix_ms,
                "available": False,
                "error": "sound_logic probe is not loaded",
            }
        else:
            try:
                raw = script.exports_sync.outerbgmsnapshot(label)
                if not isinstance(raw, dict):
                    raise TypeError(f"outer BGM snapshot is not an object: {raw!r}")
                snapshot = copy.deepcopy(raw)
                snapshot.setdefault("label", label)
                snapshot["captured_host_unix_ms"] = host_unix_ms
            except Exception as error:
                snapshot = {
                    "schema": "magireco-csl-active-sound-snapshot-v1",
                    "label": label,
                    "captured_host_unix_ms": host_unix_ms,
                    "available": False,
                    "error": f"outer BGM snapshot RPC failed: {error}",
                }
        drained_callback_count = 0
        while drained_callback_count < 10000:
            if self.pump(0.0) is None:
                break
            drained_callback_count += 1
        snapshot["capture_waterline_before_rpc"] = waterline_before
        snapshot["capture_waterline_after_rpc"] = {
            "sequence": self.sequence,
            "messages_enqueued": self.messages_enqueued,
            "messages_processed": self.messages_processed,
            "sound_request_trace_event_count": len(self.sound_request_trace_events),
            "drained_callback_count": drained_callback_count,
            "drain_limit_reached": drained_callback_count == 10000,
        }
        self.outer_bgm_snapshots.append(snapshot)
        return snapshot

    def begin_attempt(self) -> None:
        self.capture_session_headers = False
        self.attempt_active = True
        self.attempt_records = {name: [] for name in self.script_paths}
        self.attempt_bytes = 0
        self.buffer_overflow = False
        self.dispatch_tracker = DispatchBatchTracker(strict=True)
        self.complete_candidates = []
        self.lever_eligible_after_sequence = None
        self.lever_eligible_after_host_unix_ms = None
        self.selection_candidate = None
        self.observed_event_codes = []
        self.sound_pack_pre_gate_events = []
        self.sound_pack_pre_gate_last_state = {}
        self.sound_request_trace_events = []
        self.sound_request_trace_event_count_by_kind = {}
        self.sound_request_trace_dropped_count = 0
        self.attempt_probe_errors = []
        self.target_batch = None
        self.input_events = []
        self.reel_stop_events = []
        self.outer_bgm_snapshots = []
        self.bgm_upstream_window = None
        sound_logic = self.scripts.get("sound_logic")
        if sound_logic is not None:
            self.bgm_upstream_attempt_serial += 1
            try:
                raw_window = sound_logic.exports_sync.beginbgmupstreamattempt(
                    f"hunt_attempt_{self.bgm_upstream_attempt_serial:06d}"
                )
            except Exception as error:
                raise HuntError(f"BGM upstream attempt window failed to begin: {error}") from error
            self.bgm_upstream_window = validate_bgm_upstream_window_contract(
                raw_window,
                expected_active=True,
            )
            if (
                int(self.bgm_upstream_window["emitted_event_count"]) != 0
                or int(self.bgm_upstream_window["dropped_event_count"]) != 0
            ):
                raise HuntError("BGM upstream attempt window did not begin empty")

    def finish_bgm_upstream_window(self) -> dict[str, Any] | None:
        """Close the RPC window while retaining its final counters for the journal."""

        sound_logic = self.scripts.get("sound_logic")
        if (
            sound_logic is not None
            and self.bgm_upstream_window is not None
            and self.bgm_upstream_window.get("active") is True
        ):
            expected_epoch = int(self.bgm_upstream_window["epoch"])
            try:
                raw_window = sound_logic.exports_sync.endbgmupstreamattempt()
            except Exception as error:
                raise HuntError(f"BGM upstream attempt window failed to end: {error}") from error
            self.bgm_upstream_window = copy.deepcopy(raw_window)
            return validate_bgm_upstream_window_contract(
                raw_window,
                expected_active=False,
                expected_epoch=expected_epoch,
            )
        return copy.deepcopy(self.bgm_upstream_window)

    def end_attempt(self) -> None:
        try:
            self.finish_bgm_upstream_window()
        finally:
            self.attempt_active = False
            self.attempt_records = {name: [] for name in self.script_paths}
            self.attempt_bytes = 0
            self.input_events = []
            self.reel_stop_events = []
            self.sound_request_trace_events = []
            self.sound_request_trace_event_count_by_kind = {}
            self.sound_request_trace_dropped_count = 0
            self.attempt_probe_errors = []
            self.outer_bgm_snapshots = []
            self.bgm_upstream_window = None

    def mark_lever_issued(self, sequence: int, host_unix_ms: int) -> None:
        self.lever_eligible_after_sequence = sequence
        self.lever_eligible_after_host_unix_ms = host_unix_ms
        self._refresh_target()

    def _refresh_target(self) -> None:
        if (
            self.target_batch is not None
            or self.lever_eligible_after_sequence is None
            or self.lever_eligible_after_host_unix_ms is None
        ):
            return
        for candidate in self.complete_candidates:
            candidate_sequence = int(candidate.get("completion_sequence", 0))
            candidate_host_unix_ms = int(candidate.get("completion_host_unix_ms", 0))
            if candidate_sequence <= self.lever_eligible_after_sequence:
                continue
            if candidate_host_unix_ms <= self.lever_eligible_after_host_unix_ms:
                continue
            target = target_for_batch(candidate)
            if target is None:
                continue
            self.selection_candidate = {
                **candidate,
                "expected_target": target,
            }
            expected_code = target["event_code_hex"].lower()
            for event_row in self.observed_event_codes:
                # The exact event code must be emitted after this completed
                # ID19+ID24 selection batch, not merely after the lever.  A
                # matching code from an earlier dispatch in the same attempt
                # is unrelated evidence and must fail closed.
                if int(event_row.get("sequence", 0)) <= candidate_sequence:
                    continue
                if (
                    int(event_row.get("host_unix_ms", 0))
                    <= candidate_host_unix_ms
                ):
                    continue
                if str(event_row.get("event_code_hex", "")).lower() == expected_code:
                    self.target_batch = {
                        **self.selection_candidate,
                        "resolved_event": target,
                        "event_code_observation": event_row,
                    }
                    return

    def _retain_line(self, probe_name: str, line: str) -> None:
        if self.attempt_active:
            encoded_size = len(line.encode("utf-8")) + 1
            if self.max_buffer_bytes > 0 and self.attempt_bytes + encoded_size > self.max_buffer_bytes:
                self.buffer_overflow = True
                return
            self.attempt_records[probe_name].append(line)
            self.attempt_bytes += encoded_size
        elif self.capture_session_headers:
            self.session_records[probe_name].append(line)

    def pump(self, timeout: float) -> dict[str, Any] | None:
        if self.detached_reason:
            raise HuntError(f"Gadget session detached: {self.detached_reason}")
        try:
            probe_name, record, line = self.events.get(timeout=max(timeout, 0.0))
        except queue.Empty:
            return None
        self.sequence += 1
        self.messages_processed += 1
        self._retain_line(probe_name, line)
        message = record.get("message")
        if isinstance(message, dict) and message.get("type") == "error":
            error_row = {
                "sequence": self.sequence,
                "host_unix_ms": record.get("host_unix_ms"),
                "probe": probe_name,
                "description": str(message.get("description") or "")[:4096],
                "stack": str(message.get("stack") or "")[:16384],
                "file_name": str(message.get("fileName") or "")[:1024],
                "line_number": message.get("lineNumber"),
                "column_number": message.get("columnNumber"),
            }
            if len(self.probe_errors) < 64:
                self.probe_errors.append(copy.deepcopy(error_row))
            if self.attempt_active and len(self.attempt_probe_errors) < 64:
                self.attempt_probe_errors.append(copy.deepcopy(error_row))
            raise HuntError(
                f"probe {probe_name} emitted a Frida script error: "
                f"{error_row['description'] or error_row['stack'][:512]}"
            )
        payload = payload_for(record)
        kind = str(payload.get("kind") or "")
        if kind == READY_KINDS.get(probe_name):
            if payload.get("installed") is False:
                raise HuntError(f"probe {probe_name} reported not installed: {payload!r}")
            self.ready.add(probe_name)
            self.ready_payloads[probe_name] = copy.deepcopy(payload)

        if (
            self.attempt_active
            and probe_name == "sound_logic"
            and kind in SOUND_REQUEST_TRACE_KINDS
        ):
            self.sound_request_trace_event_count_by_kind[kind] = (
                self.sound_request_trace_event_count_by_kind.get(kind, 0) + 1
            )
            if len(self.sound_request_trace_events) < self.max_sound_request_trace_events:
                self.sound_request_trace_events.append(
                    compact_sound_request_event(
                        payload,
                        sequence=self.sequence,
                        host_unix_ms=record.get("host_unix_ms"),
                    )
                )
            else:
                self.sound_request_trace_dropped_count += 1
            if kind == "sound_logic_bgm_upstream_trace_overflow":
                raise HuntError("BGM upstream trace overflowed its bounded attempt window")

        if probe_name == "slot_gate" and kind == "slot_gate_state":
            state_after = payload.get("state_after")
            if isinstance(state_after, dict):
                self.latest_gate_state = state_after
            try:
                self.latest_gate_event_count = max(
                    self.latest_gate_event_count,
                    int(payload.get("event_count") or 0),
                )
            except (TypeError, ValueError):
                pass
            if payload.get("input_nonzero"):
                self.input_events.append(
                    {
                        "sequence": self.sequence,
                        "host_unix_ms": record.get("host_unix_ms"),
                        "source_unix_ms": payload.get("unix_ms"),
                        "payload": payload,
                    }
                )

        if probe_name == "slot_gate" and kind == "reel_stop_angle_enter":
            self.reel_stop_events.append(
                {
                    "sequence": self.sequence,
                    "host_unix_ms": record.get("host_unix_ms"),
                    "source_unix_ms": payload.get("unix_ms"),
                    "axis_i32": payload.get("axis_i32"),
                    "angle_i32": payload.get("angle_i32"),
                    "slot_body_pointer": payload.get("slot_body_pointer"),
                }
            )

        if probe_name == "dispatch":
            sdgm_fields = {
                key: value
                for key, value in payload.items()
                if key.startswith("sdgm_")
            }
            if sdgm_fields:
                self.latest_sdgm_state.update(sdgm_fields)
                self.latest_sdgm_state.update(
                    {
                        "observed_sequence": self.sequence,
                        "observed_host_unix_ms": record.get("host_unix_ms"),
                        "observed_kind": kind,
                    }
                )
            if kind == "id401_get_cmd_buf_leave":
                self.dispatch_tracker.register_get_cmd_buf(
                    payload,
                    line=self.sequence,
                    rel_time=None,
                )
            _row, complete = self.dispatch_tracker.observe_access(
                payload,
                line=self.sequence,
                rel_time=None,
                source_kind=kind,
            )
            if complete is not None:
                complete = dict(complete)
                complete["completion_sequence"] = self.sequence
                complete["completion_host_unix_ms"] = record.get("host_unix_ms")
                complete["completion_source_unix_ms"] = payload.get("unix_ms")
                self.complete_candidates.append(complete)
                self._refresh_target()
            if kind in {"direction_scene_request", "ctrl_snd_req_event_code"}:
                event_code = str(payload.get("event_code_hex") or "").lower()
                if event_code:
                    self.observed_event_codes.append(
                        {
                            "sequence": self.sequence,
                            "host_unix_ms": record.get("host_unix_ms"),
                            "source_unix_ms": payload.get("unix_ms"),
                            "kind": kind,
                            "event_code_hex": event_code,
                            "return_symbol": payload.get("return_symbol", ""),
                        }
                    )
                    self._refresh_target()
        if (
            probe_name == "sound_logic"
            and kind == "sound_logic_sound_pack_pre_gate_volume"
        ):
            emission_reason = payload.get("emission_reason")
            caller_offset = payload.get("return_module_offset")
            volume_control_call = (
                caller_offset == "0x425f918"
                and emission_reason
                in {
                    "first_observed_volume_control_state",
                    "volume_control_state_changed",
                }
            )
            state_key = (
                payload.get("sound_resource_id_i32"),
                payload.get("volume_index_i32"),
                payload.get("return_module_offset"),
            )
            signature = (
                payload.get("sound_pack_active_u32"),
                payload.get("volume_class_u8"),
                payload.get("class_volume_u16"),
                payload.get("indexed_volume_u16"),
                payload.get("master_volume_u16"),
                payload.get("pre_gate_stage_volume_i32"),
                payload.get("authorized_final_volume_i32"),
                payload.get("current_gate_will_zero"),
            )
            previous = (
                self.sound_pack_pre_gate_last_state.get(state_key)
                if volume_control_call
                else None
            )
            if previous is not None and previous[0] == signature:
                aggregate = self.sound_pack_pre_gate_events[previous[1]]
                aggregate["observation_count"] += 1
                aggregate["last_sequence"] = self.sequence
                aggregate["last_host_unix_ms"] = record.get("host_unix_ms")
                aggregate["last_source_unix_ms"] = payload.get("unix_ms")
            else:
                aggregate = {
                    "sequence": self.sequence,
                    "first_sequence": self.sequence,
                    "last_sequence": self.sequence,
                    "host_unix_ms": record.get("host_unix_ms"),
                    "first_host_unix_ms": record.get("host_unix_ms"),
                    "last_host_unix_ms": record.get("host_unix_ms"),
                    "source_unix_ms": payload.get("unix_ms"),
                    "first_source_unix_ms": payload.get("unix_ms"),
                    "last_source_unix_ms": payload.get("unix_ms"),
                    "observation_count": 1,
                    "sound_resource_id_i32": payload.get("sound_resource_id_i32"),
                    "volume_index_i32": payload.get("volume_index_i32"),
                    "sound_pack_active_u32": payload.get("sound_pack_active_u32"),
                    "volume_class_u8": payload.get("volume_class_u8"),
                    "class_volume_u16": payload.get("class_volume_u16"),
                    "indexed_volume_u16": payload.get("indexed_volume_u16"),
                    "master_volume_u16": payload.get("master_volume_u16"),
                    "pre_gate_stage_volume_i32": payload.get(
                        "pre_gate_stage_volume_i32"
                    ),
                    "authorized_final_volume_i32": payload.get(
                        "authorized_final_volume_i32"
                    ),
                    "current_gate_will_zero": payload.get("current_gate_will_zero"),
                    "reconstruction_complete": payload.get("reconstruction_complete"),
                    "emission_reason": emission_reason,
                    "return_module_offset": payload.get("return_module_offset"),
                    "return_symbol": payload.get("return_symbol", ""),
                }
                self.sound_pack_pre_gate_events.append(aggregate)
                if volume_control_call:
                    self.sound_pack_pre_gate_last_state[state_key] = (
                        signature,
                        len(self.sound_pack_pre_gate_events) - 1,
                    )
        return {"probe": probe_name, "record": record, "payload": payload, "kind": kind}

    def pump_for(self, seconds: float) -> None:
        deadline = time.monotonic() + max(seconds, 0.0)
        while time.monotonic() < deadline:
            self.pump(min(0.1, max(deadline - time.monotonic(), 0.0)))

    def wait_until(self, predicate: Callable[[], bool], timeout: float, description: str) -> None:
        deadline = time.monotonic() + max(timeout, 0.0)
        while not predicate():
            if time.monotonic() >= deadline:
                raise HuntError(f"timed out waiting for {description}")
            self.pump(min(0.1, max(deadline - time.monotonic(), 0.0)))


def state_value(capture: LiveCapture, key: str) -> Any:
    return (capture.latest_gate_state or {}).get(key)


def is_idle_state(capture: LiveCapture) -> bool:
    return (
        state_value(capture, "body_state_i32_at_0x00") == 1
        and state_value(capture, "body_mode_i32_at_0x04") == 1
    )


def is_bettable_state(capture: LiveCapture) -> bool:
    state = state_value(capture, "body_state_i32_at_0x00")
    mode = state_value(capture, "body_mode_i32_at_0x04")
    return (state, mode) in {(0, 0), (1, 1)}


def is_input_released(capture: LiveCapture) -> bool:
    return (
        state_value(capture, "body_input_mask_i32_at_0x408") == 0
        and state_value(capture, "body_button_state_i32_at_0x74") == 0
    )


def state_age(capture: LiveCapture) -> int | None:
    try:
        return int(state_value(capture, "body_initialized_i32_at_0x08"))
    except (TypeError, ValueError):
        return None


def state_has_advanced(capture: LiveCapture, minimum_steps: int = 1) -> bool:
    age = state_age(capture)
    return age is not None and age >= max(int(minimum_steps), 1)


def is_idle_armed_state(capture: LiveCapture) -> bool:
    return (
        is_idle_state(capture)
        and state_value(capture, "body_bet_i32_at_0x58") == 3
        and is_input_released(capture)
        and state_has_advanced(capture)
    )


def needs_max_bet(capture: LiveCapture) -> bool:
    """Only a confirmed idle 1/1 state with bet 3 is already armed.

    A fresh 0/0 sample can retain a stale bet field, so it must always pass
    through an accepted MAX BET input before the lever is allowed.
    """

    return not is_idle_armed_state(capture)


def ensure_message_queue_caught_up(
    capture: LiveCapture,
    *,
    timeout: float,
) -> dict[str, int]:
    """Consume every callback already enqueued before an input boundary.

    Frida callbacks timestamp records before enqueueing them.  Reaching equal
    enqueue/processed counters with an empty queue establishes a local live
    edge.  If the observer stream cannot be caught up within the bound, input
    is forbidden instead of being repeated against stale evidence.
    """

    deadline = time.monotonic() + max(timeout, 0.0)
    while True:
        while capture.messages_processed < capture.messages_enqueued:
            if time.monotonic() >= deadline:
                raise HuntError(
                    "observer message queue did not catch up before input: "
                    f"processed={capture.messages_processed} "
                    f"enqueued={capture.messages_enqueued} "
                    f"queued={capture.events.qsize()}"
                )
            if capture.pump(0.0) is None:
                break
        if (
            capture.messages_processed == capture.messages_enqueued
            and capture.events.empty()
        ):
            return {
                "sequence": capture.sequence,
                "host_unix_ms": int(time.time() * 1000),
                "messages_processed": capture.messages_processed,
            }
        if time.monotonic() >= deadline:
            raise HuntError(
                "observer message queue did not catch up before input: "
                f"processed={capture.messages_processed} "
                f"enqueued={capture.messages_enqueued} "
                f"queued={capture.events.qsize()}"
            )
        capture.pump(min(0.01, max(deadline - time.monotonic(), 0.0)))


def target_for_batch(batch: dict[str, Any]) -> dict[str, Any] | None:
    pairs = batch.get("sp_story_selection_pairs")
    if not isinstance(pairs, list):
        return None
    resolved: list[dict[str, Any]] = []
    for pair in pairs:
        if not isinstance(pair, dict):
            continue
        try:
            key = (int(pair.get("stage")), int(pair.get("selector")))
        except (TypeError, ValueError):
            continue
        target = TARGETS_BY_STAGE_SELECTOR.get(key)
        if target is not None:
            resolved.append({**target, "stage": key[0], "selector": key[1]})
    if not resolved:
        return None
    first = resolved[0]
    if any(row["event"] != first["event"] for row in resolved[1:]):
        return None
    return first


def is_spin_state(capture: LiveCapture) -> bool:
    return (
        state_value(capture, "body_state_i32_at_0x00") == 3
        and state_value(capture, "body_mode_i32_at_0x04") == 3
    )


def is_spin_ready_state(capture: LiveCapture, minimum_steps: int = 1) -> bool:
    return (
        is_spin_state(capture)
        and is_input_released(capture)
        and state_has_advanced(capture, minimum_steps)
    )


def is_stop_engine_ready(capture: LiveCapture, minimum_steps: int = 17) -> bool:
    """Gate a stop on the counters used by CSlotBody::STOP/calcStop.

    In the normal non-FastAuto path, body+0x538 reaches 16 before calcStop is
    entered.  calcStop then requires the inter-stop counter at +0x53c to reach
    5 and +0x540 to be -1 (no axis waiting for updateReel).  These are bounded
    named fields from the same CSlotBody pointer, not visual readiness guesses.
    """

    try:
        wait16 = int(state_value(capture, "body_stop_wait16_i32_at_0x538"))
        interstop = int(state_value(capture, "body_interstop_i32_at_0x53c"))
        selected_axis = int(state_value(capture, "body_selected_axis_i32_at_0x540"))
    except (TypeError, ValueError):
        return False
    return (
        is_spin_ready_state(capture, minimum_steps)
        and wait16 >= 16
        and interstop >= 5
        and selected_axis == -1
    )


def has_stop_progress(capture: LiveCapture, action: str) -> bool:
    """Confirm that the reel state machine, not merely input routing, advanced."""

    expected = STOP_PROGRESS_MASKS[action]
    try:
        observed = int(state_value(capture, "state_u32_at_0x64"))
    except (TypeError, ValueError):
        return False
    return observed & expected == expected


def find_reel_stop_after(
    capture: LiveCapture,
    *,
    baseline_sequence: int,
    issued_host_unix_ms: int,
    expected_axis: int,
) -> dict[str, Any] | None:
    """Return the exact post-input CReel::setStopAngle(axis, ...) call."""

    for event in capture.reel_stop_events:
        if int(event.get("sequence", 0)) <= baseline_sequence:
            continue
        if int(event.get("host_unix_ms", 0)) <= issued_host_unix_ms:
            continue
        try:
            axis = int(event.get("axis_i32"))
        except (TypeError, ValueError):
            continue
        if axis == expected_axis:
            return event
    return None


def has_reel_stop_after(
    capture: LiveCapture,
    *,
    baseline_sequence: int,
    issued_host_unix_ms: int,
    expected_axis: int,
) -> bool:
    return find_reel_stop_after(
        capture,
        baseline_sequence=baseline_sequence,
        issued_host_unix_ms=issued_host_unix_ms,
        expected_axis=expected_axis,
    ) is not None


def capture_stop_progress_evidence(
    capture: LiveCapture,
    *,
    action: str,
    stop_action: dict[str, Any],
    expected_axis: int,
) -> dict[str, Any] | None:
    """Freeze the first state snapshot proving an accepted stop advanced.

    The returned row binds the authoritative CReel callback and cumulative
    state+0x64 mask to the same post-input waterline.  Callers retain the first
    non-null result rather than later, more advanced masks.
    """

    if not has_stop_progress(capture, action):
        return None
    reel_stop = find_reel_stop_after(
        capture,
        baseline_sequence=int(stop_action["issued_after_sequence"]),
        issued_host_unix_ms=int(stop_action["issued_host_unix_ms"]),
        expected_axis=expected_axis,
    )
    if reel_stop is None:
        return None
    try:
        observed_mask = int(state_value(capture, "state_u32_at_0x64"))
    except (TypeError, ValueError):
        return None
    return {
        "progress_expected_mask": STOP_PROGRESS_MASKS[action],
        "progress_observed_mask": observed_mask,
        "progress_observed_sequence": capture.sequence,
        "progress_observed_host_unix_ms": int(time.time() * 1000),
        "progress_observed_state_age": state_age(capture),
        "progress_observed_gate_snapshot": copy.deepcopy(capture.latest_gate_state),
        "progress_reel_stop_sequence": reel_stop.get("sequence"),
        "progress_reel_stop_host_unix_ms": reel_stop.get("host_unix_ms"),
        "progress_reel_stop_axis_i32": reel_stop.get("axis_i32"),
    }


def is_post_lever_state(capture: LiveCapture) -> bool:
    """Recognize the sampled transition after an accepted lever.

    The change-only gate observes ``CSlotBody::process`` calls, not a periodic
    state poll.  A lever call can therefore leave the latest sample at 1/2;
    the historical 3/3 sample is first seen only when a stop candidate enters
    ``process``.  Requiring 3/3 before trying that stop is a circular gate.
    Stop acceptance remains authoritative only when process reports bit 2/4/8.
    """

    state = state_value(capture, "body_state_i32_at_0x00")
    mode = state_value(capture, "body_mode_i32_at_0x04")
    return (state, mode) in {(1, 2), (3, 3)}


def find_input_after(
    capture: LiveCapture,
    *,
    baseline_sequence: int,
    issued_host_unix_ms: int,
    expected_bit: int,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    expected: dict[str, Any] | None = None
    unexpected: dict[str, Any] | None = None
    for event in capture.input_events:
        if int(event.get("sequence", 0)) <= baseline_sequence:
            continue
        if int(event.get("host_unix_ms", 0)) <= issued_host_unix_ms:
            continue
        payload = event.get("payload") or {}
        if payload.get("process_input_a_i32") == expected_bit:
            expected = event
            break
        unexpected = event
        break
    return expected, unexpected


def tap_until_accepted(
    args: argparse.Namespace,
    capture: LiveCapture,
    *,
    expected_pid: int,
    action: str,
    coordinate: tuple[int, int],
    expected_reel_axis: int | None = None,
) -> dict[str, Any]:
    if not args.execute:
        raise HuntError("internal safety error: attempted input without --execute")
    expected_bit = EXPECTED_INPUT_BITS[action]
    if action in STOP_PROGRESS_MASKS and expected_reel_axis is None:
        raise HuntError(f"internal safety error: no expected reel axis for {action}")
    overall_deadline = time.monotonic() + max(args.input_overall_timeout, 0.0)
    require_same_runtime(args, expected_pid)
    queue_waterline = ensure_message_queue_caught_up(
        capture,
        timeout=min(
            max(args.queue_catch_up_timeout, 0.0),
            max(overall_deadline - time.monotonic(), 0.0),
        ),
    )
    baseline_sequence = capture.sequence
    issued_host_unix_ms = int(time.time() * 1000)
    press_duration_ms = max(int(args.press_duration_ms), 1)
    input_argv = adb_command(
        args,
        "shell",
        "input",
        "swipe",
        str(coordinate[0]),
        str(coordinate[1]),
        str(coordinate[0]),
        str(coordinate[1]),
        str(press_duration_ms),
    )
    input_method = "single_stationary_swipe"
    result = run_command(input_argv)
    if result.returncode != 0:
        raise HuntError(f"ADB tap failed for {action}: {result.stderr!r}")

    def accepted_input() -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        return find_input_after(
            capture,
            baseline_sequence=baseline_sequence,
            issued_host_unix_ms=issued_host_unix_ms,
            expected_bit=expected_bit,
        )

    def accepted_reel_stop() -> dict[str, Any] | None:
        if expected_reel_axis is None:
            return None
        return find_reel_stop_after(
            capture,
            baseline_sequence=baseline_sequence,
            issued_host_unix_ms=issued_host_unix_ms,
            expected_axis=expected_reel_axis,
        )

    confirm_deadline = min(
        overall_deadline,
        time.monotonic() + max(args.input_confirm_timeout, 0.0),
    )
    while time.monotonic() < confirm_deadline:
        capture.pump(min(0.05, max(confirm_deadline - time.monotonic(), 0.0)))
        expected, unexpected = accepted_input()
        reel_stop = accepted_reel_stop()
        if unexpected is not None:
            payload = unexpected.get("payload") or {}
            raise HuntError(
                f"{action} produced unexpected nonzero process input: "
                f"A={payload.get('process_input_a_i32')} "
                f"B={payload.get('process_input_b_i32')}"
            )
        if expected is not None or reel_stop is not None:
            break
    else:
        expected, unexpected = accepted_input()
        reel_stop = accepted_reel_stop()

    if expected is None and unexpected is None:
        ensure_message_queue_caught_up(
            capture,
            timeout=min(
                max(args.queue_catch_up_timeout, 0.0),
                max(overall_deadline - time.monotonic(), 0.0),
            ),
        )
        expected, unexpected = accepted_input()
        reel_stop = accepted_reel_stop()
    if unexpected is not None:
        payload = unexpected.get("payload") or {}
        raise HuntError(
            f"{action} produced unexpected nonzero process input: "
            f"A={payload.get('process_input_a_i32')} "
            f"B={payload.get('process_input_b_i32')}"
        )
    if expected is None and reel_stop is None:
        raise HuntError(
            f"single {action} gesture was confirmed by neither process input bit "
            f"{expected_bit} nor the expected setStopAngle axis; input was not repeated"
        )
    authoritative = reel_stop if reel_stop is not None else expected
    return {
        "action": action,
        "expected_process_input_a_i32": expected_bit,
        "coordinate": list(coordinate),
        "input_method": input_method,
        "press_duration_ms": press_duration_ms,
        "tap_attempt": 1,
        "issued_host_unix_ms": issued_host_unix_ms,
        "issued_after_sequence": baseline_sequence,
        "queue_waterline": queue_waterline,
        "accepted_sequence": authoritative.get("sequence"),
        "accepted_host_unix_ms": authoritative.get("host_unix_ms"),
        "process_input_confirmed": expected is not None,
        "process_input_sequence": expected.get("sequence") if expected is not None else None,
        "process_input_host_unix_ms": (
            expected.get("host_unix_ms") if expected is not None else None
        ),
        "reel_stop_confirmed": reel_stop is not None,
        "reel_stop_axis": reel_stop.get("axis_i32") if reel_stop is not None else None,
        "reel_stop_sequence": reel_stop.get("sequence") if reel_stop is not None else None,
        "reel_stop_host_unix_ms": (
            reel_stop.get("host_unix_ms") if reel_stop is not None else None
        ),
        "accepted_payload": expected.get("payload") if expected is not None else None,
    }


def wait_for_state_with_runtime_checks(
    args: argparse.Namespace,
    capture: LiveCapture,
    *,
    expected_pid: int,
    predicate: Callable[[], bool],
    timeout: float,
    description: str,
) -> None:
    deadline = time.monotonic() + max(timeout, 0.0)
    next_runtime_check = 0.0
    while True:
        capture.refresh_gate_snapshot()
        if predicate():
            return
        now = time.monotonic()
        if now >= deadline:
            raise HuntError(f"timed out waiting for {description}")
        if now >= next_runtime_check:
            require_same_runtime(args, expected_pid)
            next_runtime_check = now + max(args.foreground_check_interval, 0.1)
        capture.pump(min(0.1, max(deadline - now, 0.0)))


def append_journal(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", buffering=1) as handle:
        handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def bgm_upstream_probe_provenance(capture: LiveCapture) -> dict[str, Any]:
    """Bind each compact attempt trace to its validated hash/hook/field contract."""

    sound_logic = capture.ready_payloads.get("sound_logic")
    if not isinstance(sound_logic, dict):
        return {
            "available": False,
            "reason": "sound_logic_ready_payload_not_retained",
        }
    hook_status = sound_logic.get("hook_status")
    upstream_hooks = {
        key: copy.deepcopy(hook_status.get(key))
        for key in sorted(EXPECTED_BGM_UPSTREAM_HOOK_KEYS)
        if isinstance(hook_status, dict) and key in hook_status
    }
    return {
        "available": True,
        "installed_split_identity": copy.deepcopy(
            capture.installed_split_identity
        ),
        "game_proc_identity_status": copy.deepcopy(
            sound_logic.get("game_proc_identity_status")
        ),
        "upstream_hook_status": upstream_hooks,
        "sdgm_accessor_status": copy.deepcopy(
            sound_logic.get("bgm_upstream_sdgm_accessor_status")
        ),
        "field_schema": copy.deepcopy(sound_logic.get("bgm_upstream_field_schema")),
        "window_rpc": copy.deepcopy(sound_logic.get("bgm_upstream_window_rpc")),
    }


def compact_attempt_summary(
    *,
    attempt: int,
    started_unix_ms: int,
    outcome: str,
    actions: list[dict[str, Any]],
    capture: LiveCapture,
    error: str = "",
) -> dict[str, Any]:
    return {
        "schema": "magireco-natural-sp-story-hunt-attempt-v1",
        "host_unix_ms": int(time.time() * 1000),
        "attempt": attempt,
        "started_unix_ms": started_unix_ms,
        "outcome": outcome,
        "error": error,
        "accepted_actions": [
            {
                "action": row.get("action"),
                "expected_process_input_a_i32": row.get("expected_process_input_a_i32"),
                "coordinate": row.get("coordinate"),
                "input_method": row.get("input_method"),
                "press_duration_ms": row.get("press_duration_ms"),
                "tap_attempt": row.get("tap_attempt"),
                "issued_host_unix_ms": row.get("issued_host_unix_ms"),
                "issued_after_sequence": row.get("issued_after_sequence"),
                "queue_waterline": row.get("queue_waterline"),
                "accepted_sequence": row.get("accepted_sequence"),
                "accepted_host_unix_ms": row.get("accepted_host_unix_ms"),
                "process_input_confirmed": row.get("process_input_confirmed"),
                "process_input_sequence": row.get("process_input_sequence"),
                "reel_stop_confirmed": row.get("reel_stop_confirmed"),
                "reel_stop_axis": row.get("reel_stop_axis"),
                "reel_stop_sequence": row.get("reel_stop_sequence"),
                "progress_expected_mask": row.get("progress_expected_mask"),
                "progress_observed_mask": row.get("progress_observed_mask"),
                "progress_observed_sequence": row.get("progress_observed_sequence"),
                "progress_observed_host_unix_ms": row.get(
                    "progress_observed_host_unix_ms"
                ),
                "progress_observed_state_age": row.get("progress_observed_state_age"),
                "progress_observed_gate_snapshot": row.get(
                    "progress_observed_gate_snapshot"
                ),
                "progress_reel_stop_sequence": row.get("progress_reel_stop_sequence"),
                "progress_reel_stop_host_unix_ms": row.get(
                    "progress_reel_stop_host_unix_ms"
                ),
                "progress_reel_stop_axis_i32": row.get("progress_reel_stop_axis_i32"),
            }
            for row in actions
        ],
        "dispatch_batches": capture.dispatch_tracker.dispatch_batches(),
        "complete_candidate_count": len(capture.complete_candidates),
        "selection_candidate": capture.selection_candidate,
        "observed_event_codes": capture.observed_event_codes,
        "sound_pack_pre_gate_volume_events": copy.deepcopy(
            capture.sound_pack_pre_gate_events
        ),
        "sound_logic_request_trace": {
            "schema": "magireco-natural-sound-request-trace-v1",
            "retained_event_count": len(capture.sound_request_trace_events),
            "dropped_event_count": capture.sound_request_trace_dropped_count,
            "complete": capture.sound_request_trace_dropped_count == 0
            and not capture.attempt_probe_errors,
            "maximum_retained_events": capture.max_sound_request_trace_events,
            "bgm_upstream_window": copy.deepcopy(capture.bgm_upstream_window),
            "bgm_upstream_field_schema": copy.deepcopy(
                EXPECTED_BGM_UPSTREAM_FIELD_SCHEMA
            ),
            "bgm_upstream_provenance": bgm_upstream_probe_provenance(capture),
            "event_count_by_kind": dict(
                sorted(capture.sound_request_trace_event_count_by_kind.items())
            ),
            "causal_policy": (
                "only equal perform_invocation_id/play_request_call_id values emitted "
                "from a synchronous nested stack are causal; timestamps and sound IDs alone "
                "remain correlation evidence"
            ),
            "probe_errors": copy.deepcopy(capture.attempt_probe_errors),
            "events": copy.deepcopy(capture.sound_request_trace_events),
        },
        "target_batch": capture.target_batch,
        "buffer_overflow": capture.buffer_overflow,
        "buffered_observer_bytes": capture.attempt_bytes,
        "final_gate_state": capture.latest_gate_state,
        "latest_sdgm_state": dict(capture.latest_sdgm_state),
        "reel_stop_events": list(capture.reel_stop_events),
        "outer_bgm_active_sound_snapshots": copy.deepcopy(capture.outer_bgm_snapshots),
    }


def unique_target_dir(out_dir: Path, attempt: int) -> Path:
    stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    base = out_dir / f"target_hit_{stamp}_attempt_{attempt:06d}"
    if not base.exists():
        return base
    for suffix in range(1, 1000):
        candidate = out_dir / f"{base.name}_{suffix:03d}"
        if not candidate.exists():
            return candidate
    raise HuntError("could not allocate a unique target output directory")


def write_target_package(
    args: argparse.Namespace,
    capture: LiveCapture,
    *,
    attempt: int,
    runtime_state: dict[str, Any],
    actions: list[dict[str, Any]],
    journal_path: Path,
) -> Path:
    if capture.target_batch is None:
        raise HuntError("cannot write target package without a complete target batch")
    target_dir = unique_target_dir(args.out_dir, attempt)
    target_dir.mkdir(parents=True, exist_ok=False)
    observer_paths: dict[str, Path] = {}
    for name in capture.script_paths:
        path = target_dir / f"observer_{name}.jsonl"
        lines = capture.session_records[name] + capture.attempt_records[name]
        path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        observer_paths[name] = path

    injected_probe_paths: dict[str, Path] = {}
    for name, source_bytes in capture.loaded_probe_source_bytes.items():
        path = target_dir / f"injected_probe_{name}.js"
        path.write_bytes(source_bytes)
        injected_probe_paths[f"injected_probe_{name}"] = path

    provenance_paths = {
        "hunt_driver": Path(__file__).resolve(),
        "shared_batch_logic": (
            repo_root() / "tools" / "frida_runtime_probe" / "summarize_lightweight_spin_probe.py"
        ).resolve(),
        **injected_probe_paths,
    }
    hashes: dict[str, dict[str, Any]] = {}
    for name, path in {**observer_paths, **provenance_paths, "hunt_journal": journal_path}.items():
        hashes[name] = {
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    manifest = {
        "schema": "magireco-natural-sp-story-target-capture-v1",
        "created_unix_ms": int(time.time() * 1000),
        "evidence_gate": (
            "same strict ID401 getCmdBuf/accessSubProcess batch contains "
            "ID19 raw[1]=8 and legal ID24 stage/selector"
        ),
        "visual_matching_used": False,
        "adb_input_enabled": bool(args.execute),
        "single_gadget_session": True,
        "runtime": runtime_state,
        "attempt": attempt,
        "expected_process_input_a_i32": EXPECTED_INPUT_BITS,
        "accepted_actions": actions,
        "target_batch": capture.target_batch,
        "resolved_target_event": capture.target_batch.get("resolved_event"),
        "all_dispatch_batches": capture.dispatch_tracker.dispatch_batches(),
        "probe_ready_payloads": copy.deepcopy(capture.ready_payloads),
        "loaded_probe_sources": copy.deepcopy(capture.loaded_probe_sources),
        "sound_logic_request_trace": {
            "schema": "magireco-natural-sound-request-trace-v1",
            "retained_event_count": len(capture.sound_request_trace_events),
            "dropped_event_count": capture.sound_request_trace_dropped_count,
            "complete": capture.sound_request_trace_dropped_count == 0
            and not capture.attempt_probe_errors,
            "maximum_retained_events": capture.max_sound_request_trace_events,
            "bgm_upstream_window": copy.deepcopy(capture.bgm_upstream_window),
            "bgm_upstream_field_schema": copy.deepcopy(
                EXPECTED_BGM_UPSTREAM_FIELD_SCHEMA
            ),
            "bgm_upstream_provenance": bgm_upstream_probe_provenance(capture),
            "event_count_by_kind": dict(
                sorted(capture.sound_request_trace_event_count_by_kind.items())
            ),
            "probe_errors": copy.deepcopy(capture.attempt_probe_errors),
            "events": copy.deepcopy(capture.sound_request_trace_events),
        },
        "outer_bgm_active_sound_snapshots": copy.deepcopy(capture.outer_bgm_snapshots),
        "buffer_overflow": capture.buffer_overflow,
        "observer_and_source_hashes": hashes,
    }
    manifest_path = target_dir / "capture_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    hashes["capture_manifest"] = {
        "path": str(manifest_path),
        "bytes": manifest_path.stat().st_size,
        "sha256": sha256_file(manifest_path),
    }
    (target_dir / "sha256sums.json").write_text(
        json.dumps(hashes, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target_dir


def script_paths_from_args(args: argparse.Namespace) -> dict[str, Path]:
    return {
        "slot_gate": args.slot_gate_script,
        "dispatch": args.dispatch_script,
        "sound_logic": args.sound_logic_script,
    }


def validate_args(args: argparse.Namespace) -> None:
    if args.expected_pid < 0:
        raise HuntError("--expected-pid must be >= 0")
    if args.max_attempts < 0:
        raise HuntError("--max-attempts must be >= 0")
    if args.max_buffer_mib < 0:
        raise HuntError("--max-buffer-mib must be >= 0")
    if args.queue_catch_up_timeout < 0:
        raise HuntError("--queue-catch-up-timeout must be >= 0")
    missing = [str(path) for path in script_paths_from_args(args).values() if not path.is_file()]
    if missing:
        raise HuntError(f"probe script(s) missing: {missing!r}")


def main() -> int:
    args = parse_args()
    args.out_dir = args.out_dir.resolve()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    journal_path = args.out_dir / "hunt_journal.jsonl"
    capture: LiveCapture | None = None
    installed_split_identity: dict[str, Any] | None = None
    try:
        validate_args(args)
        initial_runtime = inspect_foreground(args)
        if args.expected_pid and initial_runtime["pid"] != args.expected_pid:
            raise HuntError(
                f"expected game PID {args.expected_pid}, observed {initial_runtime['pid']}"
            )
        installed_split_identity = inspect_installed_arm64_split(args)
        initial_runtime["installed_arm64_split_identity"] = copy.deepcopy(
            installed_split_identity
        )
        capture = LiveCapture(
            host=args.host,
            expected_pid=initial_runtime["pid"],
            script_paths=script_paths_from_args(args),
            max_buffer_bytes=int(args.max_buffer_mib * 1024 * 1024),
        )
        capture.installed_split_identity = copy.deepcopy(installed_split_identity)
        capture.attach()
        capture.wait_until(
            lambda: capture.ready == set(PROBE_FILES),
            args.probe_ready_timeout,
            "all three probes to report ready",
        )
        validate_probe_ready_contracts(
            capture.ready_payloads,
            installed_split_identity=installed_split_identity,
        )
        capture.wait_until(
            lambda: capture.latest_gate_state is not None,
            args.ready_state_timeout,
            "initial CSlotBody::process state",
        )
        require_same_runtime(args, initial_runtime["pid"])
        loaded_probe_sources = copy.deepcopy(capture.loaded_probe_sources)
        initial_outer_bgm_snapshot = capture.record_outer_bgm_snapshot("session_ready")
        append_journal(
            journal_path,
            {
                "schema": "magireco-natural-sp-story-hunt-session-v1",
                "host_unix_ms": int(time.time() * 1000),
                "event": "session_ready",
                "execute": bool(args.execute),
                "runtime": initial_runtime,
                "gadget_host": args.host,
                "expected_process_input_a_i32": EXPECTED_INPUT_BITS,
                "initial_gate_state": capture.latest_gate_state,
                "loaded_probe_sources": loaded_probe_sources,
                "probe_ready_payloads": copy.deepcopy(capture.ready_payloads),
                "initial_outer_bgm_active_sound_snapshot": initial_outer_bgm_snapshot,
            },
        )

        if not args.execute:
            capture.begin_attempt()
            dry_run_started_unix_ms = int(time.time() * 1000)
            try:
                capture.pump_for(args.dry_run_seconds)
                require_same_runtime(args, initial_runtime["pid"])
                capture.finish_bgm_upstream_window()
                final_outer_bgm_snapshot = capture.record_outer_bgm_snapshot(
                    "dry_run_complete"
                )
                dry_run_trace = compact_attempt_summary(
                    attempt=0,
                    started_unix_ms=dry_run_started_unix_ms,
                    outcome="read_only_dry_run",
                    actions=[],
                    capture=capture,
                )["sound_logic_request_trace"]
                append_journal(
                    journal_path,
                    {
                        "schema": "magireco-natural-sp-story-hunt-session-v1",
                        "host_unix_ms": int(time.time() * 1000),
                        "event": "dry_run_complete",
                        "adb_input_sent": False,
                        "runtime": initial_runtime,
                        "final_gate_state": capture.latest_gate_state,
                        "final_outer_bgm_active_sound_snapshot": final_outer_bgm_snapshot,
                        "sound_logic_request_trace": dry_run_trace,
                    },
                )
            except Exception as error:
                window_close_error: Exception | None = None
                try:
                    capture.finish_bgm_upstream_window()
                except Exception as close_error:
                    window_close_error = close_error
                recorded_error = repr(error)
                if window_close_error is not None:
                    recorded_error += (
                        "; bgm_upstream_window_close_error="
                        + repr(window_close_error)
                    )
                append_journal(
                    journal_path,
                    {
                        "schema": "magireco-natural-sp-story-hunt-session-v1",
                        "host_unix_ms": int(time.time() * 1000),
                        "event": "dry_run_error",
                        "adb_input_sent": False,
                        "error": recorded_error,
                        "sound_logic_request_trace": compact_attempt_summary(
                            attempt=0,
                            started_unix_ms=dry_run_started_unix_ms,
                            outcome="read_only_dry_run_error",
                            actions=[],
                            capture=capture,
                            error=recorded_error,
                        )["sound_logic_request_trace"],
                    },
                )
                raise
            finally:
                capture.end_attempt()
            print(json.dumps({"ok": True, "dry_run": True, "journal": str(journal_path)}))
            return 0

        attempt = 0
        while args.max_attempts == 0 or attempt < args.max_attempts:
            attempt += 1
            require_same_runtime(args, initial_runtime["pid"])
            wait_for_state_with_runtime_checks(
                args,
                capture,
                expected_pid=initial_runtime["pid"],
                predicate=lambda: is_bettable_state(capture),
                timeout=args.ready_state_timeout,
                description="bettable state 0/0 or idle state 1/1 before the next attempt",
            )
            ensure_message_queue_caught_up(
                capture,
                timeout=args.queue_catch_up_timeout,
            )
            if not is_bettable_state(capture):
                raise HuntError(
                    "slot left bettable state while the observer queue was catching up"
                )
            capture.begin_attempt()
            started_unix_ms = int(time.time() * 1000)
            actions: list[dict[str, Any]] = []
            try:
                capture.record_outer_bgm_snapshot("attempt_pre")
                if needs_max_bet(capture):
                    actions.append(
                        tap_until_accepted(
                            args,
                            capture,
                            expected_pid=initial_runtime["pid"],
                            action="max_bet",
                            coordinate=args.max_bet,
                        )
                    )
                    wait_for_state_with_runtime_checks(
                        args,
                        capture,
                        expected_pid=initial_runtime["pid"],
                        predicate=lambda: is_idle_armed_state(capture),
                        timeout=args.ready_state_timeout,
                        description=(
                            "released and advanced idle state 1/1 with bet 3 "
                            "after accepted max bet"
                        ),
                    )
                lever = tap_until_accepted(
                    args,
                    capture,
                    expected_pid=initial_runtime["pid"],
                    action="lever",
                    coordinate=args.lever,
                )
                actions.append(lever)
                capture.mark_lever_issued(
                    int(lever["issued_after_sequence"]),
                    int(lever["issued_host_unix_ms"]),
                )

                wait_for_state_with_runtime_checks(
                    args,
                    capture,
                    expected_pid=initial_runtime["pid"],
                    predicate=lambda: capture.target_batch is not None
                    or is_stop_engine_ready(capture, args.spin_settle_steps),
                    timeout=args.ready_state_timeout,
                    description="released and advanced spin state 3/3",
                )
                stop_actions = (
                    ("left_stop", args.left_stop, 0),
                    ("middle_stop", args.middle_stop, 1),
                    ("right_stop", args.right_stop, 2),
                )
                for stop_index, (action, coordinate, expected_axis) in enumerate(stop_actions):
                    if capture.target_batch is not None:
                        break
                    stop_action = tap_until_accepted(
                        args,
                        capture,
                        expected_pid=initial_runtime["pid"],
                        action=action,
                        coordinate=coordinate,
                        expected_reel_axis=expected_axis,
                    )
                    stop_action.update(
                        {
                            "progress_expected_mask": STOP_PROGRESS_MASKS[action],
                            "progress_observed_mask": None,
                            "progress_observed_sequence": None,
                            "progress_observed_host_unix_ms": None,
                            "progress_observed_state_age": None,
                            "progress_observed_gate_snapshot": None,
                            "progress_reel_stop_sequence": None,
                            "progress_reel_stop_host_unix_ms": None,
                            "progress_reel_stop_axis_i32": None,
                        }
                    )
                    actions.append(stop_action)
                    progress_evidence: dict[str, Any] | None = None

                    def stop_progress_reached() -> bool:
                        nonlocal progress_evidence
                        if capture.target_batch is not None:
                            return True
                        if progress_evidence is None:
                            progress_evidence = capture_stop_progress_evidence(
                                capture,
                                action=action,
                                stop_action=stop_action,
                                expected_axis=expected_axis,
                            )
                        return progress_evidence is not None

                    wait_for_state_with_runtime_checks(
                        args,
                        capture,
                        expected_pid=initial_runtime["pid"],
                        predicate=stop_progress_reached,
                        timeout=args.stop_progress_timeout,
                        description=(
                            f"{action} CReel::setStopAngle axis {expected_axis} and "
                            f"state+0x64 progress mask 0x{STOP_PROGRESS_MASKS[action]:08x}"
                        ),
                    )
                    if progress_evidence is not None:
                        stop_action.update(progress_evidence)
                    if capture.target_batch is not None:
                        break
                    if stop_index < len(stop_actions) - 1:
                        progress_age = state_age(capture)
                        if progress_age is None:
                            raise HuntError(
                                f"{action} progress was observed without a state age"
                            )
                        wait_for_state_with_runtime_checks(
                            args,
                            capture,
                            expected_pid=initial_runtime["pid"],
                            predicate=lambda: capture.target_batch is not None
                            or (
                                is_stop_engine_ready(
                                    capture,
                                    progress_age + args.inter_stop_settle_steps,
                                )
                            ),
                            timeout=args.ready_state_timeout,
                            description=(
                                "released spin state 3/3 and post-stop settle steps "
                                "before the next stop input"
                            ),
                        )

                wait_for_state_with_runtime_checks(
                    args,
                    capture,
                    expected_pid=initial_runtime["pid"],
                    predicate=lambda: capture.target_batch is not None
                    or is_bettable_state(capture),
                    timeout=args.round_timeout,
                    description="target dispatch batch or natural return to bettable 0/0 or 1/1",
                )
                if capture.target_batch is not None:
                    capture.record_outer_bgm_snapshot("target_window")
                    capture.pump_for(args.post_hit_seconds)
                    require_same_runtime(args, initial_runtime["pid"])
                    capture.record_outer_bgm_snapshot("attempt_post")
                    capture.finish_bgm_upstream_window()
                    outcome = "target_hit" if not capture.buffer_overflow else "target_hit_buffer_overflow"
                    row = compact_attempt_summary(
                        attempt=attempt,
                        started_unix_ms=started_unix_ms,
                        outcome=outcome,
                        actions=actions,
                        capture=capture,
                    )
                    append_journal(journal_path, row)
                    target_dir = write_target_package(
                        args,
                        capture,
                        attempt=attempt,
                        runtime_state=initial_runtime,
                        actions=actions,
                        journal_path=journal_path,
                    )
                    print(
                        json.dumps(
                            {
                                "ok": not capture.buffer_overflow,
                                "target_hit": True,
                                "attempt": attempt,
                                "target_dir": str(target_dir),
                                "journal": str(journal_path),
                            },
                            ensure_ascii=False,
                        )
                    )
                    return 0 if not capture.buffer_overflow else 2

                capture.record_outer_bgm_snapshot("attempt_post")
                capture.finish_bgm_upstream_window()
                append_journal(
                    journal_path,
                    compact_attempt_summary(
                        attempt=attempt,
                        started_unix_ms=started_unix_ms,
                        outcome="non_target",
                        actions=actions,
                        capture=capture,
                    ),
                )
            except Exception as error:
                window_close_error: Exception | None = None
                try:
                    capture.finish_bgm_upstream_window()
                except Exception as close_error:
                    window_close_error = close_error
                capture.record_outer_bgm_snapshot("attempt_post_error")
                recorded_error = repr(error)
                if window_close_error is not None:
                    recorded_error += (
                        "; bgm_upstream_window_close_error="
                        + repr(window_close_error)
                    )
                append_journal(
                    journal_path,
                    compact_attempt_summary(
                        attempt=attempt,
                        started_unix_ms=started_unix_ms,
                        outcome="attempt_error",
                        actions=actions,
                        capture=capture,
                        error=recorded_error,
                    ),
                )
                if window_close_error is not None:
                    raise HuntError(recorded_error) from error
                raise
            finally:
                if capture.target_batch is None:
                    capture.end_attempt()

        append_journal(
            journal_path,
            {
                "schema": "magireco-natural-sp-story-hunt-session-v1",
                "host_unix_ms": int(time.time() * 1000),
                "event": "max_attempts_reached",
                "attempts": attempt,
                "target_hit": False,
            },
        )
        print(
            json.dumps(
                {
                    "ok": True,
                    "target_hit": False,
                    "attempts": attempt,
                    "journal": str(journal_path),
                }
            )
        )
        return 0
    except Exception as error:
        fatal_row: dict[str, Any] = {
            "schema": "magireco-natural-sp-story-hunt-session-v1",
            "host_unix_ms": int(time.time() * 1000),
            "event": "fatal_error",
            "error": repr(error),
        }
        if capture is not None:
            fatal_row.update(
                {
                    "probe_ready_payloads": copy.deepcopy(capture.ready_payloads),
                    "probe_errors": copy.deepcopy(capture.probe_errors),
                    "loaded_probe_sources": copy.deepcopy(capture.loaded_probe_sources),
                    "detached_reason": capture.detached_reason,
                }
            )
        if installed_split_identity is not None:
            fatal_row["installed_arm64_split_identity"] = copy.deepcopy(
                installed_split_identity
            )
        append_journal(
            journal_path,
            fatal_row,
        )
        print(json.dumps({"ok": False, "error": repr(error), "journal": str(journal_path)}))
        return 1
    finally:
        if capture is not None:
            capture.close()


if __name__ == "__main__":
    raise SystemExit(main())
