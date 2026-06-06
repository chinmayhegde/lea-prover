"""Launch the Lea API with uvicorn:  ``python -m lea_api``  or  ``lea-api``."""

from __future__ import annotations

import uvicorn

from .app import create_app
from .settings import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
