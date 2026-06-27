const moduleName = "libGameProc.so";
let outputCallCount = 0;
let lastOutputEmitMs = 0;
let lastOutputEnabled = -1;

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

function readMemoryHex(pointerValue, size) {
  if (pointerValue === null || pointerValue.isNull()) {
    return { address: null, hex: "", error: "null pointer" };
  }
  try {
    const bytes = new Uint8Array(pointerValue.readByteArray(size));
    let hex = "";
    for (let index = 0; index < bytes.length; index += 1) {
      hex += bytes[index].toString(16).padStart(2, "0");
    }
    return { address: pointerValue.toString(), hex, error: "" };
  } catch (error) {
    return { address: pointerValue.toString(), hex: "", error: String(error) };
  }
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

function hookOutputCtrl(moduleValue) {
  const symbol = "_ZN2zg3snd10OutputCtrl6outputEbRKNS0_8TransBufE";
  const address = findExport(moduleValue, symbol);
  if (address === null) {
    return;
  }
  Interceptor.attach(address, {
    onEnter(args) {
      outputCallCount += 1;
      const current = nowMs();
      const outputEnabled = args[1].toInt32();
      const enabledChanged = outputEnabled !== lastOutputEnabled;
      const minIntervalMs = outputEnabled ? 100 : 500;
      if (
        outputCallCount > 8 &&
        !enabledChanged &&
        current - lastOutputEmitMs < minIntervalMs
      ) {
        return;
      }
      lastOutputEmitMs = current;
      lastOutputEnabled = outputEnabled;
      emit("output_ctrl_output", {
        symbol,
        address: address.toString(),
        call_count: outputCallCount,
        emit_reason: enabledChanged ? "enabled_changed" : "throttled_sample",
        receiver: args[0].toString(),
        output_enabled_i32: outputEnabled,
        transbuf_pointer: args[2].toString(),
        transbuf_head: readMemoryHex(args[2], 0x100),
      });
    },
  });
  emit("hook_installed", { symbol, address: address.toString() });
}

function hookPlayInfo(moduleValue) {
  const symbols = [
    {
      symbol: "zgSndGetPlayInfo",
      kind: "zg_snd_get_play_info",
      arg_count: 2,
    },
    {
      symbol: "_ZN2zg3snd9SndSystem11getPlayInfoE9ZGSndChNoP16TagZGSndPlayInfo",
      kind: "snd_system_get_play_info",
      arg_count: 3,
    },
  ];
  symbols.forEach((item) => {
    const address = findExport(moduleValue, item.symbol);
    if (address === null) {
      return;
    }
    Interceptor.attach(address, {
      onEnter(args) {
        const fields = {
          symbol: item.symbol,
          address: address.toString(),
        };
        for (let index = 0; index < item.arg_count; index += 1) {
          fields["arg" + index + "_pointer"] = args[index].toString();
          fields["arg" + index + "_i32"] = args[index].toInt32();
        }
        emit(item.kind, fields);
      },
    });
    emit("hook_installed", { symbol: item.symbol, address: address.toString() });
  });
}

setImmediate(function () {
  const modules = Process.enumerateModules();
  const moduleValue = Process.findModuleByName(moduleName);
  emit("probe_start", {
    architecture: Process.arch,
    platform: Process.platform,
    module_found: moduleValue !== null,
    relevant_modules: modules
      .filter((item) => /GameProc|AMAIN|OpenSLES|AAudio|audio/i.test(item.name))
      .map((item) => ({
        name: item.name,
        path: item.path,
        base: item.base.toString(),
        size: item.size,
      })),
  });
  hookOutputCtrl(moduleValue);
  hookPlayInfo(moduleValue);
});
