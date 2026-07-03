"use strict";

const moduleName = "libAMAIN.so";
const gameProcModuleName = "libGameProc.so";
const maxCStringBytes = 2048;

const symbols = {
  csndMngSndReq: "_ZN7CSndMng6SndReqEii",
  cslMngSndReq: "_ZN6CSLMng6SndReqEii",
  cslMngPlayStart: "_ZN6CSLMng9PlayStartEP11SSound_Datai",
  cslSoundCreate: "_ZN8CSLSound6CreateEv",
  cslSoundSndPlay: "_ZN8CSLSound7SndPlayEP11SSound_Data",
  cslSoundCallback: "_ZN8CSLSound8CallbackEPKPK30SLAndroidSimpleBufferQueueItf_PS_",
  cslSoundEnqueueBuffer: "_ZN8CSLSound13EnqueueBufferEv",
  cslQueueEnqueue: "_ZN27CSLAndroidSimpleBufferQueue7EnqueueEPKvj",
  cslQueueClear: "_ZN27CSLAndroidSimpleBufferQueue5ClearEv",
  cslQueueRegisterCallback:
    "_ZN27CSLAndroidSimpleBufferQueue16RegisterCallbackEPFvPKPK30SLAndroidSimpleBufferQueueItf_PvES4_",
};

const cslSoundQueueOffset = 0x70;
const soundDataSoundIdOffset = 0x2;
const maxDumpChunks = 2000;
const maxDumpTotalBytes = 96 * 1024 * 1024;
// Gameplay BGM/effect chunks can exceed 2 MiB.  Keep the total dump cap fixed
// but allow a single focused chunk, such as code 814 / sound id 287, to be
// captured for listening verification.
const maxBytesPerChunk = 0x800000;
const previewBytes = 0x80;
const maxHighLevelEmitsPerKind = 1000;
const highLevelEmitLimitsByKind = {
  // C_AnmBase::fnDataSetDir_DIR can fire hundreds of times in a short idle
  // window.  Keep enough rows to survive a full force-scan capture without
  // losing the later non-zero SP Story selector values.
  anm_base_data_set_dir_enter: 20000,
  anm_base_data_set_dir_leave: 20000,
};

let dumpedChunks = 0;
let dumpedBytes = 0;
let enqueueCallCount = 0;
let playCallCount = 0;
let callbackCallCount = 0;
const activeSoundByThread = {};
const activeEnqueueByThread = {};
const activePlayStartByThread = {};
const activeRequestByThread = {};
const soundByCslSound = {};
const soundByQueue = {};
const highLevelEmitCounts = {};
const highLevelSuppressions = {};

function nowMs() {
  return Date.now();
}

function emit(kind, fields, data) {
  send(
    Object.assign(
      {
        kind,
        unix_ms: nowMs(),
        thread_id: Process.getCurrentThreadId(),
      },
      fields || {}
    ),
    data || null
  );
}

function emitHighLevel(kind, fields) {
  const previous = highLevelEmitCounts[kind] || 0;
  highLevelEmitCounts[kind] = previous + 1;
  const limit = highLevelEmitLimitsByKind[kind] || maxHighLevelEmitsPerKind;
  if (previous < limit) {
    emit(
      kind,
      Object.assign(
        {
          high_level_call_count_for_kind: previous + 1,
        },
        fields || {}
      )
    );
    return;
  }
  if (!highLevelSuppressions[kind]) {
    highLevelSuppressions[kind] = true;
    emit("high_level_audio_hook_suppressed", {
      suppressed_kind: kind,
      max_emits_per_kind: limit,
    });
  }
}

function pointerKey(pointerValue) {
  if (pointerValue === null || pointerValue.isNull()) {
    return "0x0";
  }
  return pointerValue.toString();
}

function toU32(pointerValue) {
  try {
    return pointerValue.toUInt32();
  } catch (_) {
    try {
      return pointerValue.toInt32() >>> 0;
    } catch (error) {
      return null;
    }
  }
}

function toI32(pointerValue) {
  try {
    return pointerValue.toInt32();
  } catch (_) {
    return null;
  }
}

function readCStringSafe(pointerValue) {
  if (pointerValue === null || pointerValue.isNull()) {
    return { text_utf8: "", text_length: 0, error: "null pointer" };
  }
  try {
    let length = 0;
    while (length < maxCStringBytes && pointerValue.add(length).readU8() !== 0) {
      length += 1;
    }
    let text = "";
    try {
      text = pointerValue.readCString();
    } catch (_) {
      text = "";
    }
    return {
      text_utf8: text,
      text_length: length,
      error: "",
    };
  } catch (error) {
    return {
      text_utf8: "",
      text_length: 0,
      error: String(error),
    };
  }
}

