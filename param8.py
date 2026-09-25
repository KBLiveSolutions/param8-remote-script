import Live
import json, os
from ableton.v2.base import const, inject, recursive_map, nop, liveobj_valid, clamp, listenable_property, listens, task, index_if, depends
from ableton.v2.control_surface import ControlSurface, Layer, DeviceDecoratorFactory, PrioritizedResource, MIDI_CC_TYPE, MIDI_NOTE_TYPE, PercussionInstrumentFinder
from ableton.v2.control_surface import MIDI_CC_TYPE, MIDI_NOTE_TYPE, PrioritizedResource

_DEFAULTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "defaults.json")
from ableton.v2.control_surface.elements import ButtonElement, EncoderElement, ButtonMatrixElement, ComboElement, EncoderElement
from ableton.v2.control_surface.components import AutoArmComponent, BackgroundComponent, RightAlignTracksTrackAssigner, SessionRingComponent, UndoRedoComponent, ChannelStripComponent, SessionNavigationComponent
from ableton.v2.control_surface.mode import AddLayerMode, DelayMode, ImmediateBehaviour, ModesComponent, ReenterBehaviour
from .skin import make_default_skin
from contextlib import contextmanager
from functools import partial

from .device_navigation import SimpleDeviceNavigationComponent
from .device import SimpleDeviceParameterComponent
from .mixer import MixerComponent
from .colors import LIVE_COLORS_TO_MIDI_VALUES, RGB_COLOR_TABLE

SCRIPT_NAME = 'param8'
SCRIPT_VER = 'v1.0'

MIDI_CHANNEL = 7

import logging, traceback
logger = logging.getLogger(__name__)
def print(text):
    logger.warning(text)  

""" Dictionnaries containing all the actions performed by the buttons/sliders or interpreted by the LEDs.
 It consists of a dictionnary with the name of the action and the associated CC number."""


button_actions = {
    "Shift": 20,
    "BankUp": 27,
    "BankDown": 26,
    "DeviceUp": 25,
    "DeviceDown": 24,
    "Prev Device": 33,
    "Next Device": 32,
    "TrackDown": 20,
    "TrackUp": 21,
    "SendsDown": 56,
    "SendsUp": 57,
    "Metronome": 50,
    "Mute": 54,
    "Solo": 55,
    "Launch_Scene": 53,
    "Record": 51,
    "Play": 52,
    "Loop": 56,
    "Default": 57,
    "A/B": 23,
    "Hotswap": 22,
  }
led_actions = {
  }
slider_actions = {    
    "Device_Encoder_1": 10,
    "Device_Encoder_2": 11,
    "Device_Encoder_3": 12,
    "Device_Encoder_4": 13,
    "Device_Encoder_5": 14,
    "Device_Encoder_6": 15,
    "Device_Encoder_7": 16,
    "Device_Encoder_8": 17,
    "Tempo": 42,
    "Scene_Select": 43,
    "Cue_Volume": 41,
    "Master_Volume": 40,
    "Track Volume": 44,
    "Track Pan": 45,
    "Song Position": 46,
    "Selected Parameter": 47,
  }
display_actions =  {}

