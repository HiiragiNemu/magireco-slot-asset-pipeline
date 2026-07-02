"use strict";

// Lightweight visual-tail/BGM diagnostic probe.
//
// This script records metadata only.  It does not dump frame buffers, PCM, or
// media payloads.  It is meant to answer whether a role-voice tail is a native
// game hold/lock behavior or an artifact of the external renderer.

const moduleName = "libGameProc.so";
const maxCStringBytes = 256;
let activeEvent = null;
const lastEmitByKey = new Map();

const symbolOffsetFallbacks = {
  GLtask_display1: 0x424791c,
  GLtask_display2: 0x424797c,
  DirDrawCtrl: 0x42545d8,
  DirGetFrame: 0x42545fc,
  _ZN9CSlotBody16NotifyMovieStartEixP11CDirCriAnim: 0x4253d58,
  _ZN9CSlotBody15GetRenderTargetEix: 0x4253d50,
  _ZN14CriManaWrapper19ExecuteVideoProcessEv: 0x4258238,
  _ZN14CriManaWrapper12IsFrameReadyEv: 0x4258284,
  _ZN14CriManaWrapper12GetFrameInfoEPiS0_S0_S0_: 0x42582c8,
  _ZN14CriManaWrapper12GetFrameYUVAEPPhS1_S1_S1_PiS2_S2_: 0x42582c0,
  _ZN14CriManaWrapper13CopyFrameYUVAEPhS0_S0_S0_iii: 0x42582d0,
  _ZN16CScreenObjectMng16calcFrameControlEv: 0x424b574,
  _ZN16CScreenObjectMng4drawEv: 0x424b578,
  _ZN16CScreenObjectMng12setLockFrameEi: 0x424b5c8,
};

function nowMs() {
  return Date.now();
}

function readCString(pointerValue) {
  if (pointerValue === null || pointerValue.isNull()) {
    return { text: "", length: 0, error: "" };
  }
  try {
    let length = 0;
    while (length < maxCStringBytes && pointerValue.add(length).readU8() !== 0) {
      length += 1;
    }
    return { text: pointerValue.readCString(), length, error: "" };
  } catch (error) {
    return { text: "", length: 0, error: String(error) };
  }
}

function readS32(pointerValue) {
  if (pointerValue === null || pointerValue.isNull()) {
    return null;
  }
  try {
    return pointerValue.readS32();
  } catch (_) {
    return null;
  }
}

function readPointerValue(pointerValue) {
  if (pointerValue === null || pointerValue.isNull()) {
    return null;
  }
  try {
    return pointerValue.readPointer().toString();
  } catch (_) {
    return null;
  }
}

function readBytesHex(pointerValue, byteCount) {
  if (pointerValue === null || pointerValue.isNull() || byteCount <= 0) {
    return "";
  }
  const limit = Math.min(byteCount, 32);
  try {
    const bytes = pointerValue.readByteArray(limit);
    const values = Array.from(new Uint8Array(bytes));
    return values.map((value) => value.toString(16).padStart(2, "0")).join("");
  } catch (_) {
    return "";
  }
}

function checksumBytes(pointerValue, byteCount) {
  if (pointerValue === null || pointerValue.isNull() || byteCount <= 0) {
    return null;
  }
  const limit = Math.min(byteCount, 4096);
  try {
    const bytes = pointerValue.readByteArray(limit);
    const values = new Uint8Array(bytes);
    let hash = 2166136261 >>> 0;
    for (let index = 0; index < values.length; index += 1) {
      hash ^= values[index];
      hash = Math.imul(hash, 16777619) >>> 0;
    }
    return hash.toString(16).padStart(8, "0");
  } catch (_) {
    return null;
  }
}

