"""Auth, rate limiting, and run persistence."""

import pytest
from fastapi import HTTPException

from server.memory import sql_store
from server.rate_limit import RateLimiter


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
