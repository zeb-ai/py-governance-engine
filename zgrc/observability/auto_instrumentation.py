from __future__ import annotations

from typing import TYPE_CHECKING, List
import importlib.util
import importlib
import logging
from pydantic import BaseModel

if TYPE_CHECKING:
    from opentelemetry.sdk.resources import Resource

logger = logging.getLogger(__name__)

INSTRUMENTAL_PACKAGES = {
    "httpx": {
        "instrumentor_package": "opentelemetry.instrumentation.httpx",
        "instrumentor_class": "HTTPXClientInstrumentor",
    },
    "requests": {
        "instrumentor_package": "opentelemetry.instrumentation.requests",
        "instrumentor_class": "RequestsInstrumentor",
    },
    "aiohttp": {
        "instrumentor_package": "opentelemetry.instrumentation.aiohttp_client",
        "instrumentor_class": "AioHttpClientInstrumentor",
    },
    "urllib3": {
        "instrumentor_package": "opentelemetry.instrumentation.urllib3",
        "instrumentor_class": "URLLib3Instrumentor",
    },
    "fastapi": {
        "instrumentor_package": "opentelemetry.instrumentation.fastapi",
        "instrumentor_class": "FastAPIInstrumentor",
    },
    "flask": {
        "instrumentor_package": "opentelemetry.instrumentation.flask",
        "instrumentor_class": "FlaskInstrumentor",
    },
    "starlette": {
        "instrumentor_package": "opentelemetry.instrumentation.starlette",
        "instrumentor_class": "StarletteInstrumentor",
    },
    "psycopg2": {
        "instrumentor_package": "opentelemetry.instrumentation.psycopg2",
        "instrumentor_class": "Psycopg2Instrumentor",
    },
    "psycopg": {
        "instrumentor_package": "opentelemetry.instrumentation.psycopg",
        "instrumentor_class": "PsycopgInstrumentor",
    },
    "sqlalchemy": {
        "instrumentor_package": "opentelemetry.instrumentation.sqlalchemy",
        "instrumentor_class": "SQLAlchemyInstrumentor",
    },
    "redis": {
        "instrumentor_package": "opentelemetry.instrumentation.redis",
        "instrumentor_class": "RedisInstrumentor",
    },
    "pymongo": {
        "instrumentor_package": "opentelemetry.instrumentation.pymongo",
        "instrumentor_class": "PymongoInstrumentor",
    },
    "botocore": {
        "instrumentor_package": "opentelemetry.instrumentation.botocore",
        "instrumentor_class": "BotocoreInstrumentor",
    },
    "celery": {
        "instrumentor_package": "opentelemetry.instrumentation.celery",
        "instrumentor_class": "CeleryInstrumentor",
    },
    "logging": {
        "instrumentor_package": "opentelemetry.instrumentation.logging",
        "instrumentor_class": "LoggingInstrumentor",
    },
}


class InstrumentalPackage(BaseModel):
    name: str
    instrumentor_package: str
    instrumentor_class: str


class MissingInstrumentor(BaseModel):
    name: str
    instrumentor_package: str
    install_command: str


