# scripts/

One-off operational scripts. Nothing here is imported by the application, and
nothing here runs under `pytest` — several of these call live, billed APIs.

Run them from the project root:

```bash
python scripts/check_openai_key.py            # verify OPENAI_API_KEY works (makes a real call)
python scripts/check_mock_mode.py             # is MOCK_SEARCH on?
python scripts/enable_mock_mode.py enable     # search without spending credits
python scripts/enable_mock_mode.py disable
python scripts/keep_alive.py                  # ping Supabase so the free tier doesn't pause
python scripts/migrate_application_outcomes.py  # create the application_outcomes table
```

`check_openai_key.py` was previously named `test_openai_key.py`. pytest imports
every `test_*.py` it discovers during collection, so the old name meant a bare
`pytest` run silently issued a paid OpenAI request. Keep the `check_` prefix.
