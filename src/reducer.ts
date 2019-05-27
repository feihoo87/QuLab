import { State, initState } from './state'
import { AddData, Pause } from './actions'
import { combineReducers, Action, Reducer } from 'redux'

const data = (state: typeof initState.data, action: AddData) => {
    if (!state)
        return initState.data
    if (!action.x)
        return state
    let x = state.x;
    let y = state.y;
    return {
        x: x.concat([x[x.length - 1] + action.x]),
        y: y.concat([action.y])
    }
}

const isPaused = (state: typeof initState.isPaused, action: Pause) => {
    if (state === undefined)
        return initState.isPaused
    if (action.type === 'PAUSE')
        return !state
    else
        return state
}

export default combineReducers<State>({
    data: data, isPaused: isPaused
}) as Reducer<State, Action>
