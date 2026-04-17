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
    policy_id: str = Field(..., description="Policy identifier")
    # TODO: for now just adding, need to remove later part
    user_id: str
    project_id: str

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
                domain=payload.get("u"),
                opentelemetry=payload.get("otel"),
                policy_id=payload.get("poid"),
                user_id=payload.get("user_id"),
                project_id=payload.get("project_id"),
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

    # TODO: Need to remove when all testing done
    @staticmethod
    def encode(
        domain: str, opentelemetry: str, policy_id: str, user_id: str, project_id: str
    ) -> str:
        """Encode configuration into a GRC API key."""
        payload = {
            "u": domain,
            "otel": opentelemetry,
            "poid": policy_id,
            "user_id": user_id,
            "project_id": project_id,
        }

        json_bytes = json.dumps(payload).encode("utf-8")
        compressed = zlib.compress(json_bytes)
        encoded = base64.urlsafe_b64encode(compressed).decode("utf-8").rstrip("=")

        return f"grc_{encoded}"


# for dev purpose
# TODO: Need to remove when all testing done
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "encode":
        domain = "http://localhost:3000"
        opentelemetry = "http://localhost:4318"
        policy_id = "69d5289f7d344da86a254e47"
        user_id = "69d528817d344da86a254e3d"
        project_id = "69d528897d344da86a254e3f"

        api_key = AuthToken.encode(
            domain, opentelemetry, policy_id, user_id, project_id
        )
        print(f"\nGenerated API Key:\n{api_key}")

        decoded = AuthToken.decode(api_key)
        print(f"Decoded API Key:\n{decoded}")

    elif len(sys.argv) > 1 and sys.argv[1] == "decode":
        api_key = input("Enter API key: ").strip()
        try:
            decoded = AuthToken.decode(api_key)
            print("\nDecoded API Key:", decoded)
        except Exception as e:
            print(f"Error: {e}")
