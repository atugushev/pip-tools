import locale
import os
import sys

from piptools.click import secho

# Inject vendored directory into system path.
vendored_path = os.path.abspath(
    os.path.sep.join([os.path.dirname(os.path.realpath(__file__)), "_vendored"])
)
sys.path.insert(0, vendored_path)

# Needed for locale.getpreferredencoding(False) to work
# in pip._internal.utils.encoding.auto_decode
try:
    locale.setlocale(locale.LC_ALL, "")
except locale.Error as e:  # pragma: no cover
    # setlocale can apparently crash if locale are uninitialized
    secho("Ignoring error when setting locale: {}".format(e), fg="red")
