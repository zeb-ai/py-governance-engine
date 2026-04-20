from __future__ import annotations

import base64
import json
import logging
import zlib
from typing import Dict

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


class AuthToken(BaseModel):
    domain: str = Field(..., description="Governance server URL")
    opentelemetry: str = Field(..., description="OpenTelemetry collector endpoint")
    group_id: str = Field(..., description="User Group identifier")
    user_id: str = Field(..., description="User identifier")

    @classmethod
    def decode(cls, api_key: str) -> AuthToken:
        """
        Decode and validate a GRC API key to extract configuration parameters.
        The API key is expected to start with 'grc_' followed by base64url-encoded, zlib-compressed JSON payload.
        """
        try:
            if not api_key.startswith("grc_"):
                raise ValueError("Invalid API key format: must start with 'grc_'")

            token: str = api_key.replace("grc_", "")

            # Add padding automatically (handles base64url without padding)
            token += "=" * (-len(token) % 4)

            compressed: bytes = base64.urlsafe_b64decode(token)
            json_bytes: bytes = zlib.decompress(compressed)
            payload: Dict[str, str] = json.loads(json_bytes.decode("utf-8"))

            auth_token: AuthToken = cls(
                domain=payload.get("host"),
                opentelemetry=payload.get("otel"),
                group_id=payload.get("gid"),
                user_id=payload.get("uid"),
            )

            logger.debug("Successfully decoded API key")
            return auth_token

        except ValidationError as e:
            logger.debug(f"Invalid API key data: {e}")
            raise ValueError("API key is corrupted, please provide a valid API key")
        except zlib.error as e:
            logger.debug("compression has been failed", e)
            raise ValueError("API key is corrupted, please provide a valid API key")
        except json.JSONDecodeError as e:
            logger.debug("JSON decoding has been failed", e)
            raise ValueError("API key is corrupted, please provide a valid API key")
        except Exception as e:
            logger.debug(f"Error decoding API key: {e}")
            raise ValueError(f"Failed to decode API key: {e}")


# for dev purpose
# TODO: Need to remove when all testing done
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "encode":
        pass
    elif len(sys.argv) > 1 and sys.argv[1] == "decode":
        api_key = input("Enter API key: ").strip()
        try:
            decoded = AuthToken.decode(api_key)
            print("\nDecoded API Key:", decoded)
        except Exception as e:
            print(f"Error: {e}")
