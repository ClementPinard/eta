'''
Core numeric utilities.

Copyright 2017, Voxel51, LLC
voxel51.com

Jason Corso, jjc@voxel51.com
'''
# pragma pylint: disable=redefined-builtin
# pragma pylint: disable=unused-wildcard-import
# pragma pylint: disable=wildcard-import
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from builtins import *
# pragma pylint: enable=redefined-builtin
# pragma pylint: enable=unused-wildcard-import
# pragma pylint: enable=wildcard-import

import numpy as np


class GrowableArray(object):
    '''A class for building a numpy array from streaming data.'''

    def __init__(self, rowlen):
        self.data = []
        self.rowlen = rowlen

    def update(self, row):
        '''Add row to array.'''
        assert len(row) == self.rowlen, "Expected row length %d" % self.rowlen
        for r in row:
            self.data.append(r)

    def finalize(self):
        '''Return numpy array.'''
        return np.reshape(
            self.data,
            newshape=( int(len(self.data) / self.rowlen), self.rowlen),
        )
