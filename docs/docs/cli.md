## CLI Reference

Binary: `pinion` (also available as `pinion-queue`).

Global flags:

- `-V/--version`: print version and exit
- `--no-update-check`: disable the lightweight PyPI update check
- `--demo`: run a small in-memory demo and exit

Admin subcommands (SQLite only):

- `status --db pinion.db`: show queue size, job counts by status, DLQ count
- `running --db pinion.db --limit N`: list RUNNING jobs
- `pending --db pinion.db --limit N`: list PENDING jobs
- `dlq-list --db pinion.db --limit N`: list DLQ entries
- `dlq-replay --db pinion.db --limit N`: re-enqueue oldest DLQ entries, removing them from DLQ
- `enqueue TASK --db pinion.db --args JSON --kwargs JSON`: enqueue a job by name
- `worker --db pinion.db [opts]`: run a worker loop against the DB

Worker options:

- `--max-retries INT` (default 3)
- `--base-delay FLOAT` (default 0.5s)
- `--no-jitter` (disable randomization)
- `--task-timeout FLOAT` (seconds; 0 disables)
- `--visibility-timeout FLOAT` (default 10s)
- `--run-seconds FLOAT` (if set, run in background for N seconds then exit)
- `--import MOD` (repeatable; import Python module(s) to register tasks in-process)

Examples:

```bash
pinion status --db pinion.db
pinion running --db pinion.db --limit 10
pinion enqueue add --db pinion.db --args '[1,2]'
pinion worker --db pinion.db --max-retries 2 --task-timeout 5 \
  --import your_project.tasks --run-seconds 5
```

