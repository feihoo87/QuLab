from waveforms.sys.sched.task_tree import TaskTree as TaskTree
import pytest


def test_tree1():
    t = TaskTree()
    assert t.add_task(1, 0b1)
    assert set(t.ask_task()) == {1}
    assert t.add_task(2, 0b10)
    assert set(t.ask_task()) == {1, 2}
    assert t.add_task(3, 0b100)
    assert set(t.ask_task()) == {1, 2, 3}
    t.remove_task(2)
    assert set(t.ask_task()) == {1, 3}
    t.remove_task(1)
    assert set(t.ask_task()) == {3}
    t.remove_task(3)
    assert set(t.ask_task()) == set()


def test_tree2():
    t = TaskTree()
    assert t.add_task(1, 0b1)
    assert set(t.ask_task()) == {1}
    assert t.add_task(2, 0b10, 1)
    assert set(t.ask_task()) == {2}
    assert t.add_task(3, 0b100, 2)
    assert set(t.ask_task()) == {3}
    assert not t.add_task(4, 0b100, 1)
    assert set(t.ask_task()) == {3}
    assert t.add_task(4, 0b10, 1)
    assert set(t.ask_task()) == {3, 4}
    assert t.add_task(5, 0b1)
    assert set(t.ask_task()) == {3, 4, 5}
    t.remove_task(3)
    assert set(t.ask_task()) == {4, 5}
    t.remove_task(4)
    assert set(t.ask_task()) == {2, 5}
    t.remove_task(2)
    assert set(t.ask_task()) == {5}
    t.remove_task(5)
    assert set(t.ask_task()) == {1}
    t.remove_task(1)
    assert set(t.ask_task()) == set()


def test_tree3():
    return
    import itertools
    import random

    t = TaskTree()
    task_counter = itertools.count(start=1)

    finished = []
    cancelled = []
    runing = []
    history = {0: (0, [])}

    def create_task(i, parent):
        runing.append(i)
        history[i] = parent, []
        history[parent][1].append(i)

    def finish_task(task):
        finished.append(task)
        runing.remove(task)
        history[history[task][0]][1].remove(task)

    def cancel_task(task):
        for t in history[task][1].copy():
            cancel_task(t)
        if task in runing:
            runing.remove(task)
            cancelled.append(task)
        elif task in finished:
            pass
        else:
            raise ValueError("Task {} is not running".format(task))
        history[history[task][0]][1].remove(task)

    for step in range(100):
        if len(runing) == 0 or random.choice([True, False]):
            parent = 0
        else:
            parent = random.choice(runing)
        i = next(task_counter)
        assert t.add_task(i, 0, parent)
        create_task(i, parent)

    assert set(t.ask_task()) <= set(runing)
    assert set(runing) & set(finished) == set()
    assert set(runing) & set(cancelled) == set()
    assert set(finished) & set(cancelled) == set()
    assert set(history) == set(runing) | set(finished) | set(cancelled) | {
        0
    }

    for step in range(100):
        if random.choice([True, False]):
            for j in range(random.randint(0, 10)):
                if len(runing) == 0 or random.choice([True, False]):
                    parent = 0
                else:
                    parent = random.choice(runing)
                i = next(task_counter)
                assert t.add_task(i, 0, parent)
                create_task(i, parent)

                assert set(t.ask_task()) <= set(runing)
                assert set(runing) & set(finished) == set()
                assert set(runing) & set(cancelled) == set()
                assert set(finished) & set(cancelled) == set()
                assert set(history) == set(runing) | set(finished) | set(
                    cancelled) | {0}

        if random.choice([True, False]):
            active = t.ask_task()
            if len(active) > 0:
                random.shuffle(active)
                f = active[:random.randint(0, len(active))]
                for task in f:
                    assert task in runing
                    assert len(history[task][1]) == 0
                    t.remove_task(task)
                    finish_task(task)

                    assert set(t.ask_task()) <= set(runing)
                    assert set(runing) & set(finished) == set()
                    assert set(runing) & set(cancelled) == set()
                    assert set(finished) & set(cancelled) == set()
                    assert set(history) == set(runing) | set(finished) | set(
                        cancelled) | {0}

        if random.choice([True, False]):
            if len(runing) > 0:
                task = random.choice(runing)
                t.remove_task(task)
                cancel_task(task)

                assert set(t.ask_task()) <= set(runing)
                assert set(runing) & set(finished) == set()
                assert set(runing) & set(cancelled) == set()
                assert set(finished) & set(cancelled) == set()
                assert set(history) == set(runing) | set(finished) | set(
                    cancelled) | {0}

        assert set(t.ask_task()) <= set(runing)
        assert set(runing) & set(finished) == set()
        assert set(runing) & set(cancelled) == set()
        assert set(finished) & set(cancelled) == set()
        assert set(history) == set(runing) | set(finished) | set(cancelled) | {
            0
        }

    while True:
        active = t.ask_task()
        if len(active) == 0:
            break
        for task in active:
            assert task in runing
            assert len(history[task][1]) == 0
            t.remove_task(task)
            finish_task(task)
    assert set(t.ask_task()) == set()
    assert set(runing) == set()
    assert set(history) == set(finished) | set(cancelled) | {0}


def test_tree4():
    t = TaskTree()
    assert t.add_task(1, 0b1)
    assert set(t.ask_task()) == {1}
    assert t.add_task(2, 0b10, 1)
    assert set(t.ask_task()) == {2}
    assert t.add_task(3, 0b100, 1)
    assert set(t.ask_task()) == {2, 3}
    assert not t.add_task(4, 0b100, 1)
    assert t.add_task(5, 0b1000)
    assert t.add_task(6, 0b10001, 5)
    t.remove_task(2)
    assert set(t.ask_task()) == {3, 6}
    t.remove_task(3)
    assert set(t.ask_task()) == {6}
    t.remove_task(6)
    assert set(t.ask_task()) == {1, 5}


