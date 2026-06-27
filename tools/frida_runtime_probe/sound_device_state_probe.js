"use strict";

const moduleName = "libGameProc.so";
const outputDeviceOffset = 0x10;

const hooks = [
  {
    kind: "zg_snd_open_device",
    symbol: "zgSndOpenDevice",
    args: ["device_type"],
  },
  {
    kind: "zg_snd_close_device",
    symbol: "zgSndCloseDevice",
    args: [],
  },
  {
    kind: "snd_system_init",
    symbol: "_ZN2zg3snd9SndSystem4initEPK14TagZGSndConfig",
    args: ["this", "config"],
  },
  {
    kind: "snd_system_open_device",
    symbol: "_ZN2zg3snd9SndSystem10openDeviceEi",
    args: ["this", "device_type"],
  },
  {
    kind: "snd_system_close_device",
    symbol: "_ZN2zg3snd9SndSystem11closeDeviceEv",
    args: ["this"],
  },
  {
    kind: "output_ctrl_init_device",
    symbol: "_ZN2zg3snd10OutputCtrl10initDeviceEv",
    args: ["this"],
  },
  {
    kind: "output_ctrl_open_device",
    symbol: "_ZN2zg3snd10OutputCtrl10openDeviceEi",
    args: ["this", "device_type"],
  },
  {
    kind: "output_ctrl_close_device",
    symbol: "_ZN2zg3snd10OutputCtrl11closeDeviceEv",
    args: ["this"],
  },
  {
    kind: "output_ctrl_is_opened",
    symbol: "_ZN2zg3snd10OutputCtrl8isOpenedEv",
    args: ["this"],
  },
  {
    kind: "output_ctrl_output",
    symbol: "_ZN2zg3snd10OutputCtrl6outputEbRKNS0_8TransBufE",
    args: ["this", "output_enabled", "transbuf"],
    throttle: true,
  },
];

let outputCallCount = 0;
let lastOutputEmitMs = 0;
let lastOutputDevice = "";
let lastOutputEnabled = -1;

function nowMs() {
  return Date.now();
}

function emit(kind, fields) {
  send(
    Object.assign(
      {
        kind,
        unix_ms: nowMs(),
        thread_id: Process.getCurrentThreadId(),
      },
      fields || {}
    )
  );
}

function retvalFields(retval) {
  const fields = {
    return_pointer: retval.toString(),
  };
  try {
    fields.return_i32 = retval.toInt32();
  } catch (error) {
    fields.return_i32_error = String(error);
  }
  return fields;
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

function readPointer(pointerValue, offset) {
  if (pointerValue === null || pointerValue.isNull()) {
    return ptr(0);
  }
  try {
    return pointerValue.add(offset).readPointer();
  } catch (_) {
    return ptr(0);
  }
}

function describeOutputCtrl(pointerValue) {
  const device = readPointer(pointerValue, outputDeviceOffset);
  let deviceVtable = ptr(0);
  if (!device.isNull()) {
    deviceVtable = readPointer(device, 0);
  }
  return {
    output_ctrl: pointerValue.toString(),
    output_device: device.toString(),
    output_device_vtable: deviceVtable.toString(),
  };
}

function describeConfig(pointerValue) {
  if (pointerValue === null || pointerValue.isNull()) {
    return { pointer: "0x0" };
  }
  try {
    return {
      pointer: pointerValue.toString(),
      file_system: pointerValue.readU32(),
      sample_rate: pointerValue.add(4).readU32(),
      root_path_pointer: pointerValue.add(8).readPointer().toString(),
    };
  } catch (error) {
    return { pointer: pointerValue.toString(), error: String(error) };
  }
}

function makeArgFields(item, args) {
  const fields = {};
  item.args.forEach((name, index) => {
    fields[name + "_pointer"] = args[index].toString();
    fields[name + "_i32"] = args[index].toInt32();
  });
  if (item.kind.startsWith("output_ctrl_")) {
    Object.assign(fields, describeOutputCtrl(args[0]));
  }
  if (item.kind === "snd_system_open_device" || item.kind === "snd_system_close_device") {
    Object.assign(fields, describeOutputCtrl(args[0].add(0xf78)));
  }
  if (item.kind === "snd_system_init") {
    fields.config = describeConfig(args[1]);
    Object.assign(fields, describeOutputCtrl(args[0].add(0xf78)));
  }
  return fields;
}

function installHook(moduleValue, item) {
  const address = findExport(moduleValue, item.symbol);
  if (address === null) {
    return;
  }
  Interceptor.attach(address, {
    onEnter(args) {
      this.item = item;
      this.args = args;
      this.fields = makeArgFields(item, args);
      this.targetPointer = args[0];
      if (item.kind === "output_ctrl_output") {
        outputCallCount += 1;
        const current = nowMs();
        const device = this.fields.output_device || "";
        const enabled = args[1].toInt32();
        const changed = device !== lastOutputDevice || enabled !== lastOutputEnabled;
        if (
          outputCallCount > 8 &&
          !changed &&
          current - lastOutputEmitMs < 1000
        ) {
          this.skip = true;
          return;
        }
        lastOutputEmitMs = current;
        lastOutputDevice = device;
        lastOutputEnabled = enabled;
        this.fields.call_count = outputCallCount;
        this.fields.emit_reason = changed ? "state_changed" : "throttled_sample";
      }
      emit(item.kind + "_enter", Object.assign({
        symbol: item.symbol,
        address: address.toString(),
      }, this.fields));
    },
    onLeave(retval) {
      if (this.skip) {
        return;
      }
      if (item.kind === "output_ctrl_output") {
        return;
      }
      const fields = Object.assign({}, this.fields || {}, {
        symbol: item.symbol,
        address: address.toString(),
      }, retvalFields(retval));
      if (
        item.kind.startsWith("output_ctrl_") ||
        item.kind === "snd_system_open_device" ||
        item.kind === "snd_system_close_device" ||
        item.kind === "snd_system_init"
      ) {
        if (item.kind.startsWith("output_ctrl_")) {
          Object.assign(fields, describeOutputCtrl(this.targetPointer));
        } else if (this.targetPointer) {
          Object.assign(fields, describeOutputCtrl(this.targetPointer.add(0xf78)));
        }
      }
      emit(item.kind + "_leave", fields);
    },
  });
  emit("hook_installed", { hook_kind: item.kind, symbol: item.symbol, address: address.toString() });
}

setImmediate(function () {
  const moduleValue = Process.findModuleByName(moduleName);
  emit("probe_start", {
    architecture: Process.arch,
    platform: Process.platform,
    module_found: moduleValue !== null,
  });
  hooks.forEach((item) => installHook(moduleValue, item));
});
