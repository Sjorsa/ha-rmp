from typing import Any
from homeassistant import config_entries
from . import DOMAIN
import voluptuous as vol

class RaphsonPlaybackServerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Example config flow."""
    # The schema version of the entries that it creates
    # Home Assistant will call your migrate method if the version changes
    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            # TODO check if connection works before adding it
            unique_id = user_input['host'] + ':' + str(user_input['port'])
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=unique_id, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema({vol.Required("host", default='localhost'): str,
                                                    vol.Required("port", default=8181): int})
        )