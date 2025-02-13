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