class param8(ControlSurface):
    
    def __init__(self, *a, **k):
        self._param_watchers = {}
        self._last_name_request_sysex = ()
        self._revert_snapshot = None
        super(param8, self).__init__(*a, **k)
        print("====================================")
        self._last_sent_layout_byte = None
        self._skin = make_default_skin()
        
        # Initialiser device_bank_registry avant de créer les composants
        self._device_bank_registry = self._create_device_bank_registry()
        
        with self.component_guard():
            self._create_buttons()
            self._create_device_parameters()
            self.create_device_navigation()
            self.create_mixer()
            # self.set_device_component(self._device)
        self.active_mode = 1
        self._device_parameters.look_for_param8_device(self.active_mode)
        self.send_sysex((240, 111, 5, 0, 247))
        self.schedule_message(20, self._delayed_handshake)
        self._restore_param_mappings()
        self._on_transport_changed.subject = self.song
        self._mixer.set_sync_callback(self._send_song_position)
        print("param8 OK")

    def _delayed_handshake(self):
        self.send_sysex((240, 111, 5, 0, 247))

    def _send_song_position(self):
        try:
            song = self.song()
            sig_num = song.signature_numerator
            sig_den = song.signature_denominator
            ticks = int(song.current_song_time * sig_num * (4.0 / sig_den) * 24)
            high = (ticks >> 14) & 0x7F
            mid  = (ticks >> 7)  & 0x7F
            low  =  ticks        & 0x7F
            self._send_midi((0xF0, 0x6F, 0x1C, high, mid, low, 0xF7))
        except Exception as e:
            print(f"_send_song_position error: {e}")

    @listens('is_playing')
    def _on_transport_changed(self):
        if self.song().is_playing:
            self._mixer._last_sync_beat = -1
            self._send_song_position()

    def _scan_set_devices(self):
        """Scan toutes les devices du Live Set actuel. Celles qui ne sont pas
        déjà dans defaults.json sont ajoutées avec leurs banks par défaut.
        Usage: décommenter l'appel dans __init__, recharger le script, recommenter."""
        try:
            if os.path.exists(_DEFAULTS_PATH):
                with open(_DEFAULTS_PATH, "r") as f:
                    result = json.load(f)
            else:
                result = {}

            browser = self.application.browser
            browser_cat = {}
            for cat_key, cat_item in [("audio_effects", browser.audio_effects),
                                       ("instruments", browser.instruments),
                                       ("midi_effects", browser.midi_effects)]:
                for item in cat_item.children:
                    if item.is_folder:
                        for child in item.children:
                            if not child.is_folder:
                                browser_cat[child.name] = cat_key
                    else:
                        browser_cat[item.name] = cat_key

            added = 0
            all_tracks = list(self.song.visible_tracks) + list(self.song.return_tracks) + [self.song.master_track]
            for track in all_tracks:
                for device in track.devices:
                    cn = device.class_name
                    dn = device.class_display_name
                    cat = browser_cat.get(dn, "audio_effects")
                    from .device import _resolve_banks, _auto_banks
                    pbanks, bnames = _resolve_banks(device)
                    if not pbanks or len(pbanks) <= 1:
                        pbanks = _auto_banks(device) or pbanks or []
                        bnames = ["Bank %d" % (i + 1) for i in range(len(pbanks))]
                    banks = []
                    for i, bank in enumerate(pbanks):
                        bname = bnames[i] if i < len(bnames) else "Bank %d" % (i + 1)
                        params = []
                        for p in bank:
                            if liveobj_valid(p):
                                params.append(p.name)
                            else:
                                params.append(None)
                        banks.append({"name": bname, "parameters": params})
                    entry = {"display_name": dn, "category": cat}
                    if banks:
                        entry["banks"] = banks
                    result[cn] = entry
                    added += 1
                    print("param8: + %s (%s, %d banks)" % (dn, cn, len(banks)))

            with open(_DEFAULTS_PATH, "w") as f:
                json.dump(result, f, indent=2, sort_keys=True)
            print("param8: scan done — added %d new devices (total: %d)" % (added, len(result)))
        except Exception as e:
            import traceback
            print("param8: scan failed: %s" % e)
            traceback.print_exc()

    def _create_device_bank_registry(self):
        """Crée le registre des banques de device"""
        from ableton.v2.control_surface.device_bank_registry import DeviceBankRegistry
        return DeviceBankRegistry()

    def create_device_navigation(self):
        self._device_navigation = SimpleDeviceNavigationComponent( name="Device_Navigation",
            is_enabled=True)       
        self._device_navigation.layer=Layer( next_button=self.buttons["DeviceUp"],
                                    prev_button=self.buttons["DeviceDown"],
                      )

    def _create_buttons(self):
        """ Create all the buttons one by one then buils the button matrixes if needed"""
        self.buttons = {}
        self.encoders = {}
        for control in button_actions:
            self.buttons[control] = self.make_button(button_actions[control], MIDI_CHANNEL, msg_type=MIDI_CC_TYPE, name=control)
        for control in slider_actions:
            self.encoders[control] = self.make_encoder(slider_actions[control], MIDI_CHANNEL, msg_type=MIDI_CC_TYPE, name=control)
            self.encoders[control].set_feedback_delay(1)
        self.parameter_controls_raw = [self.encoders["Device_Encoder_1"], self.encoders["Device_Encoder_2"], self.encoders["Device_Encoder_3"], self.encoders["Device_Encoder_4"], self.encoders["Device_Encoder_5"], self.encoders["Device_Encoder_6"], self.encoders["Device_Encoder_7"], self.encoders["Device_Encoder_8"]]
        self.device_parameter_buttons = ButtonMatrixElement(rows=[self.parameter_controls_raw])
        self.global_param_controls = ButtonMatrixElement(name="Track_Controls", rows=[self.parameter_controls_raw])
        self._shift_active = False

    def make_button(self, identifier, channel, name, msg_type = MIDI_CC_TYPE, skin = None, is_modifier = False):
        return ButtonElement(True, msg_type, channel, identifier, skin=self._skin, name=name, resource_type=PrioritizedResource if is_modifier else None)

    def make_encoder(self, identifier, channel, name, msg_type = MIDI_CC_TYPE, skin = None, is_modifier = False):
        encoder = EncoderElement(MIDI_CC_TYPE, channel, identifier, Live.MidiMap.MapMode.relative_smooth_two_compliment)
        encoder.mapping_sensitivity = 2.0  # Augmente cette valeur pour rendre l'encodeur plus "rapide"
        return encoder

    def _create_device_parameters(self):
        self._device_parameters = SimpleDeviceParameterComponent(parent=self, name="Device_Parameters",
            is_enabled=True,
            use_parameter_banks=True,
            device_bank_registry = self._device_bank_registry,
        )            
        self._device_parameters.layer=Layer(parameter_controls=self.device_parameter_buttons,
                                    next_bank_button=self.buttons["BankUp"],
                                    prev_bank_button=self.buttons["BankDown"],
                                    Compare=self.buttons["A/B"],
                                    DeviceOn=self.buttons["Hotswap"],
                    #   bank_select_buttons=self._elements.bank_select_buttons
                      )

    def create_mixer(self):
        """ Create the mixer component and assign the buttons to it"""
        self._session_ring = SessionRingComponent(is_enabled=False, num_tracks=1, num_scenes=0, tracks_to_use=lambda : tuple(self.song.visible_tracks) + tuple(self.song.return_tracks) + (self.song.master_track,), name=u'Session_Ring')
        self._mixer = MixerComponent(is_enabled=True, tracks_provider=self._session_ring, track_assigner=RightAlignTracksTrackAssigner(song=self.song, include_master_track=True), channel_strip_component_type=ChannelStripComponent, name=u'Mixer')
        
        # Configurer le layer après création
        self._mixer.layer = Layer(
            Master_Volume=self.encoders["Master_Volume"],
            Cue_Volume=self.encoders["Cue_Volume"],
            Track_Volume= self.encoders["Track Volume"],
            Track_Pan= self.encoders["Track Pan"],
            Selected_Parameter=self.encoders["Selected Parameter"],
            Song_Position=self.encoders["Song Position"],
            next_track_button=self.buttons["TrackUp"],
            prev_track_button=self.buttons["TrackDown"],
            next_sends_button=self.buttons["SendsUp"],
            prev_sends_button=self.buttons["SendsDown"],
            tempo=self.encoders["Tempo"],
            scene_select=self.encoders["Scene_Select"],
            Mute=self.buttons["Mute"],
            Solo=self.buttons["Solo"],
            Record=self.buttons["Record"],
            Play=self.buttons["Play"],
            Loop=self.buttons["Loop"],
            Launch_Scene=self.buttons["Launch_Scene"],
            Default=self.buttons["Default"],
            Metronome=self.buttons["Metronome"],
        )
        self._mixer.set_parent(self)


    def _handle_name_request(self, idx, is_button):
        selected_param = self.song.view.selected_parameter
        if not liveobj_valid(selected_param):
            print(f"NameRequest: no parameter selected")
            return
        name = selected_param.name[:11]
        preset = self.active_mode
        if preset >= 6:
            print(f"NameRequest: ignored on preset {preset}")
            return
        message = [240, 111, 15, preset, idx, is_button]
        for c in name:
            message.append(ord(c) & 0x7F)
        message.append(247)
        self._send_midi(tuple(message))

        parent = selected_param.canonical_parent if liveobj_valid(selected_param.canonical_parent) else None
        if parent and hasattr(parent, 'sends'):
            device_name = "MixerDevice"
            track = parent.canonical_parent if liveobj_valid(parent.canonical_parent) else None
            track_name = track.name if track and hasattr(track, 'name') else ""
        elif parent and hasattr(parent, 'name'):
            device_name = parent.name
            track = self._find_track_for_device(parent)
            track_name = track.name if track and hasattr(track, 'name') else ""
        else:
            device_name = ""
            track_name = ""
        print(f"NameRequest: parent={type(parent).__name__} device='{device_name}' track='{track_name}'")
        if not is_button:
            value_str = selected_param.str_for_value(selected_param.value)
            self.send_display(1, idx, value_str)
            self._watch_parameter(preset, idx, selected_param)

        self._save_param_mapping(preset, idx, is_button,
            track_name, device_name, selected_param.name)

        label = "button" if is_button else "encoder"
        print(f"NameRequest: assigned '{name}' to {label} {idx} preset {preset}")

    def _find_track_for_device(self, device):
        obj = device
        while obj and liveobj_valid(obj):
            parent = obj.canonical_parent
            if not liveobj_valid(parent):
                break
            if isinstance(parent, Live.Track.Track):
                return parent
            obj = parent
        return None

    def _watch_parameter(self, preset, idx, param):
        key = (preset, idx)
        if key in self._param_watchers:
            old_param, old_cb = self._param_watchers[key]
            try:
                if liveobj_valid(old_param) and old_param.value_has_listener(old_cb):
                    old_param.remove_value_listener(old_cb)
            except Exception:
                pass

        def on_value_changed(p=param, i=idx, pr=preset):
            if self.active_mode != pr:
                return
            if liveobj_valid(p):
                self.send_display(1, i, p.str_for_value(p.value))

        param.add_value_listener(on_value_changed)
        self._param_watchers[key] = (param, on_value_changed)
        self._send_midi((240, 111, 18, preset, idx, 1, 247))
        print(f"NameRequest: watching '{param.name}' for value updates on encoder {idx}")

    def _save_param_mapping(self, preset, idx, is_button, track_name, device_name, param_name):
        data_key = "param8_mappings"
        try:
            raw = self.song.get_data(data_key, "")
            mappings = json.loads(raw) if raw else {}
        except Exception:
            mappings = {}
        key = f"{preset}:{'b' if is_button else 'e'}:{idx}"
        mappings[key] = {"track": track_name, "device": device_name, "param": param_name}
        self.song.set_data(data_key, json.dumps(mappings))
        print(f"NameRequest: saved mapping {key} -> {param_name} ({device_name} / {track_name})")

    def _clear_param_mapping(self, preset, idx, is_button):
        key = (preset, idx)
        if not is_button and key in self._param_watchers:
            old_param, old_cb = self._param_watchers[key]
            try:
                if liveobj_valid(old_param) and old_param.value_has_listener(old_cb):
                    old_param.remove_value_listener(old_cb)
            except Exception:
                pass
            del self._param_watchers[key]
            self._send_midi((240, 111, 18, preset, idx, 0, 247))
            print(f"ClearNaming: removed watcher for encoder {idx} preset {preset}")

        data_key = "param8_mappings"
        try:
            raw = self.song.get_data(data_key, "")
            mappings = json.loads(raw) if raw else {}
        except Exception:
            mappings = {}
        map_key = f"{preset}:{'b' if is_button else 'e'}:{idx}"
        if map_key in mappings:
            del mappings[map_key]
            self.song.set_data(data_key, json.dumps(mappings))
            print(f"ClearNaming: removed mapping {map_key}")

    def _restore_param_mappings(self):
        data_key = "param8_mappings"
        try:
            raw = self.song.get_data(data_key, "")
            mappings = json.loads(raw) if raw else {}
        except Exception:
            print("NameRequest: no saved mappings found")
            return
        if not mappings:
            return
        print(f"NameRequest: restoring {len(mappings)} mapping(s)")
        for key, info in mappings.items():
            parts = key.split(":")
            if len(parts) != 3:
                continue
            preset = int(parts[0])
            is_button = parts[1] == "b"
            idx = int(parts[2])
            param = self._find_param_by_names(info["track"], info["device"], info["param"])
            if param and not is_button:
                self._watch_parameter(preset, idx, param)
                print(f"NameRequest: restored watcher for '{info['param']}' on encoder {idx} preset {preset}")
            elif not param:
                print(f"NameRequest: could not find param '{info['param']}' on '{info['device']}' ({info['track']})")

    def _find_param_by_names(self, track_name, device_name, param_name):
        for track in list(self.song.visible_tracks) + list(self.song.return_tracks) + [self.song.master_track]:
            if not liveobj_valid(track) or track.name != track_name:
                continue
            if device_name == "MixerDevice":
                md = track.mixer_device
                for attr in ('volume', 'panning'):
                    p = getattr(md, attr, None)
                    if p and liveobj_valid(p) and p.name == param_name:
                        return p
                if track == self.song.master_track:
                    try:
                        p = md.cue_volume
                        if liveobj_valid(p) and p.name == param_name:
                            return p
                    except Exception:
                        pass
                for send in md.sends:
                    if liveobj_valid(send) and send.name == param_name:
                        return send
            else:
                for device in track.devices:
                    if liveobj_valid(device) and device.name == device_name:
                        for p in device.parameters:
                            if liveobj_valid(p) and p.name == param_name:
                                return p
        return None

    def send_sysex(self, midi_bytes):
        self._send_midi(midi_bytes)

    def send_display_simple(self, status_byte, param_number, name):
        _len = min(len(name), 10)
        message = [240, 111, status_byte, param_number]
        for i in range(_len):
            char_code = ord(name[i])
            if 0 <= char_code - 32 <= 94:  # Caractères standards (32 à 126)
                message.append(char_code - 32)
            else:  # Autres caractères non valides
                message.append(95)  # Remplace par `_`
        message.append(247)
        print(message)
        self.send_sysex(tuple(message))

    def send_display(self, status_byte, param_number, name, static_overlay=0):
        _name = name[:32].strip()  # Limiter à 14 caractères et enlever les espaces
        _len = len(_name)
        message = [240, 111, status_byte, param_number, static_overlay]
        for i in range(_len):
            char_code = ord(_name[i])
            if 0 <= char_code - 32 <= 94:  # Caractères standards (32 à 126)
                message.append(0)  # Byte spécial pour indiquer un caractère étendu
                message.append(char_code - 32)
            elif 128 <= char_code <= 255:  # Caractères spéciaux (128 à 255)
                message.append(1)  # Byte spécial pour indiquer un caractère étendu
                message.append(char_code - 128)  # Ajout du caractère étendu
            else:  # Autres caractères non valides
                message.append(95)  # Remplace par `_`
        message.append(247)
        self.send_sysex(tuple(message))

        # sequence_to_run = [
        #  None] * (len(self._messages_to_send) * 2)
        # sequence_to_run[None[None:2]] = [Task.run(partial(self._send_midi, msg)) for msg in self._messages_to_send]
        # sequence_to_run[1[None:2]] = [Task.wait(INDIVIDUAL_MESSAGE_DELAY) for _ in self._messages_to_send]
        # for subsequence in split_list(sequence_to_run, 40):
        #     self._tasks.add((Task.sequence)(*subsequence))

    def port_settings_changed(self):
        super(param8, self).port_settings_changed()
        self.set_enabled(True)

    def handle_sysex(self, midi_bytes):
        print(f"=== SYSEX IN: {list(midi_bytes[:8])} ===")
        if midi_bytes[1] == (111):
            if midi_bytes[2] == 17:
                print(f"NameRequest SysEx received: {list(midi_bytes)}")
                self._handle_name_request(midi_bytes[3], midi_bytes[4])
                return
            if midi_bytes[2] == 0x1A:
                val = midi_bytes[3]
                print(f"Revert SysEx 0x1A: val={val}")
                if val == 1:
                    self._enter_revert()
                elif val == 0:
                    self._restore_revert()
                elif val == 2:
                    self._discard_revert()
                return
            if midi_bytes[2] == 0x19:
                preset = midi_bytes[3]
                idx = midi_bytes[4]
                is_button = midi_bytes[5]
                print(f"ClearNaming SysEx received: preset={preset} idx={idx} is_button={is_button}")
                self._clear_param_mapping(preset, idx, is_button)
                return
            if midi_bytes[2] == 0x1D:
                self._send_song_position()
                return
            if midi_bytes[2] == 4:
                print(f"=== PRESET SYSEX received: {midi_bytes[3]} ===")
                self.active_mode = midi_bytes[3]
                self._mixer.mixer_control_enabled = False
                self._device_parameters.device_control_enabled = False
                if self.active_mode == 7:
                    self._device_parameters.device_control_enabled = True
                    self._device_parameters._update_parameter_banks()
                    self._device_parameters.update()
                elif self.active_mode == 6:
                    self._mixer.mixer_control_enabled = True
                    self._mixer.update_component()
                    self.schedule_message(5, self._mixer._send_all_value_displays)
                else:
                    self._device_parameters.look_for_param8_device(self.active_mode)
                    self.request_rebuild_midi_map()
                    self._device_parameters.update()


    def process_midi_bytes(self, midi_bytes, midi_processor):
        if midi_bytes[0] == 240 and midi_bytes[-1] == 247:
            self.handle_sysex(midi_bytes)
            return
        if len(midi_bytes) >= 3:
            status = midi_bytes[0] & 0xF0
            channel = midi_bytes[0] & 0x0F
            if status == 0xB0 and channel == MIDI_CHANNEL:
                cc = midi_bytes[1]
                val = midi_bytes[2]
                if cc == 110:
                    is_shift = val > 63
                    if is_shift != self._shift_active:
                        self._shift_active = is_shift
                        sens = 0.01 if is_shift else 2.0
                        for enc in self.parameter_controls_raw:
                            enc.mapping_sensitivity = sens
                    return
        super(param8, self).process_midi_bytes(midi_bytes, midi_processor)

    def _enter_revert(self):
        self._revert_snapshot = []
        params = self._get_active_parameters()
        print(f"Revert: active_mode={self.active_mode} params_count={len(params)}")
        for i, p in enumerate(params):
            if p and liveobj_valid(p):
                self._revert_snapshot.append((p, p.value))
                print(f"  [{i}] '{p.name}' = {p.value}")
            else:
                self._revert_snapshot.append(None)
                print(f"  [{i}] None")
        print(f"Revert: snapshot {len([s for s in self._revert_snapshot if s])} params")

    def _restore_revert(self):
        if not self._revert_snapshot:
            print("Revert: nothing to restore")
            self._revert_snapshot = None
            return
        for i, entry in enumerate(self._revert_snapshot):
            if entry:
                param, value = entry
                if liveobj_valid(param):
                    param.value = value
                    self.send_display(1, i, param.str_for_value(value))
                    print(f"Revert: restored '{param.name}' = {value}")
        self._revert_snapshot = None

    def _discard_revert(self):
        self._revert_snapshot = None
        print("Revert: discarded")

    def _get_active_parameters(self):
        if self.active_mode == 7:
            return list(self._device_parameters.parameters)
        elif self.active_mode == 6:
            return self._mixer.get_snapshotable_params()
        return []

    def _add_control(self, number):
        return ButtonElement(True, MIDI_CC_TYPE, MIDI_CHANNEL, number)

    def _add_slider(self, number):
        return EncoderElement(MIDI_CC_TYPE, MIDI_CHANNEL, number, Live.MidiMap.MapMode.relative_smooth_two_compliment)

    # def disconnect(self):
    #     super(param8, self).disconnect()
    #     # self._session = None
