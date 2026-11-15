
import dbus
import dbus.service
import logging
import pwd
from gi.repository import GLib


INTERFACE_NAME = 'net.reactivated.Fprint.Device'

class NoSuchDevice(dbus.DBusException):
    _dbus_error_name = 'net.reactivated.Fprint.Error.NoSuchDevice'

    def __init__(self):
        super().__init__('No usable fingerprint device')

class AlreadyInUse(dbus.DBusException):
    _dbus_error_name = 'net.reactivated.Fprint.Error.AlreadyInUse'

    def __init__(self):
        super().__init__('Device is already in use')

class ClaimDevice(dbus.DBusException):
    _dbus_error_name = 'net.reactivated.Fprint.Error.ClaimDevice'

    def __init__(self):
        super().__init__('Client must claim device first')

class PermissionDenied(dbus.DBusException):
    _dbus_error_name = 'net.reactivated.Fprint.Error.PermissionDenied'

    def __init__(self):
        super().__init__('Permission denied')

class Device(dbus.service.Object):
    cnt=0

    def __init__(self, mgr):
        self.manager = mgr
        bus_name = mgr.bus_name
        dbus.service.Object.__init__(self, bus_name, '/net/reactivated/Fprint/Device/%d' % Device.cnt)
        Device.cnt += 1
        self.bus = bus_name.get_bus()
        self.target_props = dbus.Dictionary({ 
                'name':  'DBus driver', 
                'num-enroll-stages': 5,
                'scan-type': 'press'
            })
        # The backing driver is registered later by RegisterDevice() and can
        # disappear at any time (USB re-enumeration, service restart, crash).
        # Every method must tolerate a missing target instead of raising
        # AttributeError into the D-Bus client.
        self.target = None
        self.target_sender = None
        self.target_watcher = None
        self.signal_matches = []
        self.owner_watcher = None
        self.claimed_by = None
        self.claim_sender = None
        self.busy = False
        self.operation = None
        self.removed = False

        self.suspended = False
        self.callbacks = []

    @property
    def online(self):
        return self.target is not None

    def _require_target(self):
        if self.target is None:
            raise NoSuchDevice()
        return self.target

    def proxy_call(self, cb, errback=None):
        if self.target is None:
            logging.debug('The service is offline, failing the call')
            if errback is not None:
                errback(NoSuchDevice())
            return

        if self.suspended:
            logging.debug('The service is suspended, delay the call')
            self.callbacks += [(cb, errback)]
            return

        try:
            cb()
        except dbus.DBusException as error:
            if errback is not None:
                errback(error)
            else:
                raise


    def call_cbs(self):
        callbacks, self.callbacks = self.callbacks, []
        for cb, errback in callbacks:
            try:
                if self.target is None:
                    if errback is not None:
                        errback(NoSuchDevice())
                    continue
                cb()
            except Exception as e:
                logging.debug('callback resulted in error: %s' % repr(e))
                if errback is not None:
                    try:
                        errback(NoSuchDevice())
                    except Exception:
                        logging.debug('errback resulted in error', exc_info=True)

        logging.debug('Callbacks complete')

        self.suspended = False

    def _cancel_target_watcher(self):
        if self.target_watcher is not None:
            try:
                self.target_watcher.cancel()
            except Exception:
                logging.debug('Failed to cancel target watcher', exc_info=True)
            self.target_watcher = None

        for match in self.signal_matches:
            try:
                match.remove()
            except Exception:
                logging.debug('Failed to disconnect target signal', exc_info=True)
        self.signal_matches = []

    def _fail_active_operation(self):
        operation = self.operation
        self.operation = None
        self.busy = False

        if operation == 'enroll':
            try:
                self.EnrollStatus('enroll-failed', True)
            except Exception:
                logging.debug('Failed to report lost enrollment', exc_info=True)
        elif operation == 'verify':
            try:
                self.VerifyStatus('verify-no-match', True)
            except Exception:
                logging.debug('Failed to report lost verification', exc_info=True)

    def set_target(self, target_name, sender):
        self._cancel_target_watcher()
        self.target_sender = sender
        self.target = self.bus.get_object(sender, target_name, introspect=False)
        target = dbus.Interface(self.target, 'io.github.uunicorn.Fprint.Device')
        self.target = target
        self.signal_matches = [
            target.connect_to_signal('VerifyStatus', self.VerifyStatus),
            target.connect_to_signal('VerifyFingerSelected', self.VerifyFingerSelected),
            target.connect_to_signal('EnrollStatus', self.EnrollStatus),
        ]
        self.removed = False

        def watch_cb(name):
            if name == '':
                logging.debug('%s went offline' % sender)
                if self.target_sender == sender:
                    self.unset_target()

        self.target_watcher = self.connection.watch_name_owner(sender, watch_cb)

        # We called from RegisterDeivce DBus method. 
        # Calling device methods from here will cause a deadlock.
        # Postpone processing till RegisterDeivce method is finished.

        def process_offline():
            if not self.suspended:
                self.call_cbs()

        GLib.idle_add(process_offline)

    def unset_target(self):
        logging.debug('Device target went offline')
        already_removed = self.removed

        self.target = None
        self.target_sender = None
        self._cancel_target_watcher()
        self._fail_active_operation()

        # Nothing can service these calls any more. Keep the clients from
        # blocking until their own timeout instead of leaving them queued.
        callbacks, self.callbacks = self.callbacks, []
        for cb, errback in callbacks:
            if errback is not None:
                try:
                    errback(NoSuchDevice())
                except Exception:
                    logging.debug('errback resulted in error', exc_info=True)

        if already_removed:
            return

        self.removed = True
        self.manager.remove_device(self)
        try:
            self.remove_from_connection()
        except Exception:
            logging.debug('Failed to remove device from the bus', exc_info=True)

    def Resume(self):
        self.suspended = False

        if self.target is not None:
            self.target.Resume()

        self.call_cbs()

    def Suspend(self):
        self.suspended = True

        if self.target is not None:
            self.target.Suspend()

    # ------------------ Template Database --------------------------

    @dbus.service.method(dbus_interface=INTERFACE_NAME,
                         in_signature="s", 
                         out_signature="as",
                         connection_keyword='connection',
                         sender_keyword='sender',
                         async_callbacks=('callback', 'errback'))
    def ListEnrolledFingers(self, username, sender, connection, callback, errback):
        logging.debug('ListEnrolledFingers')

        if username is None or username == '':
            uid=self.bus.get_unix_user(sender)
            pw=pwd.getpwuid(uid)
            username=pw.pw_name

        def cb():
            callback(self.target.ListEnrolledFingers(username, signature='s'))

        self.proxy_call(cb, errback)

    @dbus.service.method(dbus_interface=INTERFACE_NAME,
                         in_signature='s', 
                         out_signature='',
                         connection_keyword='connection',
                         sender_keyword='sender')
    def DeleteEnrolledFingers(self, username, sender, connection):
        logging.debug('DeleteEnrolledFingers: %s' % username)

        uid = self.bus.get_unix_user(sender)
        pw = pwd.getpwuid(uid)
        if username is None or len(username) == 0:
            username = pw.pw_name
        elif username != pw.pw_name and uid != 0:
            raise PermissionDenied()

        return self._require_target().DeleteEnrolledFingers(username, signature='s')

    @dbus.service.method(dbus_interface=INTERFACE_NAME,
                         in_signature='', 
                         out_signature='',
                         connection_keyword='connection',
                         sender_keyword='sender')
    def DeleteEnrolledFingers2(self, sender, connection):
        logging.debug('DeleteEnrolledFingers2')

        if self.owner_watcher is None or self.claim_sender != sender:
            raise ClaimDevice()

        return self._require_target().DeleteEnrolledFingers(self.claimed_by, signature='s')

    # ------------------ Claim/Release --------------------------

    @dbus.service.method(dbus_interface=INTERFACE_NAME,
                         in_signature='s', 
                         out_signature='',
                         connection_keyword='connection',
                         sender_keyword='sender')
    def Claim(self, username, sender, connection):
        logging.debug('Claim')

        uid=self.bus.get_unix_user(sender)
        pw=pwd.getpwuid(uid)
        if username is None or len(username) == 0:
            username = pw.pw_name
        elif username != pw.pw_name and uid != 0:
            raise PermissionDenied()

        if self.owner_watcher is not None:
            raise AlreadyInUse()

        def watch_cb(x):
            if x == '':
                self.do_release()

        self.owner_watcher = self.connection.watch_name_owner(sender, watch_cb)
        self.claimed_by = username
        self.claim_sender = sender

    @dbus.service.method(dbus_interface=INTERFACE_NAME,
                         in_signature='', 
                         out_signature='',
                         connection_keyword='connection',
                         sender_keyword='sender')
    def Release(self, sender, connection):
        logging.debug('Release')

        if self.owner_watcher is None or self.claim_sender != sender:
            raise ClaimDevice()
        
        self.do_release()

    def do_release(self):
        logging.debug('do_release')
        self.claimed_by = None
        self.claim_sender = None

        if self.owner_watcher is not None:
            self.owner_watcher.cancel()
            self.owner_watcher = None

        was_busy = self.busy
        self.busy = False
        self.operation = None

        # The driver may already be gone (USB re-enumeration, crash), in which
        # case there is nothing left to cancel.
        if was_busy and self.target is not None:
            try:
                self.target.Cancel(signature='')
            except Exception as error:
                logging.debug('Cancel on release failed: %s' % repr(error))

    # ------------------ Verify --------------------------

    @dbus.service.method(dbus_interface=INTERFACE_NAME,
                         in_signature='s', 
                         out_signature='',
                         connection_keyword='connection',
                         sender_keyword='sender')
    def VerifyStart(self, finger_name, sender, connection):
        logging.debug('VerifyStart')

        if self.owner_watcher is None or self.claim_sender != sender:
            raise ClaimDevice()

        target = self._require_target()
        self.busy = True
        self.operation = 'verify'
        try:
            return target.VerifyStart(self.claimed_by, finger_name, signature='ss')
        except Exception:
            self.busy = False
            self.operation = None
            raise


    @dbus.service.method(dbus_interface=INTERFACE_NAME,
                         in_signature='', 
                         out_signature='',
                         connection_keyword='connection',
                         sender_keyword='sender')
    def VerifyStop(self, sender, connection):
        logging.debug('VerifyStop')

        if self.owner_watcher is None or self.claim_sender != sender:
            raise ClaimDevice()
        
        self.busy = False
        self.operation = None
        if self.target is not None:
            self.target.Cancel(signature='')

    @dbus.service.signal(dbus_interface=INTERFACE_NAME, signature='s')
    def VerifyFingerSelected(self, finger):
        logging.debug('VerifyFingerSelected')

    @dbus.service.signal(dbus_interface=INTERFACE_NAME, signature='sb')
    def VerifyStatus(self, result, done):
        logging.debug('VerifyStatus')
        if done:
            self.busy = False
            self.operation = None

    # ------------------ Enroll --------------------------

    @dbus.service.method(dbus_interface=INTERFACE_NAME,
                         in_signature='s', 
                         out_signature='',
                         connection_keyword='connection',
                         sender_keyword='sender')
    def EnrollStart(self, finger_name, sender, connection):
        logging.debug('EnrollStart')

        if self.owner_watcher is None or self.claim_sender != sender:
            raise ClaimDevice()

        target = self._require_target()
        self.busy = True
        self.operation = 'enroll'
        logging.debug('Actually calling target...')
        try:
            rc = target.EnrollStart(self.claimed_by, finger_name, signature='ss')
        except Exception:
            self.busy = False
            self.operation = None
            raise
        logging.debug('...rc=%s' % repr(rc))
        return rc


    @dbus.service.method(dbus_interface=INTERFACE_NAME,
                         in_signature='', 
                         out_signature='',
                         connection_keyword='connection',
                         sender_keyword='sender')
    def EnrollStop(self, sender, connection):
        logging.debug('EnrollStop')

        if self.owner_watcher is None or self.claim_sender != sender:
            raise ClaimDevice()

        self.busy = False
        self.operation = None
        if self.target is not None:
            self.target.Cancel(signature='')


    @dbus.service.signal(dbus_interface=INTERFACE_NAME, signature='sb')
    def EnrollStatus(self, result, done):
        logging.debug('EnrollStatus')
        if done:
            self.busy = False
            self.operation = None

    # ------------------ Debug --------------------------

    @dbus.service.method(dbus_interface=INTERFACE_NAME,
                         in_signature='s', 
                         out_signature='s',
                         connection_keyword='connection',
                         sender_keyword='sender')
    def RunCmd(self, s, sender, connection):
        logging.debug('RunCmd')
        return self._require_target().RunCmd(s, signature='s')

    # ------------------ Props --------------------------

    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature='ss', out_signature='v')
    def Get(self, interface, prop):
        logging.debug('Get %s.%s' % (interface, prop))
        
        return self.GetAll(interface)[prop]

    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature='ssv')
    def Set(self, interface, prop, value):
        logging.debug('Set %s.%s=%s' % (interface, prop, repr(value)))
        
        if interface != INTERFACE_NAME:
            raise dbus.exceptions.DBusException('net.reactivated.Fprint.Error.UnknownInterface')
        
        raise dbus.exceptions.DBusException('net.reactivated.Fprint.Error.NotImplemented')

    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature='s', out_signature='a{sv}')
    def GetAll(self, interface):
        logging.debug('GetAll %s' % interface)
        
        if interface != INTERFACE_NAME:
            raise dbus.exceptions.DBusException('net.reactivated.Fprint.Error.UnknownInterface')

        return self.target_props
