from nwbwidgets.utils.timeseries import (get_timeseries_maxt, get_timeseries_mint,
                                         timeseries_time_to_ind, get_timeseries_in_units,
                                         get_timeseries_tt)
from nwbwidgets.controllers import StartAndDurationController
from nwbwidgets.ophys import OphysImageSeriesWidget, compute_outline
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from ipywidgets import widgets, Layout
from tifffile import imread, TiffFile
from pathlib import Path, PureWindowsPath
import numpy as np


class AllenDashboard(widgets.VBox):
    def __init__(self, nwb):
        super().__init__()
        self.nwb = nwb

        # Start time and duration controller
        self.tmin = get_timeseries_mint(nwb.processing['ophys'].data_interfaces['fluorescence'].roi_response_series['roi_response_series'])
        self.tmax = get_timeseries_maxt(nwb.processing['ophys'].data_interfaces['fluorescence'].roi_response_series['roi_response_series'])
        self.time_window_controller = StartAndDurationController(
            tmin=self.tmin,
            tmax=self.tmax,
            start=0,
            duration=5,
        )

        # Traces
        traces = make_subplots(rows=3, cols=1, row_heights=[0.4, 0.2, 0.4],
                               shared_xaxes=False, vertical_spacing=0.02)

        # Electrophysiology
        self.ecephys_trace = nwb.processing['ecephys'].data_interfaces['filtered_membrane_voltage']
        traces.add_trace(
            go.Scatter(
                x=[0],
                y=[0],
                line={"color": "black", "width": 1},
                mode='lines'
            ),
            row=1, col=1
        )

        # Optophysiology
        self.ophys_trace = nwb.processing['ophys'].data_interfaces['fluorescence'].roi_response_series['roi_response_series']
        traces.add_trace(
            go.Scatter(
                x=[0],
                y=[0],
                line={"color": "black", "width": 1},
                mode='lines'),
            row=3, col=1
        )

        # Layout
        traces.update_layout(
            height=400, width=800, showlegend=False, title=None,
            paper_bgcolor='rgba(0, 0, 0, 0)', plot_bgcolor='rgba(0, 0, 0, 0)',
            margin=dict(l=60, r=200, t=8, b=20)
        )
        traces.update_xaxes(patch={
            'showgrid': False,
            'visible': False,
        })
        traces.update_xaxes(patch={
            'visible': True,
            'showline': True,
            'linecolor': 'rgb(0, 0, 0)',
            'title_text': 'time [s]'},
            row=3, col=1
        )
        traces.update_yaxes(patch={
            'showgrid': False,
            'visible': True,
            'showline': True,
            'linecolor': 'rgb(0, 0, 0)'
        })
        traces.update_yaxes(title_text="Ephys [V]", row=1, col=1)
        traces.update_yaxes(title_text="dF/F", row=3, col=1)
        traces.update_yaxes(patch={
            "title_text": "Spikes",
            "showticklabels": False,
            "ticks": ""},
            row=2, col=1
        )

        self.widget_traces = go.FigureWidget(traces)

        # Two photon imaging
        self.photon_series = OphysImageSeriesWidget(
            imageseries=nwb.acquisition['raw_ophys'],
            pixel_mask=nwb.processing['ophys'].data_interfaces['image_segmentation'].plane_segmentations['plane_segmentation'].pixel_mask[:],
            foreign_time_window_controller=self.time_window_controller,
        )
        self.photon_series.out_fig.update_layout(
            showlegend=False,
            margin=dict(l=10, r=30, t=20, b=30),
            width=300, height=300,
        )

        # Frame controller
        self.frame_controller = widgets.FloatSlider(
            value=0,
            step=1 / self.nwb.acquisition['raw_ophys'].rate,
            min=self.time_window_controller.value[0],
            max=self.time_window_controller.value[1],
            description='Frame: ',
            style={'description_width': '355px'},
            continuous_update=False,
            readout=False,
            orientation='horizontal',
            layout=Layout(width='910px')
        )

        # Add line traces marking Image frame point
        for i in range(3):
            self.widget_traces.add_trace(go.Scatter(
                x=[0, 0], y=[-1000, 1000],
                line={"color": "rgb(86, 117, 153)", "width": 4},
                mode='lines'),
                row=i + 1, col=1
            )

        # Updates frame point
        self.frame_controller.observe(self.update_frame_point)

        # Updates list of valid spike times at each change in time range
        self.time_window_controller.observe(self.updated_time_range)

        # Layout
        hbox_header = widgets.HBox([self.time_window_controller])
        hbox_widgets = widgets.HBox([self.photon_series, self.widget_traces])
        self.children = [hbox_header, self.frame_controller, hbox_widgets]

        self.updated_time_range()
        self.add_mask()

    def update_frame_point(self, change):
        """Updates Image frame and frame point relative position on temporal traces"""
        if isinstance(change['new'], float):
            # Update frame traces position
            self.widget_traces.data[2].x = [change['new'], change['new']]
            self.widget_traces.data[3].x = [change['new'], change['new']]
            self.widget_traces.data[4].x = [change['new'], change['new']]

            # Update image frame
            frame_number = int(change['new'] * self.nwb.acquisition['raw_ophys'].rate)
            file_path = self.nwb.acquisition['raw_ophys'].external_file[0]
            if "\\" in file_path:
                win_path = PureWindowsPath(file_path)
                path_ext_file = Path(win_path)
            else:
                path_ext_file = Path(file_path)
            image = imread(path_ext_file, key=frame_number)
            self.photon_series.out_fig.data[0].z = image

    def updated_time_range(self, change=None):
        """Operations to run whenever time range gets updated"""
        with self.widget_traces.batch_update():
            # Update frame slider
            if self.time_window_controller.value[1] < self.frame_controller.min:
                self.frame_controller.min = self.time_window_controller.value[0]
                self.frame_controller.max = self.time_window_controller.value[1]
            else:
                self.frame_controller.max = self.time_window_controller.value[1]
                self.frame_controller.min = self.time_window_controller.value[0]
            xpoint = round(np.mean(self.time_window_controller.value))
            self.frame_controller.value = xpoint

            # Renew plots
            self.widget_traces.data = [
                self.widget_traces.data[0],  # Ecephys trace
                self.widget_traces.data[1],  # Ophys trace
                self.widget_traces.data[2],  # Frame trace upper panel
                self.widget_traces.data[3],  # Frame trace middle panel
                self.widget_traces.data[4],  # Frame trace lower panel
            ]

            time_window = self.time_window_controller.value

            # Update electrophys trace
            timeseries = self.ecephys_trace
            istart = timeseries_time_to_ind(timeseries, time_window[0])
            istop = timeseries_time_to_ind(timeseries, time_window[1])
            yy, units = get_timeseries_in_units(timeseries, istart, istop)
            xx = get_timeseries_tt(timeseries, istart, istop)
            xrange0, xrange1 = min(xx), max(xx)
            self.widget_traces.data[0].x = xx
            self.widget_traces.data[0].y = list(yy)
            self.widget_traces.update_layout(
                yaxis={"range": [min(yy), max(yy)], "autorange": False},
                xaxis={"range": [xrange0, xrange1], "autorange": False}
            )

            # Update ophys trace
            timeseries = self.ophys_trace
            istart = timeseries_time_to_ind(timeseries, time_window[0])
            istop = timeseries_time_to_ind(timeseries, time_window[1])
            yy, units = get_timeseries_in_units(timeseries, istart, istop)
            xx = get_timeseries_tt(timeseries, istart, istop)
            self.widget_traces.data[1].x = xx
            self.widget_traces.data[1].y = list(yy)
            self.widget_traces.update_layout(
                yaxis3={"range": [min(yy), max(yy)], "autorange": False},
                xaxis3={"range": [xrange0, xrange1], "autorange": False}
            )

            # Update spikes traces
            self.update_spike_traces()
            self.widget_traces.update_layout(
                xaxis2={"range": [xrange0, xrange1], "autorange": False}
            )

    def update_spike_traces(self):
        """Updates list of go.Scatter objects at spike times"""
        self.spike_traces = []
        t_start = self.time_window_controller.value[0]
        t_end = self.time_window_controller.value[1]
        all_spikes = self.nwb.units['spike_times'][0]
        mask = (all_spikes > t_start) & (all_spikes < t_end)
        selected_spikes = all_spikes[mask]
        # Makes a go.Scatter object for each spike in chosen interval
        for spkt in selected_spikes:
            self.widget_traces.add_trace(go.Scatter(
                x=[spkt, spkt],
                y=[-1000, 1000],
                line={"color": "gray", "width": .5},
                mode='lines'),
                row=2, col=1
            )

    def add_mask(self, b=0):
        """Add pixel mask to Image frame"""
        # self.btn_mask_active = not self.btn_mask_active
        # if self.btn_mask_active:
        mask_array = self.nwb.processing['ophys'].data_interfaces['image_segmentation']['plane_segmantation']['pixel_mask'][:][0]
        win_path = PureWindowsPath(self.nwb.acquisition['raw_ophys'].external_file[0])
        path_ext_file = Path(win_path)
        tif = TiffFile(path_ext_file)
        page = tif.pages[0]
        n_y, n_x = page.shape

        mask_matrix = np.zeros((n_y, n_x))
        for px in mask_array:
            mask_matrix[px[1], px[0]] = 1

        x_coords, y_coords = compute_outline(image_mask=mask_matrix, threshold=0.9)

        if len(self.photon_series.out_fig.data) == 1:
            trace = go.Scatter(
                x=x_coords,
                y=y_coords,
                fill='toself',
                mode='lines',
                line={"color": "rgb(219, 59, 59)", "width": 4},
            )
            self.photon_series.out_fig.add_trace(trace)
        else:
            self.photon_series.out_fig.data[1].x = x_coords
            self.photon_series.out_fig.data[1].y = y_coords
        # else:
        #     self.photon_series.out_fig.data[1].x = []
        #     self.photon_series.out_fig.data[1].y = []
