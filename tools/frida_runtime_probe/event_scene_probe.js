"use strict";

const moduleName = "libGameProc.so";
const bucketCount = 127;
const bucketSize = 24;
const loaderBucketOffset = 0x20;
const sceneLoaderOffset = 0x48;

let gameModule = null;
let sceneObject = null;
let pendingRequest = null;
let requestSequence = 0;
let lastAnimationRequest = null;
let lastAnimationFrameObject = null;
let activeForcedEvent = null;
let hooksInstalled = false;

function emit(kind, fields) {
  const eventFields =
    activeForcedEvent === null
      ? {}
      : {
          forced_event_code: activeForcedEvent.code_hex,
          forced_event_label: activeForcedEvent.label,
          forced_event_request_id: activeForcedEvent.request_id,
          forced_event_relative_ms: Date.now() - activeForcedEvent.start_unix_ms,
        };
  send(
    Object.assign(
      {
        kind,
        unix_ms: Date.now(),
        thread_id: Process.getCurrentThreadId(),
      },
      eventFields,
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

function safeCString(pointerValue) {
  if (pointerValue === null || pointerValue.isNull()) {
    return null;
  }
  try {
    return pointerValue.readCString();
  } catch (_) {
    return null;
  }
}

function readMemoryHex(pointerValue, relativeOffset, size) {
  if (pointerValue === null || pointerValue.isNull()) {
    return { address: null, hex: "", error: "null pointer" };
  }
  const address = pointerValue.add(relativeOffset);
  try {
    const bytes = new Uint8Array(address.readByteArray(size));
    let hex = "";
    for (let index = 0; index < bytes.length; index += 1) {
      hex += bytes[index].toString(16).padStart(2, "0");
    }
    return { address: address.toString(), hex, error: "" };
  } catch (error) {
    return { address: address.toString(), hex: "", error: String(error) };
  }
}

function describeAddress(pointerValue) {
  if (pointerValue === null || pointerValue.isNull()) {
    return null;
  }
  const range = Process.findRangeByAddress(pointerValue);
  if (range === null) {
    return { pointer: pointerValue.toString(), readable: false };
  }
  const result = {
    pointer: pointerValue.toString(),
    readable: range.protection.indexOf("r") !== -1,
    range_base: range.base.toString(),
    range_size: range.size,
    protection: range.protection,
  };
  if (range.file) {
    result.file = {
      path: range.file.path,
      offset: range.file.offset,
      size: range.file.size,
    };
  }
  return result;
}

function describeZ2DCallbackElement(element) {
  if (element === null || element.isNull()) {
    return { error: "null element" };
  }
  try {
    const argData = element.add(0x20).readPointer();
    const argCapacity = element.add(0x28).readU32();
    const argCount = element.add(0x2c).readU32();
    const rawFunctionName = element.add(0x30).readPointer();
    const copyStrings = element.add(0x44).readU8() !== 0;
    const functionNamePointer =
      copyStrings && !rawFunctionName.isNull()
        ? rawFunctionName.readPointer()
        : rawFunctionName;
    const args = [];
    const safeArgCount = Math.min(argCount, 64);
    for (let index = 0; index < safeArgCount; index += 1) {
      const record = argData.add(index * 0x10);
      const typeAndFlag = record.readU8();
      const type = typeAndFlag & 0xf;
      const flag = typeAndFlag >>> 4;
      const valueAddress = record.add(0x8);
      const item = { index, type, flag };
      if (type === 1) {
        item.value_int = valueAddress.readS32();
      } else if (type === 2) {
        item.value_float = valueAddress.readFloat();
      } else if (type === 3) {
        const rawString = valueAddress.readPointer();
        const stringPointer =
          copyStrings && !rawString.isNull() ? rawString.readPointer() : rawString;
        item.value_string = safeCString(stringPointer);
        item.string_address = describeAddress(stringPointer);
      }
      args.push(item);
    }
    return {
      arg_data: describeAddress(argData),
      arg_capacity: argCapacity,
      arg_count: argCount,
      copy_strings: copyStrings,
      function_name: safeCString(functionNamePointer),
      function_name_address: describeAddress(functionNamePointer),
      function_hash_u32: element.add(0x38).readU32(),
      exec_frame: element.add(0x3c).readS32(),
      args,
    };
  } catch (error) {
    return { error: String(error) };
  }
}

function padHex(value) {
  return (value >>> 0).toString(16).padStart(8, "0");
}

function hashPart(text, multiplier) {
  const bytes = unescape(encodeURIComponent(text));
  let value = 0;
  for (let index = 0; index < bytes.length; index += 1) {
    let byteValue = bytes.charCodeAt(index);
    if (byteValue >= 0x80) {
      byteValue -= 0x100;
    }
    value = Math.imul((value + byteValue) | 0, multiplier) >>> 0;
  }
  return value >>> 0;
}

function eventCodeForName(name) {
  const low = hashPart(name, 31);
  const high = hashPart(name, 73);
  return {
    name,
    low_u32: low,
    high_u32: high,
    hex: "0x" + padHex(high) + padHex(low),
  };
}

function getSceneObject() {
  if (sceneObject === null) {
    const call = new NativeFunction(
      findExport("_ZN2zg5SCENEEv"),
      "pointer",
      []
    );
    sceneObject = call();
  }
  return sceneObject;
}

function getLoader() {
  const scene = getSceneObject();
  if (scene === null || scene.isNull()) {
    return null;
  }
  try {
    return scene.add(sceneLoaderOffset).readPointer();
  } catch (_) {
    return null;
  }
}

function describeObject(pointerValue) {
  if (pointerValue === null || pointerValue.isNull()) {
    return null;
  }
  try {
    const vtable = pointerValue.readPointer();
    const moduleValue = Process.findModuleByAddress(vtable);
    return {
      pointer: pointerValue.toString(),
      vtable: vtable.toString(),
      vtable_module: moduleValue === null ? null : moduleValue.name,
      vtable_module_offset:
        moduleValue === null ? null : vtable.sub(moduleValue.base).toString(),
      readable: Process.findRangeByAddress(pointerValue) !== null,
    };
  } catch (error) {
    return {
      pointer: pointerValue.toString(),
      error: String(error),
      readable: false,
    };
  }
}

function getAnimationState() {
  let manager = null;
  let managerTask = null;
  let taskGame = null;
  let currentTaskId = null;
  let oldTaskId = null;
  const errors = [];

  try {
    const getManager = new NativeFunction(findExport("_Z6ANMMNGv"), "pointer", []);
    manager = getManager();
    if (!manager.isNull()) {
      currentTaskId = manager.readU32();
      oldTaskId = manager.add(4).readU32();
      managerTask = manager.add(8).readPointer();
    }
  } catch (error) {
    errors.push("ANMMNG: " + String(error));
  }

  try {
    const getTaskGame = new NativeFunction(findExport("_Z8TSK_GAMEv"), "pointer", []);
    taskGame = getTaskGame();
  } catch (error) {
    errors.push("TSK_GAME: " + String(error));
  }

  let selected = null;
  let selectedSource = null;
  const managerDescription = describeObject(managerTask);
  const taskGameDescription = describeObject(taskGame);
  const observedDescription =
    lastAnimationRequest === null
      ? null
      : describeObject(ptr(lastAnimationRequest.animation_object));
  const frameDescription =
    lastAnimationFrameObject === null
      ? null
      : describeObject(ptr(lastAnimationFrameObject.animation_object));
  let activeChild = null;
  let activeChildDescription = null;
  if (lastAnimationFrameObject !== null) {
    try {
      activeChild = ptr(lastAnimationFrameObject.animation_object)
        .add(0x350)
        .readPointer();
      activeChildDescription = describeObject(activeChild);
    } catch (error) {
      errors.push("C_AnmMain+0x350: " + String(error));
    }
  }
  if (
    observedDescription !== null &&
    observedDescription.readable &&
    observedDescription.vtable_module !== null
  ) {
    selected = ptr(lastAnimationRequest.animation_object);
    selectedSource = "last_animation_request";
  } else if (
    activeChildDescription !== null &&
    activeChildDescription.readable &&
    activeChildDescription.vtable_module !== null
  ) {
    selected = activeChild;
    selectedSource = "C_AnmMain+0x350";
  } else if (
    frameDescription !== null &&
    frameDescription.readable &&
    frameDescription.vtable_module !== null
  ) {
    selected = ptr(lastAnimationFrameObject.animation_object);
    selectedSource = "C_AnmMain::pre";
  } else if (
    managerDescription !== null &&
    managerDescription.readable &&
    managerDescription.vtable_module !== null
  ) {
    selected = managerTask;
    selectedSource = "ANMMNG+0x8";
  } else if (
    taskGameDescription !== null &&
    taskGameDescription.readable &&
    taskGameDescription.vtable_module !== null
  ) {
    selected = taskGame;
    selectedSource = "TSK_GAME";
  }

  return {
    manager: manager === null ? null : manager.toString(),
    current_task_id: currentTaskId,
    old_task_id: oldTaskId,
    manager_task: managerDescription,
    task_game: taskGameDescription,
    observed_animation_object: observedDescription,
    frame_animation_object: frameDescription,
    active_animation_child: activeChildDescription,
    last_animation_frame: lastAnimationFrameObject,
    selected_object: describeObject(selected),
    selected_source: selectedSource,
    errors,
  };
}

function loaderStatus() {
  const scene = getSceneObject();
  const loader = getLoader();
  let count = null;
  if (loader !== null && !loader.isNull()) {
    try {
      count = loader.add(0x18).readU32();
    } catch (_) {
      count = null;
    }
  }
  return {
    module_base: gameModule === null ? null : gameModule.base.toString(),
    scene_object: scene === null ? null : scene.toString(),
    loader: loader === null ? null : loader.toString(),
    event_count: count,
    pending_request: pendingRequest,
    last_animation_request: lastAnimationRequest,
    animation_state: getAnimationState(),
  };
}

function printableCString(pointerValue) {
  const value = safeCString(pointerValue);
  if (value === null || value.length === 0 || value.length > 256) {
    return null;
  }
  for (let index = 0; index < value.length; index += 1) {
    const code = value.charCodeAt(index);
    if (code < 0x20 || code > 0x7e) {
      return null;
    }
  }
  return value;
}

function dumpModuleAddress(relativeOffsetValue, sizeValue) {
  if (gameModule === null) {
    throw new Error("game module is not available");
  }
  const relativeOffset = Number(relativeOffsetValue);
  const size = Math.max(0, Math.min(Number(sizeValue), 0x4000));
  const address = gameModule.base.add(relativeOffset);
  const rows = [];
  for (let offset = 0; offset + Process.pointerSize <= size; offset += Process.pointerSize) {
    const slot = address.add(offset);
    let pointerValue = null;
    let unsignedValue = null;
    let stringValue = null;
    try {
      pointerValue = slot.readPointer();
      unsignedValue = slot.readU64();
      stringValue = printableCString(pointerValue);
    } catch (_) {
      pointerValue = null;
    }
    rows.push({
      relative_offset: "0x" + (relativeOffset + offset).toString(16),
      address: slot.toString(),
      u64_hex:
        unsignedValue === null
          ? null
          : "0x" + unsignedValue.toString(16).padStart(16, "0"),
      pointer: pointerValue === null ? null : pointerValue.toString(),
      pointed_cstring: stringValue,
    });
  }
  return {
    module_name: gameModule.name,
    module_base: gameModule.base.toString(),
    relative_offset: "0x" + relativeOffset.toString(16),
    address: address.toString(),
    size,
    rows,
  };
}

function searchSymbols(patternValue) {
  if (gameModule === null) {
    throw new Error("game module is not available");
  }
  const pattern = String(patternValue).toLowerCase();
  const entries = gameModule.enumerateSymbols().concat(gameModule.enumerateExports());
  const seen = new Set();
  return entries
    .filter((symbol) => symbol.name.toLowerCase().includes(pattern))
    .filter((symbol) => {
      const key = symbol.name + "@" + symbol.address.toString();
      if (seen.has(key)) {
        return false;
      }
      seen.add(key);
      return true;
    })
    .slice(0, 500)
    .map((symbol) => ({
      name: symbol.name,
      address: symbol.address.toString(),
      relative_offset: symbol.address.sub(gameModule.base).toString(),
      type: symbol.type,
    }));
}

function enumerateEventInfo(limitValue) {
  const table = findExport("EventInfo");
  const total = 0x39060 / 24;
  const limit =
    limitValue === undefined || limitValue === null
      ? total
      : Math.max(0, Math.min(Number(limitValue), total));
  const rows = [];
  for (let index = 0; index < limit; index += 1) {
    const entry = table.add(index * 24);
    const code = entry.readU64();
    rows.push({
      index,
      entry: entry.toString(),
      code_hex: "0x" + code.toString(16).padStart(16, "0"),
      base_name: safeCString(entry.add(8).readPointer()),
      scene_name: safeCString(entry.add(16).readPointer()),
    });
  }
  return {
    table: table.toString(),
    total,
    returned: rows.length,
    rows,
  };
}

function describeEventCode(codeHex, name) {
  const loader = getLoader();
  if (loader === null || loader.isNull()) {
    throw new Error("GBoss loader is not available");
  }
  const code = uint64(codeHex);
  const getEventObject = new NativeFunction(
    findExport("_ZN2zg11GBossLoader14getEventObjectEy"),
    "pointer",
    ["pointer", "uint64"]
  );
  const getAnimCount = new NativeFunction(
    findExport("zgGBossGetAnimCount"),
    "int",
    ["pointer", "uint64"]
  );
  const getAnimObject = new NativeFunction(
    findExport("zgGBossGetAnimObject"),
    "pointer",
    ["pointer", "uint64", "int"]
  );
  const getSoundCount = new NativeFunction(
    findExport("zgGBossGetSoundCount"),
    "int",
    ["pointer", "uint64"]
  );
  const getSoundObject = new NativeFunction(
    findExport("zgGBossGetSoundObject"),
    "pointer",
    ["pointer", "uint64", "int"]
  );
  const getSoundHashCode = new NativeFunction(
    findExport("zgGBossGetSoundHashCode"),
    "uint64",
    ["pointer"]
  );
  const getAnimGroupName = new NativeFunction(
    findExport("zgGBossGetAnimGroupName"),
    "pointer",
    ["pointer"]
  );
  const getAnimSceneCount = new NativeFunction(
    findExport("zgGBossGetAnimSceneCount"),
    "int",
    ["pointer"]
  );
  const getAnimSceneName = new NativeFunction(
    findExport("zgGBossGetAnimSceneName"),
    "pointer",
    ["pointer", "int"]
  );
  const getAnimChoiceCount = new NativeFunction(
    findExport("zgGBossGetAnimChoiceCount"),
    "int",
    ["pointer"]
  );
  const getAnimChoiceName = new NativeFunction(
    findExport("zgGBossGetAnimChoiceName"),
    "pointer",
    ["pointer", "int"]
  );
  const getAnimChoiceId = new NativeFunction(
    findExport("zgGBossGetAnimChoiceID"),
    "int",
    ["pointer", "int"]
  );

  const eventObject = getEventObject(loader, code);
  const animCount = getAnimCount(loader, code);
  const soundCount = getSoundCount(loader, code);
  const animations = [];
  const sounds = [];
  for (let animIndex = 0; animIndex < animCount; animIndex += 1) {
    const animation = getAnimObject(loader, code, animIndex);
    if (animation.isNull()) {
      continue;
    }
    const sceneCount = getAnimSceneCount(animation);
    const choiceCount = getAnimChoiceCount(animation);
    const scenes = [];
    const choices = [];
    for (let sceneIndex = 0; sceneIndex < sceneCount; sceneIndex += 1) {
      scenes.push(safeCString(getAnimSceneName(animation, sceneIndex)));
    }
    for (let choiceIndex = 0; choiceIndex < choiceCount; choiceIndex += 1) {
      choices.push({
        index: choiceIndex,
        id: getAnimChoiceId(animation, choiceIndex),
        name: safeCString(getAnimChoiceName(animation, choiceIndex)),
      });
    }
    animations.push({
      index: animIndex,
      pointer: animation.toString(),
      group_name: safeCString(getAnimGroupName(animation)),
      scene_count: sceneCount,
      scenes,
      choice_count: choiceCount,
      choices,
    });
  }
  for (let soundIndex = 0; soundIndex < soundCount; soundIndex += 1) {
    const sound = getSoundObject(loader, code, soundIndex);
    if (sound.isNull()) {
      continue;
    }
    const hashCode = getSoundHashCode(sound);
    sounds.push({
      index: soundIndex,
      pointer: sound.toString(),
      hash_code_hex: "0x" + hashCode.toString(16).padStart(16, "0"),
    });
  }

  return {
    name: name || null,
    code_hex: codeHex,
    event_object: eventObject.toString(),
    exists: !eventObject.isNull(),
    anim_count: animCount,
    animations,
    sound_count: soundCount,
    sounds,
  };
}

function enumerateEventCodes(limitValue) {
  const loader = getLoader();
  if (loader === null || loader.isNull()) {
    throw new Error("GBoss loader is not available");
  }
  const expected = loader.add(0x18).readU32();
  const limit =
    limitValue === undefined || limitValue === null
      ? expected
      : Math.max(0, Math.min(Number(limitValue), expected));
  const events = [];
  const visited = new Set();

  for (let bucketIndex = 0; bucketIndex < bucketCount; bucketIndex += 1) {
    const sentinel = loader
      .add(loaderBucketOffset)
      .add(bucketIndex * bucketSize);
    let node = sentinel.add(8).readPointer();
    let bucketSteps = 0;
    while (!node.equals(sentinel) && events.length < limit) {
      const key = node.toString();
      if (visited.has(key)) {
        throw new Error("cycle outside sentinel at " + key);
      }
      visited.add(key);
      const eventObject = node.add(16).readPointer();
      const code = eventObject.readU64();
      events.push({
        bucket: bucketIndex,
        node: key,
        event_object: eventObject.toString(),
        code_hex: "0x" + code.toString(16).padStart(16, "0"),
        anim_count: eventObject.add(8).readU32(),
        sound_count: eventObject.add(0x18).readU32(),
        lamp_count: eventObject.add(0x28).readU32(),
        control_count: eventObject.add(0x38).readU32(),
      });
      node = node.add(8).readPointer();
      bucketSteps += 1;
      if (bucketSteps > expected + 1) {
        throw new Error("bucket traversal exceeded event count");
      }
    }
    if (events.length >= limit) {
      break;
    }
  }
  return {
    expected_event_count: expected,
    returned_event_count: events.length,
    events,
  };
}

function executePendingRequest(source) {
  if (pendingRequest === null) {
    return;
  }
  const request = pendingRequest;
  pendingRequest = null;
  try {
    activeForcedEvent = {
      code_hex: request.code_hex,
      label: request.label,
      request_id: request.id,
      start_unix_ms: Date.now(),
    };
    emit("forced_event_context_started", { request });
    if (request.official) {
      const animationState = getAnimationState();
      if (
        !["last_animation_request", "C_AnmMain+0x350"].includes(
          animationState.selected_source
        ) ||
        animationState.selected_object === null ||
        !animationState.selected_object.readable
      ) {
        throw new Error(
          "no observed C_AnmBase instance: " + JSON.stringify(animationState)
        );
      }
      const call = new NativeFunction(
        findExport("_ZN9C_AnmBase10fnReqSceneEyhtt"),
        "void",
        ["pointer", "uint64", "uint8", "uint16", "uint16"]
      );
      call(
        ptr(animationState.selected_object.pointer),
        uint64(request.code_hex),
        request.immediate ? 1 : 0,
        request.layer_flags,
        request.request_flags
      );
    } else {
      const scene = getSceneObject();
      const call = new NativeFunction(
        findExport("_ZN2zg7C_Scene10fnReqSceneEyhPKc"),
        "void",
        ["pointer", "uint64", "uchar", "pointer"]
      );
      const label = Memory.allocUtf8String(request.label);
      call(scene, uint64(request.code_hex), request.immediate ? 1 : 0, label);
    }
    if (request.with_sound && !request.official) {
      const getSoundController = new NativeFunction(
        findExport("_Z10CTRLSNDLIBv"),
        "pointer",
        []
      );
      const requestSound = new NativeFunction(
        findExport("_ZN12C_CtrlSndLib17fnReqSndEventCodeEy"),
        "void",
        ["pointer", "uint64"]
      );
      requestSound(getSoundController(), uint64(request.code_hex));
    }
    emit("scene_request_executed", {
      request_id: request.id,
      execution_source: source,
      request,
      animation_state: request.official ? getAnimationState() : null,
      status_after: loaderStatus(),
    });
  } catch (error) {
    emit("scene_request_error", {
      request_id: request.id,
      execution_source: source,
      request,
      error: String(error),
      status_after: loaderStatus(),
    });
  }
}

function installHooks() {
  const requestAddress = findExport("_ZN2zg7C_Scene10fnReqSceneEyhPKc");
  Interceptor.attach(requestAddress, {
    onEnter(args) {
      emit("scene_request_observed", {
        address: requestAddress.toString(),
        scene_object: args[0].toString(),
        code_hex: "0x" + args[1].toString(16).padStart(16, "0"),
        immediate: args[2].toInt32() & 0xff,
        label: safeCString(args[3]),
      });
    },
  });

  const animationRequestAddress = findExport("_ZN9C_AnmBase10fnReqSceneEyhtt");
  Interceptor.attach(animationRequestAddress, {
    onEnter(args) {
      lastAnimationRequest = {
        animation_object: args[0].toString(),
        code_hex: "0x" + args[1].toString(16).padStart(16, "0"),
        immediate: args[2].toInt32() & 0xff,
        layer_flags: args[3].toInt32() & 0xffff,
        request_flags: args[4].toInt32() & 0xffff,
        unix_ms: Date.now(),
      };
      emit("animation_request_observed", {
        address: animationRequestAddress.toString(),
        ...lastAnimationRequest,
      });
    },
  });

  const animationFrameAddress = findExport("_ZN9C_AnmMain3preEv");
  Interceptor.attach(animationFrameAddress, {
    onEnter(args) {
      lastAnimationFrameObject = {
        animation_object: args[0].toString(),
        unix_ms: Date.now(),
      };
    },
  });

  const soundRequestAddress = findExport("_ZN12C_CtrlSndLib17fnReqSndEventCodeEy");
  Interceptor.attach(soundRequestAddress, {
    onEnter(args) {
      emit("sound_event_request_observed", {
        address: soundRequestAddress.toString(),
        controller: args[0].toString(),
        code_hex: "0x" + args[1].toString(16).padStart(16, "0"),
      });
    },
  });

  const codeLookupAddress = findExport(
    "_ZN2zg3snd11RequestCtrl14codeName2ReqIdEPKc"
  );
  Interceptor.attach(codeLookupAddress, {
    onEnter(args) {
      this.forcedCodeName =
        activeForcedEvent === null ? null : safeCString(args[1]);
    },
    onLeave(retval) {
      if (this.forcedCodeName === null) {
        return;
      }
      emit("forced_sound_code_lookup", {
        address: codeLookupAddress.toString(),
        code_name: this.forcedCodeName,
        request_id: retval.toUInt32(),
      });
    },
  });

  const soundPlayBytesAddress = findExport("_ZN8SoundMng4playEPhii");
  Interceptor.attach(soundPlayBytesAddress, {
    onEnter(args) {
      if (activeForcedEvent === null) {
        return;
      }
      emit("forced_sound_play", {
        address: soundPlayBytesAddress.toString(),
        code_name: safeCString(args[1]),
        arg2_i32: args[2].toInt32(),
        arg3_i32: args[3].toInt32(),
      });
    },
  });

  const z2dSoundAddress = findExport(
    "_ZN2zg19Z2DreqSoundCallbackEPNS_10CZ2DPlayerEPNS_15CZ2DElemUCBFuncEPv"
  );
  Interceptor.attach(z2dSoundAddress, {
    onEnter(args) {
      if (activeForcedEvent === null) {
        return;
      }
      emit("forced_z2d_sound_callback", {
        address: z2dSoundAddress.toString(),
        player: args[0].toString(),
        element: args[1].toString(),
        user_data: args[2].toString(),
        element_window: readMemoryHex(args[1], -0x40, 0x200),
        player_window: readMemoryHex(args[0], 0, 0x100),
        user_data_window: readMemoryHex(args[2], 0, 0x80),
        callback: describeZ2DCallbackElement(args[1]),
      });
    },
  });

  const readZ2DAddress = findExport("_ZN2zg10CZ2DPlayer7ReadZ2DEPKc");
  Interceptor.attach(readZ2DAddress, {
    onEnter(args) {
      if (activeForcedEvent === null) {
        return;
      }
      this.active = true;
      this.player = args[0].toString();
      this.filename = safeCString(args[1]);
      emit("forced_z2d_read_file", {
        address: readZ2DAddress.toString(),
        player: this.player,
        filename: this.filename,
        filename_address: describeAddress(args[1]),
      });
    },
    onLeave(retval) {
      if (!this.active) {
        return;
      }
      emit("forced_z2d_read_file_result", {
        address: readZ2DAddress.toString(),
        player: this.player,
        filename: this.filename,
        return_u32: retval.toUInt32(),
      });
    },
  });

  const makeZ2DAddress = findExport("_ZN2zg10CZ2DPlayer8MakeCZ2DEPv");
  Interceptor.attach(makeZ2DAddress, {
    onEnter(args) {
      if (activeForcedEvent === null) {
        return;
      }
      this.active = true;
      this.player = args[0].toString();
      emit("forced_z2d_make", {
        address: makeZ2DAddress.toString(),
        player: this.player,
        data: describeAddress(args[1]),
        data_head: readMemoryHex(args[1], 0, 0x100),
      });
    },
    onLeave(retval) {
      if (!this.active) {
        return;
      }
      emit("forced_z2d_make_result", {
        address: makeZ2DAddress.toString(),
        player: this.player,
        return_u32: retval.toUInt32(),
      });
    },
  });

  const createZ2DFileAddress = findExport("_ZN2zg15Z2DP_CreateFileEPKc");
  Interceptor.attach(createZ2DFileAddress, {
    onEnter(args) {
      if (activeForcedEvent === null) {
        return;
      }
      this.active = true;
      this.filename = safeCString(args[0]);
    },
    onLeave(retval) {
      if (!this.active) {
        return;
      }
      emit("forced_z2d_create_file", {
        address: createZ2DFileAddress.toString(),
        filename: this.filename,
        handle: retval.toString(),
      });
    },
  });

  const getZ2DFileDataAddress = findExport("_ZN2zg16Z2DP_GetFileDataEPv");
  Interceptor.attach(getZ2DFileDataAddress, {
    onEnter(args) {
      if (activeForcedEvent === null) {
        return;
      }
      this.active = true;
      this.handle = args[0].toString();
    },
    onLeave(retval) {
      if (!this.active) {
        return;
      }
      emit("forced_z2d_get_file_data", {
        address: getZ2DFileDataAddress.toString(),
        handle: this.handle,
        data: describeAddress(retval),
        data_head: readMemoryHex(retval, 0, 0x100),
      });
    },
  });

  const loadResourceAddress = findExport(
    "_ZN2zg18CGFDirectionPlayer16LoadResourceFileEPKcS2_"
  );
  Interceptor.attach(loadResourceAddress, {
    onEnter(args) {
      if (activeForcedEvent === null) {
        return;
      }
      emit("forced_direction_load_resource", {
        address: loadResourceAddress.toString(),
        player: args[0].toString(),
        filename: safeCString(args[1]),
        resource_root: safeCString(args[2]),
      });
    },
  });

  const calcAddress = findExport("_ZN8CScnSlot4CalcEv");
  Interceptor.attach(calcAddress, {
    onEnter() {
      executePendingRequest("CScnSlot::Calc");
    },
  });

  emit("hooks_installed", {
    request_address: requestAddress.toString(),
    animation_request_address: animationRequestAddress.toString(),
    animation_frame_address: animationFrameAddress.toString(),
    sound_request_address: soundRequestAddress.toString(),
    code_lookup_address: codeLookupAddress.toString(),
    sound_play_bytes_address: soundPlayBytesAddress.toString(),
    z2d_sound_address: z2dSoundAddress.toString(),
    read_z2d_address: readZ2DAddress.toString(),
    make_z2d_address: makeZ2DAddress.toString(),
    create_z2d_file_address: createZ2DFileAddress.toString(),
    get_z2d_file_data_address: getZ2DFileDataAddress.toString(),
    load_resource_address: loadResourceAddress.toString(),
    calc_address: calcAddress.toString(),
    status: loaderStatus(),
  });
  hooksInstalled = true;
}

function installWhenReady() {
  if (hooksInstalled) {
    return;
  }
  const calcAddress = Module.findGlobalExportByName("_ZN8CScnSlot4CalcEv");
  gameModule =
    calcAddress === null ? Process.findModuleByName(moduleName) : Process.findModuleByAddress(calcAddress);
  if (calcAddress === null || gameModule === null) {
    emit("probe_waiting", {
      reason: "CScnSlot::Calc is not loaded",
      requested_module: moduleName,
    });
    setTimeout(installWhenReady, 1000);
    return;
  }
  try {
    installHooks();
  } catch (error) {
    emit("probe_error", { error: String(error), status: loaderStatus() });
  }
}

setImmediate(installWhenReady);

rpc.exports = {
  status() {
    return loaderStatus();
  },
  hash(name) {
    return eventCodeForName(String(name));
  },
  inspect(name) {
    const code = eventCodeForName(String(name));
    return Object.assign({}, code, describeEventCode(code.hex, code.name));
  },
  enumerate(limitValue) {
    return enumerateEventCodes(limitValue);
  },
  eventinfo(limitValue) {
    return enumerateEventInfo(limitValue);
  },
  queuerequest(name, immediateValue) {
    if (pendingRequest !== null) {
      throw new Error("a scene request is already pending");
    }
    const code = eventCodeForName(String(name));
    requestSequence += 1;
    pendingRequest = {
      id: requestSequence,
      name: code.name,
      label: code.name,
      code_hex: code.hex,
      immediate: Boolean(immediateValue),
      queued_unix_ms: Date.now(),
    };
    return {
      accepted: true,
      request: pendingRequest,
      event: describeEventCode(code.hex, code.name),
    };
  },
  inspectcode(codeHex) {
    return describeEventCode(String(codeHex), null);
  },
  queuecode(codeHex, labelValue, immediateValue, withSoundValue, officialValue) {
    if (pendingRequest !== null) {
      throw new Error("a scene request is already pending");
    }
    const normalizedCode = String(codeHex);
    const label = labelValue ? String(labelValue) : normalizedCode;
    requestSequence += 1;
    pendingRequest = {
      id: requestSequence,
      name: null,
      label,
      code_hex: normalizedCode,
      immediate: Boolean(immediateValue),
      with_sound: Boolean(withSoundValue),
      official: Boolean(officialValue),
      layer_flags:
        officialValue && lastAnimationRequest !== null
          ? lastAnimationRequest.layer_flags
          : 0,
      request_flags:
        officialValue && lastAnimationRequest !== null
          ? lastAnimationRequest.request_flags
          : 0,
      queued_unix_ms: Date.now(),
    };
    return {
      accepted: true,
      request: pendingRequest,
      event: describeEventCode(normalizedCode, label),
    };
  },
  dump(relativeOffsetValue, sizeValue) {
    return dumpModuleAddress(relativeOffsetValue, sizeValue);
  },
  symbols(patternValue) {
    return searchSymbols(patternValue);
  },
};
