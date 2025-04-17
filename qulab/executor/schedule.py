import functools
import inspect
import pickle
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from loguru import logger

from .load import WorkflowType, get_dependents
from .storage import (Report, find_report, get_head, get_heads, renew_report,
                      revoke_report, save_item, save_report)
from .transform import current_config, obey_the_oracle, update_parameters

__session_id = None
__session_cache = {}


def set_cache(session_id, key, report: Report):
    global __session_id
    if __session_id is None:
        __session_id = session_id
    if __session_id != session_id:
        __session_cache.clear()
    if report.workflow.startswith('cfg:'):
        __session_cache[key] = report
    else:
        __session_cache[key] = report.base_path, report.path


def get_cache(session_id, key) -> Report:
    from .storage import load_report
    global __session_id
    if __session_id is None or __session_id != session_id:
        return None
    index = __session_cache.get(key, None)
    if index is None:
        return None
    if isinstance(index, tuple):
        base_path, path = index
        return load_report(path, base_path)
    elif isinstance(index, Report):
        return index
    else:
        return None


class CalibrationFailedError(Exception):
    pass


def is_pickleable(obj) -> bool:
    try:
        pickle.dumps(obj)
        return True
    except:
        return False


def veryfy_analyzed_report(report: Report, script: str, method: str):
    if not isinstance(report, Report):
        raise TypeError(f'"{script}" : "{method}" must return a Report object')
    if not is_pickleable(report.parameters):
        raise TypeError(
            f'"{script}" : "{method}" return not pickleable data in .parameters'
        )
    if not is_pickleable(report.other_infomation):
        raise TypeError(
            f'"{script}" : "{method}" return not pickleable data in .other_infomation'
        )


def check_state(workflow: WorkflowType, code_path: str | Path,
                state_path: str | Path, veryfy_source_code: bool) -> bool:
    """
    check state should report a pass if and only if the following are satisfied:
    
    1. The cal has had check data or calibrate pass within the timeout period.
    2. The cal has not failed calibrate without resolution.
    3. No dependencies have been recalibrated since the last time check data or calibrate was run on this cal.
    4. All dependencies pass check state.
    """
    logger.debug(f'check_state: "{workflow.__workflow_id__}"')
    report = find_report(workflow.__workflow_id__, state_path)
    if not report:
        logger.debug(
            f'check_state failed: No history found for "{workflow.__workflow_id__}"'
        )
        return False
    if hasattr(workflow, 'check_state') and callable(workflow.check_state):
        logger.debug(
            f'check_state: "{workflow.__workflow_id__}" has custom check_state method'
        )
        return workflow.check_state(report)
    if datetime.fromtimestamp(workflow.__mtime__) > report.checked_time:
        logger.debug(
            f'check_state failed: "{workflow.__workflow_id__}" has been modified after last calibration'
        )
        return False
    if workflow.__timeout__ is not None and datetime.now(
    ) > report.checked_time + timedelta(seconds=workflow.__timeout__):
        logger.debug(
            f'check_state failed: "{workflow.__workflow_id__}" has expired')
        return False
    if not report.in_spec:
        logger.debug(
            f'check_state failed: "{workflow.__workflow_id__}" is out of spec')
        return False
    if report.bad_data:
        logger.debug(
            f'check_state failed: "{workflow.__workflow_id__}" has bad data')
        return False
    for n in get_dependents(workflow, code_path, veryfy_source_code):
        r = find_report(n.__workflow_id__, state_path)
        if r is None or r.checked_time > report.checked_time:
            logger.debug(
                f'check_state failed: "{workflow.__workflow_id__}" has outdated dependencies'
            )
            return False
    for n in get_dependents(workflow, code_path, veryfy_source_code):
        if not check_state(n, code_path, state_path, veryfy_source_code):
            logger.debug(
                f'check_state failed: "{workflow.__workflow_id__}" has bad dependencies'
            )
            return False
    return True


@logger.catch(reraise=False)
async def call_plot(node: WorkflowType, report: Report, check=False):
    if hasattr(node, 'plot') and callable(node.plot):
        if inspect.iscoroutinefunction(node.plot):
            await node.plot(report, check=check)
        else:
            node.plot(report)


