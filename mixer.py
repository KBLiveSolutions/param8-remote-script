#Embedded file name: /Users/versonator/Jenkins/live/output/Live/mac_64_static/Release/python-bundle/MIDI Remote Scripts/Akai_Force_MPC/mixer.py
from __future__ import absolute_import, print_function, unicode_literals
from functools import partial
from future.moves.itertools import zip_longest
from ableton.v2.base import clamp, listens, sign, liveobj_valid, forward_property
from ableton.v2.control_surface.components import MixerComponent as MixerComponentBase
from ableton.v2.control_surface.control import SendValueEncoderControl, ButtonControl, SendValueControl, ToggleButtonControl, EncoderControl
from .control import SendReceiveValueControl
# from .elements import MAX_NUM_SENDS


PARAM_NAME = 0
PARAM_VALUE = 1
BANK_NAME = 2
DEVICE_NAME = 3
MAX_NUM_SENDS = 4

class MixerComponent(MixerComponentBase):
    Master_Volume = SendReceiveValueControl()
    Cue_Volume = SendReceiveValueControl()
    Track_Volume = SendReceiveValueControl()
    Track_Pan = SendReceiveValueControl()
    Selected_Parameter = SendReceiveValueControl()
    Song_Position = SendReceiveValueControl()
    next_track_button = ButtonControl()
    prev_track_button = ButtonControl()
    next_sends_button = ButtonControl()
    prev_sends_button = ButtonControl()
    tempo = SendReceiveValueControl()
    scene_select = SendReceiveValueControl()
    Mute = ToggleButtonControl(toggled_color='Mixer.ArmOn', untoggled_color='Mixer.ArmOff')
    Solo = ToggleButtonControl(toggled_color='Mixer.ArmOn', untoggled_color='Mixer.ArmOff')
    Record = ToggleButtonControl(toggled_color='Mixer.ArmOn', untoggled_color='Mixer.ArmOff')
    Play = ToggleButtonControl(toggled_color='Mixer.ArmOn', untoggled_color='Mixer.ArmOff')
    Loop = ToggleButtonControl(toggled_color='Mixer.ArmOn', untoggled_color='Mixer.ArmOff')
    Launch_Scene = ButtonControl()
    Default = ButtonControl()
    Metronome = ToggleButtonControl(toggled_color='Mixer.ArmOn', untoggled_color='Mixer.ArmOff')

    def process_relative_encoder(self, current_value, encoder_value, sensitivity=1, min_val=0.0, max_val=1.0):
        """
        Traite les valeurs d'un encodeur relatif en mode relative_smooth_two_compliment
        
        Args:
            current_value: Valeur actuelle du paramètre (0.0-1.0)
            encoder_value: Valeur MIDI de l'encodeur (1-63 horaire, 127-65 anti-horaire)
            sensitivity: Facteur de sensibilité (par défaut 0.01)
            min_val: Valeur minimale (par défaut 0.0)
            max_val: Valeur maximale (par défaut 1.0)
        
        Returns:
            Nouvelle valeur clampée entre min_val et max_val
        """
        # Conversion en mode two's complement
        if encoder_value <= 64:
            # Rotation horaire : 1, 2, 3... = +1, +2, +3...
            increment = encoder_value * sensitivity
        else:
            # Rotation anti-horaire : 127, 126, 125... = -1, -2, -3...
            increment = (encoder_value - 128) * sensitivity
        
        new_value = clamp(current_value + increment, min_val, max_val)
        return new_value
    
    def __init__(self, *a, **k):
        self._parent = None
        self._selected_track = None
        self._sync_callback = None
        self._last_sync_beat = -1

        super(MixerComponent, self).__init__(*a, **k)
        self.on_cue_volume_changed.subject = self.song.master_track.mixer_device.cue_volume
        self.on_master_volume_changed.subject = self.song.master_track.mixer_device.volume
        self._on_selected_scene_changed.subject = self.song.view
        self.on_tempo_changed.subject = self.song
        self.on_selected_parameter_changed.subject = self.song.view
        self._on_selected_track_changed.subject = self.song.view
        self._on_song_position_changed.subject = self.song
        self._on_playing_state_changed.subject = self.song
        self._on_record_mode_changed.subject = self.song
        self._on_loop_changed.subject = self.song
        self._on_metronome_changed.subject = self.song
        
        # self.update_component()

    @listens('is_playing')
    def _on_playing_state_changed(self):
        self.Play.is_toggled = self.song.is_playing

    @listens('record_mode')
    def _on_record_mode_changed(self):
        self.Record.is_toggled = self.song.record_mode

    @listens('loop')
    def _on_loop_changed(self):
        self.Loop.is_toggled = self.song.loop

    @listens('metronome')
    def _on_metronome_changed(self):
        self.Metronome.is_toggled = self.song.metronome

    @listens('current_song_time')
    def _on_song_position_changed(self):
        try:
            sig_num = self.song.signature_numerator
            sig_den = self.song.signature_denominator
            beat = int(self.song.current_song_time * sig_num * (4.0 / sig_den))
            if beat != self._last_sync_beat:
                self._last_sync_beat = beat
                if self._sync_callback is not None:
                    self._sync_callback()
        except Exception as e:
            print(f"_on_song_position_changed sync error: {e}")

        song_length = self.song.song_length
        if song_length > 0:
            ratio = self.song.current_song_time / song_length
            bt = self.song.get_current_beats_song_time()
            self._try_send_fn_display(54, f"{bt.bars}.{bt.beats}.{bt.sub_division}", ratio * 127)

    @listens('selected_parameter')
    def on_selected_parameter_changed(self):
        selected_param = self.song.view.selected_parameter
        if liveobj_valid(selected_param):
            r = selected_param.max - selected_param.min
            cc_val = (selected_param.value - selected_param.min) / r * 127 if r > 0 else 0
            self._try_send_fn_display(55, selected_param.str_for_value(selected_param.value), cc_val)
            self.on_parameter_changed.subject = selected_param
        else:
            self._try_send_fn_display(55, "No Param")

    @listens('value')
    def on_parameter_changed(self):
        selected_param = self.song.view.selected_parameter
        if liveobj_valid(selected_param):
            r = selected_param.max - selected_param.min
            cc_val = (selected_param.value - selected_param.min) / r * 127 if r > 0 else 0
            self._try_send_fn_display(55, selected_param.str_for_value(selected_param.value), cc_val)

    @Selected_Parameter.value
    def on_Selected_Parameter_changed(self, value, button):
        selected_param = self.song.view.selected_parameter
        if liveobj_valid(selected_param):
            current_value = selected_param.value
            if selected_param.is_quantized:
                sensitivity = 1
            else:
                sensitivity = (selected_param.max - selected_param.min) / 127.0
            value = self.process_relative_encoder(current_value, value, sensitivity=sensitivity, min_val=selected_param.min, max_val=selected_param.max)
            selected_param.value = value
    
    @Song_Position.value
    def on_Song_Position_changed(self, value, button):
        current_pos = self.song.current_song_time
        if value <= 64:
            delta = value * 4
        else:
            delta = (value - 128) * 4
        new_pos = max(0, current_pos + delta)
        self.song.current_song_time = new_pos
    
    def set_control_names(self):
        self.send_display(PARAM_NAME, 0, "Master Vol.")
        self.send_display(PARAM_NAME, 1, "Cue Vol.")
        self.send_display(PARAM_NAME, 4, "Volume")
        self.send_display(PARAM_NAME, 5, "Pan")
        self.send_display(PARAM_NAME, 7, "Sel. Param.")

    def set_parent(self, parent):
        """Permet de définir le parent pour envoyer des messages"""
        self._parent = parent

    def set_sync_callback(self, cb):
        self._sync_callback = cb

    @listens("selected_track")
    def _on_selected_track_changed(self):
        selected_track = self.song.view.selected_track
        tracks = list(self.song.visible_tracks) + list(self.song.return_tracks) + [self.song.master_track]
        t_idx = next((i for i, t in enumerate(tracks) if t == selected_track), 0)
        self._try_send_fn_display(57, selected_track.name, t_idx / max(len(tracks) - 1, 1) * 127)
        self._update_selected_strip()

    def _update_selected_strip(self):
        """Met à jour la channel strip pour la piste sélectionnée"""
        selected_track = self.song.view.selected_track
        
        if selected_track != self._selected_track:
            # Déconnecter l'ancienne piste
            if self._selected_track:
                self._disconnect_track_listeners()
            
            # Connecter la nouvelle piste
            self._selected_track = selected_track
            if self._selected_track:
                self._connect_track_listeners()
                print(f"Channel strip assigned to: {self._selected_track.name}")
            if self._parent is not None:
                selected_track_index = list(self.song.tracks).index(selected_track) if selected_track in self.song.tracks else -1
                # if selected_track_index-1 < 0:
                #     self._parent.send_display(PARAM_NAME, 0+8, "---")
                # elif selected_track_index + 1 >= len(self.song.tracks):
                #     self._parent.send_display(PARAM_NAME, 1+8, "---")
                # self._parent.send_display(PARAM_NAME, 0+8, "Track -")
                # self._parent.send_display(PARAM_NAME, 1+8, "Track +")

    def _connect_track_listeners(self):
        """Connecte les listeners pour la piste sélectionnée"""
        print("Connecting track listeners")
        if self._selected_track and hasattr(self._selected_track, 'mixer_device'):
            self.on_track_volume_changed.subject = self._selected_track.mixer_device.volume
            self.on_track_pan_changed.subject = self._selected_track.mixer_device.panning
            self.on_selected_device_changed.subject = self._selected_track.view
            self._on_track_mute_changed.subject = self._selected_track
            self._on_track_solo_changed.subject = self._selected_track
            self._on_track_arm_changed.subject = self._selected_track if self._selected_track.can_be_armed else None

            self.on_track_volume_changed()
            self.on_track_pan_changed()
            self._on_track_mute_changed()
            self._on_track_solo_changed()
            self._on_track_arm_changed()

    def _disconnect_track_listeners(self):
        """Déconnecte les listeners de l'ancienne piste"""
        self.on_track_volume_changed.subject = None
        self.on_track_pan_changed.subject = None
        self._on_track_mute_changed.subject = None
        self._on_track_solo_changed.subject = None
        self._on_track_arm_changed.subject = None

    @listens('mute')
    def _on_track_mute_changed(self):
        if self._selected_track:
            self.Mute.is_toggled = self._selected_track.mute

    @listens('solo')
    def _on_track_solo_changed(self):
        if self._selected_track:
            self.Solo.is_toggled = self._selected_track.solo

    @listens('arm')
    def _on_track_arm_changed(self):
        if self._selected_track and self._selected_track.can_be_armed:
            self.Record.is_toggled = self._selected_track.arm

    @listens("selected_device")
    def on_selected_device_changed(self):
        print("Selected device changed")

    def _all_navigable_tracks(self):
        return list(self.song.visible_tracks) + list(self.song.return_tracks) + [self.song.master_track]

    @next_track_button.released_immediately
    def on_next_track_button_pressed(self, button):
        tracks = self._all_navigable_tracks()
        selected = self.song.view.selected_track
        current_index = next((i for i, t in enumerate(tracks) if t == selected), 0)
        self.song.view.selected_track = tracks[(current_index + 1) % len(tracks)]
        print(f"Selected track: {self.song.view.selected_track.name}")

    @prev_track_button.released_immediately
    def on_prev_track_button_pressed(self, button):
        tracks = self._all_navigable_tracks()
        selected = self.song.view.selected_track
        current_index = next((i for i, t in enumerate(tracks) if t == selected), 0)
        self.song.view.selected_track = tracks[(current_index - 1) % len(tracks)]
        print(f"Selected track: {self.song.view.selected_track.name}")

    @next_track_button.pressed_delayed
    def on_next_track_button_pressed_delayed(self, button):
        tracks = self._all_navigable_tracks()
        selected = self.song.view.selected_track
        current_index = next((i for i, t in enumerate(tracks) if t == selected), 0)
        if hasattr(tracks[current_index], 'is_foldable') and tracks[current_index].is_foldable and tracks[current_index].view.is_collapsed:
            tracks[current_index].view.is_collapsed = False
            print(f"Track {tracks[current_index].name} expanded")

    @prev_track_button.pressed_delayed
    def on_prev_track_button_pressed_delayed(self, button):
        tracks = self._all_navigable_tracks()
        selected = self.song.view.selected_track
        current_index = next((i for i, t in enumerate(tracks) if t == selected), 0)
        if hasattr(tracks[current_index], 'is_foldable') and tracks[current_index].is_foldable and not tracks[current_index].view.is_collapsed:
            tracks[current_index].view.is_collapsed = True
            print(f"Track {tracks[current_index].name} collapsed")

    @Cue_Volume.value
    def on_Cue_Volume_changed(self, value, button):
        current_value = self.song.master_track.mixer_device.cue_volume.value
        value = self.process_relative_encoder(current_value, value, sensitivity=0.01)
        self.song.master_track.mixer_device.cue_volume.value = value

    @Master_Volume.value
    def on_Master_Volume_changed(self, value, button):
        v = self.song.master_track.mixer_device.volume
        value = self.process_relative_encoder(v.value, value, sensitivity=0.01, min_val=v.min, max_val=v.max)
        v.value = value

    @Track_Volume.value
    def on_Track_Volume_changed(self, value, button):
        if self._selected_track and hasattr(self._selected_track, 'mixer_device'):
            v = self._selected_track.mixer_device.volume
            v.value = self.process_relative_encoder(v.value, value, sensitivity=0.01)

    @Track_Pan.value
    def on_Track_Pan_changed(self, value, button):
        if self._selected_track and hasattr(self._selected_track, 'mixer_device'):
            p = self._selected_track.mixer_device.panning
            p.value = self.process_relative_encoder(p.value, value, sensitivity=0.015, min_val=-1.0, max_val=1.0)

    @tempo.value
    def on_Tempo_changed(self, value, button):
        self.song.tempo = self.process_relative_encoder(self.song.tempo, value, sensitivity=1, min_val=20.0, max_val=300.0)

    @scene_select.value
    def on_Scene_Select_changed(self, value, button):
        scenes = self.song.scenes
        if not scenes:
            return
        current_index = list(scenes).index(self.song.view.selected_scene)
        if value <= 64:
            delta = 1
        else:
            delta = -1
        new_index = clamp(current_index + delta, 0, len(scenes) - 1)
        self.song.view.selected_scene = scenes[new_index]
    
    @next_sends_button.pressed
    def on_next_sends_button_pressed(self, button):
        if self._selected_track and hasattr(self._selected_track, 'mixer_device'):
            sends = self._selected_track.mixer_device.sends
            current_send_index = next((i for i, send in enumerate(sends) if send.is_enabled), 0)
            next_send_index = (current_send_index + 1) % len(sends)
            for i, send in enumerate(sends):
                send.is_enabled = (i == next_send_index)
            print(f"Next Send: {sends[next_send_index].name if sends else 'None'}") 

    @prev_sends_button.pressed
    def on_prev_sends_button_pressed(self, button): 
        if self._selected_track and hasattr(self._selected_track, 'mixer_device'):
            sends = self._selected_track.mixer_device.sends
            current_send_index = next((i for i, send in enumerate(sends) if send.is_enabled), 0)
            prev_send_index = (current_send_index - 1) % len(sends)
            for i, send in enumerate(sends):
                send.is_enabled = (i == prev_send_index)
            print(f"Previous Send: {sends[prev_send_index].name if sends else 'None'}")

    @Mute.toggled
    def on_Mute_toggled(self, is_toggled, button):
        if self._selected_track:
            self._selected_track.mute = is_toggled
            print(f"Track Mute: {self._selected_track.name} = {is_toggled}")
    @Solo.toggled
    def on_Solo_toggled(self, is_toggled, button):
        if self._selected_track:
            self._selected_track.solo = is_toggled
            print(f"Track Solo: {self._selected_track.name} = {is_toggled}")
    @Record.toggled
    def on_Record_toggled(self, is_toggled, button):
        if self._selected_track:
            self._selected_track.arm = is_toggled
            print(f"Track Record Arm: {self._selected_track.name} = {is_toggled}")
    @Play.toggled
    def on_Play_toggled(self, is_toggled, button):
        self.song.is_playing = is_toggled
        print(f"Song Play: {is_toggled}")
    @Loop.toggled
    def on_Loop_toggled(self, is_toggled, button):
        self.song.loop = is_toggled
        print(f"Song Loop: {is_toggled}")
    @Launch_Scene.pressed
    def on_Launch_Scene_pressed(self, button):
        scene = self.song.view.selected_scene
        if liveobj_valid(scene):
            scene.fire()
            print(f"Scene launched: {scene.name}")
    @Default.pressed
    def on_Default_pressed(self, button):
        selected_param = self.song.view.selected_parameter
        if liveobj_valid(selected_param):
            default_value = selected_param.default_value
            selected_param.value = default_value
            self.send_display(PARAM_VALUE, 7, selected_param.str_for_value(default_value))
            print(f"Parameter reset to default: {selected_param.name} = {selected_param.str_for_value(default_value)}")

    @Metronome.toggled
    def on_Metronome_toggled(self, is_toggled, button):
        self.song.metronome = is_toggled
        print(f"Metronome: {is_toggled}")

    @listens(u'value')
    def on_track_volume_changed(self):
        if self._selected_track and hasattr(self._selected_track, 'mixer_device'):
            v = self._selected_track.mixer_device.volume
            self._try_send_fn_display(52, v.str_for_value(v.value), v.value * 127)

    @listens(u'value')
    def on_track_pan_changed(self):
        if self._selected_track and hasattr(self._selected_track, 'mixer_device'):
            p = self._selected_track.mixer_device.panning
            self._try_send_fn_display(53, p.str_for_value(p.value), (p.value + 1.0) * 63.5)

    @listens(u'tempo')
    def on_tempo_changed(self):
        t = self.song.tempo
        self._try_send_fn_display(50, f"{t:.2f} BPM", (t - 20.0) / (300.0 - 20.0) * 127)

    @listens(u'selected_scene')
    def _on_selected_scene_changed(self):
        scene = self.song.view.selected_scene
        if liveobj_valid(scene):
            scenes = list(self.song.scenes)
            idx = scenes.index(scene)
            name = scene.name if scene.name else f"Scene {idx + 1}"
            self._try_send_fn_display(51, name, idx / max(len(scenes) - 1, 1) * 127)

    @listens(u'value')
    def on_cue_volume_changed(self):
        v = self.song.master_track.mixer_device.cue_volume
        self._try_send_fn_display(49, v.str_for_value(v.value), v.value * 127)

    @listens(u'value')
    def on_master_volume_changed(self):
        v = self.song.master_track.mixer_device.volume
        self._try_send_fn_display(48, v.str_for_value(v.value), v.value * 127)

    def send_display(self, param_type, param_index, value):
        if self._parent:
            self._parent.send_display(param_type, param_index, value)
            print(f"Display sent: {param_type}, {param_index}, {value}")

    def _try_send_fn_display(self, fn_id, v_str, cc_val=None):
        fn_map = getattr(self._parent, '_fn_fader_map', None) if self._parent else None
        if fn_map is None:
            return
        fader_idx = fn_map.get(fn_id)
        if fader_idx is not None:
            self.send_display(PARAM_VALUE, fader_idx, v_str)
            if cc_val is not None and self._parent:
                cc = fn_id - 8 if 48 <= fn_id <= 55 else fn_id
                self._parent._send_midi((0xB0 | 7, cc & 0x7F, min(max(int(cc_val), 0), 127)))

    def get_snapshotable_params(self):
        params = [None] * 8
        params[0] = self.song.master_track.mixer_device.volume
        params[1] = self.song.master_track.mixer_device.cue_volume
        if self._selected_track and hasattr(self._selected_track, 'mixer_device'):
            params[4] = self._selected_track.mixer_device.volume
            params[5] = self._selected_track.mixer_device.panning
        params[7] = self.song.view.selected_parameter if liveobj_valid(self.song.view.selected_parameter) else None
        return params

    def _update_fn_sends(self):
        fn_map = getattr(self._parent, '_fn_fader_map', None) if self._parent else None
        if fn_map is None:
            return
        t = self.song.view.selected_track
        if not liveobj_valid(t) or not hasattr(t, 'mixer_device'):
            return
        sends = t.mixer_device.sends
        for send_idx in range(12):
            fn_id = 64 + send_idx
            if fn_id not in fn_map:
                continue
            if send_idx >= len(sends):
                continue
            v = sends[send_idx]
            r = v.max - v.min
            cc_val = (v.value - v.min) / r * 127 if r > 0 else 0
            self._try_send_fn_display(fn_id, v.str_for_value(v.value), cc_val)

    def update_component(self):
        self._update_selected_strip()
        self.on_cue_volume_changed()
        self.on_master_volume_changed()
        self.on_tempo_changed()
        self._on_selected_scene_changed()
        self.on_track_volume_changed()
        self.on_selected_parameter_changed()
        self.on_track_pan_changed()
        self._on_playing_state_changed()
        self._on_record_mode_changed()
        self._on_loop_changed()
        self._on_metronome_changed()
        self._on_selected_track_changed()
        self._update_fn_sends()

    def _send_all_value_displays(self):
        print("=== _send_all_value_displays called ===")
        self.send_display(PARAM_VALUE, 0, self.song.master_track.mixer_device.volume.str_for_value(
            self.song.master_track.mixer_device.volume.value))
        self.send_display(PARAM_VALUE, 1, self.song.master_track.mixer_device.cue_volume.str_for_value(
            self.song.master_track.mixer_device.cue_volume.value))
        self.send_display(PARAM_VALUE, 2, f"{self.song.tempo:.2f} BPM")
        scene = self.song.view.selected_scene
        if liveobj_valid(scene):
            scenes = list(self.song.scenes)
            idx = scenes.index(scene)
            self.send_display(PARAM_VALUE, 3, scene.name if scene.name else f"Scene {idx + 1}")
        if self._selected_track and hasattr(self._selected_track, 'mixer_device'):
            self.send_display(PARAM_VALUE, 4, self._selected_track.mixer_device.volume.str_for_value(
                self._selected_track.mixer_device.volume.value))
            self.send_display(PARAM_VALUE, 5, self._selected_track.mixer_device.panning.str_for_value(
                self._selected_track.mixer_device.panning.value))
        bt = self.song.get_current_beats_song_time()
        self.send_display(PARAM_VALUE, 6, f"{bt.bars}.{bt.beats}.{bt.sub_division}")
        selected_param = self.song.view.selected_parameter
        if liveobj_valid(selected_param):
            self.send_display(PARAM_VALUE, 7, selected_param.str_for_value(selected_param.value))

