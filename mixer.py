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

def process_relative_encoder(current_value, encoder_value, sensitivity=0.01, min_val=0.0, max_val=1.0):
    """
    Traite les valeurs d'un encodeur relatif
    
    Args:
        current_value: Valeur actuelle du paramètre (0.0-1.0)
        encoder_value: Valeur MIDI de l'encodeur (64-68 horaire, 60-64 anti-horaire)
        sensitivity: Facteur de sensibilité (par défaut 0.01)
        min_val: Valeur minimale (par défaut 0.0)
        max_val: Valeur maximale (par défaut 1.0)
    
    Returns:
        Nouvelle valeur clampée entre min_val et max_val
    """
    if encoder_value >= 64:
        # Rotation horaire (64 = lent, 68 = rapide)
        steps = encoder_value - 64
        increment = steps * sensitivity
    else:
        # Rotation anti-horaire (60-63)
        steps = 64 - encoder_value
        increment = -steps * sensitivity
    
    new_value = clamp(current_value + increment, min_val, max_val)
    return new_value

MAX_NUM_SENDS = 4
class MixerComponent(MixerComponentBase):
    Master_Volume = SendReceiveValueControl()
    Cue_Volume = SendReceiveValueControl()
    Track_Volume = SendReceiveValueControl()
    Track_Pan = SendReceiveValueControl()
    next_track_button = ButtonControl()
    prev_track_button = ButtonControl()
    next_sends_button = ButtonControl()
    prev_sends_button = ButtonControl()
    tempo = SendReceiveValueControl()
    groove = SendReceiveValueControl()

    def __init__(self, *a, **k):
        # Initialiser _selected_track AVANT d'appeler super().__init__()
        self._selected_track = None
        
        super(MixerComponent, self).__init__(*a, **k)
        
        self.on_cue_volume_changed.subject = self.song.master_track.mixer_device.cue_volume
        self.on_master_volume_changed.subject = self.song.master_track.mixer_device.volume
        self.on_groove_amount_changed.subject = self.song
        self.on_tempo_changed.subject = self.song
        self._on_selected_track_changed.subject = self.song.view
        
        self.update_component()


    def set_control_names(self):
        self.send_display(PARAM_NAME, 0, "Tempo")
        self.send_display(PARAM_NAME, 1, "Groove")
        self.send_display(PARAM_NAME, 2, "Cue Vol.")
        self.send_display(PARAM_NAME, 3, "Master Vol.")
        self.send_display(PARAM_NAME, 4, "Volume")
        self.send_display(PARAM_NAME, 5, "Pan")
        self.send_display(PARAM_NAME, 6, "Send A")
        self.send_display(PARAM_NAME, 7, "Send B")

    def set_parent(self, parent):
        """Permet de définir le parent pour envoyer des messages"""
        self._parent = parent
        self.update_component()

    @listens("selected_track")
    def _on_selected_track_changed(self):
        print("Selected track changed")
        selected_track = self.song.view.selected_track
        self.send_display(DEVICE_NAME, 0, selected_track.name)
        self.send_display(BANK_NAME, 1, "Sends A/B")
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

    def _connect_track_listeners(self):
        """Connecte les listeners pour la piste sélectionnée"""
        if self._selected_track and hasattr(self._selected_track, 'mixer_device'):
            # Connecter les listeners pour volume et pan
            self.on_track_volume_changed.subject = self._selected_track.mixer_device.volume
            self.on_track_pan_changed.subject = self._selected_track.mixer_device.panning
            
            # Mettre à jour les valeurs initiales
            self.on_track_volume_changed()
            self.on_track_pan_changed()

    def _disconnect_track_listeners(self):
        """Déconnecte les listeners de l'ancienne piste"""
        self.on_track_volume_changed.subject = None
        self.on_track_pan_changed.subject = None

    @next_track_button.pressed
    def on_next_track_button_pressed(self, button):
        tracks = list(self.song.tracks)
        current_index = tracks.index(self.song.view.selected_track)
        next_index = (current_index + 1) % len(tracks)
        self.song.view.selected_track = tracks[next_index]
        print(f"Selected track: {self.song.view.selected_track.name}")  
    
    @prev_track_button.pressed
    def on_prev_track_button_pressed(self, button):    
        tracks = list(self.song.tracks)
        current_index = tracks.index(self.song.view.selected_track)
        prev_index = (current_index - 1) % len(tracks)
        self.song.view.selected_track = tracks[prev_index]
        print(f"Selected track: {self.song.view.selected_track.name}")

    @Track_Volume.value
    def on_Track_Volume_changed(self, value, button):
        print(f"Track_Volume changed: {value}")
        if self._selected_track and hasattr(self._selected_track, 'mixer_device'):
            current_value = self._selected_track.mixer_device.volume.value
            new_value = process_relative_encoder(current_value, value, sensitivity=0.015)
            self._selected_track.mixer_device.volume.value = new_value
            print(f"Track Volume: {current_value:.3f} -> {new_value:.3f}")

    @Track_Pan.value
    def on_Track_Pan_changed(self, value, button):
        if self._selected_track and hasattr(self._selected_track, 'mixer_device'):
            current_value = self._selected_track.mixer_device.panning.value
            new_value = process_relative_encoder(current_value, value, sensitivity=0.015, min_val=0.0, max_val=1.0)
            self._selected_track.mixer_device.panning.value = new_value
            print(f"Track Pan: {current_value:.3f} -> {new_value:.3f}")


    @tempo.value
    def on_Tempo_changed(self, value, button):
        current_tempo = self.song.tempo
        new_tempo = process_relative_encoder(current_tempo, value, sensitivity=1, min_val=20.0, max_val=999.0)
        self.song.tempo = new_tempo
        self.send_display(PARAM_VALUE, 0, self.song.tempo.str_for_value(new_tempo)+ "BPM")

    @groove.value
    def on_Groove_changed(self, value, button): 
        current_groove = self.song.groove_amount
        new_groove = process_relative_encoder(current_groove, value, sensitivity=0.01, min_val=0.0, max_val=1.3)
        self.song.groove_amount = new_groove
        self.send_display(PARAM_VALUE, 1, str(int(new_groove * 100)) + "%")
    
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

    @listens(u'value')
    def on_track_volume_changed(self):
        if self._selected_track and hasattr(self._selected_track, 'mixer_device'):
            volume_value = self._selected_track.mixer_device.volume.value
            self.Track_Volume.value = int(volume_value * 127)

    @listens(u'value')
    def on_track_pan_changed(self):
        if self._selected_track and hasattr(self._selected_track, 'mixer_device'):
            pan_value = self._selected_track.mixer_device.panning.value
            # Convertir -1.0/1.0 vers 0-127
            self.Track_Pan.value = int((pan_value + 1.0) * 63.5)

    @listens(u'tempo')
    def on_tempo_changed(self):
        current_tempo = self.song.tempo
        self.tempo.value = int((current_tempo - 20.0) / (999.0 - 20.0) * 127)
        self.send_display(PARAM_VALUE, 0, f"{current_tempo:.2f} BPM")
        print(f"Tempo updated: {current_tempo:.2f} BPM")

    @listens(u'groove_amount')
    def on_groove_amount_changed(self):
        if self.song.groove_amount is not None:
            current_groove = self.song.groove_amount / 1.3
            self.groove.value = int(current_groove * 127)

    def send_display(self, param_type, param_index, value):
        if self._parent:
            self._parent.send_display(param_type, param_index, value)
            print(f"Display sent: {param_type}, {param_index}, {value}")

    @Cue_Volume.value
    def on_Cue_Volume_changed(self, value, button):
        current_value = self.song.master_track.mixer_device.cue_volume.value
        value = process_relative_encoder(current_value, value) 
        self.song.master_track.mixer_device.cue_volume.value  = value
        self.send_display(PARAM_VALUE, 2, self.song.master_track.mixer_device.cue_volume.str_for_value(value))

    @Master_Volume.value
    def on_Master_Volume_changed(self, value, button):
        current_value = self.song.master_track.mixer_device.volume.value
        value = process_relative_encoder(current_value, value) 
        self.song.master_track.mixer_device.volume.value  = value
        self.send_display(PARAM_VALUE, 3, self.song.master_track.mixer_device.volume.str_for_value(value))

    @Track_Volume.value
    def on_Track_Volume_changed(self, value, button):
        current_value = self._selected_track.mixer_device.volume.value
        value = process_relative_encoder(current_value, value) 
        self._selected_track.mixer_device.volume.value  = value
        self.send_display(PARAM_VALUE, 4, self._selected_track.mixer_device.volume.str_for_value(value))

    @Track_Pan.value
    def on_Track_Pan_changed(self, value, button):
        current_value = self._selected_track.mixer_device.panning.value
        value = process_relative_encoder(current_value, value, min_val=-1.0, max_val=1.0) 
        self._selected_track.mixer_device.panning.value  = value
        self.send_display(PARAM_VALUE, 5, self._selected_track.mixer_device.panning.str_for_value(value))

    @listens(u'value')
    def on_cue_volume_changed(self):
        self.Cue_Volume.value = (int(self.song.master_track.mixer_device.cue_volume.value * 127))

    @listens(u'value')
    def on_master_volume_changed(self):
        self.Master_Volume.value = (int(self.song.master_track.mixer_device.volume.value * 127))

    def update_component(self):
        self.set_control_names()
        self.on_cue_volume_changed()
        self.on_master_volume_changed()
        self.on_tempo_changed()
        self.on_groove_amount_changed()