async def call_check(workflow: WorkflowType, session_id: str,
                     state_path: Path):
    report = get_cache(session_id, (workflow.__workflow_id__, 'check'))
    if report is not None:
        logger.debug(f'Cache hit for "{workflow.__workflow_id__}:check"')
        return report

    if inspect.iscoroutinefunction(workflow.check):
        data = await workflow.check()
    else:
        data = workflow.check()
    if not is_pickleable(data):
        raise TypeError(
            f'"{workflow.__workflow_id__}" : "check" return not pickleable data'
        )
    report = Report(workflow=workflow.__workflow_id__,
                    data=data,
                    config_path=current_config(state_path),
                    base_path=state_path,
                    heads=get_heads(state_path),
                    previous_path=get_head(workflow.__workflow_id__,
                                           state_path),
                    script_path=save_item(workflow.__source__, 'items',
                                          state_path))

    save_report(workflow.__workflow_id__, report, state_path)

    set_cache(session_id, (workflow.__workflow_id__, 'check'), report)
    return report


async def call_calibrate(workflow: WorkflowType, session_id: str,
                         state_path: Path):
    report = get_cache(session_id, (workflow.__workflow_id__, 'calibrate'))
    if report is not None:
        logger.debug(f'Cache hit for "{workflow.__workflow_id__}:calibrate"')
        return report

    if inspect.iscoroutinefunction(workflow.calibrate):
        data = await workflow.calibrate()
    else:
        data = workflow.calibrate()
    if not is_pickleable(data):
        raise TypeError(
            f'"{workflow.__workflow_id__}" : "calibrate" return not pickleable data'
        )
    report = Report(workflow=workflow.__workflow_id__,
                    data=data,
                    config_path=current_config(state_path),
                    base_path=state_path,
                    heads=get_heads(state_path),
                    previous_path=get_head(workflow.__workflow_id__,
                                           state_path),
                    script_path=save_item(workflow.__source__, 'items',
                                          state_path))

    save_report(workflow.__workflow_id__, report, state_path)

    set_cache(session_id, (workflow.__workflow_id__, 'calibrate'), report)
    return report


async def call_check_analyzer(node: WorkflowType,
                              report: Report,
                              history: Report | None,
                              state_path: Path,
                              plot=False) -> Report:
    if inspect.iscoroutinefunction(node.check_analyze):
        report = await node.check_analyze(report, history=history)
    else:
        report = node.check_analyze(report, history=history)
    veryfy_analyzed_report(report, node.__workflow_id__, "check_analyze")
    report.fully_calibrated = False
    if report.in_spec:
        logger.debug(
            f'"{node.__workflow_id__}": checked in spec, renewing report')
        if report.previous is not None:
            renew_report(node.__workflow_id__, report.previous, state_path)
        else:
            renew_report(node.__workflow_id__, report, state_path)
    else:
        logger.debug(
            f'"{node.__workflow_id__}": checked out of spec, revoking report')
        if report.previous is not None:
            revoke_report(node.__workflow_id__, report.previous, state_path)
        else:
            revoke_report(node.__workflow_id__, report, state_path)
    return report


async def call_analyzer(node: WorkflowType,
                        report: Report,
                        history: Report | None,
                        state_path: Path,
                        plot=False) -> Report:
    if inspect.iscoroutinefunction(node.analyze):
        report = await node.analyze(report, history=history)
    else:
        report = node.analyze(report, history=history)
    veryfy_analyzed_report(report, node.__workflow_id__, "analyze")
    if hasattr(node, 'oracle') and callable(node.oracle):
        logger.debug(
            f'"{node.__workflow_id__}" has oracle method, calling ...')
        report = await call_oracle(node, report, history)
    report.fully_calibrated = True
    save_report(node.__workflow_id__, report, state_path, overwrite=True)
    if plot:
        await call_plot(node, report)
    return report


async def call_oracle(node: WorkflowType, report: Report,
                      history: Report | None):
    sig = inspect.signature(node.oracle)
    try:
        if 'history' in sig.parameters and 'system_state' in sig.parameters:
            report = node.oracle(report,
                                 history=history,
                                 system_state=get_heads(report.base_path))
        elif 'history' in sig.parameters:
            report = node.oracle(report, history=history)
        elif 'system_state' in sig.parameters:
            report = node.oracle(report,
                                 system_state=get_heads(report.base_path))
        else:
            report = node.oracle(report)
        if inspect.isawaitable(report):
            report = await report
    except Exception as e:
        logger.exception(e)
        report.oracle = {}
        return report
    if not isinstance(report, Report):
        raise TypeError(
            f'"{node.__workflow_id__}" : function "oracle" must return a Report object'
        )
    if not is_pickleable(report.oracle):
        raise TypeError(
            f'"{node.__workflow_id__}" : function "oracle" return not pickleable data'
        )
    return report


