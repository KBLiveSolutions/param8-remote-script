# uncompyle6 version 3.9.1
# Python bytecode version base 3.7.0 (3394)
# Decompiled from: Python 3.12.2 (main, Feb  6 2024, 20:19:44) [Clang 15.0.0 (clang-1500.1.0.2.5)]
# Embedded file name: output/Live/mac_universal_64_static/Release/python-bundle/MIDI Remote Scripts/novation/simple_device.py
# Compiled at: 2024-03-09 01:30:22
# Size of source mod 2**32: 6020 bytes
from __future__ import absolute_import, print_function, unicode_literals
from future.moves.itertools import zip_longest
from _Generic.Devices import best_of_parameter_bank, parameter_banks
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

    def select_bank(self, factor):
        prev_bank = self.bank_index
        self.bank_index += factor
        # self._bank_index = self._clamp_to_bank_size(self._bank_index)
        # if prev_bank != self.bank_index:
        #     self.control_offset = self.bank_index
        #     self.update()

    @depends(device_provider=None)
    def __init__(self, parent = None, device_provider=None, banking_info=None, device_bank_registry=None, toggle_lock=None, use_parameter_banks=False, *a, **k):
        (super(SimpleDeviceParameterComponent, self).__init__)(*a, **k)
        self.device_control_enabled = False
        self.sysex_smoother = 0
        self._parent = parent
        self.control_offset = 0
        self._toggle_lock = toggle_lock
        self._use_parameter_banks = use_parameter_banks
        self._device = None
        self._banks = []
        self._bank_index = 0
        self._banking_info = banking_info
        self._parameter_controls = None
        self._empty_control_slots = self.register_disconnectable(EventObject())
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

    @listens_group("value")
    def _on_control_value_changed(self, value, control):
        index = list(self._parameter_controls).index(control)
        self.sysex_smoother += 1
        if self.sysex_smoother > 2:
            self.sysex_smoother = 0
        if self.device_control_enabled:
            self._parent.send_display(PARAM_VALUE, index, str(self.parameters[index]))


    @listens_group("name")
    def _on_parameter_changed(self, parameter):
        index = self.parameters.index(parameter)
        if self.device_control_enabled:
            self._parent.send_display(PARAM_NAME, index, parameter.name)
            print("PARAMETER CHANGED", index, parameter.name)

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
        print("SETTING BANK INDEX", value, self._bank_index)
        self._bank_index = self._clamp_to_bank_size(value)
        if self._device_bank_registry:
            self._device_bank_registry.set_device_bank(self._device, self._bank_index)
            num_banks = len(self._banking_info.device_bank_names(self._device))
        self.control_offset = self.bank_index
        self.next_bank_button.color = 127 if self._bank_index < num_banks - 1 else 0
        self.prev_bank_button.color = 127 if self._bank_index > 0 else 0

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
        self._SimpleDeviceParameterComponent__on_bank_changed.subject = self._device_bank_registry
        self.bank_index = 0
        self.update()
        # devices = self.song.view.selected_track.devices
        
        # devices_amount = len(list(devices))
        # device_index = list(devices).index(self._device)
        # self.next_device_button.color = 127 if device_index < devices_amount - 1 else 0
        # self.prev_device_button.color = 127 if device_index > 0 else 0

    @listens("device_bank")
    def __on_bank_changed(self, device, bank):
        if device == self._device:
            self.bank_index = bank

    @listens("is_locked_to_device")
    def __on_is_locked_to_device_changed(self):
        self._update_device_lock_button()

    def update(self):
        super(SimpleDeviceParameterComponent, self).update()
        print("UPDATE DEVICE PARAMETERS", self._is_enabled)
        if not self._is_enabled:
            self._disconnect_parameters()
            return

        self._update_parameter_banks()
        self._empty_control_slots.disconnect()
        if liveobj_valid(self._device):
            self._connect_parameters()
        else:
            self._disconnect_parameters()

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
                self.parameters = [self.selected_bank[i] for i in range(8)]
                self._on_control_value_changed.replace_subjects(self._parameter_controls)
                self._on_parameter_changed.replace_subjects(self.parameters)
                for i, control in enumerate(controls):
                    parameter = self.parameters[i]
                    if liveobj_valid(parameter):
                        name = parameter.name
                        control.connect_to(parameter)
                        if self.device_control_enabled:
                            self._parent.send_display(PARAM_NAME, i, name)
                    else:
                        control.release_parameter()
                        if self.device_control_enabled:
                            self._parent.send_display(PARAM_NAME, i, "******")
                        self._empty_control_slots.register_slot(control, nop, "value")

    def release_parameter_controls(self):
        controls = list(self._parameter_controls)
        for i, control in enumerate(controls):
            self._empty_control_slots.register_slot(control, nop, "value")

    def _update_parameter_banks(self):
        device = self._device
        print("UPDATE PARAMETER BANKS", device, self._use_parameter_banks)
        if liveobj_valid(device):
            if self._use_parameter_banks:
                self._banks = parameter_banks(device)
            else:
                self._banks = [
                 best_of_parameter_bank(device)]
            device_bank_names = self._banking_info.device_bank_names(device)
            if device_bank_names and self.device_control_enabled:
                print(self._device_bank_registry.get_device_bank(device), device_bank_names)
                bank_name = device_bank_names[self._device_bank_registry.get_device_bank(device)]
                if self.device_control_enabled:
                        self._parent.send_display(DEVICE_NAME, 0, self._device.class_display_name)
                        self._parent.send_display(BANK_NAME, 1, bank_name)
        else:
            self._banks = []
            if self.device_control_enabled:
                self._parent.send_display(DEVICE_NAME, 0, "No Device Selected", static_overlay = 1)
                self._parent.send_display(BANK_NAME, 1, "No Device Selected", static_overlay = 1)

    def _update_device_lock_button(self):
        self.device_lock_button.is_toggled = self._device_provider.is_locked_to_device

    def look_for_param8_device(self, active_mode):
        for t in self.song.visible_tracks:
            for d in t.devices:
                if d.name.startswith("param8"):
                    items = d.name.split(" ")
                    device = d
                    print("Found param8 device", d.name, items, len(d.chains), (int(items[1])-1) == active_mode)
                    if len(items) > 1 and (int(items[1])-1) == active_mode:
                        # if len(d.chains) > 0:
                        #     chain_selector = int(d.parameters[17].value)
                        #     device = d.chains[chain_selector].devices[0]
                        for i in range(16):
                            p = device.parameters[i+1]
                            if not p.name.startswith("Macro"):
                                print(p.name, p.name.startswith("Macro"))
                                self._parent.send_display(PARAM_NAME, i, p.name)
                    return