"use strict";

// Low-noise sound request/control observer.
//
// This probe follows metadata only.  It intentionally does not dump PCM,
// compressed media, arbitrary memory windows, or full backtraces.  It records
// all request/order/play metadata so later joins can use exact request and sound
// IDs instead of temporal or visual guesses.

const STATIC_REFERENCE = {
  game_proc_sha256: "5A0AE3CE7F25B89A3B9A13D11BF36AAA1DE04FACEB612357FA04F42426F17EBF",
  game_proc_size_bytes: 79683640,
  game_proc_logical_name: "libGameProc.so",
  game_proc_apk_entry: "lib/arm64-v8a/libGameProc.so",
  game_proc_apk_entry_compression_method: 0,
  game_proc_apk_entry_crc32: "BBB59DED",
  game_proc_apk_entry_header_offset: 2469872,
  game_proc_apk_entry_data_offset: 2473984,
  arm64_apk_module: "split_config.arm64_v8a.apk",
  arm64_apk_size_bytes: 83710748,
  arm64_apk_sha256: "89ACC81D02FF63697603FCE2E5F4281850C092FA833FD8CF3E636B44AB624E24",
  lib_amain_sha256: "58E3F7A9DBCE2E3D79D1A5A30F1DBFEEAC5BB4712BD4D8FF4E6328D2631DCA5D",
  abi: "aarch64-aapcs64",
  csl_active_slot_layout: {
    vector_begin_offset: "0xa0",
    vector_end_offset: "0xa8",
    stride: "0x38",
    source_constructor_offset: "0x12f004",
  },
};

const SYMBOLS = {
  codeName2ReqId: {
    name: "_ZN2zg3snd11RequestCtrl14codeName2ReqIdEPKc",
    expectedOffset: "0x4288b28",
  },
  zgSndReqId: { name: "zgSndReqId", expectedOffset: "0x4272e28" },
  getRequest: {
    name: "_ZN2zg3snd11RequestCtrl10getRequestEjRNS0_7RequestE",
    expectedOffset: "0x42891a4",
  },
  setRequestList: {
    name: "_ZN2zg3snd11RequestCtrl14setRequestListERKNS0_7RequestE",
    expectedOffset: "0x428927c",
  },
  performRequest: {
    name: "_ZN2zg3snd10PlayerImpl14performRequestERNS0_11RequestCtrlERNS0_8ReqOrderEb",
    expectedOffset: "0x4282a3c",
  },
  soundMngSndPlayReq: {
    name: "_ZN8SoundMng10sndPlayReqEiii",
    expectedOffset: "0x425fbdc",
  },
  soundMngChangeVolume: {
    name: "_ZN8SoundMng12changeVolumeEii",
    expectedOffset: "0x425ee68",
  },
  cslMngPlayStart: {
    name: "_ZN6CSLMng9PlayStartEP11SSound_Datai",
    expectedOffset: "0x12fa9c",
  },
  cslMngSndReq: {
    name: "_ZN6CSLMng6SndReqEii",
    expectedOffset: "0x130124",
  },
  cslMngCalc: { name: "_ZN6CSLMng4CalcEv", expectedOffset: "0x12f7c8" },
  cslMngSndGetId: { name: "_ZN6CSLMng8SndGetIDEi", expectedOffset: "0x1308c0" },
  cslMngSndGetChannel: {
    name: "_ZN6CSLMng13SndGetChannelEi",
    expectedOffset: "0x130888",
  },
  cslMngSndGetTime: { name: "_ZN6CSLMng10SndGetTimeEi", expectedOffset: "0x130934" },
  cslMngSndGetLoopNum: {
    name: "_ZN6CSLMng13SndGetLoopNumEi",
    expectedOffset: "0x1309a8",
  },
  cslMngSndGetPriority: {
    name: "_ZN6CSLMng14SndGetPriorityEi",
    expectedOffset: "0x130d04",
  },
  cslMngSndGetLoopF: { name: "_ZN6CSLMng11SndGetLoopFEi", expectedOffset: "0x130d60" },
  cslMngSndGetWaitF: { name: "_ZN6CSLMng11SndGetWaitFEi", expectedOffset: "0x130dbc" },
  cslMngSndGetPauseF: {
    name: "_ZN6CSLMng12SndGetPauseFEi",
    expectedOffset: "0x130e18",
  },
  kndCalLotCcDirEnd: {
    name: "fnKndCalLot_CcDirEnd",
    expectedOffset: "0x4445e3c",
    requiresGameProcIdentity: true,
  },
  kndCalLotRlStart: {
    name: "fnKndCalLot_RlStart",
    expectedOffset: "0x444466c",
    requiresGameProcIdentity: true,
  },
  mstComCbkUpdateGmData: {
    name: "_ZN11C_MstComCbk14fnUpDateGmDataEv",
    expectedOffset: "0x4399a4c",
    requiresGameProcIdentity: true,
  },
  anmBaseDataSetDir: {
    name: "_ZN9C_AnmBase16fnDataSetDir_DIREv",
    expectedOffset: "0x4387f90",
    requiresGameProcIdentity: true,
  },
  objNmlSndRequestBgmDir: {
    name: "_ZN8C_ObjNml20fnSndRequest_BGM_DIREv",
    expectedOffset: "0x43a86b0",
    requiresGameProcIdentity: true,
  },
};

const REQUEST_CODE_BY_ID = { 96: "291", 100: "295", 3094: "16048" };
const CONTEXT_WINDOW_MS = 3000;
const REQUEST_METADATA_TTL_MS = 10000;
const MAX_REQDATA_ROWS = 8;
const CSL_ACTIVE_VECTOR_BEGIN_OFFSET = 0xa0;
const CSL_ACTIVE_VECTOR_END_OFFSET = 0xa8;
const CSL_ACTIVE_SLOT_STRIDE = 0x38;
// Defensive capture cap only.  The game's declared vector length is read from
// begin/end at runtime and is not asserted to equal this value.
const MAX_ACTIVE_SOUND_SLOTS = 128;
const ACTIVE_SNAPSHOT_WAIT_TIMEOUT_MS = 15000;
const CSL_SOUND_DATA_TABLE_BEGIN_OFFSET = 0x08;
const CSL_SOUND_DATA_TABLE_END_OFFSET = 0x10;
const CSL_SOUND_DATA_ENTRY_STRIDE = 0x0c;
const CSL_SOUND_DATA_ENTRY_ID_OFFSET = 0x00;
const CSL_SOUND_DATA_ENTRY_SLOT_OFFSET = 0x08;
const CSL_PENDING_SOUND_DATA_SLOT_OFFSET = 0x20;
const MAX_CSL_SOUND_DATA_TABLE_ROWS = 65536;
const SOUND_PACK_GATE_TABLE_OFFSET = 0x14458dc;
const SOUND_PACK_GATE_ENTRY_COUNT = 222;
const SOUND_PACK_CATEGORY_MAP_POINTER_SLOT_OFFSET = 0x4b8f1c0;
const SOUND_PACK_ADDON_POINTER_SLOT_OFFSET = 0x4b8ea08;
const SOUND_PACK_ACTIVE_ADDON_OFFSET = 0x14c0c;
const SOUND_MNG_INDEXED_VOLUME_BASE_OFFSET = 0x82c;
const SOUND_MNG_MASTER_VOLUME_OFFSET = 0x8ac;
const SDGM_ACCESSOR_SYMBOL = "fnGetAddrSdGmData";
const SDGM_ACCESSOR_EXPECTED_OFFSET = "0x424d474";
const MAX_BGM_UPSTREAM_EVENTS_PER_WINDOW = 1024;
const BGM_UPSTREAM_FIELD_SCHEMA = {
  schema: "magireco-target-bgm-upstream-field-schema-v1",
  sdgm_snapshot_fields: {
    current_kind_u16_at_0x13da: { offset: "0x13da", type: "u16" },
    next_kind_u16_at_0x13dc: { offset: "0x13dc", type: "u16" },
    current_no_u16_at_0x13de: { offset: "0x13de", type: "u16" },
    next_no_u16_at_0x13e0: { offset: "0x13e0", type: "u16" },
    restore_state_u16_at_0x1472: { offset: "0x1472", type: "u16" },
    saved_kind_u16_at_0x1474: { offset: "0x1474", type: "u16" },
    saved_no_u16_at_0x149a: { offset: "0x149a", type: "u16" },
  },
  mstcomcbk_commit_fields: {
    committed_kind_u16_at_0x0a72: { offset: "0xa72", type: "u16" },
    committed_no_u16_at_0x0a76: { offset: "0xa76", type: "u16" },
  },
  obj_nml_snapshot_fields: {
    direction_kind_u16_at_0x00ca: { offset: "0xca", type: "u16" },
    direction_no_u16_at_0x011a: { offset: "0x11a", type: "u16" },
    cached_code_pointer_at_0x0800: { offset: "0x800", type: "pointer" },
    cached_code_string_at_0x0800: {
      offset: "0x800",
      type: "nul_terminated_utf8",
      maximum_bytes: 64,
    },
    cached_code_text_error_at_0x0800: {
      offset: "0x800",
      type: "bounded_read_diagnostic_string",
    },
  },
  event_kinds: {
    knd_cal_lot_cc_dir_end: "sound_logic_bgm_upstream_kndcal_cc_dir_end",
    knd_cal_lot_rl_start: "sound_logic_bgm_upstream_kndcal_rl_start",
    update_gm_data_commit: "sound_logic_bgm_upstream_update_gm_data_commit",
    data_set_dir_commit: "sound_logic_bgm_upstream_data_set_dir_commit",
    bgm_dir_request: "sound_logic_bgm_upstream_bgm_dir_request",
    trace_overflow: "sound_logic_bgm_upstream_trace_overflow",
  },
  emission_policy: {
    window_control: "explicit_rpc_begin_end",
    lottery_hooks: "every_entry_leave_pair_within_window",
    high_frequency_hooks: "first_observation_or_state_change_within_window",
    maximum_emitted_events_per_window: MAX_BGM_UPSTREAM_EVENTS_PER_WINDOW,
    overflow_policy: "emit_overflow_once_and_fail_attempt",
    read_only_observer: true,
  },
};
const SOUND_PACK_REFERENCE_KEYS = {
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
};
const ACTIVE_SOUND_ACCESSOR_TYPES = {
  cslMngSndGetId: "int",
  cslMngSndGetChannel: "int",
  cslMngSndGetTime: "float",
  cslMngSndGetLoopNum: "int",
  cslMngSndGetPriority: "int",
  cslMngSndGetLoopF: "int",
  cslMngSndGetWaitF: "int",
  cslMngSndGetPauseF: "int",
};

const FUNCTION_TYPE_NAMES = {
  0: "NONE",
  1: "PLAY",
  2: "STOP",
  3: "VOL_SPK",
  4: "VOL_EFCT",
  5: "PAUSE",
  6: "REPLAY",
  7: "MUTE_ON",
  8: "MUTE_OFF",
  9: "SET_DUCKING",
  10: "RST_DUCKING",
  11: "VOL_PERMANENT",
  12: "VOL2_PERMANENT",
  13: "CANCEL_REQ",
};

const MEDIA_FORMAT_NAMES = { 0: "NONE", 1: "PCM", 2: "SMZ" };

let eventCountByKind = {};
let nextContextId = 1;
let recentContexts = [];
let requestMetadataByPointer = {};
let codeByRequestId = Object.assign({}, REQUEST_CODE_BY_ID);
let activePerformStackByThread = {};
let activeSoundPlayStackByThread = {};
let nextPerformInvocationId = 1;
let nextSoundPlayCallId = 1;
let nextCslEnqueueId = 1;
let cslRequestTableCacheByManager = {};
let pendingCslEnqueueByKey = {};
let pendingCslEnqueueKeyBySlot = {};
let hookStaticMatchByKey = {};
let hookStatusByKey = {};
let activeSoundAccessors = {};
let activeSoundAccessorStatus = {};
let lastCslMngPointer = null;
let lastCslMngPointerSource = "";
let lastCslMngPointerObservedMs = null;
let cslCalcSnapshotAddress = null;
let cslCalcSnapshotStatus = { status: "not_initialized" };
let activeSnapshotRequestInFlight = false;
let soundPackGateIds = {};
let soundPackPreGateStatus = { status: "not_initialized" };
let lastSoundPackPreGateSignatureByKey = {};
let gameProcIdentityStatus = { status: "not_initialized" };
let gameProcDerivedBase = null;
let sdGmDataAccessor = null;
let sdGmDataAccessorStatus = { status: "not_initialized" };
let bgmUpstreamWindowActive = false;
let bgmUpstreamWindowLabel = "";
let bgmUpstreamWindowEpoch = 0;
let bgmUpstreamWindowEventCount = 0;
let bgmUpstreamWindowDroppedCount = 0;
let bgmUpstreamWindowOverflowEmitted = false;
let bgmUpstreamSignatureByHook = {};
let nextBgmUpstreamCallId = 1;

