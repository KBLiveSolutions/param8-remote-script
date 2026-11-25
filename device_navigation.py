from __future__ import absolute_import, print_function, unicode_literals
import Live
from ableton.v2.control_surface import Component
from ableton.v2.control_surface.control import ButtonControl
NavDirection = Live.Application.Application.View.NavDirection

PARAM_NAME = 0

class SimpleDeviceNavigationComponent(Component):
    next_button = ButtonControl()
    prev_button = ButtonControl()

    def __init__(self, navigate_callback=None, *a, **k):
        super(SimpleDeviceNavigationComponent, self).__init__(*a, **k)
        self._navigate_callback = navigate_callback

    @next_button.pressed
    def next_button(self, value):
        self._scroll_device_chain(1)

    @prev_button.pressed
    def prev_button(self, value):
        self._scroll_device_chain(-1)

    def _scroll_device_chain(self, direction):
        if self._navigate_callback:
            self._navigate_callback(direction)
        else:
            nav_dir = NavDirection.right if direction > 0 else NavDirection.left
            view = self.application.view
            if not (view.is_view_visible('Detail') and view.is_view_visible('Detail/DeviceChain')):
                view.show_view('Detail')
                view.show_view('Detail/DeviceChain')
            else:
                view.scroll_view(nav_dir, 'Detail/DeviceChain', False)
