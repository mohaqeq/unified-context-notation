import platform
import sys

import sqlfluff
from sqlfluff.api import info


def test_version_info_keys_and_values():
    v = info.version_info()
    assert set(v) == {"sqlfluff", "python", "implementation"}
    assert v["sqlfluff"] == sqlfluff.__version__
    assert v["python"] == platform.python_version()
    assert v["python"].count(".") == 2
    assert v["implementation"] == sys.implementation.name
    assert all(isinstance(x, str) for x in v.values())


def test_existing_info_still_works():
    assert info.list_dialects()
    assert info.list_rules()