function readU16Safe(pointerValue, offset) {
  if (pointerValue === null || pointerValue.isNull()) {
    return null;
  }
  try {
    return pointerValue.add(offset).readU16();
  } catch (_) {
    return null;
  }
}

function readU8Safe(pointerValue, offset) {
  if (pointerValue === null || pointerValue.isNull()) {
    return null;
  }
  try {
    return pointerValue.add(offset).readU8();
  } catch (_) {
    return null;
  }
}

function readU32Safe(pointerValue, offset) {
  if (pointerValue === null || pointerValue.isNull()) {
    return null;
  }
  try {
    return pointerValue.add(offset).readU32();
  } catch (_) {
    return null;
  }
}

function readU64HexSafe(pointerValue, offset) {
  if (pointerValue === null || pointerValue.isNull()) {
    return null;
  }
  try {
    const value = pointerValue.add(offset).readU64();
    return "0x" + value.toString(16).padStart(16, "0");
  } catch (_) {
    return null;
  }
}

function readPointerSafe(pointerValue, offset) {
  if (pointerValue === null || pointerValue.isNull()) {
    return ptr(0);
  }
  try {
    return pointerValue.add(offset).readPointer();
  } catch (_) {
    return ptr(0);
  }
}

function readMemoryPreview(pointerValue, size) {
  if (pointerValue === null || pointerValue.isNull()) {
    return { address: "0x0", hex: "", error: "null pointer" };
  }
  try {
    const byteCount = Math.max(0, Math.min(size, previewBytes));
    const bytes = new Uint8Array(pointerValue.readByteArray(byteCount));
    let hex = "";
    let nonZero = 0;
    for (let index = 0; index < bytes.length; index += 1) {
      const value = bytes[index];
      if (value !== 0) {
        nonZero += 1;
      }
      hex += value.toString(16).padStart(2, "0");
    }
    return {
      address: pointerValue.toString(),
      bytes: byteCount,
      nonzero_preview_bytes: nonZero,
      hex,
      error: "",
    };
  } catch (error) {
    return {
      address: pointerValue.toString(),
      bytes: 0,
      nonzero_preview_bytes: 0,
      hex: "",
      error: String(error),
    };
  }
}

function describeSoundData(pointerValue) {
  if (pointerValue === null || pointerValue.isNull()) {
    return { sound_data: "0x0" };
  }
  return {
    sound_data: pointerValue.toString(),
    sound_id_u16_at_0x2: readU16Safe(pointerValue, soundDataSoundIdOffset),
    u32_at_0x0: readU32Safe(pointerValue, 0x0),
    u32_at_0x4: readU32Safe(pointerValue, 0x4),
    u32_at_0x8: readU32Safe(pointerValue, 0x8),
    head: readMemoryPreview(pointerValue, 0x20),
  };
}

function describeCslSound(cslSound) {
  const queue = cslSound.add(cslSoundQueueOffset);
  const storedSoundData = readPointerSafe(cslSound, 0xb0);
  const streamState = readU32Safe(cslSound, 0x538);
  const callbackCount = readU32Safe(cslSound, 0xa8);
  const mapped = soundByCslSound[pointerKey(cslSound)] || {};
  return Object.assign(
    {
      csl_sound: cslSound.toString(),
      queue_object: queue.toString(),
      stored_sound_data_pointer: storedSoundData.toString(),
      stream_state_u32_at_0x538: streamState,
      callback_count_u32_at_0xa8: callbackCount,
    },
    mapped
  );
}

function rememberSound(cslSound, soundData, extra) {
  if (cslSound === null || cslSound.isNull()) {
    return {};
  }
  const queue = cslSound.add(cslSoundQueueOffset);
  const soundDataInfo = describeSoundData(soundData);
  const record = Object.assign(
    {
      csl_sound: cslSound.toString(),
      queue_object: queue.toString(),
    },
    soundDataInfo,
    extra || {}
  );
  soundByCslSound[pointerKey(cslSound)] = record;
  soundByQueue[pointerKey(queue)] = record;
  return record;
}

function findExport(moduleValue, symbol) {
  const address =
    moduleValue !== null
      ? moduleValue.findExportByName(symbol)
      : Module.findGlobalExportByName(symbol);
  if (address === null) {
    emit("hook_missing", { symbol });
    return null;
  }
  return address;
}

