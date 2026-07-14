"use strict";

// Minimal observer for natural SP-story hunts.  Its evidence surface is kept
// deliberately small: the real ID401 dispatch batch, the resolved scene/event
// code, and one low-frequency SP-story lottery boundary.

const MODULE_NAME = "libGameProc.so";
const SYMBOLS = Object.freeze({
  getCmdBuf: "_ZN5ID4019getCmdBufEPhi",
  accessSubProcess: "_ZN5ID40116accessSubProcessEPh",
  requestScene: "_ZN9C_AnmBase10fnReqSceneEyhtt",
  requestSoundEventCode: "_ZN12C_CtrlSndLib17fnReqSndEventCodeEy",
  lotSpStoryKind: "fnLot_OT_AT_SpStryKnd",
  getSdGmData: "fnGetAddrSdGmData",
});

let getCmdBufCallCount = 0;
let sdGmCallback = null;
const eventCountByKind = Object.create(null);
const hookStatusByKind = Object.create(null);
const latestGetCmdBufByThread = Object.create(null);

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

function findExport(symbol) {
  try {
    return Module.findGlobalExportByName(symbol);
  } catch (_) {
    return null;
  }
}

function findGameModule() {
  try {
    const named = Process.findModuleByName(MODULE_NAME);
    if (named !== null) {
      return named;
    }
  } catch (_) {
  }

  // Houdini may expose the ARM64 ELF mapping under the split APK name rather
  // than libGameProc.so.  Resolve the owner of a game-specific export so the
  // evidence identity follows code provenance, not the loader's display name.
  const sentinels = [
    SYMBOLS.getCmdBuf,
    SYMBOLS.accessSubProcess,
    SYMBOLS.requestScene,
    SYMBOLS.lotSpStoryKind,
  ];
  for (const symbol of sentinels) {
    const address = findExport(symbol);
    if (address === null) {
      continue;
    }
    try {
      const owner = Process.findModuleByAddress(address);
      if (owner !== null) {
        return owner;
      }
    } catch (_) {
    }
  }
  return null;
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

function pointerText(value) {
  try {
    return value === null || value.isNull() ? "0x0" : value.toString();
  } catch (_) {
    return "0x0";
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

function describeReturnAddress(returnAddress) {
  const result = {
    return_address: pointerText(returnAddress),
    return_module: "",
    return_module_offset: null,
    return_symbol: "",
  };
  if (returnAddress === null) {
    return result;
  }
  try {
    const owner = Process.findModuleByAddress(returnAddress);
    if (owner !== null) {
      result.return_module = owner.name;
      result.return_module_offset = returnAddress.sub(owner.base).toString();
    }
  } catch (_) {
  }
  try {
    const symbol = DebugSymbol.fromAddress(returnAddress);
    if (symbol !== null && symbol.name) {
      result.return_symbol = symbol.name;
    }
  } catch (_) {
  }
  return result;
}

function markHook(kind, symbol, status, address, error) {
  const row = {
    hook_kind: kind,
    symbol,
    status,
    address: address === null ? null : address.toString(),
  };
  if (error) {
    row.error = String(error);
  }
  hookStatusByKind[kind] = row;
  if (status === "installed") {
    emit("hook_installed", row);
  } else if (status === "unavailable") {
    emit("hook_unavailable", row);
  } else {
    emit("hook_attach_error", row);
  }
}

function attachEnterLeave(symbol, hookKind, enterKind, leaveKind, callbacks) {
  const address = findExport(symbol);
  if (address === null) {
    markHook(hookKind, symbol, "unavailable", null, "export not found");
    return false;
  }
  try {
    Interceptor.attach(address, {
      onEnter(args) {
        this.probeReturnAddress = this.returnAddress;
        this.probeFields = callbacks && callbacks.onEnter
          ? callbacks.onEnter.call(this, args)
          : {};
        emit(
          enterKind,
          Object.assign(
            { symbol, address: address.toString() },
            describeReturnAddress(this.probeReturnAddress),
            this.probeFields || {}
          )
        );
      },
      onLeave(retval) {
        const leaveFields = callbacks && callbacks.onLeave
          ? callbacks.onLeave.call(this, retval, this.probeFields || {})
          : {};
        emit(
          leaveKind,
          Object.assign(
            { symbol, address: address.toString() },
            describeReturnAddress(this.probeReturnAddress),
            leaveFields || {}
          )
        );
      },
    });
  } catch (error) {
    markHook(hookKind, symbol, "error", address, error);
    return false;
  }
  markHook(hookKind, symbol, "installed", address, null);
  return true;
}

function attachSignal(symbol, kind, callback) {
  const address = findExport(symbol);
  if (address === null) {
    markHook(kind, symbol, "unavailable", null, "export not found");
    return false;
  }
  try {
    Interceptor.attach(address, {
      onEnter(args) {
        emit(
          kind,
          Object.assign(
            { symbol, address: address.toString() },
            describeReturnAddress(this.returnAddress),
            callback ? callback(args) : {}
          )
        );
      },
    });
  } catch (error) {
    markHook(kind, symbol, "error", address, error);
    return false;
  }
  markHook(kind, symbol, "installed", address, null);
  return true;
}

function describeSdGmData() {
  if (sdGmCallback === null) {
    return { sdgm_pointer: "0x0", sdgm_error: "fnGetAddrSdGmData unavailable" };
  }
  try {
    const data = sdGmCallback();
    if (data === null || data.isNull()) {
      return { sdgm_pointer: "0x0", sdgm_error: "fnGetAddrSdGmData returned null" };
    }
    return {
      sdgm_pointer: data.toString(),
      sdgm_sp_story_special_case_u16_at_0x35e: readU16Safe(data, 0x35e),
      sdgm_sp_story_enable_u16_at_0x45a: readU16Safe(data, 0x45a),
      sdgm_sp_story_probability_selector_u16_at_0x592: readU16Safe(data, 0x592),
      sdgm_lot_dispatch_u16_at_0x13be: readU16Safe(data, 0x13be),
      sdgm_lot_dispatch_prev2_u16_at_0x13c4: readU16Safe(data, 0x13c4),
      sdgm_lot_start_gate_u16_at_0x14cc: readU16Safe(data, 0x14cc),
      sdgm_sp_story_kind_u16_at_0x1f82: readU16Safe(data, 0x1f82),
      sdgm_sp_story_lottery_result_u16_at_0x2fdc: readU16Safe(data, 0x2fdc),
      sdgm_error: "",
    };
  } catch (error) {
    return { sdgm_pointer: "0x0", sdgm_error: String(error) };
  }
}

function installGetCmdBufHook() {
  return attachEnterLeave(
    SYMBOLS.getCmdBuf,
    "id401_get_cmd_buf",
    "id401_get_cmd_buf_enter",
    "id401_get_cmd_buf_leave",
    {
      onEnter(args) {
        getCmdBufCallCount += 1;
        const threadId = Process.getCurrentThreadId();
        return {
          id401_get_cmd_buf_call_count: getCmdBufCallCount,
          id401_get_cmd_buf_enter_thread_id: threadId,
          id401_get_cmd_buf_dest: pointerText(args[0]),
          id401_get_cmd_buf_len: toI32(args[1]),
        };
      },
      onLeave(_retval, fields) {
        const threadId = Process.getCurrentThreadId();
        const metadata = {
          id401_get_cmd_buf_call_count: fields.id401_get_cmd_buf_call_count,
          id401_get_cmd_buf_enter_thread_id: fields.id401_get_cmd_buf_enter_thread_id,
          id401_get_cmd_buf_leave_thread_id: threadId,
          id401_command_buffer_pointer: fields.id401_get_cmd_buf_dest,
          id401_command_buffer_length: fields.id401_get_cmd_buf_len,
          id401_command_buffer_packets: [],
        };
        latestGetCmdBufByThread[String(threadId)] = metadata;
        return metadata;
      },
    }
  );
}

function installAccessSubProcessHook() {
  return attachSignal(SYMBOLS.accessSubProcess, "id401_access_subprocess", (args) => {
    const packet = args[0];
    const fields = {
      id401_packet_pointer: pointerText(packet),
    };
    let complete = packet !== null && !packet.isNull();
    for (let index = 0; index < 8; index += 1) {
      const value = complete ? readU8Safe(packet, index) : null;
      fields["id401_raw_packet_u8_at_" + index] = value;
      if (value === null) {
        complete = false;
      }
    }
    fields.id401_raw_packet_complete = complete;
    if (complete) {
      fields.id401_packet_id = fields.id401_raw_packet_u8_at_0 & 0x7f;
    } else {
      fields.id401_packet_id = null;
    }
    const threadMetadata = latestGetCmdBufByThread[String(Process.getCurrentThreadId())];
    if (threadMetadata) {
      fields.id401_correlated_get_cmd_buf_call_count =
        threadMetadata.id401_get_cmd_buf_call_count;
    }
    return fields;
  });
}

function installEventCodeHooks() {
  const directionInstalled = attachSignal(
    SYMBOLS.requestScene,
    "direction_scene_request",
    (args) => ({
      animation_object: pointerText(args[0]),
      event_code_hex: args[1].toString(),
      request_arg2_u8: toU32(args[2]) & 0xff,
      request_arg3_u16: toU32(args[3]) & 0xffff,
      request_arg4_u16: toU32(args[4]) & 0xffff,
    })
  );
  const soundInstalled = attachSignal(
    SYMBOLS.requestSoundEventCode,
    "ctrl_snd_req_event_code",
    (args) => ({
      this_pointer: pointerText(args[0]),
      event_code_hex: args[1].toString(),
      event_code_i32_low: toI32(args[1]),
    })
  );
  return { directionInstalled, soundInstalled };
}

function installLotteryHook() {
  return attachEnterLeave(
    SYMBOLS.lotSpStoryKind,
    "lot_sp_story_kind",
    "lot_sp_story_kind_enter",
    "lot_sp_story_kind_leave",
    {
      onEnter() {
        return describeSdGmData();
      },
      onLeave() {
        return describeSdGmData();
      },
    }
  );
}

setImmediate(function () {
  const moduleValue = findGameModule();
  if (moduleValue === null || Process.arch !== "arm64" || Process.pointerSize !== 8) {
    emit("probe_error", {
      error: moduleValue === null ? "libGameProc.so not loaded" : "unsupported ABI",
      architecture: Process.arch,
      pointer_size: Process.pointerSize,
    });
    emit("sp_story_dispatch_hunt_probe_ready", {
      installed: false,
      hook_status: hookStatusByKind,
    });
    return;
  }

  const sdGmAddress = findExport(SYMBOLS.getSdGmData);
  if (sdGmAddress !== null) {
    try {
      sdGmCallback = new NativeFunction(sdGmAddress, "pointer", []);
      emit("dependency_ready", {
        dependency_kind: "sdgm_callback",
        symbol: SYMBOLS.getSdGmData,
        address: sdGmAddress.toString(),
      });
    } catch (error) {
      emit("dependency_error", {
        dependency_kind: "sdgm_callback",
        symbol: SYMBOLS.getSdGmData,
        address: sdGmAddress.toString(),
        error: String(error),
      });
    }
  } else {
    emit("dependency_unavailable", {
      dependency_kind: "sdgm_callback",
      symbol: SYMBOLS.getSdGmData,
    });
  }

  emit("sp_story_dispatch_hunt_probe_start", {
    architecture: Process.arch,
    platform: Process.platform,
    logical_module_name: MODULE_NAME,
    module_name: moduleValue.name,
    module_path: moduleValue.path,
    module_base: moduleValue.base.toString(),
  });

  const getCmdBufInstalled = installGetCmdBufHook();
  const accessInstalled = installAccessSubProcessHook();
  const eventHooks = installEventCodeHooks();
  const lotteryInstalled = installLotteryHook();
  const requiredInstalled =
    getCmdBufInstalled && accessInstalled && eventHooks.directionInstalled;

  emit("sp_story_dispatch_hunt_probe_ready", {
    installed: requiredInstalled,
    required_hooks_installed: requiredInstalled,
    optional_sound_event_hook_installed: eventHooks.soundInstalled,
    optional_lottery_hook_installed: lotteryInstalled,
    hook_status: hookStatusByKind,
    evidence_policy: "real_dispatch_packets_and_exact_event_codes_only",
  });
});
