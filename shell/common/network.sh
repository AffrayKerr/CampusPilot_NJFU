#!/usr/bin/env bash
set -eu

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

# 专项检测 VPN 门户是否可达（不跟随跳转，只看 HTTP 状态）
shell_network_check_vpn() {
  python - <<'PY'
import sys
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

url = "https://vpn.njfu.edu.cn/portal/"
try:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=8) as resp:
        print("true" if resp.status < 500 else "false")
except (URLError, HTTPError, TimeoutError, Exception):
    print("false")
PY
}

# 带 cookie 文件请求指定 URL，返回 HTTP 状态码；cookie_file 可为空
shell_network_request_with_cookie() {
  local url="${1:-}"
  local cookie_file="${2:-}"
  python - "$url" "$cookie_file" <<'PY'
import sys
import http.cookiejar
from urllib.request import Request, build_opener, HTTPCookieProcessor
from urllib.error import URLError, HTTPError

url = sys.argv[1]
cookie_file = sys.argv[2]

jar = http.cookiejar.MozillaCookieJar()
if cookie_file:
    try:
        jar.load(cookie_file, ignore_discard=True, ignore_expires=True)
    except Exception:
        pass

opener = build_opener(HTTPCookieProcessor(jar))
try:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with opener.open(req, timeout=8) as resp:
        print(resp.status)
except HTTPError as e:
    print(e.code)
except (URLError, TimeoutError, Exception):
    print(0)
PY
}
