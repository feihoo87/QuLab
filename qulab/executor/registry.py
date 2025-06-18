import copy
import importlib
import os
import sys
from typing import Any

from ..cli.config import get_config_value
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
    global query_config, update_config, delete_config, export_config, clear_config, _api

    query_config = query_method
    update_config = update_method
    delete_config = delete_method
    export_config = export_method
    clear_config = clear_method

    return query_config, update_config, delete_config, export_config, clear_config


def _init():
    code = get_config_value("code", str, default=None)
    if code is not None:
        code = os.path.expanduser(code)
        if code not in sys.path:
            sys.path.insert(0, code)

    api = get_config_value('api', str, None)
    if api is not None:
        api = importlib.import_module(api)
        set_config_api(api.query_config, api.update_config, api.delete_config,
                       api.export_config, api.clear_config)


_init()


class RegistrySnapshot:

    def __init__(self, data: dict[str, Any]):
        self.data = copy.deepcopy(data)

    def query(self, key: str, default=...) -> Any:
        """
        Query a value from the nested dictionary using dot-separated keys.
        
        Args:
            key: Dot-separated key path (e.g., 'level1.level2.level3')
            default: Default value to return if key not found.
                     If not provided and key is missing, raises KeyError.
            
        Returns:
            The value at the specified path, default value, or raises KeyError
        """
        keys = key.split('.')
        current = self.data

        # Track which level we're at for error reporting
        for i, k in enumerate(keys):
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                # Key not found at this level
                missing_path = '.'.join(keys[:i + 1])
                if default is ...:
                    raise KeyError(
                        f"Key '{missing_path}' not found in registry (failed at level {i+1})"
                    )
                return default

        return current

    def get(self, key: str, default=...) -> Any:
        """
        Query a value from the nested dictionary using dot-separated keys.
        
        Args:
            key: Dot-separated key path (e.g., 'level1.level2.level3')
            default: Default value to return if key not found.
                     If not provided and key is missing, raises KeyError.
            
        Returns:
            The value at the specified path, default value, or raises KeyError
        """
        return self.query(key, default)

    def export(self) -> dict[str, Any]:
        return self.data

    def set(self, key: str, value: Any):
        """
        Set a value in the nested dictionary using dot-separated keys.
        Creates intermediate dictionaries if they don't exist.
        
        Args:
            key: Dot-separated key path (e.g., 'level1.level2.level3')
            value: Value to set
        """
        keys = key.split('.')
        current = self.data

        # Navigate to the parent of the target key, creating dicts as needed
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            elif not isinstance(current[k], dict):
                # If existing value is not a dict, replace it with a dict
                current[k] = {}
            current = current[k]

        # Set the final value
        current[keys[-1]] = value

    def delete(self, key: str):
        """
        Delete a value from the nested dictionary using dot-separated keys.
        Also cleans up empty parent dictionaries after deletion.
        
        Args:
            key: Dot-separated key path (e.g., 'level1.level2.level3')
        """
        keys = key.split('.')

        # First check if the path exists
        try:
            self.query(key)
        except KeyError:
            return  # Path doesn't exist, nothing to delete

        # Navigate and collect references to all parent dictionaries
        path_refs = []
        current = self.data

        for k in keys[:-1]:
            path_refs.append((current, k))
            current = current[k]

        # Delete the final key
        if isinstance(current, dict) and keys[-1] in current:
            del current[keys[-1]]

            # Clean up empty dictionaries from leaf to root
            for parent_dict, parent_key in reversed(path_refs):
                # Check if the current dictionary is empty
                if isinstance(current, dict) and len(current) == 0:
                    del parent_dict[parent_key]
                    current = parent_dict
                else:
                    # Stop if we encounter a non-empty dictionary
                    break

    def clear(self):
        self.data.clear()

    def update(self, parameters: dict[str, Any]):
        for k, v in parameters.items():
            self.set(k, v)


class Registry():

    def __init__(self):
        self.api = (query_config, update_config, delete_config, export_config,
                    clear_config)

    def query(self, key: str) -> Any:
        return self.api[0](key)

    def get(self, key: str) -> Any:
        return self.query(key)

    def export(self) -> dict[str, dict[str, Any]]:
        return self.api[3]()

    def set(self, key: str, value: Any):
        return self.api[1]({key: value})

    def delete(self, key: str):
        return self.api[2](key)

    def clear(self):
        return self.api[4]()

    def update(self, parameters: dict[str, Any]):
        return self.api[1](parameters)

    def snapshot(self) -> RegistrySnapshot:
        return RegistrySnapshot(self.export())
