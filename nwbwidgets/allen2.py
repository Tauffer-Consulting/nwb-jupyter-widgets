from ipywidgets import widgets
# from nwbwidgets.utils.timeseries import get_timeseries_maxt, get_timeseries_mint
from .controllers import StartAndDurationController
import plotly.graph_objects as go
from .timeseries import SingleTracePlotlyWidget
from .image import ImageSeriesWidget


class AllenDashboard(widgets.VBox):
    def __init__(self, nwb):
        super().__init__()
        self.nwb = nwb

        # self.tmin = get_timeseries_mint(time_series)
        # self.tmax = get_timeseries_maxt(time_series)
        self.show_spikes = False
        self.btn_spike_times = widgets.Button(description='Show spike times', button_style='')
        self.btn_spike_times.on_click(self.spikes_viewer)

        # Start time and duration controller
        self.time_window_controller = StartAndDurationController(
            tmin=0,
            tmax=120,
            start=0,
            duration=5
        )

        # Electrophys single trace
        self.electrical = SingleTracePlotlyWidget(
            timeseries=nwb.processing['ecephys'].data_interfaces['filtered_membrane_voltage'],
            foreign_time_window_controller=self.time_window_controller,
            foreign_group_and_sort_controller=None,
            neurodata_vis_spec=None
        )
        self.electrical.out_fig.update_layout(
            title=None,
            showlegend=False,
            xaxis_title=None,
            width=600,
            height=230,
            margin=dict(l=0, r=8, t=8, b=8),
            # yaxis={"position": 0, "anchor": "free"},
            yaxis={"range": [min(self.electrical.out_fig.data[0].y), max(self.electrical.out_fig.data[0].y)],
                   "autorange": False},
            xaxis={"showticklabels": False, "ticks": ""}
        )
        # Fluorescence single trace
        self.fluorescence = SingleTracePlotlyWidget(
            timeseries=nwb.processing['ophys'].data_interfaces['fluorescence'].roi_response_series['roi_response_series'],
            foreign_time_window_controller=self.time_window_controller,
        )

        self.output_box = widgets.VBox([self.time_window_controller, self.fluorescence, self.electrical])

        self.children = [hbox_header, hbox_widgets]

        self.update_spike_traces()

    def update_frame_point(self, change):
        """Updates Image frame and frame point relative position on temporal traces"""
        if isinstance(change['new'], int):
            self.electrical.out_fig.data[1].x = [change['new'], change['new']]
            self.fluorescence.out_fig.data[1].x = [change['new'], change['new']]

    def updated_time_range(self, change=None):
        """Operations to run whenever time range gets updated"""
        self.update_spike_traces()
        self.show_spikes = False
        self.btn_spike_times.description = 'Show spike times'
        self.fluorescence.out_fig.data = [self.fluorescence.out_fig.data[0]]
        self.electrical.out_fig.data = [self.electrical.out_fig.data[0]]

    def spikes_viewer(self, b=None):
        self.show_spikes = not self.show_spikes
        if self.show_spikes:
            self.btn_spike_times.description = 'Hide spike times'
            for spike_trace in self.spike_traces:
                self.fluorescence.out_fig.add_trace(spike_trace)
                # self.electrical.out_fig.add_trace(spike_trace)
        else:
            self.btn_lines.description = 'Disable spike times'
