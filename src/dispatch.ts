import { Action, Dispatch } from 'redux'
import { connect } from 'react-redux'
import { State } from './state'
import { addData, pause } from './actions'


function mapStateToProps({ data, isPaused }: State) {
    return {
        data,
        isPaused
    }
}

function mapDispatchToProps(dispatch: Dispatch<Action>) {
    return {
        newData: () => dispatch(addData(Math.random(), Math.random())),
        pause: () => dispatch(pause())
    }
}

export default connect(mapStateToProps, mapDispatchToProps)
