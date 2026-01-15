from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional
import requests
from dataclasses import field

from .utils import RetryConfig, RateLimiter, backoff_sleep

@dataclass
class HttpConfig:
    timeout: float = 15.0
    min_interval: float = 0.25
    retry: RetryConfig = field(default_factory=RetryConfig)

class HttpClient:
    """requests.Session + 重试 + 简单限速 + Host 轮换"""

    def __init__(self, base_hosts: Optional[Iterable[str]] = None, config: Optional[HttpConfig] = None):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
            "Accept": "application/json,text/plain,*/*",
            "Referer": "https://quote.eastmoney.com/",
        })
        self.config = config or HttpConfig()
        self.limiter = RateLimiter(self.config.min_interval)

        # 东财 push2 主域名 + 常见数字子域名（网页端会用到）
        self.base_hosts = list(base_hosts) if base_hosts else [
            "https://push2.eastmoney.com",
            "https://80.push2.eastmoney.com",
            "https://82.push2.eastmoney.com",
            "https://85.push2.eastmoney.com",
        ]

    def get_json(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        last_err = None
        for i in range(self.config.retry.max_retries):
            for host in self.base_hosts:
                try:
                    self.limiter.wait()
                    url = host.rstrip("/") + "/" + path.lstrip("/")
                    r = self.session.get(url, params=params, timeout=self.config.timeout)
                    r.raise_for_status()
                    return r.json()
                except Exception as e:
                    last_err = e
                    # 换 host 试试
                    continue
            # 所有 host 都失败，再指数退避后重试
            backoff_sleep(i, self.config.retry)
        raise RuntimeError(f"GET JSON failed after retries: {last_err}") from last_err
