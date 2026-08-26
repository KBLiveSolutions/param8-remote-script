from __future__ import absolute_import, print_function, unicode_literals
from ableton.v2.base import listens, liveobj_valid
from ableton.v2.control_surface import Component

import logging
logger = logging.getLogger(__name__)
def print(text):
    logger.warning(text)


class MidiMappingDetector(Component):
    """Detects user MIDI mappings by monitoring parameter changes
    when entering/exiting Ableton's MIDI map mode (Cmd+M).

    Flow:
    1. User enters MIDI map mode -> we attach listeners on selected track's parameters
    2. User assigns a CC/note to a parameter -> we cache which parameters changed
    3. User exits MIDI map mode -> we listen to incoming MIDI and check if cached
       parameters respond, confirming the mapping
    4. On confirmation -> store the mapping, clean up listeners
    """

    def __init__(self, parent, *a, **k):
        super(MidiMappingDetector, self).__init__(*a, **k)
        self._parent = parent
        self._is_mapping_mode = False
        self._parameter_listeners = []
        self._candidate_params = []
        self._confirmed_mappings = []
        self._pending_midi = None
        self._validation_mode = False
        self._on_midi_mapping_changed.subject = self.song

    @listens('midi_mapping_is_enabled')
    def _on_midi_mapping_changed(self):
        enabled = self.song.midi_mapping_is_enabled
        if enabled:
            self._enter_mapping_mode()
        else:
            self._exit_mapping_mode()

    def _enter_mapping_mode(self):
        print("MidiMapping: entering map mode")
        self._is_mapping_mode = True
        self._validation_mode = False
        self._candidate_params = []
        self._attach_parameter_listeners()

    def _exit_mapping_mode(self):
        print("MidiMapping: exiting map mode")
        self._is_mapping_mode = False
        if self._candidate_params:
            print(f"MidiMapping: {len(self._candidate_params)} candidate param(s), entering validation")
            self._validation_mode = True
        else:
            print("MidiMapping: no candidates, cleaning up")
            self._cleanup()

    def _attach_parameter_listeners(self):
        self._remove_parameter_listeners()
        track = self.song.view.selected_track
        if not liveobj_valid(track):
            return
        for device in track.devices:
            if not liveobj_valid(device):
                continue
            for param in device.parameters:
                if not liveobj_valid(param):
                    continue
                cb = lambda p=param, d=device, t=track: self._on_param_changed_during_mapping(p, d, t)
                param.add_value_listener(cb)
                self._parameter_listeners.append((param, cb))
        print(f"MidiMapping: listening to {len(self._parameter_listeners)} params on '{track.name}'")

    def _remove_parameter_listeners(self):
        for param, cb in self._parameter_listeners:
            try:
                if liveobj_valid(param) and param.value_has_listener(cb):
                    param.remove_value_listener(cb)
            except Exception:
                pass
        self._parameter_listeners = []

    def _on_param_changed_during_mapping(self, param, device, track):
        if not self._is_mapping_mode:
            return
        entry = {
            'param': param,
            'param_name': param.name,
            'device_name': device.name,
            'device_class': device.class_name,
            'track_name': track.name,
        }
        for c in self._candidate_params:
            if c['param'] == param:
                return
        self._candidate_params.append(entry)
        print(f"MidiMapping: candidate '{param.name}' on '{device.name}' ({track.name})")

    def on_midi_received(self, status, channel, data1, data2):
        """Called from process_midi_bytes for CC and Note messages."""
        if not self._validation_mode:
            return
        msg_type = status & 0xF0
        if msg_type == 0xB0:
            midi_type = 'cc'
        elif msg_type in (0x90, 0x80):
            midi_type = 'note'
        else:
            return

        self._pending_midi = {
            'type': midi_type,
            'channel': channel,
            'number': data1,
            'value': data2,
        }
        self._check_candidates_after_midi()

    def _check_candidates_after_midi(self):
        if not self._pending_midi or not self._candidate_params:
            return
        for candidate in list(self._candidate_params):
            param = candidate['param']
            if not liveobj_valid(param):
                self._candidate_params.remove(candidate)
                continue
            cb = lambda p=param, c=candidate: self._on_param_changed_validation(p, c)
            param.add_value_listener(cb)
            self._parameter_listeners.append((param, cb))

    def _on_param_changed_validation(self, param, candidate):
        if not self._pending_midi:
            return
        mapping = {
            'midi_type': self._pending_midi['type'],
            'channel': self._pending_midi['channel'],
            'number': self._pending_midi['number'],
            'param_name': candidate['param_name'],
            'device_name': candidate['device_name'],
            'device_class': candidate['device_class'],
            'track_name': candidate['track_name'],
        }
        for m in self._confirmed_mappings:
            if m['param_name'] == mapping['param_name'] and m['device_name'] == mapping['device_name']:
                return
        self._confirmed_mappings.append(mapping)
        ch_display = mapping['channel'] + 1
        print(f"MidiMapping: CONFIRMED {mapping['midi_type'].upper()} "
              f"ch{ch_display} #{mapping['number']} -> "
              f"'{mapping['param_name']}' on '{mapping['device_name']}' ({mapping['track_name']})")
        self._candidate_params = [c for c in self._candidate_params if c['param'] != param]
        if not self._candidate_params:
            print(f"MidiMapping: all candidates validated, {len(self._confirmed_mappings)} mapping(s) found")
            self._send_mappings_to_firmware()
            self._cleanup()

    def _send_mappings_to_firmware(self):
        for m in self._confirmed_mappings:
            print(f"MidiMapping: {m['midi_type'].upper()} ch{m['channel']+1} #{m['number']} "
                  f"-> {m['param_name']} ({m['device_name']} / {m['track_name']})")

    def get_confirmed_mappings(self):
        return list(self._confirmed_mappings)

    def _cleanup(self):
        self._remove_parameter_listeners()
        self._candidate_params = []
        self._pending_midi = None
        self._validation_mode = False

    def disconnect(self):
        self._cleanup()
        self._confirmed_mappings = []
        super(MidiMappingDetector, self).disconnect()
