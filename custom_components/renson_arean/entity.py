"""Base entities.

Two things live here that §4.3 and §5.0 insist on:

* identity is physical and the label is functional — the unique_id and the
  entity_id follow the datapoint, the display name follows the function, and
  the user's own name always wins;
* an entity is unavailable as soon as its source is, and never quietly borrows
  a value from another source or freezes on the last known one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import (
    CONFIDENCE_CONFIRMED,
    CONFIDENCE_UNKNOWN,
    INTERLOCK_NOTE,
    SOURCE_GATEWAY_CORE,
)

if TYPE_CHECKING:
    from homeassistant.helpers.device_registry import DeviceInfo

    from .const import HvacChannel, Origin
    from .coordinators import RensonCoordinator


def entity_id_for(domain: str, origin: Origin, key: str) -> str:
    """The entity_id `RensonEntity` registers for one datapoint.

    Exported so the channel overview can advertise the real ids rather than
    rebuild them from a rule that would drift apart from this one (§4.3).

    A key that merely repeats the platform adds nothing, so the primary entity
    of a device becomes `climate.thermostat_0` and not
    `climate.thermostat_0_climate`.
    """
    suffix = "" if key == domain else f"_{key}"
    return f"{domain}.{slugify(origin.slug + suffix)}"


class RensonEntity(CoordinatorEntity):
    """Every entity of this integration.

    Identity comes from the `Origin` — what the datapoint *is* — and never from
    the device it is displayed on, so re-parenting an entity costs nothing
    (§4.3). `device` therefore only decides where it shows up.

    The entity_id is set here rather than left to Home Assistant. That is the
    one mechanism that decouples it from the display name: `entity_platform`
    honours an entity_id an entity has set itself, and only falls back to
    "<device name> <entity name>" when it has not. The `suggested_object_id`
    property is no use for this — it is read-only in core and returns the name.
    Whether the entity_id is free is still checked by the registry, so a
    collision cannot silently overwrite anything.
    """

    _attr_has_entity_name = True

    # Set by each platform's base class; without it Home Assistant generates
    # the entity_id from the display name, which is what §4.3 avoids.
    _entity_domain: str = ""

    def __init__(
        self,
        coordinator: RensonCoordinator,
        device: DeviceInfo,
        origin: Origin,
        key: str,
        name: str | None,
        source: str,
        source_endpoint: str | None = None,
    ) -> None:
        """Bind the entity to its datapoint, its device and its source."""
        super().__init__(coordinator)
        self._attr_device_info = device
        self._attr_unique_id = f"{origin.uid}:{key}"
        self._attr_name = name
        self._source = source
        self._source_endpoint = source_endpoint
        if self._entity_domain:
            self.entity_id = entity_id_for(self._entity_domain, origin, key)

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
        origin: Origin,
        channel: HvacChannel,
        module_model: str,
        module_address: str,
        source: str,
        source_endpoint: str | None = None,
    ) -> None:
        """Bind the entity to one channel of one module."""
        super().__init__(
            coordinator,
            device,
            origin,
            channel.key,
            channel.default_name,
            source,
            source_endpoint,
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
        origin: Origin,
        key: str,
        name: str,
        endpoint: str,
    ) -> None:
        """Bind the entity to a gateway endpoint."""
        super().__init__(
            coordinator,
            device,
            origin,
            key,
            name,
            SOURCE_GATEWAY_CORE,
            endpoint,
        )
