""" The Config Flow """
import logging
from typing import Any, List
import copy
from collections.abc import Mapping

from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.config_entries import ConfigFlow, OptionsFlow, ConfigEntry
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from .const import *


_LOGGER = logging.getLogger(__name__)

_USER_FORM = vol.Schema({
    vol.Required(CONF_AUTH_ID): cv.string,
    vol.Required(CONF_SYSTEM_ID): cv.string,
    vol.Optional(CONF_ECU_ID): cv.string,
    vol.Optional(CONF_VIEW_ID): cv.string,
    vol.Optional(CONF_NAME, default="APsystems"): cv.string,
    vol.Optional(CONF_PANELS, default=[]): selector.TextSelector(selector.TextSelectorConfig(multiple=True)),
})


def ensure_list_validator(values: str) -> List:
    if not all(value.strip() for value in values.split(",")):
        raise vol.Invalid(
            "Values must be separated by coma and not to be empty.")
    return values.split(",")


def add_suggested_values_to_schema(
    data_schema: vol.Schema, suggested_values: Mapping[str, Any]
) -> vol.Schema:
    """Make a copy of the schema, populated with suggested values.

    For each schema marker matching items in `suggested_values`,
    the `suggested_value` will be set. The existing `suggested_value` will
    be left untouched if there is no matching item.
    """
    schema = {}
    for key, val in data_schema.schema.items():
        new_key = key
        if key in suggested_values and isinstance(key, vol.Marker):
            # Copy the marker to not modify the flow schema
            new_key = copy.copy(key)
            new_key.description = {"suggested_value": suggested_values[key]}
        schema[new_key] = val
    _LOGGER.debug("add_suggested_values_to_schema: schema=%s", schema)
    return vol.Schema(schema)


class ApSystemsConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        """Get options flow for this handler"""
        return ApSystemsOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict | None = None):
        if user_input is not None:
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self.async_show_form(step_id="user", data_schema=_USER_FORM)


class ApSystemsOptionsFlow(OptionsFlow):
    """La classe qui implémente le option flow pour notre DOMAIN.
    Elle doit dériver de OptionsFlow"""

    _user_inputs: dict = {}
    # Pour mémoriser la config en cours
    config_entry: ConfigEntry = None

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialisation de l'option flow. On a le ConfigEntry existant en entrée"""
        self.config_entry = config_entry
        # On initialise les user_inputs avec les données du configEntry
        self._user_inputs = config_entry.data.copy()

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        """Gestion de l'étape 'user'. Point d'entrée de notre
        optionsFlow. Comme pour le ConfigFlow, cette méthode est appelée 2 fois
        """
        if user_input is None:
            return self.async_show_form(
                step_id="init",
                data_schema=add_suggested_values_to_schema(
                    data_schema=_USER_FORM, suggested_values=self._user_inputs
                ),
            )

        self._user_inputs.update(user_input)
        return await self.async_end()

    async def async_end(self):
        """Finalization of the ConfigEntry creation"""
        _LOGGER.info(
            "Recreation de l'entry %s. La nouvelle config est maintenant : %s",
            self.config_entry.entry_id,
            self._user_inputs,
        )
        # Modification des data de la configEntry
        # (et non pas ajout d'un objet options dans la configEntry)
        self.hass.config_entries.async_update_entry(
            self.config_entry, data=self._user_inputs
        )
        # Suppression de l'objet options dans la configEntry
        return self.async_create_entry(title=None, data=None)
