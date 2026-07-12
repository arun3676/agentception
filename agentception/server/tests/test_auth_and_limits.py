"""Auth, rate limiting, and run persistence."""

import gc
import sqlite3

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from server.app import app
from server.auth import User, require_user
from server.memory import sql_store
from server.rate_limit import RateLimiter


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def as_user():
    """Sign in as a given user id for the duration of a test."""

    def _sign_in(user_id: str):
        app.dependency_overrides[require_user] = lambda: User(id=user_id, is_anonymous=False)
        return TestClient(app)

    yield _sign_in
    app.dependency_overrides.pop(require_user, None)


class TestOutcomesOwnership:
    """`/outcomes/*` took the owner from the client — body field on log, query
    string on patterns, defaulting to "demo-user". So anyone could read or write
    another user's application outcomes by naming them. Same hole as the v1
    application and learning-path routes; it just lived on the root app, which is
    why the first pass missed it.
    """

    def test_patterns_rejects_anonymous(self, client):
        assert client.get("/outcomes/patterns").status_code == 401

    def test_patterns_cannot_be_targeted_at_another_user(self, client):
        # The old signature was `outcome_patterns(user_id: str = "demo-user")`.
        # A query param must not be able to select whose outcomes come back.
        assert client.get("/outcomes/patterns?user_id=victim").status_code == 401

    def test_log_rejects_anonymous(self, client):
        r = client.post(
            "/outcomes/log",
            json={"company": "Acme", "role": "AI Engineer", "outcome": "offer"},
        )
        assert r.status_code == 401

    def test_log_ignores_a_client_supplied_owner(self, as_user):
        # Even signed in, a user_id in the body must not choose the owner.
        c = as_user("bob")
        r = c.post(
            "/outcomes/log",
            json={
                "user_id": "alice",  # attacker-controlled; must be ignored
                "company": "Acme",
                "role": "AI Engineer",
                "outcome": "offer",
            },
        )
        # Pydantic drops the unknown field; the route must still succeed as *bob*.
        assert r.status_code == 200, r.text


class TestRateLimiter:
    def test_allows_up_to_the_burst(self):
        limiter = RateLimiter("test", per_minute=60, burst=3)
        for _ in range(3):
            limiter.check("client-a")  # must not raise

    def test_blocks_past_the_burst(self):
        limiter = RateLimiter("test", per_minute=60, burst=2)
        limiter.check("client-b")
        limiter.check("client-b")
        with pytest.raises(HTTPException) as exc:
            limiter.check("client-b")
        assert exc.value.status_code == 429
        assert "Retry-After" in exc.value.headers

    def test_clients_have_separate_buckets(self):
        # One noisy visitor must not rate-limit everyone else.
        limiter = RateLimiter("test", per_minute=60, burst=1)
        limiter.check("client-c")
        limiter.check("client-d")  # different client: still allowed

    def test_refills_over_time(self):
        limiter = RateLimiter("test", per_minute=6000, burst=1)  # 100/sec
        limiter.check("client-e")
        import time

        time.sleep(0.05)
        limiter.check("client-e")  # bucket refilled


class TestRunPersistence:
    def test_run_survives_the_process_that_created_it(self):
        sql_store.init()
        doc = {"run_id": "persist-1", "role": "AI Engineer", "companies": [{"company_name": "Acme"}]}
        sql_store.search_run_save("persist-1", user_id="u1", role="AI Engineer", city="SF", doc=doc)

        # Simulates a fresh process: nothing in memory, everything from the DB.
        loaded = sql_store.search_run_get("persist-1")
        assert loaded is not None
        assert loaded["companies"][0]["company_name"] == "Acme"

    def test_unknown_run_is_none(self):
        sql_store.init()
        assert sql_store.search_run_get("no-such-run") is None

    def test_runs_are_listed_per_user(self):
        sql_store.init()
        sql_store.search_run_save("persist-2", "user-x", "Data Engineer", "NYC", {"a": 1})
        runs = sql_store.search_runs_for_user("user-x")
        assert any(r["run_id"] == "persist-2" for r in runs)


class TestDataDeletion:
    def test_purge_removes_the_users_rows(self):
        sql_store.init()
        sql_store.search_run_save("purge-me", "doomed-user", "AI Engineer", "SF", {"x": 1})
        assert sql_store.search_run_get("purge-me") is not None

        sql_store.purge_user_data("doomed-user")

        # A privacy promise that doesn't delete anything is a lie.
        assert sql_store.search_run_get("purge-me") is None

    def test_purge_leaves_other_users_alone(self):
        sql_store.init()
        sql_store.search_run_save("keep-me", "safe-user", "AI Engineer", "SF", {"x": 1})
        sql_store.purge_user_data("some-other-user")
        assert sql_store.search_run_get("keep-me") is not None


class TestResumePII:
    def test_forget_user_drops_every_cached_copy(self):
        from server.tools import resume_store

        token = resume_store.put_text("Jane Doe — jane@example.com — Senior Engineer")
        resume_store.associate_token("user-pii", token)
        assert resume_store.get_text(token) is not None

        resume_store.forget_user("user-pii")
        assert resume_store.get_text(token) is None


class TestApplicationOwnership:
    def test_status_update_cannot_cross_user_boundary(self):
        sql_store.init()
        sql_store.job_application_add(
            app_id="owned-application", user_id="owner", company_name="Acme",
            job_title="AI Engineer", job_url="https://example.com/job", application_status="saved",
        )

        assert sql_store.job_application_update_status("owned-application", "offer", user_id="other-user") is None
        owner_rows = sql_store.job_applications_list(user_id="owner")
        assert owner_rows[0]["application_status"] == "saved"


