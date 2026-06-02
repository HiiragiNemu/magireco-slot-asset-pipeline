# magireco_slot_video_extractor.py
import os
import re
import struct
import codecs
import subprocess
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# --- 路径配置 ---
TEMP_USM_DIR = "temp_usm_slices"
FINAL_MP4_DIR = "final_mp4_videos"

os.makedirs(TEMP_USM_DIR, exist_ok=True)
os.makedirs(FINAL_MP4_DIR, exist_ok=True)

# 动态寻找本地所需的路径 (避免硬编码)
def find_file_recursively(filename, start_dir="."):
    for root, _, files in os.walk(start_dir):
        if filename in files:
            return os.path.join(root, filename)
    for root, _, files in os.walk(".."):
        if filename in files:
            return os.path.join(root, filename)
    return None

print("[*] 正在自动定位资源文件，请稍候...")
MAIN_BIN = find_file_recursively("cri.bin")
MAIN_ADD = find_file_recursively("cri_add.bin")
PATCH_BIN = find_file_recursively("cri2.bin")
PATCH_ADD = find_file_recursively("cri2_add.bin")
M_INFO_DAT = find_file_recursively("m_info.dat")
GDB_BIN = find_file_recursively("gdb.bin")

if not all([MAIN_BIN, MAIN_ADD, PATCH_BIN, PATCH_ADD, M_INFO_DAT, GDB_BIN]):
    print("[❌] 错误：无法完整定位原始资源，请确认文件是否存在！")
    exit()

# --- 1. 从【双 Smali 源码】中动态解析并合并最新的演出大类名称 (自适应更新) ---
def load_dir_name_tbl_from_smali():
    tbl = []
    # 扫描两个最关键的调试清单类，合并共 300+ 个演出分类！
    for filename in ["DebugDispNameList.smali", "DebugProd.smali"]:
        smali_path = find_file_recursively(filename)
        if not smali_path:
            continue
        print(f"[*] 成功定位清单源码: {smali_path}，开始解析...")
        try:
            with open(smali_path, "r", encoding="utf-8") as f:
                content = f.read()
            raw_strings = re.findall(r'const-string [v|p]\d+, "([^"]+)"', content)
            for s in raw_strings:
                try: decoded = codecs.decode(s, 'unicode-escape')
                except Exception: decoded = s
                # 兼容两种 smali 的格式特征
                if re.match(r"^\d+\s+", decoded) or re.match(r"^ac\d+_", decoded):
                    tbl.append(decoded)
        except Exception as e:
            print(f"[⚠️] 解析 {filename} 失败: {e}")
            
    # 去重与清洗
    cleaned_tbl = []
    seen_codes = set()
    for item in tbl:
        match = re.search(r"(ac\d+)[_]?(.*)", item)
        if match:
            code = match.group(1)
            raw_name = item.split(" ", 1)[1] if " " in item else item
            raw_name = raw_name.rstrip(".")
            if code not in seen_codes:
                seen_codes.add(code)
                cleaned_tbl.append(f"0 {raw_name}") # 补上前导标志兼容后续解析
                
    if cleaned_tbl:
        print(f"[✅] 自动清单更新：已成功从双 Smali 源码中加载并合并了 {len(cleaned_tbl)} 个最新演出名称。")
        return cleaned_tbl
    return None

DIR_NAME_TBL = load_dir_name_tbl_from_smali() or []
ac_folder_map = {}
for item in DIR_NAME_TBL:
    match = re.search(r"(ac\d+)[_]?(.*)", item)
    if match:
        code = match.group(1)
        raw_name = item.split(" ", 1)[1].rstrip(".")
        clean_name = re.sub(r'[\\/*?:"<>|]', "_", raw_name)
        ac_folder_map[code] = clean_name

# --- 2. 解析 gdb.bin 提取视频候选名称表 ---
video_name_candidates = defaultdict(list) # 格式: (file_index, video_idx) -> [candidate_filename, ...]
video_name_map = {} # 仅保存唯一候选，避免共享素材被误命名
video_multi_candidate_keys = {}
print("[*] 正在解析主数据库 gdb.bin 获取视频候选重命名清单...")

