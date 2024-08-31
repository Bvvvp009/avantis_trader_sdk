from ..types import (
    TradeInput,
    TradeInputOrderType,
    TradeExtendedResponse,
    TradeResponse,
    TradeInfo,
    PendingLimitOrderExtendedResponse,
    MarginUpdateType,
)
import math


class TradeRPC:
    """
    The TradeRPC class contains methods for retrieving trading parameters from the Avantis Protocol.
    """

    def __init__(self, client, FeedClient):
        """
        Constructor for the TradeRPC class.

        Args:
            client: The TraderClient object.
            FeedClient: The FeedClient object.
        """
        self.client = client
        self.FeedClient = FeedClient

    async def build_trade_open_tx(
        self,
        trade_input: TradeInput,
        trade_input_order_type: TradeInputOrderType,
        slippage_percentage: int,
    ):
        """
        Builds a transaction to open a trade.

        Args:
            trade: The trade input object.
            trade_input_order_type: The trade input order type.
            slippage_percentage: The slippage percentage.

        Returns:
            A transaction object.
        """
        Trading = self.client.contracts.get("Trading")

        execution_fee = await self.get_trade_execution_fee()

        if (
            trade_input_order_type == TradeInputOrderType.MARKET
            and not trade_input.openPrice
        ):
            feed_client = self.FeedClient()
            pair_name = await self.client.pairs_cache.get_pair_name_from_index(
                trade_input.pairIndex
            )
            price_data = await feed_client.get_latest_price_updates([pair_name])
            price = int(price_data.parsed[0].converted_price * 10**10)
            trade_input.openPrice = price

        if (
            trade_input_order_type == TradeInputOrderType.LIMIT
            or trade_input_order_type == TradeInputOrderType.STOP_LIMIT
        ) and not trade_input.openPrice:
            raise Exception("Open price is required for LIMIT/STOP LIMIT order type")

        transaction = await Trading.functions.openTrade(
            trade_input.model_dump(),
            trade_input_order_type.value,
            slippage_percentage * 10**10,
            0,
        ).build_transaction(
            {
                "from": trade_input.trader,
                "value": execution_fee,
                "chainId": self.client.chain_id,
                "nonce": await self.client.get_transaction_count(trade_input.trader),
            }
        )

        return transaction

    async def get_trade_execution_fee(self):
        """
        Gets the correct trade execution fee.

        Returns:
            The trade execution fee
        """
        execution_fee = round(0.00035, 18)  # default value

        try:
            feeScalar = 0.001

            estimatedL1Gas = math.floor(22676 * feeScalar)
            estimatedL2Gas = math.floor(850000 * 1.1)

            l2GasPrice = await self.client.async_web3.eth.gas_price
            estimatedL2GasEth = l2GasPrice * estimatedL2Gas

            l1GasPrice = await self.client.l1_async_web3.eth.gas_price
            estimatedL1GasEth = l1GasPrice * estimatedL1Gas

            feeEstimate = estimatedL1GasEth + estimatedL2GasEth
            feeEstimate = round(feeEstimate, 18)
            return feeEstimate
        except Exception as e:
            print("Error getting correct trade execution fee. Using fallback: ", e)
            return execution_fee

    async def get_trades(self, trader: str):
        """
        Gets the trades.

        Args:
            trader: The trader's wallet address.

        Returns:
            The trades.
        """
        result = (
            await self.client.contracts.get("Multicall")
            .functions.getPositions(trader)
            .call()
        )
        trades = []
        pendingOpenLimitOrders = []

        for aggregated_trade in result[0]:  # Access the list of aggregated trades
            (trade, trade_info, margin_fee, liquidation_price) = aggregated_trade

            if trade[7] <= 0:
                continue

            # Extract and format the trade data
            trade_details = {
                "trade": {
                    "trader": trade[0],
                    "pairIndex": trade[1],
                    "index": trade[2],
                    "initialPosToken": trade[3],
                    "positionSizeUSDC": trade[4],
                    "openPrice": trade[5],
                    "buy": trade[6],
                    "leverage": trade[7],
                    "tp": trade[8],
                    "sl": trade[9],
                    "timestamp": trade[10],
                },
                "additional_info": {
                    "openInterestUSDC": trade_info[0],
                    "tpLastUpdated": trade_info[1],
                    "slLastUpdated": trade_info[2],
                    "beingMarketClosed": trade_info[3],
                    "lossProtectionPercentage": await self.client.trading_parameters.get_loss_protection_percentage_by_tier(
                        trade_info[4], trade[1]
                    ),
                },
                "margin_fee": margin_fee,
                "liquidationPrice": liquidation_price,
            }
            trades.append(
                TradeExtendedResponse(
                    trade=TradeResponse(**trade_details["trade"]),
                    additional_info=TradeInfo(**trade_details["additional_info"]),
                    margin_fee=trade_details["margin_fee"],
                    liquidation_price=trade_details["liquidationPrice"],
                )
            )

        for aggregated_order in result[1]:  # Access the list of aggregated orders
            (order, liquidation_price) = aggregated_order

            if order[5] <= 0:
                continue

            # Extract and format the order data
            order_details = {
                "trader": order[0],
                "pairIndex": order[1],
                "index": order[2],
                "positionSize": order[3],
                "buy": order[4],
                "leverage": order[5],
                "tp": order[6],
                "sl": order[7],
                "price": order[8],
                "slippageP": order[9],
                "block": order[10],
                # 'executionFee': order[11],
                "liquidation_price": liquidation_price,
            }
            pendingOpenLimitOrders.append(
                PendingLimitOrderExtendedResponse(**order_details)
            )

        return trades, pendingOpenLimitOrders

    async def build_trade_close_tx(
        self, trader: str, pair_index: int, trade_index: int, collateral_to_close: float
    ):
        """
        Builds a transaction to close a trade.

        Args:
            pair_index: The pair index.
            trade_index: The trade index.
            collateral_to_close: The collateral to close.

        Returns:
            A transaction object.
        """
        Trading = self.client.contracts.get("Trading")

        execution_fee = await self.get_trade_execution_fee()

        transaction = await Trading.functions.closeTradeMarket(
            pair_index, trade_index, collateral_to_close, 0
        ).build_transaction(
            {
                "from": trader,
                "chainId": self.client.chain_id,
                "nonce": await self.client.get_transaction_count(trader),
                "value": execution_fee,
            }
        )

        return transaction

    async def build_order_cancel_tx(
        self, trader: str, pair_index: int, trade_index: int
    ):
        """
        Builds a transaction to cancel an order.

        Args:
            pair_index: The pair index.
            trade_index: The trade/order index.
            position_size: The position size.

        Returns:
            A transaction object.
        """
        Trading = self.client.contracts.get("Trading")

        transaction = await Trading.functions.cancelOpenLimitOrder(
            pair_index, trade_index
        ).build_transaction(
            {
                "from": trader,
                "chainId": self.client.chain_id,
                "nonce": await self.client.get_transaction_count(trader),
            }
        )

        return transaction

    async def build_trade_margin_update_tx(
        self,
        trader: str,
        pair_index: int,
        trade_index: int,
        margin_update_type: MarginUpdateType,
        collateral_change: float,
    ):
        """
        Builds a transaction to update the margin of a trade.

        Args:
            pair_index: The pair index.
            trade_index: The trade index.
            margin_update_type: The margin update type.
            collateral_change: The collateral change.

        Returns:
            A transaction object.
        """
        Trading = self.client.contracts.get("Trading")

        collateral_change = int(collateral_change * 10**6)
        fee_in_wei = 1 * 10**18

        feed_client = self.FeedClient()

        pair_name = await self.client.pairs_cache.get_pair_name_from_index(pair_index)

        price_data = await feed_client.get_latest_price_updates([pair_name])

        price_update_data = "0x" + price_data.binary.data[0]

        transaction = await Trading.functions.updateMargin(
            pair_index,
            trade_index,
            margin_update_type.value,
            collateral_change,
            [price_update_data],
        ).build_transaction(
            {
                "from": trader,
                "chainId": self.client.chain_id,
                "value": fee_in_wei,
                "nonce": await self.client.get_transaction_count(trader),
            }
        )

        return transaction