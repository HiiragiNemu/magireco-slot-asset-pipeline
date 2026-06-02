# search_ac_code.py
import os

target = b"ac0101"
found_files = []

# 只检索解包出的 assets 目录和核心代码目录
search_dirs = [
    "unpacked_base",
    "unpacked_assets"
]

print("[*] 开始执行全盘深度扫描，寻找映射密钥 'ac0101' 的踪迹...")
for s_dir in search_dirs:
    if not os.path.exists(s_dir):
        continue
    for root, dirs, files in os.walk(s_dir):
        for f in files:
            p = os.path.join(root, f)
            try:
                # 以二进制方式读取文件，检索是否存在 ac0101
                with open(p, "rb") as file_obj:
                    # 为防止大文件卡死，每次只读 10MB
                    chunk = file_obj.read(10 * 1024 * 1024)
                    if target in chunk:
                        found_files.append(p)
            except Exception:
                pass

if found_files:
    print(f"\n[✅] 成功！在以下本地解包文件中找到了 'ac0101' 的映射关系：")
    for p in found_files:
        print(f"  - {p} (大小: {os.path.getsize(p)} 字节)")
else:
    print("\n[!] 遗憾：全盘未发现任何包含 'ac0101' 的离线资产。")
    print("    这说明映射逻辑可能被硬编码进了 libARES.so / libGameProc.so 底层 C++ 库中。")