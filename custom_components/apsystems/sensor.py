from __future__ import annotations

import asyncio
import logging
import time
from datetime import date, datetime, timedelta
from typing import Any, Dict, NamedTuple, Optional

import homeassistant.helpers.config_validation as cv
import requests
import voluptuous as vol  # type: ignore
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
     SensorEntity,
    SensorDeviceClass,
    )
from homeassistant.const import (
    CONF_NAME,
    STATE_UNAVAILABLE,
    SUN_EVENT_SUNRISE,
    SUN_EVENT_SUNSET,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.helpers.sun import get_astral_event_date
from homeassistant.util.dt import as_local
from homeassistant.util.dt import utcnow as dt_utcnow

CONF_AUTH_ID = "authId"
CONF_ECU_ID = "ecuId"
CONF_SUNSET = "sunset"
CONF_SYSTEM_ID = "systemId"

EXTRA_TIMESTAMP = "timestamp"
SENSOR_ENERGY_DAY = "energy_day"
SENSOR_ENERGY_LATEST = "energy_latest"
SENSOR_ENERGY_TOTAL = "energy_total"
SENSOR_POWER_LATEST = "power_latest"
SENSOR_POWER_MAX = "power_max_day"
SENSOR_TIME = "date"

# to move apsystems timestamp to UTC
OFFSET_MS = (
    timedelta(hours=7).total_seconds() / timedelta(milliseconds=1).total_seconds()
)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_AUTH_ID): cv.string,
        vol.Required(CONF_SYSTEM_ID): cv.string,
        vol.Required(CONF_ECU_ID): cv.string,
        vol.Optional(CONF_NAME, default="APsystems"): cv.string,
        vol.Optional(CONF_SUNSET, default="off"): cv.string,
    }
)


class ApsMetadata(NamedTuple):
    json_key: str
    icon: str
    unit: str = ""
    state_class: Optional[str] = None


SENSORS = {
    SENSOR_ENERGY_DAY: ApsMetadata(
        json_key="total",
        unit=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:solar-power",
        state_class="total_increasing",
    ),
    SENSOR_ENERGY_LATEST: ApsMetadata(
        json_key="energy",
        unit=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:solar-power",
    ),
    SENSOR_POWER_MAX: ApsMetadata(
        json_key="max",
        unit=UnitOfPower.WATT,
        icon="mdi:solar-power",
    ),
    SENSOR_POWER_LATEST: ApsMetadata(
        json_key="power",
        unit=UnitOfPower.WATT,
        icon="mdi:solar-power",
    ),
    SENSOR_TIME: ApsMetadata(
        json_key="time",
        icon="mdi:clock-outline",
    ),
}

SCAN_INTERVAL = timedelta(minutes=1)
_LOGGER = logging.getLogger(__name__)

DOMAIN = "apsystems"

offset_hours = (8 * 60 * 60 * 1000) - (time.localtime().tm_gmtoff * 1000)
_LOGGER.debug("Offset set to : "+ str(offset_hours/(60*60*1000)) + " hours")

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    auth_id = config[CONF_AUTH_ID]
    system_id = config[CONF_SYSTEM_ID]
    ecu_id = config[CONF_ECU_ID]
    sunset = config[CONF_SUNSET]

    #data fetcher
    fetcher = APsystemsFetcher(hass, auth_id, system_id, ecu_id)

    sensors = []
    for type, metadata in SENSORS.items():
        sensor_name = config.get(CONF_NAME).lower() + "_" + type
        sensor = ApsystemsSensor(
            sensor_name, auth_id, system_id, sunset, fetcher, metadata
        )
        sensors.append(sensor)

    async_add_entities(sensors, True)


