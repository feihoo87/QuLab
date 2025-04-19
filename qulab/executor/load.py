import atexit
import inspect
import os
import pickle
import shutil
import tempfile
import time
import warnings
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from typing import Any

from loguru import logger

from .registry import Registry
from .storage import Report
from .template import (TemplateKeyError, TemplateTypeError, decode_mapping,
                       inject_mapping)


class SetConfigWorkflow():
    __timeout__ = None
    __mtime__ = 0
    __source__ = ''

    def __init__(self, key):
        self.key = key
        self.__workflow_id__ = f"cfg:{self.key}"

    def depends(self):
        return []

    def check_state(self, history: Report) -> bool:
        reg = Registry()
        try:
            return self._equal(history.parameters[self.key], reg.get(self.key))
        except:
            return False

    def calibrate(self):
        reg = Registry()
        try:
            value = reg.get(self.key)
        except:
            value = eval(input(f'"{self.key}": '))
        return value

    def analyze(self, report: Report, history: Report):
        report.state = 'OK'
        report.parameters = {self.key: report.data}
        return report

    def check(self):
        return self.calibrate()

    def check_analyze(self, report: Report, history: Report | None):
        if self.check_state(history):
            report.state = 'OK'
            report.parameters = {self.key: history.data}
        else:
            report.state = 'Outdated'
        return report

    @staticmethod
    def _equal(a, b):
        import numpy as np

        if a is b:
            return True
        try:
            return a == b
        except:
            pass

        if isinstance(a, np.ndarray) and isinstance(b, np.ndarray):
            return a.shape == b.shape and np.all(a == b)

        return False

    def __hash__(self):
        return hash(self.__workflow_id__)


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
            f"Workflow {module.__file__} does not have 'check' function, it will be set to 'calibrate' function"
        )
    else:
        if not can_call_without_args(module.check):
            raise AttributeError(
                f"Workflow {module.__file__} 'check' function should not have any parameters"
            )

        if not hasattr(module, 'check_analyze'):
            raise AttributeError(
                f"Workflow {module.__file__} has 'check' function but does not have 'check_analyze' function"
            )


def verify_dependence_key(workflow: str | tuple[str, dict[str, Any]]
                          | tuple[str, str, dict[str, Any]], base_path: Path):
    if isinstance(workflow, str):
        return
    if not isinstance(workflow, tuple) or len(workflow) not in [2, 3]:
        raise ValueError(f"Invalid workflow: {workflow}")

    if len(workflow) == 2 and isinstance(workflow[1], str):
        file_name, mapping = workflow
        if not Path(file_name).exists():
            raise FileNotFoundError(f"File not found: {file_name}")
    elif len(workflow) == 2 and isinstance(workflow[1], dict):
        template_path, mapping = workflow
        if not (Path(base_path) / template_path).exists():
            raise FileNotFoundError(f"File not found: {template_path}")
    elif len(workflow) == 3:
        template_path, target_path, mapping = workflow
        if not (Path(base_path) / template_path).exists():
            raise FileNotFoundError(f"File not found: {template_path}")
        if not isinstance(target_path, (Path, str)) or target_path == '':
            raise ValueError(f"Invalid target_path: {target_path}")
        if not isinstance(target_path, (Path, str)):
            raise ValueError(f"Invalid target_path: {target_path}")
        if Path(target_path).suffix != '.py':
            raise ValueError(
                f"Invalid target_path: {target_path}. Only .py file is supported"
            )
    else:
        raise ValueError(f"Invalid workflow: {workflow}")

    if not isinstance(mapping, dict):
        raise ValueError(f"Invalid mapping: {mapping}")

    for key, value in mapping.items():
        if not isinstance(key, str):
            raise ValueError(
                f"Invalid key: {key}, should be str type and valid identifier")
        if not key.isidentifier():
            raise ValueError(f"Invalid key: {key}, should be identifier")
        try:
            pickle.dumps(value)
        except Exception as e:
            raise ValueError(
                f"Invalid value: {key}: {value}, should be pickleable") from e
    return


def verify_depends(module: WorkflowType, base_path):
    if not hasattr(module, 'depends'):
        return

    deps = []

    if callable(module.depends):
        if not can_call_without_args(module.depends):
            raise AttributeError(
                f"Workflow {module.__file__} 'depends' function should not have any parameters"
            )
        deps = list(module.depends())
    elif isinstance(module.depends, (list, tuple)):
        deps = module.depends
    else:
        raise AttributeError(
            f"Workflow {module.__file__} 'depends' should be a callable or a list"
        )
    for workflow in deps:
        verify_dependence_key(workflow, base_path)


