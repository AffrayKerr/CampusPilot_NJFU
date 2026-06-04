#!/usr/bin/env bash
set -euo pipefail

shell_network_is_available() {
  local url="${1:-https://www.baidu.com}"
  python - "$url" <<'PY'
import sys
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

url = sys.argv[1]
try:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=5) as resp:
        print("true" if resp.status < 500 else "false")
except (URLError, HTTPError, TimeoutError, Exception):
    print("false")
PY
}
