#! /usr/bin/env python
#
# Copyright (c) 2015 Jakub Krajniak <jkrajniak@gmail.com>
#
# Distributed under terms of the GNU GPLv3 license.
#

import urllib
import socket

IDLE = 0
INIT = 1
DOWNLOAD = 2
MATCHING = 3
SENDING = 4
RECEIVING = 5
COMPOSING = 6
FINISHED = 7

valid_status = [IDLE, INIT, DOWNLOAD, SENDING, RECEIVING, MATCHING, COMPOSING, FINISHED]


class PLogger(object):
    """Parallel logger.

    Args:
        source_rank: The MPI rank of the source of logs.
        initial_status: The status of the message.
        host_url: The URL to the web server.
    """
    def __init__(self, source_rank, initial_status=0, host_url='http://0.0.0.0:5050'):
        self.rank = source_rank
        self.node = socket.gethostname()
        self.status = 0
        if self.status not in valid_status:
            raise Exception('Invalid status')
        self.update_url = '{}/update_log/?'.format(host_url)
        self.host_url = host_url
        print('PLogger node: {}, rank:{}, host_url:{}'.format(self.node, source_rank, host_url))

    def write(self, message, status=None):
        if status is not None:
            self.status = status
        if self.status not in valid_status:
            raise Exception('Invalid status {}'.format(status))
        params = {'source': self.rank, 'node': self.node, 'message': message, 'status': self.status}
        update_url = self.update_url + urllib.urlencode(params)
        try:
            urllib.urlopen(update_url)
        except IOError:
            pass
        print('{}: {}'.format(self.rank, message))

    def emit_partial(self, filename):
        params = {'filename': filename}
        url = '{}/partial/?'.format(self.host_url) + urllib.urlencode(params)
        try:
            urllib.urlopen(url)
        except IOError:
            pass

    def emit_finished(self, filename):
        params = {'filename': filename}
        url = '{}/finished/?'.format(self.host_url) + urllib.urlencode(params)
        try:
            urllib.urlopen(url)
        except IOError:
            pass

    def pong(self):
        """Notify GUI that daemon is alive."""
        print('{}/pong/'.format(self.host_url))
        urllib.urlopen('{}/pong/'.format(self.host_url))
