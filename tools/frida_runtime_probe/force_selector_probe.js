"use strict";

const moduleName = "libGameProc.so";
const forceWindowOffset = 0xbb0;
const symbolOffsets = {
  calc: 0x42412c4,
  touchForce: 0x423c768,
  touchMenu: 0x423d9c4,
  forceSetImage: 0x4233850,
  forceSetVisible: 0x4235798,
  forceGetSelection: 0x4235448,
  forceResetSelection: 0x42332a0,
  forceButtonOk: 0x4233edc,
  debugSelectVisible: 0x426252c,
  uniDebug: 0x4cf3aa1,
  isDebugMode: 0x4c2b499,
  isPause: 0x4c2b496,
  gatCallback: 0x4247574,
  gatStat: 0x4ba2080,
  gatStatSet: 0x4ba2084,
  gatStatEnd: 0x4ba2088,
};

let moduleValue = null;
let slotPointer = null;
let slotBodyPointer = null;
let pendingAction = null;
let pendingRelease = null;
let actionSequence = 0;
let lastObservationSource = null;
let lastForceSetImageValue = null;
let lastForceSetVisibleValue = null;
let lastBodyCalcSignature = null;
let lastGatCallbackLogMs = 0;
let gatDriveFramesRemaining = 0;
let gatDriveFramesRequested = 0;
let gatDriveFramesCompleted = 0;
let gatDriveActive = false;

function emit(kind, fields) {
  send(
    Object.assign(
      {
        kind,
        unix_ms: Date.now(),
        thread_id: Process.getCurrentThreadId(),
      },
      fields || {}
    )
  );
}

function resolve(symbol, fallbackOffset) {
  const exported = Module.findGlobalExportByName(symbol);
  return exported === null ? moduleValue.base.add(fallbackOffset) : exported;
}

function readU8(address) {
  try {
    return address.readU8();
  } catch (_) {
    return null;
  }
}

function readS32(address) {
  try {
    return address.readS32();
  } catch (_) {
    return null;
  }
}

function readPointer(address) {
  try {
    return address.readPointer();
  } catch (_) {
    return null;
  }
}

function snapshot() {
  const result = {
    module_base: moduleValue === null ? null : moduleValue.base.toString(),
    slot_pointer: slotPointer === null ? null : slotPointer.toString(),
    slot_body_pointer:
      slotBodyPointer === null ? null : slotBodyPointer.toString(),
    uni_debug: null,
    is_debug_mode: null,
    is_pause: null,
    gat_stat: null,
    gat_stat_set: null,
    gat_stat_end: null,
  };
  if (moduleValue === null) {
    return result;
  }

  result.uni_debug = readU8(resolve("g_UniDebugSW", symbolOffsets.uniDebug));
  result.is_debug_mode = readU8(resolve("uk_isDebugMode", symbolOffsets.isDebugMode));
  result.is_pause = readU8(resolve("uk_isPause", symbolOffsets.isPause));
  result.gat_stat = readS32(resolve("g_gatStat", symbolOffsets.gatStat));
  result.gat_stat_set = readS32(
    resolve("g_gatStat_set", symbolOffsets.gatStatSet)
  );
  result.gat_stat_end = readS32(
    resolve("g_gatStat_end", symbolOffsets.gatStatEnd)
  );
  if (slotPointer === null) {
    return result;
  }

  const force = slotPointer.add(forceWindowOffset);
  const manager = readPointer(slotPointer.add(0x308));
  result.slot_input_enabled = readU8(slotPointer.add(0x455));
  result.menu_open = readU8(slotPointer.add(0x44c));
  result.menu_draw_offset = readS32(slotPointer.add(0x448));
  result.menu_layout_index = readS32(slotPointer.add(0x450));
  result.force_visible = readU8(force.add(0x10));
  result.force_current_index = readS32(force.add(0x804));
  result.force_selected_index = readS32(force.add(0x810));
  result.force_selection_valid = readU8(force.add(0x814));
  result.force_old_selection_valid = readU8(force.add(0x820));
  result.manager_pointer = manager === null ? null : manager.toString();
  result.manager_gate =
    manager === null || manager.isNull() ? null : readS32(manager.add(0x98));
  if (slotBodyPointer !== null && !slotBodyPointer.isNull()) {
    const bodyState = readPointer(slotBodyPointer.add(0x4e8));
    result.body_state_pointer =
      bodyState === null ? null : bodyState.toString();
    result.body_input_mask = readS32(slotBodyPointer.add(0x408));
    result.body_touch_mask = readS32(slotBodyPointer.add(0x40c));
    result.body_force_main = readS32(slotBodyPointer.add(0x520));
    result.body_force_parameter = readS32(slotBodyPointer.add(0x528));
    if (bodyState !== null && !bodyState.isNull()) {
      result.body_state = readS32(bodyState);
      result.body_mode = readS32(bodyState.add(0x4));
      result.body_initialized = readS32(bodyState.add(0x8));
      result.body_credit = readS32(bodyState.add(0x44));
      result.body_bet = readS32(bodyState.add(0x58));
      result.body_button_state = readS32(bodyState.add(0x74));
      result.body_lever_state = readS32(bodyState.add(0x7c));
    }
  }
  return result;
}