function emit(kind, fields) {
  eventCountByKind[kind] = (eventCountByKind[kind] || 0) + 1;
  send(
    Object.assign(
      {
        kind,
        unix_ms: Date.now(),
        thread_id: Process.getCurrentThreadId(),
        call_count_for_kind: eventCountByKind[kind],
      },
      fields || {}
    )
  );
}

function toI32(value) {
  try {
    return value.toInt32();
  } catch (_) {
    return null;
  }
}

function toU32(value) {
  try {
    return value.toUInt32();
  } catch (_) {
    return null;
  }
}

function readU8Safe(base, offset) {
  try {
    return base.add(offset).readU8();
  } catch (_) {
    return null;
  }
}

function readU16Safe(base, offset) {
  try {
    return base.add(offset).readU16();
  } catch (_) {
    return null;
  }
}

function readU32Safe(base, offset) {
  try {
    return base.add(offset).readU32();
  } catch (_) {
    return null;
  }
}

function readS32Safe(base, offset) {
  try {
    return base.add(offset).readS32();
  } catch (_) {
    return null;
  }
}

function readPointerSafe(base, offset) {
  try {
    return base.add(offset).readPointer();
  } catch (_) {
    return null;
  }
}

function readU64HexSafe(base, offset) {
  try {
    return normalizeHex("0x" + base.add(offset).readU64().toString(16));
  } catch (_) {
    return null;
  }
}

function pointerText(pointerValue) {
  try {
    return pointerValue === null || pointerValue.isNull() ? "0x0" : pointerValue.toString();
  } catch (_) {
    return "0x0";
  }
}

function readable(pointerValue) {
  try {
    if (pointerValue === null || pointerValue.isNull()) {
      return false;
    }
    const range = Process.findRangeByAddress(pointerValue);
    return range !== null && range.protection.indexOf("r") !== -1;
  } catch (_) {
    return false;
  }
}

function readableSpan(pointerValue, byteLength) {
  try {
    if (!readable(pointerValue) || byteLength < 0) {
      return false;
    }
    const range = Process.findRangeByAddress(pointerValue);
    const requestedEnd = pointerValue.add(byteLength);
    const rangeEnd = range.base.add(range.size);
    return requestedEnd.compare(rangeEnd) <= 0;
  } catch (_) {
    return false;
  }
}

function readUtf8PrefixSafe(pointerValue, limit, requireTerminator) {
  try {
    if (!readable(pointerValue)) {
      return { text_utf8: "", text_error: "null_or_unreadable" };
    }
    const range = Process.findRangeByAddress(pointerValue);
    const offsetInRange = pointerValue.sub(range.base).toInt32();
    const requested = Math.max(0, limit || 512);
    const readableBytes = Math.max(0, Math.min(requested, range.size - offsetInRange));
    let textLength = 0;
    let terminated = false;
    for (; textLength < readableBytes; textLength += 1) {
      if (pointerValue.add(textLength).readU8() === 0) {
        terminated = true;
        break;
      }
    }
    if (requireTerminator && !terminated) {
      return { text_utf8: "", text_error: "unterminated_within_readable_limit" };
    }
    return {
      text_utf8: textLength === 0 ? "" : pointerValue.readUtf8String(textLength),
      text_error: "",
    };
  } catch (error) {
    return { text_utf8: "", text_error: String(error) };
  }
}

function readCStringSafe(pointerValue, limit) {
  return readUtf8PrefixSafe(pointerValue, limit || 512, true);
}

function pointerDistance(endPointer, beginPointer) {
  try {
    if (endPointer === null || beginPointer === null) {
      return null;
    }
    return endPointer.sub(beginPointer).toInt32();
  } catch (_) {
    return null;
  }
}

function readVectorText(base, offset, limit) {
  const begin = readPointerSafe(base, offset);
  const end = readPointerSafe(base, offset + Process.pointerSize);
  const length = pointerDistance(end, begin);
  const result = {
    begin_pointer: begin === null ? null : begin.toString(),
    end_pointer: end === null ? null : end.toString(),
    length,
    text_utf8: "",
    text_error: "",
  };
  if (length === null || length < 0 || length > (limit || 512) || !readable(begin)) {
    result.text_error = "invalid_vector";
    return result;
  }
  const text = readUtf8PrefixSafe(begin, length, false);
  result.text_utf8 = text.text_utf8;
  result.text_error = text.text_error;
  return result;
}

function normalizeHex(value) {
  if (value === null || value === undefined) {
    return "";
  }
  let text = String(value).toLowerCase();
  if (text.indexOf("0x") === 0) {
    text = text.slice(2);
  }
  text = text.replace(/^0+/, "");
  return "0x" + (text || "0");
}

function knownCodeForRequestId(requestId) {
  if (requestId === null || requestId === undefined) {
    return "";
  }
  return codeByRequestId[requestId] || "";
}

function describeAddress(address) {
  const result = { address: address === null ? null : address.toString() };
  if (address === null) {
    return result;
  }
  try {
    const moduleValue = Process.findModuleByAddress(address);
    if (moduleValue !== null) {
      result.module = moduleValue.name;
      result.module_path = moduleValue.path;
      result.module_offset = normalizeHex(address.sub(moduleValue.base).toString());
    }
  } catch (_) {
  }
  try {
    const symbol = DebugSymbol.fromAddress(address);
    result.symbol = symbol === null ? "" : symbol.toString();
  } catch (_) {
  }
  return result;
}

function callerFields(returnAddress) {
  const description = describeAddress(returnAddress);
  return {
    return_address: description.address || null,
    return_module: description.module || "",
    return_module_offset: description.module_offset || null,
    return_symbol: description.symbol || "",
  };
}

function cleanupState() {
  const now = Date.now();
  recentContexts = recentContexts.filter((item) => now - item.updated_ms <= CONTEXT_WINDOW_MS);
  for (const key of Object.keys(requestMetadataByPointer)) {
    if (now - requestMetadataByPointer[key].updated_ms > REQUEST_METADATA_TTL_MS) {
      delete requestMetadataByPointer[key];
    }
  }
}

function createOrReuseContext(code, requestId, stage) {
  cleanupState();
  const now = Date.now();
  const threadId = Process.getCurrentThreadId();
  let context = null;
  for (let index = recentContexts.length - 1; index >= 0; index -= 1) {
    const candidate = recentContexts[index];
    const codeMatches = code && candidate.code && candidate.code === code;
    const requestMatches =
      requestId !== null && candidate.request_id !== null && candidate.request_id === requestId;
    if (candidate.thread_id === threadId && (codeMatches || requestMatches)) {
      context = candidate;
      break;
    }
  }
  if (context === null) {
    context = {
      context_id: nextContextId,
      code: code || "",
      request_id: requestId === undefined ? null : requestId,
      thread_id: threadId,
      created_ms: now,
      updated_ms: now,
      last_stage: stage,
    };
    nextContextId += 1;
    recentContexts.push(context);
  } else {
    if (code) {
      context.code = code;
    }
    if (requestId !== null && requestId !== undefined) {
      context.request_id = requestId;
    }
    context.updated_ms = now;
    context.last_stage = stage;
  }
  return context;
}

function contextForRequest(requestId) {
  cleanupState();
  for (let index = recentContexts.length - 1; index >= 0; index -= 1) {
    if (recentContexts[index].request_id === requestId) {
      return { context: recentContexts[index], basis: "request_id" };
    }
  }
  return { context: null, basis: "none" };
}

function describeReqData(reqData, index) {
  const functionType = readU16Safe(reqData, 0x08);
  const mediaPointer = readPointerSafe(reqData, 0x28);
  const mediaText = readCStringSafe(mediaPointer, 256);
  const mediaFormat = readU8Safe(reqData, 0x40);
  return {
    reqdata_index: index,
    reqdata_pointer: reqData.toString(),
    channel_hex_at_0x00: readU64HexSafe(reqData, 0x00),
    function_type_u16_at_0x08: functionType,
    function_type_name: FUNCTION_TYPE_NAMES[functionType] || "UNKNOWN",
    raw_u16_at_0x0a: readU16Safe(reqData, 0x0a),
    delay_time_i32_at_0x0c: readS32Safe(reqData, 0x0c),
    priority_i32_at_0x10: readS32Safe(reqData, 0x10),
    master_volume_index_i32_at_0x14: readS32Safe(reqData, 0x14),
    media_pointer_at_0x28: mediaPointer === null ? null : mediaPointer.toString(),
    media_name_utf8: mediaText.text_utf8,
    media_name_error: mediaText.text_error,
    media_format_u8_at_0x40: mediaFormat,
    media_format_name: MEDIA_FORMAT_NAMES[mediaFormat] || "UNKNOWN",
    chain_u8_at_0x41: readU8Safe(reqData, 0x41),
    loop_u16_at_0x42: readU16Safe(reqData, 0x42),
    seek_time_u32_at_0x44: readU32Safe(reqData, 0x44),
    own_id_u32_at_0x48: readU32Safe(reqData, 0x48),
    target_id_u32_at_0x4c: readU32Safe(reqData, 0x4c),
    fade_attr_u32_at_0x50: readU32Safe(reqData, 0x50),
    duck_attr_u32_at_0x54: readU32Safe(reqData, 0x54),
  };
}

function describeRequest(requestPointer) {
  const result = {
    request_pointer: requestPointer === null ? null : requestPointer.toString(),
    request_code_name_utf8: "",
    request_code_name_error: "",
    request_flag_u32_at_0x28: null,
    request_flag_u32_at_0x2c: null,
    reqdata_count: null,
    reqdata_rows: [],
  };
  if (requestPointer === null || requestPointer.isNull()) {
    return result;
  }
  const codeName = readVectorText(requestPointer, 0x00, 512);
  result.request_code_name_utf8 = codeName.text_utf8;
  result.request_code_name_error = codeName.text_error;
  result.request_flag_u32_at_0x28 = readU32Safe(requestPointer, 0x28);
  result.request_flag_u32_at_0x2c = readU32Safe(requestPointer, 0x2c);

  const begin = readPointerSafe(requestPointer, 0x40);
  const end = readPointerSafe(requestPointer, 0x48);
  const byteLength = pointerDistance(end, begin);
  result.reqdata_begin_pointer = begin === null ? null : begin.toString();
  result.reqdata_end_pointer = end === null ? null : end.toString();
  result.reqdata_byte_length = byteLength;
  if (byteLength === null || byteLength < 0 || byteLength % 0x90 !== 0 || !readable(begin)) {
    result.reqdata_error = "invalid_reqdata_vector";
    return result;
  }
  const count = Math.floor(byteLength / 0x90);
  result.reqdata_count = count;
  result.reqdata_truncated = count > MAX_REQDATA_ROWS;
  for (let index = 0; index < Math.min(count, MAX_REQDATA_ROWS); index += 1) {
    result.reqdata_rows.push(describeReqData(begin.add(index * 0x90), index));
  }
  return result;
}

function requestIdsFromDescription(description) {
  const values = [];
  for (const row of description.reqdata_rows || []) {
    const value = row.own_id_u32_at_0x48;
    if (value !== null && value !== undefined && values.indexOf(value) === -1) {
      values.push(value);
    }
  }
  return values;
}

