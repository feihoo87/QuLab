import { createStore } from 'redux'
import { initState } from './state'
import reducer from './reducer'

export default createStore(reducer, initState);
