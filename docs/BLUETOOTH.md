## Local Bluetooth mode

This integration now includes an experimental `Bluetooth` connection mode for Micronova stoves equipped with a local BLE module (for example the Micronova / Navel `T009_*` module seen by Home Assistant).

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
