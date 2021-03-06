# Connection thread
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

import threading
import socket
import db

import os
import os.path

class Client(threading.Thread):
	
	def __init__(self, con, addr, savedir):
		threading.Thread.__init__(self)
		self.con = con
		self.addr = addr
		self._savedir = savedir

		# Set up db connection
		self._db = db.Db()

	def _checkUsernamePassword(self, username, password):
		result = self._db.executeSelect("select * from usertable where email = '" + username + "' and password = '" + password + "'")
		if (result.first() is None):
			return False
		else:
			# Return userid
			return result.first()[0]

	def _checkUsername(self, username):
		# For now always accept the username. Might change in future versions
		self.con.send(bytes("0", "utf8"))

	def _checkPassword(self, password):
		self._userid = self._checkUsernamePassword(self._username, password)
		if ((self._username != None) and (password != None) and 
			(self._userid != None)):
			self.con.send(bytes("0", "utf8"))
		else:
			self.con.send(bytes("1", "utf8"))
			thread.exit()

		# Set also the savedir to the correct one for the client
		self._savedir = os.path.join(self._savedir, str(self._userid) + "/")


	def _recieveFile(self, path):
		# Recieve the file from the client
		writefile = open(path, 'wb')
		rec = self.con.recv(1024)
		split = rec.decode("utf8").partition(" ")
		length = None
		if (split[0] == "7"):
			length = int(split[2])
		else:
			print("Wrong code for sending the length")
			exit()

		self.con.send(b'A')

		while (length):
			rec = self.con.recv(min(1024, length))
			writefile.write(rec)
			length -= len(rec)

		self.con.send(b'A') # single character A to prevent issues with buffering

	def _storeFile(self, path):
		# Check if savedir exists
		if (not(os.path.exists(self._savedir))):
			try:
				os.makedirs(self._savedir)
			except error:
				print ("Something went wrong with the path creation")
				exit()
		
		pathfile = os.path.split (path)

		if (not(os.path.exists(os.path.join(self._savedir, pathfile[0])))):
			try:
				os.makedirs(os.path.join(self._savedir, pathfile[0]))
			except error:
				print ("Something went wrong with the path creation")
				exit()

		# Everything is set up, recieve the file and write it to the disk
		self._recieveFile(os.path.join(self._savedir, path))

	def _newFile(self, filename):
		self.con.send(bytes("0", "utf8"))
		# Get changetime
		rec = self.con.recv(4096).decode("utf8")
		split = rec.partition(" ")
		lastchange = None
		if (split[0] == "6"):
			# Get the date on which the file was created
			lastchange = split[2]
		else:
			# Something went wrong. Kick the client out.
			exit()

		self.con.send(bytes("0", "utf8"))
		# Filename includes the whole path. (Poor naming anyway)
		self._storeFile(filename)
		index = self._db.executeSelect("insert into filetable (userid, path, lastchange) values (" + str(self._userid) + ", '" + filename + "', '" + lastchange + "') RETURNING fileid")
		fileid = index.first()

		self._db.executeQuery("delete from hasnewest where fileid = " + str(fileid))
		self._db.executeQuery("insert into hasnewest(clientid, fileid) values (" + self._clientid + ", " + str(fileid) + ")")
		self.con.send(bytes(str(fileid), "utf8"))
		

	def _updateFile(self, fileid):
		self.con.send(bytes("0", "utf8"))
		rec = self.con.recv(4096).decode("utf8")
		split = rec.partition(" ")
		lastchange = None
		if (split[0] == "6"):
			# Get the date on which the file was created
			lastchange = split[2]
		else:
			# Something went wrong. Kick the client out.
			exit()


		self._db.executeQuery("update filetable set lastchange = '" + lastchange + "' where fileid = " + fileid)
		self._db.executeQuery("delete from hasnewest where fileid = " + str(fileid))
		# ACK Timestamp
		self.con.send(bytes("0", "utf8"))
		path = self._db.executeSelect("select path from filetable where fileid = " + fileid)
		self._storeFile(path.first())
		self.con.send(bytes("0", "utf8"))
		self._db.executeQuery("insert into hasnewest(clientid, fileid) values (" + self._clientid + ", " + str(fileid) + ")")



	def _sendClientId(self):
		index = self._db.executeSelect("insert into client (userid) values (" + str(self._userid) + ") returning clientid")
		self.con.send(bytes(str(index.first()), "utf8"))

	def _sendFiles(self):
		# TODO Update lastchange on server, but not so important, since it is not used anywhere
		# Find all files, that the connected client doesn't have.
		for fileid, path in self._db.executeSelect("""
			select filetable.fileid, path
			from filetable natural join usertable natural join client natural join hasnewest
			where userid = """ + str(self._userid) + """
			and clientid != """ + str(self._clientid) + """
			except
			select filetable.fileid, path
			from filetable natural join usertable natural join client natural join hasnewest
			where userid = """ + str(self._userid) + """
			and clientid = """ + str(self._clientid)): # QUERY IS PLAIN WRONG FUCK YOU TOMMY

			# Send filename
			self.con.send(bytes(path, "utf8"))
			# Recieve Acknowledgement
			if (self.con.recv(1).decode("utf8") != '0'):
				print("Wrong acknowledgement. Exiting thread")
				self.con.close()
				exit()

			# Send fileid
			self.con.send(bytes(str(fileid), "utf8"))
			if (self.con.recv(1).decode("utf8") != '0'):
				print("Wrong acknowledgement. Exiting thread")
				self.con.close()
				exit()


			sendfile = open(os.path.join(self._savedir, path), 'rb')
			data = sendfile.read()
			# Send filesize
			self.con.send(bytes("7 " + str(len(data)), "utf8"))
			if (self.con.recv(1).decode("utf8") != '0'):
				print("Wrong acknowledgement. Exiting thread")
				self.con.close()
				exit()

			self.con.sendall(data)
			if (self.con.recv(1).decode("utf8") != '0'):
				print("Wrong acknowledgement. Exiting thread")
				self.con.close()
				exit()

			# Add client to hasnewest
			self._db.executeQuery("insert into hasnewest (fileid, clientid) values (" + str(fileid) + ", " + str(self._clientid) + ")")

		self.con.send(bytes("//", "utf8"))


	def run(self):
		while True:
			try:
				rec = self.con.recv(4096).decode("utf8")
				# Split the string on the first occurence of a blank. Protocol says all send strings are
				# a number followed by a blank, followed by the thing that is sent
				split = rec.partition(' ')

				if (split[0] == '0'):			# Username
					self._username = split[2]
					self._checkUsername(self._username)

				elif (split[0] == '1'):  		# Password
					self._password = split[2]
					self._checkPassword(self._password)

				elif (split[0] == '2'):
					self._sendClientId()

				elif (split[0] == '3'):
					self._clientid = split[2]
					
				elif (split[0] == '4'):			# New file
					filename = split[2]
					self._newFile(filename)

				elif (split[0] == '5'):			# Changed file
					fileid = split[2]
					self._updateFile(fileid)

				elif (split[0] == '9'):			# Request all changed files
					self._sendFiles()

				else:							# Exit signal or a wrong signal send. Close the thread, so that it doesn't consume some extra cpu.
					break

			except socket.error:
				break

		#_db.close()