function readStdStringCandidates(pointerValue) {
  if (pointerValue === null || pointerValue.isNull()) {
    return [];
  }
  const candidates = [];

  function addCandidate(source, text, error) {
    if (text && text.length > 0) {
      candidates.push({ source, text, error: error || "" });
    } else if (error) {
      candidates.push({ source, text: "", error });
    }
  }

  try {
    // libc++ short-string layout usually stores bytes after the first control
    // byte.  This is heuristic only; SetData is the stronger identification.
    addCandidate("short+1", pointerValue.add(1).readCString());
  } catch (error) {
    addCandidate("short+1", "", String(error));
  }

  try {
    // libc++ long-string layout commonly stores the char* at +16 on arm64.
    const dataPointer = pointerValue.add(16).readPointer();
    const value = readCString(dataPointer);
    addCandidate("long+16", value.text, value.error);
  } catch (error) {
    addCandidate("long+16", "", String(error));
  }

  try {
    const value = readCString(pointerValue);
    addCandidate("direct", value.text, value.error);
  } catch (error) {
    addCandidate("direct", "", String(error));
  }

  return candidates;
}

function describeAddress(pointerValue) {
  if (pointerValue === null || pointerValue.isNull()) {
    return null;
  }
  const range = Process.findRangeByAddress(pointerValue);
  const result = { pointer: pointerValue.toString(), readable: false };
  if (range !== null) {
    result.readable = range.protection.indexOf("r") !== -1;
    result.range_base = range.base.toString();
    result.range_size = range.size;
    result.protection = range.protection;
    if (range.file) {
      result.file = range.file.path;
      result.file_offset = range.file.offset;
    }
  }
  return result;
}

function activeFields() {
  if (activeEvent === null) {
    return {};
  }
  return {
    active_event_code: activeEvent.code_hex,
    active_event_object: activeEvent.animation_object,
    active_event_relative_ms: nowMs() - activeEvent.start_unix_ms,
  };
}

function emit(kind, fields) {
  send(
    Object.assign(
      {
        kind,
        unix_ms: nowMs(),
        thread_id: Process.getCurrentThreadId(),
      },
      activeFields(),
      fields || {}
    )
  );
}

function shouldEmit(kind, identity, intervalMs) {
  const key =
    (activeEvent === null ? "" : activeEvent.code_hex) +
    "\u0000" +
    kind +
    "\u0000" +
    identity;
  const current = nowMs();
  const previous = lastEmitByKey.get(key) || 0;
  if (current - previous < intervalMs) {
    return false;
  }
  lastEmitByKey.set(key, current);
  return true;
}

function findGameModule() {
  const namedModule = Process.findModuleByName(moduleName);
  if (namedModule !== null) {
    return namedModule;
  }
  const anchorSymbols = [
    "_ZN9C_AnmBase10fnReqSceneEyhtt",
    "Java_util_JniBridge_nscnCalc",
    "_ZN14CriManaWrapper7SetDataEPKhm",
  ];
  for (const symbol of anchorSymbols) {
    const address = Module.findGlobalExportByName(symbol);
    if (address === null) {
      continue;
    }
    const addressModule = Process.findModuleByAddress(address);
    if (addressModule !== null) {
      return addressModule;
    }
  }
  return null;
}

function findExport(moduleValue, symbol) {
  let address =
    moduleValue !== null
      ? moduleValue.findExportByName(symbol)
      : Module.findGlobalExportByName(symbol);
  if (address === null) {
    address = Module.findGlobalExportByName(symbol);
  }
  if (address === null && moduleValue !== null) {
    const fallbackOffset = symbolOffsetFallbacks[symbol];
    if (fallbackOffset !== undefined) {
      if (fallbackOffset >= 0 && fallbackOffset < moduleValue.size) {
        address = moduleValue.base.add(fallbackOffset);
        emit("hook_resolved_by_offset", {
          symbol,
          module_base: moduleValue.base.toString(),
          module_size: moduleValue.size,
          offset: "0x" + fallbackOffset.toString(16),
          address: address.toString(),
        });
      } else {
        emit("hook_offset_out_of_range", {
          symbol,
          module_base: moduleValue.base.toString(),
          module_size: moduleValue.size,
          offset: "0x" + fallbackOffset.toString(16),
        });
      }
    }
  }
  if (address === null) {
    emit("hook_missing", { symbol });
    return null;
  }
  return address;
}

