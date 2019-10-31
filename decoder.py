'''
START UP
start micmLSLServer.py
start mockAmp.py
'''
import time
import sys
import yaml

import numpy as np
import pandas as pd
from pylsl import StreamInlet, StreamOutlet, StreamInfo, resolve_streams

from classifiers.CCAClassifier import CCAClassifier


class Decoder():
	''' Handles all data streams between amplifiers, UI and classifier'''

	def __init__(self):
		# Experiment
		self.closed_loop = None
		self.eeg_channels = []
		self.freqList = []

		# LSL Streams
		self.inlets = {}
		self.outlets = {}
		self.inlet_names = []
		self.outlet_names = []

		# Data buffers
		self.timestamp_buffer = []
		self.data_buffer = []
		
		# Classifier
		self.classification_start = None
		self.classification_stop = None
		self.window_size = 1  # Seconds
		self.step_size = 0.1  # Seconds

		self.classifier = None
		self.max_sample_length = None
		self.labels = []
		self.results = []
		self.trial_count = 0

		# Commands
		self.command_mapping = None

	def load_config(self, filename):
		''' Loads all data from the config file and saves in the instance
		variables. '''
		with open(filename, 'r') as file:
			try:
				conf = yaml.safe_load(file)
			except yaml.YAMLError as exc:
				pass

		self.closed_loop = conf['experiment']['closedLoop']
		self.command_mapping = conf['experiment']['commandMapping']
		self.eeg_channels = conf['experiment']['channels']
		
		self.freqList = conf['experiment']['stimulusFrequencies']
		self.max_sample_length = conf['classifier']['maxSampleLength']

		config_inlets = conf['streams']['decoder']['inlet_names']
		self.inlet_names = [config_inlets[inlet_type] for inlet_type in config_inlets]  # TODO: Change inlet loading such that you can choose the eeg stream dynamically
		self.outlet_names = conf['streams']['decoder']['outlet_names']

		# Uncomment to include classification labels
		if 'labelFile' in conf['classifier']:
			self.labels = self.read_label_file(conf['classifier']['labelFile'])

	def read_label_file(self, lab_file):
		'''
		Read all labels in the supplied label file and saves it for later
		classifier performance measurements.
		'''

		try:
			with open(lab_file, 'r') as f:
				labels = f.read()
			return [int(l) for l in list(labels)]
		except Exception as err:
			raise

	def initialize_classifier(self, on_stream):
		'''
		Initialize and save a Canonical correlation analysis classifier in self and
		calculated the standards signal that the classifier compares the EEG data
		with.

		TODO: Change to classifier.initialize() -> More modular
		'''

		freqs = list(self.freqList.values())
		samplerate = self.inlets[on_stream].info().nominal_srate()

		self.classifier = CCAClassifier()
		self.classifier.generateSignals(freqs, self.max_sample_length , samplerate)

	def connect_streams(self):
		'''
		Creates streamOutlets for sending commands to the UI. Then looks for
		streamInlets corresponding to the names given in the config file.
		Check infinitely until all streams are connected and prints out the
		names of the stream that are still not connected.

		LSL DOCS/CODE: https://github.com/chkothe/pylsl/blob/master/pylsl/pylsl.py
		# For selecting streamInlets, see also: resolve_byprop, resolve_pypred
		'''

		stream_name = self.outlet_names[0]
		info = StreamInfo(stream_name, 'Commands', 1, 0, 'int8', 'com1')
		self.outlets[stream_name] = StreamOutlet(info)
		
		# StreamInlets
		print('Searching for stream inlets...')
		while len(self.inlets) < len(self.inlet_names):
			# Iterate over LSL streams and connect them to an outlet
			streams = resolve_streams(wait_time=1.0)
			for stream in streams:
				if stream.name() in self.inlet_names and stream.name() not in self.inlets.keys():
					self.inlets[stream.name()] = StreamInlet(stream)

			# Check which streams are missing and let user know
			missing_streams = [n for n in self.inlet_names if n not in self.inlets.keys()]
			if any(missing_streams):
				print('Waiting for stream(s): {}'.format(missing_streams))

		print('''\nDecoder connected to streams:\n\tInlets: {}\n\tOutlets: {}'''
				.format(list(self.inlets.keys()), list(self.outlets.keys())))


	def read_chunk(self, stream_name, max_chunk_samples=1024):
		'''
		Reads a chunk of given size from StreamInlet
		Chunk is a list of samples and timestamp a list of timestamps
		'''
		chunk, timestamps = self.inlets[stream_name].pull_chunk(timeout=0.0, max_samples=max_chunk_samples)

		if len(chunk) == 0:
			return False
		self.data_buffer.extend(chunk)
		self.timestamp_buffer.extend(timestamps)

		return True
	
	def check_markers(self, stream_name):
		'''
		Reads markers stream from UI and handles incoming markers. Used to determine
		the start and end of trials or the experiment
		'''
		marker, marker_ts = self.inlets[stream_name].pull_sample(timeout=0.0)
		if marker is not None:
			if marker[0] == 'trial_start':
				self.classification_start = marker_ts
			elif marker[0] == 'trial_end' and self.classification_start is not None:
				self.classification_stop = marker_ts
				self.trial_count += 1
				return True
			elif marker[0] == 'experiment_start':
				self.classification_start = marker_ts
			elif marker[0] == 'experiment_end':
				self.running = False
				print('Experiment finished.')
		return False

	def get_score(self):
		'''Prints classifier accuracy'''
		n_correct = sum([1 for i in range(len(self.labels)) if self.labels[i] == self.results[i]])
		print('Accuracy: {:.2f}'.format(n_correct/len(self.labels)))

	def select_channels(self, from_stream):
		''' Retrieves all channels sent through stream from the streamInlet
		For all StreamInlet information: StreamInlet.info().as_xml()
		'''

		info = self.inlets[from_stream].info()  # channels

		self.ch_idx = []
		ch = info.desc().child("channels").child("channel")
		for k in range(info.channel_count()):
		    ch_name = ch.child_value('label')
		    for eeg_channel in self.eeg_channels:  # This way you can select based on partial names too
		    	if str(eeg_channel) in ch_name:
		    		self.ch_idx += [k]
			    	print("{} ".format(ch_name), end='')
		    ch = ch.next_sibling()
		print('-> added to channels')


	def apply_model(self):
		'''
		Processes chunk and applies it to the model. Returns the
		prediction result of the model.

		Open loop tracks trials by markers send from the UI.
		Closed loop starts prediction from the experiment_start marker (also send
		by the UI) and selects a dataslice with size self.window_size. Progresses
		each classication with self.step_size

		Removes all data from buffer (in class, not the LSL buffer) before
		classification end. Data is still saved by LabRecorder.
		
		Class mapping: See config

		'''
		# Determine data slice in buffer
		pos_start = self.classifier.locate_pos(self.timestamp_buffer,
											   self.classification_start)
		if self.closed_loop:
			pos_step = self.classifier.locate_pos(self.timestamp_buffer,
												  self.classification_start + self.step_size)
			pos_stop = self.classifier.locate_pos(self.timestamp_buffer,
												  self.classification_start + self.window_size)
		else:
			pos_stop = self.classifier.locate_pos(self.timestamp_buffer,
												  self.classification_stop)

		# Select that part
		data = np.array(self.data_buffer[pos_start:pos_stop])[:, self.ch_idx]

		# TODO: Implement dynamic referencing
		# data = data[:, :7] - data[:,7][:,None]

		# Classify
		classId = self.classifier.classify_chunk(data)

		if self.closed_loop:
			# Move window
			self.classification_start += self.step_size

			self.data_buffer = self.data_buffer[pos_step:]
			self.timestamp_buffer = self.timestamp_buffer[pos_step:]
		else:
			# Reset buffers
			self.data_buffer = []
			self.timestamp_buffer = []

		return classId

	def send_commands(self, stream, result):
		''' Sends the classification results to the LSL server '''
		self.outlets[stream].push_sample([result])

	def run(self, eeg_stream_name):
		self.load_config('config.yml')

		self.connect_streams()
		self.initialize_classifier(eeg_stream_name)
		self.select_channels(eeg_stream_name)

		self.running = True
		while self.running:
			received_data = self.read_chunk(eeg_stream_name)

			if not received_data:
				continue

			if (self.check_markers('UiOutput')) or \
			 (self.closed_loop and
			  self.classification_start and
			  self.classification_start + self.window_size <= self.timestamp_buffer[-1]):
			    # Returns True is complete trial is in buffer or exp is a closed loop,
			    # classification start index exists and a full window size is present
				result = self.apply_model()
				self.results.extend([result])
				self.send_commands('UiInput', result)
				if not self.closed_loop:
					print('T|P - {}|{}'.format(self.labels[self.trial_count-1], self.results[self.trial_count-1]))

		if any(self.labels) and not self.closed_loop:
			try:
				self.get_score()
			except Exception:
				pass

if __name__ == '__main__':
	print('Starting decoder...')
	input_stream_name = 'Micromed'  # TODO: Get input_stream_name from config
	dec = Decoder()
	dec.run(eeg_stream_name=input_stream_name)












