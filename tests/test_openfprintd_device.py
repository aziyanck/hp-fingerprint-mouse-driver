import unittest
from unittest import mock

from openfprintd.device import Device, NoSuchDevice
from openfprintd.manager import Manager


def make_device(target=None, busy=False, operation=None):
    """Build a Device without exporting it on a real D-Bus connection."""
    device = Device.__new__(Device)
    device._object_path = '/net/reactivated/Fprint/Device/0'
    device.manager = mock.Mock()
    device.target = target
    device.target_sender = None
    device.target_watcher = None
    device.signal_matches = []
    device.owner_watcher = None
    device.claimed_by = None
    device.claim_sender = None
    device.busy = busy
    device.operation = operation
    device.removed = False
    device.suspended = False
    device.callbacks = []
    # Signals and bus teardown would otherwise talk to a live connection.
    device.EnrollStatus = mock.Mock()
    device.VerifyStatus = mock.Mock()
    device.remove_from_connection = mock.Mock()
    return device


class OfflineDeviceTests(unittest.TestCase):
    def setUp(self):
        self.device = make_device()
        self.device.owner_watcher = object()
        self.device.claim_sender = ':1.5'

    def test_enroll_start_reports_no_such_device(self):
        with self.assertRaises(NoSuchDevice):
            Device.EnrollStart(
                self.device, 'right-index-finger', ':1.5', None)
        self.assertFalse(self.device.busy)
        self.assertIsNone(self.device.operation)

    def test_verify_start_reports_no_such_device(self):
        with self.assertRaises(NoSuchDevice):
            Device.VerifyStart(self.device, 'any', ':1.5', None)
        self.assertFalse(self.device.busy)

    def test_run_cmd_reports_no_such_device(self):
        with self.assertRaises(NoSuchDevice):
            Device.RunCmd(self.device, '01', ':1.5', None)

    def test_list_enrolled_fingers_errbacks_instead_of_crashing(self):
        errback = mock.Mock()
        Device.ListEnrolledFingers(
            self.device, 'sonu', ':1.5', None, mock.Mock(), errback)

        errback.assert_called_once()
        self.assertIsInstance(errback.call_args[0][0], NoSuchDevice)

    def test_stop_methods_are_no_ops_without_a_target(self):
        self.device.owner_watcher = mock.Mock()
        Device.VerifyStop(self.device, ':1.5', None)
        Device.EnrollStop(self.device, ':1.5', None)
        self.assertFalse(self.device.busy)


class ReleaseTests(unittest.TestCase):
    def test_do_release_tolerates_a_dead_target(self):
        device = make_device(target=None, busy=True, operation='enroll')
        watcher = mock.Mock()
        device.owner_watcher = watcher
        device.claim_sender = ':1.5'

        Device.do_release(device)

        watcher.cancel.assert_called_once()
        self.assertFalse(device.busy)
        self.assertIsNone(device.operation)

    def test_do_release_cancels_the_backend_operation(self):
        target = mock.Mock()
        device = make_device(target=target, busy=True, operation='verify')
        device.owner_watcher = mock.Mock()

        Device.do_release(device)

        target.Cancel.assert_called_once_with(signature='')
        self.assertFalse(device.busy)


class TargetLossTests(unittest.TestCase):
    def test_unset_target_cleans_up_and_fails_pending_calls(self):
        target = mock.Mock()
        device = make_device(target=target, busy=True, operation='enroll')
        watcher = mock.Mock()
        device.target_watcher = watcher
        signal_match = mock.Mock()
        device.signal_matches = [signal_match]
        pending = (mock.Mock(), mock.Mock())
        device.callbacks = [pending]

        device.unset_target()

        self.assertIsNone(device.target)
        self.assertTrue(device.removed)
        self.assertFalse(device.busy)
        watcher.cancel.assert_called_once()
        signal_match.remove.assert_called_once()
        device.EnrollStatus.assert_called_once_with('enroll-failed', True)
        pending[1].assert_called_once()
        self.assertIsInstance(pending[1].call_args[0][0], NoSuchDevice)
        device.manager.remove_device.assert_called_once_with(device)
        device.remove_from_connection.assert_called_once()

    def test_unset_target_is_idempotent(self):
        device = make_device(target=mock.Mock())
        device.target_watcher = mock.Mock()

        device.unset_target()
        device.unset_target()

        device.manager.remove_device.assert_called_once_with(device)
        device.remove_from_connection.assert_called_once()

    def test_verification_loss_uses_the_verify_failure_status(self):
        device = make_device(target=mock.Mock(), busy=True, operation='verify')

        device.unset_target()

        device.VerifyStatus.assert_called_once_with('verify-no-match', True)


class ManagerRoutingTests(unittest.TestCase):
    def setUp(self):
        self.manager = Manager.__new__(Manager)
        self.live = make_device(target=mock.Mock())
        self.dead = make_device(target=None)
        self.manager.devices = {
            '/io/github/uunicorn/Fprint/Device': self.live,
            '/io/github/uunicorn/Fprint/Device/dead': self.dead,
        }

    def test_only_live_devices_are_advertised(self):
        self.assertEqual(self.manager.GetDevices(None, None), [self.live])

    def test_default_device_skips_a_dead_registration(self):
        self.assertIs(self.manager.GetDefaultDevice(None, None), self.live)

    def test_default_device_raises_when_only_dead_devices_remain(self):
        self.manager.remove_device(self.live)

        with self.assertRaises(NoSuchDevice):
            self.manager.GetDefaultDevice(None, None)
        self.assertEqual(self.manager.GetDevices(None, None), [])

    def test_remove_device_keeps_unrelated_wrappers(self):
        self.manager.remove_device(self.dead)

        self.assertEqual(list(self.manager.devices.values()), [self.live])

    def test_online_property_tracks_the_target(self):
        self.assertTrue(self.live.online)
        self.assertFalse(self.dead.online)


if __name__ == '__main__':
    unittest.main()