def test_tree5():
    import itertools
    import random

    t = TaskTree()
    task_counter = itertools.count(start=1)

    queue = []
    finished = []
    cancelled = []
    runing = []
    history = {0: (0, [])}

    def make_task():
        if len(runing) == 0 or random.choice([True, False]):
            parent = 0
        else:
            parent = random.choice(runing)
        task_id = next(task_counter)
        mask = (1 << random.randint(0, 31)) | (
            1 << random.randint(0, 31)) | (1 << random.randint(0, 31))
        return task_id, mask, parent

    def create_task(i, parent):
        runing.append(i)
        history[i] = parent, []
        history[parent][1].append(i)

    def finish_task(task):
        finished.append(task)
        runing.remove(task)
        history[history[task][0]][1].remove(task)

    def cancel_task(task):
        for t in history[task][1].copy():
            cancel_task(t)
        if task in runing:
            runing.remove(task)
            cancelled.append(task)
        elif task in finished:
            pass
        else:
            raise ValueError("Task {} is not running".format(task))
        history[history[task][0]][1].remove(task)

    for step in range(10):
        i, mask, parent = make_task()
        flag = t.add_task(i, mask, parent)
        if flag:
            create_task(i, parent)
        else:
            queue.append((i, parent, mask))

        assert set(t.ask_task()) <= set(runing)
        assert set(runing) & set(finished) == set()
        assert set(runing) & set(cancelled) == set()
        assert set(finished) & set(cancelled) == set()
        assert set(history) == set(runing) | set(finished) | set(
            cancelled) | {0}
    
    for step in range(100):
        for task, parent, mask in queue.copy():
            flag = t.add_task(task, mask, parent if parent in runing else 0)
            if flag:
                create_task(task, parent if parent in runing else 0)
                queue.remove((task, parent, mask))

        if random.choice([True, False]):
            for j in range(random.randint(0, 10)):
                i, mask, parent = make_task()
                flag = t.add_task(i, mask, parent)
                if flag:
                    create_task(i, parent)
                else:
                    queue.append((i, parent, mask))

                assert set(t.ask_task()) <= set(runing)
                assert set(runing) & set(finished) == set()
                assert set(runing) & set(cancelled) == set()
                assert set(finished) & set(cancelled) == set()
                assert set(history) == set(runing) | set(finished) | set(
                    cancelled) | {0}

        if random.choice([True, False]):
            active = t.ask_task()
            if len(active) > 0:
                random.shuffle(active)
                f = active[:random.randint(0, len(active))]
                for task in f:
                    assert task in runing
                    assert len(history[task][1]) == 0
                    t.remove_task(task)
                    finish_task(task)

                    assert set(t.ask_task()) <= set(runing)
                    assert set(runing) & set(finished) == set()
                    assert set(runing) & set(cancelled) == set()
                    assert set(finished) & set(cancelled) == set()
                    assert set(history) == set(runing) | set(finished) | set(
                        cancelled) | {0}

        if random.choice([True, False]):
            if len(runing) > 0:
                task = random.choice(runing)
                t.remove_task(task)
                cancel_task(task)

                assert set(t.ask_task()) <= set(runing)
                assert set(runing) & set(finished) == set()
                assert set(runing) & set(cancelled) == set()
                assert set(finished) & set(cancelled) == set()
                assert set(history) == set(runing) | set(finished) | set(
                    cancelled) | {0}

        assert set(t.ask_task()) <= set(runing)
        assert set(runing) & set(finished) == set()
        assert set(runing) & set(cancelled) == set()
        assert set(finished) & set(cancelled) == set()
        assert set(history) == set(runing) | set(finished) | set(cancelled) | {
            0
        }

    while True:
        for task, parent, mask in queue.copy():
            flag = t.add_task(task, mask, parent if parent in runing else 0)
            if flag:
                create_task(task, parent if parent in runing else 0)
                queue.remove((task, parent, mask))
        active = t.ask_task()
        if len(active) == 0:
            break
        for task in active:
            assert task in runing
            assert len(history[task][1]) == 0
            t.remove_task(task)
            finish_task(task)
    assert set(t.ask_task()) == set()
    assert set(runing) == set()
    assert set(history) == set(finished) | set(cancelled) | {0}


def test_remove_tree():
    t = TaskTree()
    assert t.add_task(1, 0b1)
    assert t.add_task(2, 0b10)
    assert t.add_task(3, 0b100)
    assert t.add_task(4, 0b1, 1)
    assert t.add_task(5, 0b1000, 1)
    assert t.add_task(6, 0b10, 2)
    assert set(t.ask_task()) == {3, 4, 5, 6}
    t.remove_task(1)
    with pytest.raises(ValueError):
        t.remove_task(4)
    with pytest.raises(ValueError):
        t.remove_task(5)
    assert set(t.ask_task()) == {3, 6}
    t.remove_task(3)
    assert set(t.ask_task()) == {6}
    t.remove_task(6)
    assert set(t.ask_task()) == {2}
    t.remove_task(2)
    assert set(t.ask_task()) == set()
    with pytest.raises(ValueError):
        t.remove_task(1)


def test_exception():
    t = TaskTree()
    with pytest.raises(ValueError):
        t.remove_task(0)

    with pytest.raises(ValueError):
        t.remove_task(1)
