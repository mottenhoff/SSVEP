'''
Tip: If you need the position of stim in pixels, you can obtain it like this:
from psychopy.tools.monitorunittools import 
posToPix posPix = posToPix(stim)
'''

import sys
import time #DEBUG
import yaml
import random     

import matplotlib.pyplot as plt
from pylsl import StreamInlet, StreamOutlet, StreamInfo, resolve_streams
from psychopy import visual, event, logging, core 

OBJ = 0
FREQ = 1

class Ui():

	def __init__(self):

		# LSL
		self.inlets = {} # Commands from decoder
		self.outlets = {} # Trial flags
		self.inlet_names = []
		self.outlet_names = []

		# Window opts
		self.win = None
		self.fullscreen = False
		self.window_size = (1024, 768)
		self.mon_refr_rate = 60 # Hz # assumed to be equal to FPS (unless machine can't calculate 60+ frames per seconds)
		self.refreshThreshold = None
		self.window_color = '#000000'
		self.nDroppedFrames = []
		self.loggingLevel = None

		# Exp opts
		self.exp_duration = 30 #s
		self.trial_length = .5 #s
		self.frames_per_trial = self.mon_refr_rate * self.trial_length # CHANGE
		self.freqs = {'top': 0,
					  'right': 0,
					  'bottom': 0,
					  'left': 0}

		# Game
		self.speed = 0.01
		self.boundary = 0.6 # Relative to screen size. # Todo, consider drawing the boundary	  

		# Stimulus
		self.stims = []
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
		self.win = visual.Window(self.window_size, fullscr=self.fullscreen, color=self.window_color)

		if not self.refreshThreshold == None:
			self.win.refreshThreshold = 1/self.mon_refr_rate + self.refresh_threshold # Default is 120% of estimated RR
		# print('Win setup, DONE', flush=True)

	def setup_stims(self):

		# Visuals
		
		# Flashing stimulus
		# Calculate ratio to normalize the size values
		self.win_ratio = self.win.size[0] / self.win.size[1] # x is n times larger than y
		stim_size_x = 1
		stim_size_y = 1
		self.add_stim(visual.Rect(self.win, pos=(0, 1), size=(stim_size_x, stim_size_y*self.win_ratio), fillColor="#FFFFFFF"), self.freqs['top']) # Up
		self.add_stim(visual.Rect(self.win, pos=(0, -1), size=(stim_size_x, stim_size_y*self.win_ratio), fillColor="#FFFFFFF"), self.freqs['bottom']) # Down
		self.add_stim(visual.Rect(self.win, pos=(-1, 0), size=(stim_size_x, stim_size_y*self.win_ratio), fillColor="#FFFFFFF"), self.freqs['left']) # Left
		self.add_stim(visual.Rect(self.win, pos=(1, 0), size=(stim_size_x, stim_size_y*self.win_ratio), fillColor="#FFFFFFF"),  self.freqs['right']) # Right
		
		# print('Stimulations setup, DONE')

	def read_label_file(self, filename):
		try:
			with open(filename, 'r') as f:
				labels = f.read()
			return [int(l) for l in list(labels)]
		except Exception as err:
			raise

	def add_stim(self, obj, freq):
		self.stims += [(obj, freq)]

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

		# Controls
		# TODO ADD PLAYER HERE
		# self.setup_command()

	def move_obj(self, obj, dir):
		if dir == 'left':
			obj.pos += (-self.speed-.05, 0)
		elif dir == 'right':
			obj.pos += (self.speed+.05, 0)
		elif dir == 'up':
			obj.pos += (0, self.speed+.05)
		elif dir == 'down':
			obj.pos += (0, -self.speed-.05)

		if dir == self.command_mapping['left'] and \
		   abs(obj.pos[0]) + self.speed <= self.boundary:
			obj.pos += (-self.speed, 0)
		elif dir == self.command_mapping['right'] and \
			 abs(obj.pos[0]) + self.speed <= self.boundary:
			obj.pos += (self.speed, 0)
		elif dir == self.command_mapping['top'] and \
			 abs(obj.pos[1]) + self.speed <= self.boundary:
			obj.pos += (0, self.speed)
		elif dir == self.command_mapping['down'] and \
			 abs(obj.pos[1]) + self.speed <= self.boundary:
			obj.pos += (0, -self.speed)



	def send_flags(self, stream_name, ts, msg):
		self.outlets[stream_name].push_sample([msg])


	def apply_commands(self, stream_name): # Read LSL
		# Apply commands here
		inp, timestamp = self.inlets[stream_name].pull_sample(timeout=0.0)
		if inp:
			self.move_obj(self.pl, int(inp[0]))

	
	def wait_for_user(self):
		txtStim = visual.TextStim(self.win, text="Druk op spatiebalk om te beginnen", pos=(0.65,0))
		# txtStim.pos += [(-txtStim.width/2)/self.win.size[0], 0] # Center the text is a mystery...
		txtStim.draw()
		self.win.flip()
		while not 'space' in event.getKeys(): 
			core.wait(1)
		self.win.flip()

	def count_down(self, count_from=3):
		# Change to textbox for superduper efficiency (but not necessary in outside actual exp)
		for i in reversed(range(count_from+1)):
			txt = 'Start over {}'.format(i)
			txtStim = visual.TextStim(self.win, text=txt, pos=(0.75,0)) #Recreating the object is actually faster than changing the text
			txtStim.draw()  
			self.win.flip()
			core.wait(1)

	def instruct_user(self, direction):
		'''
		Draws the direction for the user to look at and waits for 1 second
		'''

		txt = [t[0] for t in self.command_mapping.items() if t[1] == direction][0]
		if txt == 'top':
			txt = '\u21e6'
		txtStim = visual.TextStim(self.win, text=txt, pos=(0.90,0), alignHoriz='center')
		txtStim.draw()
		self.win.flip()
		core.wait(1)

	def check_keys(self):
		# handle all key presses (Also for debugging)
		keys = event.getKeys()
		if 'escape' in keys:
			self.esc_pressed = True
		for k in ['left', 'right', 'up', 'down']:
			if k in keys:
				print(k)
				self.move_obj(self.pl, k)


	def place_target(self):
		# places a target on a random position in the field (but not directly on the player)
		while self.player_reached_target():
			self.target.pos = (random.uniform(-.5, .5), random.uniform(-.5, .5))

	def player_reached_target(self):
		return self.pl.overlaps(self.target)

	def update_score(self):
		# updates the scoreObj and makes sure a new goal will be placed
		self.pl_score += 1
		txt = "goal {} reached".format(self.pl_score)
		self.send_flags('UiOutput', self.timer.getTime(), txt)
		self.place_target()


	def run(self):
		'''
		The main experiment loop.
		'''
		# calculate the length of the trials in frames
		nFrames = self.trial_length * self.mon_refr_rate
		
		# Calculate some random classes
		self.wait_for_user()
		# self.count_down()

		self.timer = core.Clock()

		# SETUP -> TODO: Move to self.setup()
		self.player_boundary = visual.Rect(self.win, pos=(0, 0), size=(4*self.boundary, 4*self.boundary), lineColor="grey", fillColor=None)
		self.player_boundary.autoDraw = True

		self.pl = visual.Rect(self.win, pos=(0, 0), size=(.1, .1), fillColor="grey", lineColor="grey")
		self.pl.autoDraw = True
		self.target = visual.Rect(self.win, pos=(.5, .5), size=(.1, .1), fillColor="green", lineColor="green")


		self.pl_score = 0
		self.esc_pressed = False
		self.total_score = 10 # TODO: Place in Config
		fnum = 0
		self.send_flags('UiOutput', self.timer.getTime(), 'experiment_start')
		while not self.esc_pressed and self.pl_score < self.total_score:

			self.check_keys() # for esc (and arrow_keys debug)

			self.apply_commands('UiInput')

			if self.player_reached_target():
				self.update_score()

			# Draw everything
			for stim in self.stims:
				if fnum % stim[FREQ] == 0: stim[OBJ].draw()

			score_txt = 'Score: {} van {}'.format(self.pl_score, self.total_score)
			score_stim = visual.TextStim(self.win, text=score_txt, pos=(0,0.9), height=0.1)
			score_stim.draw()
			self.target.draw()

			self.win.flip()
			fnum += 1


		self.outlets['UiOutput'].push_sample(['experiment_end'])

if __name__ == '__main__':
	ui = Ui()
	ui.setup()
	ui.run()



# class StimFlash():

# 	def __init__(self):
# 		self.obj = None

# 		self.pos = (0, 0)
# 		self.size = (1, 1)
# 		self.color = (1, 1, 1)
# 		self.freq = 1 # Hz

# 	def add_stim(self, obj, pos, size, color)