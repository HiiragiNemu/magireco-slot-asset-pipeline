# magireco_slot_video_sorter.py
import os
import re
import struct
import shutil

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, **_kwargs):
        return iterable

# --- 配置区 ---
FINAL_MP4_DIR = "final_mp4_videos"
MAIN_ADD = "downloaded_assets/Unpacked_main/cri_add.bin"
PATCH_ADD = "downloaded_assets/Unpacked_patch/cri2_add.bin"
M_INFO_DAT = "unpacked_assets/assets/m_info.dat"

# --- 演出名称清单 (来自 DebugDispNameList) ---
DIR_NAME_TBL = [
    "0 なし.", "1 SE_その他.", "2 ac0101_冥界の焔（ほのお）.", "3 ac0102_毒の氷塊.", 
    "4 ac0103_闇の侵食.", "5 ac0104_トール(Tor)ハンマー(Hammer).", "6 ac0105_命の水流.", 
    "7 ac0106_ギャラル(Giallar)ホルン(Horn).", "8 ac0109_ノーマルステチェン.", 
    "9 ac0110_ビフレスト(Bifrost)ステチェン.", "10 ac0111_神話予兆.", "11 ac0112_フェンリル(Fenrir)幻影.", 
    "12 ac0115_グングニル(Gungnir)成否.", "13 ac0116_ギンヌンガップ(Ginnungagap)成否.", 
    "14 ac0160_フィンブル(Fimbul)ステチェン.", "15 ac0113_スレイプニル(Sleipnir)連続.", 
    "16 ac5003_ボーナス煽り.", "17 ac0107_ボタン予告.", "18 ac0108_色予告.", 
    "19 ac3305_ボタン予告.", "20 ac3303_雷雲バトル予兆.", "21 ac0025_スフィア獲得.", 
    "22 ac3501_ART冥界の焔（ほのお）.", "23 ac3502_ART毒の氷塊.", "24 ac3503_ART闇の侵食.", 
    "25 ac3506_ARTギャラル(Giallar)ホルン(Horn).", "26 ac3508_ART色予告.", 
    "27 ac3514_ARTグングニル(Gungnir)成否.", "28 ac3515_ARTギンヌンガップ(Ginnungagap)成否.", 
    "29 ac3516_ルーン文字演出.", "30 ac0019_メイン画面ナビ.", "31 ac0020_メイン画面ハテナナビ.", 
    "32 ac3306_報酬GET演出.", "33 ac3401_バトルVSナグルファル.", "34 ac3402_バトルVSスルト.", 
    "35 ac3403_バトルVSヨルムンガンド.", "36 ac3103_7RUSHステージ用ベース.", 
    "37 ac3113_神話7RUSHステージ用ベース.", "38 ac0017_下部映像枠予告.", 
    "39 ac0018_下部モニタ押し順ナビ.", "40 ac0154_神話モード_背景移行.", "41 ac0153_01_神話内容.", 
    "42 ac0153_02_神話内容.", "43 ac0153_03_神話内容.", "44 ac0153_04_神話内容.", 
    "45 ac0153_05_神話内容.", "46 ac0153_06_神話内容.", "47 ac0153_07_神話内容.", 
    "48 ac0153_08_神話内容.", "49 ac0153_09_神話内容.", "50 ac0153_10_神話内容.", 
    "51 ac0153_11_神話内容.", "52 ac0153_12_神話内容.", "53 ac0153_13_神話内容.", 
    "54 ac0153_14_神話内容.", "55 ac0153_15_神話内容.", "56 ac0153_16_神話内容.", 
    "57 ac0153_17_神話内容.", "58 ac0153_18_神話分岐.", "59 ac3301_ART突入.", 
    "60 ac3101_7RUSH突入.", "61 ac3101_神話RUSH突入.", "62 ac0151_神話モード突入.", 
    "63 ac0030_グングニル図柄入賞.", "64 ac0031_全回転フリーズ.", 
    "65 ac3517_ARTグングニル図柄出现.", "66 ac0021_枚数OVER表示.", 
    "67 ac4002_ヴァルハラゾーン専用カウント."
]