function activePerformForCurrentThread() {
  const key = String(Process.getCurrentThreadId());
  const stack = activePerformStackByThread[key] || [];
  return stack.length > 0 ? stack[stack.length - 1] : null;
}

function activeSoundPlayForCurrentThread() {
  const key = String(Process.getCurrentThreadId());
  const stack = activeSoundPlayStackByThread[key] || [];
  return stack.length > 0 ? stack[stack.length - 1] : null;
}

function cslSoundDataTable(cslMngPointer) {
  const managerKey = cslMngPointer.toString();
  const begin = readPointerSafe(cslMngPointer, CSL_SOUND_DATA_TABLE_BEGIN_OFFSET);
  const end = readPointerSafe(cslMngPointer, CSL_SOUND_DATA_TABLE_END_OFFSET);
  const byteLength = pointerDistance(end, begin);
  const signature = [pointerText(begin), pointerText(end), byteLength].join(":");
  const cached = cslRequestTableCacheByManager[managerKey];
  if (cached && cached.signature === signature) {
    return cached;
  }
  const result = {
    signature,
    valid: false,
    error: "",
    begin_pointer: pointerText(begin),
    end_pointer: pointerText(end),
    byte_length: byteLength,
    row_count: null,
    by_id: {},
  };
  if (
    begin === null
    || end === null
    || byteLength === null
    || byteLength < 0
    || byteLength % CSL_SOUND_DATA_ENTRY_STRIDE !== 0
    || !readableSpan(begin, byteLength)
  ) {
    result.error = "sound data table failed bounded layout validation";
    cslRequestTableCacheByManager[managerKey] = result;
    return result;
  }
  const rowCount = Math.floor(byteLength / CSL_SOUND_DATA_ENTRY_STRIDE);
  result.row_count = rowCount;
  if (rowCount > MAX_CSL_SOUND_DATA_TABLE_ROWS) {
    result.error = "sound data table exceeds defensive row cap";
    cslRequestTableCacheByManager[managerKey] = result;
    return result;
  }
  for (let index = 0; index < rowCount; index += 1) {
    const entry = begin.add(index * CSL_SOUND_DATA_ENTRY_STRIDE);
    const soundResourceId = readU16Safe(entry, CSL_SOUND_DATA_ENTRY_ID_OFFSET);
    const slotIndex = readU16Safe(entry, CSL_SOUND_DATA_ENTRY_SLOT_OFFSET);
    if (soundResourceId === null || slotIndex === null) {
      result.error = "sound data table row read failed";
      cslRequestTableCacheByManager[managerKey] = result;
      return result;
    }
    const idKey = String(soundResourceId);
    if (Object.prototype.hasOwnProperty.call(result.by_id, idKey)) {
      result.error = "sound data table contains duplicate resource ID";
      cslRequestTableCacheByManager[managerKey] = result;
      return result;
    }
    result.by_id[idKey] = {
      row_index: index,
      sound_resource_id_u16: soundResourceId,
      slot_index_u16: slotIndex,
      sound_data_pointer: entry,
    };
  }
  result.valid = true;
  cslRequestTableCacheByManager[managerKey] = result;
  return result;
}

function cslPendingEnqueueKey(cslMngPointer, slotIndex, soundDataPointer) {
  return [cslMngPointer.toString(), slotIndex, soundDataPointer.toString()].join(":");
}

function cslPendingSlotKey(cslMngPointer, slotIndex) {
  return [cslMngPointer.toString(), slotIndex].join(":");
}

function describeReqOrder(playerPointer, reqOrderPointer) {
  const functionType = readU32Safe(reqOrderPointer, 0x50);
  const playerChannelRaw = readS32Safe(playerPointer, 0x42a4);
  return {
    player_pointer: playerPointer.toString(),
    player_channel_i32: playerChannelRaw === null ? null : playerChannelRaw - 1,
    req_order_pointer: reqOrderPointer.toString(),
    function_type_u32_at_0x50: functionType,
    function_type_name: FUNCTION_TYPE_NAMES[functionType] || "UNKNOWN",
    raw_u32_at_0x24: readU32Safe(reqOrderPointer, 0x24),
    raw_u32_at_0x28: readU32Safe(reqOrderPointer, 0x28),
    raw_u32_at_0x58: readU32Safe(reqOrderPointer, 0x58),
    raw_u32_at_0x5c: readU32Safe(reqOrderPointer, 0x5c),
    raw_u32_at_0x94: readU32Safe(reqOrderPointer, 0x94),
    raw_u32_at_0x98: readU32Safe(reqOrderPointer, 0x98),
    raw_u8_at_0xd8: readU8Safe(reqOrderPointer, 0xd8),
    raw_u8_at_0xd9: readU8Safe(reqOrderPointer, 0xd9),
  };
}

function findExport(symbol) {
  try {
    return Module.findGlobalExportByName(symbol);
  } catch (_) {
    return null;
  }
}

function verifyGameProcIdentity() {
  const anchorAddress = findExport(SDGM_ACCESSOR_SYMBOL);
  if (anchorAddress === null) {
    gameProcIdentityStatus = {
      status: "anchor_symbol_unavailable",
      anchor_symbol: SDGM_ACCESSOR_SYMBOL,
      expected_anchor_offset: SDGM_ACCESSOR_EXPECTED_OFFSET,
      read_only_verification: true,
    };
    emit("sound_logic_game_proc_identity_unavailable", gameProcIdentityStatus);
    return;
  }

  const anchorLocation = describeAddress(anchorAddress);
  const expectedAnchorOffset = parseInt(SDGM_ACCESSOR_EXPECTED_OFFSET, 16);
  const derivedBase = anchorAddress.sub(expectedAnchorOffset);
  const containerNameMatches =
    anchorLocation.module === STATIC_REFERENCE.arm64_apk_module;
  const containerPathMatches = String(anchorLocation.module_path || "").endsWith(
    "/" + STATIC_REFERENCE.arm64_apk_module
  );
  const reportedOffsetMatches =
    normalizeHex(anchorLocation.module_offset) === normalizeHex(SDGM_ACCESSOR_EXPECTED_OFFSET);
  let reportedBaseMatchesDerived = false;
  let reportedContainerBase = null;
  try {
    const moduleValue = Process.findModuleByAddress(anchorAddress);
    reportedContainerBase = moduleValue === null ? null : moduleValue.base.toString();
    reportedBaseMatchesDerived = moduleValue !== null && moduleValue.base.equals(derivedBase);
  } catch (_) {
    reportedBaseMatchesDerived = false;
  }

  const elfHeader = {
    magic_u32_le_at_0x00: readU32Safe(derivedBase, 0x00),
    class_u8_at_0x04: readU8Safe(derivedBase, 0x04),
    data_encoding_u8_at_0x05: readU8Safe(derivedBase, 0x05),
    machine_u16_at_0x12: readU16Safe(derivedBase, 0x12),
  };
  const elfHeaderMatches =
    elfHeader.magic_u32_le_at_0x00 === 0x464c457f
    && elfHeader.class_u8_at_0x04 === 2
    && elfHeader.data_encoding_u8_at_0x05 === 1
    && elfHeader.machine_u16_at_0x12 === 183;

  const identityKeys = [
    "kndCalLotCcDirEnd",
    "kndCalLotRlStart",
    "mstComCbkUpdateGmData",
    "anmBaseDataSetDir",
    "objNmlSndRequestBgmDir",
  ];
  const exportChecks = [];
  let allExportChecksMatch = true;
  for (const key of identityKeys) {
    const spec = SYMBOLS[key];
    const address = findExport(spec.name);
    const location = describeAddress(address);
    const actualOffset = address === null
      ? ""
      : normalizeHex(address.sub(derivedBase).toString());
    const expectedOffset = normalizeHex(spec.expectedOffset);
    const check = {
      hook_key: key,
      symbol: spec.name,
      address: address === null ? null : address.toString(),
      container_module: location.module || "",
      container_path: location.module_path || "",
      actual_derived_elf_offset: actualOffset,
      expected_elf_offset: expectedOffset,
      offset_matches: actualOffset === expectedOffset,
      same_apk_container:
        location.module === anchorLocation.module
        && location.module_path === anchorLocation.module_path,
    };
    if (!check.offset_matches || !check.same_apk_container) {
      allExportChecksMatch = false;
    }
    exportChecks.push(check);
  }

  const mappingMatches =
    containerNameMatches
    && containerPathMatches
    && reportedOffsetMatches
    && reportedBaseMatchesDerived
    && elfHeaderMatches
    && allExportChecksMatch;
  gameProcDerivedBase = mappingMatches ? derivedBase : null;
  gameProcIdentityStatus = {
    status: mappingMatches ? "ready" : "apk_backed_mapping_mismatch",
    mapping_kind: "apk_backed_uncompressed_elf",
    logical_library_name: STATIC_REFERENCE.game_proc_logical_name,
    container_module: anchorLocation.module || "",
    container_path: anchorLocation.module_path || "",
    expected_container_module: STATIC_REFERENCE.arm64_apk_module,
    container_name_matches: containerNameMatches,
    container_path_matches: containerPathMatches,
    reported_container_base: reportedContainerBase,
    derived_elf_base: derivedBase.toString(),
    reported_base_matches_derived: reportedBaseMatchesDerived,
    anchor_symbol: SDGM_ACCESSOR_SYMBOL,
    anchor_address: anchorAddress.toString(),
    actual_anchor_derived_elf_offset: normalizeHex(
      anchorAddress.sub(derivedBase).toString()
    ),
    expected_anchor_offset: normalizeHex(SDGM_ACCESSOR_EXPECTED_OFFSET),
    reported_anchor_module_offset: normalizeHex(anchorLocation.module_offset),
    anchor_offset_matches: reportedOffsetMatches,
    elf_header: elfHeader,
    elf_header_matches_aarch64: elfHeaderMatches,
    export_checks: exportChecks,
    all_export_checks_match: allExportChecksMatch,
    installed_container_identity_required_from_host: true,
    expected_container_sha256: STATIC_REFERENCE.arm64_apk_sha256,
    expected_container_size_bytes: STATIC_REFERENCE.arm64_apk_size_bytes,
    bound_apk_entry: {
      path: STATIC_REFERENCE.game_proc_apk_entry,
      compression_method: STATIC_REFERENCE.game_proc_apk_entry_compression_method,
      crc32: STATIC_REFERENCE.game_proc_apk_entry_crc32,
      local_header_offset: STATIC_REFERENCE.game_proc_apk_entry_header_offset,
      data_offset: STATIC_REFERENCE.game_proc_apk_entry_data_offset,
      compressed_size_bytes: STATIC_REFERENCE.game_proc_size_bytes,
      uncompressed_size_bytes: STATIC_REFERENCE.game_proc_size_bytes,
      expected_uncompressed_sha256: STATIC_REFERENCE.game_proc_sha256,
    },
    read_only_verification: true,
  };
  emit(
    gameProcIdentityStatus.status === "ready"
      ? "sound_logic_game_proc_identity_ready"
      : "sound_logic_game_proc_identity_unavailable",
    gameProcIdentityStatus
  );
}

