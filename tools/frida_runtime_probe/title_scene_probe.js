"use strict";

const moduleName = "libGameProc.so";
const rootTitleCalcSymbol = "_ZN9CScnTitle4CalcEv";
const titleSmuCalcSymbol = "_ZN12CScnTitleSmu4CalcEv";
const loadCalcSymbol = "_ZN8CScnLoad4CalcEv";
const slotCalcSymbol = "_ZN8CScnSlot4CalcEv";

let moduleInfo = null;
let rootTitleObject = null;
let titleSmuObject = null;
let loadObject = null;
let slotObject = null;
let pendingEnterSlot = false;
let rootTransitionApplied = false;
let smuTransitionApplied = false;

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
  const address = Module.findGlobalExportByName(symbol);
  if (address === null) {
    throw new Error("missing export: " + symbol);
  }
  return address;
}

function readSceneState(objectValue) {
  if (objectValue === null || objectValue.isNull()) {
    return null;
  }
  try {
    return {
      object: objectValue.toString(),
      ready_state: objectValue.add(0x10).readS32(),
      transition_state: objectValue.add(0x14).readS32(),
    };
  } catch (error) {
    return {
      object: objectValue.toString(),
      error: String(error),
    };
  }
}

function installSceneHook(symbol, label, setter, transition) {
  const address = findExport(symbol);
  Interceptor.attach(address, {
    onEnter(args) {
      const objectValue = args[0];
      setter(objectValue);
      if (transition !== null) {
        this.objectValue = objectValue;
      }
    },
    onLeave() {
      if (transition !== null && this.objectValue !== null) {
        transition(this.objectValue);
      }
    },
  });
  emit("scene_hook_installed", {
    scene: label,
    symbol,
    address: address.toString(),
  });
}

function installHooks() {
  const titleCalcAddress = findExport(rootTitleCalcSymbol);
  moduleInfo = Process.findModuleByAddress(titleCalcAddress);
  if (moduleInfo === null) {
    throw new Error(
      "could not resolve module for title calc at " + titleCalcAddress
    );
  }
  installSceneHook(
    rootTitleCalcSymbol,
    "root_title",
    (value) => {
      rootTitleObject = value;
    },
    (value) => {
      if (!pendingEnterSlot || rootTransitionApplied) {
        return;
      }
      const before = readSceneState(value);
      value.add(0x14).writeS32(1);
      value.add(0xe5).writeU8(1);
      rootTransitionApplied = true;
      emit("root_title_transition_applied", {
        before,
        after: readSceneState(value),
      });
    }
  );
  installSceneHook(
    titleSmuCalcSymbol,
    "title_smu",
    (value) => {
      titleSmuObject = value;
    },
    (value) => {
      if (!pendingEnterSlot || smuTransitionApplied) {
        return;
      }
      const before = readSceneState(value);
      value.add(0x14).writeS32(2);
      smuTransitionApplied = true;
      pendingEnterSlot = false;
      emit("title_smu_transition_applied", {
        before,
        after: readSceneState(value),
      });
    }
  );
  installSceneHook(
    loadCalcSymbol,
    "load",
    (value) => {
      if (loadObject === null || !loadObject.equals(value)) {
        loadObject = value;
        emit("scene_observed", {
          scene: "load",
          state: readSceneState(value),
        });
      }
    },
    null
  );
  installSceneHook(
    slotCalcSymbol,
    "slot",
    (value) => {
      if (slotObject === null || !slotObject.equals(value)) {
        slotObject = value;
        emit("scene_observed", {
          scene: "slot",
          state: readSceneState(value),
        });
      }
    },
    null
  );
}

rpc.exports = {
  status() {
    return {
      module_base: moduleInfo === null ? null : moduleInfo.base.toString(),
      root_title: readSceneState(rootTitleObject),
      title_smu: readSceneState(titleSmuObject),
      load: readSceneState(loadObject),
      slot: readSceneState(slotObject),
      pending_enter_slot: pendingEnterSlot,
      root_transition_applied: rootTransitionApplied,
      smu_transition_applied: smuTransitionApplied,
    };
  },
  enterslot() {
    if (slotObject !== null && !slotObject.isNull()) {
      return {
        queued: false,
        reason: "slot_already_observed",
        status: this.status(),
      };
    }
    pendingEnterSlot = true;
    rootTransitionApplied = false;
    smuTransitionApplied = false;
    return {
      queued: true,
      status: this.status(),
    };
  },
};

setImmediate(() => {
  try {
    installHooks();
    emit("title_probe_ready", rpc.exports.status());
  } catch (error) {
    emit("title_probe_error", {
      error: String(error),
      stack: error.stack || null,
    });
  }
});
