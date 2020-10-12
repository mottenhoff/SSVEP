import bisect
from math import ceil, floor

import numpy as np
import mne
from sklearn.cross_decomposition import CCA


class CCAClassifier():
	''' CCA classifyer maximizes correlation between two
	canonical variates, which are linear combinations of
	the original two sets of variables.
	Let X and Y be your data. CCA finds two sets of 
	weights a and b such corr(aX, bY) is maximized.

	This classifier compares the given sample of size
	[sample x channels] with each pre-set frequency and
	its harmonics. The pre-set frequency that correlates
	the most with the sample is selected and returned.	
	
	'''

	def __init__(self):
		self.max_sample_length = None
		self.fs = None

		self.n_harmonics = 3

	def generateSignals(self, freqList, max_sample_length, samplerate):
		self.fs = samplerate
		self.max_sample_length = max_sample_length

		segment_time = np.array([x/samplerate for x in range(0, max_sample_length)])

		self.freqClasses = freqList
		
		self.generatedSignals = np.zeros((len(self.freqClasses), max_sample_length, 6))
		for i, freq in enumerate(self.freqClasses):
			self.generatedSignals[i,:,0] = np.sin(np.pi*2*freq*segment_time)
			self.generatedSignals[i,:,1] = np.cos(np.pi*2*freq*segment_time)
			self.generatedSignals[i,:,2] = np.sin(np.pi*2*freq*segment_time*2)
			self.generatedSignals[i,:,3] = np.cos(np.pi*2*freq*segment_time*2)
			self.generatedSignals[i,:,4] = np.sin(np.pi*2*freq*segment_time*3)
			self.generatedSignals[i,:,5] = np.cos(np.pi*2*freq*segment_time*3)

	def locate_pos(self, available_freqs, target_freq):
		'''
		Locates the closest value to the right for given target. 
		TODO Check if why vars are called freqs and not timestamps (which are supplied as args)
		'''
		pos = bisect.bisect_right(available_freqs, target_freq)
		if pos == 0:
			return 0
		if pos == len(available_freqs):
			return len(available_freqs)-1
		if abs(available_freqs[pos]-target_freq) < abs(available_freqs[pos-1]-target_freq):
			return pos
		else:
			return pos-1

	def preprocess(self, data):

		##### BANDPASS FILTER #####
		cutoff_low = max(2, floor(min(self.freqClasses)) - 2) #-+ to prevent filter cutting of the actual frequency
		cutoff_high = ceil(max(self.freqClasses)) * self.n_harmonics + 2

		cutoff_freqs = [[cutoff_low, cutoff_high]]

		if cutoff_high > 52:
			cutoff_freqs += [[52, 48]]

		# data = data.astype(np.float64)
		for cutoffs in cutoff_freqs:
			data = mne.filter.filter_data(data.T, self.fs, cutoffs[0], cutoffs[1], method='iir', verbose='ERROR').T

		return data

	def classify_chunk(self, eeg_data, conf_level=0):
		class_label = {
			0: 'top',
			1: 'left',
			2: 'down',
			3: 'right',
			4: 'nothing'}	

		eeg_data = np.array(eeg_data)

		## Preprocess
		# data = self.preprocess(eeg_data)

		## Classify
		cca_result = []
		# Compare generatedSignals with each FrequencyClass
		for i in range(len(self.freqClasses)):
			# Select correct sample length (i.e. check if it doesn't exceed max sample length)
			sampleLen = min(eeg_data.shape[0], len(self.generatedSignals[i]))
			ccaInput = eeg_data[:sampleLen, :]

			# Fit to correct format:
			ccaGen = self.generatedSignals[i, :sampleLen, :]

			# Create CCA-Object
			cca = CCA(n_components=1) # TODO: Check if declaring earlier is quicker
									   # 	   and repeated fitting doesn't influence data
			
			# Train model with data:
			cca.fit(ccaInput, ccaGen)

			# Transform data:
			res_sample, res_gensig = cca.transform(ccaInput, ccaGen)

			# Add Correlation coefficient of transformed data to list:
			cca_result.append(np.corrcoef(res_sample.T, res_gensig.T)[0][1])

		# Returns the class with the highest correlation:
		maxCorrel = max(cca_result) 
		classId = cca_result.index(maxCorrel)
		print('\t {0:<5s} {1:d}  [{2:.2f}] // \t [{3:.2f},   {4:.2f},   {5:.2f},   {6:.2f}]'\
			  .format(class_label[classId], classId, maxCorrel, 
			  		  cca_result[0], cca_result[1], cca_result[2], cca_result[3]))
		print(conf_level)
		if maxCorrel <= conf_level: # Empirically determine this boundary
			#TODO: Make the confidence level based on the difference between all the correlations
			classId = 4 # = NOTHING

		return classId

if __name__ == "__main__":
	import matplotlib.pyplot as plt
	cca = CCAClassifier()
	
	
	freq_list = [3, 5, 7, 11]
	freq_list = [60/f for f in freq_list]
	print(freq_list)
	max_sample_length = 1500
	fs = 500

	n_chs = 3
	n_samp = 500

	data = np.random.rand(n_samp, n_chs)

	cca.generateSignals(freq_list, max_sample_length, fs)
	result = cca.classify_chunk(data)
	

	# VISUALIZE
	fig, ax = plt.subplots(6, 1, sharex=True)
	titles = ['sin', 'cos', '2*sin', '2*cos', '3*sin', '3*cos']
	for i in range(cca.generatedSignals.shape[2]):
		ax[i].set_title(titles[i])
		for j in range(cca.generatedSignals.shape[0]):
			ax[i].plot(cca.generatedSignals[j, :, i])
	plt.legend(freq_list)
	plt.show()
	print('Done')

