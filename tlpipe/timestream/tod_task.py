"""Base pipeline tasks for time ordered data opteration.

Inheritance diagram
-------------------

.. inheritance-diagram:: tlpipe.pipeline.pipeline.TaskBase tlpipe.pipeline.pipeline.OneAndOne TaskTimestream
   :parts: 2

"""

import h5py
from timestream_common import TimestreamCommon
from raw_timestream import RawTimestream
from timestream import Timestream
from tlpipe.utils.path_util import input_path, output_path
from tlpipe.pipeline.pipeline import OneAndOne


class TaskTimestream(OneAndOne):
    """Task that provides raw timestream or timestream IO and data selection operations.

    Provides the methods `read_input`, `read_output` and `write_output` for
    raw timestream or timestream data.

    This is usually used as a direct base class as those tasks that operates on
    timestream data (can be data held in both
    :class:`~tlpipe.timestream.raw_timestream.RawTimestream` and
    :class:`~tlpipe.timestream.timestream.Timestream`), which can determine which
    data container the data is being held from the *input* or from data stored in
    the input data files.

    """

    _Tod_class = TimestreamCommon

    params_init = {
                    'mode': 'r',
                    'start': 0,
                    'stop': None,
                    'dist_axis': 0,
                    'exclude': [],
                    'check_status': True,
                    'libver': 'latest',
                    'time_select': (0, None),
                    'freq_select': (0, None),
                    'pol_select': (0, None), # only useful for ts
                    'feed_select': (0, None),
                    'corr': 'all',
                    'show_info': False,
                    'tag_input_iter': True, # tag current iteration to input file path
                    'tag_output_iter': True, # tag current iteration to output file path
                  }

    prefix = 'tt_'

    def read_process_write(self, tod):
        """Reads input, executes any processing and writes output."""

        # determine if rt or ts from the input tod, and set the correct _Tod_class
        if self._no_input:
            if not tod is None:
                # This should never happen.  Just here to catch bugs.
                raise RuntimeError("Somehow `input` was set.")
        else:
            # read from files
            if tod is None:
                if self.input_files is None or len(self.input_files) == 0:
                    if mpiutil.rank0:
                        msg = 'No file to read from, will stop then...'
                        logger.info(msg)
                    self.stop_iteration(True)
                    return None
                tag_input_iter = self.params['tag_input_iter']
                if self.iterable and tag_input_iter:
                    input_files = input_path(self.input_files, iteration=self.iteration)
                else:
                    input_files = self.input_files
                # see 'vis' dataset from the first input file
                with h5py.File(input_files[0], 'r') as f:
                    vis_shp = f['vis'].shape
                if len(vis_shp) == 3:
                    self._Tod_class = RawTimestream
                elif len(vis_shp) == 4:
                    self._Tod_class = Timestream
                else:
                    raise RuntimeError('Something wrong happened, dimension of vis data != 3 or 4')
            # from arg
            else:
                if isinstance(tod, RawTimestream):
                    self._Tod_class = RawTimestream
                elif isinstance(tod, Timestream):
                    self._Tod_class = Timestream
                else:
                    raise ValueError('Invaid input %s, need either a RawTimestream or Timestream object' % tod)
                tod = self.subset_select(tod)

        return super(TaskTimestream, self).read_process_write(tod)

    def read_input(self):
        """Method for reading time ordered data input."""

        mode = self.params['mode']
        start = self.params['start']
        stop = self.params['stop']
        dist_axis = self.params['dist_axis']
        tag_input_iter = self.params['tag_input_iter']

        if self.iterable and tag_input_iter:
            input_files = input_path(self.input_files, iteration=self.iteration)
        else:
            input_files = self.input_files
        tod = self._Tod_class(input_files, mode, start, stop, dist_axis)

        tod = self.data_select(tod)

        tod.load_all()

        return tod

    def data_select(self, tod):
        """Data select."""
        tod.time_select(self.params['time_select'])
        tod.frequency_select(self.params['freq_select'])
        if self._Tod_class == Timestream:
            tod.polarization_select(self.params['pol_select'])
        tod.feed_select(self.params['feed_select'], self.params['corr'])

        return tod

    def subset_select(self, tod):
        """Data subset select."""
        tod.subset_time_select(self.params['time_select'])
        tod.subset_frequency_select(self.params['freq_select'])
        if self._Tod_class == Timestream:
            tod.subset_polarization_select(self.params['pol_select'])
        tod.subset_feed_select(self.params['feed_select'], self.params['corr'])

        return tod

    def copy_input(self, tod):
        """Return a copy of tod, so the original tod would not be changed."""
        return tod.copy()

    def process(self, tod):

        tod.add_history(self.history)

        if self.params['show_info']:
            tod.info()

        return tod

    def write_output(self, output):
        """Method for writing time ordered data output. """

        exclude = self.params['exclude']
        check_status = self.params['check_status']
        libver = self.params['libver']
        tag_output_iter = self.params['tag_output_iter']

        if self.iterable and tag_output_iter:
            output_files = output_path(self.output_files, relative=False, iteration=self.iteration)
        else:
            output_files = self.output_files
        output.to_files(output_files, exclude, check_status, libver)
