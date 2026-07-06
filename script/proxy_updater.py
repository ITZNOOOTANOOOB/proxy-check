import requests
import logging
import random
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
logger = logging.getLogger(__name__)

MAX_VALID = 120          # 严格控制数量
TIMEOUT = 5

def main():
    start = datetime.now()
    logger.info("=== 极致高速模式启动 ===")

    # 只使用最快可靠的来源
    sources = [
        "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&protocol=http&format=text&limit=600",
        "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/http/data.txt",
        "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/socks5/data.txt",
    ]

    raw = []
    for url in sources:
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                lines = [line.strip() for line in r.text.splitlines() if ":" in line]
                raw.extend(lines)
        except:
            pass

    raw = list(dict.fromkeys(raw))
    if len(raw) > 500:
        raw = random.sample(raw, 500)

    logger.info(f"获取原始代理: {len(raw)} 个")

    # 快速验证
    valid = []
    for proxy in raw:
        try:
            proxies = {"http": f"http://{proxy}", "https": f"http://{proxy}"}
            r = requests.get("http://httpbin.org/ip", proxies=proxies, timeout=TIMEOUT)
            if r.status_code == 200:
                valid.append(proxy)
                if len(valid) % 30 == 0:
                    logger.info(f"有效: {len(valid)} 个")
                if len(valid) >= MAX_VALID:
                    break
        except:
            continue

    # 保存文件
    with open("http.txt", "w") as f:
        f.write("\n".join(valid))
    
    with open("proxies.json", "w") as f:
        json_data = {
            "update_time": datetime.utcnow().isoformat() + "Z",
            "total": len(valid),
            "note": "极致高速版 - 仅 HTTP"
        }
        f.write(str(json_data))

    duration = (datetime.now() - start).seconds
    logger.info(f"完成！耗时 {duration} 秒 | 有效代理: {len(valid)} 个")

if __name__ == "__main__":
    main()
