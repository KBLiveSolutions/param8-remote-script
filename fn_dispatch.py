import Live
import logging
from ableton.v2.base import clamp, liveobj_valid

logger = logging.getLogger(__name__)
def print(text):
    logger.warning(text)


class FnDispatchMixin:
    # CC numbers intercepted before MixerComponent in user preset mode.
    # fnIds 90,87,96,83,73 → remapped to CCs 41,42,45,46,47 → fall through to MixerComponent.
    # fnIds 1,3,14,31 → remapped to CCs 52,56,53,50 → fall through to MixerComponent.
    _ENCODER_FN_IDS = {37, 89, 86, 91, 112, 59, 60, 84, 85, 88, 99}
    _BUTTON_FN_IDS  = {2, 4, 5, 6, 7, 8, 9, 15, 16, 17, 18, 19,
                       26, 27, 28, 32, 33, 34, 40, 43, 44, 48, 49, 51, 54}

    def _dispatch_fn_encoder(self, fn_id, val):
        try:
            m = self._mixer
            song = self.song
            rel = m.process_relative_encoder
            v_str = None

            if fn_id == 37:    # Global Groove
                song.groove_amount = rel(song.groove_amount, val)
                v_str = f"{song.groove_amount * 100:.1f}%"
            elif fn_id == 89:  # Master Volume
                v = song.master_track.mixer_device.volume
                v.value = rel(v.value, val, sensitivity=0.01, min_val=v.min, max_val=v.max)
                v_str = v.str_for_value(v.value)
            elif fn_id == 86:  # Scroll Scenes
                scenes = list(song.scenes)
                if scenes:
                    idx = scenes.index(song.view.selected_scene)
                    delta = 1 if val <= 64 else -1
                    song.view.selected_scene = scenes[clamp(idx + delta, 0, len(scenes) - 1)]
                    v_str = song.view.selected_scene.name
            elif fn_id == 91:  # Track Volume
                t = song.view.selected_track
                if liveobj_valid(t) and hasattr(t, 'mixer_device'):
                    v = t.mixer_device.volume
                    v.value = rel(v.value, val, sensitivity=0.01, min_val=v.min, max_val=v.max)
                    v_str = v.str_for_value(v.value)
            elif fn_id == 112: # Track Select
                tracks = list(song.visible_tracks) + list(song.return_tracks) + [song.master_track]
                idx = next((i for i, t in enumerate(tracks) if t == song.view.selected_track), 0)
                delta = 1 if val <= 64 else -1
                song.view.selected_track = tracks[clamp(idx + delta, 0, len(tracks) - 1)]
                v_str = song.view.selected_track.name
            elif fn_id == 59:  # Send A
                t = song.view.selected_track
                if liveobj_valid(t) and hasattr(t, 'mixer_device') and t.mixer_device.sends:
                    v = t.mixer_device.sends[0]
                    v.value = rel(v.value, val, sensitivity=0.01, min_val=v.min, max_val=v.max)
                    v_str = v.str_for_value(v.value)
            elif fn_id == 60:  # Send B
                t = song.view.selected_track
                if liveobj_valid(t) and hasattr(t, 'mixer_device') and len(t.mixer_device.sends) > 1:
                    v = t.mixer_device.sends[1]
                    v.value = rel(v.value, val, sensitivity=0.01, min_val=v.min, max_val=v.max)
                    v_str = v.str_for_value(v.value)
            elif fn_id == 84:  # Loop Position
                delta = 0.5 if val <= 64 else -0.5
                song.loop_start = max(0.0, song.loop_start + delta)
                v_str = f"{song.loop_start:.2f}"
            elif fn_id == 85:  # Loop Length
                delta = 0.5 if val <= 64 else -0.5
                song.loop_length = max(0.125, song.loop_length + delta)
                v_str = f"{song.loop_length:.2f}"
            elif fn_id == 88:  # Jump Marker
                t = song.current_song_time
                cues = sorted(song.cue_points, key=lambda c: c.time)
                if cues:
                    if val <= 64:
                        nxt = next((c for c in cues if c.time > t + 0.01), cues[0])
                    else:
                        nxt = next((c for c in reversed(cues) if c.time < t - 0.01), cues[-1])
                    song.current_song_time = nxt.time
                    v_str = nxt.name if nxt.name else f"{nxt.time:.2f}"

            fader_idx = self._fn_fader_map.get(fn_id)
            if fader_idx is not None and v_str is not None:
                self.send_display(1, fader_idx, v_str)
        except Exception as e:
            print(f"fn_enc dispatch fn_id={fn_id}: {e}")

    def _dispatch_fn_button(self, fn_id, val):
        if val <= 63:
            return
        try:
            song = self.song
            if   fn_id == 2:  song.stop_playing()
            elif fn_id == 4:  song.continue_playing()
            elif fn_id == 5:  song.record_mode = not song.record_mode
            elif fn_id == 6:  song.undo()
            elif fn_id == 7:  song.redo()
            elif fn_id == 8:  song.tempo = min(song.tempo + 1.0, 999.0)
            elif fn_id == 9:  song.tempo = max(song.tempo - 1.0, 60.0)
            elif fn_id == 15:
                scenes = list(song.scenes)
                idx = scenes.index(song.view.selected_scene)
                song.view.selected_scene = scenes[max(0, idx - 1)]
            elif fn_id == 16:
                scenes = list(song.scenes)
                idx = scenes.index(song.view.selected_scene)
                song.view.selected_scene = scenes[min(len(scenes) - 1, idx + 1)]
            elif fn_id == 17: song.session_record = not song.session_record
            elif fn_id == 18:
                t = song.current_song_time
                cues = sorted(song.cue_points, key=lambda c: c.time)
                nxt = next((c for c in reversed(cues) if c.time < t - 0.01), None)
                if nxt: song.current_song_time = nxt.time
            elif fn_id == 19:
                t = song.current_song_time
                cues = sorted(song.cue_points, key=lambda c: c.time)
                nxt = next((c for c in cues if c.time > t + 0.01), None)
                if nxt: song.current_song_time = nxt.time
            elif fn_id == 26: song.current_song_time = 0.0
            elif fn_id == 27: song.capture_midi()
            elif fn_id == 28: song.re_enable_automation()
            elif fn_id == 32: song.back_to_arranger = not song.back_to_arranger
            elif fn_id == 33: song.current_song_time = song.current_song_time + 4.0
            elif fn_id == 34: song.current_song_time = max(0.0, song.current_song_time - 4.0)
            elif fn_id == 40: song.stop_all_clips()
            elif fn_id == 43:
                tracks = list(song.visible_tracks) + list(song.return_tracks) + [song.master_track]
                idx = next((i for i, t in enumerate(tracks) if t == song.view.selected_track), 0)
                song.view.selected_track = tracks[max(0, idx - 1)]
            elif fn_id == 44:
                tracks = list(song.visible_tracks) + list(song.return_tracks) + [song.master_track]
                idx = next((i for i, t in enumerate(tracks) if t == song.view.selected_track), 0)
                song.view.selected_track = tracks[min(len(tracks) - 1, idx + 1)]
            elif fn_id == 48: self._device_navigation._scroll_device_chain(
                    Live.Application.Application.View.NavDirection.left)
            elif fn_id == 49: self._device_navigation._scroll_device_chain(
                    Live.Application.Application.View.NavDirection.right)
        except Exception as e:
            print(f"fn_btn dispatch fn_id={fn_id}: {e}")
