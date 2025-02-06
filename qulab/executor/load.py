import inspect
import warnings
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType

import loguru

from .storage import Result


class SetConfigWorkflow():
    __timeout__ = None

    def __init__(self, key):
        self.key = key

    def depends(self):
        return [[]]

    def check_state(self, history: Result) -> bool:
        from . import transform
        try:
            return self._equal(history.params[self.key],
                               transform.query_config(self.key))
        except:
            return False

    def calibrate(self):
        from . import transform
        try:
            value = transform.query_config(self.key)
        except:
            value = eval(input(f'"{self.key}": '))
        return self.key, value

    def analyze(self, key, value, history):
        return 'OK', {key: value}, {}

    def check(self):
        from .transform import query_config
        return self.key, query_config(self.key)

    def check_analyze(self, key, value, history):
        return 'Out of Spec', {key: value}, {}

    @staticmethod
    def _equal(a, b):
        import numpy as np

        try:
            return a == b
        except:
            pass

        if isinstance(a, np.ndarray) and isinstance(b, np.ndarray):
            return a.shape == b.shape and np.all(a == b)

        return False


WorkflowType = ModuleType | SetConfigWorkflow


def can_call_without_args(func):
    if not callable(func):
        return False

    # 获取函数签名
    sig = inspect.signature(func)
    for param in sig.parameters.values():
        # 如果有参数没有默认值且不是可变参数，则无法无参调用
        if (param.default is param.empty and param.kind
                not in (param.VAR_POSITIONAL, param.VAR_KEYWORD)):
            return False
    return True


def verify_calibrate_method(module: WorkflowType):
    if not hasattr(module, 'calibrate'):
        raise AttributeError(
            f"Workflow {module.__file__} does not have 'calibrate' function")

    if not can_call_without_args(module.calibrate):
        raise AttributeError(
            f"Workflow {module.__file__} 'calibrate' function should not have any parameters"
        )

    if not hasattr(module, 'analyze'):
        raise AttributeError(
            f"Workflow {module.__file__} does not have 'analyze' function")


def verify_check_method(module: WorkflowType):
    if not hasattr(module, 'check'):
        warnings.warn(
            f"Workflow {module.__file__} does not have 'check' function")
    else:
        if not can_call_without_args(module.check):
            raise AttributeError(
                f"Workflow {module.__file__} 'check' function should not have any parameters"
            )

        if not hasattr(module, 'check_analyze'):
            raise AttributeError(
                f"Workflow {module.__file__} has 'check' function but does not have 'check_analyze' function"
            )


def is_workflow(module: ModuleType) -> bool:
    try:
        verify_calibrate_method(module)
        return True
    except AttributeError:
        return False


def find_unreferenced_workflows(path: str) -> list[str]:
    root = Path(path).resolve()
    workflows = []
    workflow_paths: set[str] = set()

    # Collect all workflow modules
    for file_path in root.rglob("*.py"):
        if file_path.name == "__init__.py":
            continue
        try:
            rel_path = file_path.relative_to(root)
        except ValueError:
            continue

        module = load_workflow(str(rel_path), root)

        if is_workflow(module):
            rel_str = str(rel_path)
            workflows.append(rel_str)
            workflow_paths.add(rel_str)

    dependencies: set[str] = set()

    # Check dependencies for each workflow module
    for rel_str in workflows:
        module = load_workflow(rel_str, root)

        depends_func = getattr(module, "depends", None)
        if depends_func and callable(depends_func):
            if not can_call_without_args(depends_func):
                warnings.warn(
                    f"Skipping depends() in {rel_str} as it requires arguments"
                )
                continue
            try:
                depends_list = depends_func()[0]
            except Exception as e:
                warnings.warn(f"Error calling depends() in {rel_str}: {e}")
                continue

            if not isinstance(depends_list, list) or not all(
                isinstance(item, str) for item in depends_list
            ):
                warnings.warn(
                    f"depends() in {rel_str} did not return a list of strings"
                )
                continue

            for dep in depends_list:
                dep_full = (root / dep).resolve()
                try:
                    dep_rel = dep_full.relative_to(root)
                except ValueError:
                    continue
                dep_rel_str = str(dep_rel)
                if dep_rel_str in workflow_paths:
                    dependencies.add(dep_rel_str)

    # Determine unreferenced workflows
    unreferenced = [wp for wp in workflows if wp not in dependencies]
    return unreferenced


def load_workflow(file_name: str,
                  base_path: str | Path,
                  package='workflows') -> WorkflowType:
    if file_name.startswith('cfg:'):
        return SetConfigWorkflow(file_name[4:])
    base_path = Path(base_path)
    path = Path(file_name)
    module_name = f"{package}.{'.'.join([*path.parts[:-1], path.stem])}"
    spec = spec_from_file_location(module_name, base_path / path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, '__timeout__'):
        module.__timeout__ = None

    if not hasattr(module, 'depends'):
        module.depends = lambda: [[]]

    verify_calibrate_method(module)
    verify_check_method(module)

    return module