function hookRawCall(moduleValue, symbol, kind, argCount, cStringArgIndexes) {
  const address = findExport(moduleValue, symbol);
  if (address === null) {
    return;
  }
  const cStringIndexes = new Set(cStringArgIndexes || []);
  try {
    Interceptor.attach(address, {
      onEnter(args) {
        const fields = {
          symbol,
          address: address.toString(),
        };
        for (let index = 0; index < argCount; index += 1) {
          fields["arg" + index + "_pointer"] = args[index].toString();
          fields["arg" + index + "_i32"] = toI32(args[index]);
          if (cStringIndexes.has(index)) {
            const stringInfo = readCStringSafe(args[index]);
            fields["arg" + index + "_text_utf8"] = stringInfo.text_utf8;
            fields["arg" + index + "_text_length"] = stringInfo.text_length;
            fields["arg" + index + "_text_error"] = stringInfo.error;
          }
        }
        emitHighLevel(kind, fields);
      },
    });
  } catch (error) {
    emit("hook_attach_error", {
      hook_kind: kind,
      symbol,
      address: address.toString(),
      error: String(error),
    });
    return;
  }
  emit("hook_installed", { hook_kind: kind, symbol, address: address.toString() });
}

function hookCStringAndInts(moduleValue, symbol, kind, cStringArgIndex, intArgIndexes) {
  const address = findExport(moduleValue, symbol);
  if (address === null) {
    return;
  }
  try {
    Interceptor.attach(address, {
      onEnter(args) {
        const stringInfo = readCStringSafe(args[cStringArgIndex]);
        const fields = {
          symbol,
          address: address.toString(),
          text_utf8: stringInfo.text_utf8,
          text_length: stringInfo.text_length,
          text_error: stringInfo.error,
          string_arg_index: cStringArgIndex,
        };
        for (const index of intArgIndexes || []) {
          fields["arg" + index + "_i32"] = toI32(args[index]);
          fields["arg" + index + "_pointer"] = args[index].toString();
        }
        emitHighLevel(kind, fields);
      },
    });
  } catch (error) {
    emit("hook_attach_error", {
      hook_kind: kind,
      symbol,
      address: address.toString(),
      error: String(error),
    });
    return;
  }
  emit("hook_installed", { hook_kind: kind, symbol, address: address.toString() });
}

function hookIntCall(moduleValue, symbol, kind, argCount) {
  const address = findExport(moduleValue, symbol);
  if (address === null) {
    return;
  }
  try {
    Interceptor.attach(address, {
      onEnter(args) {
        const fields = {
          symbol,
          address: address.toString(),
        };
        for (let index = 0; index < argCount; index += 1) {
          fields["arg" + index + "_i32"] = toI32(args[index]);
          fields["arg" + index + "_pointer"] = args[index].toString();
        }
        emitHighLevel(kind, fields);
      },
    });
  } catch (error) {
    emit("hook_attach_error", {
      hook_kind: kind,
      symbol,
      address: address.toString(),
      error: String(error),
    });
    return;
  }
  emit("hook_installed", { hook_kind: kind, symbol, address: address.toString() });
}

function describeSpStoryObject(thisPointer) {
  if (thisPointer === null || thisPointer.isNull()) {
    return { sp_story_this: "0x0" };
  }
  return {
    sp_story_this: thisPointer.toString(),
    stage_kind_u16_at_0x318: readU16Safe(thisPointer, 0x318),
    source_story_no_u16_at_0x31a: readU16Safe(thisPointer, 0x31a),
    active_story_no_u16_at_0x34a: readU16Safe(thisPointer, 0x34a),
    dir_no_u16_at_0x34c: readU16Safe(thisPointer, 0x34c),
    base_event_code_hex_at_0x358: readU64HexSafe(thisPointer, 0x358),
    previous_base_event_code_hex_at_0x360: readU64HexSafe(thisPointer, 0x360),
    next_event_code_hex_at_0x368: readU64HexSafe(thisPointer, 0x368),
    previous_next_event_code_hex_at_0x370: readU64HexSafe(thisPointer, 0x370),
  };
}

function describeAnmBaseDirObject(thisPointer) {
  if (thisPointer === null || thisPointer.isNull()) {
    return { anm_base_this: "0x0" };
  }
  return {
    anm_base_this: thisPointer.toString(),
    stage_kind_u16_at_0x318: readU16Safe(thisPointer, 0x318),
    source_story_no_u16_at_0x31a: readU16Safe(thisPointer, 0x31a),
    dir_special_flag_u8_at_0x31c: readU8Safe(thisPointer, 0x31c),
    dir_extra_u16_at_0x31e: readU16Safe(thisPointer, 0x31e),
    dir_scene_u16_at_0x322: readU16Safe(thisPointer, 0x322),
    active_story_no_u16_at_0x34a: readU16Safe(thisPointer, 0x34a),
    dir_no_u16_at_0x34c: readU16Safe(thisPointer, 0x34c),
    base_event_code_hex_at_0x358: readU64HexSafe(thisPointer, 0x358),
    previous_base_event_code_hex_at_0x360: readU64HexSafe(thisPointer, 0x360),
    next_event_code_hex_at_0x368: readU64HexSafe(thisPointer, 0x368),
    previous_next_event_code_hex_at_0x370: readU64HexSafe(thisPointer, 0x370),
  };
}

