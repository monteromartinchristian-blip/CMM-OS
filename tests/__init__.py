"""CMM OS test suite package.

This package marker gives every test module a unique import identity
(``tests.<subdirectory>.<module>``).

It is required because ``tests/platform/`` cannot be imported as the top-level
package ``platform``: that name is already owned by the Python standard library,
so pytest's default ``prepend`` import mode fails with
``ModuleNotFoundError: No module named 'platform.test_...'; 'platform' is not a
package``.  Without this marker, ``tests/platform/`` would have to be imported
rootless, which collides with the equally rootless
``tests/workflows/test_contracts.py``.
"""
