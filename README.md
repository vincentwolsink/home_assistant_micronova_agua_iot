# Micronova Agua IOT

[![GitHub Release][releases-shield]][releases]
[![Maintainer][maintainer-shield]][maintainer]
[![HACS Custom][hacs-shield]][hacs-url]

Home Assistant integration for controlling heating devices (pellet stoves) connected via the Agua IOT platform of Micronova.

Supports the following vendors (mobile apps):
* Alfaplam
* APP-O BIOEN
* Boreal Home
* Bronpi Home
* Darwin Evolution
* Easy Connect
* Easy Connect Plus
* Easy Connect Poêle
* Elcofire Pellet Home
* Elfire Wifi
* EOSS WIFI
* EvaCalòr - PuntoFuoco
* Fontana Forni
* Fonte Flamme contrôle 1
* Globe-fire
* GO HEAT
* Jolly Mec Wi Fi
* Karmek Wifi
* Klover Home
* LAMINOX Remote Control (2.0)
* Lorflam Home
* Moretti design
* My Corisit
* MyPiazzetta
* MySuperior
* Nina
* Nobis-Fi
* Nordic Fire 2.0
* Ravelli Wi-Fi
* Stufe a pellet Italia
* Thermoflux
* Total Control 3.0 (Extraflame)
* TS Smart
* Wi-Phire

Vendor apps **NOT** compatible (using a different platform or abstraction layer):
* Ravelli Smart Wi-Fi
* Total Control 2.0/1.x

## Screenshots
<img width="671" alt="micronova_screenshot1" src="https://github.com/vincentwolsink/home_assistant_micronova_agua_iot/assets/1639734/4c646550-637d-4e20-bc64-a6977bfee3af">
<img width="330" alt="micronova_screenshot3" src="https://github.com/vincentwolsink/home_assistant_micronova_agua_iot/assets/1639734/3a06b135-eaee-4ff2-94e4-c3da268fb7a9">

## Installation

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=vincentwolsink&repository=home_assistant_micronova_agua_iot&category=integration)

Or folow these steps:
1. Install [HACS](https://hacs.xyz/) if you haven't already
2. Install the plugin via HACS (Micronova Agua IOT)
3. Add the integration through the home assistant configuration flow

## Local Bluetooth mode

This integration now includes an experimental `Bluetooth local` connection mode for Micronova stoves equipped with a local BLE module (for example the Micronova / Navel `T009_*` module seen by Home Assistant).

### What it does

- keeps the existing cloud setup and entity model
- adds a Home Assistant Bluetooth transport for reading buffers and sending writes locally
- works with Home Assistant Bluetooth adapters and Bluetooth proxies such as ESPHome `bluetooth_proxy`
- stores the BLE bootstrap data in the config entry once discovered so normal operation can run locally

### How it works

The local transport talks to the Micronova BLE module with the same command family used by the vendor app:

- `Identity`
- `GetBufferId`
- `GetBufferReading`
- `RequestWriting`

The integration still needs one successful cloud bootstrap to learn the device metadata required for local control:

- BLE identity / MAC reference exposed by the Micronova API
- BLE security code
- register map for the stove model

After that bootstrap data is cached in Home Assistant, reads and writes can run locally over Bluetooth through Home Assistant's Bluetooth stack.

### How to enable it

1. Set up the integration normally with your vendor cloud account.
2. Make sure Home Assistant can reach the stove over Bluetooth, either directly or through a Bluetooth proxy close to the stove.
3. Open the integration options.
4. Change `Connection mode` to `Bluetooth local`.
5. Submit the form and let Home Assistant auto-detect and validate the nearby Micronova BLE module.

The options flow performs a real BLE validation before it accepts the local mode, so a successful save means the module was detected and the local transport was able to talk to it.

### Current scope and limitations

- this mode is experimental
- the first bootstrap still depends on the vendor cloud API
- compatibility is expected to vary depending on the Micronova firmware, BLE module, and stove register map
- no guarantee is made for every supported vendor app or every Micronova-based stove

### Tested hardware

This mode has been validated on:

- vendor app: `Jolly Mec Wi Fi`
- stove / insert: `SYNTHESIS/1/80/M`
- user-facing model reference: `Jolly Mec Modular Synthesis 80`
- local BLE module advertising as `T009_*`

If you test another stove or another vendor app and it works, please report the exact model and module details in your feedback.

## Credits

Some parts of the code are based on [py-agua-iot](https://github.com/fredericvl/py-agua-iot)

## Related

For local stove control with custom hardware on the stove bus, take a look at one of these projects.
* https://esphome.io/components/micronova.html
* https://github.com/eni23/micronova-controller
* https://github.com/fabrizioromanelli/Pellet-Stove-Control
* https://github.com/philibertc/micronova_controller

[releases-shield]: https://img.shields.io/github/v/release/vincentwolsink/home_assistant_micronova_agua_iot.svg?style=for-the-badge
[releases]: https://github.com/vincentwolsink/home_assistant_micronova_agua_iot/releases
[maintainer-shield]: https://img.shields.io/badge/maintainer-vincentwolsink-blue.svg?style=for-the-badge
[maintainer]: https://github.com/vincentwolsink
[hacs-shield]: https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge
[hacs-url]: https://github.com/vincentwolsink/home_assistant_micronova_agua_iot
