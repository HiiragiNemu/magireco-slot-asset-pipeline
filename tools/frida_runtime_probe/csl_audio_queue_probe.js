"use strict";

const moduleName = "libAMAIN.so";

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

setImmediate(function () {
  const modules = Process.enumerateModules();
  const moduleValue = Process.findModuleByName(moduleName);
  emit("probe_start", {
    architecture: Process.arch,
    platform: Process.platform,
    module_found: moduleValue !== null,
    target_module: moduleName,
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
});
