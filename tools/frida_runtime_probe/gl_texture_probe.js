"use strict";

// Metadata-only OpenGL ES texture upload probe.
//
// This script records texture upload dimensions, texture ids, a bounded hash of
// the first bytes of upload data, and timing metadata.  It does not call
// glReadPixels, dump framebuffers, or export texture/frame data.

const scriptStartUnixMs = Date.now();
const minInterestingWidth = 128;
const minInterestingHeight = 128;
const hashByteLimit = 4096;
const GL_TEXTURE0 = 0x84c0;
const GL_TEXTURE_2D = 0x0de1;
const GL_TEXTURE_EXTERNAL_OES = 0x8d65;

let activeTextureUnit = 0;
let currentProgram = 0;
let currentFramebuffer = 0;
let currentViewport = null;
const boundTextures = new Map();
const hookCounts = {};
const callCounts = {};
const lastEmitByKind = new Map();
const hookedAddresses = new Set();
const dynamicHookFactories = {};

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

function countCall(kind) {
  callCounts[kind] = (callCounts[kind] || 0) + 1;
}

function shouldEmit(kind, intervalMs) {
  const current = nowMs();
  const previous = lastEmitByKind.get(kind) || 0;
  if (current - previous < intervalMs) {
    return false;
  }
  lastEmitByKind.set(kind, current);
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

function keyFor(unit, target) {
  return unit.toString() + ":" + target.toString();
}

function targetName(target) {
  if (target === GL_TEXTURE_2D) {
    return "GL_TEXTURE_2D";
  }
  if (target === GL_TEXTURE_EXTERNAL_OES) {
    return "GL_TEXTURE_EXTERNAL_OES";
  }
  return "0x" + target.toString(16);
}

function boundTexture(target) {
  return boundTextures.get(keyFor(activeTextureUnit, target)) || 0;
}

function shouldRecord(width, height) {
  return width >= minInterestingWidth && height >= minInterestingHeight;
}

function hashBytes(pointerValue) {
  if (pointerValue === null || pointerValue.isNull()) {
    return { has_data: false, data_pointer: "0x0", hash_fnv1a: null, bytes_hashed: 0, error: "" };
  }
  try {
    const bytes = new Uint8Array(pointerValue.readByteArray(hashByteLimit));
    let hash = 2166136261 >>> 0;
    let nonZero = 0;
    for (let index = 0; index < bytes.length; index += 1) {
      const value = bytes[index];
      if (value !== 0) {
        nonZero += 1;
      }
      hash ^= value;
      hash = Math.imul(hash, 16777619) >>> 0;
    }
    return {
      has_data: true,
      data_pointer: pointerValue.toString(),
      hash_fnv1a: hash.toString(16).padStart(8, "0"),
      bytes_hashed: bytes.length,
      nonzero_hashed_bytes: nonZero,
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

function readCString(pointerValue) {
  if (pointerValue === null || pointerValue.isNull()) {
    return "";
  }
  try {
    return pointerValue.readCString() || "";
  } catch (_) {
    return "";
  }
}

function isLikelyGlModule(moduleValue) {
  return /GLES|EGL|adreno|mali|angle|swiftshader|emulation|opengl|hwui/i.test(
    moduleValue.name + "\n" + moduleValue.path
  );
}

function findExportAddresses(name) {
  const results = [];
  const seen = new Set();

  function add(address, source) {
    if (address === null || address.isNull()) {
      return;
    }
    const key = address.toString();
    if (seen.has(key)) {
      return;
    }
    seen.add(key);
    results.push({ address, source });
  }

  add(Module.findGlobalExportByName(name), "global");
  Process.enumerateModules()
    .filter(isLikelyGlModule)
    .forEach((moduleValue) => {
      try {
        moduleValue
          .enumerateExports()
          .filter((item) => item.type === "function" && item.name === name)
          .forEach((item) => add(item.address, moduleValue.name));
      } catch (_) {
        // Some Android pseudo-modules may reject export enumeration.
      }
    });

  if (results.length === 0) {
    emit("hook_missing", { symbol: name });
  }
  return results;
}

function installHookAtAddress(name, address, callbacks, source) {
  if (address === null || address.isNull()) {
    return false;
  }
  const hookKey = name + "@" + address.toString();
  if (hookedAddresses.has(hookKey)) {
    return false;
  }
  try {
    Interceptor.attach(address, callbacks(address));
    hookedAddresses.add(hookKey);
    hookCounts[name] = (hookCounts[name] || 0) + 1;
    emit("hook_installed", { symbol: name, address: address.toString(), source });
    return true;
  } catch (error) {
    emit("hook_attach_failed", {
      symbol: name,
      address: address.toString(),
      source,
      error: String(error),
    });
    return false;
  }
}

function installHook(name, callbacks) {
  dynamicHookFactories[name] = callbacks;
  findExportAddresses(name).forEach((item) => {
    installHookAtAddress(name, item.address, callbacks, item.source);
  });
}

function emitTextureUpload(kind, fields, dataPointer) {
  if (!shouldRecord(fields.width, fields.height)) {
    return;
  }
  emit(
    kind,
    Object.assign(
      {
        active_texture_unit: activeTextureUnit,
        target_name: targetName(fields.target),
        bound_texture: boundTexture(fields.target),
      },
      fields,
      hashBytes(dataPointer)
    )
  );
}

function installGlHooks() {
  installHook("glActiveTexture", function () {
    return {
      onEnter(args) {
        countCall("glActiveTexture");
        const texture = toI32(args[0]);
        if (texture !== null && texture >= GL_TEXTURE0) {
          activeTextureUnit = texture - GL_TEXTURE0;
        }
      },
    };
  });

  installHook("glBindTexture", function (address) {
    return {
      onEnter(args) {
        countCall("glBindTexture");
        const target = toI32(args[0]);
        const texture = toU32(args[1]);
        if (target !== null && texture !== null) {
          boundTextures.set(keyFor(activeTextureUnit, target), texture);
          if (
            texture !== 0 &&
            (target === GL_TEXTURE_2D || target === GL_TEXTURE_EXTERNAL_OES)
          ) {
            emit("gl_bind_texture", {
              symbol: "glBindTexture",
              address: address.toString(),
              active_texture_unit: activeTextureUnit,
              target,
              target_name: targetName(target),
              bound_texture: texture,
            });
          }
        }
      },
    };
  });

  installHook("glTexImage2D", function (address) {
    return {
      onEnter(args) {
        countCall("glTexImage2D");
        const target = toI32(args[0]);
        const width = toI32(args[3]);
        const height = toI32(args[4]);
        if (target === null || width === null || height === null) {
          return;
        }
        emitTextureUpload(
          "gl_tex_image_2d",
          {
            symbol: "glTexImage2D",
            address: address.toString(),
            target,
            level: toI32(args[1]),
            internal_format: toI32(args[2]),
            width,
            height,
            border: toI32(args[5]),
            format: toI32(args[6]),
            type: toI32(args[7]),
          },
          args[8]
        );
      },
    };
  });

  installHook("glTexSubImage2D", function (address) {
    return {
      onEnter(args) {
        countCall("glTexSubImage2D");
        const target = toI32(args[0]);
        const width = toI32(args[4]);
        const height = toI32(args[5]);
        if (target === null || width === null || height === null) {
          return;
        }
        emitTextureUpload(
          "gl_tex_sub_image_2d",
          {
            symbol: "glTexSubImage2D",
            address: address.toString(),
            target,
            level: toI32(args[1]),
            xoffset: toI32(args[2]),
            yoffset: toI32(args[3]),
            width,
            height,
            format: toI32(args[6]),
            type: toI32(args[7]),
          },
          args[8]
        );
      },
    };
  });

  installHook("glCompressedTexImage2D", function (address) {
    return {
      onEnter(args) {
        countCall("glCompressedTexImage2D");
        const target = toI32(args[0]);
        const width = toI32(args[3]);
        const height = toI32(args[4]);
        if (target === null || width === null || height === null) {
          return;
        }
        emitTextureUpload(
          "gl_compressed_tex_image_2d",
          {
            symbol: "glCompressedTexImage2D",
            address: address.toString(),
            target,
            level: toI32(args[1]),
            internal_format: toI32(args[2]),
            width,
            height,
            border: toI32(args[5]),
            image_size: toI32(args[6]),
          },
          args[7]
        );
      },
    };
  });

  installHook("glCompressedTexSubImage2D", function (address) {
    return {
      onEnter(args) {
        countCall("glCompressedTexSubImage2D");
        const target = toI32(args[0]);
        const width = toI32(args[4]);
        const height = toI32(args[5]);
        if (target === null || width === null || height === null) {
          return;
        }
        emitTextureUpload(
          "gl_compressed_tex_sub_image_2d",
          {
            symbol: "glCompressedTexSubImage2D",
            address: address.toString(),
            target,
            level: toI32(args[1]),
            xoffset: toI32(args[2]),
            yoffset: toI32(args[3]),
            width,
            height,
            format: toI32(args[6]),
            image_size: toI32(args[7]),
          },
          args[8]
        );
      },
    };
  });

  installHook("glEGLImageTargetTexture2DOES", function (address) {
    return {
      onEnter(args) {
        countCall("glEGLImageTargetTexture2DOES");
        const target = toI32(args[0]);
        if (target === null) {
          return;
        }
        emit("gl_egl_image_target_texture_2d_oes", {
          symbol: "glEGLImageTargetTexture2DOES",
          address: address.toString(),
          active_texture_unit: activeTextureUnit,
          target,
          target_name: targetName(target),
          bound_texture: boundTexture(target),
          image_pointer: args[1].toString(),
        });
      },
    };
  });

  installHook("glDeleteTextures", function (address) {
    return {
      onEnter(args) {
        countCall("glDeleteTextures");
        const count = toI32(args[0]) || 0;
        const values = [];
        const limit = Math.max(0, Math.min(count, 16));
        for (let index = 0; index < limit; index += 1) {
          try {
            values.push(args[1].add(index * 4).readU32());
          } catch (_) {
            values.push(null);
            break;
          }
        }
        emit("gl_delete_textures", {
          symbol: "glDeleteTextures",
          address: address.toString(),
          count,
          texture_ids_first16: values,
        });
      },
    };
  });

  installHook("glUseProgram", function () {
    return {
      onEnter(args) {
        countCall("glUseProgram");
        const program = toU32(args[0]);
        if (program !== null) {
          currentProgram = program;
        }
      },
    };
  });

  installHook("glBindFramebuffer", function () {
    return {
      onEnter(args) {
        countCall("glBindFramebuffer");
        const framebuffer = toU32(args[1]);
        if (framebuffer !== null) {
          currentFramebuffer = framebuffer;
        }
      },
    };
  });

  installHook("glViewport", function () {
    return {
      onEnter(args) {
        countCall("glViewport");
        currentViewport = {
          x: toI32(args[0]),
          y: toI32(args[1]),
          width: toI32(args[2]),
          height: toI32(args[3]),
        };
      },
    };
  });

  ["glFlush", "glFinish"].forEach((symbol) => {
    installHook(symbol, function (address) {
      return {
        onEnter() {
          countCall(symbol);
          if (!shouldEmit("gl_sync_call", 1000)) {
            return;
          }
          emit("gl_sync_call", {
            symbol,
            address: address.toString(),
            call_counts: Object.assign({}, callCounts),
          });
        },
      };
    });
  });

  function emitDraw(kind, address, fields) {
    countCall(kind);
    if (!shouldEmit("gl_draw_call", 250)) {
      return;
    }
    emit("gl_draw_call", {
      draw_kind: kind,
      address: address.toString(),
      current_program: currentProgram,
      current_framebuffer: currentFramebuffer,
      current_viewport: currentViewport,
      active_texture_unit: activeTextureUnit,
      bound_texture_2d_unit0: boundTextures.get(keyFor(0, GL_TEXTURE_2D)) || 0,
      bound_texture_2d_unit1: boundTextures.get(keyFor(1, GL_TEXTURE_2D)) || 0,
      bound_texture_external_unit0: boundTextures.get(keyFor(0, GL_TEXTURE_EXTERNAL_OES)) || 0,
      bound_texture_external_unit1: boundTextures.get(keyFor(1, GL_TEXTURE_EXTERNAL_OES)) || 0,
      fields,
    });
  }

  installHook("glDrawArrays", function (address) {
    return {
      onEnter(args) {
        emitDraw("glDrawArrays", address, {
          mode: toI32(args[0]),
          first: toI32(args[1]),
          count: toI32(args[2]),
        });
      },
    };
  });

  installHook("glDrawElements", function (address) {
    return {
      onEnter(args) {
        emitDraw("glDrawElements", address, {
          mode: toI32(args[0]),
          count: toI32(args[1]),
          type: toI32(args[2]),
          indices_pointer: args[3].toString(),
        });
      },
    };
  });

  [
    "glDrawTexiOES",
    "glDrawTexfOES",
    "glDrawTexsOES",
    "glDrawTexxOES",
  ].forEach((symbol) => {
    installHook(symbol, function (address) {
      return {
        onEnter(args) {
          emitDraw(symbol, address, {
            x: toI32(args[0]),
            y: toI32(args[1]),
            z: toI32(args[2]),
            width: toI32(args[3]),
            height: toI32(args[4]),
          });
        },
      };
    });
  });

  [
    "glDrawTexivOES",
    "glDrawTexfvOES",
    "glDrawTexsvOES",
    "glDrawTexxvOES",
  ].forEach((symbol) => {
    installHook(symbol, function (address) {
      return {
        onEnter(args) {
          emitDraw(symbol, address, {
            coords_pointer: args[0].toString(),
          });
        },
      };
    });
  });

  installHook("eglSwapBuffers", function (address) {
    return {
      onEnter(args) {
        countCall("eglSwapBuffers");
        if (!shouldEmit("egl_swap_buffers", 1000)) {
          return;
        }
        emit("egl_swap_buffers", {
          address: address.toString(),
          display_pointer: args[0].toString(),
          surface_pointer: args[1].toString(),
          call_counts: Object.assign({}, callCounts),
        });
      },
    };
  });

  ["eglSwapBuffersWithDamageKHR", "eglSwapBuffersWithDamageEXT"].forEach((symbol) => {
    installHook(symbol, function (address) {
      return {
        onEnter(args) {
          countCall(symbol);
          if (!shouldEmit("egl_swap_buffers", 1000)) {
            return;
          }
          emit("egl_swap_buffers", {
            symbol,
            address: address.toString(),
            display_pointer: args[0].toString(),
            surface_pointer: args[1].toString(),
            call_counts: Object.assign({}, callCounts),
          });
        },
      };
    });
  });

  installHook("eglGetProcAddress", function (address) {
    return {
      onEnter(args) {
        countCall("eglGetProcAddress");
        this.procName = readCString(args[0]);
      },
      onLeave(retval) {
        if (!this.procName || retval.isNull()) {
          return;
        }
        const factory = dynamicHookFactories[this.procName];
        if (factory !== undefined) {
          installHookAtAddress(this.procName, retval, factory, "eglGetProcAddress");
        }
        if (shouldEmit("egl_get_proc_address", 500)) {
          emit("egl_get_proc_address", {
            requested_symbol: this.procName,
            return_pointer: retval.toString(),
            hooked: factory !== undefined,
          });
        }
      },
    };
  });
}

setImmediate(function () {
  emit("probe_start", {
    architecture: Process.arch,
    platform: Process.platform,
    relevant_modules: Process.enumerateModules()
      .filter((item) => /GLES|EGL|adreno|mali|GameProc|AMAIN/i.test(item.name))
      .map((item) => ({
        name: item.name,
        path: item.path,
        base: item.base.toString(),
        size: item.size,
      })),
  });
  installGlHooks();
  setInterval(function () {
    emit("gl_probe_counters", {
      call_counts: Object.assign({}, callCounts),
      current_program: currentProgram,
      current_framebuffer: currentFramebuffer,
      current_viewport: currentViewport,
      active_texture_unit: activeTextureUnit,
      known_binding_count: boundTextures.size,
    });
  }, 1000);
  emit("probe_ready", { hook_counts: hookCounts });
});
