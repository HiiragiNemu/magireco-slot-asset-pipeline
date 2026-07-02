"use strict";

// Metadata-only CRI video texture probe.
//
// This records CRI movie SetData/MovieInfo plus the internal
// CriVideo::GFDirectionRenderer texture create/update calls.  It never dumps
// frame buffers or video payloads; only dimensions, texture ids, bounded hashes,
// and timing metadata are emitted.

const moduleName = "libGameProc.so";
const scriptStartUnixMs = Date.now();
const hashByteLimit = 4096;
const textureStateNumericMaxOffset = 0x80;
const lastEmitByKey = new Map();

const symbols = {
  fnReqScene: "_ZN9C_AnmBase10fnReqSceneEyhtt",
  criSetData: "_ZN14CriManaWrapper7SetDataEPKhm",
  criMovieInfo: "_ZN14CriManaWrapper12GetMovieInfoEPiS0_PfS0_S0_",
  criUpdate: "_ZN14CriManaWrapper6UpdateEv",
  criGetStatus: "_ZN14CriManaWrapper9GetStatusEv",
  createTexture: "_ZN8CriVideo19GFDirectionRenderer13CreateTextureEiii",
  updateTexture: "_ZN8CriVideo19GFDirectionRenderer13UpdateTextureEjPKhiiii",
  screenObjectCalc: "_ZN16CScreenObjectMng16calcFrameControlEv",
  screenObjectDraw: "_ZN16CScreenObjectMng4drawEv",
  screenObjectSetLockFrame: "_ZN16CScreenObjectMng12setLockFrameEi",
  screenObjectCheckLock: "_ZN16CScreenObjectMng9checkLockEv",
  screenObjectShaderSetData: "_ZN19CScreenObjectShader7SetDataEP8SRenList",
  textureStateBind: "_ZN2zg6sprite14TextureStateGL4bindEv",
  textureStateSet: "_ZN2zg6sprite14TextureStateGL3setEjjjj",
  rendererCheckBindTextureStates:
    "_ZN2zg6sprite14RendererImplGL25checkAndBindTextureStatesEPNS0_14TextureStateGLEj",
  rendererMakeupTextures:
    "_ZN2zg6sprite14RendererImplGL14makeupTexturesEPNS0_14TextureStateGLEPNS0_9PrimitiveE",
  rendererUnbindTexture: "_ZN2zg6sprite14RendererImplGL13unbindTextureEij",
  rendererUnbindCurrentTextures: "_ZN2zg6sprite8Renderer21unbindCurrentTexturesEv",
};

function nowMs() {
  return Date.now();
}

function emit(kind, fields) {
  send(
    Object.assign(
      {
        kind,
        unix_ms: nowMs(),
        relative_ms: nowMs() - scriptStartUnixMs,
        thread_id: Process.getCurrentThreadId(),
      },
      fields || {}
    )
  );
}

function shouldEmit(kind, identity, intervalMs) {
  const key = kind + "\u0000" + identity;
  const current = nowMs();
  const previous = lastEmitByKey.get(key) || 0;
  if (current - previous < intervalMs) {
    return false;
  }
  lastEmitByKey.set(key, current);
  return true;
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
    try {
      return value.toInt32() >>> 0;
    } catch (_) {
      return null;
    }
  }
}

function readS32(pointerValue) {
  if (pointerValue === null || pointerValue.isNull()) {
    return null;
  }
  try {
    return pointerValue.readS32();
  } catch (_) {
    return null;
  }
}

