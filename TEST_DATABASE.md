# Local test database

The test database is defined in `docker-compose.test.yml` and runs as the
`db` service in the `concave-support-test` Compose project. It uses PostgreSQL
16 Alpine, publishes host port `55432` on `127.0.0.1` only, and stores data in
the separate `postgres_test_data` volume.

Keep the credential file outside the repository. The Compose configuration
expects these variables from that file:

- `POSTGRES_DB` — `concave_support_desk_test`
- `POSTGRES_HOST` — `127.0.0.1` (required by the backend when it connects from the host)
- `POSTGRES_USER` — dedicated local test user
- `POSTGRES_PASSWORD` — unique local test password
- `POSTGRES_PORT` — `55432`
- `APP_ENV` — `test`
- `JWT_SECRET` — random secret of at least 32 characters

Start and stop the test service with:

```sh
docker compose --env-file /private/tmp/concave-support-test.env -f docker-compose.test.yml up -d
docker compose --env-file /private/tmp/concave-support-test.env -f docker-compose.test.yml down
```

The explicit `name` in the Compose file fixes its project name to
`concave-support-test`. Do not use this env file with the development Compose
configuration.

## Running backend tests safely

The backend test `conftest.py` checks the process environment before importing
the application or its global SQLAlchemy engine. It requires `APP_ENV=test`,
the exact test database name, host `127.0.0.1`, port `55432`, and non-empty
database credentials and JWT secret. It rejects missing or duplicate
configuration and alternate database URL variables. It does not load `.env`,
so missing test values cannot be filled from development settings.

From the repository root, load the external file into the shell first, then
run pytest from `backend`:

```sh
set -a
. /private/tmp/concave-support-test.env
set +a
cd backend
pytest
```

Add `POSTGRES_HOST=127.0.0.1` to the external test env file if it is not
already present. Exporting the dedicated values before pytest lets normal
application settings resolve to the test database; if any are absent or
point elsewhere, the guard stops pytest before app imports. The safety check
does not create the database, run migrations, or start Docker.
