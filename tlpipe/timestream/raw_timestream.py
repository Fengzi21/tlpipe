"""Container class for the raw timestream data.


Inheritance diagram
-------------------

.. inheritance-diagram:: tlpipe.timestream.container.BasicTod tlpipe.timestream.timestream_common.TimestreamCommon RawTimestream tlpipe.timestream.timestream.Timestream
   :parts: 2

"""

import itertools
import numpy as np
import timestream_common
import timestream
from caput import mpiarray
from caput import memh5


class RawTimestream(timestream_common.TimestreamCommon):
    """Container class for the raw timestream data.

    The raw timestream data are raw visibilities (the main data) and other data
    and meta data saved in HDF5 files which are recorded from the correlator.

    Parameters
    ----------
    Same as :class:`container.BasicTod`.

    """

    _main_data_name_ = 'vis'
    _main_data_axes_ = ('time', 'frequency', 'baseline')
    _main_axes_ordered_datasets_ = { 'vis': (0, 1, 2),
                                     'vis_mask': (0, 1, 2),
                                     'sec1970': (0,),
                                     'jul_date': (0,),
                                     'freq': (1,),
                                     'blorder': (2,),
                                   }
    _time_ordered_datasets_ = {'weather': (0,)}
    _time_ordered_attrs_ = {'obstime', 'sec1970'}
    _feed_ordered_datasets_ = { 'antpointing': (None, 0),
                                'feedno': (0,),
                                'channo': (0,),
                                'feedpos': (0,),
                                'polerr': (0,),
                              }


    _channel_select = None

    # def channel_select(self, value=(0, None), corr='all'):
    #     """Select data to be loaded from inputs files corresponding to the specified channels.

    #     Parameters
    #     ----------
    #     value : tuple or list, optional
    #         If a tuple, which will be created as a slice(start, stop, step) object,
    #         so it can have one to three elements (integers or None); if a list,
    #         channel No. in this list will be selected. Default (0, None) select all.
    #     corr : 'all', 'auto' or 'cross', optional
    #         Correlation type. 'auto' for auto-correlations, 'cross' for
    #         cross-correlations, 'all' for all correlations. Default 'all'.

    #     """
    #     # get channo info from the first input file
    #     channo = self.infiles[0]['channo'][:]
    #     channo1d = np.sort(channo.flatten())

    #     if isinstance(value, tuple):
    #         channels = channo1d[slice(*value)]
    #     elif isinstance(value, list):
    #         channels = np.intersect1d(channo1d, value)
    #     else:
    #         raise ValueError('Unsupported data selection %s' % value)

    #     nchan = len(channels)
    #     # use set for easy comparison
    #     if corr == 'auto':
    #         channel_pairs = [ {channels[i]} for i in xrange(nchan) ]
    #     elif corr == 'cross':
    #         channel_pairs = [ {channels[i], channels[j]} for i in xrange(nchan) for j in xrange(i+1, nchan) ]
    #     elif corr == 'all':
    #         channel_pairs = [ {channels[i], channels[j]} for i in xrange(nchan) for j in xrange(i, nchan) ]
    #     else:
    #         raise ValueError('Unknown correlation type %s' % corr)

    #     # get blorder info from the first input file
    #     blorder = self.infiles[0]['blorder']
    #     blorder = [ set(bl) for bl in blorder ]

    #     # channel pair indices
    #     indices = { blorder.index(chp) for chp in channel_pairs }
    #     indices = sorted(list(indices))

    #     self.data_select('baseline', indices)

    def feed_select(self, value=(0, None), corr='all'):
        """Select data to be loaded from inputs files corresponding to the specified feeds.

        Parameters
        ----------
        value : tuple or list, optional
            If a tuple, which will be created as a slice(start, stop, step) object,
            so it can have one to three elements (integers or None); if a list,
            feed No. in this list will be selected. Default (0, None) select all.
        corr : 'all', 'auto' or 'cross', optional
            Correlation type. 'auto' for auto-correlations, 'cross' for
            cross-correlations, 'all' for all correlations. Default 'all'.

        """

        if value == (0, None) and corr == 'all':
            # select all, no need to do anything
            return

        # get feed info from the first input file
        feedno = self.infiles[0]['feedno'][:].tolist()

        if isinstance(value, tuple):
            feeds = np.array(feedno[slice(*value)])
        elif isinstance(value, list):
            feeds = np.intersect1d(feedno, value)
        else:
            raise ValueError('Unsupported data selection %s' % value)

        # get channo info from the first input file
        channo = self.infiles[0]['channo'][:]
        # get corresponding channel_pairs
        channel_pairs = []
        if corr == 'auto':
            for fd in feeds:
                ch1, ch2 = channo[feedno.index(fd)]
                channel_pairs += [ {ch1}, {ch2}, {ch1, ch2} ]
        elif corr == 'cross':
            for fd1, fd2 in itertools.combinations(feeds, 2):
                ch1, ch2 = channo[feedno.index(fd1)]
                ch3, ch4 = channo[feedno.index(fd2)]
                channel_pairs += [ {ch1, ch3}, {ch1, ch4}, {ch2, ch3}, {ch2, ch4} ]
        elif corr == 'all':
            for fd1, fd2 in itertools.combinations_with_replacement(feeds, 2):
                ch1, ch2 = channo[feedno.index(fd1)]
                ch3, ch4 = channo[feedno.index(fd2)]
                channel_pairs += [ {ch1, ch3}, {ch1, ch4}, {ch2, ch3}, {ch2, ch4} ]
        else:
            raise ValueError('Unknown correlation type %s' % corr)

        # get blorder info from the first input file
        blorder = self.infiles[0]['blorder']
        blorder = [ set(bl) for bl in blorder ]

        # channel pair indices
        indices = { blorder.index(chp) for chp in channel_pairs }
        indices = sorted(list(indices))

        self.data_select('baseline', indices)

        self._feed_select = feeds
        self._channel_select = np.array([ channo[feedno.index(fd)] for fd in feeds ])


    def _load_a_common_dataset(self, name):
        ### load a common dataset from the first file
        if name == 'channo' and not self._channel_select is None:
            self.create_dataset(name, data=self._channel_select)
            memh5.copyattrs(self.infiles[0][name].attrs, self[name].attrs)
        else:
            super(RawTimestream, self)._load_a_common_dataset(name)


    def separate_pol_and_bl(self, keep_dist_axis=False):
        """Separate baseline axis to polarization and baseline.

        This will create and return a Timestream container holding the polarization
        and baseline separated data.

        Parameters
        ----------
        keep_dist_axis : bool, optional
            Whether to redistribute main data to the original dist axis if the
            dist axis has changed during the operation. Default False.

        """

        # if dist axis is baseline, redistribute it along time
        original_dist_axis = self.main_data_dist_axis
        if 'baseline' == self.main_data_axes[original_dist_axis]:
            keep_dist_axis = False # can not keep dist axis in this case
            self.redistribute(0)

        # create a Timestream container to hold the pol and bl separated data
        ts = timestream.Timestream(dist_axis=self.main_data_dist_axis, comm=self.comm)

        feedno = sorted(self['feedno'][:].tolist())
        xchans = [ self['channo'][feedno.index(fd)][0] for fd in feedno ]
        ychans = [ self['channo'][feedno.index(fd)][1] for fd in feedno ]

        nfeed = len(feedno)
        xx_pairs = [ (xchans[i], xchans[j]) for i in xrange(nfeed) for j in xrange(i, nfeed) ]
        yy_pairs = [ (ychans[i], ychans[j]) for i in xrange(nfeed) for j in xrange(i, nfeed) ]
        xy_pairs = [ (xchans[i], ychans[j]) for i in xrange(nfeed) for j in xrange(i, nfeed) ]
        yx_pairs = [ (ychans[i], xchans[j]) for i in xrange(nfeed) for j in xrange(i, nfeed) ]

        blorder = [ tuple(bl) for bl in self['blorder'] ]
        conj_blorder = [ tuple(bl[::-1]) for bl in self['blorder'] ]

        def _get_ind(chp):
            try:
                return False, blorder.index(chp)
            except ValueError:
                return True, conj_blorder.index(chp)
        # xx
        xx_list = [ _get_ind(chp) for chp in xx_pairs ]
        xx_inds = [ ind for (cj, ind) in xx_list ]
        xx_conj = [ cj for (cj, ind) in xx_list ]
        # yy
        yy_list = [ _get_ind(chp) for chp in yy_pairs ]
        yy_inds = [ ind for (cj, ind) in yy_list ]
        yy_conj = [ cj for (cj, ind) in yy_list ]
        # xy
        xy_list = [ _get_ind(chp) for chp in xy_pairs ]
        xy_inds = [ ind for (cj, ind) in xy_list ]
        xy_conj = [ cj for (cj, ind) in xy_list ]
        # yx
        yx_list = [ _get_ind(chp) for chp in yx_pairs ]
        yx_inds = [ ind for (cj, ind) in yx_list ]
        yx_conj = [ cj for (cj, ind) in yx_list ]

        # create a MPIArray to hold the pol and bl separated vis
        rvis = self.main_data.local_data
        shp = rvis.shape[:2] + (4, len(xx_inds))
        vis = np.empty(shp, dtype=rvis.dtype)
        vis[:, :, 0] = np.where(xx_conj, rvis[:, :, xx_inds].conj(), rvis[:, :, xx_inds]) # xx
        vis[:, :, 1] = np.where(yy_conj, rvis[:, :, yy_inds].conj(), rvis[:, :, yy_inds]) # yy
        vis[:, :, 2] = np.where(xy_conj, rvis[:, :, xy_inds].conj(), rvis[:, :, xy_inds]) # xy
        vis[:, :, 3] = np.where(yx_conj, rvis[:, :, yx_inds].conj(), rvis[:, :, yx_inds]) # yx

        vis = mpiarray.MPIArray.wrap(vis, axis=self.main_data_dist_axis, comm=self.comm)

        # create main data
        ts.create_main_data(vis)
        # copy attrs from rt
        memh5.copyattrs(self.main_data.attrs, ts.main_data.attrs)
        # create attrs of this dataset
        ts.main_data.attrs['dimname'] = 'Time, Frequency, Polarization, Baseline'

        # create a MPIArray to hold the pol and bl separated vis_mask
        rvis_mask = self['vis_mask'].local_data
        shp = rvis_mask.shape[:2] + (4, len(xx_inds))
        vis_mask = np.empty(shp, dtype=rvis_mask.dtype)
        vis_mask[:, :, 0] = rvis_mask[:, :, xx_inds] # xx
        vis_mask[:, :, 1] = rvis_mask[:, :, yy_inds] # yy
        vis_mask[:, :, 2] = rvis_mask[:, :, xy_inds] # xy
        vis_mask[:, :, 3] = rvis_mask[:, :, yx_inds] # yx

        vis_mask = mpiarray.MPIArray.wrap(vis_mask, axis=self.main_data_dist_axis, comm=self.comm)

        # create vis_mask
        axis_order = ts.main_axes_ordered_datasets[ts.main_data_name]
        ts.create_main_axis_ordered_dataset(axis_order, 'vis_mask', vis_mask, axis_order)

        # create other datasets needed
        # pol ordered dataset
        ts.create_pol_ordered_dataset('pol', data=np.array(['xx', 'yy', 'xy', 'yx']))
        ts['pol'].attrs['pol_type'] = 'linear'

        # bl ordered dataset
        blorder = np.array([ [feedno[i], feedno[j]] for i in xrange(nfeed) for j in xrange(i, nfeed) ])
        ts.create_bl_ordered_dataset('blorder', data=blorder)
        # copy attrs of this dset
        memh5.copyattrs(self['blorder'].attrs, ts['blorder'].attrs)
        # other bl ordered dataset
        if len(set(self.bl_ordered_datasets.keys()) - {'vis', 'vis_mask', 'blorder'}) > 0:
            raise RuntimeError('Should not have other bl_ordered_datasets %s' % (set(self.bl_ordered_datasets.keys()) - {'vis', 'vis_mask', 'blorder'}))

        # copy other attrs
        for attrs_name, attrs_value in self.attrs.iteritems():
            if attrs_name not in self.time_ordered_attrs:
                ts.attrs[attrs_name] = attrs_value

        # copy other datasets
        for dset_name, dset in self.iteritems():
            if dset_name == self.main_data_name or dset_name == 'vis_mask':
                # already created above
                continue
            elif dset_name in self.main_axes_ordered_datasets.keys():
                if dset_name in self.bl_ordered_datasets.keys():
                    # already created above
                    continue
                else:
                    axis_order = self.main_axes_ordered_datasets[dset_name]
                    axis = None
                    for order in axis_order:
                        if isinstance(order, int):
                            axis = order
                    if axis is None:
                        raise RuntimeError('Invalid axis order %s for dataset %s' % (axis_order, dset_name))
                    ts.create_main_axis_ordered_dataset(axis, dset_name, dset.data, axis_order)
            elif dset_name in self.time_ordered_datasets.keys():
                axis_order = self.time_ordered_datasets[dset_name]
                ts.create_time_ordered_dataset(dset_name, dset.data, axis_order)
            elif dset_name in self.feed_ordered_datasets.keys():
                if dset_name == 'channo': # channo no useful for Timestream
                    continue
                else:
                    axis_order = self.feed_ordered_datasets[dset_name]
                    ts.create_feed_ordered_dataset(dset_name, dset.data, axis_order)
            else:
                if dset.common:
                    ts.create_dataset(dset_name, data=dset)
                elif dset.distributed:
                    ts.create_dataset(dset_name, data=dset.data, shape=dset.shape, dtype=dset.dtype, distributed=True, distributed_axis=dset.distributed_axis)

            # copy attrs of this dset
            memh5.copyattrs(dset.attrs, ts[dset_name].attrs)

        # redistribute self to original axis
        if keep_dist_axis:
            self.redistribute(original_dist_axis)

        return ts