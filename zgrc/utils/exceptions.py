class PolicyException(Exception):
    """Base exception for all policy-related errors"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message)
        self.details = kwargs


class QuotaExceededException(PolicyException):
    """Raised when user has exceeded their dollar-based quota"""

    def __init__(self, used: float, remaining: float, domain: str = None):
        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text

        console = Console()

        message = Text()
        message.append(
            "Your API request was blocked due to insufficient quota.\n\n",
            style="bold red",
        )

        message.append("Quota Status:\n", style="bold yellow")
        message.append("  Used:      ", style="white")
        message.append(f"${used:.4f}\n", style="bold red")
        message.append("  Remaining: ", style="white")
        message.append(f"${remaining:.4f}\n\n", style="bold red")

        message.append("Actions:\n", style="bold yellow")
        message.append("  • Wait for monthly quota reset\n", style="white")

        if domain:
            message.append(
                f"  • Increase your quota at {domain}/user-groups", style="white"
            )
        else:
            message.append(
                "  • Increase your quota in your account settings in GRC Dashboard",
                style="white",
            )

        panel = Panel(
            message,
            title="[bold red] QUOTA EXCEEDED[/bold red]",
            border_style="red",
            padding=(1, 2),
        )

        console.print(panel)
        simple_message = f"Quota exceeded: ${used:.4f} used, ${remaining:.4f} remaining"
        super().__init__(simple_message, used=used, remaining=remaining)
        self.used = used
        self.remaining = remaining
        self.domain = domain


class InvalidAPIKeyException(PolicyException):
    """Raised when API key is missing, invalid, or corrupted"""

    def __init__(self, message: str = "API key is invalid or corrupted"):
        super().__init__(message)
        self.message = message
