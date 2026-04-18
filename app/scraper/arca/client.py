from curl_cffi import requests

DEFAULT_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "accept-language": "ko,en-US;q=0.9,en;q=0.8",
    "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
    "upgrade-insecure-requests": "1",
}

BASE_URL = "https://arca.live"


class ArcaClient:
    """curl-cffi 기반 arca.live 클라이언트. Cloudflare 우회를 위해 브라우저 impersonation 사용."""

    def __init__(self, cookies: str):
        """cookies: 브라우저에서 복사한 raw cookie 문자열."""
        self.session = requests.Session(impersonate="chrome136")
        self.session.headers.update(DEFAULT_HEADERS)
        self._set_cookies(cookies)

    def _set_cookies(self, raw: str):
        for pair in raw.split(";"):
            pair = pair.strip()
            if "=" not in pair:
                continue
            key, value = pair.split("=", 1)
            self.session.cookies.set(key.strip(), value.strip(), domain="arca.live")

    def get(self, path: str, **kwargs) -> requests.Response:
        url = f"{BASE_URL}{path}" if path.startswith("/") else path
        resp = self.session.get(url, **kwargs)
        resp.raise_for_status()
        return resp

    def close(self):
        self.session.close()