function hookEventRequest(moduleValue) {
  const symbol = "_ZN9C_AnmBase10fnReqSceneEyhtt";
  const address = findExport(moduleValue, symbol);
  if (address === null) {
    return;
  }
  Interceptor.attach(address, {
    onEnter(args) {
      activeEvent = {
        code_hex: "0x" + args[1].toString(16).padStart(16, "0"),
        animation_object: args[0].toString(),
        start_unix_ms: nowMs(),
      };
      emit("animation_event_start", {
        symbol,
        address: address.toString(),
        immediate: args[2].toInt32() & 0xff,
        layer_flags: args[3].toInt32() & 0xffff,
        request_flags: args[4].toInt32() & 0xffff,
      });
    },
  });
  emit("hook_installed", { symbol, address: address.toString() });
}

function hookEnterArgs(moduleValue, symbol, kind, argCount, throttleMs) {
  const address = findExport(moduleValue, symbol);
  if (address === null) {
    return;
  }
  try {
    Interceptor.attach(address, {
      onEnter(args) {
        const identity = argCount > 0 ? args[0].toString() : symbol;
        if (throttleMs && !shouldEmit(kind, identity, throttleMs)) {
          return;
        }
        const fields = { symbol, address: address.toString() };
        for (let index = 0; index < argCount; index += 1) {
          fields["arg" + index + "_pointer"] = args[index].toString();
          fields["arg" + index + "_i32"] = args[index].toInt32();
        }
        emit(kind, fields);
      },
    });
  } catch (error) {
    emit("hook_attach_failed", {
      symbol,
      address: address.toString(),
      kind,
      error: String(error),
    });
    return;
  }
  emit("hook_installed", { symbol, address: address.toString() });
}

function hookReturn(moduleValue, symbol, kind, argCount, throttleMs) {
  const address = findExport(moduleValue, symbol);
  if (address === null) {
    return;
  }
  try {
    Interceptor.attach(address, {
      onEnter(args) {
        const identity = argCount > 0 ? args[0].toString() : symbol;
        this.skip = throttleMs && !shouldEmit(kind, identity, throttleMs);
        if (this.skip) {
          return;
        }
        this.fields = { symbol, address: address.toString() };
        for (let index = 0; index < argCount; index += 1) {
          this.fields["arg" + index + "_pointer"] = args[index].toString();
          this.fields["arg" + index + "_i32"] = args[index].toInt32();
        }
      },
      onLeave(retval) {
        if (this.skip) {
          return;
        }
        this.fields.return_pointer = retval.toString();
        this.fields.return_i32 = retval.toInt32();
        emit(kind, this.fields);
      },
    });
  } catch (error) {
    emit("hook_attach_failed", {
      symbol,
      address: address.toString(),
      kind,
      error: String(error),
    });
    return;
  }
  emit("hook_installed", { symbol, address: address.toString() });
}

function hookCriFrameInfo(moduleValue) {
  const symbol = "_ZN14CriManaWrapper12GetFrameInfoEPiS0_S0_S0_";
  const address = findExport(moduleValue, symbol);
  if (address === null) {
    return;
  }
  try {
    Interceptor.attach(address, {
      onEnter(args) {
        this.skip = !shouldEmit("cri_frame_info", args[0].toString(), 250);
        if (this.skip) {
          return;
        }
        this.receiver = args[0];
        this.pointers = [args[1], args[2], args[3], args[4]];
      },
      onLeave(retval) {
        if (this.skip) {
          return;
        }
        emit("cri_frame_info", {
          symbol,
          address: address.toString(),
          receiver: this.receiver.toString(),
          return_i32: retval.toInt32(),
          value0: readS32(this.pointers[0]),
          value1: readS32(this.pointers[1]),
          value2: readS32(this.pointers[2]),
          value3: readS32(this.pointers[3]),
        });
      },
    });
  } catch (error) {
    emit("hook_attach_failed", {
      symbol,
      address: address.toString(),
      kind: "cri_frame_info",
      error: String(error),
    });
    return;
  }
  emit("hook_installed", { symbol, address: address.toString() });
}

