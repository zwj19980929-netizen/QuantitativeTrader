from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from datetime import datetime
from src.database import MarketDB
import pandas as pd

class AbstractBroker(ABC):
    @abstractmethod
    def get_account_state(self) -> Dict:
        pass

    @abstractmethod
    def get_positions(self) -> List[Dict]:
        pass

    @abstractmethod
    def submit_order(self, ticker: str, action: str, quantity: float, price: Optional[float] = None, order_type: str = "MARKET") -> bool:
        """
        Submit an order.
        action: "BUY" or "SELL"
        order_type: "MARKET" or "LIMIT"
        """
        pass

    @abstractmethod
    def get_total_value(self) -> float:
        pass

class SimulatedBroker(AbstractBroker):
    def __init__(self, account_id: str, initial_cash: float = 1000000.0, db: MarketDB = None):
        self.account_id = account_id
        self.db = db if db else MarketDB()

        # Initialize account if not exists
        state = self.db.get_account_state(account_id)
        if not state:
            self.db.update_account_state(account_id, initial_cash, initial_cash, 0.0)
            print(f"[Broker] Initialized account {account_id} with {initial_cash}")

    def get_account_state(self) -> Dict:
        return self.db.get_account_state(self.account_id)

    def get_positions(self) -> List[Dict]:
        return self.db.get_positions(self.account_id)

    def get_market_price(self, ticker: str) -> float:
        # Get latest price from DB (market_data_daily or minute)
        # For simulation, we ideally pass the current time context,
        # but here we might just take the latest available in DB or assume backtest loop sets it?
        # A robust simulation needs the 'current' price at the time of execution.
        # We will assume MarketDB has a method to get latest price relative to 'now' or just latest.
        # Simplified: Get latest close.
        df = self.db.load_data(ticker, limit=1)
        if not df.empty:
            # MarketDB load_data returns Title Case columns (Close, Open, etc.)
            return float(df["Close"].iloc[0])
        return 0.0

    def submit_order(self, ticker: str, action: str, quantity: float, price: Optional[float] = None, order_type: str = "MARKET") -> bool:
        if quantity <= 0:
            print(f"[Broker] Invalid quantity {quantity}")
            return False

        # 1. Get State
        state = self.get_account_state()
        if not state: return False

        available_cash = float(state["available_cash"])
        positions = {p["ticker"]: p for p in self.get_positions()}

        # 2. Determine Execution Price
        exec_price = price
        if not exec_price:
            exec_price = self.get_market_price(ticker)
            if exec_price <= 0:
                print(f"[Broker] No market price for {ticker}")
                return False

        # 3. Validation & Execution
        # Fee rate from instruments (default 0.0003)
        # We should query instruments table, but for now hardcode or assume default
        fee_rate = 0.0003

        trade_amount = exec_price * quantity
        # Small capital optimization: Enforce Minimum Fee (CNY 5.0)
        fee = max(5.0, trade_amount * fee_rate)

        if action == "BUY":
            cost = trade_amount + fee
            if available_cash < cost:
                print(f"[Broker] Insufficient funds: {available_cash} < {cost}")
                return False

            # Update Cash
            new_cash = available_cash - cost
            # Total cash decreases by full cost (money leaves account to pay for stock)
            new_total_cash = float(state["total_cash"]) - cost
            self.db.update_account_state(self.account_id, new_total_cash, new_cash, state["frozen_cash"])

            # Update Position
            pos = positions.get(ticker)
            if pos:
                new_qty = float(pos["quantity"]) + quantity
                # Available qty does not increase immediately (T+1 rule)
                avail_qty = float(pos["available_quantity"])

                # Avg cost weighted average
                old_cost_total = float(pos["quantity"]) * float(pos["avg_cost"])
                new_cost_total = old_cost_total + cost
                new_avg = new_cost_total / new_qty
                self.db.update_position(self.account_id, ticker, new_qty, avail_qty, new_avg, exec_price)
            else:
                # Available qty = 0 initially (T+1)
                self.db.update_position(self.account_id, ticker, quantity, 0, (trade_amount + fee)/quantity, exec_price)

        elif action == "SELL":
            pos = positions.get(ticker)
            if not pos:
                print(f"[Broker] No position for {ticker}")
                return False

            avail_qty = float(pos["available_quantity"])
            if avail_qty < quantity:
                print(f"[Broker] Insufficient sellable position for {ticker} (Available: {avail_qty}, Requested: {quantity}). T+1 rule?")
                return False

            proceeds = trade_amount - fee

            # Update Cash
            new_cash = available_cash + proceeds
            new_total_cash = float(state["total_cash"]) + proceeds
            self.db.update_account_state(self.account_id, new_total_cash, new_cash, state["frozen_cash"])

            # Update Position
            new_qty = float(pos["quantity"]) - quantity
            new_avail = avail_qty - quantity

            if new_qty < 1e-6:
                self.db.update_position(self.account_id, ticker, 0, 0, 0, 0)
            else:
                self.db.update_position(self.account_id, ticker, new_qty, new_avail, float(pos["avg_cost"]), exec_price)

        print(f"[Broker] Executed {action} {quantity} {ticker} @ {exec_price:.2f}")
        return True

    def settle(self):
        """
        Settle trades (T+1). Make all quantity available.
        Call this at End of Day.
        """
        positions = self.get_positions()
        for p in positions:
            qty = float(p["quantity"])
            avail = float(p["available_quantity"])
            if avail < qty:
                # Update available to match total
                self.db.update_position(self.account_id, p["ticker"], qty, qty, float(p["avg_cost"]), float(p["current_price"]))
        # print("[Broker] Settled positions (T+1).")

    def get_total_value(self, current_prices: Optional[Dict[str, float]] = None) -> float:
        """
        Calculate total equity.
        :param current_prices: Optional dict {ticker: price} for backtesting point-in-time valuation.
        """
        state = self.get_account_state()
        if not state: return 0.0

        cash = float(state["total_cash"])

        positions = self.get_positions()
        market_value = 0.0
        for p in positions:
            ticker = p["ticker"]
            if current_prices and ticker in current_prices:
                price = current_prices[ticker]
            else:
                price = self.get_market_price(ticker)

            market_value += float(p["quantity"]) * price

        return cash + market_value
