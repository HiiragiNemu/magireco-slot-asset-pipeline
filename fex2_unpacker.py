# find_dat.py
import os

target_files = ['m_info.dat', 'sound_id.dat']
found = []

# 全盘递归搜索 D:/magia/MyProducts 目录
for root, dirs, files in os.walk('D:/magia/MyProducts'):
    for f in files:
        if f in target_files:
            path = os.path.join(root, f)
            found.append((f, path))

if not found:
    print("[!] 未找到任何匹配的文件，请确认搜寻的根目录是否正确。")

for f, path in found:
    try:
        with open(path, 'rb') as file_obj:
            data = file_obj.read()
        print(f"=== {f} ===")
        print(f"Path: {path}")
        print(f"Size: {len(data)} bytes")
        print("ASCII (first 500 bytes):")
        print(repr(data[:500]))
        print("-" * 50)
    except Exception as e:
        print(f"[!] 读取 {f} 失败: {e}")