function hookCriMovieInfo(moduleValue) {
  const symbol = "_ZN14CriManaWrapper12GetMovieInfoEPiS0_PfS0_S0_";
  const address = findExport(moduleValue, symbol);
  if (address === null) {
    return;
  }
  try {
    Interceptor.attach(address, {
      onEnter(args) {
        this.skip = !shouldEmit("cri_movie_info", args[0].toString(), 1000);
        if (this.skip) {
          return;
        }
        this.receiver = args[0];
        this.i0 = args[1];
        this.i1 = args[2];
        this.f2 = args[3];
        this.i3 = args[4];
        this.i4 = args[5];
      },
      onLeave(retval) {
        if (this.skip) {
          return;
        }
        let frameRate = null;
        try {
          frameRate = this.f2.readFloat();
        } catch (_) {
          frameRate = null;
        }
        emit("cri_movie_info", {
          symbol,
          address: address.toString(),
          receiver: this.receiver.toString(),
          return_i32: retval.toInt32(),
          value0: readS32(this.i0),
          value1: readS32(this.i1),
          frame_rate: frameRate,
          value3: readS32(this.i3),
          value4: readS32(this.i4),
        });
      },
    });
  } catch (error) {
    emit("hook_attach_failed", {
      symbol,
      address: address.toString(),
      kind: "cri_movie_info",
      error: String(error),
    });
    return;
  }
  emit("hook_installed", { symbol, address: address.toString() });
}

function hookCriGetFrameYuva(moduleValue) {
  const symbol =
    "_ZN14CriManaWrapper12GetFrameYUVAEPPhS1_S1_S1_PiS2_S2_";
  const address = findExport(moduleValue, symbol);
  if (address === null) {
    return;
  }
  try {
    Interceptor.attach(address, {
      onEnter(args) {
        this.skip = !shouldEmit("cri_get_frame_yuva", args[0].toString(), 250);
        if (this.skip) {
          return;
        }
        this.receiver = args[0];
        this.planePointers = [args[1], args[2], args[3], args[4]];
        this.infoPointers = [args[5], args[6], args[7]];
      },
      onLeave(retval) {
        if (this.skip) {
          return;
        }
        emit("cri_get_frame_yuva", {
          symbol,
          address: address.toString(),
          receiver: this.receiver.toString(),
          return_pointer: retval.toString(),
          return_i32: retval.toInt32(),
          plane0_pointer: readPointerValue(this.planePointers[0]),
          plane1_pointer: readPointerValue(this.planePointers[1]),
          plane2_pointer: readPointerValue(this.planePointers[2]),
          plane3_pointer: readPointerValue(this.planePointers[3]),
          value0: readS32(this.infoPointers[0]),
          value1: readS32(this.infoPointers[1]),
          value2: readS32(this.infoPointers[2]),
        });
      },
    });
  } catch (error) {
    emit("hook_attach_failed", {
      symbol,
      address: address.toString(),
      kind: "cri_get_frame_yuva",
      error: String(error),
    });
    return;
  }
  emit("hook_installed", { symbol, address: address.toString() });
}

function hookCriCopyFrameYuva(moduleValue) {
  const symbol = "_ZN14CriManaWrapper13CopyFrameYUVAEPhS0_S0_S0_iii";
  const address = findExport(moduleValue, symbol);
  if (address === null) {
    return;
  }
  try {
    Interceptor.attach(address, {
      onEnter(args) {
        if (!shouldEmit("cri_copy_frame_yuva", args[0].toString(), 250)) {
          return;
        }
        emit("cri_copy_frame_yuva", {
          symbol,
          address: address.toString(),
          receiver: args[0].toString(),
          plane0_pointer: args[1].toString(),
          plane1_pointer: args[2].toString(),
          plane2_pointer: args[3].toString(),
          plane3_pointer: args[4].toString(),
          value0: args[5].toInt32(),
          value1: args[6].toInt32(),
          value2: args[7].toInt32(),
        });
      },
    });
  } catch (error) {
    emit("hook_attach_failed", {
      symbol,
      address: address.toString(),
      kind: "cri_copy_frame_yuva",
      error: String(error),
    });
    return;
  }
  emit("hook_installed", { symbol, address: address.toString() });
}

