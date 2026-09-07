"""Config and options flow.

The config entry deliberately gets **no** unique_id. Home Assistant uses it to
stop the same device being added twice, and that wants a stable hardware id —
never an IP address (HA ADR-0010). This gateway has no such id (V-17), and
2026.6.0's `async_set_unique_id(serial)` therefore set every installation to
the same empty string, which made adding a second gateway impossible. Instead
the flow warns when a host is already configured, which is weaker but honest
about what the hardware allows (§4.1).
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api.client import RensonAuthError, RensonClient, RensonError
from .const import (
    CONF_HOST,
    CONF_INTERVAL_CONFIG,
    CONF_INTERVAL_STATE,
    CONF_INTERVAL_THERMOSTAT,
    CONF_INTERVAL_TOPOLOGY,
    CONF_PASSWORD,
    CONF_THERMOSTAT_CONNECTED_TO,
    CONF_THERMOSTAT_SLAVE,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    CONFIG_ENTRY_VERSION,
    CONNECTED_TO_BRAIN,
    CONNECTED_TO_HVAC,
    DEFAULT_CONNECTED_TO,
    DEFAULT_INTERVAL_CONFIG,
    DEFAULT_INTERVAL_STATE,
    DEFAULT_INTERVAL_THERMOSTAT,
    DEFAULT_INTERVAL_TOPOLOGY,
    DEFAULT_THERMOSTAT_SLAVE,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    MIN_INTERVAL_CONFIG,
    MIN_INTERVAL_STATE,
    MIN_INTERVAL_THERMOSTAT,
    MIN_INTERVAL_TOPOLOGY,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def _validate(hass, host: str, username: str, password: str) -> None:
    """Try the credentials once. Raises RensonAuthError or RensonError."""
    session = async_create_clientsession(hass, verify_ssl=False)
    client = RensonClient(session, host, username, password)
    await client.login()
    await client.get_version()


class RensonConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a gateway."""

    VERSION = CONFIG_ENTRY_VERSION

    def __init__(self) -> None:
        """Start with no reauth entry."""
        self._reauth_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for host and credentials."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            try:
                await _validate(
                    self.hass, host, user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
            except RensonAuthError:
                errors["base"] = "invalid_auth"
            except RensonError:
                errors["base"] = "cannot_connect"
            else:
                if any(
                    entry.data.get(CONF_HOST) == host
                    for entry in self._async_current_entries()
                ):
                    errors["base"] = "host_already_configured"
                else:
                    return self.async_create_entry(
                        title=f"Renson Smart Living (lokaal) — {host}",
                        data=user_input,
                    )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """The gateway rejected the stored credentials."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the credentials again."""
        errors: dict[str, str] = {}
        entry = self._reauth_entry
        if user_input is not None and entry is not None:
            try:
                await _validate(
                    self.hass,
                    entry.data[CONF_HOST],
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except RensonAuthError:
                errors["base"] = "invalid_auth"
            except RensonError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry, data={**entry.data, **user_input}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> RensonOptionsFlow:
        """Return the options flow."""
        return RensonOptionsFlow()


class RensonOptionsFlow(OptionsFlow):
    """Connection settings and the per-source intervals of §6.2.

    These are settings of the integration, not of a device, so they live here
    and not as `number` or `select` entities (P-03).
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_VERIFY_SSL,
                    default=options.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
                ): bool,
                vol.Optional(
                    CONF_THERMOSTAT_SLAVE,
                    default=options.get(
                        CONF_THERMOSTAT_SLAVE, DEFAULT_THERMOSTAT_SLAVE
                    ),
                ): vol.All(int, vol.Range(min=1, max=247)),
                vol.Optional(
                    CONF_THERMOSTAT_CONNECTED_TO,
                    default=options.get(
                        CONF_THERMOSTAT_CONNECTED_TO, DEFAULT_CONNECTED_TO
                    ),
                ): vol.In([CONNECTED_TO_BRAIN, CONNECTED_TO_HVAC]),
                vol.Optional(
                    CONF_INTERVAL_THERMOSTAT,
                    default=options.get(
                        CONF_INTERVAL_THERMOSTAT,
                        int(DEFAULT_INTERVAL_THERMOSTAT.total_seconds()),
                    ),
                ): vol.All(int, vol.Range(min=MIN_INTERVAL_THERMOSTAT)),
                vol.Optional(
                    CONF_INTERVAL_STATE,
                    default=options.get(
                        CONF_INTERVAL_STATE,
                        int(DEFAULT_INTERVAL_STATE.total_seconds()),
                    ),
                ): vol.All(int, vol.Range(min=MIN_INTERVAL_STATE)),
                vol.Optional(
                    CONF_INTERVAL_CONFIG,
                    default=options.get(
                        CONF_INTERVAL_CONFIG,
                        int(DEFAULT_INTERVAL_CONFIG.total_seconds()),
                    ),
                ): vol.All(int, vol.Range(min=MIN_INTERVAL_CONFIG)),
                vol.Optional(
                    CONF_INTERVAL_TOPOLOGY,
                    default=options.get(
                        CONF_INTERVAL_TOPOLOGY,
                        int(DEFAULT_INTERVAL_TOPOLOGY.total_seconds()),
                    ),
                ): vol.All(int, vol.Range(min=MIN_INTERVAL_TOPOLOGY)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
