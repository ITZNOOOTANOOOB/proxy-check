import asyncio
import aiohttp
import requests
import json
from datetime import datetime
import os

# ==================== 配置区 ====================
TEST_URL = "http://httpbin.org/ip"
TIMEOUT = 10
MAX_VALID = 300  # 限制保存数量，避免文件过大

# Telegram 配置（必填）
TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"      # 从 @BotFather 获取
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"               # 你的用户ID或群组ID

# Discord 配置（选填）
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/..."  # Webhook URL

# ==================== 通知函数 ====================
def send_telegram(message: str):
    """发送 Telegram 通知"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        resp = requests.post(url, json=data, timeout=10)
        if resp.status_code == 200:
            print("✅ Telegram 通知已发送")
        else:
            print(f"Telegram 发送失败: {resp.text}")
    except Exception as e:
        print(f"Telegram 异常: {e}")

def send_discord(message: str, embed=None):
    """发送 Discord Webhook 通知"""
    if not DISCORD_WEBHOOK or DISCORD_WEBHOOK == "https://discord.com/api/webhooks/...":
        return
    try:
        data = {"content": message}
        if embed:
            data["embeds"] = [embed]
        
        resp = requests.post(DISCORD_WEBHOOK, json=data, timeout=10)
        if resp.status_code in (200, 204):
            print("✅ Discord 通知已发送")
        else:
            print(f"Discord 发送失败: {resp.status_code}")
    except Exception as e:
        print(f"Discord 异常: {e}")

# ==================== 代理验证（简化版，实际可换成异步） ====================
def check_proxy(proxy_str: str, proxy_type: str = "http"):
    try:
        if proxy_type.lower() in ["socks5", "socks4"]:
            proxies = {"http": f"{proxy_type}://{proxy_str}", "https": f"{proxy_type}://{proxy_str}"}
            r = requests.get(TEST_URL, proxies=proxies, timeout=TIMEOUT)
        else:
            proxies = {"http": f"http://{proxy_str}", "https": f"http://{proxy_str}"}
            r = requests.get(TEST_URL, proxies=proxies, timeout=TIMEOUT)
        
        if r.status_code == 200:
            return proxy_str
    except:
        pass
    return None

def validate_proxies(proxies_list, proxy_type="http"):
    valid = []
    print(f"正在验证 {len(proxies_list)} 个 {proxy_type} 代理...")
    for p in proxies_list[:800]:   # 限制验证数量
        result = check_proxy(p, proxy_type)
        if result:
            valid.append(result)
            print(f"✓ {result}")
        if len(valid) >= MAX_VALID:
            break
    return valid

# ==================== 主流程 ====================
if __name__ == "__main__":
    start_time = datetime.now()
    print(f"[{start_time}] 开始更新代理列表...")

    # 1. 获取代理（推荐用 ProxyScrape，支持国家/匿名度过滤）
    proxy_sources = [
        # 示例：HTTP + 美国 + elite 匿名
        "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&protocol=http&country=US&anonymity=elite&format=text&limit=500",
        # SOCKS5 示例
        "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&protocol=socks5&format=text&limit=300",
        # 添加更多国家如 CN, DE, JP 等
    ]

    all_proxies = []
    for url in proxy_sources:
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                lines = [line.strip() for line in r.text.splitlines() if ":" in line]
                all_proxies.extend(lines)
        except:
            pass

    all_proxies = list(set(all_proxies))
    print(f"获取到 {len(all_proxies)} 个原始代理")

    # 2. 验证
    valid_http = validate_proxies([p for p in all_proxies if True], "http")   # 可加过滤
    valid_socks5 = validate_proxies([p for p in all_proxies if True], "socks5")

    # 3. 保存文件
    result = {
        "update_time": datetime.utcnow().isoformat() + "Z",
        "total_valid": len(valid_http) + len(valid_socks5),
        "http": valid_http,
        "socks5": valid_socks5
    }

    with open("proxies.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    with open("http.txt", "w") as f:
        f.write("\n".join(valid_http))
    with open("socks5.txt", "w") as f:
        f.write("\n".join(valid_socks5))

    # 4. 发送通知
    duration = (datetime.now() - start_time).seconds
    msg = f"""🚀 **代理列表更新完成**

**时间**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
**耗时**: {duration} 秒
**有效代理**:
• HTTP/HTTPS: {len(valid_http)}
• SOCKS5: {len(valid_socks5)}
**总数**: {len(valid_http) + len(valid_socks5)}

仓库地址: https://github.com/你的用户名/你的仓库"""

    send_telegram(msg)

    # Discord 可加 Embed 更好看
    embed = {
        "title": "代理列表更新成功 ✅",
        "color": 0x00ff00,
        "fields": [
            {"name": "HTTP", "value": str(len(valid_http)), "inline": True},
            {"name": "SOCKS5", "value": str(len(valid_socks5)), "inline": True},
            {"name": "更新时间", "value": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'), "inline": False}
        ]
    }
    send_discord("代理更新完成", embed)

    print("🎉 全部完成！")
