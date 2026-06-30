from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Ontario typical drive-away estimate (Ottawa area dealer purchase).
HST_RATE = 0.13
OMVIC_FEE = 12.50
REGISTRATION_FEE = 100.00
MISC_FEE = 20.00
DEALER_ADMIN_FEE = 500.00


@dataclass
class DriveAwayEstimate:
    list_price: int
    hst: float
    omvic: float
    registration: float
    miscellaneous: float
    dealer_fee: float
    drive_away: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "list_price": self.list_price,
            "hst": self.hst,
            "omvic": self.omvic,
            "registration": self.registration,
            "miscellaneous": self.miscellaneous,
            "dealer_fee": self.dealer_fee,
            "drive_away": self.drive_away,
        }


def estimate_drive_away(list_price: int, include_dealer_fee: bool = True) -> DriveAwayEstimate:
    hst = round(list_price * HST_RATE, 2)
    dealer_fee = DEALER_ADMIN_FEE if include_dealer_fee else 0.0
    total = list_price + hst + OMVIC_FEE + REGISTRATION_FEE + MISC_FEE + dealer_fee
    return DriveAwayEstimate(
        list_price=list_price,
        hst=hst,
        omvic=OMVIC_FEE,
        registration=REGISTRATION_FEE,
        miscellaneous=MISC_FEE,
        dealer_fee=dealer_fee,
        drive_away=round(total),
    )
