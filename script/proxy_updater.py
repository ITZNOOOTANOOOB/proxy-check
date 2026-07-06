import requests
import logging
import random
from datetime import datetime

# 配置实时日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(message)s',
    datefmt='%H:%M:%S',
    force=True
)
logger = logging.getLogger(__name__)

MAX_VALID = 120
TIMEOUT = 5

def main():
    start = datetime.now()
    logger.info("=== 极致高速代理更新启动 ===")
    logger.info(f"最大有效数量限制: {MAX_VALID} 个 | 超时: {TIMEOUT}秒")

    # 来源
    sources = [
        "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&protocol=http&format=text&limit=700",
        "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/http/data.txt",
        "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/socks5/data.txt",
    ]

    raw = []
    for url in sources:
        try:
            r = requests.get(url, timeout=12)
            if r.status_code == 200:
                lines = [line.strip() for line in r.text.splitlines() if ":" in line]
                raw.extend(lines)
                logger.info(f"来源获取 → {len(lines)} 个")
        except Exception as e:
            logger.warning(f"来源失败 → {e}")

    raw = list(dict.fromkeys(raw))
    if len(raw) > 600:
        raw = random.sample(raw, 600)

    logger.info(f"开始验证 → 共 {len(raw)} 个原始代理")

    valid = []
    checked = 0

    for proxy in raw:
        checked += 1
        try:
            proxies = {"http": f"http://{proxy}", "https": f"http://{proxy}"}
            r = requests.get("http://httpbin.org/ip", proxies=proxies, timeout=TIMEOUT)
            
            if r.status_code == 200:
                valid.append(proxy)
                logger.info(f"✓ 有效 [{len(valid)}] → {proxy}")
        except:
            pass

        # 实时进度输出（关键！）
        if checked % 25 == 0 or len(valid) % 20 == 0:
            logger.info(f"进度: 已检查 {checked}/{len(raw)} | 当前有效: {len(valid)}")

        if len(valid) >= MAX_VALID:
            logger.info("达到最大数量，提前终止验证")
            break

    # 保存
    with open("http.txt", "w") as f:
        f.write("\n".join(valid))
    
    with open("proxies.json", "w") as f:
        f.write(str({
            "update_time": datetime.utcnow().isoformat() + "Z",
            "total": len(valid),
            "checked": checked
        }))

    duration = (datetime.now() - start).seconds
    logger.info(f"🎉 任务完成！耗时 {duration} 秒 | 最终有效代理: {len(valid)} 个")

if __name__ == "__main__":
    main()
