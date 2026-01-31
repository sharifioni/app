"""
CLOB API Client - Trading Interface
Handles order placement, orderbook queries, and trading operations
"""

import requests
import time
import logging
import hmac
import hashlib
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    GTC = "GTC"  # Good Till Cancelled


@dataclass
class OrderBook:
    """Orderbook data structure"""
    token_id: str
    bids: List[tuple]  # [(price, size), ...]
    asks: List[tuple]  # [(price, size), ...]
    timestamp: float

    @property
    def best_bid(self) -> Optional[tuple]:
        return self.bids[0] if self.bids else None

    @property
    def best_ask(self) -> Optional[tuple]:
        return self.asks[0] if self.asks else None

    @property
    def spread(self) -> float:
        if self.best_bid and self.best_ask:
            return self.best_ask[0] - self.best_bid[0]
        return float('inf')

    @property
    def mid_price(self) -> Optional[float]:
        if self.best_bid and self.best_ask:
            return (self.best_bid[0] + self.best_ask[0]) / 2
        return None


@dataclass
class Order:
    """Order data structure"""
    id: Optional[str] = None
    token_id: str = ""
    side: OrderSide = OrderSide.BUY
    order_type: OrderType = OrderType.MARKET
    price: float = 0.0
    size: float = 0.0
    filled_size: float = 0.0
    status: str = "pending"
    created_at: float = 0.0
    filled_at: Optional[float] = None

    @property
    def is_filled(self) -> bool:
        return self.status == "filled" or self.filled_size >= self.size

    @property
    def fill_price(self) -> float:
        return self.price  # Simplified, actual might differ


