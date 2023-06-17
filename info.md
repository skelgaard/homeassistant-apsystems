[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs) [![apsystems](https://img.shields.io/github/v/release/bgbraga/homeassistant-apsystems.svg)](https://github.com/bgbraga/homeassistant-apsystems) ![Maintenance](https://img.shields.io/maintenance/yes/2021.svg)

##### Please contribute:
[![Buy me a beer!](https://img.shields.io/badge/Buy%20me%20a%20beer!-%F0%9F%8D%BA-yellow.svg)](https://www.paypal.com/donate/?hosted_button_id=RWTHA7XKSMSZC)

### Features:
This component simplifies the integration of a APsystems inverter:
* creates up to individuals sensors for easy display or use in automations
* collects power (W) and energy (KWH) every 5 minutes.  There is also a sensor for daily total and max power.
* extract data from apsystemsema.com web portal instead of hack the ECU connection
* supports any kind of ASsystems inverter or ECU
* if enabled, pauses from sunset to sunrise (basically when there no sun)
* have a cache system to avoid individual sensors request the same data to apsystemsema.com. It is a great feature for I/O (HTTP) performance.
* there is a date sensor to identify exactly date/time refers each sensor data

### Minimal Configuration
Use your apsystemsema.com user to configure the configuration.yaml:
```yaml
sensor:
  - platform: apsystems
    authId: apsystemsem_authid
    systemId: apsystemsema_system_id
    ecuId: apsystemsema_ecu_id
    sunset: off
```
1 - set "Allow visitors to access to this system" and get the authid from here

2 - your systemId is found at apsystemsema.com. See the page source code and at the Settings Menu there is a code like that:
```html
<span>Settings</span>
<ul>
    <li onclick="managementClickCustomer('YOUR SYSTEM ID')"><a>Settings</a></li>
    <li onclick="intoFaq(10)"><a>Help</a></li>
</ul>
```
Get the system id inside the ```managementClickCustomer()```.

3 - There is an ecu id data at https://apsystemsema.com/ema/security/optmainmenu/intoLargeReport.action

4 - sunset attribute could be on or off

### Debug
To get debug info in the logs do
```yaml
logger:
  default: info
  logs:
    custom_components.apsystems: debug
```

and then grep the log for output

```bash
grep apsystem home-assistant.log
```

[![Buy me a beer!](https://img.shields.io/badge/Buy%20me%20a%20beer!-%F0%9F%8D%BA-yellow.svg)](https://www.paypal.com/donate/?hosted_button_id=RWTHA7XKSMSZC)
