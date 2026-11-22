#!/usr/bin/env python3
"""Focused alert behavior checks; no Hermes board or gateway is started."""
import importlib
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
br = importlib.import_module('ginflow-gate.block_routing')


def test_message():
    msg = br.build_message('t_123', 'credential rejected\nrequired_action: rotate key', 'worker', 4)
    assert len(msg.splitlines()) == 2, msg
    assert '[HIGH]' in msg and 't_123' in msg and 'Agent can fix: No' in msg, msg
    assert 'Your action: rotate key' in msg, msg


def test_trace_off_notify_fallback():
    task = {'id': 't_123', 'workspace_path': '/tmp/alert-project', 'block_kind': 'needs_input',
            'assignee': 'worker', 'status': 'blocked', 'comments': []}
    with patch.object(br, '_load_task', return_value=task), \
         patch.object(br._config, 'context_error', return_value=None), \
         patch.object(br._config, 'configured_reviewer', return_value=None), \
         patch.object(br._config, 'configured_notify_target', return_value='slack:ops'), \
         patch.object(br, '_telegram_home', return_value='telegram'), \
         patch.object(br, '_push', side_effect=[False, True]) as push:
        br.on_task_blocked(task_id='t_123', board='b', assignee='worker', run_id=4,
                           reason='credential rejected\nrequired_action: rotate key')
    assert [c.args[0] for c in push.call_args_list] == ['slack:ops', 'telegram'], push.call_args_list


if __name__ == '__main__':
    test_message()
    test_trace_off_notify_fallback()
    print('PASS: actionable alerts focused checks')
