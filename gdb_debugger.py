# gdb_debugger.py
import struct
import re

GDB_BIN = "unpacked_assets/assets/gdb.bin"

with open(GDB_BIN, "rb") as f:
    d = f.read()

# 寻找视频原厂名 (带有 \x00 结束符)
idx = d.find(b"ac0101_001\x00")
if idx != -1:
    print("=== ac0101_001 记录分析 ===")
    # 截取名字开始往后 40 字节
    chunk = d[idx : idx + 40]
    print("  1. 完整 Hex 字节流:", chunk.hex())
    
    # 寻找 GDB 标志
    gdb_pos = chunk.find(b"GDB")
    print("  2. GDB 标志在截取片段中的绝对偏移:", gdb_pos)
    
    if gdb_pos != -1:
        # 取出 GDB 前面的 12 字节属性区
        fields = chunk[gdb_pos - 12 : gdb_pos]
        print("  3. 属性区 Hex:", fields.hex())
        try:
            print("  4. 尝试解析 file_val (前4字节):", struct.unpack("<I", fields[0:4])[0])
            print("  5. 尝试解析 video_idx (中4字节):", struct.unpack("<I", fields[4:8])[0])
        except Exception as e:
            print("  [!] 解析属性失败:", e)
else:
    print("[!] 未能在 GDB 中找到 ac0101_001 视频标记")