def parse_add_file(add_path):
    """解析 add.bin 得到绝对偏移量列表"""
    with open(add_path, "rb") as f:
        data = f.read()
    return [struct.unpack("<I", data[i:i+4])[0] for i in range(0, len(data), 4)]

def main():
    print("="*60)
    print("🚀 视频资源全自动 100% 精确无损分类整理工具")
    print("="*60)

    if not os.path.exists(M_INFO_DAT):
        print(f"[!] 错误：未在 {M_INFO_DAT} 找到清单，请确认路径！")
        return

    # 1. 加载主包和补丁包的偏移量
    main_offsets = parse_add_file(MAIN_ADD)
    patch_offsets = parse_add_file(PATCH_ADD)

    # 2. 读取并解析 m_info.dat 映射清单
    with open(M_INFO_DAT, "rb") as f:
        header = f.read(9)
        mag, record_count, size = struct.unpack('<BII', header)
        
        mapping_list = []
        for i in range(record_count):
            r = f.read(12)
            if len(r) < 12:
                break
            file_index = struct.unpack("<I", r[0:4])[0] # 0为主包，1为补丁包
            offset = struct.unpack("<I", r[4:8])[0]     # 视频在包内的偏移量
            group_index = struct.unpack("<H", r[10:12])[0] # 对应 DIR_NAME_TBL 索引
            
            mapping_list.append((file_index, offset, group_index))

    # 3. 开始执行 1-to-1 数学对齐比对
    proposal_moves = []
    
    for file_index, offset, group_index in mapping_list:
        # 确定对应的原始视频文件名和后缀
        prefix = "main" if file_index == 0 else "patch"
        offsets_list = main_offsets if file_index == 0 else patch_offsets
        
        # 通过偏移量比对，精确找出它对应的是第几个视频
        if offset in offsets_list:
            video_idx = offsets_list.index(offset)
            src_filename = f"{prefix}_video_{video_idx:04d}.mp4"
            src_filepath = os.path.join(FINAL_MP4_DIR, "Unclassified_Slices", src_filename)
            
            # 如果本地确实有这个压制好的视频，我们准备移动它
            if os.path.exists(src_filepath):
                # 寻找对应的文件夹名称
                if group_index < len(DIR_NAME_TBL):
                    # 清洗文件名，去掉序号并格式化
                    raw_folder_name = DIR_NAME_TBL[group_index].split(" ", 1)[1].rstrip(".")
                    folder_name = re.sub(r'[\\/*?:"<>|]', "_", raw_folder_name)
                else:
                    folder_name = f"Unresolved_Group_{group_index}"
                
                dest_dir = os.path.join(FINAL_MP4_DIR, folder_name)
                proposal_moves.append((src_filepath, dest_dir, src_filename))

    if not proposal_moves:
        print("[!] 未在 Unclassified_Slices 中检测到待整理的视频，请确认视频是否已生成在对应文件夹。")
        return

    # 4. 模拟运行 (Dry Run) 打印前 20 条，供你肉眼安全确认！
    print(f"\n[+] 清单分析完毕，共匹配到 {len(proposal_moves)} 个视频的分类映射。")
    print("="*60)
    print("💡 【安全模拟测试 (Dry Run)】前 20 条移动规则：")
    for i, (src, dest, fname) in enumerate(proposal_moves[:20]):
        print(f"  [{i+1:02d}] 视频 {fname:30} ──> {os.path.basename(dest)}")
    print("="*60)
    
    # 5. 提示用户交互确认
    confirm = input("\n⚠️ 请双击检查已生成的视频，确认其名称与画面是否 100% 对应？(Y/N): ").strip().upper()
    if confirm == "Y":
        print("\n[*] 确认无误，开始极速物理归类整理...")
        for src, dest, fname in tqdm(proposal_moves, desc="归类进度"):
            os.makedirs(dest, exist_ok=True)
            shutil.move(src, os.path.join(dest, fname))
        print("\n[🎉] 恭喜！所有视频已 100% 绝对精确、无损地分类归档完成！")
    else:
        print("\n[!] 操作已取消。没有对任何文件进行修改。")

if __name__ == "__main__":
    main()
