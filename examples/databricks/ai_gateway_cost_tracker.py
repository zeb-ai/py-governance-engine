import os
import json
import zgrc
import requests
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential
import httpx


# Pricing is loaded from the table shipped inside the installed `zgrc` package
# (the same data/merged_pricing.json the native engine uses at request time),
# so these offline estimates stay consistent with Z-GRC's own cost calculation.
_PRICING_PATH = Path(zgrc.__file__).resolve().parent / "data" / "merged_pricing.json"
with open(_PRICING_PATH) as _f:
    _PRICING_MODELS: Dict[str, Any] = json.load(_f).get("models", {})


def calculate_cost_from_usage(model_id: str, usage: Dict[str, int]) -> float:
    """Estimate USD cost for a model given token counts.

    Mirrors zgrc's native cost_calculator (src/cost_calculator.c): pricing is
    per 1M tokens and the total is input + output + cache-read + cache-write.
    Returns 0.0 for unknown models, matching the engine's not-found behaviour.
    """
    model = _PRICING_MODELS.get(model_id)
    if not model:
        return 0.0
    pricing = model.get("pricing", {})
    million = 1_000_000.0
    return (
        usage.get("input_tokens", 0) / million * pricing.get("input", 0.0)
        + usage.get("output_tokens", 0) / million * pricing.get("output", 0.0)
        + usage.get("cache_read_tokens", 0) / million * pricing.get("cache_read", 0.0)
        + usage.get("cache_write_tokens", 0) / million * pricing.get("cache_write", 0.0)
    )


