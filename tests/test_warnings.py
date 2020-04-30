import sys
import textwrap

import pytest

from .utils import invoke


@pytest.fixture
def script():
    return textwrap.dedent(
        """\
        from piptools.warnings import (
            PipToolsDeprecationWarning,
            PipToolsPendingDeprecationWarning,
        )
        import warnings

        warnings.warn("deprecated", category=PipToolsDeprecationWarning)
        warnings.warn("pending", category=PipToolsPendingDeprecationWarning)
        """
    )


def test_warnings(script):
    """
    Warnings are shown by default.
    """
    status, output = invoke([sys.executable, "-c", script])

    assert status == 0, output
    assert "PipToolsDeprecationWarning: deprecated\n" in output
    assert "PipToolsPendingDeprecationWarning: pending\n" in output


def test_warning_filters(script):
    """
    Pip-tools doesn't filter warnings (i.e. doesn't force showing warnings)
    if the filters are already configured, for example: `python -W ignore -m compile`.
    """
    status, output = invoke([sys.executable, "-W", "ignore", "-c", script])

    assert status == 0, output
    assert output == ""
