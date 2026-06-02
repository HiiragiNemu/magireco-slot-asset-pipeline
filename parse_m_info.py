# parse_m_info.py
import os
import struct

# 自动在当前目录及子目录下搜寻 m_info.dat
m_info_path = None
for root, dirs, files in os.walk('.'):
    if 'm_info.dat' in files:
        m_info_path = os.path.join(root, 'm_info.dat')
        break

if not m_info_path:
    print("[!] 错误：未能在当前目录及子目录下找到 m_info.dat！")
    exit()

print(f"[*] 正在读取并解析: {m_info_path}")
with open(m_info_path, 'rb') as f:
    header = f.read(9)
    mag, cnt, sz = struct.unpack('<BII', header)
    print(f"[+] 清单头解析成功：记录条数 = {cnt}, 数据区大小 = {sz} 字节")
    
    print("\n=== 前 40 条记录的二进制解析比对 ===")
    for i in range(min(40, cnt)):
        r = f.read(12)
        if len(r) < 12:
            break
        # 将 12 字节分别尝试解析为：
        # 1. 6 个 16位无符号整型 (H)
        u16 = [struct.unpack("<H", r[j:j+2])[0] for j in range(0, 12, 2)]
        # 2. 3 个 32位无符号整型 (I)
        u32 = [struct.unpack("<I", r[j:j+4])[0] for j in range(0, 12, 4)]
        
        print(f"Rec {i:03d} | 16位整型数组: {u16} | 32位整型数组: {u32}")