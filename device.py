# uncompyle6 version 3.9.1
# Python bytecode version base 3.7.0 (3394)
# Decompiled from: Python 3.12.2 (main, Feb  6 2024, 20:19:44) [Clang 15.0.0 (clang-1500.1.0.2.5)]
# Embedded file name: output/Live/mac_universal_64_static/Release/python-bundle/MIDI Remote Scripts/novation/simple_device.py
# Compiled at: 2024-03-09 01:30:22
# Size of source mod 2**32: 6020 bytes
from __future__ import absolute_import, print_function, unicode_literals
import json, os
from _Generic.Devices import DEVICE_DICT

def _auto_banks(device):
    params = list(device.parameters[1:])
    if not params:
        return None
    banks = []
    for i in range(0, len(params), 8):
        bank = params[i:i+8]
        while len(bank) < 8:
            bank.append(None)
        banks.append(bank)
    return banks

_MAPPINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mappings.json")

def _load_custom_mappings():
    try:
        with open(_MAPPINGS_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _resolve_selector_slots(bank, sel, custom_display):
    values = sel["values"]
    idx = sel["index"]
    val = values[idx] if idx < len(values) else ""
    param_by_name = sel["param_by_name"]
    base_slot = sel["base_slot"]
    for t_offset, tmpl in enumerate(sel["template"]):
        t_slot = base_slot + 1 + t_offset
        if t_slot < 8:
            pname = tmpl.format(val)
            bank[t_slot] = param_by_name.get(pname)
            if sel.get("display"):
                dtmpl = sel["display"]
                if t_offset < len(dtmpl):
                    custom_display[pname] = dtmpl[t_offset].format(val) if "{}" in dtmpl[t_offset] else dtmpl[t_offset]

def _resolve_custom_banks(device, mapping_entry, saved_index=None):
    param_by_name = {}
    for p in device.parameters:
        param_by_name[p.name] = p
    banks = []
    custom_display = {}
    conditionals = {}
    selectors = {}
    for bank_idx, bank_def in enumerate(mapping_entry.get("banks", [])):
        bank = []
        skip_until = -1
        for slot_idx, slot in enumerate(bank_def.get("parameters", [])[:8]):
            if slot_idx < skip_until:
                continue
            if isinstance(slot, dict):
                if "selector" in slot:
                    values = slot.get("values", [])
                    template = slot.get("template", [])
                    view_prop = slot.get("view_property")
                    dev_prop = slot.get("device_property")
                    init_idx = 0
                    if view_prop and hasattr(device, 'view') and hasattr(device.view, view_prop):
                        init_idx = getattr(device.view, view_prop, 0)
                    elif dev_prop and hasattr(device, dev_prop):
                        init_idx = int(getattr(device, dev_prop, 0))
                    elif saved_index is not None:
                        init_idx = saved_index.get(slot["selector"], 0)
                    sel = {
                        "name": slot["selector"],
                        "values": values,
                        "template": template,
                        "display": slot.get("display"),
                        "index": init_idx,
                        "param_by_name": param_by_name,
                        "base_slot": slot_idx,
                        "view_property": view_prop,
                        "device_property": dev_prop,
                    }
                    selectors[(bank_idx, slot_idx)] = sel
                    bank.append(None)
                    for t_offset in range(len(template)):
                        bank.append(None)
                    skip_until = slot_idx + 1 + len(template)
                    _resolve_selector_slots(bank, sel, custom_display)
                    continue
                elif "watch" in slot:
                    watch_param = param_by_name.get(slot["watch"])
                    if watch_param:
                        resolved_map = {}
                        resolved_names = {}
                        resolved_displays = {}
                        for v, pn in slot["map"].items():
                            if isinstance(pn, dict):
                                pname = pn.get("name", "")
                                resolved_map[v] = param_by_name.get(pname)
                                resolved_names[v] = pname
                                if pn.get("display"):
                                    resolved_displays[v] = pn["display"]
                            elif pn:
                                resolved_map[v] = param_by_name.get(pn)
                                resolved_names[v] = pn
                        cond = {
                            "watch": watch_param,
                            "map": resolved_map,
                            "map_names": resolved_names,
                            "map_displays": resolved_displays,
                            "display": slot.get("display"),
                        }
                        conditionals[(bank_idx, slot_idx)] = cond
                        current_val = str(watch_param)
                        mapped_name = resolved_names.get(current_val) or resolved_names.get("*", "")
                        bank.append(param_by_name.get(mapped_name) if mapped_name else None)
                        disp = resolved_displays.get(current_val) or resolved_displays.get("*")
                        if disp and mapped_name:
                            custom_display[mapped_name] = disp
                    else:
                        bank.append(None)
                else:
                    name = slot.get("name", "")
                    disp = slot.get("display", "")
                    if name and disp:
                        custom_display[name] = disp
                    bank.append(param_by_name.get(name) if name else None)
            elif slot:
                bank.append(param_by_name.get(slot))
            else:
                bank.append(None)
        while len(bank) < 8:
            bank.append(None)
        banks.append(bank)
    return banks if banks else None, custom_display, conditionals, selectors
from ableton.v2.base import EventObject, clamp, depends, listens, liveobj_valid, nop, listens_group
from ableton.v2.control_surface import Component
from ableton.v2.control_surface.control import ToggleButtonControl, control_list, ButtonControl
# from .fixed_radio_button_group import FixedRadioButtonGroup
from . import colors

def release_control(control):
    if liveobj_valid(control):
        control.release_parameter()

PARAM_NAME = 0
PARAM_VALUE = 1
BANK_NAME = 2
DEVICE_NAME = 3

class SimpleDeviceParameterComponent(Component):
    bank_select_buttons = control_list(ButtonControl, control_count=15, color=colors.blue, pressed_color=colors.white)
    # bank_select_buttons = FixedRadioButtonGroup(control_count=8,
    #   unchecked_color="Mode.Device.Bank.Available",
    #   checked_color="Mode.Device.Bank.Selected")
    device_lock_button = ToggleButtonControl()
    next_device_button = ButtonControl()
    prev_device_button = ButtonControl()
    next_bank_button = ButtonControl()
    prev_bank_button = ButtonControl()
    Compare = ToggleButtonControl(toggled_color='Mixer.ArmOn', untoggled_color='Mixer.ArmOff')
    DeviceOn = ToggleButtonControl(toggled_color='Mixer.ArmOn', untoggled_color='Mixer.ArmOff')

    @next_bank_button.pressed
    def bank_up_button_pressed(self, button):
        print("BANK UP")
        self.select_bank(1)

    @prev_bank_button.pressed
    def bank_down_button_pressed(self, button):
        print("BANK DOWN")
        self.select_bank(-1)

    @bank_select_buttons.pressed
    def bank_select_buttons_pressed(self, button):
        print("BANK", button.index)
        self.select_bank(int(button.index / 2))

    @Compare.toggled
    def compare_toggled(self, is_toggled, button):
        print("TOGGLING COMPARE", self._device.can_compare_ab)
        if self._device.can_compare_ab:
            self._device.is_using_compare_preset_b = 1 if is_toggled else 0
        print(f"Compare Mode: {is_toggled}")
    
    @DeviceOn.toggled
    def device_on_toggled(self, is_toggled, button):
        if liveobj_valid(self._device):
            for p in self._device.parameters:
                if p.name == 'Device On':
                    p.value = 1.0 if is_toggled else 0.0
                    break
            print(f"Device On: {is_toggled}")

    @listens('value')
    def _on_device_on_changed(self):
        if self.device_control_enabled and self._device_on_param and liveobj_valid(self._device_on_param):
            is_on = self._device_on_param.value > 0.5
            self.DeviceOn.is_toggled = is_on
            print(f"Device On changed: {is_on}")

    @listens('is_using_compare_preset_b')
    def _on_compare_changed(self):
        if self.device_control_enabled and liveobj_valid(self._device):
            is_b = self._device.is_using_compare_preset_b
            self.Compare.is_toggled = is_b
            print(f"Compare changed: {is_b}")

    def select_bank(self, factor):
        new_index = self._clamp_to_bank_size(self._bank_index + factor)
        if new_index != self._bank_index:
            self.bank_index = new_index

    @depends(device_provider=None)
    def __init__(self, parent = None, device_provider=None, device_bank_registry=None, toggle_lock=None, use_parameter_banks=False, *a, **k):
        (super(SimpleDeviceParameterComponent, self).__init__)(*a, **k)
        self.device_control_enabled = False
        self.sysex_smoother = 0
        self._parent = parent
        self._refresh_scheduled = False
        self.control_offset = 0
        self._toggle_lock = toggle_lock
        self._use_parameter_banks = use_parameter_banks
        self._device = None
        self._banks = []
        self._bank_index = 0
        self._custom_bank_names = None
        self._custom_display_names = {}
        self._conditionals = {}
        self._selectors = {}
        self._selector_saved_index = {}
        self._selector_view_slots = self.register_disconnectable(EventObject())
        self._parameter_controls = None
        self._empty_control_slots = self.register_disconnectable(EventObject())
        self._device_param_slots = self.register_disconnectable(EventObject())
        self._chain_selector_slot = self.register_disconnectable(EventObject())
        self._device_bank_registry = device_bank_registry
        self._device_provider = device_provider
        self._SimpleDeviceParameterComponent__on_provided_device_changed.subject = device_provider
        self._SimpleDeviceParameterComponent__on_provided_device_changed()
        if toggle_lock:
            self._SimpleDeviceParameterComponent__on_is_locked_to_device_changed.subject = self._device_provider
            self._SimpleDeviceParameterComponent__on_is_locked_to_device_changed()

    # @bank_select_buttons.checked
    # def bank_select_buttons(self, button):
    #     self._on_bank_select_button_checked(button)

    def _on_bank_select_button_checked(self, button):
        self.bank_index = button.index

    # @bank_select_buttons.value
    # def bank_select_buttons(self, value, _):
    #     if not value:
    #         self._on_bank_select_button_released()

    def _on_bank_select_button_released(self):
        pass

    def _setup_selector_view_listeners(self):
        if not liveobj_valid(self._device):
            return
        registered = set()
        for (bank_idx, slot_idx), sel in self._selectors.items():
            vp = sel.get("view_property")
            if vp and vp not in registered and hasattr(self._device, 'view') and hasattr(self._device.view, vp):
                self._selector_view_slots.register_slot(self._device.view, self._on_selector_view_changed, vp)
                registered.add(("view", vp))
            dp = sel.get("device_property")
            if dp and ("device", dp) not in registered and hasattr(self._device, dp):
                self._selector_view_slots.register_slot(self._device, self._on_selector_view_changed, dp)
                registered.add(("device", dp))

    def _on_selector_view_changed(self):
        if not self._parameter_controls or not liveobj_valid(self._device):
            return
        changed = False
        for (bank_idx, slot_idx), sel in self._selectors.items():
            if bank_idx != self._bank_index:
                continue
            new_idx = sel["index"]
            vp = sel.get("view_property")
            dp = sel.get("device_property")
            if vp and hasattr(self._device, 'view') and hasattr(self._device.view, vp):
                new_idx = getattr(self._device.view, vp, 0)
            elif dp and hasattr(self._device, dp):
                new_idx = int(getattr(self._device, dp, 0))
            if new_idx != sel["index"]:
                sel["index"] = new_idx
                self._selector_saved_index[sel["name"]] = new_idx
                bank = self._banks[bank_idx]
                _resolve_selector_slots(bank, sel, self._custom_display_names)
                changed = True
        if changed:
            self._empty_control_slots.disconnect()
            self._connect_parameters()

    def _on_device_param_value_changed(self):
        if not self._parameter_controls or not liveobj_valid(self._device):
            return
        changed = False
        for (bank_idx, slot_idx), cond in self._conditionals.items():
            if bank_idx != self._bank_index:
                continue
            watch = cond["watch"]
            if not liveobj_valid(watch):
                continue
            current_val = str(watch)
            mapped_name = cond["map_names"].get(current_val) or cond["map_names"].get("*", "")
            new_param = cond["map"].get(current_val) or cond["map"].get("*")
            old_param = self._banks[bank_idx][slot_idx]
            if new_param is not old_param:
                self._banks[bank_idx][slot_idx] = new_param
                disp = cond.get("map_displays", {}).get(current_val) or cond.get("map_displays", {}).get("*")
                if disp and new_param and liveobj_valid(new_param):
                    self._custom_display_names[new_param.name] = disp
                changed = True
        new_validity = [liveobj_valid(p) and getattr(p, 'state', 0) == 0 for p in self.parameters]
        if changed or (hasattr(self, '_param_validity') and new_validity != self._param_validity):
            self._param_validity = new_validity
            self._schedule_refresh()

    def _schedule_refresh(self):
        if not self._refresh_scheduled:
            self._refresh_scheduled = True
            self._parent.schedule_message(1, self._do_deferred_refresh)

    def _do_deferred_refresh(self):
        self._refresh_scheduled = False
        if self._is_enabled and liveobj_valid(self._device):
            self.update()

    @listens_group("value")
    def _on_control_value_changed(self, value, control):
        index = list(self._parameter_controls).index(control)
        sel_key = (self._bank_index, index)
        if sel_key in self._selectors:
            sel = self._selectors[sel_key]
            n = len(sel["values"])
            delta = value if value < 64 else value - 128
            new_idx = max(0, min(n - 1, sel["index"] + (1 if delta > 0 else -1)))
            if new_idx != sel["index"]:
                sel["index"] = new_idx
                self._selector_saved_index[sel["name"]] = new_idx
                if sel.get("view_property") and liveobj_valid(self._device) and hasattr(self._device, 'view'):
                    try:
                        setattr(self._device.view, sel["view_property"], new_idx)
                    except Exception:
                        pass
                if sel.get("device_property") and liveobj_valid(self._device):
                    try:
                        setattr(self._device, sel["device_property"], new_idx)
                    except Exception:
                        pass
                bank = self._banks[self._bank_index]
                _resolve_selector_slots(bank, sel, self._custom_display_names)
                self._empty_control_slots.disconnect()
                self._connect_parameters()
            if self.device_control_enabled:
                fader_val = sel["index"] * 127 // max(1, n - 1)
                try:
                    ch = control.message_channel()
                    cc = control.message_identifier()
                    self._parent._send_midi((0xB0 | ch, cc, fader_val))
                except Exception:
                    pass
                if new_idx == sel["index"]:
                    self._parent.send_display(PARAM_VALUE, index, sel["values"][sel["index"]])
            return
        self.sysex_smoother += 1
        if self.sysex_smoother > 2:
            self.sysex_smoother = 0
        if self.device_control_enabled:
            param = self.parameters[index] if index < len(self.parameters) else None
            if liveobj_valid(param):
                self._parent.send_display(PARAM_VALUE, index, str(param))
            else:
                self._parent.send_display(PARAM_VALUE, index, "---")


    @listens_group("value")
    def _on_parameter_value_changed(self, parameter):
        if not self.device_control_enabled or not self._parameter_controls:
            return
        try:
            index = self.parameters.index(parameter)
        except ValueError:
            return
        if not liveobj_valid(parameter):
            return
        controls = list(self._parameter_controls)
        if index >= len(controls):
            return
        control = controls[index]
        try:
            cc_val = int(round((parameter.value - parameter.min) / max(parameter.max - parameter.min, 0.001) * 127))
            cc_val = max(0, min(127, cc_val))
            ch = control.message_channel()
            cc = control.message_identifier()
            self._parent._send_midi((0xB0 | ch, cc, cc_val))
        except Exception:
            pass
        if self.device_control_enabled:
            self._parent.send_display(PARAM_VALUE, index, str(parameter))

    @listens_group("name")
    def _on_parameter_changed(self, parameter):
        index = self.parameters.index(parameter)
        if self.device_control_enabled:
            name = self._custom_display_names.get(parameter.name) or parameter.name
            self._parent.send_display(PARAM_NAME, index, name)

    @device_lock_button.toggled
    def device_lock_button(self, *_):
        self._on_device_lock_button_toggled()

    def _on_device_lock_button_toggled(self):
        self._toggle_lock()
        self._update_device_lock_button()

    @property
    def bank_index(self):
        if self._use_parameter_banks:
            return self._bank_index
        return 0

    @bank_index.setter
    def bank_index(self, value):
        self._bank_index = self._clamp_to_bank_size(value)
        if self._device_bank_registry:
            self._device_bank_registry.set_device_bank(self._device, self._bank_index)
        self.control_offset = self.bank_index

        self.update()

    def _clamp_to_bank_size(self, value):
        return clamp(value, 0, self.num_banks - 1)

    @property
    def selected_bank(self):
        if self.num_banks:
            return self._banks[self._bank_index or 0]
        return []

    @property
    def num_banks(self):
        return len(self._banks)

    def set_parameter_controls(self, controls):
        for control in self._parameter_controls or []:
            release_control(control)
        self._parameter_controls = controls
        # self.update()

    @listens("device")
    def __on_provided_device_changed(self):
        for control in self._parameter_controls or []:
            release_control(control)
        self._device = self._device_provider.device
        self._SimpleDeviceParameterComponent__on_parameters_changed.subject = self._device
        self._SimpleDeviceParameterComponent__on_bank_changed.subject = self._device_bank_registry
        self._on_compare_changed.subject = self._device if liveobj_valid(self._device) else None
        self._device_on_param = None
        self._selector_saved_index = {}
        if liveobj_valid(self._device):
            print("param8: === DUMP %s ===" % self._device.class_name)
            for p in self._device.parameters[1:]:
                items = list(p.value_items) if getattr(p, 'is_quantized', False) else []
                if items:
                    print("param8:   [%s] = %s  values: %s" % (p.name, str(p), items))
                else:
                    print("param8:   [%s] = %s  (%.1f..%.1f)" % (p.name, str(p), p.min, p.max))
            print("param8: === END DUMP ===")
            for p in self._device.parameters:
                if p.name == 'Device On':
                    self._device_on_param = p
                    break
        self._on_device_on_changed.subject = self._device_on_param
        self._on_device_on_changed()
        self.bank_index = 0
        self.update()

    @listens("parameters")
    def __on_parameters_changed(self):
        self._schedule_refresh()
        # self.on_selected_parameter_changed.subject = self._device
        # devices = self.song.view.selected_track.devices
        
        # devices_amount = len(list(devices))
        # device_index = list(devices).index(self._device)
        # self.next_device_button.color = 127 if device_index < devices_amount - 1 else 0
        # self.prev_device_button.color = 127 if device_index > 0 else 0

    # @listens("selected_parameter")
    # def on_selected_parameter_changed(self):
    #     parameter = self._device_provider.selected_parameter
    #     self.on_value_changed.subject = parameter
    #     if liveobj_valid(parameter):
    #         print("SELECTED PARAMETER CHANGED", parameter.name)
    #         if self.device_control_enabled:
    #             self._parent.send_display(PARAM_NAME, 0, parameter.name)
    #     else:
    #         if self.device_control_enabled:
    #             self._parent.send_display(PARAM_NAME, 0, "No Parameter", static_overlay=1)

    # @listens("value")
    # def on_value_changed(self):
    #     parameter = self._device_provider.selected_parameter
    #     value = parameter.value if liveobj_valid(parameter) else None
    #     print("SELECTED PARAMETER VALUE CHANGED", value)
    #     if liveobj_valid(parameter):
    #         if self.device_control_enabled:
    #             self._parent.send_display(PARAM_VALUE, 0, str(parameter))

    @listens("device_bank")
    def __on_bank_changed(self, device, bank):
        if device == self._device and bank != self._bank_index:
            self.bank_index = bank

    @listens("is_locked_to_device")
    def __on_is_locked_to_device_changed(self):
        self._update_device_lock_button()

    def update(self):
        super(SimpleDeviceParameterComponent, self).update()
        if not self._is_enabled:
            self._disconnect_parameters()
            return

        self._update_parameter_banks()
        self._empty_control_slots.disconnect()
        self._selector_view_slots.disconnect()
        if liveobj_valid(self._device):
            self._setup_selector_view_listeners()
            self._connect_parameters()
            self._send_device_bank_labels()
        else:
            self._disconnect_parameters()
            if self.device_control_enabled:
                self._parent.send_display(DEVICE_NAME, 0, "No Device")
                self._parent.send_display(BANK_NAME, 0, "---")
                for i in range(8):
                    self._parent.send_display(PARAM_NAME, i, "---")
                    self._parent.send_display(PARAM_VALUE, i, "---")

    def _send_device_bank_labels(self):
        if not self.device_control_enabled:
            return
        if liveobj_valid(self._device):
            self._do_send_device_bank_labels()

    def _do_send_device_bank_labels(self):
        if not self.device_control_enabled or not liveobj_valid(self._device):
            return
        device_bank_names = self._custom_bank_names
        if not device_bank_names:
            device_bank_names = ["Bank %d" % (i + 1) for i in range(len(self._banks))]
        bank_idx = clamp(self._bank_index, 0, len(device_bank_names) - 1)
        bank_name = device_bank_names[bank_idx]
        device_label = self._device.class_display_name
        if self._device.name and self._device.name != device_label:
            device_label = self._device.name
        self._parent.send_display(DEVICE_NAME, 0, device_label)
        self._parent.send_display(BANK_NAME, 0, bank_name)

    def _disconnect_parameters(self):
        for control in self._parameter_controls or []:
            release_control(control)
            self._empty_control_slots.register_slot(control, nop, "value")

    def _connect_parameters(self):
        if self._parameter_controls is not None:
            if not self.device_control_enabled:
                self.release_parameter_controls()
            else:
                controls = list(self._parameter_controls)
                bank = self.selected_bank or []
                self.parameters = [bank[i] if i < len(bank) else None for i in range(8)]
                self._param_validity = [liveobj_valid(p) and getattr(p, 'state', 0) == 0 for p in self.parameters]
                self._on_control_value_changed.replace_subjects(self._parameter_controls)
                self._on_parameter_changed.replace_subjects(self.parameters)
                self._on_parameter_value_changed.replace_subjects(self.parameters)
                self._device_param_slots.disconnect()
                if liveobj_valid(self._device):
                    for p in self._device.parameters:
                        self._device_param_slots.register_slot(p, self._on_device_param_value_changed, "value")
                for i, control in enumerate(controls):
                    sel_key = (self._bank_index, i)
                    if sel_key in self._selectors:
                        sel = self._selectors[sel_key]
                        control.release_parameter()
                        if self.device_control_enabled:
                            self._parent.send_display(PARAM_NAME, i, sel["name"])
                            val_str = sel["values"][sel["index"]]
                            self._parent.send_display(PARAM_VALUE, i, val_str)
                            n = len(sel["values"])
                            fader_val = sel["index"] * 127 // max(1, n - 1)
                            try:
                                ch = control.message_channel()
                                cc = control.message_identifier()
                                self._parent._send_midi((0xB0 | ch, cc, fader_val))
                            except Exception:
                                pass
                        continue
                    parameter = self.parameters[i]
                    if liveobj_valid(parameter):
                        name = self._custom_display_names.get(parameter.name) or parameter.name
                        if getattr(parameter, 'state', 0) != 0:
                            name = "~" + name
                        control.connect_to(parameter)
                        if self.device_control_enabled:
                            self._parent.send_display(PARAM_NAME, i, name)
                            try:
                                self._parent.send_display(PARAM_VALUE, i, str(parameter))
                            except Exception:
                                self._parent.send_display(PARAM_VALUE, i, "---")
                    else:
                        control.release_parameter()
                        if self.device_control_enabled:
                            self._parent.send_display(PARAM_NAME, i, "---")
                            self._parent.send_display(PARAM_VALUE, i, "---")
                            try:
                                ch = control.message_channel()
                                cc = control.message_identifier()
                                self._parent._send_midi((0xB0 | ch, cc, 0))
                            except Exception:
                                pass
                        self._empty_control_slots.register_slot(control, nop, "value")

    def release_parameter_controls(self):
        controls = list(self._parameter_controls)
        for i, control in enumerate(controls):
            self._empty_control_slots.register_slot(control, nop, "value")

    def _update_parameter_banks(self):
        device = self._device
        if not liveobj_valid(device):
            self._banks = []
            return
        custom_mappings = _load_custom_mappings()
        custom_entry = custom_mappings.get(device.class_name)
        if custom_entry:
            custom_banks, custom_display, conditionals, selectors = _resolve_custom_banks(device, custom_entry, self._selector_saved_index)
            if custom_banks:
                self._banks = custom_banks
                self._custom_bank_names = [b.get("name", "Bank %d" % (i+1)) for i, b in enumerate(custom_entry.get("banks", []))]
                self._custom_display_names = custom_display
                self._conditionals = conditionals
                self._selectors = selectors
                return
        self._custom_bank_names = None
        self._custom_display_names = {}
        self._conditionals = {}
        self._selectors = {}
        auto = _auto_banks(device)
        if auto:
            self._banks = auto
        else:
            self._banks = [list(device.parameters[1:9])]


    def _update_device_lock_button(self):
        self.device_lock_button.is_toggled = self._device_provider.is_locked_to_device

    @staticmethod
    def _default_control_label(active_mode, i):
        # Matches the factory preset defaults in data/data.json: encoders on
        # CC 10-17, push buttons on CC 20-27, channel = preset number + 1.
        channel = active_mode + 1
        cc = (10 + i) if i < 8 else (20 + (i - 8))
        return "CC%d/%d" % (cc, channel)

    def _send_param8_device_names(self, device, active_mode):
        for i in range(16):
            if i + 1 < len(device.parameters) and not device.parameters[i+1].name.startswith("Macro"):
                name = device.parameters[i+1].name
            else:
                name = self._default_control_label(active_mode, i)
            self._parent.send_display(PARAM_NAME, i, name)

    def _resolve_chain_device(self, d):
        chain_selector = int(d.parameters[17].value)
        chain_selector = max(0, min(len(d.chains) - 1, chain_selector))
        chain_devices = d.chains[chain_selector].devices
        return chain_devices[0] if chain_devices else d

    def _on_chain_selector_changed(self, d, active_mode):
        if not liveobj_valid(d) or len(d.chains) == 0:
            return
        device = self._resolve_chain_device(d)
        print("Chain selector changed, now showing", device.name)
        self._send_param8_device_names(device, active_mode)

    def look_for_param8_device(self, active_mode):
        self._chain_selector_slot.disconnect()
        print(list(self.song.tracks))
        for t in self.song.tracks:
            for d in t.devices:
                if d.name.startswith("param8"):
                    items = d.name.split(" ")
                    device = d
                    if len(items) > 1 and (int(items[1])-1) == active_mode:
                        if len(d.chains) > 0 and len(d.parameters) > 17:
                            device = self._resolve_chain_device(d)
                            print("Found param8 chain device", device.name)
                            self._chain_selector_slot.register_slot(
                                d.parameters[17], lambda d=d, active_mode=active_mode: self._on_chain_selector_changed(d, active_mode), "value")
                        self._send_param8_device_names(device, active_mode)
