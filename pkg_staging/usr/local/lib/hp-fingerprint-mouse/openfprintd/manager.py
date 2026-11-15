
import dbus.service
import logging
from openfprintd.device import Device, NoSuchDevice

INTERFACE_NAME = 'net.reactivated.Fprint.Manager'

class Manager(dbus.service.Object):
    def __init__(self, bus_name):
        dbus.service.Object.__init__(self, bus_name, '/net/reactivated/Fprint/Manager')
        self.bus_name = bus_name
        self.devices = {}

    def _online_devices(self):
        return [dev for dev in self.devices.values() if dev.online]

    def remove_device(self, device):
        """Drop a wrapper whose backing driver has gone away."""
        for path, wrapped in list(self.devices.items()):
            if wrapped is device:
                logging.debug('Removing offline device %s' % path)
                del self.devices[path]
                break

    @dbus.service.method(dbus_interface=INTERFACE_NAME,
                         in_signature='', 
                         out_signature='ao',
                         connection_keyword='connection',
                         sender_keyword='sender')
    def GetDevices(self, sender, connection):
        logging.debug("GetDevices")
        return self._online_devices()

    @dbus.service.method(dbus_interface=INTERFACE_NAME,
                         in_signature='', 
                         out_signature='o',
                         connection_keyword='connection',
                         sender_keyword='sender')
    def GetDefaultDevice(self, sender, connection):
        logging.debug("GetDefaultDevice")

        devices = self._online_devices()
        if len(devices) == 0:
            logging.debug('no devices')
            raise NoSuchDevice()

        logging.debug('returning %s' % repr(devices[0]))

        return devices[0]

    # TODO: use a different interface name for this
    @dbus.service.method(dbus_interface=INTERFACE_NAME,
                         in_signature='o', 
                         out_signature='',
                         connection_keyword='connection',
                         sender_keyword='sender')
    def RegisterDevice(self, dev, sender, connection):
        # TODO: polkit: make sure we're talking to a root process!
        logging.debug('RegisterDevice %s %s' % (sender, repr(dev)))

        if dev not in self.devices:
            self.devices[dev] = Device(self)

        wrap = self.devices[dev]
        wrap.set_target(dev, sender)
        
    @dbus.service.method(dbus_interface=INTERFACE_NAME,
                         in_signature='', 
                         out_signature='',
                         connection_keyword='connection',
                         sender_keyword='sender')
    def Suspend(self, sender, connection):
        logging.debug('Suspend')

        for dev in list(self.devices.values()):
            dev.Suspend()

        logging.debug('Suspend complete')

    @dbus.service.method(dbus_interface=INTERFACE_NAME,
                         in_signature='', 
                         out_signature='',
                         connection_keyword='connection',
                         sender_keyword='sender')
    def Resume(self, sender, connection):
        logging.debug('Resume')

        for dev in list(self.devices.values()):
            dev.Resume()

        logging.debug('Resume complete')
