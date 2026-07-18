"use strict";

// Executable Node regression for the exact production window/dedup functions.
// It extracts the functions from sound_logic_chain_probe.js so this test cannot
// silently pass against a separately copied implementation.

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const probePath = path.join(__dirname, "sound_logic_chain_probe.js");
const probeSource = fs.readFileSync(probePath, "utf8");
const functionsStart = probeSource.indexOf("function beginBgmUpstreamWindow(");
const functionsEnd = probeSource.indexOf("function installBgmUpstreamHooks(");
assert(functionsStart >= 0, "production beginBgmUpstreamWindow was not found");
assert(functionsEnd > functionsStart, "production BGM window function range was not found");
const productionFunctions = probeSource.slice(functionsStart, functionsEnd);

const sandbox = { assert, console };
vm.createContext(sandbox);
vm.runInContext(
  `
"use strict";
const MAX_BGM_UPSTREAM_EVENTS_PER_WINDOW = 1024;
let bgmUpstreamWindowActive = false;
let bgmUpstreamWindowLabel = "";
let bgmUpstreamWindowEpoch = 0;
let bgmUpstreamWindowEventCount = 0;
let bgmUpstreamWindowDroppedCount = 0;
let bgmUpstreamWindowOverflowEmitted = false;
let bgmUpstreamSignatureByHook = {};
const emitted = [];
function emit(kind, fields) {
  emitted.push({ kind, fields });
}

${productionFunctions}

function emitState(hook, objectPointer, state, callId) {
  emitBgmUpstream(
    hook,
    "state_event",
    { bgm_upstream_call_id: callId, committed: state },
    JSON.stringify(state),
    false,
    objectPointer
  );
}

// A changing audit-only call_id must not defeat state suppression.
beginBgmUpstreamWindow("same-object-1000");
for (let callId = 1; callId <= 1000; callId += 1) {
  emitState("anmBaseDataSetDir", "0x1000", { kind: 47, no: 12 }, callId);
}
assert.strictEqual(emitted.length, 1);
assert.strictEqual(emitted[0].fields.bgm_upstream_call_id, 1);
assert.strictEqual(emitted[0].fields.emission_reason, "first_observation_in_window");

// The same state on another object is independently observable; a state
// transition on the original object is observable exactly once.
emitState("anmBaseDataSetDir", "0x2000", { kind: 47, no: 12 }, 1001);
emitState("anmBaseDataSetDir", "0x1000", { kind: 47, no: 13 }, 1002);
for (let callId = 1003; callId <= 2000; callId += 1) {
  emitState("anmBaseDataSetDir", "0x1000", { kind: 47, no: 13 }, callId);
}
let closed = endBgmUpstreamWindow();
assert.strictEqual(closed.active, false);
assert.strictEqual(closed.emitted_event_count, 3);
assert.strictEqual(closed.dropped_event_count, 0);
assert.strictEqual(emitted[1].fields.emission_reason, "first_observation_in_window");
assert.strictEqual(emitted[2].fields.emission_reason, "state_changed_in_window");
const afterCloseCount = emitted.length;
emitState("anmBaseDataSetDir", "0x3000", { kind: 1, no: 1 }, 2001);
assert.strictEqual(emitted.length, afterCloseCount, "closed window accepted an event");

// Starting a new window resets partition state.
beginBgmUpstreamWindow("new-window");
emitState("anmBaseDataSetDir", "0x1000", { kind: 47, no: 13 }, 2002);
closed = endBgmUpstreamWindow();
assert.strictEqual(closed.emitted_event_count, 1);

// Synthetic replay with the measured failed-run cardinalities:
// 960 DataSet calls across 17 objects -> 31 partitioned states;
// 63 BGM_DIR calls -> 2 states; 34 lottery pairs remain every-call.
emitted.length = 0;
beginBgmUpstreamWindow("measured-cardinality-replay");
for (let objectIndex = 0; objectIndex < 17; objectIndex += 1) {
  emitState("anmBaseDataSetDir", "obj-" + objectIndex, { phase: 0 }, objectIndex);
}
for (let objectIndex = 0; objectIndex < 14; objectIndex += 1) {
  emitState("anmBaseDataSetDir", "obj-" + objectIndex, { phase: 1 }, 17 + objectIndex);
}
for (let index = 31; index < 960; index += 1) {
  const objectIndex = index % 17;
  emitState(
    "anmBaseDataSetDir",
    "obj-" + objectIndex,
    { phase: objectIndex < 14 ? 1 : 0 },
    index
  );
}
for (let index = 0; index < 63; index += 1) {
  const state = index < 31 ? { entry: 0, leave: 0 } : { entry: 0, leave: 1 };
  emitBgmUpstream(
    "objNmlSndRequestBgmDir",
    "bgm_dir_event",
    { bgm_upstream_call_id: 960 + index, entry: state.entry, leave: state.leave },
    JSON.stringify(state),
    false,
    "bgm-obj"
  );
}
for (let index = 0; index < 34; index += 1) {
  emitBgmUpstream(
    "kndCalLotRlStart",
    "lottery_event",
    { bgm_upstream_call_id: 1023 + index },
    "same-lottery-state",
    true
  );
}
closed = endBgmUpstreamWindow();
assert.strictEqual(closed.emitted_event_count, 31 + 2 + 34);
assert.strictEqual(closed.dropped_event_count, 0);
assert.strictEqual(emitted.filter((row) => row.kind === "state_event").length, 31);
assert.strictEqual(emitted.filter((row) => row.kind === "bgm_dir_event").length, 2);
assert.strictEqual(emitted.filter((row) => row.kind === "lottery_event").length, 34);

// Overflow emits one diagnostic, preserves final counters on close, and never
// accepts events after close. Additional dropped state changes update only the
// final dropped counter, not the diagnostic count.
emitted.length = 0;
beginBgmUpstreamWindow("overflow-close");
for (let index = 0; index < 1025; index += 1) {
  emitState("anmBaseDataSetDir", "overflow-" + index, { state: index }, index);
}
for (let index = 1025; index < 1035; index += 1) {
  emitState("anmBaseDataSetDir", "overflow-" + index, { state: index }, index);
}
closed = endBgmUpstreamWindow();
assert.strictEqual(closed.active, false);
assert.strictEqual(closed.emitted_event_count, 1024);
assert.strictEqual(closed.dropped_event_count, 11);
assert.strictEqual(
  emitted.filter((row) => row.kind === "sound_logic_bgm_upstream_trace_overflow").length,
  1
);
const overflowClosedCount = emitted.length;
emitState("anmBaseDataSetDir", "post-close", { state: 9999 }, 9999);
assert.strictEqual(emitted.length, overflowClosedCount);

console.log(JSON.stringify({
  ok: true,
  same_object_repeated_calls: 1000,
  same_object_emitted_events: 1,
  measured_replay: { data_set: 31, bgm_dir: 2, lottery: 34, total: 67 },
  overflow: { emitted: closed.emitted_event_count, dropped: closed.dropped_event_count },
}));
`,
  sandbox,
  { filename: "bgm-upstream-dedup-production-harness.js" }
);