function prepareSdGmDataAccessor() {
  if (gameProcIdentityStatus.status !== "ready") {
    sdGmDataAccessorStatus = {
      status: "game_proc_identity_not_ready",
      symbol: SDGM_ACCESSOR_SYMBOL,
      expected_module_offset: SDGM_ACCESSOR_EXPECTED_OFFSET,
      read_only_accessor: true,
    };
    return;
  }
  const address = findExport(SDGM_ACCESSOR_SYMBOL);
  if (address === null) {
    sdGmDataAccessorStatus = {
      status: "symbol_unavailable",
      symbol: SDGM_ACCESSOR_SYMBOL,
      expected_module_offset: SDGM_ACCESSOR_EXPECTED_OFFSET,
      read_only_accessor: true,
    };
    return;
  }
  const location = describeAddress(address);
  const actualOffset = gameProcDerivedBase === null
    ? ""
    : normalizeHex(address.sub(gameProcDerivedBase).toString());
  const expectedOffset = normalizeHex(SDGM_ACCESSOR_EXPECTED_OFFSET);
  if (
    location.module !== gameProcIdentityStatus.container_module
    || location.module_path !== gameProcIdentityStatus.container_path
    || actualOffset !== expectedOffset
  ) {
    sdGmDataAccessorStatus = {
      status: "static_reference_mismatch",
      symbol: SDGM_ACCESSOR_SYMBOL,
      module: location.module || "",
      module_path: location.module_path || "",
      derived_elf_base: gameProcDerivedBase === null
        ? null
        : gameProcDerivedBase.toString(),
      offset_basis: "known_export_minus_derived_game_proc_elf_base",
      actual_module_offset: actualOffset,
      expected_module_offset: expectedOffset,
      module_offset_matches_static_reference: actualOffset === expectedOffset,
      read_only_accessor: true,
    };
    return;
  }
  try {
    sdGmDataAccessor = new NativeFunction(address, "pointer", []);
    sdGmDataAccessorStatus = {
      status: "ready",
      symbol: SDGM_ACCESSOR_SYMBOL,
      module: location.module,
      module_path: location.module_path,
      derived_elf_base: gameProcDerivedBase.toString(),
      actual_module_offset: actualOffset,
      expected_module_offset: expectedOffset,
      module_offset_matches_static_reference: true,
      read_only_accessor: true,
    };
  } catch (error) {
    sdGmDataAccessor = null;
    sdGmDataAccessorStatus = {
      status: "native_function_error",
      symbol: SDGM_ACCESSOR_SYMBOL,
      actual_module_offset: actualOffset,
      expected_module_offset: expectedOffset,
      read_only_accessor: true,
      error: String(error),
    };
  }
}

function installHook(key, callbacks) {
  const spec = SYMBOLS[key];
  if (spec.requiresGameProcIdentity && gameProcIdentityStatus.status !== "ready") {
    hookStaticMatchByKey[key] = false;
    hookStatusByKey[key] = {
      status: "game_proc_identity_not_ready",
      hook_key: key,
      symbol: spec.name,
      expected_module_offset: normalizeHex(spec.expectedOffset),
      expected_game_proc_sha256: STATIC_REFERENCE.game_proc_sha256,
      game_proc_identity_status: gameProcIdentityStatus.status,
    };
    emit("sound_logic_hook_unavailable", hookStatusByKey[key]);
    return null;
  }
  const address = findExport(spec.name);
  if (address === null) {
    hookStaticMatchByKey[key] = false;
    hookStatusByKey[key] = {
      status: "symbol_unavailable",
      hook_key: key,
      symbol: spec.name,
      expected_module_offset: normalizeHex(spec.expectedOffset),
    };
    emit("sound_logic_hook_unavailable", hookStatusByKey[key]);
    return null;
  }
  const location = describeAddress(address);
  const actualOffset = spec.requiresGameProcIdentity
    ? gameProcDerivedBase === null
      ? ""
      : normalizeHex(address.sub(gameProcDerivedBase).toString())
    : normalizeHex(location.module_offset);
  const expectedOffset = normalizeHex(spec.expectedOffset);
  const identityModuleMatches = !spec.requiresGameProcIdentity || (
    location.module === gameProcIdentityStatus.container_module
    && location.module_path === gameProcIdentityStatus.container_path
    && gameProcDerivedBase !== null
  );
  hookStaticMatchByKey[key] = actualOffset === expectedOffset && identityModuleMatches;
  if (actualOffset !== expectedOffset || !identityModuleMatches) {
    hookStatusByKey[key] = {
      status: "static_reference_mismatch",
      hook_key: key,
      symbol: spec.name,
      address: address.toString(),
      module: location.module || "",
      module_path: location.module_path || "",
      derived_elf_base: spec.requiresGameProcIdentity
        ? gameProcDerivedBase === null ? null : gameProcDerivedBase.toString()
        : null,
      offset_basis: spec.requiresGameProcIdentity
        ? "known_export_minus_derived_game_proc_elf_base"
        : "frida_reported_module_base",
      actual_module_offset: actualOffset,
      expected_module_offset: expectedOffset,
      module_offset_matches_static_reference: actualOffset === expectedOffset,
      module_identity_matches_static_reference: identityModuleMatches,
    };
    emit("sound_logic_hook_unavailable", hookStatusByKey[key]);
    return null;
  }
  try {
    const listener = Interceptor.attach(address, callbacks);
    hookStatusByKey[key] = {
      status: "installed",
      hook_key: key,
      symbol: spec.name,
      address: address.toString(),
      module: location.module || "",
      module_path: location.module_path || "",
      derived_elf_base: spec.requiresGameProcIdentity
        ? gameProcDerivedBase.toString()
        : null,
      offset_basis: spec.requiresGameProcIdentity
        ? "known_export_minus_derived_game_proc_elf_base"
        : "frida_reported_module_base",
      actual_module_offset: actualOffset,
      expected_module_offset: expectedOffset,
      module_offset_matches_static_reference: true,
      module_identity_matches_static_reference: identityModuleMatches,
    };
    emit("sound_logic_hook_installed", hookStatusByKey[key]);
    return listener;
  } catch (error) {
    hookStaticMatchByKey[key] = false;
    hookStatusByKey[key] = {
      status: "attach_error",
      hook_key: key,
      symbol: spec.name,
      address: address.toString(),
      error: String(error),
    };
    emit("sound_logic_hook_attach_error", hookStatusByKey[key]);
    return null;
  }
}

function prepareSoundPackPreGateHook() {
  const spec = SYMBOLS.soundMngChangeVolume;
  const address = findExport(spec.name);
  if (address === null) {
    soundPackPreGateStatus = {
      status: "unavailable",
      symbol: spec.name,
      expected_module_offset: normalizeHex(spec.expectedOffset),
    };
    emit("sound_logic_sound_pack_pre_gate_unavailable", soundPackPreGateStatus);
    return;
  }
  const location = describeAddress(address);
  const actualOffset = normalizeHex(location.module_offset);
  const expectedOffset = normalizeHex(spec.expectedOffset);
  const moduleValue = Process.findModuleByAddress(address);
  if (moduleValue === null || actualOffset !== expectedOffset) {
    soundPackPreGateStatus = {
      status: "static_reference_mismatch",
      symbol: spec.name,
      actual_module_offset: actualOffset,
      expected_module_offset: expectedOffset,
    };
    emit("sound_logic_sound_pack_pre_gate_unavailable", soundPackPreGateStatus);
    return;
  }
  const table = moduleValue.base.add(SOUND_PACK_GATE_TABLE_OFFSET);
  const tableBytes = SOUND_PACK_GATE_ENTRY_COUNT * 4;
  if (!readableSpan(table, tableBytes)) {
    soundPackPreGateStatus = {
      status: "gate_table_unreadable",
      table_address: table.toString(),
      table_byte_length: tableBytes,
    };
    emit("sound_logic_sound_pack_pre_gate_unavailable", soundPackPreGateStatus);
    return;
  }
  const ids = [];
  const seen = {};
  let strictlyIncreasing = true;
  for (let index = 0; index < SOUND_PACK_GATE_ENTRY_COUNT; index += 1) {
    const soundId = table.add(index * 4).readU32();
    if (index > 0 && soundId <= ids[index - 1]) {
      strictlyIncreasing = false;
    }
    ids.push(soundId);
    seen[String(soundId)] = true;
  }
  const keyChecks = Object.keys(SOUND_PACK_REFERENCE_KEYS).map((rawIndex) => {
    const index = Number(rawIndex);
    const expected = SOUND_PACK_REFERENCE_KEYS[index];
    return { index, expected, actual: ids[index], matches: ids[index] === expected };
  });
  if (!strictlyIncreasing || !keyChecks.every((row) => row.matches)) {
    soundPackPreGateStatus = {
      status: "gate_table_reference_mismatch",
      strictly_increasing_unique: strictlyIncreasing,
      key_checks: keyChecks,
    };
    emit("sound_logic_sound_pack_pre_gate_unavailable", soundPackPreGateStatus);
    return;
  }
  soundPackGateIds = seen;
  try {
    Interceptor.attach(address, {
      onEnter(args) {
        const soundId = toI32(args[1]);
        if (soundId === null || soundPackGateIds[String(soundId)] !== true) {
          return;
        }
        const volumeIndex = toI32(args[2]);
        const categoryMap = readPointerSafe(
          moduleValue.base.add(SOUND_PACK_CATEGORY_MAP_POINTER_SLOT_OFFSET),
          0
        );
        const addonInstance = readPointerSafe(
          moduleValue.base.add(SOUND_PACK_ADDON_POINTER_SLOT_OFFSET),
          0
        );
        const volumeClass = categoryMap === null || !readable(categoryMap)
          ? null
          : readU8Safe(categoryMap, soundId);
        const classVolume = volumeClass === null || volumeClass > 2
          ? null
          : readU16Safe(args[0], volumeClass * 2);
        const indexedVolume = volumeIndex === null || volumeIndex < 0 || volumeIndex > 63
          ? null
          : readU16Safe(
              args[0],
              SOUND_MNG_INDEXED_VOLUME_BASE_OFFSET + volumeIndex * 2
            );
        const masterVolume = readU16Safe(args[0], SOUND_MNG_MASTER_VOLUME_OFFSET);
        const activeAddon = addonInstance === null || !readable(addonInstance)
          ? null
          : readU32Safe(addonInstance, SOUND_PACK_ACTIVE_ADDON_OFFSET);
        const stageVolume = classVolume === null || indexedVolume === null
          ? null
          : Math.floor((classVolume * indexedVolume) / 100);
        const authorizedFinalVolume = stageVolume === null || masterVolume === null
          ? null
          : Math.floor((stageVolume * masterVolume) / 100);
        const caller = callerFields(this.returnAddress);
        const callerOffset = caller.return_module_offset || "";
        const directRequestCall =
          callerOffset === "0x425f160" || callerOffset === "0x425f31c";
        const signature = [
          activeAddon,
          volumeClass,
          classVolume,
          indexedVolume,
          masterVolume,
          stageVolume,
          authorizedFinalVolume,
        ].join(":");
        const signatureKey = [soundId, volumeIndex, callerOffset].join(":");
        const previousSignature = lastSoundPackPreGateSignatureByKey[signatureKey];
        if (!directRequestCall && previousSignature === signature) {
          return;
        }
        lastSoundPackPreGateSignatureByKey[signatureKey] = signature;
        emit(
          "sound_logic_sound_pack_pre_gate_volume",
          Object.assign(
            {
              sound_mng_pointer: args[0].toString(),
              sound_resource_id_i32: soundId,
              volume_index_i32: volumeIndex,
              sound_pack_gate_member_static: true,
              sound_pack_active_u32: activeAddon,
              volume_class_u8: volumeClass,
              class_volume_u16: classVolume,
              indexed_volume_u16: indexedVolume,
              master_volume_u16: masterVolume,
              pre_gate_stage_volume_i32: stageVolume,
              authorized_final_volume_i32: authorizedFinalVolume,
              current_gate_will_zero: activeAddon === 0,
              reconstruction_complete:
                volumeClass !== null
                && volumeClass <= 2
                && stageVolume !== null
                && authorizedFinalVolume !== null,
              reconstruction_basis:
                "changeVolume_arm64_integer_percent_chain_before_entitlement_zero",
              emission_reason: directRequestCall
                ? "direct_sound_request_call"
                : previousSignature === undefined
                ? "first_observed_volume_control_state"
                : "volume_control_state_changed",
              repeated_unchanged_volume_control_calls_suppressed: true,
            },
            caller
          )
        );
      },
    });
    soundPackPreGateStatus = {
      status: "ready",
      symbol: spec.name,
      address: address.toString(),
      module: moduleValue.name,
      module_path: moduleValue.path,
      actual_module_offset: actualOffset,
      expected_module_offset: expectedOffset,
      module_offset_matches_static_reference: true,
      gate_table_address: table.toString(),
      gate_table_offset: "0x" + SOUND_PACK_GATE_TABLE_OFFSET.toString(16),
      gate_table_entry_count: ids.length,
      gate_table_strictly_increasing_unique: strictlyIncreasing,
      gate_table_key_checks: keyChecks,
      read_only_observer: true,
      repeated_unchanged_volume_control_calls_suppressed: true,
    };
    emit("sound_logic_sound_pack_pre_gate_ready", soundPackPreGateStatus);
  } catch (error) {
    soundPackPreGateStatus = {
      status: "attach_error",
      symbol: spec.name,
      error: String(error),
    };
    emit("sound_logic_sound_pack_pre_gate_unavailable", soundPackPreGateStatus);
  }
}