class TestLearningPathOwnership:
    """`GET /api/v1/learning-paths` used to take user_id from the QUERY STRING with
    no auth at all, so anyone could list, target, or read any user's paths. Omitting
    user_id returned *every* user's paths."""

    def _seed_alice(self):
        sql_store.init()
        sql_store.learning_path_save(
            path_id="lp-alice", user_id="alice", title="Alice's private roadmap",
            topic="RAG", expertise_level="advanced", path_json={"secret": "alice"},
        )

    def test_listing_requires_a_token(self, client):
        self._seed_alice()
        assert client.get("/api/v1/learning-paths").status_code == 401

    def test_listing_cannot_be_targeted_at_another_user_by_query_param(self, client):
        # The original hole: ?user_id=alice with no token.
        self._seed_alice()
        assert client.get("/api/v1/learning-paths?user_id=alice").status_code == 401

    def test_reading_a_path_by_id_requires_a_token(self, client):
        self._seed_alice()
        assert client.get("/api/v1/learning-paths/lp-alice").status_code == 401

    def test_a_signed_in_user_sees_only_their_own_paths(self, as_user):
        self._seed_alice()
        bob = as_user("bob")
        body = bob.get("/api/v1/learning-paths").json()
        titles = [p["title"] for p in body["paths"]]
        assert "Alice's private roadmap" not in titles

    def test_a_user_cannot_read_another_users_path_by_id(self, as_user):
        self._seed_alice()
        bob = as_user("bob")
        response = bob.get("/api/v1/learning-paths/lp-alice")
        # 404, not 403: a 403 would confirm the id exists, which is itself a leak.
        assert response.status_code == 404
        assert "alice" not in response.text.lower()

    def test_the_owner_can_still_read_their_own_path(self, as_user):
        self._seed_alice()
        alice = as_user("alice")
        assert alice.get("/api/v1/learning-paths/lp-alice").status_code == 200
        titles = [p["title"] for p in alice.get("/api/v1/learning-paths").json()["paths"]]
        assert "Alice's private roadmap" in titles


class TestOwnershipIsEnforcedBySignature:
    """The store used to accept user_id=None and silently fall through to an
    unscoped query. One forgotten argument was one data leak."""

    def test_listing_applications_without_a_user_is_refused(self):
        with pytest.raises(ValueError):
            sql_store.job_applications_list(user_id="")

    def test_updating_an_application_without_a_user_is_refused(self):
        with pytest.raises(ValueError):
            sql_store.job_application_update_status("some-app", "offer", user_id="")

    def test_listing_learning_paths_without_a_user_is_refused(self):
        with pytest.raises(ValueError):
            sql_store.learning_path_list(user_id="")

    def test_saving_an_unowned_learning_path_is_refused(self):
        with pytest.raises(ValueError):
            sql_store.learning_path_save(
                path_id="lp-orphan", user_id="", title="t", topic="x",
                expertise_level="beginner", path_json={},
            )


class TestConnectionHygiene:
    """`with sqlite3.connect(...)` is a TRANSACTION manager: it commits, it does
    NOT close. Holding a cursor past the block kept a connection alive while the
    next call opened a second one against the same file — which made the DB file
    undeletable on Windows and invites `database is locked` anywhere."""

    @staticmethod
    def _open_connections() -> int:
        gc.collect()
        still_open = 0
        for obj in gc.get_objects():
            if isinstance(obj, sqlite3.Connection):
                try:
                    obj.execute("SELECT 1")
                    still_open += 1
                except sqlite3.ProgrammingError:
                    pass  # already closed — what we want
                except sqlite3.Error:
                    pass
        return still_open

    def test_conn_closes_the_handle_when_the_block_exits(self):
        """The contract, asserted directly.

        This is the test that pins the fix. The end-state checks below can be
        satisfied by refcounting luck; this one cannot — if `_conn()` stops
        closing, the handle is still usable here and the test fails.
        """
        with sql_store._conn() as c:
            c.execute("SELECT 1")

        with pytest.raises(sqlite3.ProgrammingError):
            c.execute("SELECT 1")  # closed, so this must raise

    def test_a_cursor_held_past_the_block_cannot_pin_the_connection(self):
        """The exact shape of the original bug: `cursor` escapes the `with`."""
        sql_store.init()
        with sql_store._conn() as c:
            cursor = c.execute("SELECT 1")

        # `cursor` still references the connection — but the connection is closed,
        # so it can no longer hold the database file open.
        assert cursor is not None
        with pytest.raises(sqlite3.ProgrammingError):
            cursor.execute("SELECT 1")

    def test_a_status_update_leaves_no_open_connection(self):
        sql_store.init()
        sql_store.job_application_add(
            app_id="conn-app", user_id="conn-user", company_name="Acme",
            job_title="AI Engineer", job_url="https://example.com/j", application_status="saved",
        )
        assert self._open_connections() == 0

        sql_store.job_application_update_status("conn-app", "offer", user_id="conn-user")

        # Before the fix this was 1: `cursor` escaped the `with` block and pinned
        # the connection while job_applications_list() opened another.
        assert self._open_connections() == 0

    def test_reads_leave_no_open_connection(self):
        sql_store.init()
        sql_store.job_applications_list(user_id="conn-user")
        sql_store.learning_path_list(user_id="conn-user")
        assert self._open_connections() == 0
