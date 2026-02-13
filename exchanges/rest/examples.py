#!/usr/bin/env python3
"""
Example usage and basic tests for REST API clients.
This demonstrates how to use each exchange's REST client.
"""
import os
from exchanges.rest import (
    BybitRestClient,
    KuCoinRestClient,
    HTXRestClient,
    XTRestClient,
    MEXCRestClient
)


def example_bybit():
    """Example usage of Bybit REST client."""
    print("\n=== Bybit Example ===")
    
    # Initialize client (uses environment variables)
    client = BybitRestClient()
    
    # Or with explicit credentials
    # client = BybitRestClient(api_key='your_key', api_secret='your_secret')
    
    try:
        # Get balance
        balances = client.get_balance()
        print(f"Balances: {balances}")
        
        # Get specific currency balance
        usdt_balance = client.get_balance(currency='USDT')
        print(f"USDT Balance: {usdt_balance}")
        
        # Place limit order
        order = client.place_order(
            symbol='BTC-USDT',
            side='buy',
            order_type='limit',
            quantity=0.001,
            price=40000.0
        )
        print(f"Order placed: {order}")
        
        # Get order status
        status = client.get_order_status(
            order_id=order['order_id'],
            symbol='BTC-USDT'
        )
        print(f"Order status: {status}")
        
        # Cancel order
        cancel = client.cancel_order(
            order_id=order['order_id'],
            symbol='BTC-USDT'
        )
        print(f"Order cancelled: {cancel}")
        
    except Exception as e:
        print(f"Error: {e}")


def example_kucoin():
    """Example usage of KuCoin REST client."""
    print("\n=== KuCoin Example ===")
    
    # Initialize client (requires passphrase)
    client = KuCoinRestClient()
    
    try:
        # Get balance
        balances = client.get_balance()
        print(f"Balances: {balances}")
        
        # Place limit order
        order = client.place_order(
            symbol='BTC-USDT',
            side='buy',
            order_type='limit',
            quantity=0.001,
            price=40000.0
        )
        print(f"Order placed: {order}")
        
        # Get order status
        status = client.get_order_status(
            order_id=order['order_id'],
            symbol='BTC-USDT'
        )
        print(f"Order status: {status}")
        
        # Cancel order
        cancel = client.cancel_order(
            order_id=order['order_id'],
            symbol='BTC-USDT'
        )
        print(f"Order cancelled: {cancel}")
        
    except Exception as e:
        print(f"Error: {e}")


def example_htx():
    """Example usage of HTX REST client."""
    print("\n=== HTX (Huobi) Example ===")
    
    # Initialize client
    client = HTXRestClient()
    
    try:
        # Get balance
        balances = client.get_balance()
        print(f"Balances: {balances}")
        
        # Place limit order
        order = client.place_order(
            symbol='BTC-USDT',
            side='buy',
            order_type='limit',
            quantity=0.001,
            price=40000.0
        )
        print(f"Order placed: {order}")
        
        # Get order status
        status = client.get_order_status(
            order_id=order['order_id'],
            symbol='btcusdt'
        )
        print(f"Order status: {status}")
        
        # Cancel order
        cancel = client.cancel_order(
            order_id=order['order_id'],
            symbol='btcusdt'
        )
        print(f"Order cancelled: {cancel}")
        
    except Exception as e:
        print(f"Error: {e}")


def example_xt():
    """Example usage of XT REST client."""
    print("\n=== XT.COM Example ===")
    
    # Initialize client
    client = XTRestClient()
    
    try:
        # Get balance
        balances = client.get_balance()
        print(f"Balances: {balances}")
        
        # Place limit order
        order = client.place_order(
            symbol='BTC-USDT',
            side='BUY',
            order_type='LIMIT',
            quantity=0.001,
            price=40000.0
        )
        print(f"Order placed: {order}")
        
        # Get order status
        status = client.get_order_status(
            order_id=order['order_id'],
            symbol='btc_usdt'
        )
        print(f"Order status: {status}")
        
        # Cancel order
        cancel = client.cancel_order(
            order_id=order['order_id'],
            symbol='btc_usdt'
        )
        print(f"Order cancelled: {cancel}")
        
    except Exception as e:
        print(f"Error: {e}")