const bodyInputSymbols = {
  body_bet: "_ZN9CSlotBody9touch_BetEi",
  body_lever: "_ZN9CSlotBody11touch_LeverEi",
  body_left_reel: "_ZN9CSlotBody11touch_LReelEi",
  body_center_reel: "_ZN9CSlotBody11touch_CReelEi",
  body_right_reel: "_ZN9CSlotBody11touch_RReelEi",
};

function pressBodyInput(name) {
  if (slotBodyPointer === null || slotBodyPointer.isNull()) {
    throw new Error("CSlotBody instance has not been observed");
  }
  const symbol = bodyInputSymbols[name];
  if (symbol === undefined) {
    throw new Error("unknown body input: " + name);
  }
  const address = resolve(symbol, 0);
  const call = new NativeFunction(address, "void", ["pointer", "int"]);
  call(slotBodyPointer, 1);
  pendingRelease = {
    name,
    symbol,
    address,
    frames: 2,
  };
  emit("body_input_press", {
    input: name,
    symbol,
    address: address.toString(),
    state_after: snapshot(),
  });
}

function runPendingRelease(source) {
  if (pendingRelease === null || source !== "Calc") {
    return;
  }
  pendingRelease.frames -= 1;
  if (pendingRelease.frames > 0) {
    return;
  }
  const release = pendingRelease;
  pendingRelease = null;
  try {
    const call = new NativeFunction(
      release.address,
      "void",
      ["pointer", "int"]
    );
    call(slotBodyPointer, 0);
    emit("body_input_release", {
      input: release.name,
      symbol: release.symbol,
      address: release.address.toString(),
      state_after: snapshot(),
    });
  } catch (error) {
    emit("body_input_release_error", {
      input: release.name,
      error: String(error),
      state: snapshot(),
    });
  }
}

