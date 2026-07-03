"use strict";

// Metadata-only Z2D/movie-layer probe.
//
// Purpose:
// - identify whether the CZ2D movie layer is the missing clean-story
//   compositor/texture route;
// - correlate natural Z2D movie calls with CRI SetData/MovieInfo and renderer
//   drawCall primitive metadata.
//
// This script must not dump framebuffers, texture bytes, decoded video frames,
// PCM, or game media payloads.  It only records pointers, names, small numeric
// fields, sizes, and 4 KiB FNV hashes for identification.

const moduleName = "libGameProc.so";
const maxCStringBytes = 512;
const lastEmitByKey = new Map();
let activeEvent = null;

const symbols = {
  fnReqScene: "_ZN9C_AnmBase10fnReqSceneEyhtt",
  criSetData: "_ZN14CriManaWrapper7SetDataEPKhm",
  criMovieInfo: "_ZN14CriManaWrapper12GetMovieInfoEPiS0_PfS0_S0_",
  rendererDrawCall: "_ZN2zg6sprite14RendererImplGL8drawCallEPNS0_9PrimitiveE",
  rendererCheckBindTextureStates:
    "_ZN2zg6sprite14RendererImplGL25checkAndBindTextureStatesEPNS0_14TextureStateGLEj",

  z2dPlayerExecPlayMovie: "_ZN2zg10CZ2DPlayer13ExecPlayMovieEPNS_13CZ2DPlayMovieE",
  z2dPlayerDrawMovieLayer:
    "_ZN2zg10CZ2DPlayer14DrawMovieLayerEPNS_18CZ2DElemMovieLayerEPNS_10CZ2DRBInfoEfPNS_19CZ2DElemCameraLayerE",
  z2dPlayerGetMoviePrim:
    "_ZN2zg10CZ2DPlayer12GetMoviePrimEPNS_18CZ2DElemMovieLayerEPNS_13CZ2DPlayMovieEPNS_10CZ2DRBInfoE",
  z2dPlayerCallOpenMovie: "_ZN2zg10CZ2DPlayer13CallOpenMovieEPNS_13CZ2DPlayMovieE",
  z2dPlayerCallCloseMovie: "_ZN2zg10CZ2DPlayer14CallCloseMovieEPNS_13CZ2DPlayMovieE",

  z2dHardDecodeMovie: "_ZN2zg14CZ2DHardPlayer11DecodeMovieEPNS_13CZ2DPlayMovieE",
  z2dHardDrawMovie: "_ZN2zg14CZ2DHardPlayer9DrawMovieEPNS_12CZ2DPlayPrimE",
  z2dHardDrawMovieBlend:
    "_ZN2zg14CZ2DHardPlayer9DrawMovieEPNS_12CZ2DPlayPrimENS_12Z2DBlendModeE",
  z2dHardGetMovieTexture: "_ZN2zg14CZ2DHardPlayer15GetMovieTextureEPNS_13CZ2DPlayMovieE",
  z2dHardGetMovieName: "_ZN2zg14CZ2DHardPlayer12GetMovieNameEPNS_13CZ2DPlayMovieE",
  z2dHardOpenMovie: "_ZN2zg14CZ2DHardPlayer9OpenMovieEPNS_13CZ2DPlayMovieE",
  z2dHardEndMovie: "_ZN2zg14CZ2DHardPlayer8EndMovieEPNS_13CZ2DPlayMovieE",
  z2dHardCloseMovie: "_ZN2zg14CZ2DHardPlayer10CloseMovieEPNS_13CZ2DPlayMovieE",

  z2dPlayMovieGetMovieName: "_ZN2zg13CZ2DPlayMovie12GetMovieNameEv",
  z2dPlayMovieGetMovieState: "_ZN2zg13CZ2DPlayMovie13GetMovieStateEv",
  z2dPlayMovieGetMovieStartTime: "_ZN2zg13CZ2DPlayMovie17GetMovieStartTimeEv",
  z2dPlayMovieGetMovieEndTime: "_ZN2zg13CZ2DPlayMovie15GetMovieEndTimeEv",
  z2dPlayMovieChangeMovieState: "_ZN2zg13CZ2DPlayMovie16ChangeMovieStateENS_13Z2DMovieStateE",

  z2dElemMovieGetMovieName: "_ZN2zg13CZ2DElemMovie12GetMovieNameEv",
  z2dElemMovieGetMovieOriginalName: "_ZN2zg13CZ2DElemMovie20GetMovieOriginalNameEv",
  z2dElemMovieGetStartTime: "_ZN2zg13CZ2DElemMovie12GetStartTimeEv",
  z2dElemMovieGetEndTime: "_ZN2zg13CZ2DElemMovie10GetEndTimeEv",
  z2dElemMovieGetDecodeFrame: "_ZN2zg13CZ2DElemMovie14GetDecodeFrameEi",
  z2dElemMovieGetTimeRemapFrame: "_ZN2zg13CZ2DElemMovie17GetTimeRemapFrameEi",
  z2dElemMovieIsDrawTime: "_ZN2zg13CZ2DElemMovie10IsDrawTimeEi",

  gfCriLoadUsmPath: "_ZN8CriVideo20GFDirectionCriPlayer7LoadUSMEPKc",
  gfCriLoadUsmPathWithId: "_ZN8CriVideo20GFDirectionCriPlayer7LoadUSMEPKci",
  gfCriLoadUsmBytes: "_ZN8CriVideo20GFDirectionCriPlayer7LoadUSMEPKhm",
  gfCriRender: "_ZN8CriVideo20GFDirectionCriPlayer6RenderEPNS_19GFDirectionRendererE",
  gfCriUpdate: "_ZN8CriVideo20GFDirectionCriPlayer6UpdateEv",
  gfCriGetCurrentFrameData:
    "_ZN8CriVideo20GFDirectionCriPlayer19GetCurrentFrameDataERNSt6__ndk16vectorIhNS1_9allocatorIhEEEEPiS7_",
  gfCriGetStatus: "_ZNK8CriVideo20GFDirectionCriPlayer9GetStatusEv",
  gfCriGetNativeHandle: "_ZNK8CriVideo20GFDirectionCriPlayer15GetNativeHandleEv",
};

