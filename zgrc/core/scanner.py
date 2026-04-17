import importlib.util
import logging
from typing import List

from ..providers import PACKAGE_MAP

logger = logging.getLogger(__name__)


class Scanner:
    @classmethod
    def get_installed_providers(cls) -> List[str]:
        """Return list of provider names with installed packages"""
        installed = []

        for package_name, provider in PACKAGE_MAP.items():
            if cls.is_installed(package_name):
                installed.append(provider)
                logger.debug(f"Found {package_name} -> {provider}")

        logger.info(f"Detected providers: {installed}")
        return installed

    @staticmethod
    def is_installed(package_name: str) -> bool:
        """Check if a package is installed"""
        package_normalized = package_name.replace("-", "_")
        spec = importlib.util.find_spec(package_normalized)
        return spec is not None
