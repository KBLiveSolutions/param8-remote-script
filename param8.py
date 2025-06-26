import Live
from ableton.v2.base import const, inject, recursive_map, nop, liveobj_valid, clamp, listenable_property, listens, task, index_if, depends
from ableton.v2.control_surface import ControlSurface, Layer, BankingInfo, DeviceDecoratorFactory, PrioritizedResource, MIDI_CC_TYPE, MIDI_NOTE_TYPE, PercussionInstrumentFinder
from ableton.v2.control_surface import MIDI_CC_TYPE, MIDI_NOTE_TYPE, PrioritizedResource
from ableton.v2.control_surface.default_bank_definitions import BANK_DEFINITIONS
from ableton.v2.control_surface.elements import ButtonElement, EncoderElement, ButtonMatrixElement, ComboElement, EncoderElement, SliderElement, TouchEncoderElement
from ableton.v2.control_surface.components import AutoArmComponent, BackgroundComponent, RightAlignTracksTrackAssigner, SessionRingComponent, UndoRedoComponent, ChannelStripComponent, SessionNavigationComponent
from ableton.v2.control_surface.mode import AddLayerMode, DelayMode, ImmediateBehaviour, ModesComponent, ReenterBehaviour
from .skin import make_default_skin
from contextlib import contextmanager
from functools import partial

from .device_navigation import SimpleDeviceNavigationComponent
from .device import SimpleDeviceParameterComponent
from .colors import LIVE_COLORS_TO_MIDI_VALUES, RGB_COLOR_TABLE

SCRIPT_NAME = 'param8'
SCRIPT_VER = 'v1.0'

MIDI_CHANNEL = 7
MAX_REQUESTS = 10
prefix = (240, 122, 29, 1, 19)
REQUEST_MSG = (240, 122, 29, 1, 19, 2, 247)
REPLY_MSG = (240, 122, 29, 1, 19, 2, 247)
ACKNOWLEDGMENT_MSG = (240, 122, 29, 1, 19, 78, 247)

import logging, traceback
logger = logging.getLogger(__name__)
def print(text):
    logger.warning(text)  

""" Dictionnaries containing all the actions performed by the buttons/sliders or interpreted by the LEDs.
 It consists of a dictionnary with the name of the action and the associated CC number."""


button_actions = {
    "BankUp": 27,
    "BankDown": 26,
    "DeviceUp": 25,
    "DeviceDown": 24,
    "Prev Device": 33,
    "Next Device": 32,
    "Prev Variation": 67,
    "Next Variation": 68,
    "Launch Variation": 69,
    "Store Variation": 70,
    "Recall Last Used": 72, 
    "Randomize Macros": 71
  }
led_actions = {
  }
slider_actions = {    
    "Encoder_1": 10,
    "Encoder_2": 11,
    "Encoder_3": 12,
    "Encoder_4": 13,
    "Encoder_5": 14,
    "Encoder_6": 15,
    "Encoder_7": 16,
    "Encoder_8": 17,
  }
display_actions =  {}