function nowMs() {
  return Date.now();
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

function pointerString(value) {
  if (value === null || value === undefined) {
    return "0x0";
  }
  try {
    return value.toString();
  } catch (_) {
    return "0x0";
  }
}

function readCString(pointerValue) {
  if (pointerValue === null || pointerValue.isNull()) {
    return { text: "", length: 0, error: "" };
  }
  try {
    let length = 0;
    while (length < maxCStringBytes && pointerValue.add(length).readU8() !== 0) {
      length += 1;
    }
    return { text: pointerValue.readCString(), length, error: "" };
  } catch (error) {
    return { text: "", length: 0, error: String(error) };
  }
}

function readStdStringCandidates(pointerValue) {
  if (pointerValue === null || pointerValue.isNull()) {
    return [];
  }
  const candidates = [];
  function add(source, text, error) {
    if (text || error) {
      candidates.push({ source, text: text || "", error: error || "" });
    }
  }
  try {
    add("direct", pointerValue.readCString(), "");
  } catch (error) {
    add("direct", "", String(error));
  }
  try {
    add("short+1", pointerValue.add(1).readCString(), "");
  } catch (error) {
    add("short+1", "", String(error));
  }
  try {
    add("long+16", pointerValue.add(16).readPointer().readCString(), "");
  } catch (error) {
    add("long+16", "", String(error));
  }
  return candidates;
}

function fnv1a(pointerValue, byteCount) {
  if (pointerValue === null || pointerValue.isNull() || byteCount <= 0) {
    return null;
  }
  const limit = Math.min(byteCount, 4096);
  try {
    const bytes = pointerValue.readByteArray(limit);
    const values = new Uint8Array(bytes);
    let hash = 2166136261 >>> 0;
    let nonzero = 0;
    for (let index = 0; index < values.length; index += 1) {
      const value = values[index];
      if (value !== 0) {
        nonzero += 1;
      }
      hash ^= value;
      hash = Math.imul(hash, 16777619) >>> 0;
    }
    return {
      hash_fnv1a: hash.toString(16).padStart(8, "0"),
      bytes_hashed: values.length,
      nonzero_hashed_bytes: nonzero,
    };
  } catch (error) {
    return { hash_fnv1a: null, bytes_hashed: 0, nonzero_hashed_bytes: 0, error: String(error) };
  }
}

function readU32At(pointerValue, offset) {
  if (pointerValue === null || pointerValue.isNull()) {
    return null;
  }
  try {
    return pointerValue.add(offset).readU32();
  } catch (_) {
    return null;
  }
}

function readS32Pointer(pointerValue) {
  if (pointerValue === null || pointerValue.isNull()) {
    return null;
  }
  try {
    return pointerValue.readS32();
  } catch (_) {
    return null;
  }
}

function readPointerAt(pointerValue, offset) {
  if (pointerValue === null || pointerValue.isNull()) {
    return "0x0";
  }
  try {
    return pointerValue.add(offset).readPointer().toString();
  } catch (_) {
    return "0x0";
  }
}

function sampleNumericFields(pointerValue, maxOffset) {
  if (pointerValue === null || pointerValue.isNull()) {
    return { pointer: "0x0", max_offset: "0x" + maxOffset.toString(16), fields: [] };
  }
  const fields = [];
  for (let offset = 0; offset < maxOffset; offset += 4) {
    try {
      const address = pointerValue.add(offset);
      const u32 = address.readU32();
      const f32 = address.readFloat();
      const item = { offset: "0x" + offset.toString(16) };
      let keep = false;
      if (u32 > 0 && u32 < 10000000) {
        item.u32 = u32;
        keep = true;
      }
      if (Number.isFinite(f32) && Math.abs(f32) >= 0.0001 && Math.abs(f32) < 100000) {
        item.f32 = Number(f32.toFixed(6));
        keep = true;
      }
      if (keep) {
        fields.push(item);
      }
    } catch (_) {
      break;
    }
  }
  return { pointer: pointerValue.toString(), max_offset: "0x" + maxOffset.toString(16), fields };
}

function samplePrimitive(pointerValue) {
  if (pointerValue === null || pointerValue.isNull()) {
    return { pointer: "0x0", error: "null pointer" };
  }
  const textureCount = readU32At(pointerValue, 0xb8);
  const safeTextureCount = Math.max(0, Math.min(textureCount || 0, 3));
  const textures = [];
  for (let index = 0; index < safeTextureCount; index += 1) {
    const base = 0x40 + index * 0x28;
    textures.push({
      index,
      type_u32_at_base: readU32At(pointerValue, base),
      texture_object_u32_at_base_plus_0x8: readU32At(pointerValue, base + 0x8),
      texture_object_u32_at_base_plus_0xc: readU32At(pointerValue, base + 0xc),
      texture_object_pointer_at_base_plus_0x18: readPointerAt(pointerValue, base + 0x18),
      filter_u32_at_base_plus_0x20: readU32At(pointerValue, base + 0x20),
      address_u32_at_base_plus_0x24: readU32At(pointerValue, base + 0x24),
    });
  }
  return {
    pointer: pointerValue.toString(),
    primitive_mode_u32_at_0x0: readU32At(pointerValue, 0x0),
    vertex_pointer_at_0x20: readPointerAt(pointerValue, 0x20),
    vertex_count_u32_at_0x28: readU32At(pointerValue, 0x28),
    index_pointer_at_0x30: readPointerAt(pointerValue, 0x30),
    index_count_u32_at_0x38: readU32At(pointerValue, 0x38),
    texture_count_u32_at_0xb8: textureCount,
    textures,
  };
}

function activeFields() {
  if (activeEvent === null) {
    return {};
  }
  return {
    active_event_code: activeEvent.code_hex,
    active_event_relative_ms: nowMs() - activeEvent.start_unix_ms,
  };
}

function emit(kind, fields) {
  send(
    Object.assign(
      {
        kind,
        unix_ms: nowMs(),
        thread_id: Process.getCurrentThreadId(),
      },
      activeFields(),
      fields || {}
    )
  );
}

function shouldEmit(kind, identity, intervalMs) {
  const key =
    (activeEvent === null ? "" : activeEvent.code_hex) +
    "\u0000" +
    kind +
    "\u0000" +
    identity;
  const current = nowMs();
  const previous = lastEmitByKey.get(key) || 0;
  if (current - previous < intervalMs) {
    return false;
  }
  lastEmitByKey.set(key, current);
  return true;
}

function findGameModule() {
  const named = Process.findModuleByName(moduleName);
  if (named !== null) {
    return named;
  }
  for (const symbol of [symbols.fnReqScene, symbols.criSetData, symbols.z2dHardDrawMovie]) {
    const address = Module.findGlobalExportByName(symbol);
    if (address !== null) {
      const moduleValue = Process.findModuleByAddress(address);
      if (moduleValue !== null) {
        return moduleValue;
      }
    }
  }
  return null;
}

function findExport(moduleValue, symbol) {
  let address =
    moduleValue !== null
      ? moduleValue.findExportByName(symbol)
      : Module.findGlobalExportByName(symbol);
  if (address === null) {
    address = Module.findGlobalExportByName(symbol);
  }
  if (address === null) {
    emit("hook_missing", { symbol });
  }
  return address;
}

function installHook(moduleValue, symbol, kind, callbacksFactory) {
  const address = findExport(moduleValue, symbol);
  if (address === null) {
    return;
  }
  try {
    Interceptor.attach(address, callbacksFactory(address));
    emit("hook_installed", { symbol, hook_kind: kind, address: address.toString() });
  } catch (error) {
    emit("hook_install_error", { symbol, hook_kind: kind, address: address.toString(), error: String(error) });
  }
}

function hookAnimationRequest(moduleValue) {
  installHook(moduleValue, symbols.fnReqScene, "animation_event_start", function (address) {
    return {
      onEnter(args) {
        activeEvent = {
          code_hex: "0x" + args[1].toString(16).padStart(16, "0"),
          start_unix_ms: nowMs(),
        };
        emit("animation_event_start", {
          symbol: symbols.fnReqScene,
          address: address.toString(),
          animation_object: args[0].toString(),
          immediate: toI32(args[2]) & 0xff,
          layer_flags: toI32(args[3]) & 0xffff,
          request_flags: toI32(args[4]) & 0xffff,
        });
      },
    };
  });
}

function hookCri(moduleValue) {
  installHook(moduleValue, symbols.criSetData, "cri_set_data", function (address) {
    return {
      onEnter(args) {
        const size = toU32(args[2]) || 0;
        const hash = fnv1a(args[1], size) || {};
        emit("cri_set_data", {
          symbol: symbols.criSetData,
          address: address.toString(),
          receiver: args[0].toString(),
          data_pointer: args[1].toString(),
          byte_size_u32: size,
          has_data: !args[1].isNull(),
          hash_fnv1a: hash.hash_fnv1a,
          bytes_hashed: hash.bytes_hashed,
          nonzero_hashed_bytes: hash.nonzero_hashed_bytes,
          error: hash.error || "",
        });
      },
    };
  });
  installHook(moduleValue, symbols.criMovieInfo, "cri_movie_info", function (address) {
    return {
      onEnter(args) {
        this.receiver = args[0].toString();
        this.width = args[1];
        this.height = args[2];
        this.frameRate = args[3];
        this.value3 = args[4];
        this.value4 = args[5];
      },
      onLeave(retval) {
        const ok = toI32(retval);
        emit("cri_movie_info", {
          symbol: symbols.criMovieInfo,
          address: address.toString(),
          receiver: this.receiver,
          return_i32: ok,
          width: ok ? this.width.readS32() : null,
          height: ok ? this.height.readS32() : null,
          frame_rate: ok ? this.frameRate.readFloat() : null,
          value3: ok ? this.value3.readS32() : null,
          value4: ok ? this.value4.readS32() : null,
        });
      },
    };
  });
}

function hookEnterArgs(moduleValue, symbol, kind, argNames, intervalMs, sampler) {
  installHook(moduleValue, symbol, kind, function (address) {
    return {
      onEnter(args) {
        const identityParts = [args[0].toString()];
        for (let index = 1; index < argNames.length; index += 1) {
          identityParts.push(args[index].toString());
        }
        if (!shouldEmit(kind, identityParts.join("|"), intervalMs)) {
          return;
        }
        const fields = {
          symbol,
          address: address.toString(),
        };
        for (let index = 0; index < argNames.length; index += 1) {
          fields[argNames[index]] = pointerString(args[index]);
        }
        if (sampler) {
          Object.assign(fields, sampler(args));
        }
        emit(kind, fields);
      },
    };
  });
}

function hookReturn(moduleValue, symbol, kind, returnMode, intervalMs, argNames, sampler) {
  installHook(moduleValue, symbol, kind, function (address) {
    return {
      onEnter(args) {
        this.args = [];
        for (let index = 0; index < argNames.length; index += 1) {
          this.args.push(args[index]);
        }
        this.identity = this.args.map((item) => item.toString()).join("|");
        this.skip = !shouldEmit(kind, this.identity, intervalMs);
      },
      onLeave(retval) {
        if (this.skip) {
          return;
        }
        const fields = {
          symbol,
          address: address.toString(),
          return_pointer: retval.toString(),
          return_i32: toI32(retval),
          return_u32: toU32(retval),
        };
        for (let index = 0; index < argNames.length; index += 1) {
          fields[argNames[index]] = pointerString(this.args[index]);
        }
        if (returnMode === "cstring") {
          fields.return_cstring = readCString(retval);
        }
        if (returnMode === "pointer_sample") {
          fields.return_numeric_probe = sampleNumericFields(retval, 0x80);
        }
        if (sampler) {
          Object.assign(fields, sampler(this.args, retval));
        }
        emit(kind, fields);
      },
    };
  });
}

function hookZ2D(moduleValue) {
  hookEnterArgs(
    moduleValue,
    symbols.z2dPlayerExecPlayMovie,
    "z2d_player_exec_play_movie",
    ["player_pointer", "play_movie_pointer"],
    250,
    (args) => ({ play_movie_numeric: sampleNumericFields(args[1], 0x80) })
  );
  hookEnterArgs(
    moduleValue,
    symbols.z2dPlayerDrawMovieLayer,
    "z2d_player_draw_movie_layer",
    ["player_pointer", "movie_layer_pointer", "rb_info_pointer", "alpha_or_time", "camera_layer_pointer"],
    250,
    (args) => ({
      movie_layer_numeric: sampleNumericFields(args[1], 0x80),
      rb_info_numeric: sampleNumericFields(args[2], 0x80),
    })
  );
  hookReturn(
    moduleValue,
    symbols.z2dPlayerGetMoviePrim,
    "z2d_player_get_movie_prim",
    "pointer_sample",
    250,
    ["player_pointer", "movie_layer_pointer", "play_movie_pointer", "rb_info_pointer"],
    (args) => ({
      play_movie_numeric: sampleNumericFields(args[2], 0x80),
      rb_info_numeric: sampleNumericFields(args[3], 0x80),
    })
  );
  hookEnterArgs(
    moduleValue,
    symbols.z2dPlayerCallOpenMovie,
    "z2d_player_call_open_movie",
    ["player_pointer", "play_movie_pointer"],
    0,
    (args) => ({ play_movie_numeric: sampleNumericFields(args[1], 0x80) })
  );
  hookEnterArgs(
    moduleValue,
    symbols.z2dPlayerCallCloseMovie,
    "z2d_player_call_close_movie",
    ["player_pointer", "play_movie_pointer"],
    0,
    (args) => ({ play_movie_numeric: sampleNumericFields(args[1], 0x80) })
  );

  hookEnterArgs(
    moduleValue,
    symbols.z2dHardDecodeMovie,
    "z2d_hard_decode_movie",
    ["hard_player_pointer", "play_movie_pointer"],
    250,
    (args) => ({ play_movie_numeric: sampleNumericFields(args[1], 0x80) })
  );
  hookEnterArgs(
    moduleValue,
    symbols.z2dHardDrawMovie,
    "z2d_hard_draw_movie",
    ["hard_player_pointer", "play_prim_pointer"],
    250,
    (args) => ({ play_prim_numeric: sampleNumericFields(args[1], 0x80) })
  );
  hookEnterArgs(
    moduleValue,
    symbols.z2dHardDrawMovieBlend,
    "z2d_hard_draw_movie_blend",
    ["hard_player_pointer", "play_prim_pointer", "blend_mode"],
    250,
    (args) => ({ blend_mode_i32: toI32(args[2]), play_prim_numeric: sampleNumericFields(args[1], 0x80) })
  );
  hookReturn(
    moduleValue,
    symbols.z2dHardGetMovieTexture,
    "z2d_hard_get_movie_texture",
    "pointer_sample",
    250,
    ["hard_player_pointer", "play_movie_pointer"],
    (args) => ({ play_movie_numeric: sampleNumericFields(args[1], 0x80) })
  );
  hookReturn(
    moduleValue,
    symbols.z2dHardGetMovieName,
    "z2d_hard_get_movie_name",
    "cstring",
    250,
    ["hard_player_pointer", "play_movie_pointer"],
    null
  );
  for (const [symbol, kind] of [
    [symbols.z2dHardOpenMovie, "z2d_hard_open_movie"],
    [symbols.z2dHardEndMovie, "z2d_hard_end_movie"],
    [symbols.z2dHardCloseMovie, "z2d_hard_close_movie"],
  ]) {
    hookEnterArgs(moduleValue, symbol, kind, ["hard_player_pointer", "play_movie_pointer"], 0, (args) => ({
      play_movie_numeric: sampleNumericFields(args[1], 0x80),
    }));
  }

  hookReturn(
    moduleValue,
    symbols.z2dPlayMovieGetMovieName,
    "z2d_play_movie_get_movie_name",
    "cstring",
    250,
    ["play_movie_pointer"],
    null
  );
  for (const [symbol, kind] of [
    [symbols.z2dPlayMovieGetMovieState, "z2d_play_movie_get_movie_state"],
    [symbols.z2dPlayMovieGetMovieStartTime, "z2d_play_movie_get_movie_start_time"],
    [symbols.z2dPlayMovieGetMovieEndTime, "z2d_play_movie_get_movie_end_time"],
  ]) {
    hookReturn(moduleValue, symbol, kind, "i32", 250, ["play_movie_pointer"], null);
  }
  hookEnterArgs(
    moduleValue,
    symbols.z2dPlayMovieChangeMovieState,
    "z2d_play_movie_change_movie_state",
    ["play_movie_pointer", "new_state"],
    0,
    (args) => ({ new_state_i32: toI32(args[1]), play_movie_numeric: sampleNumericFields(args[0], 0x80) })
  );

  hookReturn(
    moduleValue,
    symbols.z2dElemMovieGetMovieName,
    "z2d_elem_movie_get_movie_name",
    "cstring",
    250,
    ["elem_movie_pointer"],
    null
  );
  hookReturn(
    moduleValue,
    symbols.z2dElemMovieGetMovieOriginalName,
    "z2d_elem_movie_get_movie_original_name",
    "cstring",
    250,
    ["elem_movie_pointer"],
    null
  );
  for (const [symbol, kind] of [
    [symbols.z2dElemMovieGetStartTime, "z2d_elem_movie_get_start_time"],
    [symbols.z2dElemMovieGetEndTime, "z2d_elem_movie_get_end_time"],
  ]) {
    hookReturn(moduleValue, symbol, kind, "i32", 250, ["elem_movie_pointer"], null);
  }
  for (const [symbol, kind] of [
    [symbols.z2dElemMovieGetDecodeFrame, "z2d_elem_movie_get_decode_frame"],
    [symbols.z2dElemMovieGetTimeRemapFrame, "z2d_elem_movie_get_time_remap_frame"],
    [symbols.z2dElemMovieIsDrawTime, "z2d_elem_movie_is_draw_time"],
  ]) {
    hookReturn(moduleValue, symbol, kind, "i32", 250, ["elem_movie_pointer", "input_frame"], (args) => ({
      input_frame_i32: toI32(args[1]),
      elem_movie_numeric: sampleNumericFields(args[0], 0x80),
    }));
  }
}

function hookGFDirectionCri(moduleValue) {
  hookEnterArgs(
    moduleValue,
    symbols.gfCriLoadUsmPath,
    "gf_cri_load_usm_path",
    ["gf_cri_player_pointer", "path_pointer"],
    0,
    (args) => ({ path: readCString(args[1]) })
  );
  hookEnterArgs(
    moduleValue,
    symbols.gfCriLoadUsmPathWithId,
    "gf_cri_load_usm_path_with_id",
    ["gf_cri_player_pointer", "path_pointer", "movie_id"],
    0,
    (args) => ({ path: readCString(args[1]), movie_id_i32: toI32(args[2]) })
  );
  hookEnterArgs(
    moduleValue,
    symbols.gfCriLoadUsmBytes,
    "gf_cri_load_usm_bytes",
    ["gf_cri_player_pointer", "data_pointer", "byte_size"],
    0,
    (args) => {
      const size = toU32(args[2]) || 0;
      const hash = fnv1a(args[1], size) || {};
      return {
        byte_size_u32: size,
        hash_fnv1a: hash.hash_fnv1a,
        bytes_hashed: hash.bytes_hashed,
        nonzero_hashed_bytes: hash.nonzero_hashed_bytes,
        error: hash.error || "",
      };
    }
  );
  hookEnterArgs(
    moduleValue,
    symbols.gfCriRender,
    "gf_cri_render",
    ["gf_cri_player_pointer", "gf_renderer_pointer"],
    250,
    (args) => ({ gf_cri_player_numeric: sampleNumericFields(args[0], 0x80) })
  );
  hookEnterArgs(moduleValue, symbols.gfCriUpdate, "gf_cri_update", ["gf_cri_player_pointer"], 250, (args) => ({
    gf_cri_player_numeric: sampleNumericFields(args[0], 0x80),
  }));
  hookReturn(
    moduleValue,
    symbols.gfCriGetStatus,
    "gf_cri_get_status",
    "i32",
    250,
    ["gf_cri_player_pointer"],
    null
  );
  hookReturn(
    moduleValue,
    symbols.gfCriGetNativeHandle,
    "gf_cri_get_native_handle",
    "pointer_sample",
    250,
    ["gf_cri_player_pointer"],
    null
  );
  hookReturn(
    moduleValue,
    symbols.gfCriGetCurrentFrameData,
    "gf_cri_get_current_frame_data",
    "i32",
    250,
    ["gf_cri_player_pointer", "vector_pointer", "width_pointer", "height_pointer"],
    (args) => ({
      width_i32: readS32Pointer(args[2]),
      height_i32: readS32Pointer(args[3]),
      gf_cri_player_numeric: sampleNumericFields(args[0], 0x80),
    })
  );
}

function hookRenderer(moduleValue) {
  hookEnterArgs(
    moduleValue,
    symbols.rendererCheckBindTextureStates,
    "sprite_renderer_check_bind_texture_states",
    ["renderer_pointer", "texture_state_pointer", "flags"],
    250,
    (args) => ({
      flags_u32: toU32(args[2]),
      texture_state_numeric: sampleNumericFields(args[1], 0x80),
    })
  );
  hookEnterArgs(
    moduleValue,
    symbols.rendererDrawCall,
    "sprite_renderer_draw_call",
    ["renderer_pointer", "primitive_pointer"],
    250,
    (args) => ({ primitive: samplePrimitive(args[1]) })
  );
}

function main() {
  const moduleValue = findGameModule();
  emit("probe_start", {
    requested_module_name: moduleName,
    module_found: moduleValue !== null,
    resolved_module:
      moduleValue === null
        ? null
        : {
            name: moduleValue.name,
            path: moduleValue.path,
            base: moduleValue.base.toString(),
            size: moduleValue.size,
          },
  });
  if (moduleValue === null) {
    return;
  }
  hookAnimationRequest(moduleValue);
  hookCri(moduleValue);
  hookZ2D(moduleValue);
  hookGFDirectionCri(moduleValue);
  hookRenderer(moduleValue);
  emit("probe_ready", {});
}

main();
