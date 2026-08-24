"""Read-only IDA batch extractor for the exact Slot Z2D renderer order contract."""

from __future__ import annotations

import json
import sys

import ida_auto
import ida_funcs
import ida_hexrays
import ida_name
import ida_nalt
import idaapi
import idautils


TARGETS = {
    0x434A7E4: "RendererImplGL_setBlendMode",
    0x435A0B4: "CZ2DHardPlayer_DrawMovie",
    0x435DE7C: "CZ2DPlayer_CalcPrimitiveList",
    0x435E4CC: "CZ2DPlayer_DrawLayer",
    0x436234C: "CZ2DPlayGlobal_GetNextPrim",
    0x43626F0: "CZ2DPlayGlobal_GetDrawPrimNo",
    0x4362704: "CZ2DPlayGlobal_GetDrawPrimList",
    0x436388C: "CZ2DPlayBufferHandle_Exec_Sort",
    0x43639E4: "CZ2DPlayBufferHandle_Exec_Draw",
}


def decompile(ea: int) -> tuple[str, str]:
    try:
        return str(ida_hexrays.decompile(ea)), ""
    except Exception as exc:  # pragma: no cover - runs inside IDA
        return "", repr(exc)


def function_name(ea: int) -> str:
    raw = ida_name.get_name(ea)
    return ida_name.demangle_name(raw, ida_name.MNG_SHORT_FORM) or raw


def row(ea: int, label: str) -> dict[str, object]:
    func = ida_funcs.get_func(ea)
    pseudocode, error = decompile(ea)
    return {
        "label": label,
        "address": hex(ea),
        "raw_name": ida_name.get_name(ea),
        "demangled_name": function_name(ea),
        "function_start": hex(func.start_ea) if func else None,
        "function_end": hex(func.end_ea) if func else None,
        "pseudocode": pseudocode,
        "decompile_error": error,
        "xrefs_to": [
            {
                "from": hex(x.frm),
                "type": int(x.type),
                "caller": function_name(ida_funcs.get_func(x.frm).start_ea)
                if ida_funcs.get_func(x.frm)
                else "",
            }
            for x in idautils.XrefsTo(ea, 0)
        ],
    }


def main() -> None:
    ida_auto.auto_wait()
    if len(sys.argv) < 2:
        raise SystemExit("output JSON path required")
    output = sys.argv[1]
    rows = [row(ea, label) for ea, label in TARGETS.items()]
    caller_starts: set[int] = set()
    for target in (0x43626F0, 0x4362704):
        for xref in idautils.XrefsTo(target, 0):
            func = ida_funcs.get_func(xref.frm)
            if func:
                caller_starts.add(func.start_ea)
    callers = [row(ea, "draw_primitive_list_consumer") for ea in sorted(caller_starts)]
    result = {
        "schema": "magireco-ida-z2d-renderer-order-extract-v1",
        "status": "PASS" if all(not item["decompile_error"] for item in rows) else "PARTIAL",
        "input_path": ida_nalt.get_input_file_path(),
        "imagebase": hex(idaapi.get_imagebase()),
        "targets": rows,
        "draw_primitive_list_consumers": callers,
    }
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(
        "IDA_Z2D_RENDERER_ORDER=%s targets=%d consumers=%d"
        % (result["status"], len(rows), len(callers))
    )
    idaapi.qexit(0)


if __name__ == "__main__":
    main()
