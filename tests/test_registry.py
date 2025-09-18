from pinion.registry import REGISTRY, task


def test_task_registers_lowercase_name():
    @task("MyTask")
    def handler():
        return "ok"

    assert "mytask" in REGISTRY
    assert REGISTRY["mytask"] is handler


def test_task_default_name_lowercases_function_name():
    @task()
    def DoWork():  # noqa: N802 - intentional camelcase for test
        return "done"

    assert "dowork" in REGISTRY
