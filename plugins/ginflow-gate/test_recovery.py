#!/usr/bin/env python3
import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("recovery", Path(__file__).with_name("recovery.py"))
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def event(kind="transient", attempt=0):
    return module.blocker_event(card_id="C", workspace="/repo", previous_assignee="worker",
                                blocker_kind=kind, error="boom", worker="worker",
                                evidence={"x": 1}, event_id="E", attempt=attempt)


def main():
    base = event()
    assert module.evaluate(base, current_workspace="/repo", current_assignee="worker", status="blocked").action == "reassign"
    assert module.evaluate(event("config_error"), current_workspace="/repo", current_assignee="worker", status="blocked").action == "stay_blocked"
    assert module.evaluate(event("unknown", 3), current_workspace="/repo", current_assignee="worker", status="blocked").action == "notify_human"
    assert module.evaluate({}, current_workspace="/repo", current_assignee="worker", status="blocked").reason == "malformed_safety_state"
    store = module.RecoveryLeaseStore()
    assert store.claim("C", "run-1", 10)
    assert not store.claim("C", "run-2", 10)
    assert store.release("C", "run-1")
    sent = []
    notification = module.queue_notification(card_id="C", event_id="E", message="alert")
    assert module.deliver_notification(notification, sent.append).delivered
    assert module.deliver_notification(notification, sent.append).reason == "already_delivered"
    assert len(sent) == 1
    print("blocked recovery policy passed")


if __name__ == "__main__":
    main()
