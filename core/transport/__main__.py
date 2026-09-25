"""`python -m core.transport` — stdio JSON-lines daemon entry point."""

from .stdio import main

raise SystemExit(main())