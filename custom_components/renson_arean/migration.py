"""Migration from 2026.6.0 to the 2026.9.0 conventions (§11).

The migration gets one shot: if it fails halfway the user is left with a
half-converted registry. So the whole mapping is computed first and only then
applied, every step is logged with its old and new value, and an unknown
unique_id is left strictly alone — never removed on a hunch.

It runs in two parts. What does not need the gateway happens in
`async_migrate_entry`; the output entities need the HVAC module's bus address
and are therefore converted at setup, once the topology has been read.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import (
    CONFIG_ENTRY_VERSION,
    CONF_MODBUS_SLAVE_LEGACY,
    CONF_THERMOSTAT_SLAVE,
    DOMAIN,
    brain_id,
    legacy_target,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Set on the entry once the output entities have been converted, so the second
# part runs exactly once.
MIGRATED_OUTPUTS = "migrated_outputs"


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate the config entry itself, its device and its app entities."""
    if entry.version >= CONFIG_ENTRY_VERSION:
        return True

    _LOGGER.info("migratie van config entry %s naar versie 2", entry.entry_id)

    options = dict(entry.options)
    if CONF_MODBUS_SLAVE_LEGACY in options:
        options[CONF_THERMOSTAT_SLAVE] = options.pop(CONF_MODBUS_SLAVE_LEGACY)
        _LOGGER.info(
            "optie %s hernoemd naar %s",
            CONF_MODBUS_SLAVE_LEGACY,
            CONF_THERMOSTAT_SLAVE,
        )

    # 2026.6.0 set the entry unique_id to the empty string, which made a second
    # gateway impossible to add. There is no stable hardware id to replace it
    # with, so the entry gets none at all (§4.1).
    hass.config_entries.async_update_entry(
        entry, options=options, unique_id=None, version=CONFIG_ENTRY_VERSION
    )

    _migrate_device(hass, entry)
    _migrate_entities(hass, entry, hvac_address=None)
    return True


async def async_migrate_outputs(
    hass: HomeAssistant, entry: ConfigEntry, hvac_address: str
) -> None:
    """Convert the output entities, now that the module address is known."""
    if entry.data.get(MIGRATED_OUTPUTS):
        return
    _migrate_entities(hass, entry, hvac_address=hvac_address)
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, MIGRATED_OUTPUTS: True}
    )


def _migrate_device(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Turn the old single device into the Brain module.

    The identifier is changed rather than a new device created, so the user's
    own area, labels and dashboard references survive (§11.3 step 3).
    """
    registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(registry, entry.entry_id):
        old = {i for i in device.identifiers if i[0] == DOMAIN}
        new_identifier = (DOMAIN, brain_id(entry.entry_id))
        if not old or new_identifier in old:
            continue
        _LOGGER.info("device %s wordt %s", old, new_identifier)
        registry.async_update_device(
            device.id,
            new_identifiers={new_identifier},
            name="Brain module",
        )


def _migrate_entities(
    hass: HomeAssistant, entry: ConfigEntry, hvac_address: str | None
) -> None:
    """Apply the unique_id mapping, computing it in full before touching anything."""
    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)

    planned: list[tuple[str, str, str]] = []
    taken = {(e.domain, e.platform, e.unique_id) for e in entities}
    for entity in entities:
        target = legacy_target(entity.unique_id, entry.entry_id, hvac_address)
        if target is None or target == entity.unique_id:
            continue
        if (entity.domain, entity.platform, target) in taken:
            _LOGGER.warning(
                "overgeslagen: %s zou %s worden, maar die unique_id bestaat al",
                entity.entity_id,
                target,
            )
            continue
        planned.append((entity.entity_id, entity.unique_id, target))

    for entity_id, old, new in planned:
        _LOGGER.info("%s: unique_id %s wordt %s", entity_id, old, new)
        registry.async_update_entity(entity_id, new_unique_id=new)
