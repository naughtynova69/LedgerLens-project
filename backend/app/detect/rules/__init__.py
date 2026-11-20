"""Import all rule modules so each @register decorator runs at package load."""
from . import cancelled_service  # noqa: F401
from . import contract_price     # noqa: F401
from . import currency_tax       # noqa: F401
from . import duplicate          # noqa: F401
from . import grn_mismatch       # noqa: F401  (R7)
from . import po_mismatch        # noqa: F401
from . import split_po           # noqa: F401  (R6)
from . import graph_cross_entity_duplicate  # noqa: F401  (R8)
from . import graph_collusion               # noqa: F401  (R9)
from . import graph_lineage_credits         # noqa: F401  (R10)