function describeMstComDirData(mstComCallback) {
  if (mstComCallback === null) {
    return {
      mstcom_pointer: "0x0",
      mstcom_error: "MSTCOMCBK export missing",
    };
  }
  try {
    const mstComPointer = mstComCallback();
    if (mstComPointer === null || mstComPointer.isNull()) {
      return {
        mstcom_pointer: "0x0",
        mstcom_error: "MSTCOMCBK returned null",
      };
    }
    return {
      mstcom_pointer: mstComPointer.toString(),
      mst_stage_kind_u16_at_0x2376: readU16Safe(mstComPointer, 0x2376),
      mst_source_story_no_u16_at_0x2378: readU16Safe(mstComPointer, 0x2378),
      mst_extra_u16_at_0x238a: readU16Safe(mstComPointer, 0x238a),
      mst_scene_u16_at_0x23be: readU16Safe(mstComPointer, 0x23be),
      mstcom_error: "",
    };
  } catch (error) {
    return {
      mstcom_pointer: "0x0",
      mstcom_error: String(error),
    };
  }
}

function hookAnmBaseDirData(moduleValue) {
  const symbol = "_ZN9C_AnmBase16fnDataSetDir_DIREv";
  const address = findExport(moduleValue, symbol);
  if (address === null) {
    return;
  }

  const mstComAddress = findExport(moduleValue, "_Z9MSTCOMCBKv");
  let mstComCallback = null;
  if (mstComAddress !== null) {
    try {
      mstComCallback = new NativeFunction(mstComAddress, "pointer", []);
    } catch (error) {
      emit("hook_attach_error", {
        hook_kind: "anm_base_data_set_dir_mstcom_callback",
        symbol: "_Z9MSTCOMCBKv",
        address: mstComAddress.toString(),
        error: String(error),
      });
    }
  }

  try {
    Interceptor.attach(address, {
      onEnter(args) {
        this.thisPointer = args[0];
        emitHighLevel(
          "anm_base_data_set_dir_enter",
          Object.assign(
            {
              symbol,
              address: address.toString(),
            },
            describeAnmBaseDirObject(args[0]),
            describeMstComDirData(mstComCallback)
          )
        );
      },
      onLeave(retval) {
        emitHighLevel(
          "anm_base_data_set_dir_leave",
          Object.assign(
            {
              symbol,
              address: address.toString(),
              retval_pointer: retval.toString(),
              retval_i32: toI32(retval),
            },
            describeAnmBaseDirObject(this.thisPointer),
            describeMstComDirData(mstComCallback)
          )
        );
      },
    });
  } catch (error) {
    emit("hook_attach_error", {
      hook_kind: "anm_base_data_set_dir",
      symbol,
      address: address.toString(),
      error: String(error),
    });
    return;
  }
  emit("hook_installed", { hook_kind: "anm_base_data_set_dir", symbol, address: address.toString() });
}

function hookSpStoryMethod(moduleValue, symbol, kind, argCount, emitLeave) {
  const address = findExport(moduleValue, symbol);
  if (address === null) {
    return;
  }
  try {
    Interceptor.attach(address, {
      onEnter(args) {
        this.thisPointer = args[0];
        const fields = Object.assign(
          {
            symbol,
            address: address.toString(),
          },
          describeSpStoryObject(args[0])
        );
        for (let index = 1; index < argCount; index += 1) {
          const u32Value = toU32(args[index]);
          fields["arg" + index + "_u16"] = u32Value === null ? null : u32Value & 0xffff;
          fields["arg" + index + "_i32"] = toI32(args[index]);
          fields["arg" + index + "_pointer"] = args[index].toString();
        }
        emitHighLevel(kind, fields);
      },
      onLeave(retval) {
        if (!emitLeave) {
          return;
        }
        emitHighLevel(
          kind + "_leave",
          Object.assign(
            {
              symbol,
              address: address.toString(),
              retval_pointer: retval.toString(),
              retval_i32: toI32(retval),
            },
            describeSpStoryObject(this.thisPointer)
          )
        );
      },
    });
  } catch (error) {
    emit("hook_attach_error", {
      hook_kind: kind,
      symbol,
      address: address.toString(),
      error: String(error),
    });
    return;
  }
  emit("hook_installed", { hook_kind: kind, symbol, address: address.toString() });
}

