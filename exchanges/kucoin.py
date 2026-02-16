import aiohttp
import socket
import logging

log = logging.getLogger(__name__)

KUCOIN_BASE_URL = "https://openapi-v2.kucoin.com"
PING_ENDPOINT = "/api/v1/timestamp"


class KuCoin:
    NAME = "KUCOIN"

    def __init__(self):
        self.online = False

        # Force IPv4 with system resolver for DNS reliability
        self.connector = aiohttp.TCPConnector(
            family=socket.AF_INET,
            ssl=True,
            resolver=aiohttp.ThreadedResolver()
        )

        self.timeout = aiohttp.ClientTimeout(total=5)

    async def connect(self):
        log.info("[KUCOIN] connecting...")
        await self.ping()

    async def ping(self) -> bool:
        url = KUCOIN_BASE_URL + PING_ENDPOINT

        try:
            async with aiohttp.ClientSession(
                connector=self.connector,
                timeout=self.timeout
            ) as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if "data" in data:
                            self.online = True
                            return True

        except Exception as e:
            log.error(f"[KUCOIN] OFFLINE: {e}")

        self.online = False
        return False

    def status(self) -> bool:
        return self.online
