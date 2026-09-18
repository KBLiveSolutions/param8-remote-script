# Param8 Remote Script

An Ableton Live Control Surface script for the [Param8](https://github.com/KBLiveSolutions/param8-firmware) hardware MIDI controller. It lets Live recognize the Param8 as a native control surface — encoder-to-parameter mapping, mixer control, and color feedback — instead of relying on manual MIDI Learn.

Part of the Param8 ecosystem:

- **[param8-firmware](https://github.com/KBLiveSolutions/param8-firmware)** - Firmware running on the device
- **[param8-editor](https://github.com/KBLiveSolutions/param8-editor)** - Desktop app to configure the device and install firmware updates

## What It Does

- Maps the 8 rotary encoders to the selected device's parameters, bidirectionally
- Mixer control: track volume/pan, sends, cue/master volume, tempo, song position
- Device and bank navigation via dedicated buttons (bank up/down, device up/down, previous/next device)
- Transport and utility buttons: play, record, metronome, mute, solo, loop, launch scene
- Track/clip color feedback, mapped to the controller's LEDs via a Live color lookup table
- Requests parameter and track names over SysEx so the hardware's OLED screens can show live labels
- Runs on a fixed MIDI channel (channel 7)

## Files

```
param8.py             # Main ControlSurface class: button/encoder action tables, SysEx name requests
device.py             # Device parameter bank component (encoders <-> selected device's parameters)
device_navigation.py  # Device chain navigation (adapted from Ableton's bundled Novation script)
mixer.py              # Mixer component (volume, pan, sends, master/cue, tempo, song position)
control.py            # Base mapped-control classes (adapted from Ableton's bundled Akai Force MPC script)
skin.py               # Control surface color/skin definitions
colors.py             # Live track/clip color <-> MIDI value / RGB lookup tables
defaults.json          # Default control mapping
mappings.json          # Saved control mappings
display_names.json     # Saved display name presets
__init__.py            # Live entry point (create_instance)
```

## Installation

1. Locate Ableton Live's Remote Scripts folder:
   - **macOS**: `~/Music/Ableton/User Library/Remote Scripts/`
   - **Windows**: `Documents\Ableton\User Library\Remote Scripts\`

   (Older Live versions may instead require placing the script inside the Live application's own `MIDI Remote Scripts` folder.)
2. Copy this repository's contents into a `param8` folder inside that Remote Scripts location.
3. Restart Ableton Live, then in **Preferences > Link/Tempo/MIDI**, select **param8** as a Control Surface and set its Input/Output to the Param8 device's USB MIDI ports.

## Requirements

- Ableton Live, with a version compatible with the `ableton.v2.control_surface` framework used here
- A Param8 controller running [param8-firmware](https://github.com/KBLiveSolutions/param8-firmware), connected via USB MIDI

## Known Considerations

- `control.py` and `device_navigation.py` are adapted from Ableton's own bundled scripts (Akai Force MPC and Novation control surfaces respectively, via decompiled sources) and used here as base classes for standard Live control-surface behavior.
- `mappings copy.json` looks like a stray backup of `mappings.json` (similar but not identical size) — worth confirming whether it's still needed before relying on it.
- The SysEx prefix used for name requests here (`240, 122, 29, 1, 19`) does not match param8-firmware's current SysEx manufacturer/constructor byte (`111` / `0x6F`, see `src/midi/midi.cpp` in that repo) — this is worth re-verifying against the current firmware protocol if live name syncing misbehaves.
