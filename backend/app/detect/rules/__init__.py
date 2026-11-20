"""Import all rule modules so each @register decorator runs at package load."""
from . import cancelled_service  # noqa: F401
from . import contract_price     # noqa: F401
from . import currency_tax       # noqa: F401
from . import duplicate          # noqa: F401
from . import po_mismatch        # noqa: F401
