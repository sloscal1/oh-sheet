"""EchoMTG API client with rate limiting and retry logic."""

import asyncio
import getpass
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class EchoMTGConfig:
    """Configuration for EchoMTG API client."""
    base_url: str = "https://api.echomtg.com/api"
    api_key: str = ""
    rate_limit_per_second: float = 2.0  # Max 2 requests per second
    max_retries: int = 3
    timeout_seconds: float = 30.0


@dataclass
class EchoMTGClient:
    """Async client for EchoMTG API with rate limiting and retry logic."""
    config: EchoMTGConfig
    _last_request_time: float = field(default=0.0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    @classmethod
    async def create(cls, config: Optional["EchoMTGConfig"] = None) -> "EchoMTGClient":
        """Create an authenticated client.

        Reads credentials from environment variables ECHOMTG_EMAIL and
        ECHOMTG_PASSWORD. If ECHOMTG_PASSWORD is not set, prompts via
        getpass so it never appears in shell history or logs.

        A .env file in the project root is also supported (loaded if present).
        """
        if config is None:
            config = EchoMTGConfig()

        # Try loading .env from project root
        env_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            ".env",
        )
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    # Support both KEY=VALUE and KEY: VALUE formats
                    if "=" in line:
                        key, _, value = line.partition("=")
                    elif ": " in line:
                        key, _, value = line.partition(": ")
                    else:
                        continue
                    os.environ.setdefault(key.strip(), value.strip())

        email = os.environ.get("ECHOMTG_EMAIL", "")
        password = os.environ.get("ECHOMTG_PASSWORD", "")

        if not email:
            email = input("EchoMTG email: ").strip()
        if not password:
            password = getpass.getpass("EchoMTG password: ")

        client = cls(config=config)
        await client.login(email, password)
        return client

    async def login(self, email: str, password: str) -> None:
        """Authenticate and store the API token.

        POST /user/auth

        Args:
            email: Account email
            password: Account password
        """
        url = f"{self.config.base_url}/user/auth"
        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as http:
            response = await http.post(url, data={"email": email, "password": password})
            response.raise_for_status()
            data = response.json()

        token = data.get("token") or data.get("access_token") or data.get("api_key")
        if not token:
            raise ValueError(f"No token in auth response. Keys: {list(data.keys())}")

        self.config.api_key = token

        # Verify the token works
        status = data.get("status") or data.get("message") or ""
        user = data.get("user") or data.get("email") or data.get("username") or ""
        print(f"Login response: status={status}, user={user}, token={token[:8]}...")
        logger.info("Authenticated successfully.")

    async def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            min_interval = 1.0 / self.config.rate_limit_per_second
            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)
            self._last_request_time = time.monotonic()

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Make API request with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., /inventory/update)
            **kwargs: Additional arguments passed to httpx.request

        Returns:
            JSON response as dictionary

        Raises:
            Exception: If all retries fail
        """
        await self._rate_limit()

        url = f"{self.config.base_url}{endpoint}"
        headers = {
            "Content-Type": "application/json", 
            "Authorization": f"Bearer {self.config.api_key}",
        }

        for attempt in range(self.config.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                    req_kwargs = {}
                    if "data" in kwargs:
                        # POST: send JSON body
                        req_kwargs["content"] = json.dumps(kwargs["data"])
                    if "params" in kwargs:
                        # GET: send query params
                        req_kwargs["params"] = kwargs["params"]
                    print(f"  >> {method} {url}")
                    print(f"     body: {req_kwargs}")
                    response = await client.request(
                        method, url, headers=headers, **req_kwargs
                    )
                    response.raise_for_status()
                    return response.json()
            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code if e.response else 0
                if status_code == 429:  # Rate limited
                    wait_time = 2 ** attempt
                    logger.warning(f"Rate limited, waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                elif status_code >= 500:
                    logger.warning(
                        f"Server error {status_code}, retry {attempt + 1}/{self.config.max_retries}"
                    )
                    logger.warning(
                        e.response.text if e.response else "No response text"
                    )
                    await asyncio.sleep(1)
                else:
                    raise
            except httpx.TimeoutException:
                logger.warning(f"Timeout, retry {attempt + 1}/{self.config.max_retries}")
                await asyncio.sleep(1)

        raise Exception(f"Failed after {self.config.max_retries} retries: {endpoint}")

    async def update_inventory(
        self,
        inventory_id: str,
        quantity: Optional[int] = None,
        condition: Optional[str] = None,
        foil: Optional[bool] = None,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update an inventory item.

        POST /inventory/update

        Args:
            inventory_id: The echo_inventory_id of the item
            quantity: New quantity (optional)
            condition: New condition (optional)
            foil: Foil status (optional)
            language: Language code (optional)

        Returns:
            API response
        """
        params: Dict[str, Any] = {"id": inventory_id}
        if quantity is not None:
            params["quantity"] = quantity
        if condition is not None:
            params["condition"] = condition
        if foil is not None:
            params["foil"] = foil
        if language is not None:
            params["language"] = language

        return await self._request("POST", "/inventory/update", data=params)

    async def remove_inventory(self, inventory_id: str) -> Dict[str, Any]:
        """Remove an inventory item.

        POST /inventory/remove

        Args:
            inventory_id: The echo_inventory_id to remove

        Returns:
            API response
        """
        return await self._request(
            "POST", "/inventory/remove", data={"id": inventory_id}
        )

    async def add_inventory_batch(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Add multiple cards to inventory in a single call.

        POST /inventory/add/batch

        Each item dict should have:
            emid: int (required) - EchoMTG card ID
            quantity: int - default 1
            foil: int - 0=regular, 1=foil
            condition: str - default "NM"
            language: str - default "EN"
            acquired_price: str - optional
            acquired_date: str - optional (e.g., "1-1-2024")

        Args:
            items: List of item dicts

        Returns:
            API response
        """
        return await self._request("POST", "/inventory/add/batch", data=items)

    async def get_set(
        self,
        set_code: str,
        start: int = 0,
        limit: int = 5000,
    ) -> Dict[str, Any]:
        """Get all cards in a set.

        GET /data/set

        Args:
            set_code: 3-5 letter set code (e.g., "ISD")
            start: Index to start at
            limit: Total items to return

        Returns:
            API response with card data
        """
        return await self._request(
            "GET",
            "/data/set",
            params={
                "set_code": set_code,
                "minified": "true",
                "start": start,
                "limit": limit,
            },
        )

    async def get_set_all(self, set_code: str, page_size: int = 100) -> List[Dict[str, Any]]:
        """Fetch all cards in a set, paginating by page_size at a time.

        Continues fetching until a page returns fewer items than page_size,
        indicating the end of the set.

        Args:
            set_code: 3-5 letter set code (e.g., "ISD")
            page_size: Number of cards per request

        Returns:
            List of all card dicts from the set
        """
        all_cards: List[Dict[str, Any]] = []
        start = 0

        while True:
            data = await self.get_set(set_code, start=start, limit=page_size)
            set_data = data.get("set", {})
            cards = set_data.get("items", [])
            if not cards:
                break
            all_cards.extend(cards)
            logger.info(f"Fetched {len(all_cards)} cards from {set_code} so far...")
            if len(cards) < page_size:
                break
            start += page_size

        return all_cards

    async def create_note(
        self,
        target_id: str,
        target_app: str,
        note_text: str,
    ) -> Dict[str, Any]:
        """Create a note on a resource.

        POST /notes/create

        Args:
            target_id: ID of the target resource
            target_app: Application type (e.g., "inventory")
            note_text: The note content

        Returns:
            API response
        """
        return await self._request(
            "POST",
            "/notes/create",
            data={
                "target_id": target_id,
                "target_app": target_app,
                "note": note_text,
            },
        )

