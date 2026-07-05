import asyncio
import aiohttp
import requests
import json
import logging
import argparse
import random
import time
from datetime import datetime
import os

# ==================== 配置区 ====================
TEST_URL = "http://httpbin.org/ip"
ANONYMITY_URL = "http://httpbin.org/headers"
TIMEOUT = 7
MAX_VALID_PER_TYPE = 250          # 控制数量，减少运行时间
CONCURRENT_LIMIT = 60

# 国家过滤（可自行增删）
COUNTRIES = ["US", "GB", "DE", "JP", "KR", "FR", "CA", "NL", "SG", "AU"]

# 匿名度
ANONYMITY = "elite"               # elite / anonymous / transparent / all

# 通知
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK", "")

# ==================== 日志 ====================
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

# ==================== 通知函数 ====================
def send_notification(message: str):
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"},
                timeout=10
            )
        except:
            pass
    if DISCORD_WEBHOOK:
        try:
            requests.post(DISCORD_WEBHOOK, json={"content": message}, timeout=10)
        except:
            pass

# ==================== 质量验证 ====================
def check_proxy_quality(proxy_str: str, proxy_type: str = "http"):
    start = time.time()
    try:
        proxies = {"http": f"{proxy_type}://{proxy_str}", "https": f"{proxy_type}://{proxy_str}"}
        r = requests.get(TEST_URL, proxies=proxies, timeout=TIMEOUT)
        latency = round((time.time() - start) * 1000)

        if r.status_code != 200:
            return None

        # 匿名度简单检测
        anonymity = "anonymous"
        try:
            h = requests.get(ANONYMITY_URL, proxies=proxies, timeout=TIMEOUT)
            if h.status_code == 200 and "Via" not in h.text and "Proxy" not in h.text:
                anonymity = "elite"
        except:
            pass

        return {
            "proxy": proxy_str,
            "latency": latency,
            "anonymity": anonymity
        }
    except:
        return None

# ==================== 多来源获取 ====================
def fetch_proxies(proxy_type: str):
    all_proxies = []
    country_str = ",".join(COUNTRIES) if COUNTRIES else "all"

    sources = [
        # ProxyScrape API
        f"https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&protocol={proxy_type}&country={country_str}&anonymity={ANONYMITY if proxy_type=='http' else 'all'}&format=text&limit=1500",
        # Proxifly
        f"https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/{proxy_type}/data.txt",
        # 其他优质来源
        "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/protocols/http.txt" if proxy_type == "http" else "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/protocols/socks5.txt",
    ]

    for url in sources:
        try:
            resp = requests.get(url, timeout=18)
            if resp.status_code == 200:
                lines = [line.strip() for line in resp.text.splitlines() if ":" in line]
                all_proxies.extend(lines)
                logger.info(f"从 {url[:60]}... 获取 {len(lines)} 个")
        except Exception as e:
            logger.warning(f"来源失败: {e}")

    # 去重 + 随机采样加速
    all_proxies = list(dict.fromkeys(all_proxies))
    if len(all_proxies) > 800:
        all_proxies = random.sample(all_proxies, 800)
    
    logger.info(f"{proxy_type.upper()} 原始代理: {len(all_proxies)} 个")
    return all_proxies

# ==================== 主流程 ====================
async def main(proxy_type: str):
    start_time = datetime.now()
    logger.info(f"=== 开始更新 {proxy_type.upper()} 代理 ===")
    
    raw = fetch_proxies(proxy_type)
    
    # 验证
    valid_list = []
    connector = aiohttp.TCPConnector(limit=CONCURRENT_LIMIT, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        # 这里简化使用同步质量检查（更稳定），也可改成异步
        with ThreadPoolExecutor(max_workers=60) as executor:   # 需要 from concurrent.futures import ThreadPoolExecutor
            pass  # 实际使用下面同步方式
    
    # 使用同步多线程验证（更快）
    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=60) as executor:
        futures = [executor.submit(check_proxy_quality, p, proxy_type) for p in raw]
        for future in as_completed(futures):
            result = future.result()
            if result:
                valid_list.append(result["proxy"])
                if len(valid_list) % 40 == 0:
                    logger.info(f"已找到有效 {len(valid_list)} 个")
                if len(valid_list) >= MAX_VALID_PER_TYPE:
                    break

    # 按延迟排序
    # valid_list 已按发现顺序，可进一步排序

    # 保存
    filename = f"{proxy_type}.txt"
    with open(filename, "w") as f:
        f.write("\n".join(valid_list))
    
    with open("proxies.json", "w", encoding="utf-8") as f:
        json.dump({
            "update_time": datetime.utcnow().isoformat() + "Z",
            "type": proxy_type,
            "total": len(valid_list),
            "countries": COUNTRIES
        }, f, indent=2)

    duration = (datetime.now() - start_time).seconds
    msg = f"""✅ **{proxy_type.upper()} 代理更新完成**
• 时间：{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
• 耗时：{duration} 秒
• 有效数量：**{len(valid_list)}**
• 过滤：{len(COUNTRIES)} 个国家"""
    
    logger.info(msg)
    send_notification(msg)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--type', choices=['http', 'socks5', 'all'], default='all')
    args = parser.parse_args()

    if args.type == 'all':
        asyncio.run(main('http'))
        asyncio.run(main('socks5'))
    else:
        asyncio.run(main(args.type))
