"""Notes + reminders sqlite round-trips, including the due_outbox flow."""

from datetime import datetime, timedelta, timezone

from agent import scheduler, tool_impls
from agent import memory


def _future_iso(minutes=30):
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def _past_iso(minutes=30):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


def test_notes_jot_list_search(conn):
    assert "Noted" in tool_impls.notes_jot(conn, "buy oat milk")
    tool_impls.notes_jot(conn, "call the accountant about Q4")
    listed = tool_impls.notes_list(conn)
    assert "oat milk" in listed and "accountant" in listed
    found = tool_impls.notes_search(conn, "oat")
    assert "oat milk" in found
    assert "accountant" not in found
    assert "Nothing" in tool_impls.notes_search(conn, "zebra")


def test_notes_jot_empty(conn):
    assert "didn't catch" in tool_impls.notes_jot(conn, "   ")


def test_reminder_add_list_cancel(conn):
    msg = tool_impls.reminder_add(conn, "water the plants", _future_iso(60))
    assert "remind you" in msg
    listed = tool_impls.reminder_list(conn)
    assert "water the plants" in listed
    row = conn.execute("SELECT id FROM reminders").fetchone()
    assert "Cancelled" in tool_impls.reminder_cancel(conn, row["id"])
    assert "No reminders pending" in tool_impls.reminder_list(conn)
    assert "couldn't find" in tool_impls.reminder_cancel(conn, 9999)


def test_reminder_rejects_bad_and_past_times(conn):
    assert "couldn't make sense" in tool_impls.reminder_add(conn, "x", "not-a-time")
    assert "already past" in tool_impls.reminder_add(conn, "x", _past_iso(5))


def test_due_reminders_flow(conn):
    tool_impls.reminder_add(conn, "take out the trash", _future_iso(1))
    # Force it due by backdating (simulates the 60s watcher tick).
    conn.execute("UPDATE reminders SET scheduled_at = ? WHERE fired = 0",
                 (_past_iso(1),))
    conn.commit()
    assert scheduler.fire_due(conn) == 1
    out = conn.execute("SELECT * FROM due_outbox").fetchone()
    assert out["note"] == "take out the trash"
    assert out["announced"] == 0
    spoken = tool_impls.check_due_reminders(conn)
    assert "take out the trash" in spoken and "Ma'am" in spoken
    # Second read: already announced, nothing to say.
    assert tool_impls.check_due_reminders(conn) == ""


def test_memory_profile_episodic_followups(conn):
    memory.profile_set(conn, "timezone", "America/New_York")
    assert memory.profile_get(conn, "timezone") == "America/New_York"
    assert memory.profile_get(conn, "missing", "dflt") == "dflt"

    memory.log_episode(conn, "Evening check-in.", "2026-10-01T00:00:00+00:00")
    eps = memory.recent_episodes(conn)
    assert len(eps) == 1 and "Evening check-in" in eps[0]["summary"]

    fid = memory.add_follow_up(conn, "Ask about the grant draft", None)
    assert len(memory.open_follow_ups(conn)) == 1
    memory.complete_follow_up(conn, fid)
    assert memory.open_follow_ups(conn) == []

    brief = memory.startup_context(conn)
    assert "America/New_York" in brief