class CLOBAPI:
    """
    Polymarket CLOB API Client for trading

    Endpoints:
    - /orderbook/{token_id} - Get orderbook
    - /price/{token_id} - Get current price
    - /order - Place order (requires authentication)
    - /order/{id} - Check order status

    Note: This implementation includes simulation mode for testing
    """

    def __init__(self, base_url: str = "https://clob.polymarket.com",
                 api_key: Optional[str] = None,
                 api_secret: Optional[str] = None,
                 proxy: Optional[str] = None,
                 timeout: int = 30,
                 simulation_mode: bool = True):
        """
        Args:
            base_url: CLOB API base URL
            api_key: API key for authenticated endpoints
            api_secret: API secret for signing requests
            proxy: Proxy URL if needed
            timeout: Request timeout in seconds
            simulation_mode: If True, don't place real orders
        """
        self.base_url = base_url
        self.api_key = api_key
        self.api_secret = api_secret
        self.timeout = timeout
        self.simulation_mode = simulation_mode

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        })

        if proxy:
            self.session.proxies = {'http': proxy, 'https': proxy}

        # Track simulated orders
        self._simulated_orders: Dict[str, Order] = {}
        self._order_counter = 0

    def _sign_request(self, method: str, endpoint: str, body: str = "") -> Dict[str, str]:
        """Sign request for authenticated endpoints"""
        if not self.api_key or not self.api_secret:
            return {}

        timestamp = str(int(time.time() * 1000))
        message = f"{timestamp}{method}{endpoint}{body}"
        signature = hmac.new(
            self.api_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

        return {
            'POLY-API-KEY': self.api_key,
            'POLY-TIMESTAMP': timestamp,
            'POLY-SIGNATURE': signature,
        }

    def _request(self, method: str, endpoint: str, params: Optional[Dict] = None,
                 data: Optional[Dict] = None, authenticated: bool = False) -> Any:
        """Make HTTP request"""
        url = f"{self.base_url}{endpoint}"

        headers = {}
        body = ""
        if data:
            import json
            body = json.dumps(data)

        if authenticated:
            headers.update(self._sign_request(method, endpoint, body))

        try:
            if method == "GET":
                response = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
            elif method == "POST":
                response = self.session.post(url, json=data, headers=headers, timeout=self.timeout)
            elif method == "DELETE":
                response = self.session.delete(url, headers=headers, timeout=self.timeout)
            else:
                raise ValueError(f"Unsupported method: {method}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"CLOB API error: {e}")
            raise

    def get_orderbook(self, token_id: str) -> Optional[OrderBook]:
        """
        Get orderbook for a token

        Args:
            token_id: The CLOB token ID

        Returns:
            OrderBook object or None if failed
        """
        try:
            # Note: Actual endpoint may differ, this is based on common patterns
            result = self._request("GET", f"/book", params={'token_id': token_id})

            bids = [(float(b['price']), float(b['size'])) for b in result.get('bids', [])]
            asks = [(float(a['price']), float(a['size'])) for a in result.get('asks', [])]

            return OrderBook(
                token_id=token_id,
                bids=sorted(bids, key=lambda x: -x[0]),  # Highest first
                asks=sorted(asks, key=lambda x: x[0]),   # Lowest first
                timestamp=time.time()
            )
        except Exception as e:
            logger.error(f"Error getting orderbook for {token_id}: {e}")
            return None

    def get_price(self, token_id: str) -> Optional[float]:
        """
        Get current price for a token

        Args:
            token_id: The CLOB token ID

        Returns:
            Current mid price or None
        """
        try:
            result = self._request("GET", f"/price", params={'token_id': token_id})
            return float(result.get('price', 0))
        except Exception as e:
            logger.error(f"Error getting price for {token_id}: {e}")
            return None

    def get_prices(self, token_ids: List[str]) -> Dict[str, float]:
        """Get prices for multiple tokens"""
        prices = {}
        for token_id in token_ids:
            price = self.get_price(token_id)
            if price is not None:
                prices[token_id] = price
        return prices

    def place_order(self, token_id: str, side: OrderSide, size: float,
                    price: Optional[float] = None,
                    order_type: OrderType = OrderType.MARKET) -> Optional[Order]:
        """
        Place an order

        Args:
            token_id: Token to trade
            side: BUY or SELL
            size: Amount in dollars
            price: Limit price (optional for market orders)
            order_type: MARKET or LIMIT

        Returns:
            Order object or None if failed
        """
        if self.simulation_mode:
            return self._simulate_order(token_id, side, size, price, order_type)

        # Real order placement
        order_data = {
            'token_id': token_id,
            'side': side.value,
            'size': str(size),
            'type': order_type.value,
        }
        if price is not None:
            order_data['price'] = str(price)

        try:
            result = self._request("POST", "/order", data=order_data, authenticated=True)
            return Order(
                id=result.get('order_id'),
                token_id=token_id,
                side=side,
                order_type=order_type,
                price=price or float(result.get('filled_price', 0)),
                size=size,
                filled_size=float(result.get('filled_size', 0)),
                status=result.get('status', 'pending'),
                created_at=time.time()
            )
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None

    def _simulate_order(self, token_id: str, side: OrderSide, size: float,
                        price: Optional[float], order_type: OrderType) -> Order:
        """Simulate order placement for testing"""
        self._order_counter += 1
        order_id = f"SIM_{self._order_counter}_{int(time.time())}"

        # Simulate market price if not provided
        if price is None:
            price = 0.50  # Default mid price

        # Apply slippage for simulation
        slippage = 0.005  # 0.5%
        if side == OrderSide.BUY:
            fill_price = price * (1 + slippage)
        else:
            fill_price = price * (1 - slippage)

        order = Order(
            id=order_id,
            token_id=token_id,
            side=side,
            order_type=order_type,
            price=fill_price,
            size=size,
            filled_size=size,  # Assume full fill in simulation
            status="filled",
            created_at=time.time(),
            filled_at=time.time()
        )

        self._simulated_orders[order_id] = order
        logger.info(f"[SIMULATION] Order {order_id}: {side.value} {size} @ {fill_price:.4f}")
        return order

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order status by ID"""
        if self.simulation_mode and order_id in self._simulated_orders:
            return self._simulated_orders[order_id]

        try:
            result = self._request("GET", f"/order/{order_id}", authenticated=True)
            return Order(
                id=order_id,
                token_id=result.get('token_id', ''),
                side=OrderSide(result.get('side', 'BUY')),
                price=float(result.get('price', 0)),
                size=float(result.get('size', 0)),
                filled_size=float(result.get('filled_size', 0)),
                status=result.get('status', 'unknown'),
                created_at=float(result.get('created_at', 0))
            )
        except Exception as e:
            logger.error(f"Error getting order {order_id}: {e}")
            return None

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order"""
        if self.simulation_mode:
            if order_id in self._simulated_orders:
                self._simulated_orders[order_id].status = "cancelled"
                return True
            return False

        try:
            self._request("DELETE", f"/order/{order_id}", authenticated=True)
            return True
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False

    def get_open_orders(self) -> List[Order]:
        """Get all open orders"""
        if self.simulation_mode:
            return [o for o in self._simulated_orders.values() if o.status == "pending"]

        try:
            result = self._request("GET", "/orders", authenticated=True)
            return [
                Order(
                    id=o.get('order_id'),
                    token_id=o.get('token_id'),
                    side=OrderSide(o.get('side', 'BUY')),
                    price=float(o.get('price', 0)),
                    size=float(o.get('size', 0)),
                    filled_size=float(o.get('filled_size', 0)),
                    status=o.get('status', 'pending')
                )
                for o in result.get('orders', [])
            ]
        except Exception as e:
            logger.error(f"Error getting open orders: {e}")
            return []


# Convenience functions
def buy_market(api: CLOBAPI, token_id: str, amount: float) -> Optional[Order]:
    """Place market buy order"""
    return api.place_order(token_id, OrderSide.BUY, amount, order_type=OrderType.MARKET)


def sell_market(api: CLOBAPI, token_id: str, amount: float) -> Optional[Order]:
    """Place market sell order"""
    return api.place_order(token_id, OrderSide.SELL, amount, order_type=OrderType.MARKET)


def buy_limit(api: CLOBAPI, token_id: str, amount: float, price: float) -> Optional[Order]:
    """Place limit buy order"""
    return api.place_order(token_id, OrderSide.BUY, amount, price=price, order_type=OrderType.LIMIT)


def sell_limit(api: CLOBAPI, token_id: str, amount: float, price: float) -> Optional[Order]:
    """Place limit sell order"""
    return api.place_order(token_id, OrderSide.SELL, amount, price=price, order_type=OrderType.LIMIT)
