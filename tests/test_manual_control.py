"""Manual ownership, restart and explicit release regressions."""

from test_automatic import make_auto

from custom_components.wifimodule.api import DeviceError
from custom_components.wifimodule.automatic import AutomaticControl


async def test_manual_selection_takes_current_speed_without_expiry():
    a, c, _ = make_auto()
    await a.configure(enabled=False)
    await a.tick(10)
    kwargs = c.controller.control.call_args.kwargs
    assert (kwargs["speed"], kwargs["mode"], kwargs["duration"]) == (2, "manual", 0)
    assert a.snapshot["mode"] == "manual"
    assert c.config_entry.options["automatic"]["manual"]["speed"] == 2


async def test_restart_restores_saved_off_only_after_fresh_communication():
    a, c, _ = make_auto(False)
    c.config_entry.options["automatic"]["manual"] = {"active": True, "speed": 0}
    a = AutomaticControl(a.hass, c)
    c.controller.ready = False
    await a.tick(0)
    c.controller.control.assert_not_awaited()
    c.controller.ready = True
    await a.tick(10)
    assert c.controller.control.call_args.kwargs["speed"] == 0
    assert c.controller.control.call_args.kwargs["duration"] == 0
    await a.tick(20)
    assert c.controller.control.await_count == 1


async def test_manual_failure_is_not_retried_or_restored_after_restart():
    a, c, _ = make_auto()
    c.controller.control.side_effect = DeviceError("unknown outcome")
    await a.configure(enabled=False)
    await a.tick(10)
    await a.tick(500)
    restored = AutomaticControl(a.hass, c)
    await restored.tick(1000)
    assert c.controller.control.await_count == 1
    assert restored.status == "command_error"


async def test_automatic_selection_cancels_pending_manual_restore():
    a, c, _ = make_auto()
    c.controller.ready = False
    await a.configure(enabled=False)
    await a.configure(enabled=True)
    c.controller.ready = True
    await a.tick(10)
    c.controller.control.assert_not_awaited()
    assert not a.manual_control.active


async def test_manual_waits_for_confirmation_then_respects_external_change():
    a, c, _ = make_auto()
    await a.configure(enabled=False)
    await a.tick(10)
    assert a.status == "manual_awaiting"
    c.controller.data.update(manual_active=True, manual_mode="manual", manual_speed=2)
    await a.tick(20)
    assert a.status == "manual"
    c.controller.data.update(manual_active=False)
    await a.tick(30)
    assert a.status == "external_control"
    assert not a.manual_control.active
    assert c.controller.control.await_count == 1


async def test_manual_ack_timeout_does_not_claim_a_successful_hold():
    a, c, _ = make_auto()
    await a.configure(enabled=False)
    await a.tick(10)
    await a.tick(191)
    assert a.status == "device_timeout"
    assert not a.manual_control.active


async def test_legacy_paused_manual_defaults_to_off_on_first_restart():
    a, c, _ = make_auto(False)
    c.config_entry.options["automatic"].pop("manual", None)
    restored = AutomaticControl(a.hass, c)
    await restored.tick(10)
    assert c.controller.control.call_args.kwargs["speed"] == 0


async def test_setting_edit_cancels_only_unsent_manual_attempt_and_requeues_it():
    from custom_components.wifimodule.api import ControlCancelled

    a, c, _ = make_auto()
    await a.configure(enabled=False)

    async def interrupted(**kwargs):
        await a.configure(settings={"co2_target": 850})
        assert not kwargs["_guard"]()
        raise ControlCancelled("cancelled before write")

    c.controller.control.side_effect = interrupted
    await a.tick(10)
    assert a.manual_control.pending and not a.manual_control.awaiting
    c.controller.control.side_effect = None
    await a.tick(20)
    assert c.controller.control.await_count == 2
    assert c.controller.control.call_args.kwargs["_guard"]()


async def test_switch_to_auto_while_manual_restore_waits_prevents_manual_write():
    from custom_components.wifimodule.api import ControlCancelled

    a, c, _ = make_auto()
    await a.configure(enabled=False)

    async def interrupted(**kwargs):
        await a.configure(enabled=True)
        assert not kwargs["_guard"]()
        raise ControlCancelled("cancelled before write")

    c.controller.control.side_effect = interrupted
    await a.tick(10)
    assert a.enabled and not a.manual_control.active


async def test_confirmed_manual_keeps_speed_without_sensor_changes_or_renewals():
    a, c, _ = make_auto()
    await a.configure(enabled=False)
    await a.tick(10)
    c.controller.data.update(manual_active=True, manual_mode="manual", manual_speed=2)
    await a.tick(20)
    a.hass.states.get = lambda entity: None
    await a.tick(100000)
    assert a.status == "manual" and a.manual_control.speed == 2
    assert c.controller.control.await_count == 1


async def test_unknown_manual_failure_after_setting_edit_stops_replay():
    a, c, _ = make_auto()
    await a.configure(enabled=False)

    async def uncertain(**kwargs):
        await a.configure(settings={"co2_target": 850})
        raise DeviceError("unknown write outcome")

    c.controller.control.side_effect = uncertain
    await a.tick(10)
    await a.tick(500)
    restarted = AutomaticControl(a.hass, c)
    await restarted.tick(1000)
    assert not restarted.manual_control.active
    assert c.controller.control.await_count == 1
    assert restarted.status == "command_error"


async def test_fresh_matching_ack_at_deadline_confirms_manual():
    a, c, _ = make_auto()
    await a.configure(enabled=False)
    await a.tick(10)
    c.controller.data.update(manual_active=True, manual_mode="manual", manual_speed=2)
    await a.tick(190)
    assert a.status == "manual" and a.manual_control.active