def verify_entries(module: WorkflowType, base_path):
    if not hasattr(module, 'entries'):
        return

    deps = []

    if callable(module.entries):
        if not can_call_without_args(module.entries):
            raise AttributeError(
                f"Workflow {module.__file__} 'entries' function should not have any parameters"
            )
        deps = list(module.entries())
    elif isinstance(module.entries, (list, tuple)):
        deps = module.entries
    else:
        raise AttributeError(
            f"Workflow {module.__file__} 'entries' should be a callable or a list"
        )
    for workflow in deps:
        verify_dependence_key(workflow, base_path)


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
                            package='workflows',
                            veryfy_source_code: bool = True) -> WorkflowType:
    base_path = Path(base_path)
    path = Path(file_name)
    if not (base_path / path).exists():
        raise FileNotFoundError(f"File not found: {base_path / path}")
    module_name = f"{package}.{'.'.join([*path.parts[:-1], path.stem])}"
    spec = spec_from_file_location(module_name, base_path / path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    module.__mtime__ = (base_path / path).stat().st_mtime
    source_code = (base_path / path).read_text()
    module.__source__ = source_code

    if hasattr(module, 'entries'):
        if veryfy_source_code:
            verify_entries(module, base_path)
        return module

    if not hasattr(module, '__timeout__'):
        module.__timeout__ = None

    if not hasattr(module, 'depends'):
        module.depends = lambda: []

    if veryfy_source_code:
        verify_depends(module, base_path)
        verify_calibrate_method(module)
        verify_check_method(module)

    return module


def load_workflow_from_source_code(workflow_id: str,
                                   source_code: str,
                                   package='workflows') -> WorkflowType:
    workflow_path = Path(workflow_id)
    module_name = f"{package}.{'.'.join([*workflow_path.parts[:-1], workflow_path.stem])}"

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.py').name
    with open(temp_file, 'w') as f:
        f.write(source_code)

    atexit.register(lambda f=temp_file: Path(f).unlink(missing_ok=True))

    spec = spec_from_file_location(module_name, temp_file)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)

    module.__source__ = source_code
    module.__mtime__ = 0
    module.__workflow_id__ = workflow_id

    if not hasattr(module, '__timeout__'):
        module.__timeout__ = None

    if not hasattr(module, 'depends'):
        module.depends = lambda: []

    return module


def _generate_target_file_path(template_path: str | Path, hash_str: str,
                               content: str, base_path: str | Path) -> Path:
    path = Path(template_path)
    if path.stem == 'template':
        path = path.parent / f'tmp{hash_str}.py'
    elif path.stem.endswith('_template'):
        path = path.parent / path.stem.replace('_template',
                                               f'_tmp{hash_str}.py')
    else:
        path = path.parent / f'{path.stem}_tmp{hash_str}.py'

    if 'templates' in path.parts:
        return Path(*['run' if p == 'templates' else p for p in path.parts])
    else:
        return Path('run') / path


def load_workflow_from_template(
        template_path: str,
        mapping: dict[str, str],
        base_path: str | Path,
        target_path: str | None = None,
        package='workflows',
        mtime: float = 0,
        veryfy_source_code: bool = True) -> WorkflowType:
    base_path = Path(base_path)
    path = Path(template_path)

    with open(base_path / path) as f:
        template = f.read()

    mtime = max((base_path / template_path).stat().st_mtime, mtime)

    content, hash_str = inject_mapping(template, mapping, str(path))

    if target_path is None:
        path = _generate_target_file_path(template_path, hash_str, content,
                                          base_path)
    else:
        path = target_path

    file = base_path / path
    if not file.exists() or (file.stat().st_mtime < mtime
                             and file.read_text() != content):
        file.parent.mkdir(parents=True, exist_ok=True)
        with open(file, 'w') as f:
            f.write(content)
    elif file.read_text() != content:
        logger.warning(
            f"`{file}` already exists and is different from the new one generated from template `{template_path}`"
        )

    module = load_workflow_from_file(str(path), base_path, package,
                                     veryfy_source_code)
    module.__mtime__ = max(mtime, module.__mtime__)
    if module.__source__ == content:
        module.__source__ = template, mapping, str(template_path)

    return module


