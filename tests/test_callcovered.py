"""CallCovered knowledge base + client onboarding pipeline tests."""

from agent import kb as kbmod
from agent import tool_impls as impl


def test_kb_seed_and_search(conn):
    n = kbmod.seed_kb(conn)
    assert n == 13, f"expected 13 articles, got {n}"
    hits = kbmod.search_kb(conn, "A2P registration")
    assert hits, "A2P article should be found"
    assert "a2p" in hits[0]["title"].lower() or "a2p" in hits[0]["body"].lower()
    # LIKE fallback path still works for odd queries
    hits2 = kbmod.search_kb(conn, "Roofful")
    assert hits2


def test_kb_search_tool_voice(conn):
    kbmod.seed_kb(conn)
    out = impl.kb_search(conn, "how much is the Receptionist tier")
    assert "497" in out
    out2 = impl.kb_search(conn, "quantum xylophone zebra")
    assert "Nothing in the CallCovered handbook" in out2


def test_client_add_and_pipeline(conn):
    out = impl.client_add(conn, "Sunshine Roofing", "Bob Rivera",
                          phone="305-555-0100", tier="Receptionist")
    assert "client #1" in out and "intake" in out
    row = conn.execute("SELECT * FROM clients WHERE id = 1").fetchone()
    assert row["stage"] == "intake"
    assert row["tier"] == "Receptionist"

    out = impl.client_stage(conn, 1, "a2p")
    assert "a2p" in out
    assert conn.execute("SELECT stage FROM clients WHERE id = 1").fetchone()["stage"] == "a2p"

    out = impl.client_stage(conn, 1, "bogus")
    assert "isn't a pipeline stage" in out
    out = impl.client_stage(conn, 999, "live")
    assert "No client #999" in out


def test_client_list_get_note(conn):
    impl.client_add(conn, "Alpha Roofing", tier="Essential")
    impl.client_add(conn, "Beta Roofing", tier="Growth")
    impl.client_stage(conn, 2, "live")

    out = impl.client_list(conn)
    assert "Alpha Roofing" in out and "Beta Roofing" in out
    out = impl.client_list(conn, "live")
    assert "Beta Roofing" in out and "Alpha Roofing" not in out

    out = impl.client_note(conn, 1, "Owner wants Spanish greeting first.")
    assert "Logged" in out
    out = impl.client_get(conn, 1)
    assert "Alpha Roofing" in out and "Spanish greeting" in out
    out = impl.client_get(conn, 999)
    assert "No client #999" in out


def test_client_add_requires_name(conn):
    out = impl.client_add(conn, "   ")
    assert "business name" in out