function executeAction(action) {
  const name = action.name;
  const value = action.value;

  if (name === "set_debug") {
    const enabled = value ? 1 : 0;
    resolve("g_UniDebugSW", symbolOffsets.uniDebug).writeU8(enabled);
    resolve("uk_isDebugMode", symbolOffsets.isDebugMode).writeU8(enabled);
  } else if (name === "show_java_debug") {
    const call = new NativeFunction(
      resolve("DebugSelect_Visible", symbolOffsets.debugSelectVisible),
      "void",
      ["int"]
    );
    call(value ? 1 : 0);
  } else {
    if (slotPointer === null) {
      throw new Error("CScnSlot instance has not been observed");
    }
    const force = slotPointer.add(forceWindowOffset);

    if (name === "gat_tick") {
      const call = new NativeFunction(
        resolve("_Z12gat_CallBackv", symbolOffsets.gatCallback),
        "void",
        []
      );
      call();
    } else if (name === "gat_drive") {
      const frames = Number(value);
      if (!Number.isInteger(frames) || frames < 1 || frames > 36000) {
        throw new Error("gat drive frames must be an integer from 1 through 36000");
      }
      gatDriveFramesRemaining = frames;
      gatDriveFramesRequested = frames;
      gatDriveFramesCompleted = 0;
      gatDriveActive = true;
      emit("gat_drive_start", {
        frames_requested: frames,
        state_before: snapshot(),
      });
    } else if (Object.prototype.hasOwnProperty.call(bodyInputSymbols, name)) {
      pressBodyInput(name);
    } else if (name === "set_manager_gate") {
    const manager = readPointer(slotPointer.add(0x308));
    if (manager === null || manager.isNull()) {
      throw new Error("CplayData force gate pointer is unavailable");
    }
    manager.add(0x98).writeS32(value ? 1 : 0);
    } else if (name === "toggle_force") {
      const call = new NativeFunction(
        resolve("_ZN8CScnSlot11touch_ForceEi", symbolOffsets.touchForce),
        "void",
        ["pointer", "int"]
      );
      call(slotPointer, Number(value || 2));
    } else if (name === "toggle_menu") {
      const call = new NativeFunction(
        resolve("_ZN8CScnSlot10touch_MenuEi", symbolOffsets.touchMenu),
        "void",
        ["pointer", "int"]
      );
      call(slotPointer, Number(value || 2));
    } else if (name === "set_force_image") {
      const call = new NativeFunction(
        resolve("_ZN12CForceWindow8setImageEb", symbolOffsets.forceSetImage),
        "void",
        ["pointer", "int"]
      );
      call(force, value ? 1 : 0);
    } else if (name === "set_force_visible") {
      const call = new NativeFunction(
        resolve("_ZN12CForceWindow10setVisibleEb", symbolOffsets.forceSetVisible),
        "void",
        ["pointer", "int"]
      );
      call(force, value ? 1 : 0);
    } else if (name === "reset_force_selection") {
      const call = new NativeFunction(
        resolve("_ZN12CForceWindow19resetSelectionIndexEv", symbolOffsets.forceResetSelection),
        "void",
        ["pointer"]
      );
      call(force);
    } else if (name === "select_force_index") {
      const index = Number(value);
      if (!Number.isInteger(index) || index < 0 || index >= 20) {
        throw new Error("force index must be an integer from 0 through 19");
      }
      force.add(0x810).writeS32(index);
      force.add(0x814).writeU8(1);
    } else if (name === "confirm_force_index") {
      const index = Number(value);
      if (!Number.isInteger(index) || index < 0 || index >= 20) {
        throw new Error("force index must be an integer from 0 through 19");
      }
      if (readU8(force.add(0x808)) !== 1) {
        throw new Error("force window is not initialized and visible");
      }
      force.add(0x760).writeS32(index);
      force.add(0x764).writeS32(index + 1);
      force.add(0x810).writeS32(index);
      force.add(0x814).writeU8(1);
      const call = new NativeFunction(
        resolve("_ZN12CForceWindow10onButtonOKEi", symbolOffsets.forceButtonOk),
        "void",
        ["pointer", "int"]
      );
      call(force, 2);
    } else {
      throw new Error("unknown action: " + name);
    }
  }
}

function runPendingAction(source) {
  if (pendingAction === null) {
    return;
  }
  const action = pendingAction;
  pendingAction = null;
  try {
    executeAction(action);
    emit("action_complete", {
      action_id: action.id,
      action: action.name,
      value: action.value,
      execution_source: source,
      state: snapshot(),
    });
  } catch (error) {
    emit("action_error", {
      action_id: action.id,
      action: action.name,
      value: action.value,
      execution_source: source,
      error: String(error),
      state: snapshot(),
    });
  }
}