async def check_data(workflow: WorkflowType, state_path: str | Path,
                     plot: bool, session_id: str) -> Report:
    """
    check data answers two questions:
    Is the parameter associated with this cal in spec,
    and is the cal scan working as expected?
    """
    history = find_report(workflow.__workflow_id__, state_path)

    if history is None:
        logger.debug(f'No history found for "{workflow.__workflow_id__}"')
        report = Report(workflow=workflow.__workflow_id__,
                        config_path=current_config(state_path),
                        base_path=state_path,
                        heads=get_heads(state_path),
                        previous_path=get_head(workflow.__workflow_id__,
                                               state_path),
                        script_path=save_item(workflow.__source__, 'items',
                                              state_path))
        report.in_spec = False
        report.bad_data = False
        return report

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
        logger.debug(
            f'Checking "{workflow.__workflow_id__}" with "check" method ...')

        report = await call_check(workflow, session_id, state_path)

        logger.debug(f'Checked "{workflow.__workflow_id__}" !')
        report = await call_check_analyzer(workflow,
                                           report,
                                           history,
                                           state_path,
                                           plot=plot)
    else:
        logger.debug(
            f'Checking "{workflow.__workflow_id__}" with "calibrate" method ...'
        )

        report = await call_calibrate(workflow, session_id, state_path)

        logger.debug(f'Calibrated "{workflow.__workflow_id__}" !')
        report = await call_analyzer(workflow,
                                     report,
                                     history,
                                     state_path,
                                     plot=plot)
    return report


async def calibrate(workflow: WorkflowType, state_path: str | Path, plot: bool,
                    session_id: str) -> Report:
    history = find_report(workflow.__workflow_id__, state_path)

    logger.debug(f'Calibrating "{workflow.__workflow_id__}" ...')

    report = await call_calibrate(workflow, session_id, state_path)

    logger.debug(f'Calibrated "{workflow.__workflow_id__}" !')

    report = await call_analyzer(workflow,
                                 report,
                                 history,
                                 state_path,
                                 plot=plot)
    return report


async def diagnose(workflow: WorkflowType, code_path: str | Path,
                   state_path: str | Path, plot: bool, session_id: str,
                   fail_fast: bool, veryfy_source_code: bool):
    '''
    Returns: True if node or dependent recalibrated.
    '''
    logger.debug(f'diagnose "{workflow.__workflow_id__}"')
    # check_data
    report = await check_data(workflow, state_path, plot, session_id)
    # in spec case
    if report.in_spec:
        logger.debug(
            f'"{workflow.__workflow_id__}": Checked! In spec, no need to diagnose'
        )
        return False
    # bad data case
    recalibrated = []
    if report.bad_data:
        logger.debug(
            f'"{workflow.__workflow_id__}": Bad data, diagnosing dependents')
        recalibrated = []
        exceptions = []
        for n in get_dependents(workflow, code_path, veryfy_source_code):
            try:
                flag = await diagnose(n, code_path, state_path, plot,
                                      session_id, fail_fast,
                                      veryfy_source_code)
            except Exception as e:
                if fail_fast:
                    raise e
                exceptions.append(e)
            recalibrated.append(flag)
        if any(exceptions):
            raise exceptions[0]
    if not any(recalibrated):
        if report.bad_data:
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
    elif not report.in_spec and not report.bad_data:
        logger.debug(
            f'recalibrate "{workflow.__workflow_id__}" because out of spec.')
    elif report.in_spec:
        logger.error(
            f'Never reach: recalibrate "{workflow.__workflow_id__}" because in spec.'
        )
    elif report.bad_data:
        logger.error(
            f'Never reach: recalibrate "{workflow.__workflow_id__}" because bad data.'
        )
    else:
        logger.error(f'Never reach: recalibrate "{workflow.__workflow_id__}"')

    report = await calibrate(workflow, state_path, plot, session_id)
    if report.bad_data or not report.in_spec:
        obey_the_oracle(report, state_path)
        raise CalibrationFailedError(
            f'"{workflow.__workflow_id__}": All dependents passed, but calibration failed!'
        )
    update_parameters(report, state_path)
    logger.debug(f'"{workflow.__workflow_id__}": parameters updated')
    return True


