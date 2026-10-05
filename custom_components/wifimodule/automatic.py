"""HA demand-control lifecycle, persistent options and guarded cloud writes."""

from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from time import monotonic

from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .api import ApiError, ControlCancelled
from .demand import KINDS, UNITS, DemandEngine, Reading, Settings
from .manual_control import ManualControl

LEASE_MINUTES = 15
RENEW_SECONDS = 300
ACK_SECONDS = 180


def validate_sensors(hass, sensors):
    if not isinstance(sensors, dict) or set(sensors) - set(KINDS):
        raise ValueError("Invalid sensor configuration")
    result, seen = {}, set()
    for kind in KINDS:
        entities = sensors.get(kind, [])
        if not isinstance(entities, list) or len(entities) > 32:
            raise ValueError("Invalid sensor list")
        for entity in entities:
            if (
                not isinstance(entity, str)
                or not entity.startswith("sensor.")
                or entity in seen
            ):
                raise ValueError("Duplicate or invalid sensor")
            state = hass.states.get(entity)
            if (
                state is None
                or state.attributes.get("unit_of_measurement") not in UNITS[kind]
            ):
                raise ValueError("Sensor missing or incompatible unit")
            seen.add(entity)
        result[kind] = list(entities)
    return result


class AutomaticControl:
    def __init__(self, hass, coordinator):
        self.hass, self.coordinator = hass, coordinator
        self.entry, self.control = coordinator.config_entry, coordinator.controller
        stored = self.entry.options.get("automatic", {})
        self.settings = Settings.from_dict(stored.get("settings", {}))
        self.sensors = {k: list(stored.get("sensors", {}).get(k, [])) for k in KINDS}
        self.enabled = stored.get("enabled") is True
        self.status = "warming_up" if self.enabled else stored.get("reason", "manual")
        self.engine = DemandEngine(self.settings)
        self.signal = f"wifimodule_automatic_{self.entry.entry_id}"
        self.decision = None
        self.generation = 0
        self.last_speed = None
        self.last_sent = None
        self.last_sent_at = None
        self.awaiting = False
        self.claim_since = None
        self._running = False
        self._closed = False
        self._cancel = None
        self.manual_control = ManualControl(self, stored)

    def start(self):
        async def interval(_now):
            await self.tick()

        self._cancel = async_track_time_interval(
            self.hass, interval, timedelta(seconds=10)
        )

    async def stop(self):
        self._closed = True
        self.generation += 1
        if self._cancel:
            self._cancel()
            self._cancel = None
        # Drain any write already submitted before unloading the integration.
        async with self.control.lock:
            pass

    def _notify(self):
        async_dispatcher_send(self.hass, self.signal)

    def _persist(self):
        self.hass.config_entries.async_update_entry(
            self.entry,
            options={
                **self.entry.options,
                "automatic": {
                    "enabled": self.enabled,
                    "sensors": self.sensors,
                    "settings": self.settings.as_dict(),
                    "reason": self.status if not self.enabled else "manual",
                    "manual": self.manual_control.snapshot(),
                },
            },
        )

    async def configure(self, *, enabled=None, sensors=None, settings=None):
        new_settings = Settings.from_dict(
            {**self.settings.as_dict(), **(settings or {})}
        )
        new_sensors = (
            validate_sensors(self.hass, sensors)
            if sensors is not None
            else self.sensors
        )
        if enabled is not None and type(enabled) is not bool:
            raise ValueError("Invalid automatic mode")
        new_enabled = self.enabled if enabled is None else enabled
        if new_enabled and not any(new_sensors.values()):
            raise ValueError("Select at least one sensor")
        if new_enabled and not self.enabled:
            self.last_speed = self.last_sent = self.last_sent_at = None
            self.awaiting = False
        self.generation += 1
        self.settings, self.sensors, self.enabled = (
            new_settings,
            new_sensors,
            new_enabled,
        )
        self.status = "warming_up" if self.enabled else "manual"
        self.engine = DemandEngine(self.settings)
        if self.last_sent is not None:
            self.engine.last_sent = self.last_sent
        self.decision = None
        self.claim_since = None
        # Retain acknowledgement tracking across parameter edits; do not forget an in-flight lease.
        if enabled is True:
            self.manual_control.clear()
        elif enabled is False:
            self.manual_control.select()
        elif self.manual_control.active:
            self.status = (
                "manual_pending"
                if self.manual_control.pending
                else "manual_awaiting"
                if self.manual_control.awaiting
                else "manual"
            )
        self._persist()
        self._notify()
        if not self.enabled:
            async with self.control.lock:
                pass

    async def manual(self, reason="paused"):
        self.manual_control.clear()
        self.enabled = False
        self.status = reason
        self.generation += 1
        self.engine.reset_pending()
        self.claim_since = None
        self._persist()
        self._notify()

    def readings(self):
        now = datetime.now(UTC)
        result = []
        for kind, entities in self.sensors.items():
            for entity in entities:
                state = self.hass.states.get(entity)
                attrs = state.attributes if state else {}
                age = (
                    (now - state.last_reported).total_seconds()
                    if state
                    else float("inf")
                )
                result.append(
                    Reading(
                        entity,
                        attrs.get("friendly_name", entity),
                        kind,
                        state.state if state and not attrs.get("restored") else None,
                        attrs.get("unit_of_measurement"),
                        age,
                    )
                )
        return result

    def _physical_speed(self):
        units = (self.control.data or {}).get("units", [])
        speeds = set()
        for u in units:
            v = u.get("values", {})
            if v.get("err") != 0 or v.get("bst") == 1 or v.get("pwr") not in (0, 1):
                return None
            speed = 0 if v["pwr"] == 0 else v.get("spe")
            if type(speed) is not int or not 0 <= speed <= 7:
                return None
            speeds.add(speed)
        return speeds.pop() if len(speeds) == 1 else None

    @property
    def snapshot(self):
        d = self.decision
        return {
            "enabled": self.enabled,
            "mode": self.mode,
            "reported_mode": "schedule"
            if (self.control.data or {}).get("manual_active") is False
            else (self.control.data or {}).get("manual_mode"),
            "manual_speed": self.manual_control.speed
            if self.manual_control.active
            else None,
            "status": self.status,
            "settings": self.settings.as_dict(),
            "sensors": self.sensors,
            "target_speed": d.target if d else None,
            "requested_speed": self.last_speed,
            "actual_speed": (
                self._physical_speed()
                if self.coordinator.last_update_success and self.control.ready
                else None
            ),
            "demand_percent": round(d.demand * 100, 1) if d else None,
            "source": asdict(d.source) if d and d.source else None,
            "invalid_sensors": list(d.invalid) if d else [],
            "wait_seconds": d.wait_seconds if d else None,
            "last_command": self.last_sent_at,
            "lease_minutes": LEASE_MINUTES,
        }

    @property
    def mode(self):
        if self.enabled:
            return "automatic"
        if self.manual_control.active:
            return "manual"
        if (self.control.data or {}).get("manual_active") is False:
            return "schedule"
        return "paused"

    async def tick(self, now=None):
        if self._running or self._closed:
            return
        self._running = True
        try:
            instant = monotonic() if now is None else now
            if self.enabled:
                await self._tick(instant)
            else:
                await self.manual_control.tick(instant)
        finally:
            self._running = False
            self._notify()

    async def _tick(self, now):
        current = self._physical_speed()
        if (
            not self.coordinator.last_update_success
            or not self.control.ready
            or current is None
        ):
            self.status = "device_unavailable"
            self.engine.reset_pending()
            self.claim_since = None
            return
        if self.awaiting:
            if current == self.last_speed:
                self.awaiting = False
            elif now - self.last_sent >= ACK_SECONDS:
                await self.manual("device_timeout")
                return
            else:
                self.status = "awaiting_device"
                return
        # Respect a cloud-side manual/schedule change after propagation grace.
        data = self.control.data
        if (
            self.last_sent is not None
            and now - self.last_sent > 120
            and (
                data.get("manual_active") is not True
                or data.get("manual_mode") != "manual"
                or data.get("manual_speed") != self.last_speed
            )
        ):
            await self.manual("external_control")
            return
        self.decision = d = self.engine.evaluate(self.readings(), current, now)
        self.status = d.status
        if d.target is None:
            self.claim_since = None
            return
        if self.claim_since is None:
            self.claim_since = now
        speed = d.command
        # Acquire/renew a finite lease only when all configured inputs are valid.
        renew = self.last_sent is None or now - self.last_sent >= RENEW_SECONDS
        if (
            speed is None
            and renew
            and not d.invalid
            and self.settings.min_speed <= current <= self.settings.max_speed
            and now - self.engine.last_sent >= self.settings.minimum_interval
            and now - self.claim_since >= self.settings.rise_seconds
        ):
            speed = current
        if speed is None:
            return
        generation = self.generation

        def active():
            return self.enabled and not self._closed and generation == self.generation

        def guard():
            if not active():
                return False
            actual = self._physical_speed()
            if actual is None or not self.control.ready:
                return False
            valid = {
                r.entity_id: r.numeric(self.settings.stale_seconds)
                for r in self.readings()
            }
            return (
                d.source is not None
                and valid.get(d.source.entity_id) is not None
                and (speed > actual or all(v is not None for v in valid.values()))
            )

        try:
            await self.control.control(
                speed=speed, mode="manual", duration=LEASE_MINUTES, _guard=guard
            )
        except ControlCancelled:
            return
        except ApiError:
            if self.enabled and not self._closed:
                await self.manual("command_error")
            return
        if not self.enabled or self._closed:
            return
        self.last_speed, self.last_sent = speed, now
        self.last_sent_at = datetime.now(UTC).isoformat()
        self.engine.sent(speed, now, changed=speed != current)
        self.awaiting = True
        self.status = "awaiting_device"
        await self.coordinator.async_request_refresh()