def example_mexc():
    """Example usage of MEXC REST client."""
    print("\n=== MEXC Example ===")
    
    # Initialize client
    client = MEXCRestClient()
    
    try:
        # Get balance
        balances = client.get_balance()
        print(f"Balances: {balances}")
        
        # Place limit order
        order = client.place_order(
            symbol='BTC-USDT',
            side='BUY',
            order_type='LIMIT',
            quantity=0.001,
            price=40000.0
        )
        print(f"Order placed: {order}")
        
        # Get order status
        status = client.get_order_status(
            order_id=order['order_id'],
            symbol='BTCUSDT'
        )
        print(f"Order status: {status}")
        
        # Cancel order
        cancel = client.cancel_order(
            order_id=order['order_id'],
            symbol='BTCUSDT'
        )
        print(f"Order cancelled: {cancel}")
        
    except Exception as e:
        print(f"Error: {e}")


def test_symbol_normalization():
    """Test symbol format conversion for each exchange."""
    print("\n=== Symbol Normalization Tests ===")
    
    # Test Bybit (BTCUSDT)
    bybit = BybitRestClient(api_key='test', api_secret='test')
    assert bybit._normalize_symbol('BTC-USDT') == 'BTCUSDT'
    assert bybit._normalize_symbol('BTC_USDT') == 'BTCUSDT'
    print("✓ Bybit symbol normalization: BTC-USDT -> BTCUSDT")
    
    # Test KuCoin (BTC-USDT)
    kucoin = KuCoinRestClient(api_key='test', api_secret='test', api_passphrase='test')
    assert kucoin._normalize_symbol('BTCUSDT') == 'BTC-USDT'
    assert kucoin._normalize_symbol('BTC_USDT') == 'BTC-USDT'
    print("✓ KuCoin symbol normalization: BTCUSDT -> BTC-USDT")
    
    # Test HTX (btcusdt)
    htx = HTXRestClient(api_key='test', api_secret='test')
    assert htx._normalize_symbol('BTC-USDT') == 'btcusdt'
    assert htx._normalize_symbol('BTC_USDT') == 'btcusdt'
    print("✓ HTX symbol normalization: BTC-USDT -> btcusdt")
    
    # Test XT (btc_usdt)
    xt = XTRestClient(api_key='test', api_secret='test')
    assert xt._normalize_symbol('BTC-USDT') == 'btc_usdt'
    assert xt._normalize_symbol('BTCUSDT') == 'btc_usdt'
    print("✓ XT symbol normalization: BTC-USDT -> btc_usdt")
    
    # Test MEXC (BTCUSDT)
    mexc = MEXCRestClient(api_key='test', api_secret='test')
    assert mexc._normalize_symbol('BTC-USDT') == 'BTCUSDT'
    assert mexc._normalize_symbol('btc_usdt') == 'BTCUSDT'
    print("✓ MEXC symbol normalization: BTC-USDT -> BTCUSDT")
    
    print("\nAll symbol normalization tests passed!")


def main():
    """Run examples based on available credentials."""
    print("REST API Client Examples")
    print("=" * 50)
    
    # Test symbol normalization (doesn't require real credentials)
    test_symbol_normalization()
    
    # Run examples only if credentials are available
    if os.getenv('BYBIT_API_KEY') and os.getenv('BYBIT_API_SECRET'):
        example_bybit()
    
    if os.getenv('KUCOIN_API_KEY') and os.getenv('KUCOIN_API_SECRET') and os.getenv('KUCOIN_API_PASSPHRASE'):
        example_kucoin()
    
    if os.getenv('HTX_API_KEY') and os.getenv('HTX_API_SECRET'):
        example_htx()
    
    if os.getenv('XT_API_KEY') and os.getenv('XT_API_SECRET'):
        example_xt()
    
    if os.getenv('MEXC_API_KEY') and os.getenv('MEXC_API_SECRET'):
        example_mexc()
    
    print("\n" + "=" * 50)
    print("Examples complete!")
    print("\nTo run live examples, set environment variables:")
    print("  export BYBIT_API_KEY='your_key'")
    print("  export BYBIT_API_SECRET='your_secret'")
    print("  export KUCOIN_API_KEY='your_key'")
    print("  export KUCOIN_API_SECRET='your_secret'")
    print("  export KUCOIN_API_PASSPHRASE='your_passphrase'")
    print("  export HTX_API_KEY='your_key'")
    print("  export HTX_API_SECRET='your_secret'")
    print("  export XT_API_KEY='your_key'")
    print("  export XT_API_SECRET='your_secret'")
    print("  export MEXC_API_KEY='your_key'")
    print("  export MEXC_API_SECRET='your_secret'")


if __name__ == '__main__':
    main()
