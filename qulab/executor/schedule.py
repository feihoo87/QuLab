import functools
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from loguru import logger

from . import transform
from .load import WorkflowType, get_dependents
from .storage import (Result, find_result, get_head, renew_result,
                      revoke_result, save_result)


class CalibrationFailedError(Exception):
    pass


def check_state(workflow: WorkflowType, code_path: str | Path,
                state_path: str | Path) -> bool:
    """
    check state should report a pass if and only if the following are satisfied:
    
    1. The cal has had check data or calibrate pass within the timeout period.
    2. The cal has not failed calibrate without resolution.
    3. No dependencies have been recalibrated since the last time check data or calibrate was run on this cal.
    4. All dependencies pass check state.
    """
    logger.debug(f'check_state: "{workflow}"')
    result = find_result(workflow.__workflow_id__, state_path)
    if not result:
        logger.debug(
            f'check_state failed: No history found for "{workflow.__workflow_id__}"'
        )
        return False
    if hasattr(workflow, 'check_state') and callable(workflow.check_state):
        logger.debug(
            f'check_state: "{workflow.__workflow_id__}" has custom check_state method'
        )
        return workflow.check_state(result)
    if workflow.__timeout__ is not None and datetime.now(
    ) > result.checked_time + timedelta(seconds=workflow.__timeout__):
        logger.debug(
            f'check_state failed: "{workflow.__workflow_id__}" has expired')
        return False
    if not result.in_spec:
        logger.debug(
            f'check_state failed: "{workflow.__workflow_id__}" is out of spec')
        return False
    if result.bad_data:
        logger.debug(
            f'check_state failed: "{workflow.__workflow_id__}" has bad data')
        return False
    for n in get_dependents(workflow, code_path):
        r = find_result(n.__workflow_id__, state_path)
        if r is None or r.checked_time > result.checked_time:
            logger.debug(
                f'check_state failed: "{workflow.__workflow_id__}" has outdated dependencies'
            )
            return False
    for n in get_dependents(workflow, code_path):
        if not check_state(n, code_path, state_path):
            logger.debug(
                f'check_state failed: "{workflow.__workflow_id__}" has bad dependencies'
            )
            return False
    return True


def call_analyzer(node, data, history, check=False, plot=False):
    if check:
        result = transform.params_to_result(
            node.check_analyze(*data,
                               history=transform.result_to_params(history)))
        result.fully_calibrated = False
    else:
        result = transform.params_to_result(
            node.analyze(*data, history=transform.result_to_params(history)))
        result.fully_calibrated = True
        if plot:
            call_plot(node, result)
    result.data = data
    return result


@logger.catch()
def call_plot(node, result, check=False):
    if hasattr(node, 'plot') and callable(node.plot):
        state, params, other = transform.result_to_params(result)
        node.plot(state, params, other)


@functools.lru_cache(maxsize=128)
def check_data(workflow: WorkflowType, code_path: str | Path,
               state_path: str | Path, plot: bool, session_id: str) -> Result:
    """
    check data answers two questions:
    Is the parameter associated with this cal in spec,
    and is the cal scan working as expected?
    """
    history = find_result(workflow.__workflow_id__, state_path)

    if history is None:
        logger.debug(f'No history found for "{workflow.__workflow_id__}"')
        result = Result()
        result.in_spec = False
        result.bad_data = False
        return result

    if history.bad_data:
        logger.debug(
            f'History found for "{workflow.__workflow_id__}", but bad data')
        return history
    if not history.in_spec:
        logger.debug(
            f'History found for "{workflow.__workflow_id__}", but out of spec')
        return history

    logger.debug(
        f'History found for "{workflow.__workflow_id__}", but has expired')

    if hasattr(workflow, 'check') and callable(workflow.check) and hasattr(
            workflow, 'check_analyze') and callable(workflow.check_analyze):
        logger.debug(f'Checking "{workflow.__workflow_id__}" with "check" method ...')
        data = workflow.check()
        result = Result()
        result.data = data
        #save_result(workflow.__workflow_id__, result, state_path)

        logger.debug(f'Checked "{workflow.__workflow_id__}" !')
        result = call_analyzer(workflow, data, history, check=True, plot=plot)
        if result.in_spec:
            logger.debug(
                f'"{workflow.__workflow_id__}": checked in spec, renewing result'
            )
            renew_result(workflow.__workflow_id__, state_path)
        else:
            logger.debug(
                f'"{workflow.__workflow_id__}": checked out of spec, revoking result'
            )
            revoke_result(workflow.__workflow_id__, state_path)
    else:
        logger.debug(
            f'Checking "{workflow.__workflow_id__}" with "calibrate" method ...'
        )
        data = workflow.calibrate()
        result = Result()
        result.data = data
        save_result(workflow.__workflow_id__, result, state_path)

        logger.debug(f'Calibrated "{workflow}" !')
        result = call_analyzer(workflow, data, history, check=False, plot=plot)
        save_result(workflow.__workflow_id__, result, state_path,
                    overwrite=True)

    return result


