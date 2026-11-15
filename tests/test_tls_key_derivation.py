import unittest
from unittest.mock import MagicMock
from binascii import hexlify
from hashlib import sha256
import hmac

from validitysensor.tls import Tls, password_hardcoded, gwk_sign_hardcoded, prf
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

class TestTlsDirectKey(unittest.TestCase):
    def test_direct_password_hardcoded_derivation(self):
        """Verify that external USB accessories (e.g. HP USB Fingerprint Mouse)
        without DMI binding decrypt using direct password_hardcoded."""
        # Generate a synthetic client key blob
        x = b'\x11' * 32
        y = b'\x22' * 32
        d = b'\x33' * 32
        m = x + y + d
        pad_len = 16 - (len(m) % 16)
        m = m + bytes([pad_len]) * pad_len

        iv = b'\x44' * 16
        cipher = Cipher(algorithms.AES(password_hardcoded), modes.CBC(iv), backend=default_backend())
        enc = cipher.encryptor()
        ct = enc.update(m) + enc.finalize()
        c = iv + ct

        val_key = prf(password_hardcoded, b'GWK_SIGN' + gwk_sign_hardcoded, 0x20)
        hs = hmac.new(val_key, c, sha256).digest()

        priv_blob = b'\x02' + c + hs

        mock_usb = MagicMock()
        t = Tls(mock_usb)
        t.handle_priv(priv_blob)

        self.assertEqual(t.psk_encryption_key, password_hardcoded)
        self.assertEqual(t.psk_validation_key, val_key)
        self.assertIsNotNone(t.priv_key)

if __name__ == '__main__':
    unittest.main()
