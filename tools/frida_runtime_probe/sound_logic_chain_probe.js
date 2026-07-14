"use strict";

// Low-noise sound request/control observer.
//
// This probe follows metadata only.  It intentionally does not dump PCM,
// compressed media, arbitrary memory windows, or full backtraces.  It records
// all request/order/play metadata so later joins can use exact request and sound
// IDs instead of temporal or visual guesses.

const STATIC_REFERENCE = {
  game_proc_sha256: "5A0AE3CE7F25B89A3B9A13D11BF36AAA1DE04FACEB612357FA04F42426F17EBF",
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
  cslMngPlayStart: {
    name: "_ZN6CSLMng9PlayStartEP11SSound_Datai",
    expectedOffset: "0x12fa9c",
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
let hookStaticMatchByKey = {};
let activeSoundAccessors = {};
let activeSoundAccessorStatus = {};
let lastCslMngPointer = null;
let lastCslMngPointerSource = "";
let lastCslMngPointerObservedMs = null;
let cslCalcSnapshotAddress = null;
let cslCalcSnapshotStatus = { status: "not_initialized" };
let activeSnapshotRequestInFlight = false;

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

function installHook(key, callbacks) {
  const spec = SYMBOLS[key];
  const address = findExport(spec.name);
  if (address === null) {
    hookStaticMatchByKey[key] = false;
    emit("sound_logic_hook_unavailable", { hook_key: key, symbol: spec.name });
    return null;
  }
  const location = describeAddress(address);
  const actualOffset = normalizeHex(location.module_offset);
  const expectedOffset = normalizeHex(spec.expectedOffset);
  hookStaticMatchByKey[key] = actualOffset === expectedOffset;
  try {
    const listener = Interceptor.attach(address, callbacks);
    emit("sound_logic_hook_installed", {
      hook_key: key,
      symbol: spec.name,
      address: address.toString(),
      module: location.module || "",
      module_path: location.module_path || "",
      actual_module_offset: actualOffset,
      expected_module_offset: expectedOffset,
      module_offset_matches_static_reference: actualOffset === expectedOffset,
    });
    return listener;
  } catch (error) {
    hookStaticMatchByKey[key] = false;
    emit("sound_logic_hook_attach_error", {
      hook_key: key,
      symbol: spec.name,
      address: address.toString(),
      error: String(error),
    });
    return null;
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
      const fields = Object.assign(
        {
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
      this.fields = Object.assign(
        {
          sound_mng_pointer: args[0].toString(),
          sound_resource_id_i32: soundResourceId,
          play_index_or_bank_i32: toI32(args[2]),
          request_arg3_i32: toI32(args[3]),
          perform_order_request_id_u32: activePerform
            ? activePerform.order_request_id_u32
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
      emit("sound_logic_sound_mng_snd_play_req_enter", this.fields);
    },
    onLeave(retval) {
      emit(
        "sound_logic_sound_mng_snd_play_req_leave",
        Object.assign({}, this.fields, { return_i32: toI32(retval) })
      );
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
      emit(
        "sound_logic_csl_mng_play_start",
        Object.assign(
          {
            csl_mng_pointer: args[0].toString(),
            play_index_i32: toI32(args[2]),
            sound,
            causal_request_context: null,
            causal_association_basis: "none_static_sound_id_join_required",
          },
          callerFields(this.returnAddress)
        )
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
      csl_play_start: "all_metadata_only",
      temporal_context_is_causal: false,
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

  for (const key of Object.keys(ACTIVE_SOUND_ACCESSOR_TYPES)) {
    installActiveSoundAccessor(key, ACTIVE_SOUND_ACCESSOR_TYPES[key]);
  }

  installCodeNameLookupHook();
  installZgSndReqIdHook();
  installGetRequestHook();
  installSetRequestListHook();
  installPerformRequestHook();
  installSoundMngPlayRequestHook();
  prepareCslCalcSnapshotEntry();
  installCslPlayStartHook();

  emit("sound_logic_probe_ready", {
    installed_hook_event_count: eventCountByKind.sound_logic_hook_installed || 0,
    unavailable_hook_event_count: eventCountByKind.sound_logic_hook_unavailable || 0,
    attach_error_event_count: eventCountByKind.sound_logic_hook_attach_error || 0,
    outer_bgm_snapshot_accessors_ready: allActiveSoundAccessorsReady(),
    outer_bgm_snapshot_accessor_status: activeSoundAccessorStatus,
    outer_bgm_snapshot_calc_entry_status: cslCalcSnapshotStatus,
    outer_bgm_snapshot_policy: "bounded_active_transport_state_not_semantic_bgm_classification",
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
      capture_scope: "all_sound_logic_metadata",
      active_sound_accessors_ready: allActiveSoundAccessorsReady(),
      csl_mng_pointer: pointerText(lastCslMngPointer),
      csl_mng_pointer_source: lastCslMngPointerSource,
    };
  },
  outerbgmsnapshot(label) {
    return requestActiveSoundSnapshot(label);
  },
};
