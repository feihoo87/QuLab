export interface State {
    data: {
        x: Array<number>,
        y: Array<number>
    },
    isPaused: boolean
}

export const initState: State = {
    data: { x: [0], y: [0] },
    isPaused: false
}
