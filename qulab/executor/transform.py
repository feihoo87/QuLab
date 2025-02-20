from .storage import Report, save_config

__current_config_id = None


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


def _export_config() -> dict:
    import pickle

    try:
        with open('parameters.pkl', 'rb') as f:
            parameters = pickle.load(f)
    except:
        parameters = {}

    return parameters


def obey_the_oracle(report: Report, data_path):
    global __current_config_id
    update_config(report.oracle)
    cfg = export_config()
    __current_config_id = save_config(cfg, data_path)


def update_parameters(report: Report, data_path):
    global __current_config_id
    update_config(report.parameters)
    cfg = export_config()
    __current_config_id = save_config(cfg, data_path)


def current_config(data_path):
    global __current_config_id
    if __current_config_id is None:
        cfg = export_config()
        __current_config_id = save_config(cfg, data_path)
    return __current_config_id


query_config = _query_config
update_config = _update_config
export_config = _export_config


def set_config_api(query_method, update_method, export_method):
    """
    Set the query and update methods for the config.

    Args:
        query_method: The query method.
            the method should take a key and return the value.
        update_method: The update method.
            the method should take a dict of updates.
    """
    global query_config, update_config, export_config

    query_config = query_method
    update_config = update_method
    export_config = export_method

    return query_config, update_config, export_config
