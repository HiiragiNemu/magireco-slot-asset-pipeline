# universal_probe.py
import os
import datetime
from mitmproxy import http, ctx

# 自动在脚本同级目录下创建一个文件夹存放抓包记录
OUTPUT_DIR = "magireco_slot_traffic"

class TrafficDumper:
    def __init__(self):
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)
        ctx.log.info(f"==================================================")
        ctx.log.info(f"[*] 探针已启动！")
        ctx.log.info(f"[*] 所有截获的流量将保存至: {os.path.abspath(OUTPUT_DIR)}")
        ctx.log.info(f"==================================================")

    def response(self, flow: http.HTTPFlow):
        req = flow.request
        res = flow.response

        # 过滤掉模拟器后台的杂音，只抓未知的业务包
        ignore_domains = ["google", "android.clients", "gstatic", "play.googleapis", "gvt1.com"]
        if any(d in req.host for d in ignore_domains):
            return

        # 提取路径最后一段，构造文件名
        api_name = req.path.split('?')[0].split('/')[-1]
        if not api_name:
            api_name = "root"
            
        safe_host = req.host.replace(".", "_")
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
        filename = f"{timestamp}_{safe_host}_{api_name}.txt"
        filepath = os.path.join(OUTPUT_DIR, filename)

        try:
            with open(filepath, "w", encoding="utf-8", errors="replace") as f:
                f.write(f"========== REQUEST ==========\n")
                f.write(f"URL: {req.url}\n")
                f.write(f"Method: {req.method}\n")
                for k, v in req.headers.items():
                    f.write(f"{k}: {v}\n")
                
                f.write("\n--- Request Body ---\n")
                if req.content:
                    f.write(f"[Raw Hex (前1000字节)]: {req.content[:1000].hex()}\n")
                    f.write(f"[Text 尝试解码]: {req.content[:2000].decode('utf-8', errors='replace')}\n")
                else:
                    f.write("[Empty]\n")

                f.write(f"\n========== RESPONSE ==========\n")
                f.write(f"Status: {res.status_code}\n")
                for k, v in res.headers.items():
                    f.write(f"{k}: {v}\n")

                f.write("\n--- Response Body ---\n")
                if res.content:
                    f.write(f"[Raw Hex (前1000字节)]: {res.content[:1000].hex()}\n")
                    f.write(f"[Text 尝试解码]: {res.content[:5000].decode('utf-8', errors='replace')}\n")
                else:
                    f.write("[Empty]\n")

            # 这行代码会在你的 PowerShell 界面打印蓝色的高亮提示！
            ctx.log.info(f"[+] 捕获: {req.host} -> {api_name} | 已保存至 {filename}")
        except Exception as e:
            ctx.log.error(f"[-] 保存文件失败: {e}")

addons = [TrafficDumper()]