"""Core utility functions for the Cognive Control Plane."""

import re
from urllib.parse import urlparse, urlunparse


def mask_credentials(url: str) -> str:
    """Mask password/credentials in connection URLs.

    Supports standard URL formats like:
    - postgresql://user:password@host:port/db
    - redis://user:password@host:port/0
    - amqp://user:password@host:port//

    Args:
        url: Connection URL that may contain credentials.

    Returns:
        URL with password replaced by '***'.

    Examples:
        >>> mask_credentials("postgresql://postgres:secret@localhost:5432/db")
        'postgresql://postgres:***@localhost:5432/db'
        >>> mask_credentials("redis://localhost:6379/0")
        'redis://localhost:6379/0'
    """
    if not url:
        return url

    try:
        parsed = urlparse(url)
        if parsed.password:
            # Reconstruct netloc with masked password
            if parsed.username:
                masked_netloc = f"{parsed.username}:***@{parsed.hostname}"
            else:
                masked_netloc = f":***@{parsed.hostname}"

            if parsed.port:
                masked_netloc += f":{parsed.port}"

            # Rebuild the URL with masked credentials
            masked = parsed._replace(netloc=masked_netloc)
            return urlunparse(masked)
        return url
    except Exception:
        # Fallback: use regex if URL parsing fails
        return re.sub(r"(://[^:]+:)[^@]+(@)", r"\1***\2", url)

