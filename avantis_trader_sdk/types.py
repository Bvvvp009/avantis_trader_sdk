from pydantic import (
    BaseModel,
    Field,
    conint,
    field_validator,
    ValidationError,
    model_validator,
)
from enum import Enum
from typing import Dict, Optional, List, Union
import time
import re


class PairInfoFeed(BaseModel):
    maxDeviationP: float
    feedId: str

    @field_validator("maxDeviationP", mode="before")
    def convert_max_deviation(cls, v):
        return v / 10**10


class PairInfo(BaseModel):
    from_: str = Field(..., alias="from")
    to: str
    feed: PairInfoFeed
    backupFeed: PairInfoFeed
    constant_spread_bps: float = Field(..., alias="spreadP")
    price_impact_parameter: float = Field(..., alias="priceImpactMultiplier")
    skew_impact_parameter: float = Field(..., alias="skewImpactMultiplier")
    group_index: int = Field(..., alias="groupIndex")
    fee_index: int = Field(..., alias="feeIndex")
    group_open_interest_percentage: float = Field(
        ..., alias="groupOpenInterestPecentage"
    )
    max_wallet_oi: float = Field(..., alias="maxWalletOI")

    @field_validator("price_impact_parameter", "skew_impact_parameter", mode="before")
    def convert_to_float_10(cls, v):
        return v / 10**10

    @field_validator("constant_spread_bps", mode="before")
    def convert_to_float_10_bps(cls, v):
        return v / 10**10 * 100

    class Config:
        populate_by_name = True


class OpenInterest(BaseModel):
    long: Dict[str, float]
    short: Dict[str, float]


class OpenInterestLimits(BaseModel):
    limits: Dict[str, float]


class Utilization(BaseModel):
    utilization: Dict[str, float]


class Skew(BaseModel):
    skew: Dict[str, float]


class MarginFee(BaseModel):
    hourly_base_fee_parameter: Dict[str, float]
    hourly_margin_fee_long_bps: Dict[str, float]
    hourly_margin_fee_short_bps: Dict[str, float]


class MarginFeeSingle(BaseModel):
    hourly_base_fee_parameter: float
    hourly_margin_fee_long_bps: float
    hourly_margin_fee_short_bps: float


class DepthSingle(BaseModel):
    above: float
    below: float


class PairInfoExtended(PairInfo):
    asset_open_interest_limit: float
    asset_open_interest: Dict[str, float]
    asset_utilization: float
    asset_skew: float
    blended_utilization: float
    blended_skew: float
    margin_fee: MarginFeeSingle
    one_percent_depth: DepthSingle
    new_1k_long_opening_fee_bps: float  # Opening fee for new $1,000 long position
    new_1k_short_opening_fee_bps: float  # Opening fee for new $1,000 short position
    new_1k_long_opening_spread_bps: float  # Opening spread for new $1,000 long position
    new_1k_short_opening_spread_bps: (
        float  # Opening spread for new $1,000 short position
    )
    price_impact_spread_long_bps: float
    price_impact_spread_short_bps: float
    skew_impact_spread_long_bps: float
    skew_impact_spread_short_bps: float

    class Config:
        populate_by_name = True


class PairSpread(BaseModel):
    spread: Dict[str, float]


class PriceFeedResponse(BaseModel):
    id: str
    price: Optional[Union[Dict[str, str], Dict[str, float]]] = None
    ema_price: Optional[Union[Dict[str, str], Dict[str, float]]] = None
    pair: Optional[str] = None
    metadata: Optional[Union[Dict[str, str], Dict[str, float]]] = None
    converted_price: float = 0.0
    converted_ema_price: float = 0.0

    @model_validator(mode="before")
    def convert_price(cls, values):
        price_info = values.get("price")
        if price_info:
            values["converted_price"] = float(price_info["price"]) / 10 ** -int(
                price_info["expo"]
            )

        ema_price_info = values.get("ema_price")
        if ema_price_info:
            values["converted_ema_price"] = float(ema_price_info["price"]) / 10 ** -int(
                ema_price_info["expo"]
            )

        return values


class PriceFeesUpdateBinary(BaseModel):
    encoding: str
    data: List[str]


class PriceFeedUpdatesResponse(BaseModel):
    binary: PriceFeesUpdateBinary
    parsed: List[PriceFeedResponse]


class Spread(BaseModel):
    long: Optional[Dict[str, float]] = None
    short: Optional[Dict[str, float]] = None

    @model_validator(mode="before")
    def check_at_least_one(cls, values):
        if not values.data.get("long") and not values.data.get("short"):
            raise ValueError('At least one of "long" or "short" must be present.')
        return values


class Depth(BaseModel):
    above: Optional[Dict[str, float]] = None
    below: Optional[Dict[str, float]] = None

    @model_validator(mode="before")
    def check_at_least_one(cls, values):
        if not values.data.get("above") and not values.data.get("below"):
            raise ValueError('At least one of "above" or "below" must be present.')
        return values


class Fee(BaseModel):
    long: Optional[Dict[str, float]] = None
    short: Optional[Dict[str, float]] = None

    @model_validator(mode="before")
    def check_at_least_one(cls, values):
        if not values.data.get("long") and not values.data.get("short"):
            raise ValueError('At least one of "long" or "short" must be present.')
        return values


