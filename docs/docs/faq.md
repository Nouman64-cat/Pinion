## FAQ

- What Python versions are supported?
  - Python 3.12+.

- Do I get task return values?
  - No built-in result channel; tasks should handle their own outputs.

- Can I run across multiple machines?
  - The SQLite backend is local to a machine. Use or implement another `Storage` for distributed scenarios.

- How do I register tasks for the CLI worker?
  - Provide `--import your.module` so the worker process imports and registers your `@task` functions.

- Why did my task time out but still run?
  - Python threads can’t be forcibly killed. The worker marks the job failed after the timeout, but the task’s thread may continue. Prefer cooperative cancellation or separate processes for hard timeouts.

