import requests
import logging
import random
from datetime import datetime

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s | %(levelname)s | %(message)s',
    force=True
)
logger = logging.getLogger(__name__)

MAX_VALID = 120
TIMEOUT = 5

def main():
    start = datetime.now()
    logger.info("=== 极致版启动 ===")

    # 来源列表
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
                logger.info(f"从来源获取 {len(lines)} 个代理")
        except Exception as e:
            logger.warning(f"来源失败: {e}")

    raw = list(dict.fromkeys(raw))
    if len(raw) > 500:
        raw = random.sample(raw, 500)

    logger.info(f"开始验证 {len(raw)} 个原始代理...")

    valid = []
    for i, proxy in enumerate(raw):
        try:
            proxies = {"http": f"http://{proxy}", "https": f"http://{proxy}"}
            r = requests.get("http://httpbin.org/ip", proxies=proxies, timeout=TIMEOUT)
            if r.status_code == 200:
                valid.append(proxy)
                logger.info(f"✓ 有效 [{len(valid)}] {proxy}")
        except:
            continue
        
        if len(valid) >= MAX_VALID:
            logger.info("已达到最大有效数量，提前结束验证")
            break

        # 防止极端情况，每验证 80 个打印一次进度
        if (i + 1) % 80 == 0:
            logger.info(f"进度: 已检查 {i+1}/{len(raw)} 个")

    # 保存文件
    with open("http.txt", "w") as f:
        f.write("\n".join(valid))
    
    with open("proxies.json", "w") as f:
        f.write(str({
            "update_time": datetime.utcnow().isoformat() + "Z",
            "total": len(valid)
        }))

    duration = (datetime.now() - start).seconds
    logger.info(f"🎉 完成！总耗时 {duration} 秒 | 有效代理: {len(valid)} 个")

if __name__ == "__main__":
    main()