function installActiveSoundAccessor(key, returnType) {
  const spec = SYMBOLS[key];
  const address = findExport(spec.name);
  if (address === null) {
    activeSoundAccessorStatus[key] = {
      status: "unavailable",
      symbol: spec.name,
      expected_module_offset: normalizeHex(spec.expectedOffset),
    };
    emit("sound_logic_accessor_unavailable", Object.assign({ accessor_key: key }, activeSoundAccessorStatus[key]));
    return;
  }
  const location = describeAddress(address);
  const actualOffset = normalizeHex(location.module_offset);
  const expectedOffset = normalizeHex(spec.expectedOffset);
  const offsetMatches = actualOffset === expectedOffset;
  const status = {
    status: offsetMatches ? "ready" : "static_reference_mismatch",
    symbol: spec.name,
    address: address.toString(),
    module: location.module || "",
    module_path: location.module_path || "",
    actual_module_offset: actualOffset,
    expected_module_offset: expectedOffset,
    module_offset_matches_static_reference: offsetMatches,
    return_type: returnType,
  };
  activeSoundAccessorStatus[key] = status;
  if (!offsetMatches) {
    emit("sound_logic_accessor_unavailable", Object.assign({ accessor_key: key }, status));
    return;
  }
  try {
    activeSoundAccessors[key] = new NativeFunction(address, returnType, ["pointer", "int"]);
    emit("sound_logic_accessor_ready", Object.assign({ accessor_key: key }, status));
  } catch (error) {
    delete activeSoundAccessors[key];
    status.status = "error";
    status.error = String(error);
    emit("sound_logic_accessor_error", Object.assign({ accessor_key: key }, status));
  }
}

function allActiveSoundAccessorsReady() {
  return Object.keys(ACTIVE_SOUND_ACCESSOR_TYPES).every(
    (key) => typeof activeSoundAccessors[key] === "function"
  );
}

function rememberCslMngPointer(pointerValue, sourceHookKey) {
  if (
    pointerValue === null
    || pointerValue.isNull()
    || hookStaticMatchByKey[sourceHookKey] !== true
    || !readableSpan(pointerValue, 0xb8)
  ) {
    return false;
  }
  const changed = lastCslMngPointer === null || !lastCslMngPointer.equals(pointerValue);
  lastCslMngPointer = pointerValue;
  lastCslMngPointerSource = sourceHookKey;
  lastCslMngPointerObservedMs = Date.now();
  if (changed) {
    emit("sound_logic_csl_mng_pointer_observed", {
      csl_mng_pointer: pointerValue.toString(),
      observation_source_hook: sourceHookKey,
      static_layout_allowed: true,
    });
  }
  return true;
}

function prepareCslCalcSnapshotEntry() {
  const spec = SYMBOLS.cslMngCalc;
  const address = findExport(spec.name);
  if (address === null) {
    hookStaticMatchByKey.cslMngCalc = false;
    cslCalcSnapshotStatus = {
      status: "unavailable",
      symbol: spec.name,
      expected_module_offset: normalizeHex(spec.expectedOffset),
    };
    emit("sound_logic_snapshot_entry_unavailable", cslCalcSnapshotStatus);
    return;
  }
  const location = describeAddress(address);
  const actualOffset = normalizeHex(location.module_offset);
  const expectedOffset = normalizeHex(spec.expectedOffset);
  const offsetMatches = actualOffset === expectedOffset;
  hookStaticMatchByKey.cslMngCalc = offsetMatches;
  cslCalcSnapshotStatus = {
    status: offsetMatches ? "ready" : "static_reference_mismatch",
    symbol: spec.name,
    address: address.toString(),
    module: location.module || "",
    module_path: location.module_path || "",
    actual_module_offset: actualOffset,
    expected_module_offset: expectedOffset,
    module_offset_matches_static_reference: offsetMatches,
    execution_policy: "attach_for_one_rpc_then_snapshot_on_calc_thread_and_detach",
  };
  if (offsetMatches) {
    cslCalcSnapshotAddress = address;
    emit("sound_logic_snapshot_entry_ready", cslCalcSnapshotStatus);
  } else {
    emit("sound_logic_snapshot_entry_unavailable", cslCalcSnapshotStatus);
  }
}

function requestActiveSoundSnapshot(label) {
  if (activeSnapshotRequestInFlight) {
    return Promise.resolve({
      schema: "magireco-csl-active-sound-snapshot-v1",
      label: String(label || "manual_rpc").slice(0, 128),
      captured_unix_ms: Date.now(),
      available: false,
      error: "another active-sound snapshot request is already in flight",
    });
  }
  if (cslCalcSnapshotAddress === null || hookStaticMatchByKey.cslMngCalc !== true) {
    return Promise.resolve({
      schema: "magireco-csl-active-sound-snapshot-v1",
      label: String(label || "manual_rpc").slice(0, 128),
      captured_unix_ms: Date.now(),
      available: false,
      error: "version-checked CSLMng::Calc snapshot entry is unavailable",
      snapshot_entry_status: cslCalcSnapshotStatus,
    });
  }

  activeSnapshotRequestInFlight = true;
  return new Promise((resolve) => {
    let listener = null;
    let timeoutId = null;
    let completed = false;

    function finish(result) {
      if (completed) {
        return;
      }
      completed = true;
      if (timeoutId !== null) {
        clearTimeout(timeoutId);
      }
      setImmediate(function () {
        let detachError = "";
        if (listener !== null) {
          try {
            listener.detach();
          } catch (error) {
            detachError = String(error);
          }
        }
        activeSnapshotRequestInFlight = false;
        result.snapshot_hook_detached = detachError === "";
        result.snapshot_hook_detach_error = detachError;
        emit("sound_logic_snapshot_hook_detached", {
          label: result.label,
          detach_error: detachError,
        });
        resolve(result);
      });
    }

    try {
      listener = Interceptor.attach(cslCalcSnapshotAddress, {
        onEnter(args) {
          if (completed) {
            return;
          }
          const pointerObserved = rememberCslMngPointer(args[0], "cslMngCalc");
          if (!pointerObserved) {
            finish({
              schema: "magireco-csl-active-sound-snapshot-v1",
              label: String(label || "manual_rpc").slice(0, 128),
              captured_unix_ms: Date.now(),
              available: false,
              error: "CSLMng::Calc receiver failed version/readability validation",
            });
            return;
          }
          try {
            finish(snapshotActiveSoundState(label, args[0], "cslMngCalc_on_enter"));
          } catch (error) {
            finish({
              schema: "magireco-csl-active-sound-snapshot-v1",
              label: String(label || "manual_rpc").slice(0, 128),
              captured_unix_ms: Date.now(),
              available: false,
              error: "active-sound snapshot raised: " + String(error),
            });
          }
        },
      });
      emit("sound_logic_snapshot_hook_installed", {
        label: String(label || "manual_rpc").slice(0, 128),
        symbol: SYMBOLS.cslMngCalc.name,
        address: cslCalcSnapshotAddress.toString(),
        timeout_ms: ACTIVE_SNAPSHOT_WAIT_TIMEOUT_MS,
      });
      timeoutId = setTimeout(function () {
        finish({
          schema: "magireco-csl-active-sound-snapshot-v1",
          label: String(label || "manual_rpc").slice(0, 128),
          captured_unix_ms: Date.now(),
          available: false,
          error: "timed out waiting for the next CSLMng::Calc call",
          timeout_ms: ACTIVE_SNAPSHOT_WAIT_TIMEOUT_MS,
        });
      }, ACTIVE_SNAPSHOT_WAIT_TIMEOUT_MS);
    } catch (error) {
      finish({
        schema: "magireco-csl-active-sound-snapshot-v1",
        label: String(label || "manual_rpc").slice(0, 128),
        captured_unix_ms: Date.now(),
        available: false,
        error: "could not attach one-shot CSLMng::Calc snapshot hook: " + String(error),
      });
    }
  });
}

function callActiveSoundAccessor(key, cslMngPointer, argument, errors) {
  const callback = activeSoundAccessors[key];
  if (typeof callback !== "function") {
    errors.push(key + ":unavailable");
    return null;
  }
  try {
    const value = callback(cslMngPointer, argument);
    if (typeof value === "number" && !Number.isFinite(value)) {
      errors.push(key + ":non_finite");
      return null;
    }
    return value;
  } catch (error) {
    errors.push(key + ":" + String(error));
    return null;
  }
}

