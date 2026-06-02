# magireco_slot_auto_downloader.py
import os
import subprocess
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# --- 配置区 ---
BASE_URL = "http://app.universal-777-res.com/magireco/{}.{}.com.universal777.magireco.obb_{:04d}.obb.jar"
OUTPUT_DIR = "downloaded_assets"
TEMP_DIR = "temp_chunks"
VERSION_CODE = 9  # 对应 APK 的 versionCode

# 独立的 jobb.jar 路径，脚本若在本地找不到会自动从 GitHub 下载
SDK_JOBB_PATH = "jobb.jar"
OBB_DECRYPT_KEY = "angiosperms"

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

session = requests.Session()

def check_and_download_jobb_jar():
    """
    检查本地是否存在 jobb.jar，若不存在，则全自动从 GitHub 下载，彻底摆脱环境依赖
    """
    if os.path.exists(SDK_JOBB_PATH):
        return True
    
    url = "https://github.com/monkey0506/jobbifier/releases/download/v2.0.1/jobb.jar"
    print(f"[*] 未在本地检测到 {SDK_JOBB_PATH}，正在自动从 GitHub 抓取组件...")
    try:
        res = session.get(url, timeout=30)
        res.raise_for_status()
        with open(SDK_JOBB_PATH, "wb") as f:
            f.write(res.content)
        print(f"[✅] {SDK_JOBB_PATH} 组件自动下载成功！")
        return True
    except Exception as e:
        print(f"[❌] 自动下载 jobb.jar 失败: {e}。请手动下载并放置在脚本同级目录下。")
        return False

def probe_total_chunks(prefix, version):
    print(f"[*] 正在探测 {prefix}.{version} 的总切片数...")
    total_chunks = 0
    step = 50
    current_probe = 1
    
    while True:
        urls = [BASE_URL.format(prefix, version, i) for i in range(current_probe, current_probe + step)]
        has_ended = False
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(session.head, url, timeout=10): i for i, url in enumerate(urls, start=current_probe)}
            for future in sorted(futures, key=lambda x: futures[x]):
                idx = futures[future]
                try:
                    res = future.result()
                    if res.status_code == 200:
                        total_chunks = idx
                    elif res.status_code == 404:
                        has_ended = True
                        break
                except Exception:
                    pass
        
        if has_ended:
            break
        current_probe += step

    print(f"[+] 探测完成：{prefix}.{version} 共有 {total_chunks} 个切片分包。")
    return total_chunks

def download_chunk(prefix, version, chunk_idx):
    url = BASE_URL.format(prefix, version, chunk_idx)
    chunk_file = os.path.join(TEMP_DIR, f"{prefix}_{version}_{chunk_idx:04d}.bin")
    
    if os.path.exists(chunk_file) and os.path.getsize(chunk_file) > 0:
        return chunk_idx, True

    try:
        res = session.get(url, timeout=15, stream=True)
        res.raise_for_status()
        with open(chunk_file, "wb") as f:
            for block in res.iter_content(chunk_size=1024*1024):
                f.write(block)
        return chunk_idx, True
    except Exception as e:
        print(f"\n[!] 下载分片 {prefix}_{chunk_idx} 失败: {e}")
        return chunk_idx, False

def process_obb(prefix, version):
    obb_filename = f"{prefix}.{version}.com.universal777.magireco.obb"
    final_obb_path = os.path.join(OUTPUT_DIR, obb_filename)
    
    if os.path.exists(final_obb_path) and os.path.getsize(final_obb_path) > 1024*1024:
        print(f"[目录检测] {obb_filename} 已经下载并合并完成，跳过。")
        return final_obb_path

    total_chunks = probe_total_chunks(prefix, version)
    if total_chunks == 0:
        print(f"[!] 未探测到 {prefix} 的切片信息，跳过下载。")
        return None

    print(f"[*] 开始多线程下载 {obb_filename}...")
    success_map = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(download_chunk, prefix, version, i) for i in range(1, total_chunks + 1)]
        for future in tqdm(as_completed(futures), total=len(futures), desc=f"下载 {prefix}"):
            idx, success = future.result()
            if success:
                success_map[idx] = True

    if len(success_map) != total_chunks:
        print(f"[❌] 错误：{obb_filename} 部分切片下载失败。请重新运行此脚本补漏！")
        return None

    print(f"[*] 正在将所有切片合并为: {obb_filename}...")
    with open(final_obb_path, "wb") as outfile:
        for idx in range(1, total_chunks + 1):
            chunk_file = os.path.join(TEMP_DIR, f"{prefix}_{version}_{idx:04d}.bin")
            with open(chunk_file, "rb") as infile:
                outfile.write(infile.read())
            try:
                os.remove(chunk_file)
            except OSError:
                pass

    print(f"[✅] {obb_filename} 合并成功！大小: {os.path.getsize(final_obb_path)/(1024*1024*1024):.2f} GB")
    return final_obb_path

def auto_decrypt_obb(obb_path, prefix):
    """
    全自动调用本地 java -jar jobb.jar 进行离线解密和提取！参数已修正为 -dump
    """
    if not obb_path or not os.path.exists(obb_path):
        return
        
    extract_target = os.path.join(OUTPUT_DIR, f"Unpacked_{prefix}")
    os.makedirs(extract_target, exist_ok=True)
    
    if not os.path.exists(SDK_JOBB_PATH):
        print(f"[!] 找不到 {SDK_JOBB_PATH}，无法进行自动解包。")
        return

    print(f"[*] 正在调用 java -jar {SDK_JOBB_PATH} 解包 {os.path.basename(obb_path)} 到 {extract_target}...")
    try:
        # 使用 -dump 参数解密并解包
        cmd = [
            "java", "-jar", SDK_JOBB_PATH,
            "-dump", obb_path,
            "-d", extract_target,
            "-k", OBB_DECRYPT_KEY
        ]
        subprocess.run(cmd, check=True)
        print(f"[✅] 自动解密提取成功！资源已全部解出至: {extract_target}")
    except Exception as e:
        print(f"[❌] 自动解密提取失败，错误信息: {e}")

def main():
    print("="*60)
    print("🚀 老虎机 apk 资源离线自动化同步工具")
    print("="*60)
    
    # 0. 安全保障：检查并自动获取 jobb.jar
    if not check_and_download_jobb_jar():
        return
    
    # 1. 自动化下载、合并、解密 main 包
    main_obb = process_obb("main", VERSION_CODE)
    auto_decrypt_obb(main_obb, "main")
    
    # 2. 自动化下载、合并、解密 patch 包
    patch_obb = process_obb("patch", VERSION_CODE)
    auto_decrypt_obb(patch_obb, "patch")

if __name__ == "__main__":
    main()