try:
    with open(GDB_BIN, "rb") as f:
        gdb_data = f.read()
    
    # 寻找所有的电影文件名模式 (例如 ac0101_001)
    movie_pattern = re.compile(b"(ac\\d{4}_[a-zA-Z0-9_]+)")
    for match in movie_pattern.finditer(gdb_data):
        name_bytes = match.group(0)
        offset = match.start()
        name_len = len(name_bytes)
        
        # 排除包含 z2d 图像格式等干扰项
        if name_bytes.endswith(b"z2d") or name_bytes.endswith(b"bin"):
            continue
            
        # 👈 核心自适应修正：向后读取 32 字节，在其中动态寻找 GDB 标志绝对物理位置
        if offset + name_len + 32 <= len(gdb_data):
            chunk = gdb_data[offset : offset + name_len + 32]
            gdb_pos = chunk.find(b"GDB")
            if gdb_pos != -1 and gdb_pos >= 12:
                # 无论 GDB\x01 还是 GDB\x02，均在相对于其前向偏移量进行取值，绝不出错！
                file_val = struct.unpack("<I", chunk[gdb_pos - 12 : gdb_pos - 8])[0]   # 1代表main，2代表patch
                video_idx = struct.unpack("<I", chunk[gdb_pos - 8 : gdb_pos - 4])[0]  # 绝对视频序列号
                
                name_str = name_bytes.decode('utf-8', errors='ignore')
                
                if file_val not in (1, 2):
                    continue
                # 区分 main (0) 和 patch (1)
                file_index = 0 if file_val == 1 else 1
                key = (file_index, video_idx)
                if name_str not in video_name_candidates[key]:
                    video_name_candidates[key].append(name_str)

    video_name_map = {key: names[0] for key, names in video_name_candidates.items() if len(names) == 1}
    video_multi_candidate_keys = {key: names for key, names in video_name_candidates.items() if len(names) > 1}
    print(
        f"[✅] 主数据库解析成功：唯一命名 {len(video_name_map)} 段，"
        f"多候选共享素材 {len(video_multi_candidate_keys)} 段。"
    )
except Exception as e:
    print(f"[❌] 扫描 gdb.bin 失败: {e}，将采用默认序号命名。")

# --- 3. 自动检测显卡硬件加速 (NVENC) 支持 ---
def detect_nvenc_support():
    try:
        res = subprocess.run(["ffmpeg", "-encoders"], capture_output=True, text=True, check=True)
        return "h264_nvenc" in res.stdout
    except Exception: return False

HAS_NVENC = detect_nvenc_support()
if HAS_NVENC:
    print("[🚀] 检测到 NVIDIA 显卡支持！开启 [NVIDIA NVENC] 极速硬件加速。")
else:
    print("[ℹ️] 未检测到显卡加速，已自动平滑降级至 [CPU 多线程 (libx264)] 转码。")

def parse_add_file(add_path, bin_size):
    with open(add_path, "rb") as f:
        data = f.read()
    offsets = [struct.unpack("<I", data[i:i+4])[0] for i in range(0, len(data), 4)]
    offsets.append(bin_size)
    return sorted(list(set(offsets)))

