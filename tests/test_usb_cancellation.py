import errno
import unittest

from usb.core import USBError

from validitysensor.usb import CancelledException, Usb


class TimeoutDevice:
    def __init__(self):
        self.read_count = 0

    def read(self, endpoint, size, timeout):
        self.read_count += 1
        raise USBError('timed out', errno=errno.ETIMEDOUT)


class TimeoutWriteDevice:
    def write(self, endpoint, data):
        raise USBError('timed out', errno=errno.ETIMEDOUT)


class DisconnectedWriteDevice:
    def write(self, endpoint, data):
        raise USBError('device gone', errno=errno.ENODEV)


class UsbStaleHandleTests(unittest.TestCase):
    def test_disconnect_drops_the_stale_handle(self):
        transport = Usb()
        transport.dev = DisconnectedWriteDevice()

        with self.assertRaises(USBError):
            transport.cmd(b'\x01')

        self.assertIsNone(transport.dev)

    def test_timeout_keeps_the_handle_for_the_restart_to_reset(self):
        transport = Usb()
        device = TimeoutWriteDevice()
        transport.dev = device

        with self.assertRaises(USBError):
            transport.cmd(b'\x01')

        self.assertIs(transport.dev, device)

    def test_cmd_without_a_handle_fails_as_usb_error(self):
        transport = Usb()

        with self.assertRaises(USBError):
            transport.cmd(b'\x01')


class UsbCancellationTests(unittest.TestCase):
    def test_early_cancel_is_not_cleared_by_wait(self):
        transport = Usb()
        transport.dev = TimeoutDevice()
        transport.request_cancel()

        with self.assertRaises(CancelledException):
            transport.wait_int()

        self.assertEqual(transport.dev.read_count, 0)

    def test_new_operation_explicitly_clears_previous_cancel(self):
        transport = Usb()
        transport.request_cancel()
        transport.clear_cancel()
        self.assertFalse(transport.cancel_event.is_set())


if __name__ == '__main__':
    unittest.main()
