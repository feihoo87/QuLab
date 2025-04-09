from .storage import Report, save_item

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


def _delete_config(name: str):
    import pickle

    try:
        with open('parameters.pkl', 'rb') as f:
            parameters = pickle.load(f)
    except:
        parameters = {}

    if name in parameters:
        del parameters[name]

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


def _clear_config():
    import pickle

    try:
        with open('parameters.pkl', 'rb') as f:
            parameters = pickle.load(f)
    except:
        parameters = {}

    parameters.clear()

    with open('parameters.pkl', 'wb') as f:
        pickle.dump(parameters, f)


def obey_the_oracle(report: Report, data_path):
    global __current_config_id
    update_config(report.oracle)
    cfg = export_config()
    __current_config_id = save_item(cfg, 'items', data_path)


def update_parameters(report: Report, data_path):
    global __current_config_id
    update_config(report.parameters)
    cfg = export_config()
    __current_config_id = save_item(cfg, 'items', data_path)


def current_config(data_path):
    global __current_config_id
    if __current_config_id is None:
        cfg = export_config()
        __current_config_id = save_item(cfg, 'items', data_path)
    return __current_config_id


query_config = _query_config
update_config = _update_config
delete_config = _delete_config
export_config = _export_config
clear_config = _clear_config


def set_config_api(query_method,
                   update_method,
                   delete_method,
                   export_method,
                   clear_method=None):
    """
    Set the query and update methods for the config.

    Args:
        query_method: The query method.
            the method should take a key and return the value.
        update_method: The update method.
            the method should take a dict of updates.
        delete_method: The delete method.
            the method should take a key and delete it.
        export_method: The export method.
            the method should return a dict of the config.
        clear_method: The clear method.
            the method should clear the config.
    """
    global query_config, update_config, delete_config, export_config, clear_config

    query_config = query_method
    update_config = update_method
    delete_config = delete_method
    export_config = export_method
    clear_config = clear_method

    return query_config, update_config, delete_config, export_config, clear_config
