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
let pioTaskSearchCallback = null;
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
      sdgm_rx_dirinfo3_payload6_copy_u16_at_0x130: readU16Safe(sdGmPointer, 0x130),
      sdgm_rx_dirinfo3_payload6_premdl_copy_u16_at_0x0a8: readU16Safe(sdGmPointer, 0x0a8),
      sdgm_rx_dirinfo3_payload6_premdl_copy_u16_at_0x184: readU16Safe(sdGmPointer, 0x184),
      sdgm_rx_pre_selector_u16_at_0x0ee: readU16Safe(sdGmPointer, 0x0ee),
      sdgm_rx_pre_stage_u16_at_0x0ec: readU16Safe(sdGmPointer, 0x0ec),
      sdgm_rx_copy_stage_u16_at_0x318: readU16Safe(sdGmPointer, 0x318),
      sdgm_rx_copy_selector_u16_at_0x31a: readU16Safe(sdGmPointer, 0x31a),
      sdgm_lot_dir_case_u16_at_0x358: readU16Safe(sdGmPointer, 0x358),
      sdgm_lot_dir_aux_u16_at_0x400: readU16Safe(sdGmPointer, 0x400),
      sdgm_lot_dir_aux_u16_at_0x41e: readU16Safe(sdGmPointer, 0x41e),
      sdgm_lot_dir_flag_u8_at_0x4c8: readU8Safe(sdGmPointer, 0x4c8),
      sdgm_lot_dir_flag_u8_at_0x4c9: readU8Safe(sdGmPointer, 0x4c9),
      sdgm_lot_dir_flag_u8_at_0x4ca: readU8Safe(sdGmPointer, 0x4ca),
      sdgm_lot_dir_flag_u8_at_0x4ce: readU8Safe(sdGmPointer, 0x4ce),
      sdgm_source_story_no_u16_at_0x788: readU16Safe(sdGmPointer, 0x788),
      sdgm_lot_stage_u16_at_0x1354: readU16Safe(sdGmPointer, 0x1354),
      sdgm_lot_substage_u16_at_0x1358: readU16Safe(sdGmPointer, 0x1358),
      sdgm_lot_mode_u8_at_0x135e: readU8Safe(sdGmPointer, 0x135e),
      sdgm_lot_dispatch_u16_at_0x13be: readU16Safe(sdGmPointer, 0x13be),
      sdgm_lot_dispatch_prev0_u16_at_0x13c0: readU16Safe(sdGmPointer, 0x13c0),
      sdgm_lot_dispatch_prev1_u16_at_0x13c2: readU16Safe(sdGmPointer, 0x13c2),
      sdgm_lot_dispatch_prev2_u16_at_0x13c4: readU16Safe(sdGmPointer, 0x13c4),
      sdgm_lot_start_gate_u16_at_0x14cc: readU16Safe(sdGmPointer, 0x14cc),
      sdgm_lot_stage_gate_u16_at_0x14e2: readU16Safe(sdGmPointer, 0x14e2),
      sdgm_lot_stage_gate_u16_at_0x14e4: readU16Safe(sdGmPointer, 0x14e4),
      sdgm_lot_gate_u16_at_0x15a4: readU16Safe(sdGmPointer, 0x15a4),
      sdgm_lot_gate_u8_at_0x1676: readU8Safe(sdGmPointer, 0x1676),
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

function readU8VectorSafe(base, offset, length) {
  const values = [];
  if (base === null || base.isNull()) {
    return values;
  }
  for (let index = 0; index < length; index += 1) {
    values.push(readU8Safe(base, offset + index));
  }
  return values;
}

function describeID401CommandRecord(raw, offset) {
  const first = raw.length > 0 && raw[0] !== null ? raw[0] : 0;
  const packetId = first & 0x7f;
  const record = {
    offset,
    raw,
    packet_id: packetId,
    is_dirinfo3_lottery_dispatch_candidate: packetId === 19 && raw.length > 1 && raw[1] === 8,
  };
  try {
    const taskEntry = describeID401TaskEntry(packetId);
    record.callback0_symbol = taskEntry.id401_callback0_symbol || "";
    record.callback1_symbol = taskEntry.id401_callback1_symbol || "";
  } catch (_) {
  }
  return record;
}

function readID401CommandRecords(base, maxBytes, maxRecords) {
  const records = [];
  if (base === null || base.isNull()) {
    return records;
  }
  const limit = Math.max(0, Math.min(maxBytes, 0xc00));
  for (let offset = 0; offset + 8 <= limit && records.length < maxRecords; offset += 8) {
    const raw = readU8VectorSafe(base, offset, 8);
    if (raw.length !== 8) {
      continue;
    }
    let hasNonZero = false;
    for (let index = 0; index < raw.length; index += 1) {
      if (raw[index] !== null && raw[index] !== 0) {
        hasNonZero = true;
        break;
      }
    }
    if (!hasNonZero || raw[0] === 0) {
      continue;
    }
    records.push(describeID401CommandRecord(raw, offset));
  }
  return records;
}