class APIClient:
    def __init__(self, base_url: str, auth_token: str = None, timeout: int = 60):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.auth_token = auth_token

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def get(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Send GET request to the specified endpoint with automatic retry on failure."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            headers = {}
            if self.auth_token:
                headers["Cookie"] = f"auth_token={self.auth_token}"

            async with httpx.AsyncClient(
                timeout=self.timeout, trust_env=False
            ) as client:
                response = await client.get(url, params=params, headers=headers)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            print(f"GET {url} failed: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def post(
        self,
        endpoint: str,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Send POST request to the specified endpoint with automatic retry on failure."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            # Build headers
            request_headers = {}
            if self.auth_token:
                request_headers["Cookie"] = f"auth_token={self.auth_token}"
            if headers:
                request_headers.update(headers)

            # In mitmproxy setup for terminal, already http(s) proxy address, this overrides > trust_env=False
            async with httpx.AsyncClient(
                timeout=self.timeout, trust_env=False
            ) as client:
                response = await client.post(url, json=json, headers=request_headers)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            print(f"POST {url} failed: {e}")
            raise


class Quota(BaseModel):
    used_quota: float = 0.0  # Dollar-based tracking instead of tokens
    remaining_quota: float = 0.0  # Dollar-based tracking instead of tokens


class QuotaClient:
    def __init__(
        self, base_url: str = "https://z-grc.zeb.co/", auth_token: Optional[str] = None
    ) -> None:
        self.base_url: str = base_url
        self.client: APIClient = APIClient(
            base_url=self.base_url, auth_token=auth_token
        )

    async def get_quota(self, group_id: str, user_id: str) -> Quota:
        """Fetch current quota status from the GRC API and update the context."""
        params = {
            "group_id": group_id,
            "user_id": user_id,
        }

        response: Dict[str, Any] = await self.client.get(
            "/api/quota/user", params=params
        )

        quota_status = Quota(
            used_quota=response.get("used_cost", 0.0),
            remaining_quota=response.get("remaining_cost", 0.0),
        )
        return quota_status

    async def post_quota_usage(
        self, tokens_used: int, cost: float, user_id: str, group_id: str
    ) -> Quota:
        """Report token consumption and cost to the GRC API."""
        body = {
            "user_id": user_id,
            "policy_id": group_id,
            "group_id": group_id,
            "amount": tokens_used,
            "cost": cost,
        }

        print(f"DEBUG: Sending to /api/quota/consume: {body}")

        response: Dict[str, Any] = await self.client.post(
            "/api/quota/consume", json=body
        )

        print(f"DEBUG: Response: {response}")

        quota_status = Quota(
            used_quota=response.get("used_cost", 0.0),
            remaining_quota=response.get("remaining_cost", 0.0),
        )
        return quota_status


class Main:
    def __init__(self):
        # Name of the Databricks AI Gateway serving endpoint to govern.
        self.gateway_name: str = os.environ.get(
            "ZGRC_GATEWAY_NAME", "<YOUR_AI_GATEWAY_ENDPOINT_NAME>"
        )
        # Databricks workspace URL, e.g. "https://dbc-xxxxxxxx-xxxx.cloud.databricks.com"
        self.databricks_host: str = os.environ.get(
            "DATABRICKS_HOST", "<YOUR_DATABRICKS_HOST>"
        )
        # Databricks personal access token ("dapi..."). Prefer dbutils.secrets.get() on Databricks.
        self.databricks_token: str = os.environ.get(
            "DATABRICKS_TOKEN", "<YOUR_DATABRICKS_TOKEN>"
        )
        # Z-GRC group/policy id that owns the users and quotas.
        self.zgrc_group_id: str = os.environ.get(
            "ZGRC_GROUP_ID", "<YOUR_ZGRC_GROUP_ID>"
        )
        # Base URL of the Z-GRC application.
        self.zgrc_base_url: str = os.environ.get(
            "ZGRC_BASE_URL", "https://z-grc.zeb.co"
        )
        # Z-GRC auth token (JWT) used as the auth_token cookie. Short-lived; rotate before expiry.
        self.zgrc_auth_token: str = os.environ.get(
            "ZGRC_AUTH_TOKEN", "<YOUR_ZGRC_AUTH_TOKEN>"
        )
        self.quota_client = QuotaClient(
            base_url=self.zgrc_base_url, auth_token=self.zgrc_auth_token
        )

    async def get_usage_from_inference_table(self):
        """read the usages from the inference table for all users"""
        try:
            from pyspark.sql import SparkSession
            import json

            spark = SparkSession.builder.getOrCreate()

            catalog = "zeb_labs"
            schema = "default"
            table = "z-grc_payload"

            df = spark.sql(f"""
                SELECT
                    requester as user_email,
                    url,
                    response
                    FROM `{catalog}`.`{schema}`.`{table}`

                WHERE status_code = 200
                    ORDER BY event_time DESC

            """)

            print(df)

            user_events = {}
            for row in df.collect():
                user_email = row["user_email"]
                response_str = row["response"]
                url = row["url"]
                response_json = (
                    json.loads(response_str)
                    if isinstance(response_str, str)
                    else response_str
                )

                if user_email not in user_events:
                    user_events[user_email] = {"events": [], "url": url}

                user_events[user_email]["events"].append(response_json)

            result = {}
            for user_email, data in user_events.items():
                events = data["events"]
                url = data["url"]

                model_id = events[0].get("model") if events else None

                usage_totals = {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cache_read_tokens": 0,
                    "cache_write_tokens": 0,
                }
                for event in events:
                    usage = event.get("usage", {})
                    usage_totals["input_tokens"] += usage.get("prompt_tokens", 0)
                    usage_totals["output_tokens"] += usage.get("completion_tokens", 0)
                    usage_totals["cache_read_tokens"] += usage.get(
                        "cache_read_input_tokens", 0
                    )
                    usage_totals["cache_write_tokens"] += usage.get(
                        "cache_creation_input_tokens", 0
                    )

                cost = (
                    calculate_cost_from_usage(model_id, usage_totals)
                    if model_id
                    else 0.0
                )

                total_tokens = sum(
                    e.get("usage", {}).get("total_tokens", 0) for e in events
                )

                user_id = await self._get_user_id_from_email(user_email)

                result[user_email] = {
                    "user_email": user_email,
                    "user_id": user_id,
                    "total_tokens": total_tokens,
                    "estimated_cost_usd": cost,
                }

            return result

        except Exception as e:
            print("exception raised while in querying a table", e)
            return

    async def _get_user_id_from_email(self, email: str) -> Optional[str]:
        """Map email to UUID for GRC API by fetching from group members"""
        if not hasattr(self, "_email_to_id_cache"):
            try:
                response = await self.quota_client.client.get(
                    f"/api/groups/{self.zgrc_group_id}"
                )

                print(f"<<< {response} >>>")

                self._email_to_id_cache = {}
                for member in response.get("group", {}).get("members", []):
                    user = member.get("user", {})
                    user_email = user.get("email")
                    user_id = user.get("user_id")
                    if user_email and user_id:
                        self._email_to_id_cache[user_email] = user_id
            except Exception as e:
                print(f"Failed to fetch group members: {e}")
                self._email_to_id_cache = {}

        return self._email_to_id_cache.get(email)

    async def get_allocated_cost(self, user_email: str, user_id: str):
        """getting the allocated cost for the user from the zgrc application database"""
        self.quota_client.base_url = self.zgrc_base_url

        quota = await self.quota_client.get_quota(
            group_id=self.zgrc_group_id, user_id=user_id
        )

        return {
            "user_email": user_email,
            "used_quota": quota.used_quota,
            "remaining_quota": quota.remaining_quota,
        }

    async def post_usage_cost(self, user_email: str, usage_data: Dict):
        """calculate the usage cost from the overall usage comparing with existing usage"""
        self.quota_client.base_url = self.zgrc_base_url

        # Extract data from usage
        tokens_used = usage_data.get("total_tokens", 0)
        cost = usage_data.get("estimated_cost_usd", 0.0)
        user_id = usage_data.get("user_id", user_email)

        # Post usage to GRC
        updated_quota = await self.quota_client.post_quota_usage(
            tokens_used=tokens_used,
            cost=cost,
            user_id=user_id,
            group_id=self.zgrc_group_id,
        )

        # Check if exceeded
        exceeded = updated_quota.remaining_quota <= 0

        return {
            "user_email": user_email,
            "used_quota": updated_quota.used_quota,
            "remaining_quota": updated_quota.remaining_quota,
            "exceeded": exceeded,
        }

    async def set_rate_limit(
        self, user_email: str, requests_per_minute: int, tokens_per_minute: int
    ):
        """Updating the rate limit for a user when user is exceeded is current cost allocated"""

        headers = {
            "Authorization": f"Bearer {self.databricks_token}",
            "Content-Type": "application/json",
        }

        response = requests.get(
            f"{self.databricks_host}/api/ai-gateway/v2/endpoints/{self.gateway_name}",
            headers=headers,
        )

        if response.status_code != 200:
            print(f"Failed to get gateway config: {response.text}")
            return False

        gateway_config = response.json()
        current_limits = gateway_config.get("config", {}).get("rate_limits", [])

        new_limits = [
            limit
            for limit in current_limits
            if not (limit.get("key") == "USER" and limit.get("principal") == user_email)
        ]

        new_limits.extend(
            [
                {
                    "key": "USER",
                    "renewal_period": "MINUTE",
                    "principal": user_email,
                    "requests": requests_per_minute,
                },
                {
                    "key": "USER",
                    "renewal_period": "MINUTE",
                    "principal": user_email,
                    "tokens": tokens_per_minute,
                },
            ]
        )

        update_payload = gateway_config.get("config", {})
        update_payload["rate_limits"] = new_limits

        update_response = requests.patch(
            f"{self.databricks_host}/api/ai-gateway/v2/endpoints/{self.gateway_name}?update_mask=config.rate_limits",
            headers=headers,
            json={"config": update_payload},
        )

        if update_response.status_code in [200, 201, 202]:
            print(
                f"Rate limit set for {user_email}: {requests_per_minute} req/min, {tokens_per_minute} tokens/min"
            )
            return True
        else:
            print(f"Failed to update rate limit: {update_response.text}")
            return False

    async def add_user_to_group(self, email: str) -> Optional[str]:
        """Add a user to the group and return their user_id"""
        try:
            payload = {
                "email": email,
                "group_id": self.zgrc_group_id,
                "name": email.split("@")[0],
                "description": "Created from the databricks",
            }

            print(f"Adding user to group: {payload}")

            # Z-GRC service key ("sk_...") authorizing external API-key/user creation.
            headers = {
                "X-Service-Key": os.environ.get(
                    "ZGRC_SERVICE_KEY", "<YOUR_ZGRC_SERVICE_KEY>"
                )
            }

            response = await self.quota_client.client.post(
                "/api/external/apikey/generate", json=payload, headers=headers
            )

            print(f"User added successfully: {response}")

            # Extract user_id from response (nested in 'key' object)
            key_data = response.get("key", {})
            user_id = key_data.get("user_id")

            if user_id and hasattr(self, "_email_to_id_cache"):
                self._email_to_id_cache[email] = user_id
                print(f"Cached user_id {user_id} for {email}")

            return user_id

        except Exception as e:
            print(f"Failed to add user to group: {e}")
            return None

    async def main(self):
        """Main orchestration: get usage, check quota, apply rate limits"""
        print("Starting Cost Governance Workflow")

        all_usage = await self.get_usage_from_inference_table()
        print(f"Found {len(all_usage)} users with activity")

        for user_email, usage_data in all_usage.items():
            print(f"\nProcessing: {user_email}")
            user_id = usage_data.get("user_id", user_email)
            print("user_id >>>>>>", user_id)

            if not user_id:
                print("  User not found in group - Adding user to group")
                user_id = await self.add_user_to_group(user_email)
                if not user_id:
                    print("  Failed to add user - Blocking user")
                    await self.set_rate_limit(user_email, 0, 0)
                    continue
                # Update usage_data with the new user_id
                usage_data["user_id"] = user_id
                print(f"  User added successfully with ID: {user_id}")

            quota_info = await self.get_allocated_cost(user_email, user_id)
            print("<<<<<<< Quota Info >>>>>>>\n", quota_info)
            print(f"  Remaining quota: ${quota_info['remaining_quota']:.4f}")

            result = await self.post_usage_cost(user_email, usage_data)

            if result["exceeded"]:
                print("  EXCEEDED - Setting rate limit to 0")
                await self.set_rate_limit(user_email, 0, 0)
            else:
                print("  Within budget")

        print("\nWorkflow Complete")


if __name__ == "__main__":
    import asyncio
    import nest_asyncio

    nest_asyncio.apply()
    main_instance = Main()
    asyncio.run(main_instance.main())
