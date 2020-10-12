import yaml

from pylsl import StreamInlet, StreamOutlet, StreamInfo, resolve_streams
from psychopy import visual, event, logging, core

OBJ = 0
FREQ = 1

class Ui():

	def __init__(self):

		# LSL
		self.inlets = {}  # Commands from decoder
		self.outlets = {}  # Trial flags
		self.inlet_names = []
		self.outlet_names = []

		# Window opts
		self.win = None
		self.fullscreen = False
		self.window_size = (1024, 768)
		self.mon_refr_rate = 60  # Hz. Assumed to be equal to FPS (unless machine
								 # can't calculate 60+ frames per seconds)
		self.refreshThreshold = None
		self.window_color = '#000000'
		self.nDroppedFrames = []
		self.loggingLevel = None

		# Exp opts
		self.exp_duration = 30  # s
		self.trial_length = .5  # s
		self.frames_per_trial = self.mon_refr_rate * self.trial_length
		self.freqs = {'top': 0,
					  'right': 0,
					  'bottom': 0,
					  'left': 0}

		# Stimulus
		self.stims = []
		self.commandVis = None
		self.command_mapping = {}

		self.refresh_threshold = None


	def load_config(self, filename):
		with open(filename, 'r') as file:
			try:
				conf = yaml.safe_load(file)
			except yaml.YAMLError as exc:
				pass

		self.fullscreen = conf['ui']['fullscreen']
		self.window_size = (conf['ui']['windowSize']['width'], conf['ui']['windowSize']['height'])
		self.mon_refr_rate = conf['ui']['monitorRefreshRate']
		self.refresh_threshold = conf['ui']['refreshThreshold']
		self.frames_per_trial = self.mon_refr_rate * self.trial_length

		self.command_mapping = conf['experiment']['commandMapping']

		self.trial_length = conf['experiment']['trialLength']
		self.freqs = conf['experiment']['stimulusFrequencies']

		self.inlet_names = conf['streams']['SSVEPui']['inlet_names']
		self.outlet_names = conf['streams']['SSVEPui']['outlet_names']

		if 'labelFile' in conf['classifier']:
			self.labels = self.read_label_file(conf['classifier']['labelFile'])

		lvl = eval('logging.{}'.format(conf['ui']['loggingLevel'])) # Remember that using eval with input a security hole
		logging.console.setLevel(lvl)


	def setup_win(self):
		self.win = visual.Window(self.window_size, fullscr=self.fullscreen, color=self.window_color, gammaErrorPolicy='warn')

		if not self.refreshThreshold == None:
			self.win.refreshThreshold = 1/self.mon_refr_rate + self.refresh_threshold # Default is 120% of estimated RR
		# print('Win setup, DONE', flush=True)

	def setup_stims(self):
		''' Setup stimulus objects'''

		# Calculate ratio to normalize the size values
		ratio = self.win.size[0] / self.win.size[1]
		stim_size_x = 1
		stim_size_y = 1
		self.add_stim(visual.Rect(self.win, pos=(0, 1), size=(stim_size_x, stim_size_y*ratio), fillColor="#FFFFFFF"), self.freqs['top']) # Up
		self.add_stim(visual.Rect(self.win, pos=(0, -1), size=(stim_size_x, stim_size_y*ratio), fillColor="#FFFFFFF"), self.freqs['bottom']) # Down
		self.add_stim(visual.Rect(self.win, pos=(-1, 0), size=(stim_size_x, stim_size_y*ratio), fillColor="#FFFFFFF"), self.freqs['left']) # Left
		self.add_stim(visual.Rect(self.win, pos=(1, 0), size=(stim_size_x, stim_size_y*ratio), fillColor="#FFFFFFF"),  self.freqs['right']) # Right

	def read_label_file(self, filename):
		try:
			with open(filename, 'r') as f:
				labels = f.read()
			return [int(l) for l in list(labels)]
		except Exception as err:
			raise

	def add_stim(self, obj, freq):
		self.stims += [(obj, freq)]

	def setup_command(self):

		# Setup visuals
		sq = visual.Rect(self.win, pos=(0, 0), size = (.1, .1), fillColor="red", lineColor="red")
		self.add_stim(sq, 1)
		self.commandVis = sq

	def setup_streams(self):
		# Outlets
		# Start/stop markers
		stream_name = self.outlet_names[0]
		info = StreamInfo(stream_name, 'Markers', 1, 0, 'string', 'UiOutput1')
		self.outlets[stream_name] = StreamOutlet(info)

		# StreamInlets
		# See also: resolve_byprop, resolve_pypred
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

		print('''\nUI connected to streams:\n\tInlets: {}\n\tOutlets: {}'''.format(list(self.inlets.keys()), list(self.outlets.keys())))


	def setup(self):
		# Config
		self.load_config('config.yml')

		# Stream I/O
		self.setup_streams()

		# GUI
		self.setup_win()
		self.setup_stims()


	def move_obj(self, obj, dir):
		if dir == self.command_mapping['left']:
			obj.pos += (-0.01, 0)
		elif dir == self.command_mapping['right']:
			obj.pos += (0.01, 0)
		elif dir == self.command_mapping['top']:
			obj.pos += (0, 0.01)
		elif dir == self.command_mapping['down']:
			obj.pos += (0, -0.01)


	def send_flags(self, stream_name, ts, msg):
		self.outlets[stream_name].push_sample([msg])


	def apply_commands(self, stream_name): # Read LSL
		# Apply commands here
		inp, timestamp = self.inlets[stream_name].pull_sample(timeout=0.0)
		if inp:
			self.move_obj(self.commandVis, int(inp[0]))

	
	def wait_for_user(self):
		txtStim = visual.TextStim(self.win, text="Press space to continue.", pos=(0.65,0))
		txtStim.draw()
		self.win.flip()
		while not 'space' in event.getKeys(): 
			core.wait(1)
		self.win.flip()

	def count_down(self, count_from=3):
		for i in reversed(range(count_from+1)):
			txt = 'Starting in {}'.format(i)
			txtStim = visual.TextStim(self.win, text=txt, pos=(0.75,0))  # Recreating the object is actually faster than changing the text
			txtStim.draw()  
			self.win.flip()
			core.wait(1)

	def instruct_user(self, direction):
		'''
		Draws the direction for the user to look at and waits for 1 second
		'''

		txt = [t[0] for t in self.command_mapping.items() if t[1] == direction][0]
		# CONS: Change to unicode arrows here
		# if txt == 'top':
		# 	txt = '\u21e6'
		txtStim = visual.TextStim(self.win, text=txt, pos=(0.90,0), alignHoriz='center')
		txtStim.draw()
		self.win.flip()
		core.wait(1)

	def run(self):
		'''
		The main experiment loop.
		'''
		# calculate the length of the trials in frames
		nFrames = self.trial_length * self.mon_refr_rate
		
		# Calculate some random classes
		self.wait_for_user()
		self.count_down()
		timer =core.Clock()

		self.send_flags('UiOutput', timer.getTime(), 'experiment_start')
		for ntr, trial in enumerate(self.labels):

			self.instruct_user(trial)

			# print('Starting exp for %is (%i Frames)' % (self.exp_duration, nFrames))
			logging.log("{:<5s} \t #{} - class {}".format("START", ntr, trial), logging.DATA)
			logging.flush()
			self.win.recordFrameIntervals = True
			
			self.send_flags('UiOutput', timer.getTime(), 'trial_start')

			# THIS PART SHOULD HAVE NO FRAMEDROPS
			for fnum in range(nFrames):
				# Some framedrops? Check if all LSL connections are working

				# Draw objects
				for stim in self.stims:
					if fnum % stim[FREQ] == 0: stim[OBJ].draw()

				self.win.flip()
			# END CRITICAL PART

			self.win.recordFrameIntervals = False
			# Send trial information
			self.send_flags('UiOutput', timer.getTime(), 'trial_end')

			logging.log("{:<5s} \t #{} - class {}".format('END', ntr, trial), logging.DATA)
			logging.log("Dropped {:>2d}/{:<3d} frames ({:2.0f}%)".format(self.win.nDroppedFrames, fnum, self.win.nDroppedFrames/fnum*100), logging.WARNING)
			logging.flush()

			self.nDroppedFrames += [self.win.nDroppedFrames]
			self.win.nDroppedFrames = 0
		
			if 'escape' in event.getKeys(): 
				break

		# Let the decoder know the experiment is finished
		self.outlets['UiOutput'].push_sample(['experiment_end'])


if __name__ == '__main__':
	ui = Ui()
	ui.setup()
	ui.run()
