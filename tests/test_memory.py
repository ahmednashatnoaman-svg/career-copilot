from app.memory.checkpointer import checkpointer_cm, store_cm


def test_factories_are_context_managers():
    assert hasattr(checkpointer_cm(), "__enter__")
    assert hasattr(store_cm(), "__enter__")
