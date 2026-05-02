from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class APIClient:
    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def get(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Send GET request to the specified endpoint with automatic retry on failure."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            # In mitmproxy setup for terminal, already http(s) proxy address, this overrides > trust_env=False
            async with httpx.AsyncClient(
                timeout=self.timeout, trust_env=False
            ) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"GET {url} failed: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def post(
        self, endpoint: str, json: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Send POST request to the specified endpoint with automatic retry on failure."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            # In mitmproxy setup for terminal, already http(s) proxy address, this overrides > trust_env=False
            async with httpx.AsyncClient(
                timeout=self.timeout, trust_env=False
            ) as client:
                response = await client.post(url, json=json)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"POST {url} failed: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def put(
        self, endpoint: str, json: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Send PUT request to the specified endpoint with automatic retry on failure."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            # In mitmproxy setup for terminal, already http(s) proxy address, this overrides > trust_env=False
            async with httpx.AsyncClient(
                timeout=self.timeout, trust_env=False
            ) as client:
                response = await client.put(url, json=json)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"PUT {url} failed: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def delete(self, endpoint: str) -> Dict[str, Any]:
        """Send DELETE request to the specified endpoint with automatic retry on failure."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            # In mitmproxy setup for terminal, already http(s) proxy address, this overrides > trust_env=False
            async with httpx.AsyncClient(
                timeout=self.timeout, trust_env=False
            ) as client:
                response = await client.delete(url)
                response.raise_for_status()
                return response.json() if response.content else {}
        except Exception as e:
            logger.error(f"DELETE {url} failed: {e}")
            raise
