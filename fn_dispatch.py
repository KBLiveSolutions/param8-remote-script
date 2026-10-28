import Live
import logging
from ableton.v2.base import clamp, liveobj_valid

logger = logging.getLogger(__name__)
def print(text):
    logger.warning(text)


class FnDispatchMixin:
    # fnIds 48-55 → remapped to CCs 40-47 (offset -8) → fall through to MixerComponent.
    # fnIds 1,9,10,19,32,33,34,35 → remapped to CCs 52,50,56,53,54,55,51,57 → fall through.
    _ENCODER_FN_IDS = {
        51, 52, 53, 56, 57,           # Scroll Scenes, Track Vol, Track Pan, Groove, Track Sel
        58, 59, 60, 61, 62,           # Select Preset, Loop Pos, Loop Len, H.Zoom, Jump Mkr
        *range(64, 76),               # Sends A-L
        *range(80, 112),              # Device Params 1-32
    }
    _BUTTON_FN_IDS = {
        2, 3, 4, 5, 6, 7, 8,         # Stop, Undo, Redo, Tempo+1, Tempo-1, Capture, Re-enable
        11, 12, 13, 14, 15, 16, 17, 18,  # Arrangement
        20, 21, 22, 23,               # Session
        24, 25, 26, 27, 28, 29, 30, 31,  # Navigation
        36, 37, 38, 39,               # Variations (Randomize fn_id 40 omitted: CC 40 = Master Vol encoder)
    }

    def _dispatch_fn_encoder(self, fn_id, val):
        try:
            m = self._mixer
            song = self.song
            rel = m.process_relative_encoder
            v_str = None
            norm_val = None

            if fn_id == 56:  # Groove
                song.groove_amount = rel(song.groove_amount, val)
                v_str = f"{song.groove_amount * 100:.1f}%"
                norm_val = song.groove_amount * 127
            elif fn_id == 57:  # Track Select
                tracks = list(song.visible_tracks) + list(song.return_tracks) + [song.master_track]
                idx = next((i for i, t in enumerate(tracks) if t == song.view.selected_track), 0)
                delta = 1 if val <= 64 else -1
                idx = clamp(idx + delta, 0, len(tracks) - 1)
                song.view.selected_track = tracks[idx]
                v_str = song.view.selected_track.name
                norm_val = idx / max(len(tracks) - 1, 1) * 127
            elif fn_id == 59:  # Loop Position
                delta = 0.5 if val <= 64 else -0.5
                song.loop_start = max(0.0, song.loop_start + delta)
                v_str = f"{song.loop_start:.2f}"
            elif fn_id == 60:  # Loop Length
                delta = 0.5 if val <= 64 else -0.5
                song.loop_length = max(0.125, song.loop_length + delta)
                v_str = f"{song.loop_length:.2f}"
            elif fn_id == 62:  # Jump Marker
                t = song.current_song_time
                cues = sorted(song.cue_points, key=lambda c: c.time)
                if cues:
                    if val <= 64:
                        nxt = next((c for c in cues if c.time > t + 0.01), cues[0])
                    else:
                        nxt = next((c for c in reversed(cues) if c.time < t - 0.01), cues[-1])
                    song.current_song_time = nxt.time
                    v_str = nxt.name if nxt.name else f"{nxt.time:.2f}"
            elif 64 <= fn_id <= 75:  # Sends A-L
                send_idx = fn_id - 64
                t = song.view.selected_track
                n_sends = len(t.mixer_device.sends) if liveobj_valid(t) and hasattr(t, 'mixer_device') else -1
                print(f"Send dispatch: idx={send_idx} n_sends={n_sends} track={t.name if liveobj_valid(t) else 'inv'}")
                if n_sends > send_idx:
                    v = t.mixer_device.sends[send_idx]
                    old_v = v.value
                    v.value = rel(v.value, val, sensitivity=0.01, min_val=v.min, max_val=v.max)
                    print(f"  {old_v:.4f} -> {v.value:.4f} (min={v.min} max={v.max})")
                    v_str = v.str_for_value(v.value)
                    r = v.max - v.min
                    norm_val = (v.value - v.min) / r * 127 if r > 0 else 0
            elif 80 <= fn_id <= 111:  # Device Params 1-32
                param_idx = fn_id - 80
                device = song.view.selected_device
                if liveobj_valid(device) and len(device.parameters) > param_idx + 1:
                    p = device.parameters[param_idx + 1]  # +1: skip Device On/Off
                    p.value = rel(p.value, val, sensitivity=0.01, min_val=p.min, max_val=p.max)
                    v_str = p.str_for_value(p.value)
                    r = p.max - p.min
                    norm_val = (p.value - p.min) / r * 127 if r > 0 else 0
            # 58 (Select Preset), 61 (H.Zoom) not yet implemented

            fader_idx = self._fn_fader_map.get(fn_id)
            if fader_idx is not None and v_str is not None:
                self.send_display(1, fader_idx, v_str)
                if norm_val is not None:
                    self._send_midi((0xB0 | 7, fn_id & 0x7F, min(max(int(norm_val), 0), 127)))
        except Exception as e:
            print(f"fn_enc dispatch fn_id={fn_id}: {e}")

    def _dispatch_fn_button(self, fn_id, val):
        if val <= 63:
            return
        try:
            song = self.song
            # Global
            if   fn_id == 2:  song.stop_playing()
            elif fn_id == 3:  song.undo()
            elif fn_id == 4:  song.redo()
            elif fn_id == 5:  song.tempo = min(song.tempo + 1.0, 999.0)
            elif fn_id == 6:  song.tempo = max(song.tempo - 1.0, 60.0)
            elif fn_id == 7:  song.capture_midi()
            elif fn_id == 8:  song.re_enable_automation()
            # Arrangement
            elif fn_id == 11: song.continue_playing()
            elif fn_id == 12: song.current_song_time = 0.0
            elif fn_id == 13: song.back_to_arranger = not song.back_to_arranger
            elif fn_id == 14: song.record_mode = not song.record_mode
            elif fn_id == 15:
                t = song.current_song_time
                cues = sorted(song.cue_points, key=lambda c: c.time)
                nxt = next((c for c in reversed(cues) if c.time < t - 0.01), None)
                if nxt: song.current_song_time = nxt.time
            elif fn_id == 16:
                t = song.current_song_time
                cues = sorted(song.cue_points, key=lambda c: c.time)
                nxt = next((c for c in cues if c.time > t + 0.01), None)
                if nxt: song.current_song_time = nxt.time
            elif fn_id == 17: song.current_song_time = song.current_song_time + 4.0
            elif fn_id == 18: song.current_song_time = max(0.0, song.current_song_time - 4.0)
            # Session
            elif fn_id == 20:
                scenes = list(song.scenes)
                idx = scenes.index(song.view.selected_scene)
                song.view.selected_scene = scenes[min(len(scenes) - 1, idx + 1)]
            elif fn_id == 21:
                scenes = list(song.scenes)
                idx = scenes.index(song.view.selected_scene)
                song.view.selected_scene = scenes[max(0, idx - 1)]
            elif fn_id == 22: song.session_record = not song.session_record
            elif fn_id == 23: song.stop_all_clips()
            # Navigation
            elif fn_id == 24:
                tracks = list(song.visible_tracks) + list(song.return_tracks) + [song.master_track]
                idx = next((i for i, t in enumerate(tracks) if t == song.view.selected_track), 0)
                song.view.selected_track = tracks[max(0, idx - 1)]
            elif fn_id == 25:
                tracks = list(song.visible_tracks) + list(song.return_tracks) + [song.master_track]
                idx = next((i for i, t in enumerate(tracks) if t == song.view.selected_track), 0)
                song.view.selected_track = tracks[min(len(tracks) - 1, idx + 1)]
            elif fn_id == 26: self._device_navigation._scroll_device_chain(
                    Live.Application.Application.View.NavDirection.left)
            elif fn_id == 27: self._device_navigation._scroll_device_chain(
                    Live.Application.Application.View.NavDirection.right)
            # 28 (Bank-), 29 (Bank+), 30 (Preset-), 31 (Preset+) not yet implemented
            # Device
            # 36-40 (Variations, Randomize) not yet implemented
        except Exception as e:
            print(f"fn_btn dispatch fn_id={fn_id}: {e}")