class AutoInstrumentation:
    def __init__(self, resource: Resource):
        self.resource = resource
        self.avail_instrumental_package: List[InstrumentalPackage] = []
        self.missing_instrumental_package: List[MissingInstrumentor] = []

    def instrument(self):
        """
        Automatically instrument all detected frameworks and libraries with OpenTelemetry.

        Scans for installed packages, checks for corresponding
        OpenTelemetry instrumentors, applies instrumentation and displays installation suggestions for
        missing instrumentors to achieve complete observability coverage.
        """
        detected = self.get_installed_frameworks()
        instrumental = detected[0]
        missing = detected[1]

        logger.info(
            f"Auto-instrumentation: found {len(instrumental)} packages to instrument"
        )

        if missing:
            self._show_suggestions(missing)

        for pkg in instrumental:
            success = self._instrument_package(pkg)
            if success:
                logger.info(f"✓ Instrumented: {pkg.name}")
            else:
                logger.warning(f"✗ Failed to instrument: {pkg.name}")

    @staticmethod
    def _instrument_package(pkg: InstrumentalPackage) -> bool:
        """Apply OpenTelemetry instrumentation to a specific package by dynamically loading and invoking its instrumentor."""
        try:
            instrumentor_module = importlib.import_module(pkg.instrumentor_package)
            instrumentor_class = getattr(instrumentor_module, pkg.instrumentor_class)

            # Instantiate the instrumentor
            instrumentor = instrumentor_class()

            # Special configuration for logging instrumentor
            if pkg.name == "logging":
                instrumentor.instrument(set_logging_format=True)
            else:
                instrumentor.instrument()
            return True
        except Exception as e:
            logger.debug(f"Failed to instrument {pkg.name}: {type(e).__name__}: {e}")
            return False

    def get_installed_frameworks(self):
        """Detect installed frameworks and their corresponding OpenTelemetry instrumentors."""
        for package_name in INSTRUMENTAL_PACKAGES:
            config = INSTRUMENTAL_PACKAGES[package_name]

            # Special case: logging is built-in, always check for instrumentor
            if package_name == "logging":
                if self._is_installed(config["instrumentor_package"]):
                    self.avail_instrumental_package.append(
                        InstrumentalPackage(
                            name=package_name,
                            instrumentor_package=config["instrumentor_package"],
                            instrumentor_class=config["instrumentor_class"],
                        )
                    )
                else:
                    self.missing_instrumental_package.append(
                        MissingInstrumentor(
                            name=package_name,
                            instrumentor_package=config["instrumentor_package"].replace(
                                ".", "-"
                            ),
                            install_command=f"uv add {config['instrumentor_package'].replace('.', '-')}",
                        )
                    )
                continue

            # Check if the actual framework/library is installed (not just the instrumentor)
            if not self._is_installed(package_name):
                continue  # Skip - framework not in use by the application

            # Framework is installed, now check if instrumentor is available
            if self._is_installed(config["instrumentor_package"]):
                self.avail_instrumental_package.append(
                    InstrumentalPackage(
                        name=package_name,
                        instrumentor_package=config["instrumentor_package"],
                        instrumentor_class=config["instrumentor_class"],
                    )
                )
            else:
                self.missing_instrumental_package.append(
                    MissingInstrumentor(
                        name=package_name,
                        instrumentor_package=config["instrumentor_package"].replace(
                            ".", "-"
                        ),
                        install_command=f"uv add {config['instrumentor_package'].replace('.', '-')}",
                    )
                )

        return self.avail_instrumental_package, self.missing_instrumental_package

    @staticmethod
    def _is_installed(package_name: str) -> bool:
        """Check if a Python package is installed or not"""
        try:
            spec = importlib.util.find_spec(package_name)
            return spec is not None
        except (ImportError, ModuleNotFoundError, ValueError):
            return False

    @staticmethod
    def _show_suggestions(missing: List[MissingInstrumentor]) -> None:
        """Display rich-formatted installation suggestions for missing OpenTelemetry instrumentors."""
        if not missing:
            return

        from rich.console import Console

        console = Console()

        console.print(
            "\n[bold yellow]We are found your using below package, to get fully instrumentation Missing instrumentor Detected[/bold yellow]"
        )
        console.print("Install the following packages for complete observability:\n")

        for pkg in missing:
            console.print(
                f"  • [cyan]{pkg.name}[/cyan]: [green]{pkg.install_command}[/green]"
            )

        all_packages = " ".join([pkg.instrumentor_package for pkg in missing])
        console.print("\n[bold]Install all at once:[/bold]")
        console.print(f"  [green]uv add {all_packages}[/green]")

        console.print("\n[bold]Or install complete bundle:[/bold]")
        console.print("  [green]uv add zgrc[auto-instrument][/green]\n")