class TradeInput(BaseModel):
    trader: str = "0x1234567890123456789012345678901234567890"
    pairIndex: int = Field(..., alias="pair_index")
    index: int = Field(0, alias="trade_index")
    initialPosToken: Optional[int] = Field(None, alias="open_collateral")
    positionSizeUSDC: Optional[int] = Field(None, alias="position_size_usdc")
    openPrice: int = Field(0, alias="open_price")
    buy: bool = Field(..., alias="is_long")
    leverage: int
    tp: Optional[int] = 0
    sl: Optional[int] = 0
    timestamp: Optional[int] = None

    @field_validator("trader")
    def validate_eth_address(cls, v):
        if not re.match(r"^0x[a-fA-F0-9]{40}$", v):
            raise ValueError("Invalid Ethereum address")
        return v

    @field_validator("tp")
    def validate_tp(cls, v, values):
        if values.data.get("openPrice") not in [0, None] and v in [0, None]:
            raise ValueError("tp is required when openPrice is provided and is not 0")
        return v

    @field_validator("openPrice", "tp", "sl", "leverage", mode="before")
    def convert_to_float_10(cls, v):
        return int(v * 10**10)

    @model_validator(mode="before")
    def assign_and_validate_collateral_and_position_size_usdc(cls, values):
        collateral_in_trade = values.pop("collateral_in_trade", None)
        if collateral_in_trade is not None:
            values["positionSizeUSDC"] = collateral_in_trade

        initialPosToken = values.get("initialPosToken") or values.get("open_collateral")
        positionSizeUSDC = values.get("positionSizeUSDC") or values.get(
            "collateral_in_trade"
        )

        if initialPosToken is None and positionSizeUSDC is None:
            raise ValueError(
                "Either 'open_collateral' or 'collateral_in_trade' must be provided."
            )

        if initialPosToken is not None and positionSizeUSDC is None:
            values["positionSizeUSDC"] = 0
        elif positionSizeUSDC is not None and initialPosToken is None:
            values["initialPosToken"] = 0

        return values

    @field_validator("initialPosToken", "positionSizeUSDC", mode="before")
    def convert_to_float_6(cls, v):
        return int(v * 10**6)

    @field_validator("timestamp", mode="before")
    def set_default_timestamp(cls, v):
        if v is None:
            return int(time.time())
        return v

    class Config:
        populate_by_name = True


class TradeInputOrderType(Enum):
    MARKET = 0
    STOP_LIMIT = 1
    LIMIT = 2


class TradeResponse(BaseModel):
    trader: str
    pair_index: int = Field(..., alias="pairIndex")
    trade_index: int = Field(0, alias="index")
    open_collateral: float = Field(None, alias="initialPosToken")
    collateral_in_trade: float = Field(None, alias="positionSizeUSDC")
    open_price: float = Field(0, alias="openPrice")
    is_long: bool = Field(..., alias="buy")
    leverage: float
    tp: float
    sl: float
    timestamp: int

    @field_validator("trader")
    def validate_eth_address(cls, v):
        if not re.match(r"^0x[a-fA-F0-9]{40}$", v):
            raise ValueError("Invalid Ethereum address")
        return v

    @field_validator("open_price", "tp", "sl", "leverage", mode="before")
    def convert_to_float_10(cls, v):
        return v / 10**10

    @field_validator("open_collateral", "collateral_in_trade", mode="before")
    def convert_to_float_6(cls, v):
        return v / 10**6

    class Config:
        populate_by_name = True


class TradeInfo(BaseModel):
    open_interest_usdc: float = Field(..., alias="openInterestUSDC")
    tp_last_updated: float = Field(..., alias="tpLastUpdated")
    sl_last_updated: float = Field(..., alias="slLastUpdated")
    being_market_closed: bool = Field(..., alias="beingMarketClosed")
    loss_protection_percentage: float = Field(..., alias="lossProtectionPercentage")

    @field_validator("open_interest_usdc", mode="before")
    def convert_to_float_6(cls, v):
        return v / 10**6

    class Config:
        populate_by_name = True


class TradeExtendedResponse(BaseModel):
    trade: TradeResponse
    additional_info: TradeInfo
    margin_fee: float
    liquidation_price: float

    @field_validator("margin_fee", mode="before")
    def convert_to_float_6(cls, v):
        return v / 10**6

    @field_validator("liquidation_price", mode="before")
    def convert_to_float_10(cls, v):
        return v / 10**10

    class Config:
        populate_by_name = True


class PendingLimitOrderResponse(BaseModel):
    trader: str
    pair_index: int = Field(..., alias="pairIndex")
    index: int
    open_collateral: float = Field(..., alias="positionSize")
    buy: bool
    leverage: int
    tp: float
    sl: float
    price: float
    slippage_percentage: float = Field(..., alias="slippageP")
    block: int

    @field_validator("trader")
    def validate_eth_address(cls, v):
        if not re.match(r"^0x[a-fA-F0-9]{40}$", v):
            raise ValueError("Invalid Ethereum address")
        return v

    @field_validator(
        "price", "tp", "sl", "leverage", "slippage_percentage", mode="before"
    )
    def convert_to_float_10(cls, v):
        return v / 10**10

    @field_validator("open_collateral", mode="before")
    def convert_to_float_6(cls, v):
        return v / 10**6

    class Config:
        populate_by_name = True


class PendingLimitOrderExtendedResponse(PendingLimitOrderResponse):
    liquidation_price: float

    @field_validator("liquidation_price", mode="before")
    def convert_liq_to_float_10(cls, v):
        return v / 10**10


class MarginUpdateType(Enum):
    DEPOSIT = 0
    WITHDRAW = 1


class SnapshotOpenInterest(BaseModel):
    long: float
    short: float


class SnapshotGroup(BaseModel):
    group_open_interest_limit: float
    group_open_interest: SnapshotOpenInterest
    group_utilization: float
    group_skew: float
    pairs: Dict[str, PairInfoExtended]


class Snapshot(BaseModel):
    groups: Dict[conint(ge=0), SnapshotGroup]
