from homeassistant.const import Platform

DOMAIN = "apsystems_api"
PLATFORMS: list[Platform] = [Platform.SENSOR]

CONF_AUTH_ID = "authId"
CONF_ECU_ID = "ecuId"
CONF_VIEW_ID = "viewId"
CONF_PANELS = "panels"
CONF_SYSTEM_ID = "systemId"

EXTRA_TIMESTAMP = "timestamp"
SENSOR_IMPORTED_TOTAL = "imported_total"
SENSOR_ENERGY_LATEST = "energy_latest"
SENSOR_PRODUCTION_TOTAL = "production_total"
SENSOR_POWER_LATEST = "power_latest"
SENSOR_POWER_MAX = "power_max_day"
SENSOR_POWER_LIFETIME = "Lifetime"
SENSOR_ENERGY_DAY = "exported_latest"
SENSOR_CONSUMED_TOTAL = "consumed_total"
SENSOR_EXPORTED_TOTAL = "exported_total"
SENSOR_TIME = "date"
SENSOR_TIME_2 = "date_2"
