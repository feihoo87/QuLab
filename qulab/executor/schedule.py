import functools
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from loguru import logger

from . import transform
from .load import load_workflow
from .storage import (Result, find_result, renew_result, revoke_result,
                      save_result)


class CalibrationFailedError(Exception):
    pass


def check_state(workflow: str, code_path: str | Path,
                state_path: str | Path) -> bool:
    """
    check state should report a pass if and only if the following are satisfied:
    
    1. The cal has had check data or calibrate pass within the timeout period.
    2. The cal has not failed calibrate without resolution.
    3. No dependencies have been recalibrated since the last time check data or calibrate was run on this cal.
    4. All dependencies pass check state.
    """
    logger.debug(f'check_state: "{workflow}"')
    result = find_result(workflow, state_path)
    if not result:
        logger.debug(f'check_state failed: No history found for "{workflow}"')
        return False
    node = load_workflow(workflow, code_path)
    if hasattr(node, 'check_state') and callable(node.check_state):
        logger.debug(
            f'check_state: "{workflow}" has custom check_state method')
        return node.check_state(result)
    if node.__timeout__ is not None and datetime.now(
    ) > result.checked_time + timedelta(seconds=node.__timeout__):
        logger.debug(f'check_state failed: "{workflow}" has expired')
        return False
    if not result.in_spec:
        logger.debug(f'check_state failed: "{workflow}" is out of spec')
        return False
    if result.bad_data:
        logger.debug(f'check_state failed: "{workflow}" has bad data')
        return False
    for n in get_dependents(workflow, code_path):
        r = find_result(n, state_path)
        if r is None or r.checked_time > result.checked_time:
            logger.debug(
                f'check_state failed: "{workflow}" has outdated dependencies')
            return False
    for n in get_dependents(workflow, code_path):
        if not check_state(n, code_path, state_path):
            logger.debug(
                f'check_state failed: "{workflow}" has bad dependencies')
            return False
    return True


@functools.lru_cache(maxsize=128)
def check_data(workflow: str, code_path: str | Path, state_path: str | Path,
               session_id: str) -> Result:
    """
    check data answers two questions:
    Is the parameter associated with this cal in spec,
    and is the cal scan working as expected?
    """
    node = load_workflow(workflow, code_path)
    history = find_result(workflow, state_path)

    if history is None:
        logger.debug(f'No history found for "{workflow}"')
        result = Result()
        result.in_spec = False
        result.bad_data = False
        return result

    if history.bad_data:
        logger.debug(f'History found for "{workflow}", but bad data')
        return history
    if not history.in_spec:
        logger.debug(f'History found for "{workflow}", but out of spec')
        return history

    logger.debug(f'History found for "{workflow}", but has expired')

    if hasattr(node, 'check') and callable(node.check) and hasattr(
            node, 'check_analyze') and callable(node.check_analyze):
        logger.debug(f'Checking "{workflow}" with "check" method ...')
        data = node.check()
        logger.debug(f'Checked "{workflow}" !')
        result = transform.params_to_result(
            node.check_analyze(*data,
                               history=transform.result_to_params(history)))
        result.data = data
        if result.in_spec:
            logger.debug(f'"{workflow}": checked in spec, renewing result')
            renew_result(workflow, state_path)
        else:
            logger.debug(f'"{workflow}": checked out of spec, revoking result')
            revoke_result(workflow, state_path)
    else:
        logger.debug(f'Checking "{workflow}" with "calibrate" method ...')
        data = node.calibrate()
        logger.debug(f'Calibrated "{workflow}" !')
        result = transform.params_to_result(
            node.analyze(*data, history=transform.result_to_params(history)))
        result.data = data
        result.fully_calibrated = True
        save_result(workflow, result, state_path)

    return result


@functools.lru_cache(maxsize=128)
def calibrate(workflow, code_path: str | Path, state_path: str | Path,
              session_id: str) -> Result:
    result = Result()
    node = load_workflow(workflow, code_path)
    history = find_result(workflow, state_path)

    logger.debug(f'Calibrating "{workflow}" ...')
    data = node.calibrate()
    logger.debug(f'Calibrated "{workflow}" !')
    result = transform.params_to_result(
        node.analyze(*data, history=transform.result_to_params(history)))
    result.data = data
    result.fully_calibrated = True
    save_result(workflow, result, state_path)
    return result


def diagnose(node, code_path: str | Path, state_path: str | Path,
             session_id: str):
    '''
    Returns: True if node or dependent recalibrated.
    '''
    logger.debug(f'diagnose "{node}"')
    # check_data
    result = check_data(node, code_path, state_path, session_id)
    # in spec case
    if result.in_spec:
        return False
    # bad data case
    recalibrated = []
    if result.bad_data:
        recalibrated = [
            diagnose(n, code_path, state_path, session_id)
            for n in get_dependents(node, code_path)
        ]
    if not any(recalibrated):
        return False
    # calibrate
    if result.fully_calibrated and result.in_spec:
        pass
    else:
        logger.debug(
            f'recalibrate "{node}" because some dependents recalibrated')
        result = calibrate(node, code_path, state_path, session_id)
    if result.bad_data or not result.in_spec:
        raise CalibrationFailedError(
            f'"{node}": All dependents passed, but calibration failed!')
    transform.update_parameters(result)
    return True


def get_dependents(workflow: str, code_path: str | Path) -> list[str]:
    return [n for n in load_workflow(workflow, code_path).depends()[0]]


#@logger.catch(reraise=True)
def maintain(node,
             code_path: str | Path,
             state_path: str | Path,
             session_id: str | None = None,
             run: bool = False):
    if session_id is None:
        session_id = uuid.uuid4().hex
    logger.debug(f'run "{node}"' if run else f'maintain "{node}"')
    # recursive maintain
    for n in get_dependents(node, code_path):
        logger.debug(f'maintain "{n}" because it is depended by "{node}"')
        maintain(n, code_path, state_path, session_id)
    else:
        logger.debug(f'"{node}": All dependents maintained')
    # check_state
    if check_state(node, code_path, state_path) and not run:
        logger.debug(f'"{node}": In spec, no need to maintain')
        return
    # check_data
    result = check_data(node, code_path, state_path, session_id)
    if result.in_spec:
        if not run:
            logger.debug(f'"{node}": In spec, no need to maintain')
            return
    elif result.bad_data:
        logger.debug(f'"{node}": Bad data, diagnosing dependents')
        for n in get_dependents(node, code_path):
            logger.debug(f'diagnose "{n}" because of "{node}" bad data')
            diagnose(n, code_path, state_path, session_id)
        else:
            logger.debug(f'"{node}": All dependents diagnosed')
    # calibrate
    logger.debug(f'recalibrate "{node}"')
    result = calibrate(node, code_path, state_path, session_id)
    if result.bad_data or not result.in_spec:
        raise CalibrationFailedError(
            f'"{node}": All dependents passed, but calibration failed!')
    transform.update_parameters(result)
    return


def run(node, code_path: str | Path,
             state_path: str | Path):
    logger.debug(f'run "{node}" without dependences.')
    result = calibrate(node, code_path, state_path)
    if result.bad_data or not result.in_spec:
        raise CalibrationFailedError(
            f'"{node}": All dependents passed, but calibration failed!')
    transform.update_parameters(result)
    return
