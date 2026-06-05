class RequestResult:
    __slots__ = ("allowed", "model", "used_quota", "remaining_quota")

    def __init__(
        self, allowed: int, model: str, used_quota: float, remaining_quota: float
    ):
        self.allowed = allowed
        self.model = model
        self.used_quota = used_quota
        self.remaining_quota = remaining_quota


class ResponseResult:
    __slots__ = (
        "cost",
        "input_tokens",
        "output_tokens",
        "used_quota",
        "remaining_quota",
    )

    def __init__(
        self,
        cost: float,
        input_tokens: int,
        output_tokens: int,
        used_quota: float,
        remaining_quota: float,
    ):
        self.cost = cost
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.used_quota = used_quota
        self.remaining_quota = remaining_quota