function hookCriGetFrameYuvaWithInfo(moduleValue) {
  const symbol =
    "_ZN14CriManaWrapper21GetFrameYUVA_WithInfoEPhS0_S0_S0_PiS1_S1_";
  const address = findExport(moduleValue, symbol);
  if (address === null) {
    return;
  }
  try {
    Interceptor.attach(address, {
      onEnter(args) {
        if (!shouldEmit("cri_get_frame_yuva_with_info", args[0].toString(), 250)) {
          return;
        }
        emit("cri_get_frame_yuva_with_info", {
          symbol,
          address: address.toString(),
          receiver: args[0].toString(),
          plane0_pointer: args[1].toString(),
          plane1_pointer: args[2].toString(),
          plane2_pointer: args[3].toString(),
          plane3_pointer: args[4].toString(),
          value0: readS32(args[5]),
          value1: readS32(args[6]),
          value2: readS32(args[7]),
        });
      },
    });
  } catch (error) {
    emit("hook_attach_failed", {
      symbol,
      address: address.toString(),
      kind: "cri_get_frame_yuva_with_info",
      error: String(error),
    });
    return;
  }
  emit("hook_installed", { symbol, address: address.toString() });
}

function hookCriSetData(moduleValue) {
  const symbol = "_ZN14CriManaWrapper7SetDataEPKhm";
  const address = findExport(moduleValue, symbol);
  if (address === null) {
    return;
  }
  try {
    Interceptor.attach(address, {
      onEnter(args) {
        const size = args[2].toUInt32();
        emit("cri_set_data", {
          symbol,
          address: address.toString(),
          receiver: args[0].toString(),
          data_pointer: args[1].toString(),
          data_address: describeAddress(args[1]),
          byte_size_u32: size,
          data_head32_hex: readBytesHex(args[1], size),
          data_fnv1a_4k: checksumBytes(args[1], size),
        });
      },
    });
  } catch (error) {
    emit("hook_attach_failed", {
      symbol,
      address: address.toString(),
      kind: "cri_set_data",
      error: String(error),
    });
    return;
  }
  emit("hook_installed", { symbol, address: address.toString() });
}

function hookCriSetFile(moduleValue) {
  const symbol = "_ZN14CriManaWrapper7SetFileERKNSt6__ndk112basic_stringIcNS0_11char_traitsIcEENS0_9allocatorIcEEEE";
  const address = findExport(moduleValue, symbol);
  if (address === null) {
    return;
  }
  try {
    Interceptor.attach(address, {
      onEnter(args) {
        emit("cri_set_file", {
          symbol,
          address: address.toString(),
          receiver: args[0].toString(),
          string_pointer: args[1].toString(),
          candidates: readStdStringCandidates(args[1]),
        });
      },
    });
  } catch (error) {
    emit("hook_attach_failed", {
      symbol,
      address: address.toString(),
      kind: "cri_set_file",
      error: String(error),
    });
    return;
  }
  emit("hook_installed", { symbol, address: address.toString() });
}

function hookCriLifecycle(moduleValue) {
  hookEnterArgs(moduleValue, "_ZN14CriManaWrapper12CreatePlayerEv", "cri_create_player", 1, 0);
  hookEnterArgs(moduleValue, "_ZN14CriManaWrapper13DestroyPlayerEv", "cri_destroy_player", 1, 0);
  hookCriSetData(moduleValue);
  hookCriSetFile(moduleValue);
  hookEnterArgs(moduleValue, "_ZN14CriManaWrapper7SetLoopEb", "cri_set_loop", 2, 0);
  hookEnterArgs(moduleValue, "_ZN14CriManaWrapper5StartEv", "cri_start", 1, 0);
  hookEnterArgs(moduleValue, "_ZN14CriManaWrapper4StopEv", "cri_stop", 1, 0);
  hookEnterArgs(moduleValue, "_ZN14CriManaWrapper4SeekEi", "cri_seek", 2, 0);
  hookEnterArgs(moduleValue, "_ZN14CriManaWrapper6UpdateEv", "cri_update", 1, 1000);
}

