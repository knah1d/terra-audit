"""Version identifiers for reproducible remote-sensing features."""

import numpy as np

PROCESSING_VERSION = "s1-linear-rvi-v2"
MULTICROP_VERSION = "multicrop-s1-s2-v1"


def rvi_from_db(vv, vh):
    """Dual-pol RVI from power, not logarithmic dB values."""
    vv_power = np.power(10.0, np.asarray(vv) / 10.0)
    vh_power = np.power(10.0, np.asarray(vh) / 10.0)
    return 4 * vh_power / (vv_power + vh_power)
