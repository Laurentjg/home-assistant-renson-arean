"""The dashboard card as a dashboard resource.

Home Assistant loads dashboard resources once its own frontend is up, which is
when a card can register its element. Home Assistant has no public call for an
integration to add one, so this works on the collection behind Dashboards →
Resources and is kept free of Home Assistant imports: `__init__.py` hands the
collection in, and falls back when it is not there.
"""

from __future__ import annotations

from typing import Any


def _own(resources: Any, path: str) -> list[dict[str, Any]]:
    """Return the resources that point at the card, whatever build they name."""
    return [
        item
        for item in resources.async_items()
        if str(item.get("url", "")).split("?")[0] == path
    ]


async def async_ensure(resources: Any, path: str, url: str) -> None:
    """Make `url` the one resource for the card at `path`."""
    # Reads the stored resources; without it the collection looks empty.
    await resources.async_get_info()
    own = _own(resources, path)
    if not own:
        await resources.async_create_item({"res_type": "module", "url": url})
        return
    if own[0]["url"] != url:
        await resources.async_update_item(own[0]["id"], {"url": url})
    for extra in own[1:]:
        await resources.async_delete_item(extra["id"])


async def async_remove(resources: Any, path: str) -> None:
    """Remove the card from the resources."""
    await resources.async_get_info()
    for item in _own(resources, path):
        await resources.async_delete_item(item["id"])
