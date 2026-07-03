"use strict";

// Minimal same-session control helper for SdGmData route experiments.
//
// This script is intentionally narrow: it does not hook renderer paths and does
// not backtrace.  It exposes the same `status()` / `queue(action, value)` RPC
// shape used by runtime_probe_host.py control scripts, and only edits a small
// allow-list of SdGmData offsets that are already under active investigation.

let sdGmCallback = null;
let forceOnLotDirGmStartOnce = null;

const allowedU16Actions = {
  set_sdgm_0x358: 0x358,
  set_sdgm_0x13be: 0x13be,
  set_sdgm_0x1354: 0x1354,
  set_sdgm_0x1358: 0x1358,
  set_sdgm_0x14cc: 0x14cc,
};

const allowedU8Actions = {
  set_sdgm_0x4c8: 0x4c8,
  set_sdgm_0x4c9: 0x4c9,
  set_sdgm_0x4ca: 0x4ca,
  set_sdgm_0x4ce: 0x4ce,
};

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

function findExport(symbol) {
  try {
    return Module.findGlobalExportByName(symbol);
  } catch (_) {
    return null;
  }
}

function sdgmPointer() {
  if (sdGmCallback === null) {
    throw new Error("fnGetAddrSdGmData callback unavailable");
  }
  const pointerValue = sdGmCallback();
  if (pointerValue === null || pointerValue.isNull()) {
    throw new Error("fnGetAddrSdGmData returned null");
  }
  return pointerValue;
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

function snapshot() {
  try {
    const base = sdgmPointer();
    return {
      ok: true,
      sdgm_pointer: base.toString(),
      sdgm_lot_dir_case_u16_at_0x358: readU16Safe(base, 0x358),
      sdgm_lot_dir_aux_u16_at_0x400: readU16Safe(base, 0x400),
      sdgm_lot_dir_aux_u16_at_0x41e: readU16Safe(base, 0x41e),
      sdgm_lot_dir_flag_u8_at_0x4c8: readU8Safe(base, 0x4c8),
      sdgm_lot_dir_flag_u8_at_0x4c9: readU8Safe(base, 0x4c9),
      sdgm_lot_dir_flag_u8_at_0x4ca: readU8Safe(base, 0x4ca),
      sdgm_lot_dir_flag_u8_at_0x4ce: readU8Safe(base, 0x4ce),
      sdgm_lot_stage_u16_at_0x1354: readU16Safe(base, 0x1354),
      sdgm_lot_substage_u16_at_0x1358: readU16Safe(base, 0x1358),
      sdgm_lot_mode_u8_at_0x135e: readU8Safe(base, 0x135e),
      sdgm_lot_dispatch_u16_at_0x13be: readU16Safe(base, 0x13be),
      sdgm_lot_dispatch_prev0_u16_at_0x13c0: readU16Safe(base, 0x13c0),
      sdgm_lot_dispatch_prev1_u16_at_0x13c2: readU16Safe(base, 0x13c2),
      sdgm_lot_dispatch_prev2_u16_at_0x13c4: readU16Safe(base, 0x13c4),
      sdgm_lot_start_gate_u16_at_0x14cc: readU16Safe(base, 0x14cc),
      sdgm_lot_stage_gate_u16_at_0x14e2: readU16Safe(base, 0x14e2),
      sdgm_lot_stage_gate_u16_at_0x14e4: readU16Safe(base, 0x14e4),
      sdgm_lot_gate_u16_at_0x15a4: readU16Safe(base, 0x15a4),
      sdgm_lot_gate_u8_at_0x1676: readU8Safe(base, 0x1676),
    };
  } catch (error) {
    return {
      ok: false,
      error: String(error),
    };
  }
}

function writeU16(offset, value) {
  const numberValue = Number(value);
  if (!Number.isInteger(numberValue) || numberValue < 0 || numberValue > 0xffff) {
    throw new Error("u16 value out of range: " + value);
  }
  const base = sdgmPointer();
  const before = readU16Safe(base, offset);
  base.add(offset).writeU16(numberValue);
  const after = readU16Safe(base, offset);
  return { offset, before, after };
}

function writeU8(offset, value) {
  const numberValue = Number(value);
  if (!Number.isInteger(numberValue) || numberValue < 0 || numberValue > 0xff) {
    throw new Error("u8 value out of range: " + value);
  }
  const base = sdgmPointer();
  const before = readU8Safe(base, offset);
  base.add(offset).writeU8(numberValue);
  const after = readU8Safe(base, offset);
  return { offset, before, after };
}

function applyAction(action, value) {
  if (action === "arm_force_sdgm_0x358_on_lot_dir_gm_start_once") {
    const numberValue = Number(value);
    if (!Number.isInteger(numberValue) || numberValue < 0 || numberValue > 0xffff) {
      throw new Error("u16 value out of range: " + value);
    }
    forceOnLotDirGmStartOnce = numberValue;
    return { armed: true, action, value: numberValue };
  }
  if (Object.prototype.hasOwnProperty.call(allowedU16Actions, action)) {
    return writeU16(allowedU16Actions[action], value);
  }
  if (Object.prototype.hasOwnProperty.call(allowedU8Actions, action)) {
    return writeU8(allowedU8Actions[action], value);
  }
  throw new Error("unsupported SdGmData control action: " + action);
}

rpc.exports = {
  status() {
    return snapshot();
  },
  queue(action, value) {
    const before = snapshot();
    const writeResult = applyAction(String(action), value);
    const after = snapshot();
    emit("sdgm_control_action", {
      action: String(action),
      value: Number(value),
      write_result: writeResult,
      before,
      after,
    });
    return {
      accepted: true,
      action: String(action),
      value: Number(value),
      write_result: writeResult,
      after,
    };
  },
};

setImmediate(function () {
  const sdGmAddress = findExport("fnGetAddrSdGmData");
  if (sdGmAddress !== null) {
    try {
      sdGmCallback = new NativeFunction(sdGmAddress, "pointer", []);
    } catch (error) {
      emit("sdgm_control_error", {
        error: String(error),
        symbol: "fnGetAddrSdGmData",
        address: sdGmAddress.toString(),
      });
      return;
    }
  }
  const lotDirGmStartAddress = findExport("fnLotDirGmStart");
  if (lotDirGmStartAddress !== null) {
    try {
      Interceptor.attach(lotDirGmStartAddress, {
        onEnter() {
          if (forceOnLotDirGmStartOnce === null) {
            return;
          }
          const requestedValue = forceOnLotDirGmStartOnce;
          forceOnLotDirGmStartOnce = null;
          const before = snapshot();
          let writeResult = null;
          let error = "";
          try {
            writeResult = writeU16(0x358, requestedValue);
          } catch (writeError) {
            error = String(writeError);
          }
          emit("sdgm_control_force_on_lot_dir_gm_start", {
            value: requestedValue,
            before,
            write_result: writeResult,
            after: snapshot(),
            error,
          });
        },
      });
    } catch (error) {
      emit("sdgm_control_hook_error", {
        symbol: "fnLotDirGmStart",
        address: lotDirGmStartAddress.toString(),
        error: String(error),
      });
    }
  }
  emit("sdgm_control_ready", {
    fnGetAddrSdGmData: sdGmAddress === null ? null : sdGmAddress.toString(),
    fnLotDirGmStart: lotDirGmStartAddress === null ? null : lotDirGmStartAddress.toString(),
    status: snapshot(),
  });
});
