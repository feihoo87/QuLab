import * as React from 'react';
import * as Plotly from 'plotly.js';


export interface PlotProps {
  id: string,
  data: Plotly.PlotData[],
  layout: Partial<Plotly.Layout>
}

export class Plot extends React.Component<PlotProps, {}> {
  el: HTMLElement;

  constructor(props: PlotProps) {
    super(props)
    this.getRef = this.getRef.bind(this);
  }

  getRef(el: HTMLElement) {
    this.el = el;
  }

  componentDidMount() {
    Plotly.newPlot(this.el, this.props.data, this.props.layout);
  }

  componentDidUpdate() {
    Plotly.react(this.el, this.props.data, this.props.layout);
  }

  render() {
    return <div id={this.props.id} ref={this.getRef}></div>
  }
}

