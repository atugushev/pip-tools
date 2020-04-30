from __future__ import absolute_import

import sys
import warnings


class PipToolsBaseWarning:
    pass


class PipToolsPendingDeprecationWarning(PipToolsBaseWarning, PendingDeprecationWarning):
    """
    Deprecates things in future versions.
    """

    pass


class PipToolsDeprecationWarning(PipToolsBaseWarning, DeprecationWarning):
    """
    Deprecates things in the next or a specific version.
    """

    pass


# Setup if warning filters are not configured
if not sys.warnoptions:
    warnings.simplefilter("once", category=PipToolsBaseWarning)
