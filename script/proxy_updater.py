import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--type', choices=['http', 'socks5', 'all'], default='all')
    args = parser.parse_args()
    
    # 根据参数决定验证哪些
    if args.type == 'http':
        # 只跑 HTTP
        raw = fetch_proxies()
        valid_http = asyncio.run(validate_proxies(raw["http"], "http"))
        # 保存 http.txt 和更新 proxies.json
    elif args.type == 'socks5':
        # 只跑 SOCKS5
        ...
    else:
        # 全部

      import time
import requests

# 测试地址
TEST_URL = "http://httpbin.org/ip"
ANONYMITY_TEST_URL = "http://httpbin.org/headers"   # 检查是否泄露真实IP

def check_proxy_quality(proxy_str: str, proxy_type: str = "http", timeout=7):
    """
    返回: (是否有效, 延迟(ms), 匿名度等级, 错误信息)
    """
    start = time.time()
    result = {
        "valid": False,
        "latency": 0,
        "anonymity": "transparent",  # transparent / anonymous / elite
        "error": ""
    }
    
    try:
        proxies = {}
        if proxy_type == "socks5":
            proxies = {
                "http": f"socks5://{proxy_str}",
                "https": f"socks5://{proxy_str}"
            }
        else:
            proxies = {
                "http": f"http://{proxy_str}",
                "https": f"http://{proxy_str}"
            }
        
        # 第一步：基本连通性 + 速度
        r = requests.get(TEST_URL, proxies=proxies, timeout=timeout)
        latency = round((time.time() - start) * 1000)
        
        if r.status_code != 200:
            result["error"] = f"Status {r.status_code}"
            return result
        
        result["latency"] = latency
        result["valid"] = True
        
        # 第二步：匿名度检测（较耗时，可选关闭）
        try:
            headers_r = requests.get(ANONYMITY_TEST_URL, proxies=proxies, timeout=timeout)
            if headers_r.status_code == 200:
                data = headers_r.json()
                real_ip = "你的真实IP"  # 可替换为已知IP
                if real_ip not in str(data):
                    # 进一步判断
                    if "Via" not in str(data) and "Proxy-Connection" not in str(data):
                        result["anonymity"] = "elite"
                    else:
                        result["anonymity"] = "anonymous"
        except:
            pass  # 匿名度检测失败不影响连通性
        
        # 可选：测试 Google 通过率
        # google_r = requests.get("https://www.google.com", proxies=proxies, timeout=10)
        # if google_r.status_code == 200: result["google_pass"] = True
        
    except requests.exceptions.Timeout:
        result["error"] = "Timeout"
    except Exception as e:
        result["error"] = str(e)[:80]
    
    return result