function describeID401CommandState(thisPointer) {
  if (thisPointer === null || thisPointer.isNull()) {
    return { id401_lc701a_this: "0x0" };
  }
  const pendingLen = readU8Safe(thisPointer, 0xf0fe);
  const stagingBytes = pendingLen === null ? 0x100 : Math.max(8, Math.min(pendingLen, 0x100));
  return {
    id401_lc701a_this: thisPointer.toString(),
    id401_pc_u16_at_0x20: readU16Safe(thisPointer, 0x20),
    id401_command_queue_flag_u8_at_0x200ed: readU8Safe(thisPointer, 0x200ed),
    id401_command_queue_tail_u16_at_0x20cee: readU16Safe(thisPointer, 0x20cee),
    id401_pending_len_u8_at_0xf0fe: pendingLen,
    id401_staging_packets_at_0xf298: readID401CommandRecords(thisPointer.add(0xf298), stagingBytes, 8),
    id401_queue_packets_at_0x200ee: readID401CommandRecords(thisPointer.add(0x200ee), 0xc00, 16),
  };
}

function id401CommandPacketSignature(packets) {
  if (!packets || !packets.length) {
    return "";
  }
  const rows = [];
  for (let index = 0; index < packets.length; index += 1) {
    const packet = packets[index];
    rows.push(String(packet.offset) + ":" + packet.raw.join(","));
  }
  return rows.join("|");
}

function id401CommandBufferSignature(state) {
  if (!state) {
    return "";
  }
  return [
    state.id401_pending_len_u8_at_0xf0fe,
    state.id401_command_queue_flag_u8_at_0x200ed,
    state.id401_command_queue_tail_u16_at_0x20cee,
    id401CommandPacketSignature(state.id401_staging_packets_at_0xf298 || []),
    id401CommandPacketSignature(state.id401_queue_packets_at_0x200ee || []),
  ].join("||");
}

function attachID401CommandStateChange(symbol, kind) {
  const address = findExport(symbol);
  if (address === null) {
    emit("hook_unavailable", { hook_kind: kind, symbol });
    return null;
  }
  try {
    Interceptor.attach(address, {
      onEnter(args) {
        this.thisPointer = args[0];
        this.returnAddressValue = this.returnAddress;
        this.stateBefore = describeID401CommandState(args[0]);
        this.signatureBefore = id401CommandBufferSignature(this.stateBefore);
      },
      onLeave(retval) {
        const stateAfter = describeID401CommandState(this.thisPointer);
        const signatureAfter = id401CommandBufferSignature(stateAfter);
        if (signatureAfter !== this.signatureBefore) {
          emit(
            kind + "_command_state_change",
            Object.assign(
              {
                symbol,
                address: address.toString(),
                retval_i32: toI32(retval),
                command_signature_before: this.signatureBefore,
                command_signature_after: signatureAfter,
                state_before: this.stateBefore,
                state_after: stateAfter,
              },
              describeReturnAddress(this.returnAddressValue)
            )
          );
        }
      },
    });
  } catch (error) {
    emit("hook_attach_error", { hook_kind: kind, symbol, address: address.toString(), error: String(error) });
    return null;
  }
  emit("hook_installed", { hook_kind: kind, symbol, address: address.toString(), command_state_change_only: true });
  return address;
}

