# TODO
## Disconnect Bug
### Symtoms
1. ridewood has WLAN problems (it's raining)
2. thalgrund connections time out
3. server blocks at *shutdown monitor server*
4. after rebooting ridgewood, no more connection
5. after restarting the server, thalgrund sends again

### Thoughts
* Check git changes on time of first occurrance
* Full RAM on FritzBox 7270,
  [downgrade OS](http://avm.de/service/fritzbox/fritzbox-7270/wissensdatenbank/publication/show/1394_FRITZ-Box-wird-langsam-und-traege/)

## General
* Shorten allowed downtime (depended on sensor.json?)
* remove numpy modules in ridgewood
* Make temerpature sensor connection robust at *thalgrund*

## HTML 5 Plots
* [Highstock demos | Highcharts](http://www.highcharts.com/stock/demo)
  – looks good, CC-BY-NC license
* [Dygraphs Gallery](http://dygraphs.com/gallery/#g/range-selector) – MIT
  license, zoom, range selector
* [dc.js - Dimensional Charting Javascript Library](http://dc-js.github.io/dc.js/)
  – nice connections between graphs, Apache license
* [Line Chart With View Finder - NVD3](http://nvd3.org/examples/lineWithFocus.html)
  – Open Source, it's ok.
* Use scrollable `<div>` in HTML
* [Flot Examples: Visitors](http://www.flotcharts.org/flot/examples/visitors/index.html) – No scrolling
* [SIMILE Widgets | Timeplot](http://www.simile-widgets.org/timeplot/) – bsd,
  timeplot not zoomable – OTHERWISE LOOKS GREAT
* [jqPlot Charts and Graphs for jQuery](http://www.jqplot.com/)
	* [Zoom Proxy - Control one plot from another](http://www.jqplot.com/deploy/dist/examples/zoomProxy.html) – No scrolling
* [flotr2](http://humblesoftware.com/flotr2/#!mouse-drag) – bad navigation
* [D3.js - Data-Driven Documents](http://d3js.org/) – No scrolling
* [Beautiful HTML5 JavaScript Charts | CanvasJS](http://canvasjs.com/) - No.
* [Chart.js | Open source HTML5 Charts for your website](http://www.chartjs.org/)
  – few features
* [http://xaviershay.github.io/tufte-graph/index.html](http://xaviershay.github.io/tufte-graph/index.html)
  – only bar charts, but great layout integration
* [MPLD3 — Bringing Matplotlib to the Browser](http://mpld3.github.io/) – young
  project
* [Raphaël—JavaScript Library](http://raphaeljs.com/) – abondoned
* [Javascript library for drawing Graphs over Timelines (zoomable and selectable) - Stack Overflow](http://stackoverflow.com/questions/1890434/javascript-library-for-drawing-graphs-over-timelines-zoomable-and-selectable) – overview of libraries