def load_workflow(workflow: str | tuple[str, dict],
                  base_path: str | Path,
                  package='workflows',
                  mtime: float = 0,
                  inject: dict | None = None,
                  veryfy_source_code: bool = True) -> WorkflowType:
    if isinstance(workflow, tuple):
        if len(workflow) == 2:
            file_name, mapping = workflow
            if inject is None:
                w = load_workflow_from_template(file_name, mapping, base_path,
                                                None, package, mtime,
                                                veryfy_source_code)
            else:
                w = load_workflow_from_template(file_name, inject, base_path,
                                                None, package, mtime,
                                                veryfy_source_code)
        elif len(workflow) == 3:
            template_path, target_path, mapping = workflow
            if inject is None:
                w = load_workflow_from_template(template_path, mapping,
                                                base_path, target_path,
                                                package, mtime,
                                                veryfy_source_code)
            else:
                w = load_workflow_from_template(template_path, inject,
                                                base_path, target_path,
                                                package, mtime,
                                                veryfy_source_code)
        else:
            raise ValueError(f"Invalid workflow: {workflow}")
        w.__workflow_id__ = str(Path(w.__file__).relative_to(base_path))
    elif isinstance(workflow, str):
        if workflow.startswith('cfg:'):
            key = workflow[4:]
            w = SetConfigWorkflow(key)
            w.__workflow_id__ = workflow
        else:
            w = load_workflow_from_file(workflow, base_path, package,
                                        veryfy_source_code)
            w.__workflow_id__ = str(Path(w.__file__).relative_to(base_path))
    else:
        raise TypeError(f"Invalid workflow: {workflow}")

    return w


def _load_workflow_list(workflow, lst, code_path, veryfy_source_code):
    ret = []
    for i, n in enumerate(lst):
        try:
            ret.append(
                load_workflow(n,
                              code_path,
                              mtime=workflow.__mtime__,
                              veryfy_source_code=veryfy_source_code))
        except TemplateKeyError as e:
            msg, *_ = e.args
            e.args = (
                f"Workflow {workflow.__workflow_id__} entry {i}: {msg}", )
            raise e
    return ret


def get_dependents(workflow: WorkflowType, code_path: str | Path,
                   veryfy_source_code: bool) -> list[WorkflowType]:
    if callable(getattr(workflow, 'depends', None)):
        if not can_call_without_args(workflow.depends):
            raise AttributeError(
                f'Workflow {workflow.__workflow_id__} "depends" function should not have any parameters'
            )
        return _load_workflow_list(workflow, workflow.depends(), code_path,
                                   veryfy_source_code)
    elif isinstance(getattr(workflow, 'depends', None), (list, tuple)):
        return _load_workflow_list(workflow, workflow.depends, code_path,
                                   veryfy_source_code)
    elif getattr(workflow, 'depends', None) is None:
        return []
    else:
        raise AttributeError(
            f'Workflow {workflow.__workflow_id__} "depends" should be a callable or a list'
        )


def get_entries(workflow: WorkflowType, code_path: str | Path,
                veryfy_source_code: bool) -> list[WorkflowType]:
    if callable(getattr(workflow, 'entries', None)):
        if not can_call_without_args(workflow.entries):
            raise AttributeError(
                f'Workflow {workflow.__workflow_id__} "entries" function should not have any parameters'
            )
        return _load_workflow_list(workflow, workflow.entries(), code_path,
                                   veryfy_source_code)
    elif isinstance(getattr(workflow, 'entries', None), (list, tuple)):
        return _load_workflow_list(workflow, workflow.entries, code_path,
                                   veryfy_source_code)
    elif getattr(workflow, 'entries', None) is None:
        return []
    else:
        raise AttributeError(
            f'Workflow {workflow.__workflow_id__} "entries" should be a callable or a list'
        )


def make_graph(workflow: WorkflowType,
               graph: dict,
               code_path: str | Path,
               veryfy_source_code: bool = True):
    if workflow.__workflow_id__ in graph:
        return graph
    graph[workflow.__workflow_id__] = []

    if hasattr(workflow, 'entries'):
        for w in get_entries(workflow, code_path, veryfy_source_code):
            graph[workflow.__workflow_id__].append(w.__workflow_id__)
            make_graph(w,
                       graph=graph,
                       code_path=code_path,
                       veryfy_source_code=veryfy_source_code)
    elif hasattr(workflow, 'depends'):
        for w in get_dependents(workflow, code_path, veryfy_source_code):
            graph[workflow.__workflow_id__].append(w.__workflow_id__)
            make_graph(w,
                       graph=graph,
                       code_path=code_path,
                       veryfy_source_code=veryfy_source_code)
    if graph[workflow.__workflow_id__] == []:
        del graph[workflow.__workflow_id__]

    return graph
