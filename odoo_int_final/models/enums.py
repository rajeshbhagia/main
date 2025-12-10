from enum import Enum

class CustomerTypeEnum(str, Enum):
    INDIVIDUAL = "01"
    BUSINESS = "02"


class SellerTypeEnum(str, Enum):
    STANDARD = "01"
    MARKETPLACE = "02"
    PLATFORM = "03"



