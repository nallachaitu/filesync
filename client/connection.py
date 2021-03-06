# Class for easy connection handling
#   Copyright (C) 2011 Thomas Gummerer
#
# This file is part of Filesync.
# 
# Filesync is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# Filesync is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Filesync.  If not, see <http://www.gnu.org/licenses/>. 

import socket

class Connection:

	def __init__(self, host, port = 13131):
		self.host = host
		self.port = port

		self.s = socket.socket()

		self.s.connect((socket.gethostbyname(host), port))

	def recieve(self, nobytes = 4096):
		return self.s.recv(nobytes)

	def send(self, string):
		self.s.send(string)

	def sendall(self, string):
		self.s.sendall(string)

	def close(self):
		self.s.close();
