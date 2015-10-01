#! /usr/bin/env python
#
# Copyright (c) 2015 Jakub Krajniak <jkrajniak@gmail.com>
#
# Distributed under terms of the GNU GPLv3 license.
#

import urllib

IDLE = 0
DOWNLOAD = 1
FINISHED = 2
MATCHING = 3

valid_status = [IDLE, DOWNLOAD, MATCHING, FINISHED]


class PLogger(object):
    def __init__(self, source_rank, initial_status=0, host_url='http://0.0.0.0:5050'):
        self.rank = source_rank
        self.status = 0
        if self.status not in valid_status:
            raise Exception('Invalid status')
        self.update_url = '{}/update_log/?'.format(host_url)
        self.host_url = host_url
        print('PLogger rank:{}, host_url:{}'.format(source_rank, host_url))

    def write(self, message, status=None):
        if status is not None:
            self.status = status
        if self.status not in valid_status:
            raise Exception('Invalid status {}'.format(status))
        params = {'source': self.rank, 'message': message, 'status': self.status}
        update_url = self.update_url + urllib.urlencode(params)
        try:
            urllib.urlopen(update_url)
        except IOError:
            pass
        print('{}: {}'.format(self.rank, message))

    def emit_finished(self, filename):
        params = {'filename': filename}
        url = '{}/finished/?'.format(self.host_url) + urllib.urlencode(params)
        try:
            urllib.urlopen(url)
        except IOError:
            pass