@functools.lru_cache(maxsize=128)
def calibrate(workflow: WorkflowType, code_path: str | Path,
              state_path: str | Path, plot: bool, session_id: str) -> Result:
    history = find_result(workflow.__workflow_id__, state_path)

    logger.debug(f'Calibrating "{workflow.__workflow_id__}" ...')
    data = workflow.calibrate()
    result = Result()
    result.data = data
    save_result(workflow.__workflow_id__, result, state_path)
    logger.debug(f'Calibrated "{workflow.__workflow_id__}" !')
    result = call_analyzer(workflow, data, history, check=False, plot=plot)
    save_result(workflow.__workflow_id__, result, state_path,
                overwrite=True)
    return result


def diagnose(workflow: WorkflowType, code_path: str | Path,
             state_path: str | Path, plot: bool, session_id: str):
    '''
    Returns: True if node or dependent recalibrated.
    '''
    logger.debug(f'diagnose "{workflow.__workflow_id__}"')
    # check_data
    result = check_data(workflow, code_path, state_path, plot, session_id)
    # in spec case
    if result.in_spec:
        logger.debug(
            f'"{workflow.__workflow_id__}": Checked! In spec, no need to diagnose'
        )
        return False
    # bad data case
    recalibrated = []
    if result.bad_data:
        logger.debug(
            f'"{workflow.__workflow_id__}": Bad data, diagnosing dependents')
        recalibrated = [
            diagnose(n, code_path, state_path, plot, session_id)
            for n in get_dependents(workflow, code_path)
        ]
    if not any(recalibrated):
        if result.bad_data:
            raise CalibrationFailedError(
                f'"{workflow.__workflow_id__}": bad data but no dependents recalibrated.'
            )
        logger.debug(
            f'"{workflow.__workflow_id__}": no dependents recalibrated.')
    # calibrate
    if any(recalibrated):
        logger.debug(
            f'recalibrate "{workflow.__workflow_id__}" because some dependents recalibrated.'
        )
    elif not result.in_spec and not result.bad_data:
        logger.debug(
            f'recalibrate "{workflow.__workflow_id__}" because out of spec.')
    elif result.in_spec:
        logger.error(
            f'Never reach: recalibrate "{workflow.__workflow_id__}" because in spec.'
        )
    elif result.bad_data:
        logger.error(
            f'Never reach: recalibrate "{workflow.__workflow_id__}" because bad data.'
        )
    else:
        logger.error(f'Never reach: recalibrate "{workflow.__workflow_id__}"')

    result = calibrate(workflow, code_path, state_path, plot, session_id)
    if result.bad_data or not result.in_spec:
        raise CalibrationFailedError(
            f'"{workflow.__workflow_id__}": All dependents passed, but calibration failed!'
        )
    transform.update_parameters(result)
    return True


@logger.catch(reraise=True)
def maintain(workflow: WorkflowType,
             code_path: str | Path,
             state_path: str | Path,
             session_id: str | None = None,
             run: bool = False,
             plot: bool = False,
             update: bool = True):
    if session_id is None:
        session_id = uuid.uuid4().hex
    logger.debug(f'run "{workflow.__workflow_id__}"'
                 if run else f'maintain "{workflow.__workflow_id__}"')
    # recursive maintain
    for n in get_dependents(workflow, code_path):
        logger.debug(
            f'maintain "{n.__workflow_id__}" because it is depended by "{workflow.__workflow_id__}"'
        )
        maintain(n, code_path, state_path, session_id, run=False, plot=plot)
    else:
        logger.debug(
            f'"{workflow.__workflow_id__}": All dependents maintained')
    # check_state
    if check_state(workflow, code_path, state_path) and not run:
        logger.debug(
            f'"{workflow.__workflow_id__}": In spec, no need to maintain')
        return
    # check_data
    result = check_data(workflow, code_path, state_path, plot, session_id)
    if result.in_spec:
        if not run:
            logger.debug(
                f'"{workflow.__workflow_id__}": In spec, no need to maintain')
            return
    elif result.bad_data:
        logger.debug(
            f'"{workflow.__workflow_id__}": Bad data, diagnosing dependents')
        for n in get_dependents(workflow, code_path):
            logger.debug(
                f'diagnose "{n.__workflow_id__}" because of "{workflow.__workflow_id__}" bad data'
            )
            diagnose(n, code_path, state_path, plot, session_id)
        else:
            logger.debug(
                f'"{workflow.__workflow_id__}": All dependents diagnosed')
    # calibrate
    logger.debug(f'recalibrate "{workflow.__workflow_id__}"')
    result = calibrate(workflow, code_path, state_path, plot, session_id)
    if result.bad_data or not result.in_spec:
        raise CalibrationFailedError(
            f'"{workflow.__workflow_id__}": All dependents passed, but calibration failed!'
        )
    if update:
        transform.update_parameters(result)
    return


@logger.catch(reraise=True)
def run(workflow: WorkflowType,
        code_path: str | Path,
        state_path: str | Path,
        plot: bool = False,
        update: bool = True):
    session_id = uuid.uuid4().hex
    logger.debug(f'run "{workflow.__workflow_id__}" without dependences.')
    result = calibrate(workflow,
                       code_path,
                       state_path,
                       plot,
                       session_id=session_id)
    if result.bad_data or not result.in_spec:
        raise CalibrationFailedError(
            f'"{workflow.__workflow_id__}": All dependents passed, but calibration failed!'
        )
    if update:
        transform.update_parameters(result)
    return
