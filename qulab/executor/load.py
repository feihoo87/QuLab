import hashlib
import inspect
import pickle
import re
import string
import warnings
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType

from loguru import logger

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


def is_template(path: str | Path) -> bool:
    path = Path(path)
    if path.name == 'template.py':
        return True
    if path.name.endswith('_template.py'):
        return True
    if 'templates' in path.parts:
        return True
    return False


def find_unreferenced_workflows(path: str) -> list[str]:
    root = Path(path).resolve()
    workflows = []
    workflow_paths: set[str] = set()

    # Collect all workflow modules
    for file_path in root.rglob("*.py"):
        if file_path.name == "__init__.py":
            continue
        if is_template(file_path):
            continue
        try:
            rel_path = file_path.relative_to(root)
        except ValueError:
            continue

        module = load_workflow_from_file(str(rel_path), root)

        if is_workflow(module):
            rel_str = str(rel_path)
            workflows.append(rel_str)
            workflow_paths.add(rel_str)

    dependencies: set[str] = set()

    # Check dependencies for each workflow module
    for rel_str in workflows:
        module = load_workflow_from_file(rel_str, root)

        depends_func = getattr(module, "depends", None)
        if depends_func and callable(depends_func):
            if not can_call_without_args(depends_func):
                warnings.warn(
                    f"Skipping depends() in {rel_str} as it requires arguments"
                )
                continue
            try:
                depends_list = [
                    n.__workflow_id__ for n in get_dependents(module, root)
                ]
            except Exception as e:
                warnings.warn(f"Error calling depends() in {rel_str}: {e}")
                continue

            if not isinstance(depends_list, list) or not all(
                    isinstance(item, str) for item in depends_list):
                warnings.warn(
                    f"depends() in {rel_str} did not return a list of strings")
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


def load_workflow_from_file(file_name: str,
                            base_path: str | Path,
                            package='workflows') -> WorkflowType:
    base_path = Path(base_path)
    path = Path(file_name)
    module_name = f"{package}.{'.'.join([*path.parts[:-1], path.stem])}"
    spec = spec_from_file_location(module_name, base_path / path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)

    if hasattr(module, 'entries'):
        return module

    if not hasattr(module, '__timeout__'):
        module.__timeout__ = None

    if not hasattr(module, 'depends'):
        module.depends = lambda: [[]]

    verify_calibrate_method(module)
    verify_check_method(module)

    return module


def load_workflow_from_template(template_path: str,
                                mappping: dict[str, str],
                                base_path: str | Path,
                                target_path: str | None = None,
                                package='workflows') -> WorkflowType:
    base_path = Path(base_path)
    path = Path(template_path)

    with open(base_path / path) as f:
        content = f.read()

    def replace(text):
        """
        将给定文本中的所有 _D_("var") 替换为 ${var}。
        
        Args:
            text (str): 包含 _D_ 调用的字符串。
        
        Returns:
            str: 已经替换的新字符串。
        """
        pattern = re.compile(r'_D_\s*\(\s*(["\'])(\w+)\1\s*\)')
        replacement = r'${\2}'
        new_text = re.sub(pattern, replacement, text)
        return new_text

    template = string.Template(replace(content))
    content = template.substitute(mappping)

    hash_str = hashlib.md5(pickle.dumps(mappping)).hexdigest()[:8]
    if target_path is None:
        if path.stem == 'template':
            path = path.parent / f'tmp{hash_str}.py'
        elif path.stem.endswith('_template'):
            path = path.parent / path.stem.replace('_template',
                                                   f'_tmp{hash_str}.py')
        else:
            path = path.parent / f'{path.stem}_tmp{hash_str}.py'
    else:
        path = target_path

    file = base_path / path
    if not file.exists():
        file.parent.mkdir(parents=True, exist_ok=True)
        with open(file, 'w') as f:
            f.write(content)
    else:
        if file.stat().st_mtime < Path(template_path).stat().st_mtime:
            with open(file, 'w') as f:
                f.write(content)
        else:
            if file.read_text() != content:
                logger.warning(
                    f"`{file}` already exists and is different from the new one generated from template `{template_path}`"
                )

    module = load_workflow_from_file(str(path), base_path, package)

    return module


def load_workflow(workflow: str | tuple[str, dict],
                  base_path: str | Path,
                  package='workflows') -> WorkflowType:
    if isinstance(workflow, tuple):
        if len(workflow) == 2:
            file_name, mapping = workflow
            w = load_workflow_from_template(file_name, mapping, base_path,
                                            None, package)
        elif len(workflow) == 3:
            template_path, target_path, mapping = workflow
            w = load_workflow_from_template(template_path, mapping, base_path,
                                            target_path, package)
        else:
            raise ValueError(f"Invalid workflow: {workflow}")
        w.__workflow_id__ = str(Path(w.__file__).relative_to(base_path))
    elif isinstance(workflow, str):
        if workflow.startswith('cfg:'):
            key = workflow[4:]
            w = SetConfigWorkflow(key)
            w.__workflow_id__ = workflow
        else:
            w = load_workflow_from_file(workflow, base_path, package)
            w.__workflow_id__ = str(Path(w.__file__).relative_to(base_path))
    else:
        raise TypeError(f"Invalid workflow: {workflow}")

    return w


def get_dependents(workflow: WorkflowType,
                   code_path: str | Path) -> list[WorkflowType]:
    return [load_workflow(n, code_path) for n in workflow.depends()[0]]


def get_entries(workflow: WorkflowType, code_path: str | Path) -> WorkflowType:
    return [load_workflow(n, code_path) for n in workflow.entries()]
