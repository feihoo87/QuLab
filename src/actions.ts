import { Action } from 'redux'

// Actions

export interface AddData extends Action {
    type: 'ADD_DATA',
    x: number,
    y: number
}

export interface Pause extends Action {
    type: 'PAUSE'
}

// Action creators

export function addData(x: number, y: number): AddData {
    return {
        type: 'ADD_DATA',
        x: x,
        y: y
    }
}

export function pause(): Pause {
    return {
        type: 'PAUSE'
    }
}
