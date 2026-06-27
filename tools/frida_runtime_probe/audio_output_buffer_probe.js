"use strict";

const moduleName = "libGameProc.so";
const outputSymbol = "_ZN2zg3snd10OutputCtrl6outputEbRKNS0_8TransBufE";
const outputTailOffset = 0x508;
const outputBufferBytes = 0x2000;
const maxDumpChunks = 160;

let outputCallCount = 0;
let dumpedChunks = 0;
let dumpedTransbufChunks = 0;
let lastOutputEnabled = -1;
const activeCallsByThread = {};
const hookedDeviceWriteFunctions = {};

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

function byteWindowHasNonZero(pointerValue, size) {
  if (pointerValue === null || pointerValue.isNull()) {
    return false;
  }
  try {
    const bytes = new Uint8Array(pointerValue.readByteArray(size));
    for (let index = 0; index < bytes.length; index += 1) {
      if (bytes[index] !== 0) {
        return true;
      }
    }
  } catch (_) {
    return false;
  }
  return false;
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

function hookOutputBuffer(moduleValue) {
  const outputAddress = findExport(moduleValue, outputSymbol);
  if (outputAddress === null) {
    return;
  }
  const tailAddress = outputAddress.add(outputTailOffset);

  function hookDeviceWrite(writeFunction) {
    const key = writeFunction.toString();
    if (hookedDeviceWriteFunctions[key]) {
      return;
    }
    hookedDeviceWriteFunctions[key] = true;
    Interceptor.attach(writeFunction, {
      onEnter(args) {
        const threadKey = String(Process.getCurrentThreadId());
        const call = activeCallsByThread[threadKey] || {};
        const outputBuffer = args[1];
        const hasNonZero = byteWindowHasNonZero(outputBuffer, outputBufferBytes);
        const shouldDump =
          dumpedChunks < maxDumpChunks &&
          call.output_enabled_i32 === 1 &&
          hasNonZero;
        const fields = {
          symbol: outputSymbol,
          capture_point: "device_write",
          output_function: outputAddress.toString(),
          tail_address: tailAddress.toString(),
          call_count: call.call_count || 0,
          chunk_index: shouldDump ? dumpedChunks : null,
          output_enabled_i32: call.output_enabled_i32 ?? null,
          receiver: call.receiver || null,
          transbuf_pointer: call.transbuf_pointer || null,
          device_pointer: args[0].toString(),
          device_write_function: writeFunction.toString(),
          output_buffer_pointer: outputBuffer.toString(),
          output_buffer_bytes: outputBufferBytes,
          output_buffer_head: readMemoryHex(outputBuffer, 0x80),
          output_buffer_has_nonzero: hasNonZero,
          dumped: shouldDump,
        };
        if (shouldDump) {
          const bytes = outputBuffer.readByteArray(outputBufferBytes);
          dumpedChunks += 1;
          emit("output_buffer_chunk", fields, bytes);
        } else if (call.call_count <= 8 || hasNonZero) {
          emit("output_buffer_metadata", fields);
        }
      },
    });
    emit("device_write_hook_installed", {
      device_write_function: writeFunction.toString(),
    });
  }

  Interceptor.attach(outputAddress, {
    onEnter(args) {
      outputCallCount += 1;
      let device = ptr(0);
      let writeFunction = ptr(0);
      try {
        device = args[0].add(0x10).readPointer();
        if (!device.isNull()) {
          writeFunction = device.readPointer().add(0x48).readPointer();
          hookDeviceWrite(writeFunction);
        }
      } catch (error) {
        if (outputCallCount <= 8) {
          emit("device_write_hook_error", {
            call_count: outputCallCount,
            receiver: args[0].toString(),
            error: String(error),
          });
        }
      }
      const outputEnabled = args[1].toInt32();
      const transbufPointer = args[2];
      const transbufHasNonZero = byteWindowHasNonZero(
        transbufPointer,
        outputBufferBytes
      );
      const call = {
        call_count: outputCallCount,
        output_enabled_i32: outputEnabled,
        receiver: args[0].toString(),
        transbuf_pointer: transbufPointer.toString(),
        device_pointer: device.toString(),
        device_write_function: writeFunction.toString(),
        transbuf_has_nonzero: transbufHasNonZero,
      };
      activeCallsByThread[String(Process.getCurrentThreadId())] = call;
      const enabledChanged = outputEnabled !== lastOutputEnabled;
      lastOutputEnabled = outputEnabled;
      if (outputCallCount <= 8 || enabledChanged || outputEnabled === 1) {
        emit("output_entry", call);
      }
      const shouldDumpTransbuf =
        dumpedTransbufChunks < maxDumpChunks &&
        outputEnabled === 1 &&
        transbufHasNonZero;
      if (shouldDumpTransbuf) {
        const fields = Object.assign({}, call, {
          capture_point: "output_entry_transbuf",
          chunk_index: dumpedTransbufChunks,
          transbuf_bytes: outputBufferBytes,
          transbuf_head: readMemoryHex(transbufPointer, 0x80),
        });
        const bytes = transbufPointer.readByteArray(outputBufferBytes);
        dumpedTransbufChunks += 1;
        emit("transbuf_chunk", fields, bytes);
      }
    },
  });

  Interceptor.attach(tailAddress, {
    onEnter() {
      const threadKey = String(Process.getCurrentThreadId());
      const call = activeCallsByThread[threadKey] || {};
      const outputBuffer = this.context.x1;
      const device = this.context.x0;
      const writeFunction = this.context.x2;
      const hasNonZero = byteWindowHasNonZero(outputBuffer, outputBufferBytes);
      const shouldDump =
        dumpedChunks < maxDumpChunks &&
        call.output_enabled_i32 === 1 &&
        hasNonZero;

      const fields = {
        symbol: outputSymbol,
        output_function: outputAddress.toString(),
        tail_address: tailAddress.toString(),
        call_count: call.call_count || 0,
        chunk_index: shouldDump ? dumpedChunks : null,
        output_enabled_i32: call.output_enabled_i32 ?? null,
        receiver: call.receiver || null,
        transbuf_pointer: call.transbuf_pointer || null,
        device_pointer: device.toString(),
        device_write_function: writeFunction.toString(),
        output_buffer_pointer: outputBuffer.toString(),
        output_buffer_bytes: outputBufferBytes,
        output_buffer_head: readMemoryHex(outputBuffer, 0x80),
        output_buffer_has_nonzero: hasNonZero,
        dumped: shouldDump,
      };

      if (shouldDump) {
        const bytes = outputBuffer.readByteArray(outputBufferBytes);
        dumpedChunks += 1;
        emit("output_buffer_chunk", fields, bytes);
      } else if (call.call_count <= 8 || hasNonZero) {
        emit("output_buffer_metadata", fields);
      }
    },
  });

  emit("hook_installed", {
    symbol: outputSymbol,
    output_address: outputAddress.toString(),
    tail_address: tailAddress.toString(),
    output_buffer_bytes: outputBufferBytes,
    max_dump_chunks: maxDumpChunks,
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
  hookOutputBuffer(moduleValue);
});
