from qulab.dicttree import *

step1 = {'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'y': 4}}
step2 = {'a': {'x': 2}, 'b': {'x': 3, 'y': 5}, 'c': {'x': 15}, 'd': 1, 'e': 1}
step3 = {'a': {'x': 3, 'y': 2, 'p': {'w': 10}}, 'c': {'x': 16}, 'd': 1, 'e': 2}
step4 = {'a': {'x': 4, 'y': 2}, 'b': {'x': 6, 'y': 4}, 'c': {'x': 17}}

data = {
    'qubits': {
        'Q1': {
            'frequency': 3.5,
        },
        'Q2': {
            'frequency': 3.6,
        },
    },
    'gate': {
        'pi2': {
            'Q1': {
                'freq': '$qubits.Q1.frequency',
                'amp': 0.5,
                'duration': '& 1/$.amp',
            },
            'Q2': {
                'freq': '$....qubits.Q2.frequency',
                'amp': 0.6,
                'duration': '& sin(1/$.amp)',
            }
        }
    }
}


def test_flattenDict():
    assert flattenDict({}) == {}
    assert flattenDict(step1) == {'a.x': 1, 'a.y': 2, 'b.x': 3, 'b.y': 4}


def test_foldDict():
    assert foldDict({}) == {}
    assert foldDict(flattenDict(step1)) == step1


def test_diff():
    assert diff({}, {}) == {}
    assert diff(step1, step1) == {}
    assert diff(step1, {}) == {'a': DELETE, 'b': DELETE}

    d1 = diff({}, step1)
    assert isinstance(d1['a'], Create) and d1['a'].n == {
        'x': 1,
        'y': 2
    } and d1['a'].replace == False
    assert isinstance(d1['b'], Create) and d1['b'].n == {
        'x': 3,
        'y': 4
    } and d1['b'].replace == False


def test_patch():
    assert patch(step1, {}) == step1
    assert patch(step1, diff(step1, {})) == {}
    assert patch({}, diff({}, step1)) == step1

    test = {
        'a': 1,
        'b': 2,
        'c': {
            'x': 3
        },
        'd': {
            'y': 4
        },
        'e': {
            'x': 1,
            'y': 4
        }
    }
    patch(test, {
        'a': Update(1, 10),
        'b': DELETE,
        'c': Create({'z': 12}, replace=True),
        'd': {
            'x': Create(5),
            'y': Update(4, 40)
        },
        'e': Create({
            'x': 2,
            'z': 13
        })
    },
          in_place=True)

    assert test == {
        'a': 10,
        'c': {
            'z': 12
        },
        'd': {
            'x': 5,
            'y': 40
        },
        'e': {
            'x': 2,
            'y': 4,
            'z': 13
        }
    }

    d1 = diff(step1, step2)
    d2 = diff(step2, step3)
    d3 = diff(step3, step4)

    assert patch(step1, d1) == step2
    assert patch(step2, d2) == step3
    assert patch(step3, d3) == step4


def test_merge():
    d1 = diff(step1, step2)
    d2 = diff(step2, step3)
    d3 = diff(step3, step4)

    assert merge(d1, d2, origin=step1) == diff(step1, step3)
    assert merge(d2, d3, origin=step2) == diff(step2, step4)

    assert patch(step1, merge(d1, d2)) == step3
    assert patch(step1, merge(merge(d1, d2), d3)) == step4
    assert patch(step1, merge(d1, merge(d2, d3))) == step4


def test_query():
    assert query_tree('a', step3) == {'x': 3, 'y': 2, 'p': {'w': 10}}
    assert query_tree('a.p', step3) == {'w': 10}
    assert query_tree('a.p.w', step3) == 10
    assert query_tree('a.p.w', step1) == (NOTSET, 'a.p')


def test_ref():
    assert query_tree('gate.pi2.Q1.freq', data) == 3.5
    assert query_tree('gate.pi2.Q2.freq', data) == 3.6


# def test_eval():
#     assert query_tree('gate.pi2.Q1.duration', data) == 2.0
#     assert query_tree('gate.pi2.Q2.duration', data) == 0.9954079577517649


def test_print():
    import io
    buf = io.StringIO()

    d1 = diff(step1, step3)
    print_diff(d1, file=buf)

    buf.seek(0)
    assert buf.read() == (
        "a.x                                      Update: 1 ==> 3\n"
        "a.p                                      Create: {'w': 10}\n"
        "c                                        Create: {'x': 16}\n"
        "d                                        Create: 1\n"
        "e                                        Create: 2\n"
        "b                                        Delete\n")
