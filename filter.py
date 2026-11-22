
import base64
import ipaddress
import json
import urllib.request
from urllib.parse import urlparse

SOURCE_URL = (
    "https://raw.githubusercontent.com/"
    "freenodess/freenodess/refs/heads/main/nodes/v2ray-base64.txt"
)

ALLOWED = {"JP", "TW", "KR", "SG"}


def fetch_text(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8")


def decode_subscription(raw):
    compact = "".join(raw.split())
    try:
        return base64.b64decode(
            compact + "=" * (-len(compact) % 4)
        ).decode("utf-8", errors="replace")
    except Exception:
        return raw


def extract_host(line):
    try:
        return urlparse(line).hostname
    except ValueError:
        return None


def main():
    with open("geoip-report.json", "r", encoding="utf-8") as f:
        report = json.load(f)

    raw = fetch_text(SOURCE_URL)
    decoded = decode_subscription(raw)

    lines = [
        line.strip()
        for line in decoded.splitlines()
        if line.strip() and "://" in line
    ]

    results = report.get("results", [])

    if len(lines) != report.get("total_nodes"):
        raise RuntimeError(
            "当前订阅节点数量与 GeoIP 报告不一致，停止筛选。"
        )

    if len(results) != len(lines):
        raise RuntimeError(
            "GeoIP 结果数量与当前订阅不一致，停止筛选。"
        )

    kept = []
    counts = {
        "JP": 0,
        "TW": 0,
        "KR": 0,
        "SG": 0,
        "UNKNOWN": 0
    }

    for index, line in enumerate(lines, 1):
        item = results[index - 1]

        if item.get("index") != index:
            raise RuntimeError(
                f"第 {index} 个节点索引不匹配，停止筛选。"
            )

        if item.get("host") != extract_host(line):
            raise RuntimeError(
                f"第 {index} 个节点地址发生变化，停止筛选。"
            )

        region = item.get("region")

        if region in ALLOWED or region == "UNKNOWN":
            kept.append(line)
            counts[region] += 1

    if not kept:
        raise RuntimeError("筛选结果为空，停止生成订阅。")

    output = base64.b64encode(
        "\n".join(kept).encode("utf-8")
    ).decode("ascii")

    with open("filtered-subscription.txt", "w", encoding="utf-8") as f:
        f.write(output)

    summary = {
        "source": SOURCE_URL,
        "original_nodes": len(lines),
        "filtered_nodes": len(kept),
        "excluded_nodes": len(lines) - len(kept),
        "kept_regions": counts,
        "format": "Base64",
        "unknown_nodes_kept": True
    }

    with open("filter-summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("Filtered subscription generated.")


if __name__ == "__main__":
    main()
