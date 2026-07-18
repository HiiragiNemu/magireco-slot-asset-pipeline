"use strict";

// Read-only, fixed-field snapshot of CplayData's seven addon values.  This
// script never calls SetAddonID/getInstance, never writes memory, and never
// changes purchase/config state.  Offsets are version-specific evidence for
// libGameProc.so SHA-256 5A0AE3CE...26F17EBF.

const INSTANCE_SYMBOL = "_ZZN9CplayData11getInstanceEvE18mcplayDataInstance";
const ACTIVE_ADDON_BASE_OFFSET = 0x14bf4;
const SAVED_ADDON_BASE_OFFSET = 0x14a58;
const ADDON_COUNT = 7;
const ADDON_METADATA = [
  { sku: "magireco_addon_01", label: "save_data", archive_impact: "operational_only" },
  { sku: "magireco_addon_02", label: "wait_cut", archive_impact: "operational_only" },
  { sku: "magireco_addon_03", label: "settings_change", archive_impact: "route_probability_control" },
  { sku: "magireco_addon_04", label: "auto_play", archive_impact: "operational_only" },
  { sku: "magireco_addon_05", label: "forced_role", archive_impact: "forced_route_control" },
  { sku: "magireco_addon_06", label: "value_pack", archive_impact: "bundle_indices_0_through_4" },
  { sku: "magireco_addon_07", label: "sound_pack", archive_impact: "audio_playback_gate" },
];

function hex(value) {
  return "0x" + value.toString(16);
}

function readU32Fixed(base, offset) {
  try {
    return { value: base.add(offset).readU32(), error: "" };
  } catch (error) {
    return { value: null, error: String(error) };
  }
}

function snapshot() {
  const instance = Module.findGlobalExportByName(INSTANCE_SYMBOL);
  if (instance === null) {
    return {
      schema: "magireco-addon-entitlement-snapshot-v1",
      kind: "addon_entitlement_snapshot",
      ok: false,
      error: "CplayData singleton export is unavailable",
      process: {
        id: Process.id,
        arch: Process.arch,
        pointer_size: Process.pointerSize,
      },
      instance_symbol: INSTANCE_SYMBOL,
      read_policy: "seven_named_u32_active_and_saved_fields_no_calls_no_writes",
    };
  }
  const moduleValue = Process.findModuleByAddress(instance);
  if (moduleValue === null) {
    return {
      schema: "magireco-addon-entitlement-snapshot-v1",
      kind: "addon_entitlement_snapshot",
      ok: false,
      error: "CplayData singleton export has no owning module",
      process: {
        id: Process.id,
        arch: Process.arch,
        pointer_size: Process.pointerSize,
      },
      instance_symbol: INSTANCE_SYMBOL,
      instance_address: instance.toString(),
      read_policy: "seven_named_u32_active_and_saved_fields_no_calls_no_writes",
    };
  }

  const rows = [];
  let readOk = true;
  for (let index = 0; index < ADDON_COUNT; index += 1) {
    const activeOffset = ACTIVE_ADDON_BASE_OFFSET + index * 4;
    const savedOffset = SAVED_ADDON_BASE_OFFSET + index * 4;
    const active = readU32Fixed(instance, activeOffset);
    const saved = readU32Fixed(instance, savedOffset);
    if (active.error !== "" || saved.error !== "") {
      readOk = false;
    }
    rows.push({
      index: index,
      sku: ADDON_METADATA[index].sku,
      label: ADDON_METADATA[index].label,
      archive_impact: ADDON_METADATA[index].archive_impact,
      active_offset: hex(activeOffset),
      active_u32: active.value,
      active_read_error: active.error,
      saved_offset: hex(savedOffset),
      saved_u32: saved.value,
      saved_read_error: saved.error,
    });
  }

  return {
    schema: "magireco-addon-entitlement-snapshot-v1",
    kind: "addon_entitlement_snapshot",
    ok: readOk,
    error: readOk ? "" : "one or more fixed-field reads failed",
    process: {
      id: Process.id,
      arch: Process.arch,
      pointer_size: Process.pointerSize,
    },
    module: {
      name: moduleValue.name,
      path: moduleValue.path,
      base: moduleValue.base.toString(),
      size: moduleValue.size,
    },
    instance_symbol: INSTANCE_SYMBOL,
    instance_address: instance.toString(),
    instance_module_offset: hex(instance.sub(moduleValue.base).toUInt32()),
    active_addon_base_offset: hex(ACTIVE_ADDON_BASE_OFFSET),
    saved_addon_base_offset: hex(SAVED_ADDON_BASE_OFFSET),
    sound_pack_candidate_index: 6,
    sound_pack_index_basis: "version_specific_static_native_and_official_product_semantics",
    addon_index_map_basis: "java_sku_order_plus_CplayData_SetAddonID_and_native_xrefs",
    value_pack_policy: "index_5_sets_indices_0_through_5_but_not_index_6",
    read_policy: "seven_named_u32_active_and_saved_fields_no_calls_no_writes",
    rows: rows,
  };
}

rpc.exports = {
  snapshot() {
    return snapshot();
  },
};

setImmediate(function () {
  send(snapshot());
});
