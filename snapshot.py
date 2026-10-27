import logging
from ableton.v2.base import liveobj_valid

logger = logging.getLogger(__name__)
def print(text):
    logger.warning(text)


class SnapshotMixin:
    """A/B compare: snapshot current param values, restore or discard on release."""

    def _enter_revert(self):
        self._revert_snapshot = []
        params = self._get_active_parameters()
        print(f"Revert: active_mode={self.active_mode} params_count={len(params)}")
        for i, p in enumerate(params):
            if p and liveobj_valid(p):
                self._revert_snapshot.append((p, p.value))
                print(f"  [{i}] '{p.name}' = {p.value}")
            else:
                self._revert_snapshot.append(None)
                print(f"  [{i}] None")
        print(f"Revert: snapshot {len([s for s in self._revert_snapshot if s])} params")

    def _restore_revert(self):
        if not self._revert_snapshot:
            print("Revert: nothing to restore")
            self._revert_snapshot = None
            return
        for i, entry in enumerate(self._revert_snapshot):
            if entry:
                param, value = entry
                if liveobj_valid(param):
                    param.value = value
                    self.send_display(1, i, param.str_for_value(value))
                    print(f"Revert: restored '{param.name}' = {value}")
        self._revert_snapshot = None

    def _discard_revert(self):
        self._revert_snapshot = None
        print("Revert: discarded")

    def _get_active_parameters(self):
        if self.active_mode == 25:
            return list(self._device_parameters.parameters)
        elif self.active_mode == 24:
            return self._mixer.get_snapshotable_params()
        return []
