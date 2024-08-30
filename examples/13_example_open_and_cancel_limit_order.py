import asyncio

from avantis_trader_sdk import TraderClient
from avantis_trader_sdk.types import TradeInput, TradeInputOrderType

# Trader's private key and wallet address
# ---------------------------------------
# ---------------------------------------
# ---------------------------------------
# Change the following values to your own private key and wallet address
# ---------------------------------------
# ---------------------------------------
# ---------------------------------------
private_key = "0xmyprivatekey"
trader = "0xmywalletaddress"


# We will first prepare trade input, then open a order, get opened order's info and finally cancel the order
async def main():
    # Initialize TraderClient
    provider_url = "https://mainnet.base.org"
    trader_client = TraderClient(provider_url)

    # Get trader's USDC balance
    balance = await trader_client.get_usdc_balance(trader)
    print(f"Balance of {trader} is {balance} USDC")

    # Get pair index of the pair. For example, ETH/USD
    pair_index_of_eth_usd = await trader_client.pairs_cache.get_pair_index("ETH/USD")

    # Prepare trade input
    trade_input = TradeInput(
        trader=trader,  # Trader's wallet address
        open_price=1500,  # Open price of the trade
        pair_index=pair_index_of_eth_usd,  # Pair index
        collateral_in_trade=10,  # Amount of collateral in trade (in USDC)
        is_long=True,  # True for long, False for short
        leverage=25,  # Leverage for the trade
        index=0,  # This is the index of the trade for a pair (0 for the first trade, 1 for the second, etc.)
        tp=4000,  # Take profit price. Max allowed is 500% of open price.
        sl=0,  # Stop loss price
        timestamp=0,  # Timestamp of the trade. 0 for now
    )

    # 1% slippage
    slippage_percentage = 1

    # Order type for the trade (MARKET or LIMIT or STOP_LIMIT)
    trade_input_order_type = TradeInputOrderType.LIMIT

    # Open trade
    open_transaction = await trader_client.trade.build_trade_open_tx(
        trade_input, trade_input_order_type, slippage_percentage
    )

    receipt = await trader_client.sign_and_get_receipt(private_key, open_transaction)

    print(receipt)
    print("Order placed successfully!")

    # Get open and pending trades
    trades, pendingOpenLimitOrders = await trader_client.trade.get_trades(trader)
    print("Pending Open Limit Orders: ", pendingOpenLimitOrders)

    # Select first order to cancel
    order_to_cancel = pendingOpenLimitOrders[0]

    # Close trade
    close_transaction = await trader_client.trade.build_order_cancel_tx(
        trader=trader,
        pair_index=order_to_cancel.pair_index,
        trade_index=order_to_cancel.trade_index,
    )

    receipt = await trader_client.sign_and_get_receipt(private_key, close_transaction)

    print(receipt)

    print("Order cancelled successfully!")


if __name__ == "__main__":
    asyncio.run(main())
