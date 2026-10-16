# -*- coding: utf-8 -*-
import socket
import logging
import urllib.request
from urllib.parse import urlparse
from typing import Optional
import httpx
from openai import OpenAI

logger = logging.getLogger("core.client_utils")

def is_local_proxy_alive(proxy_url: str) -> bool:
    try:
        parsed = urlparse(proxy_url if "://" in proxy_url else "http://" + proxy_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 80
        with socket.create_connection((host, port), timeout=0.3):
            return True
    except Exception:
        return False

def should_trust_env_proxies() -> bool:
    try:
        proxies = urllib.request.getproxies()
        for proto, purl in proxies.items():
            if "127.0.0.1" in purl or "localhost" in purl:
                if not is_local_proxy_alive(purl):
                    logger.warning(f"Detected inactive local proxy {purl}, bypassing to direct connection.")
                    return False
    except Exception:
        pass
    return True

def create_resilient_openai_client(
    api_key: str, 
    base_url: Optional[str] = None, 
    timeout: float = 60.0,
    force_direct: bool = False
) -> OpenAI:
    trust_env = False if force_direct else should_trust_env_proxies()
    http_client = httpx.Client(trust_env=trust_env, timeout=timeout)
    return OpenAI(
        api_key=api_key,
        base_url=base_url or None,
        timeout=timeout,
        http_client=http_client
    )
