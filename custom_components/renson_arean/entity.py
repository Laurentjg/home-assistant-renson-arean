"""Base entities.

Two things live here that §4.3 and §5.0 insist on:

* identity is physical and the label is functional — the unique_id and the
  suggested entity_id follow the channel, the display name follows the
  function, and the user's own name always wins;
* an entity is unavailable as soon as its source is, and never quietly borrows
  a value from another source or freezes on the last known one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONFIDENCE_CONFIRMED,
    CONFIDENCE_UNKNOWN,
    INTERLOCK_NOTE,
    SOURCE_GATEWAY_CORE,
)

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo

    from .const import HvacChannel
    from .coordinators import RensonCoordinator


class RensonEntity(CoordinatorEntity):
    """Every entity of this integration.

    `device_identifier` is the same string the device carries in its
    `identifiers`, so a unique_id can always be traced back to its device
    (§4.1).
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RensonCoordinator,
        device: DeviceInfo,
        device_identifier: str,
        key: str,
        name: str | None,
        source: str,
        source_endpoint: str | None = None,
        suggested_object_id: str | None = None,
    ) -> None:
        """Bind the entity to its device and its source."""
        super().__init__(coordinator)
        self._attr_device_info = device
        self._attr_unique_id = f"{device_identifier}:{key}"
        self._attr_name = name
        self._source = source
        self._source_endpoint = source_endpoint
        if suggested_object_id:
            self._attr_suggested_object_id = suggested_object_id

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Where this value comes from (§5.0) plus whatever the subclass adds."""
        attributes: dict[str, Any] = {"source": self._source}
        if self._source_endpoint:
            attributes["source_endpoint"] = self._source_endpoint
        attributes.update(self._extra_attributes())
        return attributes

    def _extra_attributes(self) -> dict[str, Any]:
        """Attributes on top of the source. Overridden where there are any."""
        return {}


class RensonChannelEntity(RensonEntity):
    """An entity that hangs on a physical channel of a module.

    The attributes carry the story of the wiring: what kind of contact it is,
    what may be connected to it, and how sure the function label is. They are
    for the person standing at the fuse box with a screwdriver — which is why
    `module` comes from the static channel table and never from
    `get_output_configurations`, whose module field would say "Brain, open
    collector" for a relay that physically sits in the HVAC module (§4.4).
    """

    def __init__(
        self,
        coordinator: RensonCoordinator,
        device: DeviceInfo,
        device_identifier: str,
        channel: HvacChannel,
        module_model: str,
        module_address: str,
        source: str,
        source_endpoint: str | None = None,
        device_slug: str = "",
    ) -> None:
        """Bind the entity to one channel of one module."""
        super().__init__(
            coordinator,
            device,
            device_identifier,
            channel.key,
            channel.default_name,
            source,
            source_endpoint,
            suggested_object_id=(
                f"{device_slug}_{channel.channel.lower()}" if device_slug else None
            ),
        )
        self._channel = channel
        self._module_model = module_model
        self._module_address = module_address
        if channel.device_class:
            self._attr_device_class = channel.device_class

    @property
    def function_confidence(self) -> str:
        """How sure the function label is.

        The state comes from the gateway but the meaning comes from
        `hvac_config`. Lose the app and the channel keeps reporting while the
        function label falls back to unknown — exactly what §4.3 is for.
        """
        if self._channel.hvac_config_key is None:
            return CONFIDENCE_UNKNOWN
        return CONFIDENCE_CONFIRMED

    def _extra_attributes(self) -> dict[str, Any]:
        channel = self._channel
        attributes: dict[str, Any] = {
            "channel": channel.channel,
            "direction": channel.direction,
            "channel_type": channel.channel_type,
            "electrical": channel.electrical,
            "connector": channel.connector,
            "module": self._module_model,
            "module_address": self._module_address,
            "signal_range": channel.signal_range,
            "wired": channel.wired,
            "function_confidence": self.function_confidence,
        }
        if channel.shared_supply:
            attributes["shared_supply"] = channel.shared_supply
        if channel.direction == "output":
            attributes["interlock_note"] = INTERLOCK_NOTE
        if channel.note:
            attributes["note"] = channel.note
        return attributes


class GatewayEntity(RensonEntity):
    """An entity fed by the gateway itself — independent of every app (§5.2)."""

    def __init__(
        self,
        coordinator: RensonCoordinator,
        device: DeviceInfo,
        device_identifier: str,
        key: str,
        name: str,
        endpoint: str,
    ) -> None:
        """Bind the entity to a gateway endpoint."""
        super().__init__(
            coordinator,
            device,
            device_identifier,
            key,
            name,
            SOURCE_GATEWAY_CORE,
            endpoint,
        )