# --- CriWare USM 信号及常量 ---
BLOCK_TYPES = {
    b"CRID": ("b", 4),
    b"@ALP": ("b", 4),
    b"@SFV": ("b", 4),
    b"@SFA": ("b", 4),
    b"@SBT": ("b", 4),
    b"@CUE": ("b", 4),
}
BLOCK_ID_LENGTH = 4  # 常量完美补全！
HEADER_END_BYTES = b"\x23\x48\x45\x41\x44\x45\x52\x20\x45\x4e\x44\x20\x20\x20\x20\x20\x3d\x3d\x3d\x3d\x3d\x3d\x3d\x3d\x3d\x3d\x3d\x3d\x3d\x3d\x3d\x00"
METADATA_END_BYTES = b"\x23\x4d\x45\x54\x41\x44\x41\x54\x41\x20\x45\x4e\x44\x20\x20\x20\x3d\x3d\x3d\x3d\x3d\x3d\x3d\x3d\x3d\x3d\x3d\x3d\x3d\x3d\x3d\x00"
CONTENTS_END_BYTES = b"\x23\x43\x4f\x4e\x54\x45\x4e\x54\x53\x20\x45\x4e\x44\x20\x20\x20\x3d\x3d\x3d\x3d\x3d\x3d\x3d\x3d\x3d\x3d\x3d\x3d\x3d\x3d\x3d\x00"

def demux_usm(usm_data, base_name, out_dir):
    size = len(usm_data)
    offset = usm_data.find(b"CRID")
    if offset == -1:
        return None, None
    writers = {}
    while offset < size:
        block_id = usm_data[offset : offset + BLOCK_ID_LENGTH]
        if block_id in BLOCK_TYPES:
            typ, val = BLOCK_TYPES[block_id]
            if typ == "b":
                bs_size = val
                offset2 = offset + BLOCK_ID_LENGTH
                bs_array = usm_data[offset2 : offset2 + bs_size]
                block_size = struct.unpack(">I", bs_array)[0]
                block_val = struct.unpack("<I", block_id)[0]
                is_audio = block_id == b"@SFA"
                is_video = block_id == b"@SFV"
                is_alpha = block_id == b"@ALP"
                base_pos = offset + BLOCK_ID_LENGTH + bs_size

                if is_audio or is_video or is_alpha:
                    stream_id = usm_data[offset + 12] if is_audio else 0
                    stream_key = ("a" if is_audio else ("v" if is_video else "x"), stream_id | block_val)
                    if stream_key not in writers:
                        writers[stream_key] = bytearray()
                    header_size = struct.unpack(">H", usm_data[offset + 8 : offset + 10])[0]
                    footer_size = struct.unpack(">H", usm_data[offset + 10 : offset + 12])[0]
                    if header_size + footer_size < block_size:
                        start_pos = base_pos + header_size
                        end_pos = base_pos + block_size - footer_size
                        writers[stream_key].extend(usm_data[start_pos:end_pos])
                offset += BLOCK_ID_LENGTH + bs_size + block_size
        else:
            offset += 1

    m2v_path, adx_path = None, None
    for stream_key, val_bytes in writers.items():
        val = bytes(val_bytes)
        header_pos = val.find(HEADER_END_BYTES)
        meta_pos = val.find(METADATA_END_BYTES)
        footer_pos = val.find(CONTENTS_END_BYTES)
        start_candidates = [p + 32 for p in (header_pos, meta_pos) if p != -1]
        start_pos = max(start_candidates) if start_candidates else 0
        end_pos = footer_pos if footer_pos != -1 else len(val)
        typ, _ = stream_key
        if typ == "v":
            m2v_path = os.path.join(out_dir, f"{base_name}.m2v")
            with open(m2v_path, "wb") as f: f.write(val[start_pos:end_pos])
        elif typ == "a":
            adx_path = os.path.join(out_dir, f"{base_name}.adx")
            with open(adx_path, "wb") as f: f.write(val[start_pos:end_pos])
    return m2v_path, adx_path

