"use strict";

// Change-only logical input/state observer for reliable ADB spin control.
// It records no image, audio, or arbitrary memory dump.  Non-zero input bits
// are authoritative acceptance evidence for lever/stop taps.

const PROCESS_SYMBOL = "_ZN9CSlotBody7processEiiNS_10eStateModeE";
let eventCount = 0;
let lastStateByBody = {};
let hookInstalled = false;

function emit(kind, fields) {
  eventCount += 1;
  send(Object.assign({
    kind,
    unix_ms: Date.now(),
    thread_id: Process.getCurrentThreadId(),
    event_count: eventCount,
  }, fields || {}));
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

function readPointerSafe(base, offset) {
  try {
    return base.add(offset).readPointer();
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

function readS32Safe(base, offset) {
  try {
    return base.add(offset).readS32();
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

function describeState(body) {
  const result = {
    slot_body_pointer: body === null || body.isNull() ? "0x0" : body.toString(),
  };
  if (body === null || body.isNull()) {
    return result;
  }
  const state = readPointerSafe(body, 0x4e8);
  Object.assign(result, {
    body_state_pointer: state === null || state.isNull() ? "0x0" : state.toString(),
    body_input_mask_i32_at_0x408: readS32Safe(body, 0x408),
    body_touch_mask_i32_at_0x40c: readS32Safe(body, 0x40c),
    body_input_u8_at_0x454: readU8Safe(body, 0x454),
    body_input_u8_at_0x455: readU8Safe(body, 0x455),
    body_input_u8_at_0x456: readU8Safe(body, 0x456),
    body_input_u8_at_0x457: readU8Safe(body, 0x457),
  });
  if (state === null || state.isNull()) {
    return result;
  }
  Object.assign(result, {
    body_state_i32_at_0x00: readS32Safe(state, 0x00),
    body_mode_i32_at_0x04: readS32Safe(state, 0x04),
    body_initialized_i32_at_0x08: readS32Safe(state, 0x08),
    body_credit_i32_at_0x44: readS32Safe(state, 0x44),
    body_bet_i32_at_0x58: readS32Safe(state, 0x58),
    state_u32_at_0x60: readU32Safe(state, 0x60),
    state_u32_at_0x64: readU32Safe(state, 0x64),
    state_u32_at_0x68: readU32Safe(state, 0x68),
    state_u32_at_0x6c: readU32Safe(state, 0x6c),
    state_u32_at_0x70: readU32Safe(state, 0x70),
    body_button_state_i32_at_0x74: readS32Safe(state, 0x74),
    state_u32_at_0x78: readU32Safe(state, 0x78),
    body_lever_state_i32_at_0x7c: readS32Safe(state, 0x7c),
    state_u32_at_0x80: readU32Safe(state, 0x80),
    state_u32_at_0x84: readU32Safe(state, 0x84),
    state_u32_at_0x88: readU32Safe(state, 0x88),
    state_u32_at_0x8c: readU32Safe(state, 0x8c),
  });
  return result;
}

function stateSignature(state) {
  if (!state) {
    return "";
  }
  const stable = Object.assign({}, state);
  // This field is a per-process-call counter and would otherwise make a
  // change-only observer emit every frame.
  delete stable.body_initialized_i32_at_0x08;
  return JSON.stringify(stable);
}

function describeCaller(returnAddress) {
  const result = { return_address: returnAddress.toString() };
  try {
    const moduleValue = Process.findModuleByAddress(returnAddress);
    if (moduleValue !== null) {
      result.return_module = moduleValue.name;
      result.return_module_offset = returnAddress.sub(moduleValue.base).toString();
    }
  } catch (_) {
  }
  try {
    result.return_symbol = DebugSymbol.fromAddress(returnAddress).toString();
  } catch (_) {
  }
  return result;
}

function install() {
  const address = Module.findGlobalExportByName(PROCESS_SYMBOL);
  if (address === null) {
    emit("slot_gate_hook_unavailable", { symbol: PROCESS_SYMBOL });
    return;
  }
  try {
    Interceptor.attach(address, {
      onEnter(args) {
        this.body = args[0];
        this.inputA = toI32(args[1]);
        this.inputB = toI32(args[2]);
        this.requestedMode = toU32(args[3]);
        this.before = describeState(args[0]);
        this.caller = describeCaller(this.returnAddress);
      },
      onLeave(retval) {
        const after = describeState(this.body);
        const key = this.body.toString();
        const signature = stateSignature(after);
        const lastSignature = lastStateByBody[key] || "";
        const inputNonzero = Boolean(this.inputA || this.inputB);
        const changedWithinCall = stateSignature(this.before) !== signature;
        if (inputNonzero || changedWithinCall || signature !== lastSignature) {
          emit("slot_gate_state", Object.assign({
            process_input_a_i32: this.inputA,
            process_input_b_i32: this.inputB,
            process_requested_mode_u32: this.requestedMode,
            process_return_i32: toI32(retval),
            input_nonzero: inputNonzero,
            changed_within_call: changedWithinCall,
            state_before: this.before,
            state_after: after,
          }, this.caller));
        }
        lastStateByBody[key] = signature;
      },
    });
    hookInstalled = true;
    emit("slot_gate_hook_installed", {
      symbol: PROCESS_SYMBOL,
      address: address.toString(),
      emits_change_only: true,
    });
  } catch (error) {
    emit("slot_gate_hook_attach_error", {
      symbol: PROCESS_SYMBOL,
      address: address.toString(),
      error: String(error),
    });
  }
}

setImmediate(function () {
  emit("slot_gate_probe_start", {
    architecture: Process.arch,
    pointer_size: Process.pointerSize,
    evidence_rule: "nonzero_process_input_is_accepted_input",
  });
  install();
  emit("slot_gate_probe_ready", {
    installed: hookInstalled,
  });
});

rpc.exports = {
  status() {
    return {
      event_count: eventCount,
      state_by_body: lastStateByBody,
    };
  },
};
