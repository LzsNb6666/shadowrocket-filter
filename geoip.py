
import base64
import ipaddress
import json
import socket
import time
import urllib.request
from urllib.parse import urlparse

SOURCE_URL = (
    "https://raw.githubusercontent.com/"
    "freenodess/freenodess/refs/heads/main/nodes/v2ray-base64.txt"
)

API_URL = "https://ipwho.is/{}"

# 允许保留的地区
ALLOWED = {"JP", "TW", "KR", "SG"}

def fetch(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return response.read().decode("utf-8")

def decode_subscription(raw):
    raw = "".join(raw.split())
    try:
        return base64.b64decode(
            raw + "=" * (-len(raw) % 4)
        ).decode("utf-8", errors="replace")
    except Exception:
        return raw

def extract_host(line):
    try:
        parsed = urlparse(line)
        return parsed.hostname
    except Exception:
        return None

def resolve_host(host):
    try:
        ipaddress.ip_address(host)
        return [host]
    except ValueError:
        pass

    try:
        results = socket.getaddrinfo(
            host, None, socket.AF_UNSPEC, socket.SOCK_STREAM
        )
        return list(dict.fromkeys(
            item[4][0] for item in results
        ))
    except Exception:
        return []

def lookup_ip(ip, cache):
    if ip in cache:
        return cache[ip]

    try:
        data = json.loads(fetch(API_URL.format(ip)))

        if data.get("success"):
            result = {
                "country": data.get("country"),
                "country_code": data.get("country_code"),
                "city": data.get("city")
            }
        else:
            result = None

    except Exception:
        result = None

    cache[ip] = result
    time.sleep(1.1)
    return result

def main():
    raw = fetch(SOURCE_URL)
    decoded = decode_subscription(raw)

    lines = [
        line.strip()
        for line in decoded.splitlines()
        if line.strip() and "://" in line
    ]

    cache = {}
    results = []
    stats = {
        "JP": 0,
        "TW": 0,
        "KR": 0,
        "SG": 0,
        "OTHER": 0,
        "UNKNOWN": 0
    }

    for index, line in enumerate(lines, 1):
        host = extract_host(line)

        if not host:
            results.append({
                "index": index,
                "host": None,
                "region": "UNKNOWN"
            })
            stats["UNKNOWN"] += 1
            continue

        ips = resolve_host(host)

        if not ips:
            region = "UNKNOWN"
            details = []
        else:
            details = [
                lookup_ip(ip, cache)
                for ip in ips
            ]

            codes = {
                item["country_code"]
                for item in details
                if item and item.get("country_code")
            }

            if len(codes) == 1:
                code = next(iter(codes))
                region = code if code in ALLOWED else "OTHER"
            else:
                region = "UNKNOWN"

        stats[region] += 1

        results.append({
            "index": index,
            "host": host,
            "ips": ips,
            "region": region,
            "geoip": details
        })

    report = {
        "source": SOURCE_URL,
        "total_nodes": len(lines),
        "unique_ips_queried": len(cache),
        "allowed_regions": sorted(ALLOWED),
        "statistics": stats,
        "results": results,
        "note": "仅地区分析，不删除或筛选节点。"
    }

    with open("geoip-report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(json.dumps(stats, ensure_ascii=False, indent=2))
    print("GeoIP analysis completed.")

if __name__ == "__main__":
    main()
