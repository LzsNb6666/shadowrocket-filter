import base64
import json
import urllib.request
from collections import Counter
from urllib.parse import urlparse

SOURCE_URL = (
    "https://raw.githubusercontent.com/"
    "freenodess/freenodess/refs/heads/main/nodes/v2ray-base64.txt"
)

def fetch_subscription():
    req = urllib.request.Request(
        SOURCE_URL,
        headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8").strip()

def decode_subscription(raw):
    raw = "".join(raw.split())
    try:
        return base64.b64decode(
            raw + "=" * (-len(raw) % 4)
        ).decode("utf-8", errors="replace")
    except Exception:
        return raw

def analyze():
    raw = fetch_subscription()
    decoded = decode_subscription(raw)
    lines = [line.strip() for line in decoded.splitlines() if line.strip()]

    protocols = Counter()
    hosts = Counter()
    samples = []

    for line in lines:
        if "://" not in line:
            continue

        protocol = line.split("://", 1)[0].lower()
        protocols[protocol] += 1

        try:
            parsed = urlparse(line)
            host = parsed.hostname or "无法解析"
            hosts["IP" if is_ip(host) else "域名"] += 1

            if len(samples) < 8:
                samples.append({
                    "protocol": protocol,
                    "host": host
                })
        except Exception:
            hosts["解析失败"] += 1

    report = {
        "source": SOURCE_URL,
        "raw_size_bytes": len(raw.encode("utf-8")),
        "decoded_lines": len(lines),
        "node_count": sum(protocols.values()),
        "protocols": dict(protocols),
        "host_types": dict(hosts),
        "samples": samples,
        "note": "本版本只统计，不筛选、不删除节点。"
    }

    with open("report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(json.dumps(report, ensure_ascii=False, indent=2))

def is_ip(host):
    import ipaddress
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False

if __name__ == "__main__":
    analyze()
