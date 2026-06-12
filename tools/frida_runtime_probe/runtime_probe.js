"use strict";

const moduleName = "libGameProc.so";
const maxCStringBytes = 2048;
const recent = new Map();
let activeEvent = null;

function nowMs() {
  return Date.now();
}

function readCStringBytes(pointerValue) {
  if (pointerValue.isNull()) {
    return { text: "", data: null, length: 0 };
  }

  let length = 0;
  try {
    while (length < maxCStringBytes && pointerValue.add(length).readU8() !== 0) {
      length += 1;
    }
    const data = pointerValue.readByteArray(length);
    let text = "";
    try {
      text = pointerValue.readCString();
    } catch (_) {
      text = "";
    }
    return { text, data, length };
  } catch (error) {
    return { text: "", data: null, length: 0, error: String(error) };
  }
}

function emit(kind, fields, data) {
  const eventFields =
    activeEvent === null
      ? {}
      : {
          active_event_code: activeEvent.code_hex,
          active_event_object: activeEvent.animation_object,
          active_event_relative_ms: nowMs() - activeEvent.start_unix_ms,
        };
  const payload = Object.assign(
    {
      kind,
      unix_ms: nowMs(),
      thread_id: Process.getCurrentThreadId(),
    },
    eventFields,
    fields
  );
  send(payload, data || null);
}

