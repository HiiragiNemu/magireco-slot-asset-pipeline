# scan_gdb_movies.py
import os
import re

gdb_path = "unpacked_assets/assets/gdb.bin"
if not os.path.exists(gdb_path):
    print("[!] 错误：未找到 gdb.bin！")
    exit()

print(f"[*] 正在载入主数据库 {gdb_path}...")
with open(gdb_path, "rb") as f:
    data = f.read()

# 自动将二进制数据解码为 ASCII/UTF-8
decoded_data = data.decode("utf-8", errors="ignore")

# 匹配所有符合 acXXXX_ 命名的字符串 (例如 ac0101_001, ac3501_002)
raw_matches = re.findall(r"ac\d{4}_[a-zA-Z0-9_]+", decoded_data)

# 过滤掉 2D 贴图等干扰项 (带有 z2d 后缀)
movie_names = []
for m in raw_matches:
    if m.endswith("z2d") or m.endswith("png") or m.endswith("jpg") or m.endswith("bin"):
        continue
    movie_names.append(m)

# 保持顺序去重
unique_movie_names = []
seen = set()
for m in movie_names:
    if m not in seen:
        seen.add(m)
        unique_movie_names.append(m)

print(f"\n[✅] 扫描完毕！在 gdb.bin 中共提取到 {len(unique_movie_names)} 个独立的原厂视频名称。")
print("=== 前 100 个视频命名预览 ===")
for idx, name in enumerate(unique_movie_names[:100]):
    print(f"  [{idx:03d}] {name}")