class ApsystemsSensor(SensorEntity):
    """Representation of a Sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY

    def __init__(
        self,
        sensor_name: str,
        auth_id: str,
        system_id: str,
        sunset: str,
        fetcher: APsystemsFetcher,
        metadata: ApsMetadata,
    ):
        """Initialize the sensor."""
        self._state = None
        self._name = sensor_name
        self._auth_id = auth_id
        self._system_id = system_id
        self._sunset = sunset
        self._fetcher = fetcher
        self._metadata = metadata
        self._attributes: Dict[str, Any] = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state_class(self):
        """Return the state_class of the sensor."""
        return self._metadata.state_class

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def state_attributes(self):
        """Return the device state attributes."""
        return self._attributes

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._metadata.unit

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._metadata.icon

    @property
    def available(self, utc_now=None):
        _LOGGER.debug(f"Sunset variable: {self._sunset=}")

        if self._sunset == 'False':
            _LOGGER.debug("Sensor is running. Sunset is disabled")
            return True

        if utc_now is None:
            utc_now = dt_utcnow()
        now = as_local(utc_now)

        start_time = self.find_start_time(now)
        stop_time = self.find_stop_time(now)

        if as_local(start_time) <= now <= as_local(stop_time):
            _LOGGER.debug(
                "Sensor is running. Start/Stop time: "
                f"{as_local(start_time)}, {as_local(stop_time)}"
            )
            return True
        else:
            _LOGGER.debug(
                "Sensor is not running. Start/Stop time: "
                f"{as_local(start_time)}, {as_local(stop_time)}"
            )
            return False

    async def async_update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        if not self.available:
            self._state = STATE_UNAVAILABLE
            return

        ap_data = await self._fetcher.data()

        # state is not available
        if ap_data is None:
            self._state = STATE_UNAVAILABLE
            return
        index = self._metadata[0]
        value = ap_data[index]
        if isinstance(value, list):
            value = value[-1]

        #get timestamp
        index_time = SENSORS[SENSOR_TIME][0]
        timestamp = ap_data[index_time][-1]

        if value == timestamp:  # current attribute is the timestamp, so fix it
            value = int(value) + offset_hours
            value = datetime.fromtimestamp(value / 1000)
        timestamp = int(timestamp) + offset_hours

        self._attributes[EXTRA_TIMESTAMP] = timestamp

        _LOGGER.debug(self._name +':'+str(value))
        self._state = value

    def find_start_time(self, now):
        """Return sunrise or start_time if given."""
        sunrise = get_astral_event_date(self.hass, SUN_EVENT_SUNRISE, now.date())
        return sunrise

    def find_stop_time(self, now):
        """Return sunset or stop_time if given."""
        sunset = get_astral_event_date(self.hass, SUN_EVENT_SUNSET, now.date())
        return sunset


class APsystemsFetcher:
    url_login = "https://www.apsystemsema.com/ema/intoDemoUser.action?id="
    url_data = "https://www.apsystemsema.com/ema/ajax/getReportApiAjax/getPowerOnCurrentDayAjax"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:52.0) Chrome/50.0.2661.102 Firefox/62.0"
    }
    cache: Optional[Dict[Any, Any]] = None
    cache_timestamp: Optional[int] = None
    running = False

    def __init__(self, hass, auth_id, system_id, ecu_id):
        self._hass = hass
        self._auth_id = auth_id
        self._system_id = system_id
        self._ecu_id = ecu_id
        self._today = datetime.fromisoformat(date.today().isoformat())

    async def login(self):
        s = requests.Session()

        r = await self._hass.async_add_executor_job(
            s.request, "GET", self.url_login + self._auth_id, None, None, self.headers
        )
        return s

    async def run(self):
        self.running = True
        try:
            browser = await self.login()

            #OLD version datetime.today().strftime("%Y%m%d")
            post_data = {'queryDate': (datetime.now() - timedelta(seconds=(offset_hours/1000))).strftime("%Y%m%d"),
                      'selectedValue': self._ecu_id,
                      'systemId': self._system_id}

            _LOGGER.debug('post_data:')
            _LOGGER.debug(post_data)

            s = requests.session()
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            _LOGGER.debug('starting: ' + now)
            result_data = await self._hass.async_add_executor_job(
                s.request,
                "POST",
                self.url_data,
                None,
                post_data,
                self.headers,
                browser.cookies.get_dict(),
            )

            _LOGGER.debug("status code data: " + str(result_data.status_code))

            if result_data.status_code == 204:
                self.cache = None
            else:
                self.cache = result_data.json()
            _LOGGER.debug(self.cache)

            self.cache_timestamp = int(round(time.time() * 1000))
        finally:
            self.running = False

    async def data(self):
        while self.running is True:
            await asyncio.sleep(1)

        if self.cache is None:
            await self.run()

        # continue None after run(), there is no data for this day
        if self.cache is None:
            _LOGGER.debug('No data')
            return self.cache
        else:
            # rules to check cache
            timestamp_event = int(self.cache['time'][-1]) + offset_hours  # apsystems have 8h delayed in timestamp from UTC
            timestamp_now = int(round(time.time() * 1000))
            cache_time = (5 * 60 * 1000) - (10 *1000)  # 4:50 minutes
            request_time = 60 * 1000  # 60 seconds to avoid request what is already requested
            _LOGGER.debug("timestamp_now " + str(timestamp_now))
            _LOGGER.debug("timestamp_event " + str(timestamp_event))
            _LOGGER.debug("timediff " + str(timestamp_now - timestamp_event))
            _LOGGER.debug("cache_time " + str(cache_time))
            _LOGGER.debug("self.cache_timestamp " + str(self.cache_timestamp))
            _LOGGER.debug("timediff " + str(timestamp_now - self.cache_timestamp))
            _LOGGER.debug("request_time " + str(request_time))

            if (timestamp_now - timestamp_event > cache_time) and (timestamp_now - self.cache_timestamp > request_time):
                await self.run()

        return self.cache
