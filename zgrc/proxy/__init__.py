from .handlers import RequestHandler, ResponseHandler

import logging

logger = logging.getLogger(__name__)


class ProxyAddon:
    """mitmproxy addon that wraps our handlers."""

    def __init__(self):
        self.request_handler = RequestHandler()
        self.response_handler = ResponseHandler(self.request_handler)

    async def request(self, flow):
        await self.request_handler.handle(flow)

    async def response(self, flow):
        await self.response_handler.handle(flow)


__all__ = ["ProxyAddon"]
