"""Completed-bar SMAs and a receipt-driven, long-only paper account."""

from collections import deque
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
import math


def average(values):
    return math.fsum(values) / len(values)


def crossover(previous, current):
    if previous is None or current is None:
        return None
    if previous <= 0 < current:
        return "buy"
    if previous >= 0 > current:
        return "sell"
    return None


class MovingAverages:
    def __init__(self, fast=9, slow=21):
        if not 2 <= fast < slow <= 200:
            raise ValueError("Choose 2 <= fast < slow <= 200")
        self.fast, self.slow = fast, slow
        self.values = deque(maxlen=slow)
        self.previous = None

    def update(self, close):
        self.values.append(close)
        values = list(self.values)
        fast = average(values[-self.fast :]) if len(values) >= self.fast else None
        slow = average(values) if len(values) >= self.slow else None
        difference = fast - slow if slow is not None else None
        # Scale-aware equality avoids phantom crosses from floating-point noise.
        if difference is not None and math.isclose(fast, slow, rel_tol=1e-12):
            difference = 0
        signal = crossover(self.previous, difference)
        self.previous = difference
        return dict(fast=fast, slow=slow, signal=signal)


def indicators(candles, fast=9, slow=21):
    calculator = MovingAverages(fast, slow)
    points = []
    for bar in candles:
        if not bar.get("complete"):
            continue
        points.append(
            dict(
                time=bar["sourceTime"],
                observationId=bar["id"],
                **calculator.update(bar["close"]),
            )
        )
    return points


def decimal(value):
    return Decimal(str(value))


