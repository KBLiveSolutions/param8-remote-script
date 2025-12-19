#Embedded file name: /Users/versonator/Jenkins/live/output/Live/mac_64_static/Release/python-bundle/MIDI Remote Scripts/Roland_FA/skin.py
from __future__ import absolute_import, print_function, unicode_literals
from builtins import object
from ableton.v2.control_surface.elements import Color
from ableton.v2.control_surface import Skin

from . import colors

class Colors(object):

    class DefaultButton(object):
        On = Color(colors.off)
        Off = Color(colors.off)
        Disabled = Color(0)

    class Transport(object):
        RecOn = Color(colors.red)
        PlayOn = Color(colors.green)
        PlayOff = Color(colors.off)
        StopOn = Color(12)
        StopOff = Color(0)
        LoopOn = Color(colors.yellow)
        LoopOff = Color(14)
        BTAOn = Color(15)
        BTAOff = Color(0)
        MetronomeOn =Color(80)
        MetronomeOff = Color(81)
        TapTempo = Color(1)
        PunchOn = Color(80)
        PunchOff = Color(0)

    class Recording(object):
        On = Color(127)
        Off = Color(116)

    # class DefaultButton(object):
    #     On = Color(120)
    #     Off = Color(0)
    #     Disabled = Color(0)

    class Session(object):
        RecordButton = Color(colors.off)
        ClipTriggeredPlay = Color(colors.green)
        ClipTriggeredRecord = Color(colors.red)
        ClipStarted = Color(colors.green)
        ClipRecording = Color(colors.red)
        ClipStopped = Color(colors.light_white)
        StopClip = Color(colors.blue)
        Scene = Color(16)
        SceneTriggered = Color(17)
        NoScene = Color(colors.light_white)
        StopClipTriggered =Color( 19)
        StopClip = Color(20)
        StopClipDisabled = Color(21)
        ClipEmpty = Color(0)
        Navigation = Color(colors.white)
        Select = Color(23)
        SelectPressed = Color(colors.white)
        Shift = Color(23)
        ShiftPressed = Color(123)
    
    class Mixer(object):
        ArmOff = Color(0)
        ArmOn = Color(127)
        SoloOff = Color(39)
        SoloOn = Color(colors.blue)
        MuteOff = Color(14)
        MuteOn = Color(colors.yellow)
        TrackSelected = Color(colors.white)
        TrackUnselected = Color(colors.light_white)

    # class Mixer(object):
    #     ArmOn = Rgb.RED
    #     ArmOff = Rgb.RED_HALF
    #     SoloOn = Rgb.BLUE
    #     SoloOff = Rgb.BLUE_HALF
    #     MuteOn = Rgb.YELLOW_HALF
    #     MuteOff = Rgb.YELLOW
    #     Pan = Rgb.ORANGE
    #     TrackSelect = Rgb.WHITE
    #     Send = Rgb.WHITE

    # class Monitor(object):
    #     In = Rgb.LIGHT_BLUE
    #     Auto = Rgb.YELLOW
    #     Off = Rgb.YELLOW
    #     Disabled = Rgb.YELLOW_HALF

    # class Transport(object):
    #     PlayOn = Rgb.GREEN
    #     PlayOff = Rgb.GREEN_HALF
    #     StopEnabled = Rgb.WHITE
    #     StopDisabled = Rgb.WHITE_HALF
    #     SeekOn = Rgb.WHITE
    #     SeekOff = Rgb.WHITE_HALF
    #     LoopOn = Rgb.YELLOW
    #     LoopOff = Rgb.YELLOW_HALF
    #     MetronomeOn = Rgb.YELLOW
    #     MetronomeOff = Rgb.YELLOW_HALF

    # class Recording(object):
    #     On = Rgb.RED
    #     Off = Rgb.RED_HALF
    #     Transition = Rgb.BLACK

    class Mode(object):

        class Mute(object):
            On = colors.yellow
            Off = 14

        class Solo(object):
            On = colors.blue
            Off = 39

        class Monitor(object):
            On = colors.green

        class Arm(object):
            On = colors.red

        class Device:

            class Bank:
                Selected = colors.blue
                Available = colors.white


        # class Devices(object):
        #     On = Rgb.PURPLE
        #     Off = Rgb.PURPLE

        # class Pan(object):
        #     On = Rgb.ORANGE
        #     Off = Rgb.ORANGE

        # class Sends(object):
        #     On = Rgb.WHITE
        #     Off = Rgb.WHITE

    class DrumGroup(object):
        PadEmpty = colors.off
        PadFilled = colors.white
        PadSelected = colors.white
        PadSelectedNotSoloed = colors.white
        PadMuted = colors.yellow
        PadMutedSelected = colors.yellow
        PadSoloed = colors.blue
        PadSoloedSelected = colors.blue
        PadInvisible = colors.white
        PadAction = colors.red

    # class ItemNavigation(object):
    #     NoItem = Rgb.BLACK
    #     ItemSelected = Rgb.PURPLE
    #     ItemNotSelected = Rgb.PURPLE_HALF

    # class Device(object):
    #     On = Rgb.PURPLE

    # class TrackNavigation(object):
    #     On = Rgb.LIGHT_BLUE
    #     Pressed = Rgb.LIGHT_BLUE

    # class SceneNavigation(object):
    #     On = Rgb.WHITE
    #     Pressed = Rgb.WHITE

    # class Action(object):
    #     Available = Rgb.WHITE


# skin = Skin(Colors)

def make_default_skin():
    return Skin(Colors)
