import asyncio
import aiohttp
import requests
import json
import logging
from datetime import datetime
import os

# ==================== 配置区 ====================
TEST_URL = "http://httpbin.org/ip"
TIMEOUT = 8
MAX_VALID_PER_TYPE = 300   # 每个协议最多保留数量
CONCURRENT_LIMIT = 50        # 新增并发控制

# ==================== 国家过滤（可随意扩展） ====================
# 支持的国家列表（ISO 2位代码），留空表示不过滤
COUNTRIES = ["TW", "US", "GB", "DE", "JP", "KR", "FR", "CA", "AU", "SG", "NL", "SE", "NO", "FI", "DK", "IT", "ES"]

# 匿名度（仅对 HTTP 有效）
ANONYMITY = "elite"        # elite / anonymous / transparent / all

# 通知配置（推荐使用 GitHub Secrets）
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK", "")

# ==================== 日志配置 ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ==================== 通知函数 ====================
def send_telegram(message: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        requests.post(url, json=data, timeout=10)
        logger.info("Telegram 通知已发送")
    except Exception as e:
        logger.error(f"Telegram 发送失败: {e}")

def send_discord(message: str):
    if not DISCORD_WEBHOOK:
        return
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": message}, timeout=10)
        logger.info("Discord 通知已发送")
    except Exception as e:
        logger.error(f"Discord 发送失败: {e}")

# ==================== 代理获取 + 过滤 ====================
def fetch_proxies():
    proxies = {"http": [], "socks5": []}
    country_str = ",".join(COUNTRIES) if COUNTRIES else "all"
    
    logger.info(f"开始从多个来源获取代理 | 国家: {country_str if country_str != 'all' else '全部'}")

    # ==================== 多个来源 ====================
    sources = [
        # 1. ProxyScrape（推荐，稳定，支持过滤）
        {
            "base": "https://api.proxyscrape.com/v4/free-proxy-list/get",
            "params": lambda proto: {
                "request": "display_proxies",
                "proxy_format": "protocolipport",
                "format": "text",
                "protocol": proto,
                "country": country_str,
                "anonymity": ANONYMITY if proto == "http" else "all",
                "timeout": 15000,
                "limit": 1200
            }
        },
        
        # 2. Proxifly CDN（速度快，已验证）
        {
            "base": "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/http/data.txt",
            "params": None
        },
        {
            "base": "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/socks5/data.txt",
            "params": None
        },
        
        # 3. 其他公开列表（可继续添加）
        "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/protocols/http.txt",
        "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/protocols/socks5.txt",
        
        # 你可以继续添加更多 raw GitHub 或 TXT 链接
    ]

    for source in sources:
        try:
            if isinstance(source, dict):   # 有 params 的 API
                base = source["base"]
                for proto in ["http", "socks5"]:
                    if source["params"]:
                        params = source["params"](proto)
                        resp = requests.get(base, params=params, timeout=20)
                    else:
                        resp = requests.get(base, timeout=20)
                    
                    if resp.status_code == 200:
                        lines = [line.strip() for line in resp.text.splitlines() if line.strip() and ":" in line]
                        key = "http" if proto == "http" else "socks5"
                        proxies[key].extend(lines)
                        logger.info(f"✓ 从 {base[-50:]} 获取 {len(lines)} 个 {proto.upper()}")
            else:  # 直接 TXT 链接
                resp = requests.get(source, timeout=20)
                if resp.status_code == 200:
                    lines = [line.strip() for line in resp.text.splitlines() if line.strip() and ":" in line]
                    # 简单区分协议
                    for line in lines:
                        if line.endswith(":1080") or ":9050" in line:   # 粗略判断
                            proxies["socks5"].append(line)
                        else:
                            proxies["http"].append(line)
                    logger.info(f"✓ 从 {source[-40:]} 获取 {len(lines)} 个代理")
        except Exception as e:
            logger.warning(f"来源失败 {source}: {e}")
    
    # 去重
    for k in proxies:
        proxies[k] = list(dict.fromkeys(proxies[k]))
    
    logger.info(f"多来源获取完成 → HTTP: {len(proxies['http'])} | SOCKS5: {len(proxies['socks5'])}")
    return proxies
# ==================== 验证 ====================
async def check_proxy(session, proxy_str: str, proxy_type: str):
    try:
        if proxy_type == "socks5":
            proxies = {"http": f"socks5://{proxy_str}", "https": f"socks5://{proxy_str}"}
            r = requests.get(TEST_URL, proxies=proxies, timeout=TIMEOUT)
            if r.status_code == 200:
                return proxy_str
        else:
            async with session.get(TEST_URL, proxy=f"http://{proxy_str}", timeout=TIMEOUT) as resp:
                if resp.status == 200:
                    return proxy_str
    except:
        pass
    return None

async def validate_proxies(proxies_list, proxy_type="http"):
    valid = []
    connector = aiohttp.TCPConnector(limit=50, ssl=False)   # 限制并发
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [check_proxy(session, p, proxy_type) for p in proxies_list[:600]]  # 限制总验证数量
        for future in asyncio.as_completed(tasks):
            result = await future
            if result:
                valid.append(result)
                if len(valid) % 30 == 0:
                    logger.info(f"[{proxy_type}] 已找到有效 {len(valid)} 个")
                if len(valid) >= MAX_VALID_PER_TYPE:
                    break
    return valid

# ==================== 主流程 ====================
if __name__ == "__main__":
    start_time = datetime.now()
    logger.info("=== 代理更新任务开始 ===")
    
    # 1. 获取 + 过滤
    raw_proxies = fetch_proxies()
    
    # 2. 验证
    logger.info("开始验证代理...")
    valid_http = asyncio.run(validate_proxies(raw_proxies["http"], "http"))
    valid_socks5 = asyncio.run(validate_proxies(raw_proxies["socks5"], "socks5"))
    
    # 3. 保存结果
    result = {
        "update_time": datetime.utcnow().isoformat() + "Z",
        "filters": {"countries": COUNTRIES, "anonymity": ANONYMITY},
        "http": valid_http,
        "socks5": valid_socks5,
        "total": len(valid_http) + len(valid_socks5)
    }
    
    with open("proxies.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    with open("http.txt", "w") as f:
        f.write("\n".join(valid_http))
    with open("socks5.txt", "w") as f:
        f.write("\n".join(valid_socks5))
    
    duration = (datetime.now() - start_time).seconds
    logger.info(f"更新完成！总耗时 {duration} 秒 | 有效 HTTP: {len(valid_http)} | SOCKS5: {len(valid_socks5)}")
    
    # 4. 发送通知
    msg = f"""🚀 **代理更新完成**

**时间**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
**耗时**: {duration} 秒
**有效代理**:
• HTTP/HTTPS: **{len(valid_http)}**
• SOCKS5: **{len(valid_socks5)}**
**过滤条件**: {len(COUNTRIES)} 个国家 | 匿名度 {ANONYMITY}"""

    send_telegram(msg)
    send_discord(msg)
    
    logger.info("=== 任务结束 ===")
