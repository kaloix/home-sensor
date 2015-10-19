# TODO
## Refactor CSV Reading
* import with line number

## HTTP interface
* [18.2. ssl — TLS_SSL wrapper for socket objects — Python 3.4.2 documentation](https://docs.python.org/release/3.4.2/library/ssl.html)
* [Simple HTTPS Server In Python Using Self Signed Certs · Pankaj Malhotra](http://pankajmalhotra.com/Simple-HTTPS-Server-In-Python-Using-Self-Signed-Certs/)

		openssl genrsa -out server.key 4096
		openssl req -new -key server.key -out server.csr
		openssl x509 -req -days 1460 -in server.csr -signkey server.key
			-out server.crt

## Temperature Garden
0. Buy WLAN adapter for *Raspberry Pi 1 Model B Rev. 2.0* ([Conrad](http://www.conrad.de/ce/de/product/993655/Raspberry-Pi-WLAN-Stick-EDIMAX-EW-7811Un))
0. Make temerpature sensor connection robust at *thalgrund* (with jumper wires,
   Lüsterklemmen and dust protection)
0. Place *ridgewood* in Gartenhaus with temperature sensor

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