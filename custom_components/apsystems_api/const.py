from homeassistant.const import Platform

DOMAIN = "apsystems_api"
PLATFORMS: list[Platform] = [Platform.SENSOR]

CONF_AUTH_ID = "authId"
CONF_ECU_ID = "ecuId"
CONF_VIEW_ID = "viewId"
CONF_PANELS = "panels"
CONF_SYSTEM_ID = "systemId"

# Region of the APsystems EMA cloud server, selectable per config entry.
CONF_SERVER = "server"

# --- APsystems EMA cloud servers -------------------------------------------
# The integration scrapes the APsystems EMA website. There are two regional
# deployments which expose the exact same API paths but live on different
# domains (".com" = international, ".cn" = China). The region used to be
# hard-coded in sensor.py, so it had to be patched by hand after every
# update. It is now stored in the config entry and applied at runtime.
SERVER_CN = "cn"
SERVER_COM = "com"

# Keep the historical international server as the default so that existing
# installations and non-Chinese users are not affected by this new option.
DEFAULT_SERVER = SERVER_COM

SERVERS: dict[str, dict[str, str]] = {
    SERVER_COM: {
        "label": "International (apsystemsema.com)",
        "base_url": "https://www.apsystemsema.com",
    },
    SERVER_CN: {
        "label": "China (apsystemsema.cn)",
        "base_url": "https://www.apsystemsema.cn",
    },
}

DEFAULT_BASE_URL = SERVERS[DEFAULT_SERVER]["base_url"]


def get_server(server_key: str | None) -> dict[str, str]:
    """Return the description of a server region.

    Unknown or missing keys fall back to the default region, which keeps
    config entries created before this option existed fully functional.
    """
    return SERVERS.get(server_key or DEFAULT_SERVER, SERVERS[DEFAULT_SERVER])


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
