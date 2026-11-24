# Local MQTT
⚠️ This method requires you to spoof the DNS record of your stove vendor endpoint on your local network. If you don’t know how to do this, or don’t have the possibility to create custom DNS records in your router, this method won’t work for you.

Use an MQTT 3.1.1 broker or protocol-compatible endpoint reachable by both Home Assistant and the stove. Configure the endpoint before enabling local MQTT in Agua IOT.

1. Connect Agua IOT through the cloud once to cache device metadata and register maps.
2. Install a local MQTT app ([Mosquitto](https://github.com/home-assistant/apps/blob/master/mosquitto/DOCS.md)) if needed.
3. Create a user/password `navel`/`navel!!` in the MQTT broker configuration.
4. Point the stove vendor hostname (find it in [const.py](https://github.com/vincentwolsink/home_assistant_micronova_agua_iot/blob/0b6fe6a255973d6e1ee973ee3ac7390752b56d9c/custom_components/aguaiot/const.py#L126)) to your MQTT broker using your router or local DNS service.
5. In Agua IOT options, select **Local MQTT** as connection mode. The shared MQTT connection settings appear next; Leave the host empty to use the existing Home Assistant MQTT integration, or enter a host, port and credentials for a separate connection.
6. Save the settings. The mode is accepted after fresh readings arrive from every stove in the account.

Each stove has separate topics, register cache and application session. Configure the broker ACLs for the stove topics below. Stove firmware credentials may be shared and MQTT traffic is unencrypted; use a trusted LAN.

Topics are `navel/<MAC>` and `master/responses/navel/<MAC>`, with 12 uppercase hexadecimal MAC digits. Retained responses are ignored and commands are never retained or automatically retried.

Polling reads RAM and the active setpoint/status registers listed in the cached model map, including EEPROM registers. Schedule settings are excluded. Reading EEPROM does not consume write cycles. The initial cache is not accepted as a live connection check.

Writes to EEPROM are subject to the shared per-stove budget described in [EEPROM protection](EEPROM.md).

Existing entity IDs and device registrations are retained; switching connection mode does not require removing the integration. One connection mode and one MQTT endpoint configuration apply to all stoves in an account.

Compatibility depends on the Navel protocol and a valid register map for the actual stove. A vendor hostname such as `remote.mcz.it` alone does not establish compatibility.

Register reads wait until the stove answers the Identity query. The endpoint must make the current Identity announcement available when the client connects. The learned registration code is saved in the Home Assistant private device cache for later starts and redacted from diagnostics.
