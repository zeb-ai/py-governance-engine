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


class CostCalculationException(PolicyException):
    """Raised when cost calculation fails - mandatory for GRC tracking"""

    def __init__(self, model_id: str, error: str):
        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text

        console = Console()

        message = Text()
        message.append(
            "Cost calculation failed for the requested model.\n\n", style="bold red"
        )

        message.append("Details:\n", style="bold yellow")
        message.append("  Model:  ", style="white")
        message.append(f"{model_id}\n", style="bold cyan")
        message.append("  Error:  ", style="white")
        message.append(f"{error}\n\n", style="bold red")

        message.append("Possible Causes:\n", style="bold yellow")
        message.append("  • Model not supported by litellm\n", style="white")
        message.append("  • Incorrect model name or identifier\n", style="white")
        message.append("  • Model provider configuration issue\n\n", style="white")

        message.append("Actions:\n", style="bold yellow")
        message.append("  • Verify model name is correct\n", style="white")
        message.append(
            "  • Raise github issues if model should be supported", style="white"
        )

        panel = Panel(
            message,
            title="[bold red]COST CALCULATION FAILED[/bold red]",
            border_style="red",
            padding=(1, 2),
        )

        console.print(panel)
        simple_message = f"Cost calculation failed for model '{model_id}': {error}"
        super().__init__(simple_message, model_id=model_id, error=error)
        self.model_id = model_id


class QuotaReportingException(PolicyException):
    """Raised when quota usage reporting to GRC API fails"""

    def __init__(self, tokens: int, cost: float, error: str):
        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text

        console = Console()

        message = Text()
        message.append("Failed to report quota usage to GRC API.\n\n", style="bold red")

        message.append("Usage Details:\n", style="bold yellow")
        message.append("  Tokens: ", style="white")
        message.append(f"{tokens:,}\n", style="bold cyan")
        message.append("  Cost:   ", style="white")
        message.append(f"${cost:.6f}\n\n", style="bold cyan")

        message.append("Error:\n", style="bold yellow")
        message.append(f"  {error}\n\n", style="bold red")

        message.append("Actions:\n", style="bold yellow")
        message.append("  • Check network connectivity\n", style="white")
        message.append("  • Verify GRC API endpoint is accessible\n", style="white")
        message.append("  • Review API request payload format\n", style="white")
        message.append("  • Contact support if issue persists", style="white")

        panel = Panel(
            message,
            title="[bold red]✖ QUOTA REPORTING FAILED[/bold red]",
            border_style="red",
            padding=(1, 2),
        )

        console.print(panel)
        simple_message = (
            f"Quota reporting failed: {tokens} tokens, ${cost:.6f} - {error}"
        )
        super().__init__(simple_message, tokens=tokens, cost=cost, error=error)
        self.tokens = tokens
        self.cost = cost
