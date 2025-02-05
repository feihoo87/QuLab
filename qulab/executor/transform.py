import loguru

from .storage import Result


def _query_config(name: str, default=None):
    import pickle

    try:
        with open('parameters.pkl', 'rb') as f:
            parameters = pickle.load(f)
    except:
        parameters = {}

    return parameters.get(name, default)


def _update_config(updates):
    import pickle

    try:
        with open('parameters.pkl', 'rb') as f:
            parameters = pickle.load(f)
    except:
        parameters = {}

    for k, v in updates.items():
        parameters[k] = v

    with open('parameters.pkl', 'wb') as f:
        pickle.dump(parameters, f)


def update_parameters(result: Result):
    update_config(result.params)


def result_to_params(result: Result | None) -> tuple | None:
    if result is None:
        return None

    state = 'Bad data'
    match (result.in_spec, result.bad_data):
        case (True, False):
            state = 'In spec'
        case (False, True):
            state = 'Bad data'
        case (False, False):
            state = 'Out of spec'

    return state, result.params, result.info


def params_to_result(params: tuple) -> Result:
    state, cali, info = params
    result = Result()
    if state in ['In spec', 'OK']:
        result.in_spec = True
        result.bad_data = False
    elif state in ['Bad data', 'Bad']:
        result.bad_data = True
        result.in_spec = False
    else:
        result.bad_data = False
        result.in_spec = False
    result.params = cali
    result.info = info
    return result


query_config = _query_config
update_config = _update_config


def set_config_api(query_method, update_method):
    """
    Set the query and update methods for the config.

    Args:
        query_method: The query method.
            the method should take a key and return the value.
        update_method: The update method.
            the method should take a dict of updates.
    """
    global query_config, update_config

    query_config = query_method
    update_config = update_method

    return query_config, update_config
