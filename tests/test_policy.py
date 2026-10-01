"""Policy layer: allow reads, confirm external writes, refuse destructive."""

from agent import policy


def test_reads_auto_allowed():
    for tool in ("gmail_search", "gmail_read", "calendar_list", "notes_list",
                 "web_search", "weather", "reminder_add", "gmail_draft"):
        verdict, _ = policy.check(tool)
        assert verdict == policy.ALLOW, tool


def test_send_and_calendar_create_need_confirmation(conn):
    for tool in ("gmail_send", "calendar_create"):
        verdict, _ = policy.check(tool)
        assert verdict == policy.CONFIRM, tool


def test_destructive_tools_refused():
    for tool in ("gmail_delete", "note_delete", "publish_post", "pay_bill",
                 "trade_stock", "run_shell", "transfer_money"):
        verdict, reason = policy.check(tool)
        assert verdict == policy.REFUSE, tool
        assert "ma'am" in reason  # plain-English, voice-shaped


def test_unknown_tool_defaults_to_confirm():
    verdict, _ = policy.check("some_future_tool")
    assert verdict == policy.CONFIRM


def test_confirmation_round_trip(conn):
    cid = policy.request_confirmation(
        conn, "gmail_send", {"to": "a@b.c"}, detail="Send email to a@b.c")
    row = policy.get_pending(conn, cid)
    assert row["op"] == "gmail_send"
    assert row["status"] == "pending"
    policy.resolve_confirmation(conn, cid, "approved")
    assert policy.get_pending(conn, cid)["status"] == "approved"
