# Ariadne SQLite Seed

`ariadne.sqlite` is a curated seed database for local dogfooding and public collaboration.

It is a binary artifact, not a mergeable source format. Rebuild it from the trusted Ariadne database and run the preflight before committing an update:

```bash
ariadne migrate-postgres-to-sqlite seed/ariadne.sqlite --overwrite
ariadne compact --database-url sqlite+pysqlite:///seed/ariadne.sqlite --apply --keep-retrieval-logs 100
ariadne doctor --database-url sqlite+pysqlite:///seed/ariadne.sqlite
ariadne scan-db-secrets --database-url sqlite+pysqlite:///seed/ariadne.sqlite
```

Only commit the seed if `doctor` reports no issues and `scan-db-secrets` reports `ok_to_distribute: true`.