function hookCStringAndInts(moduleValue, symbol, kind, cStringArgIndex, intArgIndexes) {
  const address = findExport(moduleValue, symbol);
  if (address === null) {
    return;
  }
  try {
    Interceptor.attach(address, {
      onEnter(args) {
        const fields = { symbol, address: address.toString() };
        const value = readCString(args[cStringArgIndex]);
        fields["arg" + cStringArgIndex + "_text_utf8"] = value.text;
        fields["arg" + cStringArgIndex + "_byte_length"] = value.length;
        fields["arg" + cStringArgIndex + "_read_error"] = value.error;
        intArgIndexes.forEach((argIndex) => {
          fields["arg" + argIndex + "_i32"] = args[argIndex].toInt32();
        });
        emit(kind, fields);
      },
    });
  } catch (error) {
    emit("hook_attach_failed", {
      symbol,
      address: address.toString(),
      kind,
      error: String(error),
    });
    return;
  }
  emit("hook_installed", { symbol, address: address.toString() });
}

function hookSelectedBgmAudio(moduleValue) {
  hookEnterArgs(moduleValue, "SoundMng_isAlreadyPlayingBGM", "sound_mng_is_already_playing_bgm", 2, 500);
  hookEnterArgs(moduleValue, "SndIsAlreadyPlayingBGM", "snd_is_already_playing_bgm", 2, 500);
  hookCStringAndInts(moduleValue, "zgSndReqCode", "zg_snd_req_code", 0, [2, 3, 4, 5]);
  hookCStringAndInts(moduleValue, "zgSndReqFadeCode", "zg_snd_req_fade_code", 0, [2, 3, 4, 5]);
  hookCStringAndInts(moduleValue, "zgSndReqVolumeCode", "zg_snd_req_volume_code", 0, [2, 3, 4, 5]);
  hookCStringAndInts(
    moduleValue,
    "_ZN12C_CtrlSndLib17fnReqSndSoundCodeEPKch",
    "ctrl_snd_req_sound_code",
    1,
    [2]
  );
  hookCStringAndInts(
    moduleValue,
    "_ZN12C_CtrlSndLib17fnReqSndSeqenceSCEPKch",
    "ctrl_snd_req_sequence_sc",
    1,
    [2]
  );
  hookEnterArgs(moduleValue, "_ZN8C_ObjNml25fnSndRequest_BGM_SEQUENCEEv", "obj_nml_snd_request_bgm_sequence", 1, 0);
  hookEnterArgs(moduleValue, "_ZN8C_ObjNml20fnSndRequest_BGM_DIREv", "obj_nml_snd_request_bgm_dir", 1, 0);
  hookEnterArgs(moduleValue, "_ZN8C_ObjNml20fnSndRequest_BGM_STGEv", "obj_nml_snd_request_bgm_stg", 1, 0);
  hookEnterArgs(moduleValue, "_ZN8C_ObjNml20fnSndRequest_BGM_ENDEv", "obj_nml_snd_request_bgm_end", 1, 0);
  hookEnterArgs(moduleValue, "_ZN25C_DirectionControllerBase18Macro_SND_BGM_PLAYE32tagDirectionControllerDeviceData", "direction_macro_snd_bgm_play", 2, 0);
  hookEnterArgs(moduleValue, "_ZN14C_ObjSelectBNS15fnSndRequestBGMEv", "obj_select_bns_snd_request_bgm", 1, 0);
}

