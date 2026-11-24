"""Snapshot-grounded AI explanations and a checked, opt-in simulated bot."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import math
import struct
import uuid

from pydantic import ValidationError

from .ai_provider import ModelDecision, ProviderError
from .strategy import PaperAccount, decimal, indicators
from .yahoo import now_ms


def encode(value):
    return json.dumps(value, allow_nan=False, separators=(",", ":"))


def check(name, passed, detail):
    return dict(name=name, passed=bool(passed), detail=detail)


def image_metadata(image):
    if not image.startswith("data:image/png;base64,") or len(image) > 2_800_000:
        raise ValueError("Send a PNG chart image smaller than 2 MB")
    try:
        content = base64.b64decode(image.split(",", 1)[1], validate=True)
        if content[:8] != b"\x89PNG\r\n\x1a\n" or content[12:16] != b"IHDR":
            raise ValueError()
        width, height = struct.unpack(">II", content[16:24])
        if (
            not 32 <= width <= 4096
            or not 32 <= height <= 2160
            or len(content) > 2_000_000
        ):
            raise ValueError()
    except (ValueError, struct.error):
        raise ValueError("Invalid PNG chart image or unsupported dimensions") from None
    return dict(
        sha256=hashlib.sha256(content).hexdigest(),
        width=width,
        height=height,
        bytes=len(content),
    )


class AIAssistant:
    def __init__(self, store, provider, feed_status, clock=now_ms):
        self.store, self.provider, self.feed_status, self.clock = (
            store,
            provider,
            feed_status,
            clock,
        )
        self.decision_lock = asyncio.Lock()
        self.interaction_slots = asyncio.Semaphore(2)
        # Restarts never silently resume provider automation or an unfilled order.
        with store.lock:
            for row in store.db.execute("SELECT * FROM ai_bots").fetchall():
                account = self._account(row)
                self._cancel(account, "cancelled: application restarted")
                store.db.execute(
                    "UPDATE ai_bots SET running=0,generation=generation+1,state_json=? WHERE id=?",
                    (encode(account.state), row["id"]),
                )

    def _row(self, bot_id):
        row = self.store.db.execute(
            "SELECT * FROM ai_bots WHERE id=?", (bot_id,)
        ).fetchone()
        if row is None:
            raise KeyError(bot_id)
        return row

    @staticmethod
    def _account(row):
        return PaperAccount(
            json.loads(row["config_json"]), json.loads(row["state_json"])
        )

    @staticmethod
    def _cancel(account, reason):
        pending = account.state["pending"]
        if pending is not None:
            account.state["orders"][pending]["status"] = reason
            account.state["pending"] = None

    def _save(self, bot_id, account):
        self.store.db.execute(
            "UPDATE ai_bots SET state_json=? WHERE id=?",
            (encode(account.state), bot_id),
        )

    def ensure_bot(self, symbol, fast=9, slow=21):
        with self.store.lock:
            row = self.store.db.execute(
                "SELECT id FROM ai_bots WHERE symbol=?", (symbol,)
            ).fetchone()
            if row:
                return self.get_bot(row["id"])
            config = dict(
                symbol=symbol,
                mode="paper",
                fast=fast,
                slow=slow,
                initialCash=10000,
                feeBps=10,
                slippageBps=5,
            )
            account = PaperAccount(config)
            account.state.update(
                lastReceiptId=self.store.stats()["lastReceiptId"],
                lastOrderCandle=-1,
                lastAutoCandle=-1,
                autoCalls=0,
                autoUntil=0,
            )
            quote = self.store.quote(symbol)
            if quote:
                account.state["lastMark"] = str(quote["price"])
            bot_id = uuid.uuid4().hex
            self.store.db.execute(
                "INSERT INTO ai_bots(id,symbol,created_at,config_json,state_json) VALUES (?,?,?,?,?)",
                (bot_id, symbol, self.clock(), encode(config), encode(account.state)),
            )
            return self.get_bot(bot_id)

    def sync(self):
        with self.store.lock:
            until = self.store.stats()["lastReceiptId"]
            rows = self.store.db.execute("SELECT * FROM ai_bots").fetchall()
            if not rows:
                return
            self.store.db.execute("BEGIN IMMEDIATE")
            try:
                for row in rows:
                    account = self._account(row)
                    cursor = account.state["lastReceiptId"]
                    while cursor < until:
                        page = self.store.replay(
                            row["symbol"], after=cursor, until=until, limit=2000
                        )
                        if not page:
                            break
                        for receipt in page:
                            bar = receipt["observation"]
                            if receipt["applied"] and bar["kind"] == "quote":
                                pending = account.state["pending"]
                                order = (
                                    account.state["orders"][pending]
                                    if pending is not None
                                    else None
                                )
                                feed = self.feed_status()
                                can_fill = (
                                    not feed.get("paused")
                                    and feed.get("stream", {}).get("state")
                                    == "streaming"
                                    and 0 <= self.clock() - bar["sourceTime"] <= 60_000
                                    and (
                                        order is None
                                        or receipt["receivedAt"]
                                        >= order["decisionTime"]
                                    )
                                )
                                account.quote(receipt, not can_fill)
                            cursor = receipt["receiptId"]
                    account.state["lastReceiptId"] = until
                    self._save(row["id"], account)
                self.store.db.execute("COMMIT")
            except BaseException:
                self.store.db.execute("ROLLBACK")
                raise

    def get_bot(self, bot_id):
        with self.store.lock:
            row = self._row(bot_id)
            account = self._account(row)
            return dict(
                id=row["id"],
                symbol=row["symbol"],
                running=bool(row["running"]),
                config=account.config,
                account=account.summary(),
                orders=account.state["orders"][-30:],
                fills=account.state["fills"][-30:],
                autoCalls=account.state["autoCalls"],
                autoUntil=account.state["autoUntil"],
                generation=row["generation"],
            )

    def bot_for(self, symbol):
        with self.store.lock:
            row = self.store.db.execute(
                "SELECT id FROM ai_bots WHERE symbol=?", (symbol,)
            ).fetchone()
            return self.get_bot(row["id"]) if row else None

    def set_running(self, bot_id, running):
        with self.store.lock:
            row = self._row(bot_id)
            account = self._account(row)
            if running and bool(row["running"]):
                return self.get_bot(bot_id)
            if running and not self.provider.configured:
                raise ValueError(
                    "Configure the private Gemini API key before starting automation"
                )
            self._cancel(account, "cancelled: automation controls changed")
            if running:
                account.state.update(
                    autoCalls=0, autoUntil=self.clock() + 600_000, lastAutoCandle=-1
                )
            self.store.db.execute(
                "UPDATE ai_bots SET running=?,generation=generation+1,state_json=? WHERE id=?",
                (int(running), encode(account.state), bot_id),
            )
            return self.get_bot(bot_id)

    def context(self, symbol, bot_id=None):
        with self.store.lock:
            bot = self.get_bot(bot_id) if bot_id else self.bot_for(symbol)
            if bot and bot["symbol"] != symbol:
                raise ValueError("Account symbol does not match the request")
            fast, slow = (
                (bot["config"]["fast"], bot["config"]["slow"]) if bot else (9, 21)
            )
            bars = self.store.candles(symbol, max(80, slow + 4))
            points = indicators(bars, fast, slow)
            latest = points[-1] if points else None
            cross = next((p for p in reversed(points) if p["signal"]), None)
            completed = [bar for bar in bars if bar["complete"]]
            quote = self.store.quote(symbol)
            at = self.clock()
            feed = self.feed_status()
            qty = decimal(bot["account"]["quantity"]) if bot else 0
            candidate = "hold"
            if (
                latest
                and latest["slow"] is not None
                and not math.isclose(latest["fast"], latest["slow"], rel_tol=1e-12)
            ):
                if latest["fast"] > latest["slow"] and qty == 0:
                    candidate = "buy"
                elif latest["fast"] < latest["slow"] and qty > 0:
                    candidate = "sell"
            quote_age = at - quote["sourceTime"] if quote else None
            candle_age = (
                at - completed[-1]["sourceTime"] - 60_000 if completed else None
            )
            meta = feed.get("symbols", {}).get(symbol, {})
            seen_in_session = (
                quote is not None
                and meta.get("lastQuoteSourceTime") == quote["sourceTime"]
                and meta.get("lastQuoteReceivedAt") is not None
                and 0 <= at - meta["lastQuoteReceivedAt"] <= 60_000
            )
            healthy = (
                not feed.get("paused")
                and feed.get("stream", {}).get("state") == "streaming"
                and feed.get("symbols", {}).get(symbol, {}).get("chartState")
                == "available"
                and seen_in_session
            )
            previous = self.store.db.execute(
                "SELECT created_at,status,response_json FROM ai_activity WHERE symbol=? AND kind='decision' ORDER BY id DESC LIMIT 1",
                (symbol,),
            ).fetchone()
            prior_reply = json.loads(previous["response_json"]) if previous else {}
            return dict(
                snapshotId=uuid.uuid4().hex,
                capturedAt=at,
                symbol=symbol,
                receiptWatermark=self.store.stats()["lastReceiptId"],
                market=dict(
                    source="Yahoo Finance",
                    quote=quote,
                    quoteAgeMs=quote_age,
                    completedCandleAgeMs=candle_age,
                    feedAvailable=healthy,
                    dataMode="live"
                    if healthy
                    and quote_age is not None
                    and 0 <= quote_age <= 60_000
                    and candle_age is not None
                    and 0 <= candle_age <= 180_000
                    else "stale/recorded/unavailable",
                    completedCandles=completed[-32:],
                ),
                indicators=dict(
                    fastLength=fast,
                    slowLength=slow,
                    latest=latest,
                    latestCrossover=cross,
                    candidate=candidate,
                    rule="Buy while fast SMA is above slow and flat; sell while below and long. Crossovers explain regime changes. AI may confirm the candidate or veto with hold. Forming candles are excluded.",
                ),
                account=bot["account"] if bot else None,
                recentOrders=bot["orders"][-6:] if bot else [],
                recentFills=bot["fills"][-6:] if bot else [],
                latestCheckedDecision=dict(
                    createdAt=previous["created_at"],
                    status=previous["status"],
                    decision=prior_reply.get("decision"),
                    reason=prior_reply.get("reason"),
                    checks=prior_reply.get("checks"),
                )
                if previous
                else None,
                assumptions=dict(
                    simulated=True,
                    sizing="95% of cash on buy; entire position on sell",
                    feeBps=10,
                    slippageBps=5,
                    execution="Next fresh Yahoo quote received after the checked model decision",
                    confidenceThreshold=0.6,
                ),
            )

    def preflight(self, context, account):
        market, point = context["market"], context["indicators"]["latest"]
        return [
            check(
                "Completed SMAs",
                point is not None and point["slow"] is not None,
                "Only completed Yahoo candles are eligible",
            ),
            check(
                "Feed available",
                market["feedAvailable"],
                "Streaming quotes and available symbol candles are required",
            ),
            check(
                "Quote fresh",
                market["quoteAgeMs"] is not None
                and 0 <= market["quoteAgeMs"] <= 60_000,
                "Source quote age must be 0–60 seconds",
            ),
            check(
                "Candle fresh",
                market["completedCandleAgeMs"] is not None
                and 0 <= market["completedCandleAgeMs"] <= 180_000,
                "Completed candle end must be within three minutes",
            ),
            check(
                "No pending order",
                account.state["pending"] is None,
                "Only one pending simulated order per AI account",
            ),
        ]

    def record(
        self, symbol, kind, status, context, response, *, bot_id=None, request_key=None
    ):
        with self.store.lock:
            cursor = self.store.db.execute(
                "INSERT INTO ai_activity(request_key,bot_id,symbol,kind,created_at,status,context_json,response_json) VALUES (?,?,?,?,?,?,?,?)",
                (
                    request_key,
                    bot_id,
                    symbol,
                    kind,
                    self.clock(),
                    status,
                    encode(context),
                    encode(response),
                ),
            )
            return self.activity(cursor.lastrowid)

    def activity(self, activity_id):
        with self.store.lock:
            row = self.store.db.execute(
                "SELECT * FROM ai_activity WHERE id=?", (activity_id,)
            ).fetchone()
            if row is None:
                raise KeyError(activity_id)
            return dict(
                id=row["id"],
                botId=row["bot_id"],
                symbol=row["symbol"],
                kind=row["kind"],
                createdAt=row["created_at"],
                status=row["status"],
                context=json.loads(row["context_json"]),
                response=json.loads(row["response_json"]),
            )

    def activities(self, symbol):
        with self.store.lock:
            return [
                self.activity(r["id"])
                for r in self.store.db.execute(
                    "SELECT id FROM ai_activity WHERE symbol=? ORDER BY id DESC LIMIT 20",
                    (symbol,),
                )
            ]

    async def decide(self, bot_id, request_key, execute=True):
        if self.decision_lock.locked():
            raise ValueError(
                "A decision is already being checked. Wait for it to finish."
            )
        async with self.decision_lock:
            self.sync()
            with self.store.lock:
                existing = self.store.db.execute(
                    "SELECT id,bot_id FROM ai_activity WHERE request_key=?",
                    (request_key,),
                ).fetchone()
                if existing:
                    if existing["bot_id"] != bot_id:
                        raise ValueError("Request ID belongs to a different account")
                    return self.activity(existing["id"])
                row = self._row(bot_id)
                generation = row["generation"]
                account = self._account(row)
                context = self.context(row["symbol"], bot_id)
                checks = self.preflight(context, account)
                if execute and not all(c["passed"] for c in checks):
                    return self.record(
                        row["symbol"],
                        "decision",
                        "skipped",
                        context,
                        dict(
                            reason="Market/account checks failed; model was not called",
                            checks=checks,
                            providerCalled=False,
                        ),
                        bot_id=bot_id,
                        request_key=request_key,
                    )
            try:
                reply = await self.provider.respond(
                    context,
                    "Evaluate the SMA candidate for this simulated account. Return a checked-candidate recommendation and a short explanation.",
                    decision=True,
                )
                try:
                    decision = ModelDecision.model_validate_json(reply["text"])
                except (ValidationError, ValueError):
                    return self.record(
                        row["symbol"],
                        "decision",
                        "rejected",
                        context,
                        dict(
                            **reply,
                            reason="Invalid decision schema; no action applied",
                            checks=[
                                check(
                                    "Decision schema",
                                    False,
                                    "Action, identity, finite confidence and bounded reason are required",
                                )
                            ],
                        ),
                        bot_id=bot_id,
                        request_key=request_key,
                    )
            except ProviderError as exc:
                return self.record(
                    row["symbol"],
                    "decision",
                    "unavailable",
                    context,
                    dict(reason=str(exc), checks=checks, providerCalled=True),
                    bot_id=bot_id,
                    request_key=request_key,
                )
            self.sync()
            with self.store.lock:
                current_row = self._row(bot_id)
                account = self._account(current_row)
                current = self.context(row["symbol"], bot_id)
                original_bar = context["indicators"]["latest"]
                current_bar = current["indicators"]["latest"]
                checks = [
                    check(
                        "Decision identity",
                        decision.symbol == context["symbol"]
                        and decision.snapshotId == context["snapshotId"],
                        "The response must echo this symbol and snapshot ID",
                    ),
                    check(
                        "SMA agreement",
                        decision.action == "hold"
                        or decision.action == context["indicators"]["candidate"],
                        "The model may confirm the SMA candidate or hold",
                    ),
                    check(
                        "Confidence",
                        decision.action == "hold" or decision.confidence >= 0.6,
                        "An action needs confidence >= 0.60; this is not a calibrated probability",
                    ),
                    check(
                        "Controls unchanged",
                        current_row["generation"] == generation,
                        "Pause, start and restart invalidate in-flight decisions",
                    ),
                    check(
                        "Snapshot still eligible",
                        original_bar is not None
                        and current_bar is not None
                        and original_bar["observationId"]
                        == current_bar["observationId"]
                        and context["indicators"]["candidate"]
                        == current["indicators"]["candidate"]
                        and 0 <= self.clock() - context["capturedAt"] <= 45_000,
                        "A new/revised completed candle, changed account candidate or old response invalidates the decision",
                    ),
                ]
                if execute:
                    checks += self.preflight(current, account)
                    checks.append(
                        check(
                            "Candle not already traded",
                            decision.action == "hold"
                            or original_bar is not None
                            and account.state["lastOrderCandle"]
                            != original_bar["time"],
                            "At most one order per source candle, including later revisions",
                        )
                    )
                valid = all(c["passed"] for c in checks)
                status = (
                    "review"
                    if not execute and valid
                    else "rejected"
                    if not valid
                    else "hold"
                    if decision.action == "hold"
                    else "queued"
                )
                result = dict(
                    **reply,
                    decision=decision.model_dump(),
                    checks=checks,
                    reason="Review only: no order will be created"
                    if not execute
                    else decision.reason,
                    decisionWatermark=current["receiptWatermark"],
                )
                self.store.db.execute("BEGIN IMMEDIATE")
                try:
                    activity = self.record(
                        row["symbol"],
                        "decision",
                        status,
                        context,
                        result,
                        bot_id=bot_id,
                        request_key=request_key,
                    )
                    if status == "queued":
                        order = dict(
                            id=len(account.state["orders"]) + 1,
                            side=decision.action,
                            signalTime=original_bar["time"],
                            decisionTime=self.clock(),
                            signalReceiptId=current["receiptWatermark"],
                            signalObservationId=original_bar["observationId"],
                            activityId=activity["id"],
                            status="pending next quote",
                        )
                        account.state["orders"].append(order)
                        account.state["pending"] = len(account.state["orders"]) - 1
                        account.state["lastOrderCandle"] = original_bar["time"]
                        account.state["lastReceiptId"] = current["receiptWatermark"]
                        self._save(bot_id, account)
                    self.store.db.execute("COMMIT")
                except BaseException:
                    self.store.db.execute("ROLLBACK")
                    raise
                return activity

    async def tick(self):
        self.sync()
        with self.store.lock:
            rows = self.store.db.execute(
                "SELECT * FROM ai_bots WHERE running=1"
            ).fetchall()
        for row in rows:
            with self.store.lock:
                account = self._account(self._row(row["id"]))
                if (
                    self.clock() >= account.state["autoUntil"]
                    or account.state["autoCalls"] >= 10
                ):
                    self.set_running(row["id"], False)
                    continue
                context = self.context(row["symbol"], row["id"])
                point = context["indicators"]["latest"]
                if not point or point["time"] == account.state["lastAutoCandle"]:
                    continue
                account.state["lastAutoCandle"] = point["time"]
                account.state["autoCalls"] += 1
                self._save(row["id"], account)
            if not self.decision_lock.locked():
                result = await self.decide(row["id"], "auto-" + uuid.uuid4().hex)
                if result["status"] == "unavailable":
                    self.set_running(row["id"], False)

    async def interact(self, symbol, message, *, image=None, history=()):
        context = self.context(symbol)
        kind = "vision" if image else "chat"
        if image:
            context["chartImage"] = image_metadata(image)
            message = (
                "Interpret the attached actual chart image. Describe visible candles, SMA lines and crossover arrows. Distinguish visual estimates from exact supplied values and mention limits. "
                + message
            )
        try:
            async with self.interaction_slots:
                reply = await self.provider.respond(
                    context, message, image=image, history=history
                )
            return self.record(
                symbol, kind, "completed", context, dict(**reply, question=message)
            )
        except ProviderError as exc:
            return self.record(
                symbol,
                kind,
                "unavailable",
                context,
                dict(reason=str(exc), question=message),
            )