function hookForceRouting(moduleValue, symbol, kind, argCount, emitReturn) {
  const address = findExport(moduleValue, symbol);
  if (address === null) {
    return;
  }
  try {
    Interceptor.attach(address, {
      onEnter(args) {
        const fields = {
          symbol,
          address: address.toString(),
        };
        for (let index = 0; index < argCount; index += 1) {
          const u32Value = toU32(args[index]);
          fields["arg" + index + "_u16"] = u32Value === null ? null : u32Value & 0xffff;
          fields["arg" + index + "_i32"] = toI32(args[index]);
          fields["arg" + index + "_pointer"] = args[index].toString();
        }
        emitHighLevel(kind, fields);
      },
      onLeave(retval) {
        if (!emitReturn) {
          return;
        }
        emitHighLevel(kind + "_return", {
          symbol,
          address: address.toString(),
          retval_i32: toI32(retval),
          retval_pointer: retval.toString(),
        });
      },
    });
  } catch (error) {
    emit("hook_attach_error", {
      hook_kind: kind,
      symbol,
      address: address.toString(),
      error: String(error),
    });
    return;
  }
  emit("hook_installed", { hook_kind: kind, symbol, address: address.toString() });
}

function installSimpleEnterLeave(moduleValue, symbol, kind, onEnterExtra, onLeaveExtra) {
  const address = findExport(moduleValue, symbol);
  if (address === null) {
    return;
  }
  Interceptor.attach(address, {
    onEnter(args) {
      this.args = args;
      this.fields = Object.assign(
        {
          symbol,
          address: address.toString(),
        },
        onEnterExtra ? onEnterExtra(args) : {}
      );
      emit(kind + "_enter", this.fields);
    },
    onLeave(retval) {
      const fields = Object.assign({}, this.fields || {}, {
        return_pointer: retval.toString(),
        return_i32: toI32(retval),
      });
      if (onLeaveExtra) {
        Object.assign(fields, onLeaveExtra(this.args, retval, this.fields || {}));
      }
      emit(kind + "_leave", fields);
    },
  });
  emit("hook_installed", { hook_kind: kind, symbol, address: address.toString() });
}