function snapshotActiveSoundState(label, cslMngPointer, executionSource) {
  const result = {
    schema: "magireco-csl-active-sound-snapshot-v1",
    label: String(label || "manual_rpc").slice(0, 128),
    captured_unix_ms: Date.now(),
    available: false,
    csl_mng_pointer: pointerText(cslMngPointer),
    csl_mng_pointer_source: lastCslMngPointerSource,
    csl_mng_pointer_observed_unix_ms: lastCslMngPointerObservedMs,
    snapshot_execution_source: executionSource,
    snapshot_runs_on_csl_calc_thread: executionSource === "cslMngCalc_on_enter",
    vector_begin_offset: CSL_ACTIVE_VECTOR_BEGIN_OFFSET,
    vector_end_offset: CSL_ACTIVE_VECTOR_END_OFFSET,
    active_slot_stride: CSL_ACTIVE_SLOT_STRIDE,
    maximum_captured_slots: MAX_ACTIVE_SOUND_SLOTS,
    capture_cap_is_declared_game_limit: false,
    snapshot_atomic: false,
    classification_rule: "active_transport_state_only_csl_resource_table_channel_zero_is_not_bgm_proof",
    static_reference: STATIC_REFERENCE,
    accessor_status: activeSoundAccessorStatus,
    active_rows: [],
  };
  if (cslMngPointer === null || !readableSpan(cslMngPointer, 0xb8)) {
    result.error = "CSLMng pointer is not safely readable";
    return result;
  }
  if (!allActiveSoundAccessorsReady()) {
    result.error = "one or more version-checked CSLMng accessors are unavailable";
    return result;
  }

  const begin = readPointerSafe(cslMngPointer, CSL_ACTIVE_VECTOR_BEGIN_OFFSET);
  const end = readPointerSafe(cslMngPointer, CSL_ACTIVE_VECTOR_END_OFFSET);
  result.active_vector_begin_pointer = pointerText(begin);
  result.active_vector_end_pointer = pointerText(end);
  if (begin === null || end === null) {
    result.error = "active slot vector pointer read failed";
    return result;
  }
  if (begin.isNull() && end.isNull()) {
    result.available = true;
    result.active_vector_byte_length = 0;
    result.declared_slot_count = 0;
    result.captured_slot_count = 0;
    result.truncated = false;
    result.occupied_slot_count = 0;
    result.playing_slot_count = 0;
    result.pending_slot_count = 0;
    result.paused_slot_count = 0;
    return result;
  }
  const byteLength = pointerDistance(end, begin);
  result.active_vector_byte_length = byteLength;
  if (
    byteLength === null
    || byteLength < 0
    || byteLength % CSL_ACTIVE_SLOT_STRIDE !== 0
    || !readableSpan(begin, byteLength)
  ) {
    result.error = "active slot vector failed bounded layout validation";
    return result;
  }

  const declaredCount = Math.floor(byteLength / CSL_ACTIVE_SLOT_STRIDE);
  const capturedCount = Math.min(declaredCount, MAX_ACTIVE_SOUND_SLOTS);
  result.declared_slot_count = declaredCount;
  result.captured_slot_count = capturedCount;
  result.truncated = declaredCount > capturedCount;
  for (let index = 0; index < capturedCount; index += 1) {
    const slot = begin.add(index * CSL_ACTIVE_SLOT_STRIDE);
    const soundPointer = readPointerSafe(slot, 0x00);
    const pendingSoundData = readPointerSafe(slot, 0x20);
    const chainData = readPointerSafe(slot, 0x28);
    const getterErrors = [];
    const soundId = callActiveSoundAccessor(
      "cslMngSndGetId",
      cslMngPointer,
      index,
      getterErrors
    );
    const occupied =
      (soundPointer !== null && !soundPointer.isNull())
      || (pendingSoundData !== null && !pendingSoundData.isNull())
      || (typeof soundId === "number" && soundId >= 0);
    if (!occupied) {
      continue;
    }
    const channel = typeof soundId === "number" && soundId >= 0
      ? callActiveSoundAccessor(
        "cslMngSndGetChannel",
        cslMngPointer,
        soundId,
        getterErrors
      )
      : null;
    const pauseFlag = callActiveSoundAccessor(
      "cslMngSndGetPauseF",
      cslMngPointer,
      index,
      getterErrors
    );
    const pendingRequestPresent = pendingSoundData !== null && !pendingSoundData.isNull();
    const transportPlaying =
      !pendingRequestPresent && typeof soundId === "number" && soundId >= 0;
    const transportState = pendingRequestPresent
      ? "pending_request"
      : pauseFlag === 1
      ? "paused"
      : transportPlaying
      ? "playing"
      : "occupied_nonplaying_or_stopping";
    const row = {
      slot_index: index,
      slot_pointer: slot.toString(),
      sound_object_pointer_at_0x00: pointerText(soundPointer),
      slot_mute_u8_at_0x0c: readU8Safe(slot, 0x0c),
      slot_volume_u32_at_0x10: readU32Safe(slot, 0x10),
      slot_time_or_sample_u32_at_0x14: readU32Safe(slot, 0x14),
      slot_loop_state_u32_at_0x18: readU32Safe(slot, 0x18),
      pending_sound_data_pointer_at_0x20: pointerText(pendingSoundData),
      pending_sound_data_id_u16_at_0x00:
        pendingSoundData === null || pendingSoundData.isNull()
          ? null
          : readU16Safe(pendingSoundData, 0x00),
      chain_data_pointer_at_0x28: pointerText(chainData),
      pending_request_present: pendingRequestPresent,
      transport_state: transportState,
      transport_playing_proven: transportState === "playing",
      transport_paused: pauseFlag === 1,
      sound_id_i32: soundId,
      csl_resource_table_channel_i32: channel,
      sound_time_seconds: callActiveSoundAccessor(
        "cslMngSndGetTime",
        cslMngPointer,
        index,
        getterErrors
      ),
      sound_loop_num_i32: callActiveSoundAccessor(
        "cslMngSndGetLoopNum",
        cslMngPointer,
        index,
        getterErrors
      ),
      sound_priority_i32: callActiveSoundAccessor(
        "cslMngSndGetPriority",
        cslMngPointer,
        index,
        getterErrors
      ),
      sound_loop_flag_i32: callActiveSoundAccessor(
        "cslMngSndGetLoopF",
        cslMngPointer,
        index,
        getterErrors
      ),
      sound_wait_flag_i32: callActiveSoundAccessor(
        "cslMngSndGetWaitF",
        cslMngPointer,
        index,
        getterErrors
      ),
      sound_pause_flag_i32: pauseFlag,
      csl_resource_table_channel_zero_candidate_only:
        transportPlaying && channel === 0,
      bgm_semantics_proven: false,
      getter_errors: getterErrors,
    };
    result.active_rows.push(row);
  }
  result.available = true;
  result.occupied_slot_count = result.active_rows.length;
  result.playing_slot_count = result.active_rows.filter(
    (row) => row.transport_state === "playing"
  ).length;
  result.pending_slot_count = result.active_rows.filter(
    (row) => row.transport_state === "pending_request"
  ).length;
  result.paused_slot_count = result.active_rows.filter(
    (row) => row.transport_state === "paused"
  ).length;
  return result;
}

function installCodeNameLookupHook() {
  installHook("codeName2ReqId", {
    onEnter(args) {
      const text = readCStringSafe(args[1], 512);
      this.code = text.text_utf8;
      this.codeError = text.text_error;
      this.codePointer = args[1].toString();
      this.caller = callerFields(this.returnAddress);
      // `InvocationContext.context` is a Frida-owned, read-only CPU context.
      // Keep probe metadata under a distinct property so natural code lookups
      // do not raise `TypeError: no setter for property`.
      this.soundLogicContext = createOrReuseContext(
        this.code,
        null,
        "code_name_lookup_enter"
      );
    },
    onLeave(retval) {
      const requestId = toI32(retval);
      if (requestId !== null && this.code) {
        codeByRequestId[requestId] = this.code;
      }
      this.soundLogicContext = createOrReuseContext(
        this.code,
        requestId,
        "code_name_lookup_leave"
      );
      emit(
        "sound_logic_code_name_to_request_id",
        Object.assign(
          {
            code_string: this.code,
            code_text_error: this.codeError,
            code_pointer: this.codePointer,
            request_id_i32: requestId,
            context_id: this.soundLogicContext.context_id,
          },
          this.caller
        )
      );
    },
  });
}

function installZgSndReqIdHook() {
  installHook("zgSndReqId", {
    onEnter(args) {
      const requestId = toI32(args[0]);
      const contextResult = contextForRequest(requestId);
      const code = contextResult.context
        ? contextResult.context.code
        : knownCodeForRequestId(requestId);
      const context = createOrReuseContext(code, requestId, "zg_snd_req_id");
      emit(
        "sound_logic_zg_snd_req_id",
        Object.assign(
          {
            request_id_i32: requestId,
            request_arg1_i32: toI32(args[1]),
            request_arg2_i32: toI32(args[2]),
            context_id: context.context_id,
            context_code: context.code,
          },
          callerFields(this.returnAddress)
        )
      );
    },
  });
}

function installGetRequestHook() {
  installHook("getRequest", {
    onEnter(args) {
      this.requestId = toI32(args[1]);
      this.outputPointer = args[2];
      this.caller = callerFields(this.returnAddress);
    },
    onLeave(retval) {
      const success = toI32(retval);
      const description = describeRequest(this.outputPointer);
      if (description.request_code_name_utf8) {
        codeByRequestId[this.requestId] = description.request_code_name_utf8;
      }
      const existing = contextForRequest(this.requestId);
      const context = createOrReuseContext(
        existing.context
          ? existing.context.code
          : knownCodeForRequestId(this.requestId) || description.request_code_name_utf8,
        this.requestId,
        "request_ctrl_get_request"
      );
      requestMetadataByPointer[this.outputPointer.toString()] = {
        request_id: this.requestId,
        context_id: context.context_id,
        code: context.code,
        updated_ms: Date.now(),
      };
      emit(
        "sound_logic_request_ctrl_get_request",
        Object.assign(
          {
            request_id_i32: this.requestId,
            get_request_success_i32: success,
            context_id: context.context_id,
            context_code: context.code,
            request: description,
          },
          this.caller
        )
      );
    },
  });
}

function installSetRequestListHook() {
  installHook("setRequestList", {
    onEnter(args) {
      cleanupState();
      const requestPointer = args[1];
      const description = describeRequest(requestPointer);
      const remembered = requestMetadataByPointer[requestPointer.toString()] || null;
      const derivedRequestIds = requestIdsFromDescription(description);
      const requestId = derivedRequestIds.length === 1
        ? derivedRequestIds[0]
        : remembered
        ? remembered.request_id
        : null;
      const exactCode = description.request_code_name_utf8
        || knownCodeForRequestId(requestId)
        || (remembered ? remembered.code : "");
      if (requestId !== null && exactCode) {
        codeByRequestId[requestId] = exactCode;
      }
      const context = createOrReuseContext(exactCode, requestId, "request_ctrl_set_request_list");
      requestMetadataByPointer[requestPointer.toString()] = {
        request_id: requestId,
        context_id: context.context_id,
        code: exactCode,
        updated_ms: Date.now(),
      };
      emit(
        "sound_logic_request_ctrl_set_request_list",
        Object.assign(
          {
            request_id_i32: requestId,
            derived_request_ids: derivedRequestIds,
            request_id_association_basis: derivedRequestIds.length === 1
              ? "reqdata_own_id"
              : remembered
              ? "same_request_pointer_previous_get"
              : "none",
            context_id: context.context_id,
            context_code: context.code,
            request: description,
          },
          callerFields(this.returnAddress)
        )
      );
    },
  });
}

function installPerformRequestHook() {
  installHook("performRequest", {
    onEnter(args) {
      const order = describeReqOrder(args[0], args[2]);
      const orderRequestId = order.raw_u32_at_0x28;
      const performInvocationId = nextPerformInvocationId;
      nextPerformInvocationId += 1;
      const fields = Object.assign(
        {
          perform_invocation_id: performInvocationId,
          request_ctrl_pointer: args[1].toString(),
          perform_arg3_bool: (toU32(args[3]) & 1) !== 0,
          order_request_id_u32: orderRequestId,
          order_code: knownCodeForRequestId(orderRequestId),
          order_association_basis: "req_order_u32_at_0x28_static_join_key",
          order,
        },
        callerFields(this.returnAddress)
      );
      const threadKey = String(Process.getCurrentThreadId());
      const stack = activePerformStackByThread[threadKey] || [];
      stack.push(fields);
      activePerformStackByThread[threadKey] = stack;
      this.performThreadKey = threadKey;
      emit("sound_logic_player_perform_request", fields);
    },
    onLeave() {
      const stack = activePerformStackByThread[this.performThreadKey] || [];
      if (stack.length > 0) {
        stack.pop();
      }
      if (stack.length === 0) {
        delete activePerformStackByThread[this.performThreadKey];
      }
    },
  });
}

function installSoundMngPlayRequestHook() {
  installHook("soundMngSndPlayReq", {
    onEnter(args) {
      const soundResourceId = toI32(args[1]);
      const activePerform = activePerformForCurrentThread();
      const playRequestCallId = nextSoundPlayCallId;
      nextSoundPlayCallId += 1;
      this.fields = Object.assign(
        {
          play_request_call_id: playRequestCallId,
          sound_mng_pointer: args[0].toString(),
          sound_resource_id_i32: soundResourceId,
          play_index_or_bank_i32: toI32(args[2]),
          request_arg3_i32: toI32(args[3]),
          perform_order_request_id_u32: activePerform
            ? activePerform.order_request_id_u32
            : null,
          perform_invocation_id: activePerform
            ? activePerform.perform_invocation_id
            : null,
          perform_order_code: activePerform ? activePerform.order_code : "",
          perform_function_type_name: activePerform
            ? activePerform.order.function_type_name
            : "",
          perform_player_channel_i32: activePerform
            ? activePerform.order.player_channel_i32
            : null,
          perform_association_basis: activePerform
            ? "nested_within_perform_request"
            : "none",
        },
        callerFields(this.returnAddress)
      );
      const threadKey = String(Process.getCurrentThreadId());
      const stack = activeSoundPlayStackByThread[threadKey] || [];
      stack.push(this.fields);
      activeSoundPlayStackByThread[threadKey] = stack;
      this.soundPlayThreadKey = threadKey;
      emit("sound_logic_sound_mng_snd_play_req_enter", this.fields);
    },
    onLeave(retval) {
      emit(
        "sound_logic_sound_mng_snd_play_req_leave",
        Object.assign({}, this.fields, { return_i32: toI32(retval) })
      );
      const stack = activeSoundPlayStackByThread[this.soundPlayThreadKey] || [];
      if (stack.length > 0) {
        stack.pop();
      }
      if (stack.length === 0) {
        delete activeSoundPlayStackByThread[this.soundPlayThreadKey];
      }
    },
  });
}

