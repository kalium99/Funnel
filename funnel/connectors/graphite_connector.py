from socket import socket

class GraphiteConnection(object):

    def __init__(self, host='localhost', port=2023):
        self.graphite = socket()
        self.graphite.connect((host,port))

    def send(self, stat_string):
        self.graphite.sendall(stat_string)