def dollars(value):
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class PaperAccount:
    """State is JSON-serializable so a receipt checkpoint survives restart."""

    def __init__(self, config, state=None):
        self.config = config
        self.indicator = MovingAverages(config["fast"], config["slow"])
        self.state = state or dict(
            cash=str(dollars(decimal(config["initialCash"]))),
            quantity="0",
            costBasis="0",
            realized="0",
            fees="0",
            lastMark=None,
            lastCandleTime=-1,
            lastQuoteTime=-1,
            closes=[],
            previous=None,
            orders=[],
            fills=[],
            signals=[],
            equity=[],
            completedBars=0,
            processedReceipts=0,
            lastReceiptId=0,
            pending=None,
            peak=str(config["initialCash"]),
            maxDrawdown=0,
            firstReceiptTime=None,
            lastReceiptTime=None,
        )
        self.indicator.values.extend(self.state["closes"])
        self.indicator.previous = self.state["previous"]

    def process(self, receipt, warmup=False):
        s = self.state
        if receipt["receiptId"] <= s["lastReceiptId"]:
            return
        s["lastReceiptId"] = receipt["receiptId"]
        s["processedReceipts"] += 1
        s["firstReceiptTime"] = s["firstReceiptTime"] or receipt["receivedAt"]
        s["lastReceiptTime"] = receipt["receivedAt"]
        if not receipt["applied"]:
            return
        bar = receipt["observation"]
        if bar["kind"] == "quote":
            self.quote(receipt, warmup)
        elif bar["complete"] and bar["sourceTime"] > s["lastCandleTime"]:
            # A completed bar is consumed once. Later corrections stay in the
            # market audit log and cannot rewrite historical account decisions.
            s["lastCandleTime"] = bar["sourceTime"]
            s["completedBars"] += 1
            point = self.indicator.update(bar["close"])
            s["closes"] = list(self.indicator.values)
            s["previous"] = self.indicator.previous
            timely = (
                0 <= receipt["receivedAt"] - (bar["sourceTime"] + 60_000) <= 120_000
            )
            if point["signal"] and not warmup and timely:
                signal = dict(
                    **point,
                    time=bar["sourceTime"],
                    observationId=bar["id"],
                    receiptId=receipt["receiptId"],
                    receivedAt=receipt["receivedAt"],
                )
                s["signals"].append(signal)
                if s["pending"] is not None:
                    s["orders"][s["pending"]][
                        "status"
                    ] = "cancelled by opposite crossover"
                    s["pending"] = None
                side = point["signal"]
                held = decimal(s["quantity"]) > 0
                order = dict(
                    id=len(s["orders"]) + 1,
                    side=side,
                    signalTime=bar["sourceTime"],
                    decisionTime=receipt["receivedAt"],
                    signalReceiptId=receipt["receiptId"],
                    signalObservationId=bar["id"],
                    status="pending next quote",
                )
                if (side == "buy" and held) or (side == "sell" and not held):
                    order["status"] = (
                        "skipped: already long" if held else "skipped: flat account"
                    )
                else:
                    s["pending"] = len(s["orders"])
                s["orders"].append(order)

    def quote(self, receipt, warmup):
        s, bar = self.state, receipt["observation"]
        if bar["sourceTime"] < s["lastQuoteTime"]:
            return
        s["lastQuoteTime"] = bar["sourceTime"]
        price = decimal(bar["price"])
        s["lastMark"] = str(price)
        if s["pending"] is not None and not warmup:
            order = s["orders"][s["pending"]]
            if receipt["receivedAt"] - order["decisionTime"] > 300_000:
                order["status"] = "expired: no eligible quote within five minutes"
                s["pending"] = None
            elif (
                bar["sourceTime"] >= order["signalTime"] + 60_000
                and 0 <= receipt["receivedAt"] - bar["sourceTime"] <= 60_000
            ):
                self.fill(order, receipt, price)
                s["pending"] = None
        summary = self.summary()
        equity = decimal(summary["equity"])
        peak = max(decimal(s["peak"]), equity)
        s["peak"] = str(peak)
        s["maxDrawdown"] = max(s["maxDrawdown"], float((peak - equity) / peak * 100))
        point = dict(
            time=bar["sourceTime"], receiptId=receipt["receiptId"], value=float(equity)
        )
        if s["equity"] and s["equity"][-1]["time"] // 60_000 == point["time"] // 60_000:
            s["equity"][-1] = point
        else:
            s["equity"].append(point)

    def fill(self, order, receipt, quote_price):
        s = self.state
        side = order["side"]
        fee_rate = decimal(self.config["feeBps"]) / 10_000
        slip = decimal(self.config["slippageBps"]) / 10_000
        price = quote_price * (1 + slip if side == "buy" else 1 - slip)
        cash, qty, cost = (
            decimal(s["cash"]),
            decimal(s["quantity"]),
            decimal(s["costBasis"]),
        )
        realized = Decimal(0)
        if side == "buy":
            budget = cash * Decimal("0.95")
            qty = (budget / (price * (1 + fee_rate))).quantize(
                Decimal("0.00000001"), rounding=ROUND_DOWN
            )
            if qty <= 0:
                order["status"] = "rejected: insufficient simulated cash"
                return
            notional = dollars(qty * price)
            fee = dollars(notional * fee_rate)
            cost = notional + fee
            cash -= cost
        else:
            notional = dollars(qty * price)
            fee = dollars(notional * fee_rate)
            proceeds = notional - fee
            cash += proceeds
            realized = proceeds - cost
        fill = dict(
            orderId=order["id"],
            side=side,
            quantity=str(qty),
            price=float(price),
            notional=float(notional),
            fee=float(fee),
            realizedPnl=float(realized),
            quoteObservationId=receipt["observation"]["id"],
            receiptId=receipt["receiptId"],
            sourceTime=receipt["observation"]["sourceTime"],
            receivedAt=receipt["receivedAt"],
        )
        s["fills"].append(fill)
        s["cash"] = str(cash)
        s["quantity"] = str(qty if side == "buy" else Decimal(0))
        s["costBasis"] = str(cost if side == "buy" else Decimal(0))
        s["realized"] = str(decimal(s["realized"]) + realized)
        s["fees"] = str(decimal(s["fees"]) + fee)
        order["status"] = "filled"

    def summary(self):
        s = self.state
        cash, qty = decimal(s["cash"]), decimal(s["quantity"])
        market = dollars(qty * decimal(s["lastMark"] or 0))
        equity = cash + market
        unrealized = market - decimal(s["costBasis"])
        return dict(
            cash=float(cash),
            quantity=str(qty),
            costBasis=float(decimal(s["costBasis"])),
            realizedPnl=float(decimal(s["realized"])),
            unrealizedPnl=float(unrealized),
            equity=float(equity),
            fees=float(decimal(s["fees"])),
            returnPercent=float(
                (equity / decimal(self.config["initialCash"]) - 1) * 100
            ),
            maxDrawdownPercent=s["maxDrawdown"],
            completedBars=s["completedBars"],
            signals=len(s["signals"]),
            fills=len(s["fills"]),
            markPrice=s["lastMark"],
        )
