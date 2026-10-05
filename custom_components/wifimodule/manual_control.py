"""Persistent manual ownership, independent of sensor demand."""

from .api import ApiError, ControlCancelled

ACK_SECONDS = 180


class ManualControl:
    def __init__(self, automatic, stored):
        self.auto = automatic
        # Legacy "Manual" meant only paused. With no saved speed, start off.
        saved = stored.get("manual", {})
        legacy = "manual" not in stored and stored.get("reason", "manual") == "manual"
        self.active = not automatic.enabled and (saved.get("active") is True or legacy)
        speed = saved.get("speed", 0)
        self.speed = speed if type(speed) is int and 0 <= speed <= 7 else None
        self.pending = self.active
        self.sent_at = None
        self.awaiting = False
        if self.active:
            automatic.status = "manual_pending"

    def snapshot(self):
        return {"active": self.active, "speed": self.speed}

    def clear(self):
        self.active = self.pending = self.awaiting = False
        self.sent_at = None

    def select(self):
        self.active = self.pending = True
        self.awaiting = False
        self.speed = (
            self.auto._physical_speed()
            if self.auto.coordinator.last_update_success and self.auto.control.ready
            else None
        )
        self.auto.status = "manual_pending"

    def record(self, payload, now):
        self.clear()
        if payload.get("manual") is False:
            self.auto.status = "schedule"
        elif (
            payload.get("mode") == "manual"
            and payload.get("switch") == "never"
            and type(payload.get("speed")) is int
            and 0 <= payload["speed"] <= 7
        ):
            self.active = self.awaiting = True
            self.speed = payload["speed"]
            self.sent_at = now
            self.auto.status = "manual_awaiting"
        else:
            self.auto.status = "device_control"
        self.auto._persist()
        self.auto._notify()

    async def tick(self, now):
        a = self.auto
        if not self.active:
            return
        fresh = a.coordinator.last_update_success and a.control.ready
        current = a._physical_speed() if fresh else None
        if current is None and self.awaiting and now - self.sent_at >= ACK_SECONDS:
            await a.manual("device_timeout")
            return
        if current is None:
            a.status = "manual_pending" if self.pending else "device_unavailable"
            return
        if self.pending:
            if self.speed is None:
                self.speed = current
            generation = a.generation

            def guard():
                return (
                    self.active
                    and not a.enabled
                    and not a._closed
                    and generation == a.generation
                )

            self.pending = False
            self.awaiting = True
            self.sent_at = now
            a.status = "manual_awaiting"
            a._persist()
            try:
                await a.control.control(
                    speed=self.speed, mode="manual", duration=0, _guard=guard
                )
            except ControlCancelled:
                if self.active and not a.enabled and not a._closed:
                    self.pending = True
                    self.awaiting = False
                return
            except ApiError:
                if self.active and not a.enabled and not a._closed:
                    await a.manual("command_error")
                return
            if guard():
                await a.coordinator.async_request_refresh()
            return
        data = a.control.data
        matches = (
            current == self.speed
            and data.get("manual_active") is True
            and data.get("manual_mode") == "manual"
            and data.get("manual_speed") == self.speed
        )
        if matches:
            self.awaiting = False
            a.status = "manual"
        elif self.awaiting and now - self.sent_at >= ACK_SECONDS:
            await a.manual("device_timeout")
        elif self.awaiting:
            a.status = "manual_awaiting"
        else:
            # An intentional change from the remote/vendor UI takes precedence.
            await a.manual("external_control")