function shouldEmitText(kind, text, length, includeEmpty) {
  if (length === 0 && !includeEmpty) {
    return false;
  }
  const eventKey = activeEvent === null ? "" : activeEvent.code_hex;
  const key = eventKey + "\u0000" + kind + "\u0000" + text;
  const current = nowMs();
  const previous = recent.get(key) || 0;
  recent.set(key, current);
  return current - previous >= 100;
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

function hookCString(
  moduleValue,
  symbol,
  argIndex,
  kind,
  includeReturn,
  includeEmpty
) {
  const address = findExport(moduleValue, symbol);
  if (address === null) {
    return;
  }

  Interceptor.attach(address, {
    onEnter(args) {
      const value = readCStringBytes(args[argIndex]);
      this.probeValue = value;
      this.receiver = args[0].toString();
      if (
        !includeReturn &&
        shouldEmitText(kind, value.text, value.length, includeEmpty)
      ) {
        emit(
          kind,
          {
            symbol,
            address: address.toString(),
            receiver: this.receiver,
            pointer: args[argIndex].toString(),
            text_utf8: value.text,
            byte_length: value.length,
            read_error: value.error || "",
          },
          value.data
        );
      }
    },
    onLeave(retval) {
      if (!includeReturn) {
        return;
      }
      const value = this.probeValue;
      if (
        value &&
        shouldEmitText(kind, value.text, value.length, includeEmpty)
      ) {
        emit(
          kind,
          {
            symbol,
            address: address.toString(),
            receiver: this.receiver,
            text_utf8: value.text,
            byte_length: value.length,
            return_u32: retval.toUInt32(),
            read_error: value.error || "",
          },
          value.data
        );
      }
    },
  });
  emit("hook_installed", { symbol, address: address.toString() });
}

function hookEventRequest(moduleValue) {
  const symbol = "_ZN9C_AnmBase10fnReqSceneEyhtt";
  const address = findExport(moduleValue, symbol);
  if (address === null) {
    return;
  }
  Interceptor.attach(address, {
    onEnter(args) {
      const current = nowMs();
      activeEvent = {
        code_hex: "0x" + args[1].toString(16).padStart(16, "0"),
        animation_object: args[0].toString(),
        start_unix_ms: current,
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

function hookIntCall(moduleValue, symbol, kind, argumentCount) {
  const address = findExport(moduleValue, symbol);
  if (address === null) {
    return;
  }

  Interceptor.attach(address, {
    onEnter(args) {
      const fields = {
        symbol,
        address: address.toString(),
      };
      for (let index = 0; index < argumentCount; index += 1) {
        fields["arg" + index + "_i32"] = args[index + 1].toInt32();
      }
      emit(kind, fields);
    },
  });
  emit("hook_installed", { symbol, address: address.toString() });
}

function hookCStringAndInts(moduleValue, symbol, kind, stringArgIndex, intArgIndexes) {
  const address = findExport(moduleValue, symbol);
  if (address === null) {
    return;
  }

  Interceptor.attach(address, {
    onEnter(args) {
      const value = readCStringBytes(args[stringArgIndex]);
      const fields = {
        symbol,
        address: address.toString(),
        pointer: args[stringArgIndex].toString(),
        text_utf8: value.text,
        byte_length: value.length,
        read_error: value.error || "",
      };
      intArgIndexes.forEach((argIndex) => {
        fields["arg" + argIndex + "_i32"] = args[argIndex].toInt32();
      });
      emit(kind, fields, value.data);
    },
  });
  emit("hook_installed", { symbol, address: address.toString() });
}

function hookPointerEvent(moduleValue, symbol, kind) {
  const address = findExport(moduleValue, symbol);
  if (address === null) {
    return;
  }

  Interceptor.attach(address, {
    onEnter(args) {
      emit(kind, {
        symbol,
        address: address.toString(),
        arg0: args[0].toString(),
        arg1: args[1].toString(),
        arg2: args[2].toString(),
      });
    },
  });
  emit("hook_installed", { symbol, address: address.toString() });
}

setImmediate(function () {
  const modules = Process.enumerateModules();
  const moduleValue = Process.findModuleByName(moduleName);
  emit("probe_start", {
    architecture: Process.arch,
    platform: Process.platform,
    module_found: moduleValue !== null,
    relevant_modules: modules
      .filter((item) => /GameProc|AMAIN|openal|ogg|ARES/i.test(item.name))
      .map((item) => ({
        name: item.name,
        path: item.path,
        base: item.base.toString(),
        size: item.size,
      })),
  });

  hookEventRequest(moduleValue);
  hookCString(
    moduleValue,
    "_ZN2zg3snd11RequestCtrl14codeName2ReqIdEPKc",
    1,
    "sound_code_lookup",
    true,
    false
  );
  hookCString(
    moduleValue,
    "_ZN2zg10CZ2DString9SetStringEPKc",
    1,
    "z2d_string_set",
    false,
    true
  );
  hookCString(
    moduleValue,
    "_ZN2zg6sprite8FontImpl8drawTextEiiRKNS_5ColorEPKc",
    4,
    "font_draw_text",
    false,
    false
  );
  hookCString(
    moduleValue,
    "_ZN2zg6sprite8FontImpl14drawTextFormatEiiRKNS_5ColorEPKcz",
    4,
    "font_draw_text_format",
    false,
    false
  );
  hookCString(
    moduleValue,
    "_ZN2zg6sprite8FontImpl10drawTextExERKNS_6VectorES4_RKNS_5ColorEbPKc",
    5,
    "font_draw_text_ex",
    false,
    false
  );
  hookCString(
    moduleValue,
    "_ZN2zg6sprite8FontImpl16drawTextExFormatERKNS_6VectorES4_RKNS_5ColorEbPKcz",
    5,
    "font_draw_text_ex_format",
    false,
    false
  );
  hookIntCall(moduleValue, "_ZN8SoundMng4playEii", "sound_mng_play", 2);
  hookCStringAndInts(
    moduleValue,
    "_ZN8SoundMng4playEPhii",
    "sound_mng_play_bytes",
    1,
    [2, 3]
  );
  hookIntCall(moduleValue, "_ZN8SoundMng10sndPlayReqEiii", "sound_mng_play_request", 3);
  hookIntCall(moduleValue, "_ZN8SoundMng10wrapSndReqEi", "sound_mng_wrap_request", 1);
  hookIntCall(moduleValue, "_ZN8SoundMng12wrapSndReqChEii", "sound_mng_wrap_request_channel", 2);
  hookIntCall(
    moduleValue,
    "_ZN2zg3snd11RequestCtrl10getRequestEjRNS0_7RequestE",
    "request_get",
    1
  );
  hookIntCall(
    moduleValue,
    "_ZN2zg3snd9SndSystem14getRequestByIdEjRNS0_7RequestE",
    "sound_system_get_request",
    1
  );
  hookPointerEvent(
    moduleValue,
    "_ZN2zg3snd11RequestCtrl14setRequestListERKNS0_7RequestE",
    "request_list_set"
  );
  hookPointerEvent(
    moduleValue,
    "_ZN2zg19Z2DreqSoundCallbackEPNS_10CZ2DPlayerEPNS_15CZ2DElemUCBFuncEPv",
    "z2d_sound_callback"
  );
});