setImmediate(function () {
  const moduleValue = findGameModule();
  emit("probe_start", {
    architecture: Process.arch,
    platform: Process.platform,
    requested_module_name: moduleName,
    module_found: moduleValue !== null,
    resolved_module:
      moduleValue === null
        ? null
        : {
            name: moduleValue.name,
            path: moduleValue.path,
            base: moduleValue.base.toString(),
            size: moduleValue.size,
          },
    relevant_modules: Process.enumerateModules()
      .filter((item) => /GameProc|AMAIN|openal|ogg|ARES/i.test(item.name))
      .map((item) => ({
        name: item.name,
        path: item.path,
        base: item.base.toString(),
        size: item.size,
      })),
  });

  hookEventRequest(moduleValue);

  hookEnterArgs(moduleValue, "Java_util_JniBridge_nscnCalc", "nscn_calc", 1, 250);
  hookEnterArgs(moduleValue, "GLtask_display1", "gl_task_display1", 0, 500);
  hookEnterArgs(moduleValue, "GLtask_display2", "gl_task_display2", 0, 500);

  hookReturn(moduleValue, "DirGetFrame", "dir_get_frame", 2, 250);
  hookEnterArgs(moduleValue, "DirSetFrame", "dir_set_frame", 3, 0);
  hookEnterArgs(moduleValue, "DirDrawCtrl", "dir_draw_ctrl", 3, 250);

  hookEnterArgs(
    moduleValue,
    "_ZN15CDirMngListener15NotifyStartAnimEixP8CDirAnim",
    "dir_notify_start_anim",
    3,
    0
  );
  hookEnterArgs(
    moduleValue,
    "_ZN9CSlotBody16NotifyMovieStartEixP11CDirCriAnim",
    "slot_body_notify_movie_start",
    3,
    0
  );
  hookReturn(moduleValue, "_ZN9CSlotBody15GetRenderTargetEix", "slot_body_get_render_target", 3, 500);

  hookEnterArgs(moduleValue, "_ZN14CriManaWrapper19ExecuteVideoProcessEv", "cri_execute_video_process", 1, 250);
  hookEnterArgs(moduleValue, "_ZN14CriManaWrapper17ExecutePlayerMainEv", "cri_execute_player_main", 1, 250);
  hookReturn(moduleValue, "_ZN14CriManaWrapper12IsFrameReadyEv", "cri_is_frame_ready", 1, 250);
  hookReturn(moduleValue, "_ZN14CriManaWrapper9GetStatusEv", "cri_get_status", 1, 250);
  hookCriLifecycle(moduleValue);
  hookCriFrameInfo(moduleValue);
  hookCriMovieInfo(moduleValue);
  hookCriGetFrameYuva(moduleValue);
  hookCriCopyFrameYuva(moduleValue);
  hookCriGetFrameYuvaWithInfo(moduleValue);

  hookEnterArgs(moduleValue, "_ZN16CScreenObjectMng16calcFrameControlEv", "screen_object_calc_frame_control", 1, 250);
  hookEnterArgs(moduleValue, "_ZN16CScreenObjectMng4drawEv", "screen_object_draw", 1, 250);
  hookEnterArgs(moduleValue, "_ZN16CScreenObjectMng12setLockFrameEi", "screen_object_set_lock_frame", 2, 0);
  hookReturn(moduleValue, "_ZN16CScreenObjectMng9checkLockEv", "screen_object_check_lock", 1, 250);
  hookReturn(moduleValue, "_ZNK16CScreenObjectMng6isLockEv", "screen_object_is_lock", 1, 250);

  hookEnterArgs(moduleValue, "_ZN25C_DirectionControllerBase13PlayAnimationEv", "direction_play_animation", 1, 250);
  hookEnterArgs(moduleValue, "_ZN25C_DirectionControllerBase16Macro_CHANGE_ANME32tagDirectionControllerDeviceDatat", "direction_macro_change_anm", 3, 0);
  hookEnterArgs(moduleValue, "_ZN25C_DirectionControllerBase16Macro_EVENT_PLAYE32tagDirectionControllerDeviceData", "direction_macro_event_play", 2, 0);

  hookSelectedBgmAudio(moduleValue);

  emit("probe_ready", {});
});