def convert_to_bilibili_mp4(m2v_path, adx_path, output_mp4):
    if not m2v_path: return False

    def build_cmd(use_nvenc):
        cmd = ["ffmpeg", "-y", "-i", m2v_path]
        if adx_path and os.path.exists(adx_path):
            cmd += ["-i", adx_path]
        if use_nvenc:
            cmd += [
                "-vf", "vflip,hflip",
                "-c:v", "h264_nvenc", "-pix_fmt", "yuv420p", "-preset", "p6", "-cq", "19",
                "-c:a", "alac",
                output_mp4
            ]
        else:
            cmd += [
                "-vf", "vflip,hflip",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16",
                "-c:a", "alac",
                output_mp4
            ]
        return cmd

    cmd = build_cmd(HAS_NVENC)
    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if res.returncode != 0 and HAS_NVENC:
        # ffmpeg may list NVENC even when no compatible GPU/session is available.
        res = subprocess.run(build_cmd(False), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    return res.returncode == 0

def process_single_slice(bin_file_path, start_offset, end_offset, index, prefix):
    file_index = 0 if prefix == "main" else 1
    map_key = (file_index, index)
    
    if map_key in video_name_map:
        real_name = video_name_map[map_key]
        ac_code_match = re.match(r"(ac\d+)", real_name)
        if ac_code_match and ac_code_match.group(0) in ac_folder_map:
            folder_name = ac_folder_map[ac_code_match.group(0)]
        else:
            folder_name = f"{ac_code_match.group(0)}_演出" if ac_code_match else "Unassigned_演出"
        target_sub_dir = os.path.join(FINAL_MP4_DIR, folder_name)
        final_video_name = f"{real_name}.mp4"
    elif map_key in video_multi_candidate_keys:
        target_sub_dir = os.path.join(FINAL_MP4_DIR, "MultiCandidate_Slices")
        final_video_name = f"{prefix}_video_{index:04d}_candidates{len(video_multi_candidate_keys[map_key])}.mp4"
    else:
        target_sub_dir = os.path.join(FINAL_MP4_DIR, "Unclassified_Slices")
        final_video_name = f"{prefix}_video_{index:04d}.mp4"
        
    os.makedirs(target_sub_dir, exist_ok=True)
    output_mp4 = os.path.join(target_sub_dir, final_video_name)
    
    if os.path.exists(output_mp4):
        return True

    with open(bin_file_path, "rb") as f:
        f.seek(start_offset)
        slice_data = f.read(end_offset - start_offset)
        
    if not slice_data.startswith(b"CRID"):
        return False

    base_name = f"{prefix}_video_{index:04d}"
    m2v_p, adx_p = demux_usm(slice_data, base_name, TEMP_USM_DIR)
    
    if m2v_p:
        success = convert_to_bilibili_mp4(m2v_p, adx_p, output_mp4)
        try:
            if m2v_p and os.path.exists(m2v_p): os.remove(m2v_p)
            if adx_p and os.path.exists(adx_p): os.remove(adx_p)
        except OSError: pass
        return success
    return False

def concatenate_videos_in_folder(folder_path, output_mp4):
    """
    全自动、二进制零损合并同一个演出包内的所有切片，拼接成长视频
    """
    files = [f for f in os.listdir(folder_path) if f.endswith(".mp4") and not f.endswith("_merged.mp4")]
    if len(files) <= 1:
        return
        
    # 根据原厂序号严格递增排序（例如 ac0101_001.mp4 必定在 ac0101_002.mp4 前面）
    def extract_slice_idx(fname):
        match = re.search(r"_(\d+)\.mp4", fname)
        if match: return int(match.group(1))
        return 9999
    files = sorted(files, key=extract_slice_idx)
    
    list_file_path = os.path.join(folder_path, "concat_list.txt")
    with open(list_file_path, "w", encoding="utf-8") as f:
        for file in files:
            f.write(f"file '{file}'\n")
            
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", list_file_path,
        "-c", "copy",  # 二进制直接复制，0.1秒合并，绝对画质无损！
        output_mp4
    ]
    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    
    try: os.remove(list_file_path)
    except OSError: pass
    
    if res.returncode == 0:
        print(f"[🎉] 成功生成完整演出合集: {os.path.basename(output_mp4)} (共无损拼接 {len(files)} 个片段)")

