import bisect

import numpy as np
from sklearn.cross_decomposition import CCA


class CCAClassifier():

	def __init__(self):
		self.max_sample_length = None
		self.samplerate = None

		self.frequencies = []
		self.generated_signals = []


	def generateSignals(self, freqList, max_sample_length, samplerate):
		segment_time = np.array([x/samplerate for x in range(0, max_sample_length)])

		self.freqClasses = freqList
		
		self.generatedSignals = np.zeros((len(self.freqClasses),max_sample_length, 6))
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

	def classify_chunk(self, eeg_data):
		cca_result = []
		for i in range(len(self.freqClasses)):
			#Calculate length of compared samples (to use the longest possible sample size):
			sampleLen = min(len(eeg_data), len(self.generatedSignals[i]))

			#Fit to correct format:
			ccaInput = np.array(eeg_data)[:sampleLen,:]
			ccaGen = self.generatedSignals[i,:sampleLen,:]

			#Create CCA-Object
			cca2 = CCA(n_components=1) # TODO: Check if declaring earlier is quicker
									   # 	   and repeated fitting doesn't influence data
				#Train model with data:
			cca2.fit(ccaInput, ccaGen)

			#Transform data:
			res_x, res_y = cca2.transform(ccaInput, ccaGen)

			#Add Correlation coefficient of transformed data to list:
			cca_result.append(np.corrcoef(res_x.T, res_y.T)[0][1])

		#Returns the class with the highest correlation:
		maxCorrel = max(cca_result) 
		classId = cca_result.index(maxCorrel) # CHECK IF CLASSID CORRESPONDS TO CLASSID IN UI
		return classId