function installCslSndReqHook() {
  installHook("cslMngSndReq", {
    onEnter(args) {
      rememberCslMngPointer(args[0], "cslMngSndReq");
      const activeSoundPlay = activeSoundPlayForCurrentThread();
      this.cslMngPointer = args[0];
      this.requestedSoundResourceId = toI32(args[1]);
      this.requestMode = toI32(args[2]);
      this.caller = callerFields(this.returnAddress);
      this.enqueueId = nextCslEnqueueId;
      nextCslEnqueueId += 1;
      this.activeSoundPlay = activeSoundPlay;
    },
    onLeave() {
      const table = cslSoundDataTable(this.cslMngPointer);
      const entry = table.valid && this.requestMode !== 1
        ? table.by_id[String(this.requestedSoundResourceId)] || null
        : null;
      let pendingPointer = null;
      let slotPointer = null;
      let enqueueCommitted = false;
      let replacedEnqueueId = null;
      let enqueueKey = "";
      if (entry !== null) {
        const activeBegin = readPointerSafe(
          this.cslMngPointer,
          CSL_ACTIVE_VECTOR_BEGIN_OFFSET
        );
        const activeEnd = readPointerSafe(
          this.cslMngPointer,
          CSL_ACTIVE_VECTOR_END_OFFSET
        );
        const activeByteLength = pointerDistance(activeEnd, activeBegin);
        const activeRowCount = activeByteLength !== null
          && activeByteLength >= 0
          && activeByteLength % CSL_ACTIVE_SLOT_STRIDE === 0
          ? Math.floor(activeByteLength / CSL_ACTIVE_SLOT_STRIDE)
          : -1;
        if (
          activeBegin !== null
          && activeEnd !== null
          && activeRowCount >= 0
          && entry.slot_index_u16 < activeRowCount
          && readableSpan(activeBegin, activeByteLength)
        ) {
          slotPointer = activeBegin.add(
            entry.slot_index_u16 * CSL_ACTIVE_SLOT_STRIDE
          );
          pendingPointer = readPointerSafe(
            slotPointer,
            CSL_PENDING_SOUND_DATA_SLOT_OFFSET
          );
          enqueueCommitted = pendingPointer !== null
            && pendingPointer.equals(entry.sound_data_pointer);
        }
      }
      const activeSoundPlay = this.activeSoundPlay;
      const fields = Object.assign(
        {
          csl_enqueue_id: this.enqueueId,
          csl_mng_pointer: this.cslMngPointer.toString(),
          requested_sound_resource_id_i32: this.requestedSoundResourceId,
          request_mode_i32: this.requestMode,
          callback_remap_possible: this.requestMode === 1,
          request_table_valid: table.valid,
          request_table_error: table.error,
          request_table_begin_pointer: table.begin_pointer,
          request_table_end_pointer: table.end_pointer,
          request_table_byte_length: table.byte_length,
          request_table_row_count: table.row_count,
          request_table_row_index: entry ? entry.row_index : null,
          request_table_entry_sound_resource_id_u16: entry
            ? entry.sound_resource_id_u16
            : null,
          request_table_entry_slot_index_u16: entry ? entry.slot_index_u16 : null,
          sound_data_pointer: entry ? entry.sound_data_pointer.toString() : null,
          active_slot_pointer: pointerText(slotPointer),
          pending_sound_data_pointer_after_request: pointerText(pendingPointer),
          enqueue_committed: enqueueCommitted,
          play_request_call_id: activeSoundPlay
            ? activeSoundPlay.play_request_call_id
            : null,
          perform_invocation_id: activeSoundPlay
            ? activeSoundPlay.perform_invocation_id
            : null,
          perform_order_request_id_u32: activeSoundPlay
            ? activeSoundPlay.perform_order_request_id_u32
            : null,
          perform_order_code: activeSoundPlay ? activeSoundPlay.perform_order_code : "",
          causal_association_basis: activeSoundPlay
            ? "nested_within_sound_mng_snd_play_req"
            : "none",
        },
        this.caller
      );
      if (enqueueCommitted) {
        enqueueKey = cslPendingEnqueueKey(
          this.cslMngPointer,
          entry.slot_index_u16,
          entry.sound_data_pointer
        );
        const slotKey = cslPendingSlotKey(
          this.cslMngPointer,
          entry.slot_index_u16
        );
        const previousEnqueueKey = pendingCslEnqueueKeyBySlot[slotKey] || "";
        const replaced = previousEnqueueKey
          ? pendingCslEnqueueByKey[previousEnqueueKey] || null
          : null;
        replacedEnqueueId = replaced ? replaced.csl_enqueue_id : null;
        if (previousEnqueueKey) {
          delete pendingCslEnqueueByKey[previousEnqueueKey];
        }
        pendingCslEnqueueByKey[enqueueKey] = Object.assign({}, fields);
        pendingCslEnqueueKeyBySlot[slotKey] = enqueueKey;
      }
      fields.pending_enqueue_key = enqueueKey;
      fields.replaced_pending_csl_enqueue_id = replacedEnqueueId;
      emit("sound_logic_csl_mng_snd_req_enqueue", fields);
    },
  });
}

function describeSoundData(soundData) {
  if (soundData === null || soundData.isNull()) {
    return { sound_data_pointer: null };
  }
  return {
    sound_data_pointer: soundData.toString(),
    final_sound_id_u16_at_0x02: readU16Safe(soundData, 0x02),
    raw_u32_at_0x00: readU32Safe(soundData, 0x00),
    raw_u32_at_0x04: readU32Safe(soundData, 0x04),
  };
}

function installCslPlayStartHook() {
  installHook("cslMngPlayStart", {
    onEnter(args) {
      rememberCslMngPointer(args[0], "cslMngPlayStart");
      const sound = describeSoundData(args[1]);
      const playIndex = toI32(args[2]);
      const enqueueKey = playIndex === null || args[1].isNull()
        ? ""
        : cslPendingEnqueueKey(args[0], playIndex, args[1]);
      const pendingEnqueue = enqueueKey
        ? pendingCslEnqueueByKey[enqueueKey] || null
        : null;
      if (pendingEnqueue !== null) {
        delete pendingCslEnqueueByKey[enqueueKey];
        const slotKey = cslPendingSlotKey(args[0], playIndex);
        if (pendingCslEnqueueKeyBySlot[slotKey] === enqueueKey) {
          delete pendingCslEnqueueKeyBySlot[slotKey];
        }
      }
      const activeSoundPlay = activeSoundPlayForCurrentThread();
      emit(
        "sound_logic_csl_mng_play_start",
        Object.assign(
          {
            csl_mng_pointer: args[0].toString(),
            play_index_i32: playIndex,
            sound,
            causal_csl_enqueue_id: pendingEnqueue
              ? pendingEnqueue.csl_enqueue_id
              : null,
            causal_play_request_call_id: pendingEnqueue
              ? pendingEnqueue.play_request_call_id
              : activeSoundPlay
              ? activeSoundPlay.play_request_call_id
              : null,
            causal_sound_resource_id_i32: pendingEnqueue
              ? pendingEnqueue.requested_sound_resource_id_i32
              : activeSoundPlay
              ? activeSoundPlay.sound_resource_id_i32
              : null,
            causal_perform_invocation_id: pendingEnqueue
              ? pendingEnqueue.perform_invocation_id
              : activeSoundPlay
              ? activeSoundPlay.perform_invocation_id
              : null,
            causal_perform_order_request_id_u32: pendingEnqueue
              ? pendingEnqueue.perform_order_request_id_u32
              : activeSoundPlay
              ? activeSoundPlay.perform_order_request_id_u32
              : null,
            causal_perform_order_code: pendingEnqueue
              ? pendingEnqueue.perform_order_code
              : activeSoundPlay
              ? activeSoundPlay.perform_order_code
              : "",
            causal_request_table_row_index: pendingEnqueue
              ? pendingEnqueue.request_table_row_index
              : null,
            causal_association_basis: pendingEnqueue
              ? "same_csl_slot_and_pending_sound_data_pointer_written_by_snd_req_then_consumed_by_calc"
              : activeSoundPlay
              ? "nested_within_sound_mng_snd_play_req"
              : "none_static_sound_id_join_required",
          },
          callerFields(this.returnAddress)
        )
      );
    },
  });
}

function currentSdGmDataPointer() {
  if (sdGmDataAccessor === null || sdGmDataAccessorStatus.status !== "ready") {
    return null;
  }
  try {
    return sdGmDataAccessor();
  } catch (_) {
    return null;
  }
}

function snapshotSdGmData(pointerValue) {
  return {
    current_kind_u16_at_0x13da: readU16Safe(pointerValue, 0x13da),
    next_kind_u16_at_0x13dc: readU16Safe(pointerValue, 0x13dc),
    current_no_u16_at_0x13de: readU16Safe(pointerValue, 0x13de),
    next_no_u16_at_0x13e0: readU16Safe(pointerValue, 0x13e0),
    restore_state_u16_at_0x1472: readU16Safe(pointerValue, 0x1472),
    saved_kind_u16_at_0x1474: readU16Safe(pointerValue, 0x1474),
    saved_no_u16_at_0x149a: readU16Safe(pointerValue, 0x149a),
  };
}

function snapshotMstComCbkCommit(pointerValue) {
  return {
    committed_kind_u16_at_0x0a72: readU16Safe(pointerValue, 0xa72),
    committed_no_u16_at_0x0a76: readU16Safe(pointerValue, 0xa76),
  };
}

function snapshotObjNmlBgm(pointerValue) {
  const cachedCodePointer = readPointerSafe(pointerValue, 0x800);
  const cachedCode = readCStringSafe(cachedCodePointer, 64);
  return {
    direction_kind_u16_at_0x00ca: readU16Safe(pointerValue, 0xca),
    direction_no_u16_at_0x011a: readU16Safe(pointerValue, 0x11a),
    cached_code_pointer_at_0x0800: pointerText(cachedCodePointer),
    cached_code_string_at_0x0800: cachedCode.text_utf8,
    cached_code_text_error_at_0x0800: cachedCode.text_error,
  };
}

function changedSnapshotFields(entry, leave) {
  const keys = {};
  for (const key of Object.keys(entry || {})) {
    keys[key] = true;
  }
  for (const key of Object.keys(leave || {})) {
    keys[key] = true;
  }
  return Object.keys(keys).filter(
    (key) => JSON.stringify((entry || {})[key]) !== JSON.stringify((leave || {})[key])
  );
}

function beginBgmUpstreamWindow(label) {
  bgmUpstreamWindowEpoch += 1;
  bgmUpstreamWindowActive = true;
  bgmUpstreamWindowLabel = String(label || "").slice(0, 128);
  bgmUpstreamWindowEventCount = 0;
  bgmUpstreamWindowDroppedCount = 0;
  bgmUpstreamWindowOverflowEmitted = false;
  bgmUpstreamSignatureByHook = {};
  return {
    schema: "magireco-target-bgm-upstream-window-v1",
    active: true,
    label: bgmUpstreamWindowLabel,
    epoch: bgmUpstreamWindowEpoch,
    emitted_event_count: 0,
    dropped_event_count: 0,
    maximum_emitted_events: MAX_BGM_UPSTREAM_EVENTS_PER_WINDOW,
    read_only_observer: true,
  };
}

function endBgmUpstreamWindow() {
  const result = {
    schema: "magireco-target-bgm-upstream-window-v1",
    active: false,
    label: bgmUpstreamWindowLabel,
    epoch: bgmUpstreamWindowEpoch,
    emitted_event_count: bgmUpstreamWindowEventCount,
    dropped_event_count: bgmUpstreamWindowDroppedCount,
    maximum_emitted_events: MAX_BGM_UPSTREAM_EVENTS_PER_WINDOW,
    read_only_observer: true,
  };
  bgmUpstreamWindowActive = false;
  return result;
}