function describeID401CopiedCommandBuffer(bufferPointer, lengthValue) {
  if (bufferPointer === null || bufferPointer.isNull()) {
    return { id401_command_buffer_pointer: "0x0", id401_command_buffer_packets: [] };
  }
  const lengthLimit = lengthValue === null ? 0xc00 : Math.max(0, Math.min(lengthValue, 0xc00));
  return {
    id401_command_buffer_pointer: bufferPointer.toString(),
    id401_command_buffer_length: lengthLimit,
    id401_command_buffer_packets: readID401CommandRecords(bufferPointer, lengthLimit, 32),
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
        emit(
          kind + "_enter",
          Object.assign(
            { symbol, address: address.toString() },
            describeReturnAddress(this.returnAddress),
            this.fields
          )
        );
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

function describeReturnAddress(returnAddress) {
  const result = {
    return_address: returnAddress === null ? "0x0" : returnAddress.toString(),
    return_module: "",
    return_module_offset: null,
    return_symbol: "",
  };
  if (returnAddress === null) {
    return result;
  }
  try {
    const moduleValue = Process.findModuleByAddress(returnAddress);
    if (moduleValue !== null) {
      result.return_module = moduleValue.name;
      result.return_module_offset = returnAddress.sub(moduleValue.base).toString();
    }
  } catch (_) {
  }
  try {
    const debugSymbol = DebugSymbol.fromAddress(returnAddress);
    if (debugSymbol !== null && debugSymbol.name) {
      result.return_symbol = debugSymbol.name;
    }
  } catch (_) {
  }
  return result;
}

function describePointer(prefix, pointerValue) {
  const result = {};
  result[prefix] = pointerValue === null || pointerValue.isNull() ? "0x0" : pointerValue.toString();
  result[prefix + "_symbol"] = "";
  result[prefix + "_module"] = "";
  result[prefix + "_module_offset"] = null;
  if (pointerValue === null || pointerValue.isNull()) {
    return result;
  }
  try {
    const pointerModule = Process.findModuleByAddress(pointerValue);
    if (pointerModule !== null) {
      result[prefix + "_module"] = pointerModule.name;
      result[prefix + "_module_offset"] = pointerValue.sub(pointerModule.base).toString();
    }
  } catch (_) {
  }
  try {
    const debugSymbol = DebugSymbol.fromAddress(pointerValue);
    if (debugSymbol !== null && debugSymbol.name) {
      result[prefix + "_symbol"] = debugSymbol.name;
    }
  } catch (_) {
  }
  return result;
}

function describeID401TaskEntry(packetId) {
  const result = {
    id401_packet_id: packetId,
    id401_task_entry: "0x0",
  };
  if (pioTaskSearchCallback === null) {
    result.id401_task_error = "fnPioTaskTbl_SearchTblApp unavailable";
    return result;
  }
  try {
    const entry = pioTaskSearchCallback(packetId);
    result.id401_task_entry = entry === null || entry.isNull() ? "0x0" : entry.toString();
    if (entry === null || entry.isNull()) {
      return result;
    }
    for (let index = 0; index < 4; index += 1) {
      const callbackPointer = readPointerSafe(entry, 0x8 + index * 0x8);
      Object.assign(result, describePointer("id401_callback" + index, callbackPointer || ptr(0)));
    }
  } catch (error) {
    result.id401_task_error = String(error);
  }
  return result;
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
  attachEnterLeave("_ZN5ID4019getCmdBufEPhi", "id401_get_cmd_buf", {
    onEnter(args) {
      return {
        id401_get_cmd_buf_dest: args[0].toString(),
        id401_get_cmd_buf_len: toI32(args[1]),
      };
    },
    onLeave(_retval, fields) {
      return describeID401CopiedCommandBuffer(
        ptr(fields.id401_get_cmd_buf_dest || "0x0"),
        fields.id401_get_cmd_buf_len
      );
    },
  });
  attachEnterLeave("_ZN5ID40111LC701A_SLOT12mn_getCmdBufEPhi", "id401_mn_get_cmd_buf", {
    onEnter(args) {
      return {
        id401_mn_get_cmd_buf_dest: args[1].toString(),
        id401_mn_get_cmd_buf_len: toI32(args[2]),
        state_before: describeID401CommandState(args[0]),
      };
    },
    onLeave(_retval, fields) {
      return {
        state_after: fields && fields.state_before ? describeID401CommandState(ptr(fields.state_before.id401_lc701a_this)) : {},
        copied_buffer: describeID401CopiedCommandBuffer(
          ptr(fields.id401_mn_get_cmd_buf_dest || "0x0"),
          fields.id401_mn_get_cmd_buf_len
        ),
      };
    },
  });
  attachEnterLeave("_ZN5ID40111LC701A_SLOT16_USER_LABEL_WORKEv", "id401_user_label_work", {
    onEnter(args) {
      return {
        state_before: describeID401CommandState(args[0]),
      };
    },
    onLeave(retval, fields) {
      return {
        retval_i32: toI32(retval),
        state_after: fields && fields.state_before ? describeID401CommandState(ptr(fields.state_before.id401_lc701a_this)) : {},
      };
    },
  });
  attachEnterLeave("_ZN5ID40111LC701A_SLOT14SET_BANKBUFFEREv", "id401_set_bankbuffer", {
    onEnter(args) {
      return {
        state_before: describeID401CommandState(args[0]),
      };
    },
    onLeave(_retval, fields) {
      return {
        state_after: fields && fields.state_before ? describeID401CommandState(ptr(fields.state_before.id401_lc701a_this)) : {},
      };
    },
  });
  [
    ["_ZN5ID4017CLC701A5_OUTIEib", "lc701a_outi"],
    ["_ZN5ID4017CLC701A6_OUTICEib", "lc701a_outic"],
    ["_ZN5ID4017CLC701A3_INEv", "lc701a_in"],
    ["_ZN5ID4017CLC701A4_INIEib", "lc701a_ini"],
    ["_ZN5ID4017CLC701A5_INICEib", "lc701a_inic"],
    ["_ZN5ID4017CLC701A3_JPEt", "lc701a_jp"],
    ["_ZN5ID4017CLC701A4_RETEv", "lc701a_ret"],
    ["_ZN5ID4017CLC701A6_RETEXEv", "lc701a_retex"],
    ["_ZN5ID4017CLC701A8ASM_0xA7Ev", "lc701a_asm_a7"],
    ["_ZN5ID4017CLC701A8ASM_0xAFEv", "lc701a_asm_af"],
    ["_ZN5ID4017CLC701A8ASM_0xF8Ev", "lc701a_asm_f8"],
    ["_ZN5ID4017CLC701A15SET_ENC_SUBFUNCEv", "lc701a_set_enc_subfunc"],
    ["_ZN5ID4017CLC701A17RESET_ENC_SUBFUNCEv", "lc701a_reset_enc_subfunc"],
  ].forEach((entry) => {
    attachID401CommandStateChange(entry[0], entry[1]);
  });
  attachSignal("_ZN5ID40116accessSubProcessEPh", "id401_access_subprocess", (args) => {
    const fields = {
      id401_packet_pointer: args[0].toString(),
    };
    for (let index = 0; index < 8; index += 1) {
      fields["id401_raw_packet_u8_at_" + index] = readU8Safe(args[0], index);
    }
    const packetId = (fields.id401_raw_packet_u8_at_0 || 0) & 0x7f;
    Object.assign(fields, describeID401TaskEntry(packetId));
    return fields;
  });
  attachEnterLeave("fnLotDirGmStart", "lot_dir_gm_start", {
    onEnter() {
      return describeSdGmData();
    },
    onLeave() {
      return describeSdGmData();
    },
  });
  attachEnterLeave("fnLotOther_AfterGetParam", "lot_other_after_get_param", {
    onEnter() {
      return describeSdGmData();
    },
    onLeave() {
      return describeSdGmData();
    },
  });
  attachEnterLeave("fnLotOther_AfterKndCal_ST", "lot_other_after_kndcal_st", {
    onEnter() {
      return describeSdGmData();
    },
    onLeave() {
      return describeSdGmData();
    },
  });
  attachEnterLeave("fnInitGmData_GmStart", "init_gmdata_gmstart", {
    onEnter() {
      return describeSdGmData();
    },
    onLeave() {
      return describeSdGmData();
    },
  });
  attachEnterLeave("fnInitGmData_PowerOn", "init_gmdata_poweron", {
    onEnter() {
      return describeSdGmData();
    },
    onLeave() {
      return describeSdGmData();
    },
  });
  attachEnterLeave("fnKndCalLot_Start", "kndcal_lot_start", {
    onEnter() {
      return describeSdGmData();
    },
    onLeave() {
      return describeSdGmData();
    },
  });
  attachEnterLeave("fnKndCalLot_PreMdl", "kndcal_lot_pre_mdl", {
    onEnter() {
      return describeSdGmData();
    },
    onLeave() {
      return describeSdGmData();
    },
  });
  attachEnterLeave("fnKndCalUsr_SetGR_DirPrmCopy", "kndcal_usr_set_gr_dir_prm_copy", {
    onEnter(args) {
      const fields = describeSdGmData();
      fields.arg0 = args[0].toString();
      fields.arg1 = args[1].toString();
      fields.arg2 = args[2].toString();
      return fields;
    },
    onLeave() {
      return describeSdGmData();
    },
  });
  attachEnterLeave("fnRxComGmStart", "rxcom_gm_start", {
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
  attachEnterLeave("fnRxComDirInfo3", "rxcom_dirinfo3", {
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
  const pioTaskSearchAddress = findExport("_ZN5ID40125fnPioTaskTbl_SearchTblAppEh");
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
  if (pioTaskSearchAddress !== null) {
    try {
      pioTaskSearchCallback = new NativeFunction(pioTaskSearchAddress, "pointer", ["int"]);
    } catch (error) {
      emit("hook_attach_error", {
        hook_kind: "pio_task_search_callback",
        symbol: "_ZN5ID40125fnPioTaskTbl_SearchTblAppEh",
        address: pioTaskSearchAddress.toString(),
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
    pio_task_search_callback: pioTaskSearchAddress === null ? null : pioTaskSearchAddress.toString(),
  });
  installSlotInputHooks();
  installStoryHooks();
  installAudioHooks();
  emit("probe_ready", {});
});
