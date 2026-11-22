
import base64
import ipaddress
import json
import socket
import time
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urlparse

SOURCE_URL = (
    "https://raw.githubusercontent.com/"
    "freenodess/freenodess/refs/heads/main/nodes/v2ray-base64.txt"
)
API_URL = "https://ipwho.is/{}"
ALLOWED = {"JP", "TW", "KR", "SG"}

CACHE_FILE = "geoip-cache.json"
STATE_FILE = "geoip-state.json"
MAX_LOOKUPS_PER_UTC_DAY = 750


def fetch_text(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        return response.read().decode("utf-8")


def decode_subscription(raw):
    compact = "".join(raw.split())
    try:
        return base64.b64decode(
            compact + "=" * (-len(compact) % 4)
        ).decode("utf-8", errors="replace")
    except Exception:
        return raw


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def extract_host(line):
    try:
        return urlparse(line).hostname
    except ValueError:
        return None


def resolve_host(host):
    try:
        ip = ipaddress.ip_address(host)
        return [str(ip)] if ip.is_global else []
    except ValueError:
        pass

    try:
        answers = socket.getaddrinfo(
            host, None, socket.AF_UNSPEC, socket.SOCK_STREAM
        )
        ips = []
        for answer in answers:
            value = answer[4][0]
            try:
                parsed = ipaddress.ip_address(value)
                if parsed.is_global and value not in ips:
                    ips.append(value)
            except ValueError:
                continue
        return ips
    except (OSError, UnicodeError):
        return []


def lookup_ip(ip, cache, state):
    if ip in cache:
        return cache[ip]

    if state["requests"] >= MAX_LOOKUPS_PER_UTC_DAY:
        return None

    state["requests"] += 1

    try:
        data = json.loads(fetch_text(API_URL.format(ip)))

        if not data.get("success"):
            return None

        result = {
            "country": data.get("country"),
            "country_code": data.get("country_code"),
            "city": data.get("city")
        }

        if not result["country_code"]:
            return None

        cache[ip] = result
        return result

    except Exception as exc:
        print("GeoIP lookup failed:", ip, str(exc))
        return None

    finally:
        if state["requests"] % 10 == 0:
            save_json(CACHE_FILE, cache)
            save_json(STATE_FILE, state)
        time.sleep(1.1)


def main():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    cache = load_json(CACHE_FILE, {})
    state = load_json(
        STATE_FILE,
        {"date": today, "requests": 0}
    )

    if state.get("date") != today:
        state = {"date": today, "requests": 0}

    raw = fetch_text(SOURCE_URL)
    decoded = decode_subscription(raw)

    lines = [
        line.strip()
        for line in decoded.splitlines()
        if line.strip() and "://" in line
    ]

    host_cache = {}
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
            ips = []
            details = []
            region = "UNKNOWN"
        else:
            if host not in host_cache:
                host_cache[host] = resolve_host(host)

            ips = host_cache[host]
            details = [
                lookup_ip(ip, cache, state)
                for ip in ips
            ]

            codes = {
                item["country_code"]
                for item in details
                if item and item.get("country_code")
            }

            if details and all(details) and len(codes) == 1:
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

    save_json(CACHE_FILE, cache)
    save_json(STATE_FILE, state)

    report = {
        "source": SOURCE_URL,
        "total_nodes": len(lines),
        "unique_cached_ips": len(cache),
        "requests_used_today_utc": state["requests"],
        "daily_request_cap": MAX_LOOKUPS_PER_UTC_DAY,
        "allowed_regions": sorted(ALLOWED),
        "statistics": stats,
        "results": results,
        "note": "仅地区分析，不筛选或删除节点。UNKNOWN 节点全部保留。",
        "geoip_provider": "ipwho.is"
    }

    save_json("geoip-report.json", report)

    print(json.dumps({
        "total_nodes": len(lines),
        "unique_cached_ips": len(cache),
        "requests_used_today_utc": state["requests"],
        "statistics": stats
    }, ensure_ascii=False, indent=2))

    print("GeoIP analysis completed.")


if __name__ == "__main__":
    main()