function checksumBytes(pointerValue, byteCount) {
  if (pointerValue === null || pointerValue.isNull() || byteCount <= 0) {
    return {
      has_data: false,
      data_pointer: pointerValue === null ? "0x0" : pointerValue.toString(),
      hash_fnv1a: null,
      bytes_hashed: 0,
      nonzero_hashed_bytes: 0,
      error: "",
    };
  }
  const limit = Math.min(byteCount, hashByteLimit);
  try {
    const bytes = new Uint8Array(pointerValue.readByteArray(limit));
    let hash = 2166136261 >>> 0;
    let nonzero = 0;
    for (let index = 0; index < bytes.length; index += 1) {
      const value = bytes[index];
      if (value !== 0) {
        nonzero += 1;
      }
      hash ^= value;
      hash = Math.imul(hash, 16777619) >>> 0;
    }
    return {
      has_data: true,
      data_pointer: pointerValue.toString(),
      hash_fnv1a: hash.toString(16).padStart(8, "0"),
      bytes_hashed: bytes.length,
      nonzero_hashed_bytes: nonzero,
      error: "",
    };
  } catch (error) {
    return {
      has_data: true,
      data_pointer: pointerValue.toString(),
      hash_fnv1a: null,
      bytes_hashed: 0,
      nonzero_hashed_bytes: 0,
      error: String(error),
    };
  }
}