function runGatDrive(source) {
  if (
    source !== "Calc" ||
    !gatDriveActive ||
    gatDriveFramesRemaining <= 0
  ) {
    return;
  }

  try {
    const call = new NativeFunction(
      resolve("_Z12gat_CallBackv", symbolOffsets.gatCallback),
      "void",
      []
    );
    call();
    gatDriveFramesRemaining -= 1;
    gatDriveFramesCompleted += 1;

    if (
      gatDriveFramesCompleted === 1 ||
      gatDriveFramesCompleted % 60 === 0
    ) {
      emit("gat_drive_progress", {
        frames_requested: gatDriveFramesRequested,
        frames_completed: gatDriveFramesCompleted,
        frames_remaining: gatDriveFramesRemaining,
        state: snapshot(),
      });
    }

    if (gatDriveFramesRemaining === 0) {
      gatDriveActive = false;
      emit("gat_drive_complete", {
        frames_requested: gatDriveFramesRequested,
        frames_completed: gatDriveFramesCompleted,
        state_after: snapshot(),
      });
    }
  } catch (error) {
    gatDriveActive = false;
    emit("gat_drive_error", {
      frames_requested: gatDriveFramesRequested,
      frames_completed: gatDriveFramesCompleted,
      frames_remaining: gatDriveFramesRemaining,
      error: String(error),
      state: snapshot(),
    });
  }
}

function observeSlot(pointerValue, source) {
  if (pointerValue === null || pointerValue.isNull()) {
    return;
  }
  const changed = slotPointer === null || !slotPointer.equals(pointerValue);
  slotPointer = pointerValue;
  const observedBody = readPointer(slotPointer.add(0x1b98));
  if (observedBody !== null && !observedBody.isNull()) {
    slotBodyPointer = observedBody;
  }
  lastObservationSource = source;
  if (changed) {
    emit("slot_observed", {
      observation_source: source,
      state: snapshot(),
    });
  }
  runPendingAction(source);
  runPendingRelease(source);
  runGatDrive(source);
}

function observeSlotBody(pointerValue, source) {
  if (pointerValue === null || pointerValue.isNull()) {
    return;
  }
  const changed =
    slotBodyPointer === null || !slotBodyPointer.equals(pointerValue);
  slotBodyPointer = pointerValue;
  if (changed) {
    emit("slot_body_observed", {
      observation_source: source,
      state: snapshot(),
    });
  }
}

function attachSlotObserver(symbol, source) {
  const address = Module.findGlobalExportByName(symbol);
  if (address === null) {
    emit("hook_unavailable", { symbol, source });
    return null;
  }
  Interceptor.attach(address, {
    onEnter(args) {
      observeSlot(args[0], source);
    },
  });
  return address;
}

function attachSlotBodyObserver(symbol, source) {
  const address = Module.findGlobalExportByName(symbol);
  if (address === null) {
    emit("hook_unavailable", { symbol, source });
    return null;
  }
  Interceptor.attach(address, {
    onEnter(args) {
      observeSlotBody(args[0], source);
      const signature = [
        args[1].toInt32(),
        args[2].toInt32(),
        args[3].toInt32(),
      ].join(":");
      if (signature !== lastBodyCalcSignature) {
        lastBodyCalcSignature = signature;
        emit("slot_body_calc_state", {
          body_pointer: args[0].toString(),
          state_mode: args[1].toInt32(),
          iterations: args[2].toInt32(),
          paused: args[3].toInt32(),
          state: snapshot(),
        });
      }
    },
  });
  return address;
}

function attachSimpleTrace(symbol, kind, options) {
  const address = Module.findGlobalExportByName(symbol);
  if (address === null) {
    emit("hook_unavailable", { symbol, source: kind });
    return null;
  }
  Interceptor.attach(address, {
    onEnter(args) {
      if (options && options.observeSlot) {
        observeSlot(args[0], kind);
      }
      this.fields = options && options.onEnter ? options.onEnter(args) : {};
      emit(kind, Object.assign({ address: address.toString() }, this.fields));
    },
    onLeave(retval) {
      if (options && options.onLeave) {
        emit(kind + "_return", options.onLeave(retval, this.fields));
      }
    },
  });
  return address;
}

