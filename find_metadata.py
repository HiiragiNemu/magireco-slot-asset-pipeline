# find_metadata.py
import os
import sys

# 动态获取当前脚本所在的绝对路径，不进行任何硬编码
script_dir = os.path.dirname(os.path.abspath(sys.argv[0])) if sys.argv else os.getcwd()
print(f"[*] 正在递归扫描当前目录及其子目录: {script_dir}")

target_files = ['m_info.dat', 'sound_id.dat']
found = []

# 递归寻找当前目录下的目标文件
for root, dirs, files in os.walk(script_dir):
    for f in files:
        if f in target_files:
            path = os.path.join(root, f)
            found.append((f, path))

if not found:
    print("[!] 错误：未在当前目录下寻找到 m_info.dat 或 sound_id.dat！")
    print(f"    当前搜寻目录为: {script_dir}")
    print("    请确保此脚本与你的 'unpacked_base' 或 'assets' 文件夹在同一驱动器或父目录下。")

for f, path in found:
    try:
        with open(path, 'rb') as file_obj:
            data = file_obj.read()
        print(f"\n=== 成功找到: {f} ===")
        print(f"路径: {path}")
        print(f"大小: {len(data)} 字节")
        print("头部 1000 字节二进制数据 (Repr):")
        print(repr(data[:1000]))
        print("-" * 50)
    except Exception as e:
        print(f"[!] 读取 {f} 失败: {e}")