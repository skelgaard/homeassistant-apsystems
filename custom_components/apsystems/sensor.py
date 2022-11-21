import logging
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.sun import get_astral_event_date
from homeassistant.util.dt import utcnow as dt_utcnow, as_local
import voluptuous as vol
import requests
import asyncio
from requests.adapters import HTTPAdapter
from datetime import datetime, timedelta, date
import time
import mechanize

CONF_AUTH_ID = 'authId'
CONF_SYSTEM_ID = 'systemId'
CONF_ECU_ID = 'ecuId'
CONF_NAME = 'name'
CONF_SUNSET = 'sunset'

SENSOR_ENERGY_DAY = 'energy_day'
SENSOR_ENERGY_LATEST = 'energy_latest'
SENSOR_ENERGY_TOTAL = 'energy_total'
SENSOR_POWER_MAX = 'power_max_day'
SENSOR_POWER_LATEST = 'power_latest'
SENSOR_TIME = 'date'

EXTRA_TIMESTAMP = 'timestamp'

from homeassistant.const import (
    CONF_NAME, SUN_EVENT_SUNRISE, SUN_EVENT_SUNSET, STATE_UNAVAILABLE, ENERGY_KILO_WATT_HOUR, POWER_WATT, TIME_MILLISECONDS
    )

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_AUTH_ID): cv.string,
    vol.Required(CONF_SYSTEM_ID): cv.string,
    vol.Required(CONF_ECU_ID): cv.string,
    vol.Optional(CONF_NAME, default='APsystems'): cv.string,
    vol.Optional(CONF_SUNSET, default='off'): cv.string
})

# Key: ['json_key', 'unit', 'icon']
SENSORS = {
    SENSOR_ENERGY_DAY:  ['total', ENERGY_KILO_WATT_HOUR, 'mdi:solar-power'],
    SENSOR_ENERGY_LATEST: ['energy', ENERGY_KILO_WATT_HOUR, 'mdi:solar-power'],
    SENSOR_POWER_MAX:     ['max', POWER_WATT, 'mdi:solar-power'],
    SENSOR_POWER_LATEST:  ['power', POWER_WATT, 'mdi:solar-power'],
    SENSOR_TIME:  ['time', "", 'mdi:clock-outline']
}

SCAN_INTERVAL = timedelta(minutes=5)
_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    auth_id = config[CONF_AUTH_ID]
    system_id = config[CONF_SYSTEM_ID]
    ecu_id = config[CONF_ECU_ID]
    sunset = config[CONF_SUNSET]

    #data fetcher
    fetcher = APsystemsFetcher(hass, auth_id, system_id, ecu_id)

    sensors = []
    for type in SENSORS:
        metadata = SENSORS[type]
        sensor_name = config.get(CONF_NAME).lower() + "_" + type
        sensor = ApsystemsSensor(sensor_name, auth_id, system_id, sunset, fetcher, metadata)
        sensors.append(sensor)

    async_add_entities(sensors, True)

class ApsystemsSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, sensor_name, auth_id, system_id, sunset, fetcher, metadata):
        """Initialize the sensor."""
        self._state = None
        self._name = sensor_name
        self._auth_id = auth_id
        self._system_id = system_id
        self._sunset = sunset
        self._fetcher = fetcher
        self._metadata = metadata
        self._attributes = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

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
        return self._metadata[1]

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._metadata[2]

    @property
    def available(self, utc_now=None):
        _LOGGER.debug("Sunset variable: "+self._sunset)

        if self._sunset == 'False':
            _LOGGER.debug("Sensor is running. Sunset is disabled")
            return True

        if utc_now is None:
            utc_now = dt_utcnow()
        now = as_local(utc_now)

        start_time = self.find_start_time(now)
        stop_time = self.find_stop_time(now)

        if as_local(start_time) <= now <= as_local(stop_time):
            _LOGGER.debug("Sensor is running. Start/Stop time: {}, {}".format(as_local(start_time), as_local(stop_time)))
            return True
        else:
            _LOGGER.debug("Sensor is not running. Start/Stop time: {}, {}".format(as_local(start_time), as_local(stop_time)))
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

        offset_hours = 7 * 60 * 60 * 1000  # to move apsystems timestamp to UTC

        #get timestamp
        index_time = SENSORS[SENSOR_TIME][0]
        timestamp = ap_data[index_time][-1]

        if value == timestamp:  # current attribute is the timestamp, so fix it
            value = int(value) + offset_hours
            value = datetime.fromtimestamp(value / 1000)
        timestamp = int(timestamp) + offset_hours

        self._attributes[EXTRA_TIMESTAMP] = timestamp

        _LOGGER.debug(value)
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
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:52.0) Chrome/50.0.2661.102 Firefox/62.0'}
    cache = None
    cache_timestamp = None
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

            #TODO should this not have offset too on it ?
            post_data = {'queryDate': datetime.today().strftime("%Y%m%d"),
                      'selectedValue': self._ecu_id,
                      'systemId': self._system_id}

            _LOGGER.debug('post_data:')
            _LOGGER.debug(post_data)

            s = requests.session()
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            _LOGGER.debug('starting: ' + now)
            result_data = await self._hass.async_add_executor_job(
             s.request, "POST", self.url_data, None, post_data, self.headers, browser.cookies.get_dict()
            )

            _LOGGER.debug("status code data: " + str(result_data.status_code))

            if result_data.status_code == 204:
                self.cache = None
            else:
                self.cache = result_data.json()

            self.cache_timestamp = int(round(time.time() * 1000))
        finally:
            self.running = False

    async def data(self):
        while self.running is True:
            await asyncio.sleep(1)

        if self.cache is None:
            await self.run()

        # continue None after run(), there is no data for this day
        #if self.cache is None:
        #    return self.cache

        # rules to check cache
        offset_hours = 7 * 60 * 60 * 1000
        timestamp_event = int(self.cache['time'][-1]) + offset_hours  # apsystems have 8h delayed in timestamp from UTC
        timestamp_now = int(round(time.time() * 1000))
        cache_time = 6 * 60 * 1000  # 6 minutes
        request_time = 20 * 1000  # 20 seconds to avoid request what is already requested

        if (timestamp_now - timestamp_event > cache_time) and (timestamp_now - self.cache_timestamp > request_time):
            await self.run()

        return self.cache
