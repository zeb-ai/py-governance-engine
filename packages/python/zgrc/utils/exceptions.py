class QuotaExceededError(Exception):
    def __init__(self, used: float, remaining: float):
        self.used = used
        self.remaining = remaining
        super().__init__(f"Quota exceeded. Used: {used}, Remaining: {remaining}")
