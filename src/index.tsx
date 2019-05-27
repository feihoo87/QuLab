import * as React from "react";
import * as ReactDOM from "react-dom";
import * as Plotly from 'plotly.js';

import { Provider } from 'react-redux'
import { Plot } from './components/Plot'
import store from './store'
import connect from './dispatch'

interface AppProps {
    data?: {
        x: Array<number>,
        y: Array<number>,
    },
    isPaused?: boolean,
    newData?: () => void,
    pause?: () => void
}

class App extends React.Component<AppProps> {
    timerID: number;

    constructor(props: AppProps) {
        super(props)
        this.update = this.update.bind(this)
    }

    componentDidMount() {
        this.timerID = setInterval(
            () => this.update(),
            1000
        );
    }

    componentWillUnmount() {
        clearInterval(this.timerID);
    }

    update() {
        if (!this.props.isPaused) {
            this.props.newData()
        }
    }

    render() {
        let plotData: Plotly.PlotData[] = [
            {
                x: this.props.data.x,
                y: this.props.data.y,
                type: 'scatter',
                mode: 'lines+markers',
                marker: { color: 'red' },
            } as Plotly.PlotData,
        ];

        let layout: Partial<Plotly.Layout> = {
            width: 800,
            height: 600,
            title: 'A Fancy Plot'
        }

        return (
            <div>
                <Plot id="testplot" data={plotData} layout={layout} />
                <button onClick={this.props.pause}>
                    {this.props.isPaused ? 'Continue' : 'Pause'}
                </button>
            </div>
        )
    }
}

const AppContainer = connect(App)

// ========================================

ReactDOM.render(
    <Provider store={store}>
        <AppContainer />
    </Provider>,
    document.getElementById('example')
);