@logger.catch(reraise=True)
async def maintain(workflow: WorkflowType,
                   code_path: str | Path,
                   state_path: str | Path,
                   session_id: str | None = None,
                   run: bool = False,
                   plot: bool = False,
                   freeze: bool = False,
                   fail_fast: bool = False,
                   veryfy_source_code: bool = True):
    if session_id is None:
        session_id = uuid.uuid4().hex
    logger.debug(f'run "{workflow.__workflow_id__}"'
                 if run else f'maintain "{workflow.__workflow_id__}"')
    # recursive maintain
    exceptions = []
    for n in get_dependents(workflow, code_path, veryfy_source_code):
        logger.debug(
            f'maintain "{n.__workflow_id__}" because it is depended by "{workflow.__workflow_id__}"'
        )
        try:
            await maintain(n,
                           code_path,
                           state_path,
                           session_id,
                           run=False,
                           plot=plot,
                           freeze=freeze,
                           fail_fast=fail_fast,
                           veryfy_source_code=veryfy_source_code)
        except Exception as e:
            if fail_fast:
                raise e
            exceptions.append(e)
    else:
        logger.debug(
            f'"{workflow.__workflow_id__}": All dependents maintained')
    if any(exceptions):
        raise exceptions[0]
    # check_state
    if check_state(workflow, code_path, state_path,
                   veryfy_source_code) and not run:
        logger.debug(
            f'"{workflow.__workflow_id__}": In spec, no need to maintain')
        return
    # check_data
    report = await check_data(workflow, state_path, plot, session_id)
    if report.in_spec:
        if not run:
            logger.debug(
                f'"{workflow.__workflow_id__}": In spec, no need to maintain')
            return
    elif report.bad_data:
        logger.debug(
            f'"{workflow.__workflow_id__}": Bad data, diagnosing dependents')
        exceptions = []
        for n in get_dependents(workflow, code_path, veryfy_source_code):
            logger.debug(
                f'diagnose "{n.__workflow_id__}" because of "{workflow.__workflow_id__}" bad data'
            )
            try:
                await diagnose(n, code_path, state_path, plot, session_id,
                               fail_fast, veryfy_source_code)
            except Exception as e:
                if fail_fast:
                    raise e
                exceptions.append(e)
        else:
            logger.debug(
                f'"{workflow.__workflow_id__}": All dependents diagnosed')
        if any(exceptions):
            raise exceptions[0]
    # calibrate
    logger.debug(f'recalibrate "{workflow.__workflow_id__}"')
    report = await calibrate(workflow, state_path, plot, session_id)
    if report.bad_data or not report.in_spec:
        if not freeze:
            obey_the_oracle(report, state_path)
        raise CalibrationFailedError(
            f'"{workflow.__workflow_id__}": All dependents passed, but calibration failed!'
        )
    if not freeze:
        update_parameters(report, state_path)
        logger.debug(f'"{workflow.__workflow_id__}": parameters updated')
    else:
        logger.debug(f'"{workflow.__workflow_id__}": parameters freezed')
    return


@logger.catch(reraise=True)
async def run(workflow: WorkflowType,
              code_path: str | Path,
              state_path: str | Path,
              plot: bool = False,
              freeze: bool = False):
    session_id = uuid.uuid4().hex
    logger.debug(f'run "{workflow.__workflow_id__}" without dependences.')
    report = await calibrate(workflow, state_path, plot, session_id=session_id)
    if report.bad_data or not report.in_spec:
        if not freeze:
            obey_the_oracle(report, state_path)
        raise CalibrationFailedError(
            f'"{workflow.__workflow_id__}": All dependents passed, but calibration failed!'
        )
    if not freeze:
        update_parameters(report, state_path)
        logger.debug(f'"{workflow.__workflow_id__}": parameters updated')
    else:
        logger.debug(f'"{workflow.__workflow_id__}": parameters freezed')
    return