class param8(ControlSurface):
    
    def __init__(self, *a, **k):
        super(param8, self).__init__(*a, **k)
        print("====================================")
        self._has_been_identified = False
        self._request_count = 0
        self._last_sent_layout_byte = None
        self._skin = make_default_skin()
        with self.component_guard():
            self._create_buttons()
            self._create_device_parameters()
            self.create_device_navigation()
            # self.set_device_component(self._device)
        self.active_mode = 1
        self._device_parameters.look_for_custome_device(self.active_mode)
        print("param8 OK")

    def create_device_navigation(self):
        self._device_navigation = SimpleDeviceNavigationComponent( name="Device_Navigation",
            is_enabled=True)       
        self._device_navigation.layer=Layer( next_button=self.buttons["DeviceUp"],
                                    prev_button=self.buttons["DeviceDown"],
                      )

    def _create_buttons(self):
        """ Create all the buttons one by one then buils the button matrixes if needed"""
        self.buttons = {}
        for control in button_actions:
            self.buttons[control] = self.make_button(button_actions[control], MIDI_CHANNEL, msg_type=MIDI_CC_TYPE, name=control)
        for control in slider_actions:
            self.buttons[control] = self.make_slider(slider_actions[control], MIDI_CHANNEL, msg_type=MIDI_CC_TYPE, name=control)
        self.device_parameter_buttons = ButtonMatrixElement(rows=[[self.buttons["Encoder_1"], self.buttons["Encoder_2"], self.buttons["Encoder_3"], self.buttons["Encoder_4"], self.buttons["Encoder_5"], self.buttons["Encoder_6"], self.buttons["Encoder_7"], self.buttons["Encoder_8"]]])
        
    def make_button(self, identifier, channel, name, msg_type = MIDI_CC_TYPE, skin = None, is_modifier = False):
        return ButtonElement(True, msg_type, channel, identifier, skin=self._skin, name=name, resource_type=PrioritizedResource if is_modifier else None)


    def make_slider(self, identifier, channel, name, msg_type = MIDI_CC_TYPE, skin = None, is_modifier = False):
        return EncoderElement(MIDI_CC_TYPE, channel, identifier, Live.MidiMap.MapMode.absolute)

    def _create_device_parameters(self):
        self._banking_info = BankingInfo(BANK_DEFINITIONS)
        self._device_parameters = SimpleDeviceParameterComponent(parent=self, name="Device_Parameters",
            is_enabled=True,
            use_parameter_banks=True,
            device_bank_registry = self._device_bank_registry,
            banking_info = self._banking_info
        )            
        self._device_parameters.layer=Layer(parameter_controls=self.device_parameter_buttons,
                                    next_bank_button=self.buttons["BankUp"],
                                    prev_bank_button=self.buttons["BankDown"],
                    #   bank_select_buttons=self._elements.bank_select_buttons
                      )

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

    def send_display(self, status_byte, param_number, name):
        _len = len(name)
        message = [240, 111, status_byte, param_number]
        for i in range(_len):
            char_code = ord(name[i])
            if 0 <= char_code - 32 <= 94:  # Caractères standards (32 à 126)
                message.append(0)  # Byte spécial pour indiquer un caractère étendu
                message.append(char_code - 32)
            elif 128 <= char_code <= 255:  # Caractères spéciaux (128 à 255)
                message.append(1)  # Byte spécial pour indiquer un caractère étendu
                message.append(char_code - 128)  # Ajout du caractère étendu
            else:  # Autres caractères non valides
                message.append(95)  # Remplace par `_`
        message.append(247)
        print(message)
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
        self._request_count = 0
        self._has_been_identified = True
        # self._request_identification()

    def _request_identification(self):
        """ Sends request and schedules message to call this method again and do
        so repeatedly until handshake succeeds or MAX_REQUESTS have been sent. """
        if not self._has_been_identified and self._request_count < MAX_REQUESTS:
            self._send_midi(REQUEST_MSG)
            self.schedule_message(2, self._request_identification)
            self._request_count += 1

    def handle_sysex(self, midi_bytes):
        if midi_bytes[1] == (111):
            if midi_bytes[2] == 2 and midi_bytes[3] == 3:
                self._device_parameters.update()
            if midi_bytes[2] == 4:
                self.active_mode = midi_bytes[3]
                if self.active_mode == 7:
                    self._device_parameters.is_enabled = True
                    self._device_parameters.update()
                else:
                    self._device_parameters.is_enabled = False
                    self._device_parameters.look_for_custome_device(self.active_mode)


    def process_midi_bytes(self, midi_bytes, midi_processor):
        if midi_bytes[0] == 240 and midi_bytes[-1] == 247:
            self.handle_sysex(midi_bytes)
        """Intercepts incoming MIDI bytes, including Program Change."""
        super(param8, self).process_midi_bytes(midi_bytes, midi_processor)

    def _add_control(self, number):
        return ButtonElement(True, MIDI_CC_TYPE, MIDI_CHANNEL, number)

    def _add_slider(self, number):
        return EncoderElement(MIDI_CC_TYPE, MIDI_CHANNEL, number, Live.MidiMap.MapMode.absolute)

    def disconnect(self):
        super(param8, self).disconnect()
        # self._send_midi(prefix + (3, 247))
        # self._session = None
