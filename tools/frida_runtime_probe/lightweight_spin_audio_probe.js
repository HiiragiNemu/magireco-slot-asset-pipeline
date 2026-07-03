"use strict";

// Lightweight runtime observer for real screen-input experiments.
//
// This script deliberately avoids high-frequency GL/per-frame hooks and avoids
// Thread.backtrace().  The full CSL probe is useful for short, idle, or targeted
// captures, but it can destabilize MuMu/houdini when real spin input drives the
// render thread.  Use this probe when the test itself is "tap the real UI and
// observe what the game requests".

const moduleName = "libGameProc.so";

let moduleValue = null;
let sdGmCallback = null;
let lastPlayStart = null;
let eventCountByKind = {};
let lastEmitMsByKind = {};

function emit(kind, fields) {
  eventCountByKind[kind] = (eventCountByKind[kind] || 0) + 1;
  send(
    Object.assign(
      {
        kind,
        unix_ms: Date.now(),
        thread_id: Process.getCurrentThreadId(),
        high_level_call_count_for_kind: eventCountByKind[kind],
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

function findExport(symbol) {
  try {
    return Module.findGlobalExportByName(symbol);
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

function readS32Safe(base, offset) {
  try {
    return base.add(offset).readS32();
  } catch (_) {
    return null;
  }
}

function readU64HexSafe(base, offset) {
  try {
    return "0x" + base.add(offset).readU64().toString(16);
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

function readCStringSafe(pointerValue) {
  try {
    if (pointerValue === null || pointerValue.isNull()) {
      return { text_utf8: "", text_error: "null" };
    }
    return { text_utf8: pointerValue.readUtf8String(), text_error: "" };
  } catch (error) {
    return { text_utf8: "", text_error: String(error) };
  }
}

function describeSoundData(soundData) {
  if (soundData === null || soundData.isNull()) {
    return { sound_data: "0x0" };
  }
  return {
    sound_data: soundData.toString(),
    sound_id_u16_at_0x2: readU16Safe(soundData, 0x2),
    sound_u32_at_0x0: (() => {
      try {
        return soundData.readU32();
      } catch (_) {
        return null;
      }
    })(),
    sound_u32_at_0x4: (() => {
      try {
        return soundData.add(4).readU32();
      } catch (_) {
        return null;
      }
    })(),
  };
}

function describeSlotBody(bodyPointer) {
  const result = {
    slot_body_pointer: bodyPointer === null ? "0x0" : bodyPointer.toString(),
  };
  if (bodyPointer === null || bodyPointer.isNull()) {
    return result;
  }
  const statePointer = readPointerSafe(bodyPointer, 0x4e8);
  result.body_state_pointer =
    statePointer === null || statePointer.isNull() ? "0x0" : statePointer.toString();
  result.body_input_mask = readS32Safe(bodyPointer, 0x408);
  result.body_touch_mask = readS32Safe(bodyPointer, 0x40c);
  result.body_force_main = readS32Safe(bodyPointer, 0x520);
  result.body_force_sub = readS32Safe(bodyPointer, 0x524);
  result.body_force_parameter = readS32Safe(bodyPointer, 0x528);
  if (statePointer !== null && !statePointer.isNull()) {
    result.body_state = readS32Safe(statePointer, 0x0);
    result.body_mode = readS32Safe(statePointer, 0x4);
    result.body_initialized = readS32Safe(statePointer, 0x8);
    result.body_credit = readS32Safe(statePointer, 0x44);
    result.body_bet = readS32Safe(statePointer, 0x58);
    result.body_button_state = readS32Safe(statePointer, 0x74);
    result.body_lever_state = readS32Safe(statePointer, 0x7c);
  }
  return result;
}

function describeSdGmData() {
  if (sdGmCallback === null) {
    return { sdgm_pointer: "0x0", sdgm_error: "fnGetAddrSdGmData unavailable" };
  }
  try {
    const sdGmPointer = sdGmCallback();
    if (sdGmPointer === null || sdGmPointer.isNull()) {
      return { sdgm_pointer: "0x0", sdgm_error: "fnGetAddrSdGmData returned null" };
    }
    return {
      sdgm_pointer: sdGmPointer.toString(),
      sdgm_rx_source_selector_u16_at_0x16e: readU16Safe(sdGmPointer, 0x16e),
      sdgm_rx_source_stage_u16_at_0x170: readU16Safe(sdGmPointer, 0x170),
      sdgm_rx_pre_selector_u16_at_0x0ee: readU16Safe(sdGmPointer, 0x0ee),
      sdgm_rx_pre_stage_u16_at_0x0ec: readU16Safe(sdGmPointer, 0x0ec),
      sdgm_rx_copy_stage_u16_at_0x318: readU16Safe(sdGmPointer, 0x318),
      sdgm_rx_copy_selector_u16_at_0x31a: readU16Safe(sdGmPointer, 0x31a),
      sdgm_source_story_no_u16_at_0x788: readU16Safe(sdGmPointer, 0x788),
      sdgm_ot_at_stryknd_pool0_u16_at_0x1f72: readU16Safe(sdGmPointer, 0x1f72),
      sdgm_ot_at_stryknd_pool1_u16_at_0x1f74: readU16Safe(sdGmPointer, 0x1f74),
      sdgm_ot_at_stryknd_pool2_u16_at_0x1f76: readU16Safe(sdGmPointer, 0x1f76),
      sdgm_ot_at_stryknd_pool3_u16_at_0x1f78: readU16Safe(sdGmPointer, 0x1f78),
      sdgm_ot_at_stryknd_pool4_u16_at_0x1f7a: readU16Safe(sdGmPointer, 0x1f7a),
      sdgm_ot_at_stryknd_pool5_u16_at_0x1f7c: readU16Safe(sdGmPointer, 0x1f7c),
      sdgm_ot_at_stryknd_pool6_u16_at_0x1f7e: readU16Safe(sdGmPointer, 0x1f7e),
      sdgm_ot_at_stryknd_pool7_u16_at_0x1f80: readU16Safe(sdGmPointer, 0x1f80),
      sdgm_ot_at_strychara_pool0_u16_at_0x1f94: readU16Safe(sdGmPointer, 0x1f94),
      sdgm_ot_at_strychara_pool1_u16_at_0x1f96: readU16Safe(sdGmPointer, 0x1f96),
      sdgm_ot_at_strychara_pool2_u16_at_0x1f98: readU16Safe(sdGmPointer, 0x1f98),
      sdgm_ot_at_strychara_pool3_u16_at_0x1f9a: readU16Safe(sdGmPointer, 0x1f9a),
      sdgm_ot_at_strychara_pool4_u16_at_0x1f9c: readU16Safe(sdGmPointer, 0x1f9c),
      sdgm_ot_at_strychara_flag_u8_at_0x1f9e: readU8Safe(sdGmPointer, 0x1f9e),
      sdgm_error: "",
    };
  } catch (error) {
    return { sdgm_pointer: "0x0", sdgm_error: String(error) };
  }
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
    next_event_code_hex_at_0x368: readU64HexSafe(thisPointer, 0x368),
  };
}

function attachEnterLeave(symbol, kind, callbacks) {
  const address = findExport(symbol);
  if (address === null) {
    emit("hook_unavailable", { hook_kind: kind, symbol });
    return null;
  }
  try {
    Interceptor.attach(address, {
      onEnter(args) {
        this.fields = callbacks && callbacks.onEnter ? callbacks.onEnter(args) : {};
        emit(kind + "_enter", Object.assign({ symbol, address: address.toString() }, this.fields));
      },
      onLeave(retval) {
        if (callbacks && callbacks.onLeave) {
          emit(kind + "_leave", callbacks.onLeave(retval, this.fields || {}));
        }
      },
    });
  } catch (error) {
    emit("hook_attach_error", { hook_kind: kind, symbol, address: address.toString(), error: String(error) });
    return null;
  }
  emit("hook_installed", { hook_kind: kind, symbol, address: address.toString() });
  return address;
}

function attachSignal(symbol, kind, callback, options) {
  const address = findExport(symbol);
  if (address === null) {
    emit("hook_unavailable", { hook_kind: kind, symbol });
    return null;
  }
  try {
    Interceptor.attach(address, {
      onEnter(args) {
        if (options && options.rateLimitMs) {
          const now = Date.now();
          const previous = lastEmitMsByKind[kind] || 0;
          if (now - previous < options.rateLimitMs) {
            return;
          }
          lastEmitMsByKind[kind] = now;
        }
        emit(kind, Object.assign({ symbol, address: address.toString() }, callback ? callback(args) : {}));
      },
    });
  } catch (error) {
    emit("hook_attach_error", { hook_kind: kind, symbol, address: address.toString(), error: String(error) });
    return null;
  }
  emit("hook_installed", { hook_kind: kind, symbol, address: address.toString() });
  return address;
}

function installSlotInputHooks() {
  attachEnterLeave("_ZN9CSlotBody3BETEii", "slot_body_bet", {
    onEnter(args) {
      return {
        input_a: toI32(args[1]),
        input_b: toI32(args[2]),
        state_before: describeSlotBody(args[0]),
      };
    },
    onLeave(retval, fields) {
      return {
        retval_i32: toI32(retval),
        state_after: describeSlotBody(fields && fields.state_before ? ptr(fields.state_before.slot_body_pointer) : ptr(0)),
      };
    },
  });
  attachEnterLeave("_ZN9CSlotBody5STARTEii", "slot_body_start", {
    onEnter(args) {
      return {
        input_a: toI32(args[1]),
        input_b: toI32(args[2]),
        state_before: describeSlotBody(args[0]),
      };
    },
    onLeave(retval, fields) {
      return {
        retval_i32: toI32(retval),
        state_after: describeSlotBody(fields && fields.state_before ? ptr(fields.state_before.slot_body_pointer) : ptr(0)),
      };
    },
  });
  attachEnterLeave("_ZN9CSlotBody4STOPEii", "slot_body_stop", {
    onEnter(args) {
      return {
        input_a: toI32(args[1]),
        input_b: toI32(args[2]),
        state_before: describeSlotBody(args[0]),
      };
    },
    onLeave(retval, fields) {
      return {
        retval_i32: toI32(retval),
        state_after: describeSlotBody(fields && fields.state_before ? ptr(fields.state_before.slot_body_pointer) : ptr(0)),
      };
    },
  });
}

function installStoryHooks() {
  attachEnterLeave("fnLot_OT_AT_StryKnd", "lot_ot_at_stryknd", {
    onEnter() {
      return describeSdGmData();
    },
    onLeave() {
      return describeSdGmData();
    },
  });
  attachEnterLeave("fnLot_OT_AT_StryChara", "lot_ot_at_strychara", {
    onEnter() {
      return describeSdGmData();
    },
    onLeave() {
      return describeSdGmData();
    },
  });
  attachEnterLeave("fnRxComDirInfo8", "rxcom_dirinfo8", {
    onEnter(args) {
      const fields = describeSdGmData();
      fields.rxcom_payload_pointer = args[0].toString();
      for (let index = 0; index < 8; index += 1) {
        fields["rxcom_payload_u8_at_" + index] = readU8Safe(args[0], index);
      }
      return fields;
    },
    onLeave() {
      return describeSdGmData();
    },
  });
  attachEnterLeave("fnRxComPreMdl", "rxcom_pre_mdl", {
    onEnter() {
      return describeSdGmData();
    },
    onLeave() {
      return describeSdGmData();
    },
  });
  attachEnterLeave("fnLotDirPreMdl", "lot_dir_pre_mdl", {
    onEnter() {
      return describeSdGmData();
    },
    onLeave() {
      return describeSdGmData();
    },
  });

  for (const [symbol, kind] of [
    ["_ZN21C_ObjStageAT_SP_Story3preEv", "sp_story_pre"],
    ["_ZN21C_ObjStageAT_SP_Story9fnSetDataEv", "sp_story_set_data"],
    ["_ZN21C_ObjStageAT_SP_Story14fnSetEventCodeEv", "sp_story_set_event_code"],
    ["_ZN21C_ObjStageAT_SP_Story13fnSetEvCdBaseEt", "sp_story_set_evcd_base"],
    ["_ZN21C_ObjStageAT_SP_Story13fnSetEvCdNextEt", "sp_story_set_evcd_next"],
    ["_ZN21C_ObjStageAT_SP_Story9fnPlayAnmEv", "sp_story_play_anm"],
  ]) {
    attachSignal(symbol, kind, (args) => describeSpStoryObject(args[0]));
  }
}

function installAudioHooks() {
  attachSignal("_ZN12C_CtrlSndLib17fnReqSndEventCodeEy", "ctrl_snd_req_event_code", (args) => ({
    this_pointer: args[0].toString(),
    event_code_hex: args[1].toString(),
    event_code_i32_low: toI32(args[1]),
  }));
  attachSignal("_ZN12C_CtrlSndLib17fnReqSndSoundCodeEPKch", "ctrl_snd_req_sound_code", (args) => {
    const text = readCStringSafe(args[1]);
    return {
      this_pointer: args[0].toString(),
      sound_code_pointer: args[1].toString(),
      sound_code_text_utf8: text.text_utf8,
      sound_code_text_error: text.text_error,
      arg2_i32: toI32(args[2]),
    };
  });
  attachSignal("_ZN12C_CtrlSndLib17fnReqSndSoundCodeEPKchm", "ctrl_snd_req_sound_code_timed", (args) => {
    const text = readCStringSafe(args[1]);
    return {
      this_pointer: args[0].toString(),
      sound_code_pointer: args[1].toString(),
      sound_code_text_utf8: text.text_utf8,
      sound_code_text_error: text.text_error,
      arg2_i32: toI32(args[2]),
      arg3_i32: toI32(args[3]),
    };
  });
  attachSignal("_ZN6CSLMng9PlayStartEP11SSound_Datai", "csl_mng_play_start", (args) => {
    lastPlayStart = Object.assign(
      {
        this_pointer: args[0].toString(),
        play_index_i32: toI32(args[2]),
      },
      describeSoundData(args[1])
    );
    return lastPlayStart;
  });
  attachSignal("_ZN27CSLAndroidSimpleBufferQueue7EnqueueEPKvj", "queue_enqueue_metadata", (args) => ({
    queue_object: args[0].toString(),
    buffer_pointer: args[1].toString(),
    buffer_bytes: toI32(args[2]),
    last_play_start: lastPlayStart,
  }));

  for (const [symbol, kind] of [
    ["_ZN8C_ObjNml25fnSndRequest_BGM_SEQUENCEEv", "obj_nml_snd_request_bgm_sequence"],
    ["_ZN8C_ObjNml20fnSndRequest_BGM_DIREv", "obj_nml_snd_request_bgm_dir"],
    ["_ZN8C_ObjNml20fnSndRequest_BGM_STGEv", "obj_nml_snd_request_bgm_stg"],
    ["_ZN8C_ObjNml20fnSndRequest_BGM_ENDEv", "obj_nml_snd_request_bgm_end"],
    ["_ZN8C_ObjNml25fnSndRequest_BGM_DIR_NEXTEv", "obj_nml_snd_request_bgm_dir_next"],
    ["_ZN8C_ObjNml26fnSndRequest_BGM_FADE_NEXTEv", "obj_nml_snd_request_bgm_fade_next"],
    ["_ZN8C_ObjNml21fnSndRequest_BGM_FADEEv", "obj_nml_snd_request_bgm_fade"],
    ["_ZN25C_DirectionControllerBase18Macro_SND_BGM_PLAYE32tagDirectionControllerDeviceData", "direction_macro_snd_bgm_play"],
  ]) {
    attachSignal(symbol, kind, (args) => ({ this_pointer: args[0].toString() }), { rateLimitMs: 1000 });
  }
}

setImmediate(function () {
  const calcExport = findExport("_ZN8CScnSlot4CalcEv");
  moduleValue = calcExport === null ? Process.findModuleByName(moduleName) : Process.findModuleByAddress(calcExport);
  if (moduleValue === null) {
    emit("probe_error", { error: "libGameProc.so not loaded" });
    return;
  }
  const sdGmAddress = findExport("fnGetAddrSdGmData");
  if (sdGmAddress !== null) {
    try {
      sdGmCallback = new NativeFunction(sdGmAddress, "pointer", []);
    } catch (error) {
      emit("hook_attach_error", {
        hook_kind: "fnGetAddrSdGmData_callback",
        symbol: "fnGetAddrSdGmData",
        address: sdGmAddress.toString(),
        error: String(error),
      });
    }
  }
  emit("probe_start", {
    architecture: Process.arch,
    platform: Process.platform,
    module_name: moduleValue.name,
    module_base: moduleValue.base.toString(),
    sdgm_callback: sdGmAddress === null ? null : sdGmAddress.toString(),
  });
  installSlotInputHooks();
  installStoryHooks();
  installAudioHooks();
  emit("probe_ready", {});
});