function sampleNumericFields(pointerValue, maxOffset) {
  if (pointerValue === null || pointerValue.isNull()) {
    return { pointer: "0x0", max_offset: "0x" + maxOffset.toString(16), fields: [] };
  }
  const fields = [];
  for (let offset = 0; offset < maxOffset; offset += 4) {
    const address = pointerValue.add(offset);
    try {
      const u32 = address.readU32();
      const f32 = address.readFloat();
      const item = { offset: "0x" + offset.toString(16) };
      let keep = false;
      if (u32 > 0 && u32 < 0x10000000) {
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
    } catch (error) {
      fields.push({ offset: "0x" + offset.toString(16), error: String(error) });
      break;
    }
  }
  return {
    pointer: pointerValue.toString(),
    max_offset: "0x" + maxOffset.toString(16),
    fields,
  };
}

function findGameModule() {
  const namedModule = Process.findModuleByName(moduleName);
  if (namedModule !== null) {
    return namedModule;
  }
  for (const symbol of [symbols.fnReqScene, symbols.criSetData, symbols.updateTexture]) {
    const address = Module.findGlobalExportByName(symbol);
    if (address === null) {
      continue;
    }
    const moduleValue = Process.findModuleByAddress(address);
    if (moduleValue !== null) {
      return moduleValue;
    }
  }
  return null;
}

function findExport(moduleValue, symbol) {
  let address =
    moduleValue === null
      ? Module.findGlobalExportByName(symbol)
      : moduleValue.findExportByName(symbol);
  if (address === null) {
    address = Module.findGlobalExportByName(symbol);
  }
  if (address === null) {
    emit("hook_missing", { symbol });
    return null;
  }
  return address;
}

function installHook(moduleValue, symbol, kind, callbacks) {
  const address = findExport(moduleValue, symbol);
  if (address === null) {
    return;
  }
  try {
    Interceptor.attach(address, callbacks(address));
    emit("hook_installed", { symbol, hook_kind: kind, address: address.toString() });
  } catch (error) {
    emit("hook_attach_failed", {
      symbol,
      hook_kind: kind,
      address: address.toString(),
      error: String(error),
    });
  }
}

function hookFnReqScene(moduleValue) {
  installHook(moduleValue, symbols.fnReqScene, "animation_event_start", function (address) {
    return {
      onEnter(args) {
        emit("animation_event_start", {
          symbol: symbols.fnReqScene,
          address: address.toString(),
          animation_object: args[0].toString(),
          code_hex: "0x" + args[1].toString(16).padStart(16, "0"),
          immediate: toI32(args[2]),
          layer_flags: toI32(args[3]),
          request_flags: toI32(args[4]),
        });
      },
    };
  });
}

function hookCriSetData(moduleValue) {
  installHook(moduleValue, symbols.criSetData, "cri_set_data", function (address) {
    return {
      onEnter(args) {
        const size = toU32(args[2]) || 0;
        emit(
          "cri_set_data",
          Object.assign(
            {
              symbol: symbols.criSetData,
              address: address.toString(),
              receiver: args[0].toString(),
              byte_size_u32: size,
            },
            checksumBytes(args[1], size)
          )
        );
      },
    };
  });
}

function hookCriMovieInfo(moduleValue) {
  installHook(moduleValue, symbols.criMovieInfo, "cri_movie_info", function (address) {
    return {
      onEnter(args) {
        this.skip = !shouldEmit("cri_movie_info", args[0].toString(), 1000);
        if (this.skip) {
          return;
        }
        this.receiver = args[0];
        this.i0 = args[1];
        this.i1 = args[2];
        this.f2 = args[3];
        this.i3 = args[4];
        this.i4 = args[5];
      },
      onLeave(retval) {
        if (this.skip) {
          return;
        }
        let frameRate = null;
        try {
          frameRate = this.f2.readFloat();
        } catch (_) {
          frameRate = null;
        }
        emit("cri_movie_info", {
          symbol: symbols.criMovieInfo,
          address: address.toString(),
          receiver: this.receiver.toString(),
          return_i32: toI32(retval),
          width: readS32(this.i0),
          height: readS32(this.i1),
          frame_rate: frameRate,
          value3: readS32(this.i3),
          value4: readS32(this.i4),
        });
      },
    };
  });
}

function hookCriStatus(moduleValue) {
  installHook(moduleValue, symbols.criUpdate, "cri_update", function (address) {
    return {
      onEnter(args) {
        if (!shouldEmit("cri_update", args[0].toString(), 250)) {
          return;
        }
        emit("cri_update", {
          symbol: symbols.criUpdate,
          address: address.toString(),
          receiver: args[0].toString(),
        });
      },
    };
  });
  installHook(moduleValue, symbols.criGetStatus, "cri_get_status", function (address) {
    return {
      onEnter(args) {
        this.skip = !shouldEmit("cri_get_status", args[0].toString(), 250);
        if (this.skip) {
          return;
        }
        this.receiver = args[0];
      },
      onLeave(retval) {
        if (this.skip) {
          return;
        }
        emit("cri_get_status", {
          symbol: symbols.criGetStatus,
          address: address.toString(),
          receiver: this.receiver.toString(),
          return_i32: toI32(retval),
        });
      },
    };
  });
}

function hookEnterArgs(moduleValue, symbol, kind, argCount, throttleMs) {
  installHook(moduleValue, symbol, kind, function (address) {
    return {
      onEnter(args) {
        const identity = argCount > 0 ? args[0].toString() : symbol;
        if (throttleMs && !shouldEmit(kind, identity, throttleMs)) {
          return;
        }
        const fields = { symbol, address: address.toString() };
        for (let index = 0; index < argCount; index += 1) {
          fields["arg" + index + "_pointer"] = args[index].toString();
          fields["arg" + index + "_i32"] = toI32(args[index]);
        }
        emit(kind, fields);
      },
    };
  });
}

function hookReturn(moduleValue, symbol, kind, argCount, throttleMs) {
  installHook(moduleValue, symbol, kind, function (address) {
    return {
      onEnter(args) {
        const identity = argCount > 0 ? args[0].toString() : symbol;
        this.skip = throttleMs && !shouldEmit(kind, identity, throttleMs);
        if (this.skip) {
          return;
        }
        this.fields = { symbol, address: address.toString() };
        for (let index = 0; index < argCount; index += 1) {
          this.fields["arg" + index + "_pointer"] = args[index].toString();
          this.fields["arg" + index + "_i32"] = toI32(args[index]);
        }
      },
      onLeave(retval) {
        if (this.skip) {
          return;
        }
        this.fields.return_pointer = retval.toString();
        this.fields.return_i32 = toI32(retval);
        emit(kind, this.fields);
      },
    };
  });
}

function hookRendererActivity(moduleValue) {
  hookEnterArgs(moduleValue, symbols.screenObjectCalc, "screen_object_calc_frame_control", 1, 250);
  hookEnterArgs(moduleValue, symbols.screenObjectDraw, "screen_object_draw", 1, 250);
  hookEnterArgs(moduleValue, symbols.screenObjectSetLockFrame, "screen_object_set_lock_frame", 2, 0);
  hookReturn(moduleValue, symbols.screenObjectCheckLock, "screen_object_check_lock", 1, 250);
  hookEnterArgs(moduleValue, symbols.screenObjectShaderSetData, "screen_object_shader_set_data", 2, 250);
  hookEnterArgs(moduleValue, symbols.textureStateBind, "sprite_texture_state_bind", 1, 250);
  hookEnterArgs(moduleValue, symbols.textureStateSet, "sprite_texture_state_set", 5, 0);
  installHook(
    moduleValue,
    symbols.rendererCheckBindTextureStates,
    "sprite_renderer_check_bind_texture_states",
    function (address) {
      return {
        onEnter(args) {
          const identity = args[0].toString() + "\u0000" + args[1].toString() + "\u0000" + args[2].toString();
          if (!shouldEmit("sprite_renderer_check_bind_texture_states", identity, 250)) {
            return;
          }
          emit("sprite_renderer_check_bind_texture_states", {
            symbol: symbols.rendererCheckBindTextureStates,
            address: address.toString(),
            arg0_pointer: args[0].toString(),
            arg0_i32: toI32(args[0]),
            arg1_pointer: args[1].toString(),
            arg1_i32: toI32(args[1]),
            arg2_pointer: args[2].toString(),
            arg2_i32: toI32(args[2]),
            texture_state_numeric: sampleNumericFields(args[1], textureStateNumericMaxOffset),
          });
        },
      };
    }
  );
  hookEnterArgs(moduleValue, symbols.rendererMakeupTextures, "sprite_renderer_makeup_textures", 3, 250);
  hookEnterArgs(moduleValue, symbols.rendererUnbindTexture, "sprite_renderer_unbind_texture", 3, 250);
  hookEnterArgs(moduleValue, symbols.rendererUnbindCurrentTextures, "sprite_renderer_unbind_current_textures", 1, 250);
}

function hookCreateTexture(moduleValue) {
  installHook(moduleValue, symbols.createTexture, "cri_video_create_texture", function (address) {
    return {
      onEnter(args) {
        this.renderer = args[0];
        this.value0 = toI32(args[1]);
        this.value1 = toI32(args[2]);
        this.value2 = toI32(args[3]);
      },
      onLeave(retval) {
        emit("cri_video_create_texture", {
          symbol: symbols.createTexture,
          address: address.toString(),
          renderer: this.renderer.toString(),
          value0: this.value0,
          value1: this.value1,
          value2: this.value2,
          return_u32: toU32(retval),
          return_pointer: retval.toString(),
        });
      },
    };
  });
}

function hookUpdateTexture(moduleValue) {
  installHook(moduleValue, symbols.updateTexture, "cri_video_update_texture", function (address) {
    return {
      onEnter(args) {
        const textureId = toU32(args[1]);
        const value0 = toI32(args[3]);
        const value1 = toI32(args[4]);
        const value2 = toI32(args[5]);
        const value3 = toI32(args[6]);
        const bytesToHash = Math.max(0, Math.min((value0 || 0) * (value1 || 0) * 4, hashByteLimit));
        emit(
          "cri_video_update_texture",
          Object.assign(
            {
              symbol: symbols.updateTexture,
              address: address.toString(),
              renderer: args[0].toString(),
              texture_id_u32: textureId,
              value0,
              value1,
              value2,
              value3,
            },
            checksumBytes(args[2], bytesToHash || hashByteLimit)
          )
        );
      },
    };
  });
}

setImmediate(function () {
  const moduleValue = findGameModule();
  emit("probe_start", {
    architecture: Process.arch,
    platform: Process.platform,
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

  hookFnReqScene(moduleValue);
  hookCriSetData(moduleValue);
  hookCriMovieInfo(moduleValue);
  hookCriStatus(moduleValue);
  hookCreateTexture(moduleValue);
  hookUpdateTexture(moduleValue);
  hookRendererActivity(moduleValue);

  emit("probe_ready", {});
});
