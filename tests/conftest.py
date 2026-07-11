from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.fixture
def write_package() -> Callable[..., Path]:
    def write(
        directory: Path,
        *,
        name: str = "demo_pkg",
        version: str = "0.1.0",
        description: str = "A demo package",
        build_type: str | None = None,
        package_format: str = "3",
        licenses: tuple[str, ...] = ("Apache-2.0",),
    ) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        export = f"<export><build_type>{build_type}</build_type></export>" if build_type else ""
        license_xml = "".join(f"<license>{license_name}</license>" for license_name in licenses)
        xml = (
            f'<package format="{package_format}">'
            f"<name>{name}</name>"
            f"<version>{version}</version>"
            f"<description>{description}</description>"
            '<maintainer email="dev@example.com">Developer</maintainer>'
            f"{license_xml}{export}</package>"
        )
        manifest = directory / "package.xml"
        manifest.write_text(xml, encoding="utf-8")
        return directory

    return write
