# test_usm_headers.py
import os
import struct
import re

MAIN_BIN = "downloaded_assets/Unpacked_main/cri.bin"
MAIN_ADD = "downloaded_assets/Unpacked_main/cri_add.bin"

def parse_add_file(add_path, bin_size):
    with open(add_path, "rb") as f:
        data = f.read()
    offsets = [struct.unpack("<I", data[i:i+4])[0] for i in range(0, len(data), 4)]
    offsets.append(bin_size)
    return sorted(list(set(offsets)))

def main():
    if not os.path.exists(MAIN_BIN) or not os.path.exists(MAIN_ADD):
        print("[!] 缺失源文件，请确认位置！")
        return

    bin_size = os.path.getsize(MAIN_BIN)
    offsets = parse_add_file(MAIN_ADD, bin_size)
    
    print("[*] 正在扫描前 50 个视频切片的内部元数据...")
    with open(MAIN_BIN, "rb") as f:
        for i in range(min(50, len(offsets) - 1)):
            start = offsets[i]
            size = offsets[i+1] - start
            
            f.seek(start)
            # 只读前 2048 字节，避免占用高吞吐
            header_data = f.read(min(2048, size))
            
            # 1. 尝试用正则找出所有包含 acXXXX 或者带有 .usm/.m2v 的 ASCII 字符串
            # 过滤掉非打印字符，提取 4 到 50 长度的字母数字下划线组合
            found_strings = re.findall(b"[a-zA-Z0-9_]{4,50}", header_data)
            
            # 过滤出包含 ac 编号或者显式视频命名的词
            keywords = []
            for b_str in found_strings:
                s = b_str.decode('utf-8', errors='ignore')
                if 'ac' in s or 'video' in s or 'movie' in s or 'm2v' in s:
                    keywords.append(s)
            
            # 去重
            keywords = sorted(list(set(keywords)))
            
            print(f"Slice {i:03d} (Offset: {start}) -> 匹配到的原厂标记: {keywords}")

if __name__ == "__main__":
    main()