function emitBgmUpstream(hookKey, kind, fields, signature, everyCall, statePartition) {
  if (!bgmUpstreamWindowActive) {
    return;
  }
  const signatureKey = statePartition === undefined
    ? hookKey
    : hookKey + "@" + String(statePartition);
  const previousSignature = bgmUpstreamSignatureByHook[signatureKey];
  const emissionReason = everyCall
    ? "every_entry_leave_pair"
    : previousSignature === undefined
    ? "first_observation_in_window"
    : previousSignature !== signature
    ? "state_changed_in_window"
    : "unchanged_suppressed";
  if (emissionReason === "unchanged_suppressed") {
    return;
  }
  bgmUpstreamSignatureByHook[signatureKey] = signature;
  if (bgmUpstreamWindowEventCount >= MAX_BGM_UPSTREAM_EVENTS_PER_WINDOW) {
    bgmUpstreamWindowDroppedCount += 1;
    if (!bgmUpstreamWindowOverflowEmitted) {
      bgmUpstreamWindowOverflowEmitted = true;
      emit("sound_logic_bgm_upstream_trace_overflow", {
        bgm_upstream_window_label: bgmUpstreamWindowLabel,
        bgm_upstream_window_epoch: bgmUpstreamWindowEpoch,
        maximum_emitted_events: MAX_BGM_UPSTREAM_EVENTS_PER_WINDOW,
        dropped_event_count: bgmUpstreamWindowDroppedCount,
        overflow_policy: "fail_attempt",
      });
    }
    return;
  }
  bgmUpstreamWindowEventCount += 1;
  emit(
    kind,
    Object.assign(
      {
        bgm_upstream_hook: hookKey,
        bgm_upstream_window_label: bgmUpstreamWindowLabel,
        bgm_upstream_window_epoch: bgmUpstreamWindowEpoch,
        bgm_upstream_window_event_index: bgmUpstreamWindowEventCount,
        bgm_upstream_state_partition: signatureKey,
        emission_reason: emissionReason,
      },
      fields
    )
  );
}

function installBgmUpstreamHooks() {
  const installLotteryHook = function (hookKey, eventKind) {
    installHook(hookKey, {
      onEnter() {
        this.captureBgmUpstream = bgmUpstreamWindowActive;
        if (!this.captureBgmUpstream) {
          return;
        }
        this.bgmUpstreamCallId = nextBgmUpstreamCallId;
        nextBgmUpstreamCallId += 1;
        this.sdgmEntryPointer = currentSdGmDataPointer();
        this.sdgmEntry = snapshotSdGmData(this.sdgmEntryPointer);
      },
      onLeave() {
        if (!this.captureBgmUpstream) {
          return;
        }
        const leavePointer = currentSdGmDataPointer();
        const leave = snapshotSdGmData(leavePointer);
        const fields = {
          bgm_upstream_call_id: this.bgmUpstreamCallId,
          sdgm_pointer_entry: pointerText(this.sdgmEntryPointer),
          sdgm_pointer_leave: pointerText(leavePointer),
          entry: this.sdgmEntry,
          leave,
          changed_fields: changedSnapshotFields(this.sdgmEntry, leave),
        };
        emitBgmUpstream(
          hookKey,
          eventKind,
          fields,
          JSON.stringify(fields),
          true
        );
      },
    });
  };

  installLotteryHook(
    "kndCalLotCcDirEnd",
    "sound_logic_bgm_upstream_kndcal_cc_dir_end"
  );
  installLotteryHook(
    "kndCalLotRlStart",
    "sound_logic_bgm_upstream_kndcal_rl_start"
  );

  installHook("mstComCbkUpdateGmData", {
    onEnter(args) {
      this.captureBgmUpstream = bgmUpstreamWindowActive;
      this.mstComCbkPointer = args[0];
      if (this.captureBgmUpstream) {
        this.bgmUpstreamCallId = nextBgmUpstreamCallId;
        nextBgmUpstreamCallId += 1;
      }
    },
    onLeave() {
      if (!this.captureBgmUpstream) {
        return;
      }
      const committed = snapshotMstComCbkCommit(this.mstComCbkPointer);
      const fields = {
        bgm_upstream_call_id: this.bgmUpstreamCallId,
        mstcomcbk_pointer: pointerText(this.mstComCbkPointer),
        committed,
      };
      emitBgmUpstream(
        "mstComCbkUpdateGmData",
        "sound_logic_bgm_upstream_update_gm_data_commit",
        fields,
        JSON.stringify(committed),
        false,
        pointerText(this.mstComCbkPointer)
      );
    },
  });

  installHook("anmBaseDataSetDir", {
    onEnter(args) {
      this.captureBgmUpstream = bgmUpstreamWindowActive;
      this.objNmlPointer = args[0];
      if (this.captureBgmUpstream) {
        this.bgmUpstreamCallId = nextBgmUpstreamCallId;
        nextBgmUpstreamCallId += 1;
      }
    },
    onLeave() {
      if (!this.captureBgmUpstream) {
        return;
      }
      const committed = snapshotObjNmlBgm(this.objNmlPointer);
      const fields = {
        bgm_upstream_call_id: this.bgmUpstreamCallId,
        obj_nml_pointer: pointerText(this.objNmlPointer),
        committed,
      };
      emitBgmUpstream(
        "anmBaseDataSetDir",
        "sound_logic_bgm_upstream_data_set_dir_commit",
        fields,
        JSON.stringify(committed),
        false,
        pointerText(this.objNmlPointer)
      );
    },
  });

  installHook("objNmlSndRequestBgmDir", {
    onEnter(args) {
      this.captureBgmUpstream = bgmUpstreamWindowActive;
      this.objNmlPointer = args[0];
      if (!this.captureBgmUpstream) {
        return;
      }
      this.bgmUpstreamCallId = nextBgmUpstreamCallId;
      nextBgmUpstreamCallId += 1;
      this.entry = snapshotObjNmlBgm(this.objNmlPointer);
    },
    onLeave() {
      if (!this.captureBgmUpstream) {
        return;
      }
      const leave = snapshotObjNmlBgm(this.objNmlPointer);
      const fields = {
        bgm_upstream_call_id: this.bgmUpstreamCallId,
        obj_nml_pointer: pointerText(this.objNmlPointer),
        entry: this.entry,
        leave,
        changed_fields: changedSnapshotFields(this.entry, leave),
      };
      emitBgmUpstream(
        "objNmlSndRequestBgmDir",
        "sound_logic_bgm_upstream_bgm_dir_request",
        fields,
        JSON.stringify({ entry: this.entry, leave }),
        false,
        pointerText(this.objNmlPointer)
      );
    },
  });
}

setImmediate(function () {
  emit("sound_logic_probe_start", {
    architecture: Process.arch,
    platform: Process.platform,
    pointer_size: Process.pointerSize,
    static_reference: STATIC_REFERENCE,
    capture_scope: {
      code_lookups: "all",
      request_ids: "all",
      request_metadata: "all_bounded_to_8_reqdata_rows",
      perform_orders: "all",
      sound_play_requests: "all_metadata_only",
      sound_pack_pre_gate_volume: "gate_table_members_only_read_only_reconstruction",
      csl_request_enqueue: "bounded_named_table_and_pending_slot_fields_only",
      csl_play_start: "all_metadata_only",
      target_bgm_upstream: "named_fields_only_explicit_attempt_window",
      temporal_context_is_causal: false,
      synchronous_nested_invocation_ids_are_causal: true,
    },
    constraints: {
      pcm_dump: false,
      compressed_media_dump: false,
      full_backtrace: false,
      arbitrary_memory_window_dump: false,
    },
  });

  if (Process.arch !== "arm64" || Process.pointerSize !== 8) {
    emit("sound_logic_abi_mismatch", {
      expected_architecture: "arm64",
      expected_pointer_size: 8,
      actual_architecture: Process.arch,
      actual_pointer_size: Process.pointerSize,
    });
    return;
  }

  verifyGameProcIdentity();
  prepareSdGmDataAccessor();

  for (const key of Object.keys(ACTIVE_SOUND_ACCESSOR_TYPES)) {
    installActiveSoundAccessor(key, ACTIVE_SOUND_ACCESSOR_TYPES[key]);
  }

  installCodeNameLookupHook();
  installZgSndReqIdHook();
  installGetRequestHook();
  installSetRequestListHook();
  installPerformRequestHook();
  installSoundMngPlayRequestHook();
  installCslSndReqHook();
  prepareSoundPackPreGateHook();
  prepareCslCalcSnapshotEntry();
  installCslPlayStartHook();
  installBgmUpstreamHooks();

  emit("sound_logic_probe_ready", {
    installed_hook_event_count: eventCountByKind.sound_logic_hook_installed || 0,
    unavailable_hook_event_count: eventCountByKind.sound_logic_hook_unavailable || 0,
    attach_error_event_count: eventCountByKind.sound_logic_hook_attach_error || 0,
    hook_status: hookStatusByKey,
    outer_bgm_snapshot_accessors_ready: allActiveSoundAccessorsReady(),
    outer_bgm_snapshot_accessor_status: activeSoundAccessorStatus,
    outer_bgm_snapshot_calc_entry_status: cslCalcSnapshotStatus,
    outer_bgm_snapshot_policy: "bounded_active_transport_state_not_semantic_bgm_classification",
    sound_pack_pre_gate_status: soundPackPreGateStatus,
    game_proc_identity_status: gameProcIdentityStatus,
    bgm_upstream_sdgm_accessor_status: sdGmDataAccessorStatus,
    bgm_upstream_field_schema: BGM_UPSTREAM_FIELD_SCHEMA,
    bgm_upstream_window_rpc: {
      schema: "magireco-target-bgm-upstream-window-v1",
      begin_export: "beginbgmupstreamattempt",
      end_export: "endbgmupstreamattempt",
      status_export: "bgmupstreamstatus",
      read_only_observer: true,
    },
    capture_scope: {
      code_lookups: "all",
      request_ids: "all",
      request_metadata: "all_bounded_to_8_reqdata_rows",
      perform_orders: "all",
      sound_play_requests: "all_metadata_only",
      sound_pack_pre_gate_volume: "gate_table_members_only_read_only_reconstruction",
      csl_request_enqueue: "bounded_named_table_and_pending_slot_fields_only",
      csl_play_start: "all_metadata_only",
      target_bgm_upstream: "named_fields_only_explicit_attempt_window",
      temporal_context_is_causal: false,
      synchronous_nested_invocation_ids_are_causal: true,
    },
  });
});

rpc.exports = {
  status() {
    cleanupState();
    return {
      event_count_by_kind: eventCountByKind,
      recent_context_count: recentContexts.length,
      remembered_request_pointer_count: Object.keys(requestMetadataByPointer).length,
      runtime_request_code_mapping_count: Object.keys(codeByRequestId).length,
      active_perform_thread_count: Object.keys(activePerformStackByThread).length,
      active_sound_play_thread_count: Object.keys(activeSoundPlayStackByThread).length,
      capture_scope: "all_sound_logic_metadata",
      active_sound_accessors_ready: allActiveSoundAccessorsReady(),
      csl_mng_pointer: pointerText(lastCslMngPointer),
      csl_mng_pointer_source: lastCslMngPointerSource,
      sound_pack_pre_gate_status: soundPackPreGateStatus,
      game_proc_identity_status: gameProcIdentityStatus,
      bgm_upstream_sdgm_accessor_status: sdGmDataAccessorStatus,
      bgm_upstream_window: {
        schema: "magireco-target-bgm-upstream-window-v1",
        active: bgmUpstreamWindowActive,
        label: bgmUpstreamWindowLabel,
        epoch: bgmUpstreamWindowEpoch,
        emitted_event_count: bgmUpstreamWindowEventCount,
        dropped_event_count: bgmUpstreamWindowDroppedCount,
        maximum_emitted_events: MAX_BGM_UPSTREAM_EVENTS_PER_WINDOW,
        read_only_observer: true,
      },
    };
  },
  outerbgmsnapshot(label) {
    return requestActiveSoundSnapshot(label);
  },
  beginbgmupstreamattempt(label) {
    return beginBgmUpstreamWindow(label);
  },
  endbgmupstreamattempt() {
    return endBgmUpstreamWindow();
  },
  bgmupstreamstatus() {
    return {
      schema: "magireco-target-bgm-upstream-window-v1",
      active: bgmUpstreamWindowActive,
      label: bgmUpstreamWindowLabel,
      epoch: bgmUpstreamWindowEpoch,
      emitted_event_count: bgmUpstreamWindowEventCount,
      dropped_event_count: bgmUpstreamWindowDroppedCount,
      maximum_emitted_events: MAX_BGM_UPSTREAM_EVENTS_PER_WINDOW,
      read_only_observer: true,
    };
  },
};
