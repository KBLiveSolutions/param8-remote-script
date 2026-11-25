import logging
from ableton.v2.base import clamp, liveobj_valid

logger = logging.getLogger(__name__)
def print(text):
    logger.warning(text)


class FnDispatchMixin:
    # fnId == CC everywhere. Encoder fn IDs are intercepted in process_midi_bytes.
    # Button fn IDs are handled by registered ButtonElements in param8._fn_button_elements (CC22 excepted).
    _ENCODER_FN_IDS = {
        44, 45,                       # Track Vol, Track Pan (selected track — not MixerComponent)
        # 63,                           # Groove
        58,                           # Select Preset
        *range(80, 112),              # Device Params 1-32
    }
    def _dispatch_fn_encoder(self, fn_id, val):
        try:
            m = self._mixer
            song = self.song
            rel = m.process_relative_encoder
            v_str = None
            norm_val = None

            if fn_id == 44:  # Track Volume (selected track)
                track = song.view.selected_track
                if liveobj_valid(track):
                    p = track.mixer_device.volume
                    p.value = rel(p.value, val, sensitivity=0.01, min_val=p.min, max_val=p.max)
                    v_str = p.str_for_value(p.value)
                    r = p.max - p.min
                    norm_val = (p.value - p.min) / r * 127 if r > 0 else 0
            elif fn_id == 45:  # Track Pan (selected track)
                track = song.view.selected_track
                if liveobj_valid(track):
                    p = track.mixer_device.panning
                    p.value = rel(p.value, val, sensitivity=0.01, min_val=p.min, max_val=p.max)
                    v_str = p.str_for_value(p.value)
                    r = p.max - p.min
                    norm_val = (p.value - p.min) / r * 127 if r > 0 else 0
            # elif fn_id == 63:  # Groove (0–130%)
            #     song.groove_amount = rel(song.groove_amount, val, sensitivity=0.005, min_val=0.0, max_val=1.3)
            #     v_str = f"{song.groove_amount * 100:.1f}%"
            #     norm_val = song.groove_amount / 1.3 * 127
            elif 80 <= fn_id <= 111:  # Device Params 1-32
                param_idx = fn_id - 80
                device = song.view.selected_device
                if liveobj_valid(device) and len(device.parameters) > param_idx + 1:
                    p = device.parameters[param_idx + 1]  # +1: skip Device On/Off
                    p.value = rel(p.value, val, sensitivity=0.01, min_val=p.min, max_val=p.max)
                    v_str = p.str_for_value(p.value)
                    r = p.max - p.min
                    norm_val = (p.value - p.min) / r * 127 if r > 0 else 0
            # 58 (Select Preset) not yet implemented

            fader_idx = self._fn_fader_map.get(fn_id)
            if fader_idx is not None and v_str is not None:
                self.send_display(1, fader_idx, v_str)
                if norm_val is not None:
                    self._send_midi((0xB0 | 7, fn_id & 0x7F, min(max(int(norm_val), 0), 127)))
        except Exception as e:
            print(f"fn_enc dispatch fn_id={fn_id}: {e}")

    def _dispatch_fn_button(self, fn_id, val):
        if val <= 63:
            if fn_id in (119, 18):
                self._skip_held = False
            return
        try:
            song = self.song
            # Global
            if   fn_id == 2:  song.stop_playing()
            elif fn_id == 3:  song.undo()
            elif fn_id == 4:  song.redo()
            elif fn_id == 5:  song.tempo = min(song.tempo + 1.0, 999.0)
            elif fn_id == 6:  song.tempo = max(song.tempo - 1.0, 20.0)
            elif fn_id == 7:
                song.session_record = not song.session_record
                self._send_midi((0xB0 | 7, 7, 127 if song.session_record else 0))
            elif fn_id == 8:  song.re_enable_automation()
            # Arrangement (113-119: moved from 11-17 to avoid conflict with device mode encoder CCs 11-17)
            elif fn_id == 113: song.continue_playing()
            elif fn_id == 114: song.current_song_time = 0.0
            elif fn_id == 115:
                song.back_to_arranger = not song.back_to_arranger
                self._send_midi((0xB0 | 7, 115, 127 if song.back_to_arranger else 0))
            elif fn_id == 116:
                song.record_mode = not song.record_mode
                self._send_midi((0xB0 | 7, 116, 127 if song.record_mode else 0))
            elif fn_id == 117:
                t = song.current_song_time
                cues = sorted(song.cue_points, key=lambda c: c.time)
                nxt = next((c for c in reversed(cues) if c.time < t - 0.01), None)
                if nxt: song.current_song_time = nxt.time
            elif fn_id == 118:
                t = song.current_song_time
                cues = sorted(song.cue_points, key=lambda c: c.time)
                nxt = next((c for c in cues if c.time > t + 0.01), None)
                if nxt: song.current_song_time = nxt.time
            elif fn_id in (119, 18):
                self._skip_held = True
                self._do_skip(fn_id)
                self.schedule_message(4, lambda: self._repeat_skip(fn_id))
            # Session
            elif fn_id == 48:
                scenes = list(song.scenes)
                idx = scenes.index(song.view.selected_scene)
                song.view.selected_scene = scenes[min(len(scenes) - 1, idx + 1)]
            elif fn_id == 49:
                scenes = list(song.scenes)
                idx = scenes.index(song.view.selected_scene)
                song.view.selected_scene = scenes[max(0, idx - 1)]
            elif fn_id == 28: song.stop_all_clips()
            elif fn_id == 36: self._toggle_device_lock()
        except Exception as e:
            print(f"fn_btn dispatch fn_id={fn_id}: {e}")

    def _do_skip(self, fn_id):
        song = self.song
        if fn_id == 119:
            song.current_song_time = song.current_song_time + 4.0
        else:
            song.current_song_time = max(0.0, song.current_song_time - 4.0)

    def _repeat_skip(self, fn_id):
        if getattr(self, '_skip_held', False):
            self._do_skip(fn_id)
            self.schedule_message(2, lambda: self._repeat_skip(fn_id))
