from __future__ import annotations

from .logger import get_logger
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from .const import *

import requests
import voluptuous as vol  # type: ignore
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, STATE_UNAVAILABLE, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util.dt import as_local
from homeassistant.util.dt import utcnow as dt_utcnow



_LOGGER = get_logger(__name__)

@dataclass(kw_only=True)
class ApsystemsSensorEntityDescription(SensorEntityDescription):
    json_key: str


SENSORS: List[ApsystemsSensorEntityDescription] = [
    # "https://www.apsystemsema.com/ema/ajax/getReportApiAjax/getPowerOnCurrentDayAjax"
     ApsystemsSensorEntityDescription(
        key=SENSOR_ENERGY_LATEST,
        json_key="energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:solar-power",
        device_class="energy",
        state_class="measurement",
    ),
    ApsystemsSensorEntityDescription(
        key=SENSOR_POWER_MAX,
        json_key="max",
        native_unit_of_measurement=UnitOfPower.WATT,
        icon="mdi:solar-power",
        device_class="power",
        state_class="measurement",
    ),
    ApsystemsSensorEntityDescription(
        key=SENSOR_POWER_LATEST,
        json_key="power",
        native_unit_of_measurement=UnitOfPower.WATT,
        icon="mdi:solar-power",
        device_class="power",
        state_class="measurement",
    ),
    ApsystemsSensorEntityDescription(
        key=SENSOR_POWER_LIFETIME,
        json_key="lifetime",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:solar-power",
        device_class="energy",
        state_class="total_increasing",
    ),
    ApsystemsSensorEntityDescription(
        key=SENSOR_ENERGY_DAY,
        json_key="total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:solar-power",
        device_class="energy",
        state_class="total_increasing",
    ),
    ApsystemsSensorEntityDescription(
        key="co2_tons",
        json_key="co2",
        native_unit_of_measurement="kg",
        icon="mdi:molecule-co2",
        device_class=None,  # no built-in CO₂ mass device class
        state_class="total_increasing",
    ),
]

SCAN_INTERVAL = timedelta(minutes=1)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    auth_id = entry.data[CONF_AUTH_ID]
    system_id = entry.data[CONF_SYSTEM_ID]
    ecu_id = entry.data[CONF_ECU_ID]
    view_id = entry.data[CONF_VIEW_ID]
    panels = entry.data[CONF_PANELS]

    sensors = []

    for entity_description in SENSORS:
        sensor = ApsystemsSensor(entity_description, entry)
        sensors.append(sensor)

    for panel in panels:
        entity_description = ApsystemsSensorEntityDescription(
            key=panel,
            json_key=panel,
            native_unit_of_measurement=UnitOfPower.WATT,
            icon="mdi:solar-power",
            device_class="power",
            state_class="measurement",
        )
        sensor = ApsystemsSensor(entity_description, entry)
        sensors.append(sensor)

    # data fetcher
    fetcher = APsystemsFetcher(
        auth_id, system_id, ecu_id, view_id, entry, sensors)

    async_add_entities(sensors + [fetcher], True)


class ApsystemsSensor(SensorEntity):
    """Representation of a Sensor."""

    entity_description: ApsystemsSensorEntityDescription

    def __init__(
            self,
            entity_description: ApsystemsSensorEntityDescription,
            entry_infos
    ):
        self._attr_name = entry_infos.data[CONF_NAME].lower() + "_" + entity_description.key
        self._attr_unique_id = f"{entry_infos.entry_id}_{entity_description.key}"
        self._device_id = entry_infos.entry_id
        self.entity_description = entity_description
        self.native_value = None
        self._attr_available = True
        self._attr_should_poll = False

    # async def async_update(self, ap_data):
    #     pass

    async def set_value(self, ap_data):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        # state is not available
        if ap_data is None:
            self._attr_state = STATE_UNAVAILABLE
            return
        _LOGGER.debug(self.entity_description.json_key)

        try:
            index = self.entity_description.json_key
            value = ap_data[index]
            if isinstance(value, list):
                value = value[-1]
        except (KeyError, IndexError) as e:
            _LOGGER.error(f"{str(e)} missing in post_data")
            return

        _LOGGER.debug(self.name + ':' + str(value))
        self.native_value = value
        self._async_write_ha_state()


