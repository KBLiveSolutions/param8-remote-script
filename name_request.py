import Live
import json
import logging
from ableton.v2.base import liveobj_valid

logger = logging.getLogger(__name__)
def print(text):
    logger.warning(text)


class NameRequestMixin:
    """Double-press on latch: assign selected Live parameter to a control with live value watcher."""

    def _handle_name_request(self, idx, is_button):
        selected_param = self.song.view.selected_parameter
        if not liveobj_valid(selected_param):
            print(f"NameRequest: no parameter selected")
            return
        name = selected_param.name[:11]
        preset = self.active_mode
        if preset >= 24:
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

    def _send_preset_names(self, preset):
        data_key = "param8_mappings"
        try:
            raw = self.song.get_data(data_key, "")
            mappings = json.loads(raw) if raw else {}
        except Exception:
            return
        for key, info in mappings.items():
            parts = key.split(":")
            if len(parts) != 3 or int(parts[0]) != preset:
                continue
            is_button = parts[1] == "b"
            idx = int(parts[2])
            name = info["param"][:11]
            message = [240, 111, 15, preset, idx, 1 if is_button else 0]
            for c in name:
                message.append(ord(c) & 0x7F)
            message.append(247)
            self._send_midi(tuple(message))

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
        sent_presets = set()
        for key, info in mappings.items():
            parts = key.split(":")
            if len(parts) != 3:
                continue
            preset = int(parts[0])
            is_button = parts[1] == "b"
            idx = int(parts[2])
            sent_presets.add(preset)
            param = self._find_param_by_names(info["track"], info["device"], info["param"])
            if param and not is_button:
                self._watch_parameter(preset, idx, param)
                print(f"NameRequest: restored watcher for '{info['param']}' on encoder {idx} preset {preset}")
            elif not param:
                print(f"NameRequest: could not find param '{info['param']}' on '{info['device']}' ({info['track']})")
        for p in sent_presets:
            self._send_preset_names(p)

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
