import enum


class ExtensionTrigger(str, enum.Enum):
   

    BID_RECEIVED = "BID_RECEIVED"  
    ANY_RANK_CHANGE = "ANY_RANK_CHANGE"  
    L1_RANK_CHANGE = "L1_RANK_CHANGE"  


class AuctionStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"  
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"  
    FORCE_CLOSED = "FORCE_CLOSED"  


class AuctionEventType(str, enum.Enum):
    RFQ_CREATED = "RFQ_CREATED"
    BID_SUBMITTED = "BID_SUBMITTED"
    AUCTION_EXTENDED = "AUCTION_EXTENDED"
    AUCTION_CLOSED = "AUCTION_CLOSED"
    AUCTION_FORCE_CLOSED = "AUCTION_FORCE_CLOSED"