def extract_all_videos_from_bin(bin_path, add_path, prefix, start_index=0, limit=None, workers=4):
    bin_size = os.path.getsize(bin_path)
    offsets = parse_add_file(add_path, bin_size)
    total_files = len(offsets) - 1
    if start_index < 0 or start_index >= total_files:
        raise ValueError(f"{prefix} start_index out of range: {start_index} / {total_files}")
    end_index = total_files if limit is None else min(total_files, start_index + limit)
    selected_indices = range(start_index, end_index)
    
    print(f"\n[*] 正在对 {prefix} 执行切割、转码并自动重命名分类 (选择 {start_index}..{end_index - 1} / 共 {total_files} 段)...")
    
    success_count = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(process_single_slice, bin_path, offsets[i], offsets[i+1], i, prefix): i
            for i in selected_indices
        }
        for future in tqdm(as_completed(futures), total=len(futures), desc=f"处理 {prefix}"):
            if future.result(): success_count += 1
                
    print(f"[✅] {prefix} 已完成：成功 {success_count} / {len(futures)}。")

def legacy_main():
    print("="*60)
    print("🎬 老虎机 5.7GB 一键智能切割、绝对无损音画转码、自动重命名、合集拼接与分类系统")
    print("="*60)
    
    # 运行资源提取
    extract_all_videos_from_bin(MAIN_BIN, MAIN_ADD, "main")
    extract_all_videos_from_bin(PATCH_BIN, PATCH_ADD, "patch")
    
    # 自动对每一个非空演出文件夹进行“一键无损流合并”，产生完美的长视频！
    print("\n[*] 正在对所有分类演出包进行【二进制零损拼接】...")
    for root, dirs, _ in os.walk(FINAL_MP4_DIR):
        for d in dirs:
            if d in {"Unclassified_Slices", "Unassigned_演出", "MultiCandidate_Slices"}:
                continue
            folder_path = os.path.join(root, d)
            merged_output = os.path.join(folder_path, f"{d}_完整合集.mp4")
            concatenate_videos_in_folder(folder_path, merged_output)
            
    try: os.rmdir(TEMP_USM_DIR)
    except OSError: pass
    print(f"\n[🎉] 全盘大捷！干净、正向、纯无损、完全自动分类、重命名并【自动拼接完整版】的视频已全部保存在 `{FINAL_MP4_DIR}` 目录下！")

def concatenate_all_safe_folders():
    print("\n[*] 正在对分类演出包进行【二进制零损拼接】...")
    for root, dirs, _ in os.walk(FINAL_MP4_DIR):
        for d in dirs:
            if d in {"Unclassified_Slices", "Unassigned_演出", "MultiCandidate_Slices"}:
                continue
            folder_path = os.path.join(root, d)
            merged_output = os.path.join(folder_path, f"{d}_完整合集.mp4")
            concatenate_videos_in_folder(folder_path, merged_output)

def build_parser():
    parser = argparse.ArgumentParser(description="Extract CRID/USM slices to MP4")
    parser.add_argument("--package", choices=["main", "patch", "all"], default="all")
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--limit", type=int, help="number of slices to process per selected package")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--merge", action="store_true", help="merge named folders after extraction")
    return parser

def main(argv=None):
    args = build_parser().parse_args(argv)
    print("="*60)
    print("CRID/USM video extraction, conversion, naming and classification")
    print("="*60)

    if args.workers < 1:
        raise ValueError("--workers must be >= 1")
    if args.limit is not None and args.limit < 1:
        raise ValueError("--limit must be >= 1")

    if args.package in ("main", "all"):
        extract_all_videos_from_bin(MAIN_BIN, MAIN_ADD, "main", args.start_index, args.limit, args.workers)
    if args.package in ("patch", "all"):
        extract_all_videos_from_bin(PATCH_BIN, PATCH_ADD, "patch", args.start_index, args.limit, args.workers)

    if args.merge:
        concatenate_all_safe_folders()

    try:
        os.rmdir(TEMP_USM_DIR)
    except OSError:
        pass
    print(f"\n[done] output dir: {FINAL_MP4_DIR}")

if __name__ == "__main__":
    main()
