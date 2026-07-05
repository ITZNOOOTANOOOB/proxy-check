import requests
import logging
import random
import time
from datetime import datetime
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

MAX_VALID = 180          # 大幅降低
TIMEOUT = 5
COUNTRIES = ["US", "DE", "GB", "JP", "KR", "FR", "CA"]   # 减少国家数量

def send_notification(msg):
    # 你的 Telegram / Discord 代码保持不变...
    pass

def check_fast(proxy):
    try:
        proxies = {"http": f"http://{proxy}", "https": f"http://{proxy}"}
        start = time.time()
        r = requests.get("http://httpbin.org/ip", proxies=proxies, timeout=TIMEOUT)
        latency = round((time.time() - start) * 1000)
        return proxy if r.status_code == 200 else None
    except:
        return None

# ==================== 主程序 ====================
if __name__ == "__main__":
    start = datetime.now()
    logger.info("=== 高速模式启动 ===")

    # 1. 只用最快来源
    urls = [
        f"https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&protocol=http&country={','.join(COUNTRIES)}&format=text&limit=800",
        "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/http/data.txt",
        "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/socks5/data.txt",
    ]

    raw = []
    for url in urls:
        try:
            r = requests.get(url, timeout=12)
            if r.status_code == 200:
                lines = [line.strip() for line in r.text.splitlines() if ":" in line]
                raw.extend(lines)
        except:
            pass

    raw = list(dict.fromkeys(raw))
    if len(raw) > 600:
        raw = random.sample(raw, 600)

    logger.info(f"原始代理: {len(raw)} 个，开始验证...")

    # 2. 快速验证（多线程 + 严格限制）
    valid = []
    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=80) as executor:
        futures = [executor.submit(check_fast, p) for p in raw]
        for future in as_completed(futures):
            res = future.result()
            if res:
                valid.append(res)
                if len(valid) % 30 == 0:
                    logger.info(f"已找到有效代理: {len(valid)} 个")
                if len(valid) >= MAX_VALID:
                    break

    # 保存
    with open("http.txt", "w") as f:
        f.write("\n".join(valid))
    
    duration = (datetime.now() - start).seconds
    msg = f"🚀 高速更新完成\n耗时: {duration}秒\n有效: {len(valid)} 个"
    logger.info(msg)
    send_notification(msg)
