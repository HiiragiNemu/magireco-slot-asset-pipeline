# inspect_gdb.py
import os
import re

gdb_path = "unpacked_assets/assets/gdb.bin"

if not os.path.exists(gdb_path):
    print(f"[!] 错误：在当前目录下未找到 gdb.bin！路径: {gdb_path}")
    exit()

print(f"[*] 正在载入主数据库 {gdb_path}...")
with open(gdb_path, "rb") as f:
    data = f.read()

# 寻找 ac0101 的所有出现位置（物理偏移量）
pattern = b"ac0101"
offsets = [m.start() for m in re.finditer(pattern, data)]

print(f"[+] 在 gdb.bin 中共找到了 {len(offsets)} 处关于 'ac0101' 的底层记录：\n")

# 打印每一处记录前后各 32 字节的明文和十六进制，用于肉眼分析对齐结构
for i, offset in enumerate(offsets):
    start = max(0, offset - 16)
    end = min(len(data), offset + 32)
    surrounding = data[start:end]
    
    print(f"第 {i+1:02d} 处记录 (绝对偏移量: {offset} / 16进制: 0x{offset:x})")
    print(f"  - Hex 字节流: {surrounding.hex()}")
    print(f"  - ASCII 明文: {repr(surrounding)}")
    print("-" * 60)