function installHooks(moduleValue) {
  installSimpleEnterLeave(
    moduleValue,
    symbols.csndMngSndReq,
    "csnd_mng_snd_req",
    (args) => {
      const fields = {
        this_pointer: args[0].toString(),
        request_id_i32: toI32(args[1]),
        arg2_i32: toI32(args[2]),
        source: "CSndMng::SndReq",
      };
      activeRequestByThread[String(Process.getCurrentThreadId())] = fields;
      return fields;
    }
  );

  installSimpleEnterLeave(
    moduleValue,
    symbols.cslMngSndReq,
    "csl_mng_snd_req",
    (args) => {
      const fields = {
        this_pointer: args[0].toString(),
        request_id_i32: toI32(args[1]),
        arg2_i32: toI32(args[2]),
        source: "CSLMng::SndReq",
      };
      activeRequestByThread[String(Process.getCurrentThreadId())] = fields;
      return fields;
    }
  );

  installSimpleEnterLeave(
    moduleValue,
    symbols.cslMngPlayStart,
    "csl_mng_play_start",
    (args) => {
      const fields = {
        this_pointer: args[0].toString(),
        play_index_i32: toI32(args[2]),
        request:
          activeRequestByThread[String(Process.getCurrentThreadId())] || null,
        sound: describeSoundData(args[1]),
      };
      activePlayStartByThread[String(Process.getCurrentThreadId())] = fields;
      return fields;
    }
  );

  installSimpleEnterLeave(
    moduleValue,
    symbols.cslSoundCreate,
    "csl_sound_create",
    (args) => describeCslSound(args[0]),
    (args) => describeCslSound(args[0])
  );

  const sndPlayAddress = findExport(moduleValue, symbols.cslSoundSndPlay);
  if (sndPlayAddress !== null) {
    Interceptor.attach(sndPlayAddress, {
      onEnter(args) {
        playCallCount += 1;
        const cslSound = args[0];
        const soundData = args[1];
        const record = rememberSound(cslSound, soundData, {
          play_call_count: playCallCount,
        });
        activeSoundByThread[String(Process.getCurrentThreadId())] = record;
        this.fields = Object.assign(
          {
            symbol: symbols.cslSoundSndPlay,
            address: sndPlayAddress.toString(),
            play_call_count: playCallCount,
          },
          describeCslSound(cslSound),
          { sound: describeSoundData(soundData) }
        );
        emit("csl_sound_snd_play_enter", this.fields);
      },
      onLeave(retval) {
        const fields = Object.assign({}, this.fields || {}, {
          return_pointer: retval.toString(),
          return_i32: toI32(retval),
        });
        emit("csl_sound_snd_play_leave", fields);
      },
    });
    emit("hook_installed", {
      hook_kind: "csl_sound_snd_play",
      symbol: symbols.cslSoundSndPlay,
      address: sndPlayAddress.toString(),
    });
  }

  const callbackAddress = findExport(moduleValue, symbols.cslSoundCallback);
  if (callbackAddress !== null) {
    Interceptor.attach(callbackAddress, {
      onEnter(args) {
        callbackCallCount += 1;
        const cslSound = args[1];
        const fields = Object.assign(
          {
            symbol: symbols.cslSoundCallback,
            address: callbackAddress.toString(),
            callback_call_count: callbackCallCount,
            sl_buffer_queue_itf_pointer: args[0].toString(),
          },
          describeCslSound(cslSound)
        );
        activeSoundByThread[String(Process.getCurrentThreadId())] =
          soundByCslSound[pointerKey(cslSound)] || fields;
        emit("csl_sound_callback_enter", fields);
      },
    });
    emit("hook_installed", {
      hook_kind: "csl_sound_callback",
      symbol: symbols.cslSoundCallback,
      address: callbackAddress.toString(),
    });
  }

  const enqueueBufferAddress = findExport(moduleValue, symbols.cslSoundEnqueueBuffer);
  if (enqueueBufferAddress !== null) {
    Interceptor.attach(enqueueBufferAddress, {
      onEnter(args) {
        const cslSound = args[0];
        const fields = describeCslSound(cslSound);
        activeEnqueueByThread[String(Process.getCurrentThreadId())] = fields;
        emit(
          "csl_sound_enqueue_buffer_enter",
          Object.assign(
            {
              symbol: symbols.cslSoundEnqueueBuffer,
              address: enqueueBufferAddress.toString(),
            },
            fields
          )
        );
      },
      onLeave(retval) {
        emit("csl_sound_enqueue_buffer_leave", {
          symbol: symbols.cslSoundEnqueueBuffer,
          address: enqueueBufferAddress.toString(),
          return_pointer: retval.toString(),
          return_i32: toI32(retval),
        });
      },
    });
    emit("hook_installed", {
      hook_kind: "csl_sound_enqueue_buffer",
      symbol: symbols.cslSoundEnqueueBuffer,
      address: enqueueBufferAddress.toString(),
    });
  }

  const queueEnqueueAddress = findExport(moduleValue, symbols.cslQueueEnqueue);
  if (queueEnqueueAddress !== null) {
    Interceptor.attach(queueEnqueueAddress, {
      onEnter(args) {
        enqueueCallCount += 1;
        const threadKey = String(Process.getCurrentThreadId());
        const queue = args[0];
        const buffer = args[1];
        const byteCount = toU32(args[2]) || 0;
        const active = activeEnqueueByThread[threadKey] || {};
        const activePlayStart = activePlayStartByThread[threadKey] || {};
        const activeRequest =
          activePlayStart.request || activeRequestByThread[threadKey] || {};
        const mapped = soundByQueue[pointerKey(queue)] || {};
        const preview = readMemoryPreview(buffer, Math.min(byteCount, previewBytes));
        const shouldDump =
          byteCount > 0 &&
          byteCount <= maxBytesPerChunk &&
          dumpedChunks < maxDumpChunks &&
          dumpedBytes + byteCount <= maxDumpTotalBytes;
        const fields = Object.assign(
          {
            symbol: symbols.cslQueueEnqueue,
            address: queueEnqueueAddress.toString(),
            capture_point: "csl_android_simple_buffer_queue_enqueue",
            enqueue_call_count: enqueueCallCount,
            chunk_index: shouldDump ? dumpedChunks : null,
            queue_object: queue.toString(),
            buffer_pointer: buffer.toString(),
            buffer_bytes: byteCount,
            preview,
            dumped: shouldDump,
            dumped_chunks_so_far: dumpedChunks,
            dumped_bytes_so_far: dumpedBytes,
          },
          mapped,
          {
            play_start_this_pointer: activePlayStart.this_pointer || null,
            play_start_index_i32: activePlayStart.play_index_i32 ?? null,
            request:
              activePlayStart.request ||
              (activeRequest.request_id_i32 !== undefined ? activeRequest : null),
            request_id_i32: activeRequest.request_id_i32 ?? null,
            request_arg2_i32: activeRequest.arg2_i32 ?? null,
            sound:
              activePlayStart.sound ||
              mapped.sound ||
              (mapped.sound_data ? describeSoundData(ptr(mapped.sound_data)) : undefined),
            sound_data:
              (activePlayStart.sound && activePlayStart.sound.sound_data) ||
              mapped.sound_data ||
              null,
            sound_id_u16_at_0x2:
              (activePlayStart.sound &&
                activePlayStart.sound.sound_id_u16_at_0x2) ??
              mapped.sound_id_u16_at_0x2 ??
              null,
          },
          active
        );
        if (shouldDump) {
          const bytes = buffer.readByteArray(byteCount);
          dumpedChunks += 1;
          dumpedBytes += byteCount;
          emit("queue_enqueue_chunk", fields, bytes);
        } else {
          emit("queue_enqueue_metadata", fields);
        }
      },
    });
    emit("hook_installed", {
      hook_kind: "csl_android_simple_buffer_queue_enqueue",
      symbol: symbols.cslQueueEnqueue,
      address: queueEnqueueAddress.toString(),
      max_dump_chunks: maxDumpChunks,
      max_dump_total_bytes: maxDumpTotalBytes,
      max_bytes_per_chunk: maxBytesPerChunk,
    });
  }

  installSimpleEnterLeave(
    moduleValue,
    symbols.cslQueueClear,
    "csl_android_simple_buffer_queue_clear",
    (args) =>
      Object.assign(
        {
          queue_object: args[0].toString(),
        },
        soundByQueue[pointerKey(args[0])] || {}
      )
  );

  installSimpleEnterLeave(
    moduleValue,
    symbols.cslQueueRegisterCallback,
    "csl_android_simple_buffer_queue_register_callback",
    (args) => ({
      queue_object: args[0].toString(),
      callback_pointer: args[1].toString(),
      context_pointer: args[2].toString(),
    })
  );
}

