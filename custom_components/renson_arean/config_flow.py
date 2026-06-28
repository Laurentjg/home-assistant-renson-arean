"""Config flow for the Renson Arean integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .api import RensonApiClient, RensonAuthError, RensonConnectionError
from .const import (
    CONF_HOST,
    CONF_MODBUS_SLAVE,
    CONF_PASSWORD,
    CONF_USERNAME,
    DEFAULT_MODBUS_SLAVE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def _validate_connection(host: str, username: str, password: str) -> str:
    """Try to connect and return the gateway serial number."""
    api = RensonApiClient(host, username, password)
    try:
        serial = await api.get_gateway_serial()
    finally:
        await api.close()
    return serial


class RensonAreanConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Renson Arean."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlowHandler:
        """Return the options flow handler."""
        return OptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial user step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                serial = await _validate_connection(
                    user_input[CONF_HOST],
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except RensonAuthError:
                errors["base"] = "invalid_auth"
            except RensonConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during config flow")
                errors["base"] = "unknown"
            else:
                # Use the gateway serial as unique ID — never the IP address (HA ADR-0010)
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: user_input[CONF_HOST]}
                )
                return self.async_create_entry(
                    title=f"Renson Arean ({user_input[CONF_HOST]})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication after token expiry or credential change."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show reauth form — only asks for password, not the full setup again."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            try:
                await _validate_connection(
                    reauth_entry.data[CONF_HOST],
                    reauth_entry.data[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except RensonAuthError:
                errors["base"] = "invalid_auth"
            except RensonConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during reauth")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class OptionsFlowHandler(OptionsFlow):
    """Handle Renson Arean options (accessible via the Configure button)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the options form."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current_slave: int = self.config_entry.options.get(
            CONF_MODBUS_SLAVE, DEFAULT_MODBUS_SLAVE
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MODBUS_SLAVE, default=current_slave): vol.All(
                        NumberSelector(
                            NumberSelectorConfig(min=1, max=247, step=1, mode=NumberSelectorMode.BOX)
                        ),
                        vol.Coerce(int),
                    ),
                }
            ),
        )
