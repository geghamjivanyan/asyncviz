"""Transition-guard tests."""

from __future__ import annotations

import pytest

from asyncviz.replay.runtime.control import (
    IllegalTransitionError,
    PlaybackPhase,
    check_transition,
    legal_next_phases,
)


def test_no_op_transitions_are_allowed() -> None:
    for phase in PlaybackPhase:
        assert check_transition(phase, phase).allowed


def test_playing_can_pause_or_step_or_terminate() -> None:
    legal = legal_next_phases(PlaybackPhase.PLAYING)
    assert PlaybackPhase.PAUSING in legal
    assert PlaybackPhase.PAUSED in legal
    assert PlaybackPhase.STEPPING in legal
    assert PlaybackPhase.STOPPED in legal
    assert PlaybackPhase.FAILED in legal


def test_paused_cannot_become_pausing_directly() -> None:
    verdict = check_transition(PlaybackPhase.PAUSED, PlaybackPhase.PAUSING)
    assert not verdict.allowed


def test_terminal_phases_only_transition_to_idle() -> None:
    assert legal_next_phases(PlaybackPhase.STOPPED) == frozenset({PlaybackPhase.IDLE})
    assert legal_next_phases(PlaybackPhase.FAILED) == frozenset({PlaybackPhase.IDLE})


def test_illegal_transition_raises_under_strict() -> None:
    verdict = check_transition(PlaybackPhase.IDLE, PlaybackPhase.PAUSED)
    with pytest.raises(IllegalTransitionError):
        verdict.raise_if_illegal()


def test_resuming_can_go_back_to_paused() -> None:
    verdict = check_transition(PlaybackPhase.RESUMING, PlaybackPhase.PAUSED)
    assert verdict.allowed