setImmediate(function () {
  const calcExport = Module.findGlobalExportByName("_ZN8CScnSlot4CalcEv");
  if (calcExport !== null) {
    moduleValue = Process.findModuleByAddress(calcExport);
  } else {
    moduleValue = Process.findModuleByName(moduleName);
  }
  if (moduleValue === null || calcExport === null) {
    emit("probe_error", {
      error: "CScnSlot::Calc export is not loaded",
      requested_module: moduleName,
    });
    return;
  }

  const calcAddress = calcExport;
  const touchMenuAddress = resolve("_ZN8CScnSlot10touch_MenuEi", 0x423d9c4);
  const touchForceAddress = resolve("_ZN8CScnSlot11touch_ForceEi", symbolOffsets.touchForce);
  const forceSetImageAddress = resolve(
    "_ZN12CForceWindow8setImageEb",
    symbolOffsets.forceSetImage
  );
  const forceSetVisibleAddress = resolve(
    "_ZN12CForceWindow10setVisibleEb",
    symbolOffsets.forceSetVisible
  );

  const slotObserverAddresses = {
    calc: attachSlotObserver("_ZN8CScnSlot4CalcEv", "Calc"),
    wait: attachSlotObserver("_ZN8CScnSlot4WaitEv", "Wait"),
    react: attachSlotObserver("_ZN8CScnSlot5ReActEv", "ReAct"),
    draw_menu_bar: attachSlotObserver("_ZN8CScnSlot11drawMenuBarEv", "drawMenuBar"),
    set_touch_data: attachSlotObserver("_ZN8CScnSlot12setTouchDataEv", "setTouchData"),
  };
  const traceAddresses = {
    gat_callback: (() => {
      const address = resolve("_Z12gat_CallBackv", symbolOffsets.gatCallback);
      Interceptor.attach(address, {
        onEnter() {
          const now = Date.now();
          if (now - lastGatCallbackLogMs >= 1000) {
            lastGatCallbackLogMs = now;
            emit("gat_callback", {
              address: address.toString(),
              state_before: snapshot(),
            });
          }
        },
      });
      return address;
    })(),
    slot_body_calc: attachSlotBodyObserver(
      "_ZN9CSlotBody4CalcENS_10eStateModeEii",
      "CSlotBody::Calc"
    ),
    slot_body_bet: attachSimpleTrace(
      "_ZN9CSlotBody3BETEii",
      "slot_body_bet",
      {
        onEnter(args) {
          observeSlotBody(args[0], "CSlotBody::BET");
          return {
            input_a: args[1].toInt32(),
            input_b: args[2].toInt32(),
            state_before: snapshot(),
          };
        },
        onLeave(retval) {
          return { result: retval.toInt32(), state_after: snapshot() };
        },
      }
    ),
    slot_body_start: attachSimpleTrace(
      "_ZN9CSlotBody5STARTEii",
      "slot_body_start",
      {
        onEnter(args) {
          observeSlotBody(args[0], "CSlotBody::START");
          return {
            input_a: args[1].toInt32(),
            input_b: args[2].toInt32(),
            state_before: snapshot(),
          };
        },
        onLeave(retval) {
          return { result: retval.toInt32(), state_after: snapshot() };
        },
      }
    ),
    slot_body_stop: attachSimpleTrace(
      "_ZN9CSlotBody4STOPEii",
      "slot_body_stop",
      {
        onEnter(args) {
          observeSlotBody(args[0], "CSlotBody::STOP");
          return {
            input_a: args[1].toInt32(),
            input_b: args[2].toInt32(),
            state_before: snapshot(),
          };
        },
        onLeave(retval) {
          return { result: retval.toInt32(), state_after: snapshot() };
        },
      }
    ),
    on_touch_screen: attachSimpleTrace(
      "_ZN8CScnSlot13onTouchScreenEv",
      "on_touch_screen",
      { observeSlot: true }
    ),
    calc_touch: attachSlotObserver("_ZN8CScnSlot9calcTouchEv", "calcTouch"),
    on_start_init: attachSimpleTrace(
      "_ZN8CScnSlot11onStartInitEv",
      "on_start_init",
      {
        observeSlot: true,
        onEnter() {
          return { state_before: snapshot() };
        },
        onLeave() {
          return { state_after: snapshot() };
        },
      }
    ),
    addon_force_execute: attachSimpleTrace(
      "_ZN8CScnSlot23addonForceSelectExecuteEv",
      "addon_force_execute",
      {
        observeSlot: true,
        onEnter() {
          return { state_before: snapshot() };
        },
        onLeave(retval) {
          return {
            return_index: retval.toInt32(),
            state_after: snapshot(),
          };
        },
      }
    ),
    set_force_main: attachSimpleTrace(
      "_ZN9CSlotBody16setForceMainFlagEi",
      "set_force_main",
      {
        onEnter(args) {
          return {
            slot_body_pointer: args[0].toString(),
            index: args[1].toInt32(),
          };
        },
      }
    ),
    fn_set_force_flag: attachSimpleTrace(
      "_ZN5ID40114fnSetForceFlagEtt",
      "fn_set_force_flag",
      {
        onEnter(args) {
          return {
            kind_u16: args[0].toUInt32() & 0xffff,
            parameter_u16: args[1].toUInt32() & 0xffff,
          };
        },
        onLeave(retval) {
          return { result: retval.toInt32() };
        },
      }
    ),
  };
  Interceptor.attach(touchMenuAddress, {
    onEnter(args) {
      observeSlot(args[0], "touch_Menu");
      emit("touch_menu", {
        slot_pointer: args[0].toString(),
        flags: args[1].toInt32(),
        state_before: snapshot(),
      });
      this.slotPointer = args[0];
    },
    onLeave() {
      observeSlot(this.slotPointer, "touch_Menu");
      emit("touch_menu_return", { state_after: snapshot() });
    },
  });
  Interceptor.attach(touchForceAddress, {
    onEnter(args) {
      observeSlot(args[0], "touch_Force");
      emit("touch_force", {
        slot_pointer: args[0].toString(),
        flags: args[1].toInt32(),
        state_before: snapshot(),
      });
      this.slotPointer = args[0];
    },
    onLeave() {
      observeSlot(this.slotPointer, "touch_Force");
      emit("touch_force_return", { state_after: snapshot() });
    },
  });
  Interceptor.attach(forceSetImageAddress, {
    onEnter(args) {
      this.value = args[1].toInt32();
      this.shouldEmit =
        this.value !== lastForceSetImageValue || this.value !== 0;
      lastForceSetImageValue = this.value;
      if (this.shouldEmit) {
        emit("force_set_image", {
          force_pointer: args[0].toString(),
          value: this.value,
          state_before: snapshot(),
        });
      }
    },
    onLeave() {
      if (this.shouldEmit) {
        emit("force_set_image_return", {
          value: this.value,
          state_after: snapshot(),
        });
      }
    },
  });
  Interceptor.attach(forceSetVisibleAddress, {
    onEnter(args) {
      this.value = args[1].toInt32();
      this.shouldEmit =
        this.value !== lastForceSetVisibleValue || this.value !== 0;
      lastForceSetVisibleValue = this.value;
      if (this.shouldEmit) {
        emit("force_set_visible", {
          force_pointer: args[0].toString(),
          value: this.value,
          state_before: snapshot(),
        });
      }
    },
    onLeave() {
      if (this.shouldEmit) {
        emit("force_set_visible_return", {
          value: this.value,
          state_after: snapshot(),
        });
      }
    },
  });

  emit("probe_ready", {
    architecture: Process.arch,
    module_base: moduleValue.base.toString(),
    calc_address: calcAddress.toString(),
    touch_menu_address: touchMenuAddress.toString(),
    touch_force_address: touchForceAddress.toString(),
    force_set_image_address: forceSetImageAddress.toString(),
    force_set_visible_address: forceSetVisibleAddress.toString(),
    slot_observer_addresses: Object.fromEntries(
      Object.entries(slotObserverAddresses).map(([key, value]) => [
        key,
        value === null ? null : value.toString(),
      ])
    ),
    trace_addresses: Object.fromEntries(
      Object.entries(traceAddresses).map(([key, value]) => [
        key,
        value === null ? null : value.toString(),
      ])
    ),
  });
});

rpc.exports = {
  status() {
    return snapshot();
  },
  queue(action, value) {
    if (pendingAction !== null) {
      throw new Error("another action is still pending");
    }
    actionSequence += 1;
    pendingAction = {
      id: actionSequence,
      name: String(action),
      value,
    };
    if (pendingAction.name === "set_debug" && moduleValue !== null) {
      runPendingAction("rpc");
    }
    return {
      accepted: true,
      action_id: actionSequence,
      state_before: snapshot(),
    };
  },
};
