"use strict";

// Read-only runtime symbol/export survey for renderer and CRI investigation.
//
// This script enumerates loaded modules and emits symbol/export names matching
// likely video, GL, EGL, Surface, and CRI-Mana paths.  It does not call game
// functions, dump memory, or modify runtime state.

const matchPattern =
  /ANativeWindow|Surface|BufferQueue|queueBuffer|eglSwap|eglGetProc|glDraw|glTex|glBind|DrawTex|CriMana|criMana|FrameYUVA|GetFrame|ExecuteVideo|ScreenObject|DirGet|GLtask|Texture|RenderTarget|Window/i;
const maxMatchesPerModule = 200;
const maxTotalMatches = 2500;

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

function safeEnumerate(moduleValue, methodName) {
  try {
    return moduleValue[methodName]();
  } catch (error) {
    emit("symbol_survey_enumeration_failed", {
      module_name: moduleValue.name,
      module_path: moduleValue.path,
      method: methodName,
      error: String(error),
    });
    return [];
  }
}

setImmediate(function () {
  const modules = Process.enumerateModules();
  emit("symbol_survey_start", {
    architecture: Process.arch,
    platform: Process.platform,
    module_count: modules.length,
    pattern: matchPattern.source,
    relevant_modules: modules
      .filter((item) => matchPattern.test(item.name + "\n" + item.path))
      .map((item) => ({
        name: item.name,
        path: item.path,
        base: item.base.toString(),
        size: item.size,
      })),
  });

  let totalMatches = 0;
  for (const moduleValue of modules) {
    if (totalMatches >= maxTotalMatches) {
      break;
    }
    const localMatches = [];
    [
      ["export", "enumerateExports"],
      ["symbol", "enumerateSymbols"],
    ].forEach((item) => {
      if (localMatches.length >= maxMatchesPerModule || totalMatches >= maxTotalMatches) {
        return;
      }
      const sourceKind = item[0];
      const methodName = item[1];
      safeEnumerate(moduleValue, methodName).forEach((entry) => {
        if (localMatches.length >= maxMatchesPerModule || totalMatches >= maxTotalMatches) {
          return;
        }
        if (!entry.name || !matchPattern.test(entry.name)) {
          return;
        }
        localMatches.push({
          source_kind: sourceKind,
          name: entry.name,
          type: entry.type || "",
          address: entry.address ? entry.address.toString() : null,
        });
        totalMatches += 1;
      });
    });
    if (localMatches.length > 0) {
      emit("symbol_survey_module_matches", {
        module_name: moduleValue.name,
        module_path: moduleValue.path,
        module_base: moduleValue.base.toString(),
        module_size: moduleValue.size,
        match_count_emitted: localMatches.length,
        truncated_at_module_limit: localMatches.length >= maxMatchesPerModule,
        matches: localMatches,
      });
    }
  }

  emit("symbol_survey_done", {
    total_matches_emitted: totalMatches,
    truncated_at_total_limit: totalMatches >= maxTotalMatches,
  });
});