function installHighLevelAudioHooks(moduleValue) {
  hookAnmBaseDirData(moduleValue);
  hookSpStoryMethod(
    moduleValue,
    "_ZN21C_ObjStageAT_SP_Story3preEv",
    "sp_story_pre",
    1,
    true
  );
  hookSpStoryMethod(
    moduleValue,
    "_ZN21C_ObjStageAT_SP_Story9fnSetDataEv",
    "sp_story_set_data",
    1,
    true
  );
  hookSpStoryMethod(
    moduleValue,
    "_ZN21C_ObjStageAT_SP_Story14fnSetEventCodeEv",
    "sp_story_set_event_code",
    1,
    true
  );
  hookSpStoryMethod(
    moduleValue,
    "_ZN21C_ObjStageAT_SP_Story13fnSetEvCdBaseEt",
    "sp_story_set_evcd_base",
    2,
    true
  );
  hookSpStoryMethod(
    moduleValue,
    "_ZN21C_ObjStageAT_SP_Story13fnSetEvCdNextEt",
    "sp_story_set_evcd_next",
    2,
    true
  );
  hookSpStoryMethod(
    moduleValue,
    "_ZN21C_ObjStageAT_SP_Story9fnPlayAnmEv",
    "sp_story_play_anm",
    1,
    false
  );
  hookForceRouting(
    moduleValue,
    "_ZN5ID40114fnClrForceFlagEv",
    "force_flag_clear",
    0,
    false
  );
  hookForceRouting(
    moduleValue,
    "_ZN5ID40114fnSetForceFlagEtt",
    "force_flag_set",
    2,
    true
  );
  hookForceRouting(
    moduleValue,
    "_ZN5ID40118fnGetForceFlagKindEv",
    "force_flag_get_kind",
    0,
    true
  );
  hookForceRouting(
    moduleValue,
    "_ZN5ID40121fnGetForceFlagKind_ATEh",
    "force_flag_get_kind_at",
    1,
    true
  );
  hookForceRouting(
    moduleValue,
    "_ZN5ID40111LC701A_SLOT12SetForceFlagEv",
    "force_lc701a_set_force_flag",
    1,
    true
  );
  hookForceRouting(
    moduleValue,
    "_ZN5ID40121fnGameLot_SetEPBforceEi",
    "force_game_lot_set_epb_force",
    1,
    false
  );
  hookForceRouting(
    moduleValue,
    "fnGameLot_GetEPBforce",
    "force_game_lot_get_epb_force",
    0,
    true
  );
  hookIntCall(moduleValue, "_ZN8SoundMng4playEii", "sound_mng_play", 2);
  hookCStringAndInts(
    moduleValue,
    "_ZN8SoundMng4playEPhii",
    "sound_mng_play_bytes",
    1,
    [2, 3]
  );
  hookCStringAndInts(
    moduleValue,
    "SoundMng_play_bySoundCd",
    "sound_mng_play_by_sound_cd",
    0,
    [1, 2]
  );
  hookCStringAndInts(moduleValue, "SndReqBySoundCd", "snd_req_by_sound_cd", 0, [1, 2]);
  hookIntCall(moduleValue, "_ZN8SoundMng10sndPlayReqEiii", "sound_mng_play_request", 3);
  hookIntCall(moduleValue, "_ZN8SoundMng10wrapSndReqEi", "sound_mng_wrap_request", 1);
  hookIntCall(
    moduleValue,
    "_ZN8SoundMng12wrapSndReqChEii",
    "sound_mng_wrap_request_channel",
    2
  );
  hookRawCall(
    moduleValue,
    "SoundMng_isAlreadyPlayingBGM",
    "sound_mng_is_already_playing_bgm",
    2,
    []
  );
  hookRawCall(moduleValue, "SndIsAlreadyPlayingBGM", "snd_is_already_playing_bgm", 2, []);
  hookRawCall(moduleValue, "zgSndReqCode", "zg_snd_req_code", 6, [0, 1]);
  hookRawCall(moduleValue, "zgSndReqFadeCode", "zg_snd_req_fade_code", 6, [0, 1]);
  hookRawCall(moduleValue, "zgSndReqVolumeCode", "zg_snd_req_volume_code", 6, [0, 1]);
  hookRawCall(moduleValue, "zgSndReqPauseCode", "zg_snd_req_pause_code", 4, [0, 1]);
  hookRawCall(
    moduleValue,
    "_ZN8C_ObjNml25fnSndRequest_BGM_SEQUENCEEv",
    "obj_nml_snd_request_bgm_sequence",
    1,
    []
  );
  hookRawCall(
    moduleValue,
    "_ZN8C_ObjNml20fnSndRequest_BGM_DIREv",
    "obj_nml_snd_request_bgm_dir",
    1,
    []
  );
  hookRawCall(
    moduleValue,
    "_ZN8C_ObjNml20fnSndRequest_BGM_STGEv",
    "obj_nml_snd_request_bgm_stg",
    1,
    []
  );
  hookRawCall(
    moduleValue,
    "_ZN8C_ObjNml20fnSndRequest_BGM_ENDEv",
    "obj_nml_snd_request_bgm_end",
    1,
    []
  );
  hookRawCall(
    moduleValue,
    "_ZN8C_ObjNml25fnSndRequest_BGM_DIR_NEXTEv",
    "obj_nml_snd_request_bgm_dir_next",
    1,
    []
  );
  hookRawCall(
    moduleValue,
    "_ZN8C_ObjNml26fnSndRequest_BGM_FADE_NEXTEv",
    "obj_nml_snd_request_bgm_fade_next",
    1,
    []
  );
  hookRawCall(
    moduleValue,
    "_ZN8C_ObjNml21fnSndRequest_BGM_FADEEv",
    "obj_nml_snd_request_bgm_fade",
    1,
    []
  );
  hookRawCall(
    moduleValue,
    "_ZN25C_DirectionControllerBase18Macro_SND_BGM_PLAYE32tagDirectionControllerDeviceData",
    "direction_macro_snd_bgm_play",
    2,
    []
  );
  hookRawCall(
    moduleValue,
    "_ZN14C_ObjSelectBNS15fnSndRequestBGMEv",
    "obj_select_bns_snd_request_bgm",
    1,
    []
  );
  hookRawCall(
    moduleValue,
    "_ZN12C_CtrlSndLib17fnReqSndEventCodeEy",
    "ctrl_snd_req_event_code",
    2,
    []
  );
  hookCStringAndInts(
    moduleValue,
    "_ZN12C_CtrlSndLib17fnReqSndSoundCodeEPKch",
    "ctrl_snd_req_sound_code",
    1,
    [2]
  );
  hookCStringAndInts(
    moduleValue,
    "_ZN12C_CtrlSndLib17fnReqSndSoundCodeEPKchm",
    "ctrl_snd_req_sound_code_timed",
    1,
    [2, 3]
  );
  hookCStringAndInts(
    moduleValue,
    "_ZN12C_CtrlSndLib17fnReqSndSeqenceSCEPKch",
    "ctrl_snd_req_sequence_sc",
    1,
    [2]
  );
  hookCStringAndInts(
    moduleValue,
    "_ZN12C_CtrlSndLib25fnReqSndSoundCodeCallBackEPKc",
    "ctrl_snd_req_sound_code_callback",
    1,
    []
  );
  hookCStringAndInts(
    moduleValue,
    "_ZN12C_CtrlSndLib11fnReqSndNowEPKc",
    "ctrl_snd_req_now",
    1,
    []
  );
  hookCStringAndInts(
    moduleValue,
    "_ZN12C_CtrlSndLib16fnCallSndCodeCbkEPKc",
    "ctrl_snd_call_code_callback",
    1,
    []
  );
  hookCStringAndInts(
    moduleValue,
    "_Z16fnProcSndCodeCbkPKc",
    "snd_proc_code_callback",
    0,
    []
  );
}

setImmediate(function () {
  const modules = Process.enumerateModules();
  const moduleValue = Process.findModuleByName(moduleName);
  const gameProcModuleValue = Process.findModuleByName(gameProcModuleName);
  emit("probe_start", {
    architecture: Process.arch,
    platform: Process.platform,
    module_found: moduleValue !== null,
    game_proc_module_found: gameProcModuleValue !== null,
    target_module: moduleName,
    high_level_audio_module: gameProcModuleName,
    max_high_level_emits_per_kind: maxHighLevelEmitsPerKind,
    relevant_modules: modules
      .filter((item) => /AMAIN|OpenSLES|openal|GameProc|ARES|audio|snd/i.test(item.name))
      .map((item) => ({
        name: item.name,
        path: item.path,
        base: item.base.toString(),
        size: item.size,
      })),
  });
  installHooks(moduleValue);
  installHighLevelAudioHooks(gameProcModuleValue);
});