class APsystemsFetcher(SensorEntity):
    url_login = "https://www.apsystemsema.com/ema/intoDemoUser.action?id="
    url_datas = (
        "https://www.apsystemsema.com/ema/ajax/getReportApiAjax/getPowerOnCurrentDayAjax"
#        ,"https://www.apsystemsema.com/ema/ajax/getReportApiAjax/getPowerWithAllParameterOnCurrentDayAjax"
        ,"https://www.apsystemsema.com/ema/ajax/getDashboardApiAjax/getDashboardProductionInfoAjax"
    )
    url_data_panel = "https://www.apsystemsema.com/ema/ajax/getViewAjax/getViewPowerByViewAjax"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:52.0) Chrome/50.0.2661.102 Firefox/62.0"
    }
    data: Optional[Dict[Any, Any]] = None

    def __init__(self, auth_id, system_id, ecu_id, view_id, entry_infos, sensors: ApsystemsSensor):
        self._attr_name = entry_infos.data[CONF_NAME].lower() + "_updater"
        self._device_id = entry_infos.entry_id
        self._attr_should_poll = False

        self._auth_id = auth_id
        self._system_id = system_id
        self._ecu_id = ecu_id
        self._view_id = view_id
        self._sensors: List[ApsystemsSensor] = sensors

    async def login(self):
        s = requests.Session()

        r = await self.hass.async_add_executor_job(
            s.request, "GET", self.url_login + self._auth_id, None, None, self.headers
        )
        _LOGGER.debug(s)
        return s

    async def run(self, _):
        try:
            browser = await self.login()
            self.data = {}

            now = datetime.now()

            post_data = {'queryDate': now.strftime("%Y%m%d"),
                         'selectedValue': self._ecu_id,
                         'systemId': self._system_id}

            _LOGGER.debug(f'post_data: {post_data}')

            s = requests.session()
            _LOGGER.debug('starting: ' + now.strftime('%Y-%m-%d %H:%M:%S'))
            for url_data in self.url_datas:
                result_data = await self.hass.async_add_executor_job(
                    s.request,
                    "POST",
                    url_data,
                    None,
                    post_data,
                    self.headers,
                    browser.cookies.get_dict(),
                )

                _LOGGER.debug(f"{url_data} => statuscode: {str(result_data.status_code)}")

                try:
                    if result_data.status_code != 204:
                        self.data.update(result_data.json())
                except Exception as e:
                    _LOGGER.error(f"{str(e)} => self.cache : {self.data}")

            post_data = {'date': now.strftime("%Y%m%d"),
                         'vid': self._view_id,
                         'sid': self._system_id,
                         'iid': ""}

            result_data = await self.hass.async_add_executor_job(
                s.request,
                "POST",
                self.url_data_panel,
                None,
                post_data,
                self.headers,
                browser.cookies.get_dict(),
            )

            _LOGGER.debug(f"{self.url_data_panel} => {str(result_data.status_code)}")

            try:
                if result_data.status_code != 204:
                    json_data = result_data.json()
                    detail = json_data.get("detail")  # returns None if not present
                    if detail:
                        panels = {}
                        for panel in detail.split("&"):
                            name, data = panel.split("/")
                            panels[name] = []
                            for d in data.split(","):
                                panels[name].append(d)
                        self.data.update(panels)

            except Exception as e:
                _LOGGER.error(f"{str(e)} => self.cache : {self.data}")

        except Exception as e:
            _LOGGER.error(f"{str(e)} => self.cache : {self.data}")
        finally:
            self.native_value = as_local(dt_utcnow())
#            _LOGGER.debug(self.data)
            _LOGGER.debug("Keys available: %s", ", ".join(self.data.keys()))
            for sensor in self._sensors:
                await sensor.set_value(self.data)
            self.async_write_ha_state()

    @callback
    async def async_added_to_hass(self):
        await self.run(None)

        timer_cancel = async_track_time_interval(
            self.hass,
            self.run,
            interval=SCAN_INTERVAL,
        )
        self.async_on_remove(timer_cancel)
