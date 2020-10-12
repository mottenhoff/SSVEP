'''
Copyright (C) 2019 Maarten Ottenhoff.
You may use, distribute and modify this code under the
terms of the MIT license.
'''

import yaml
import random 
import time 

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
		self.refresh_threshold = None
		self.window_color = '#000000'
		self.nDroppedFrames = []
		self.loggingLevel = None

		# Exp opts
		self.exp_duration = 30  # s
		self.trial_length = .5  # s
		self.frames_per_trial = None
		self.freqs = {'top': 0,
					  'right': 0,
					  'bottom': 0,
					  'left': 0}

		# Game
		self.speed = 0.01
		self.boundary = 0.6  # Relative to screen size.

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

		lvl = eval('logging.{}'.format(conf['ui']['loggingLevel']))
		logging.console.setLevel(lvl)

	def setup_win(self):
		self.win = visual.Window(self.window_size, fullscr=self.fullscreen, color=self.window_color, gammaErrorPolicy='ignore')
		# self.win.aspect
		if not self.refresh_threshold == None:
			self.win.refreshThreshold = 1/self.mon_refr_rate + self.refresh_threshold  # Default is 120% of estimated RR

	def setup_stims(self):
		''' Setup stimulus objects'''

		# Calculate ratio to normalize the size values
		self.win_ratio = self.win.size[0] / self.win.size[1]
		stim_size_x = 1
		stim_size_y = 1
		self.add_stim(visual.Rect(self.win, pos=(0, 1), size=(stim_size_x, stim_size_y*self.win_ratio), fillColor="#FFFFFFF"), self.freqs['top']) # Up
		self.add_stim(visual.Rect(self.win, pos=(0, -1), size=(stim_size_x, stim_size_y*self.win_ratio), fillColor="#FFFFFFF"), self.freqs['bottom']) # Down
		self.add_stim(visual.Rect(self.win, pos=(-1, 0), size=(stim_size_x, stim_size_y*self.win_ratio), fillColor="#FFFFFFF"), self.freqs['left']) # Left
		self.add_stim(visual.Rect(self.win, pos=(1, 0), size=(stim_size_x, stim_size_y*self.win_ratio), fillColor="#FFFFFFF"),  self.freqs['right']) # Right

		# Use for psychopy version 2020+
		# self.add_stim(visual.Rect(self.win, pos=(0, 1), size=(stim_size_x, stim_size_y*self.win.aspect), fillColor="#FFFFFFF"), self.freqs['top']) # Up
		# self.add_stim(visual.Rect(self.win, pos=(0, -1), size=(stim_size_x, stim_size_y*self.win.aspect), fillColor="#FFFFFFF"), self.freqs['bottom']) # Down
		# self.add_stim(visual.Rect(self.win, pos=(-1, 0), size=(stim_size_x, stim_size_y*self.win.aspect), fillColor="#FFFFFFF"), self.freqs['left']) # Left
		# self.add_stim(visual.Rect(self.win, pos=(1, 0), size=(stim_size_x, stim_size_y*self.win.aspect), fillColor="#FFFFFFF"),  self.freqs['right']) # Right


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

	def draw_player(self):
		self.player_boundary = visual.Rect(self.win, pos=(0, 0), size=(4*self.boundary, 4*self.boundary), lineColor="grey", fillColor=None)
		self.player_boundary.autoDraw = True

		self.pl = visual.Rect(self.win, pos=(0, 0), size=(.1, .1), fillColor="grey", lineColor="grey")
		self.pl.autoDraw = True
		self.target = visual.Rect(self.win, pos=(.5, .5), size=(.1, .1), fillColor="green", lineColor="green")

		self.send_player_marker()
		self.send_target_marker()

	def move_obj(self, obj, dir):
		''' Move the player. Arrows keys implemented for debugging purposes'''

		# Arrowkeys
		if dir == 'left':
			obj.pos += (-self.speed-.05, 0)
		elif dir == 'right':
			obj.pos += (self.speed+.05, 0)
		elif dir == 'up':
			obj.pos += (0, self.speed+.05)
		elif dir == 'down':
			obj.pos += (0, -self.speed-.05)
			

		# Move using command_mapping
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
		else:
			pass
		
		self.send_player_marker()

	def send_flags(self, stream_name, ts, msg):
		self.outlets[stream_name].push_sample([msg])

	def send_player_marker(self):
		msg = 'playerposition_{}_{}'.format(self.pl.pos[0], self.pl.pos[1])
		self.outlets['UiOutput'].push_sample([msg])

	def send_target_marker(self):
		msg = 'targetposition_{}_{}'.format(self.target.pos[0], self.target.pos[1])
		self.outlets['UiOutput'].push_sample([msg])

	def apply_commands(self, stream_name):
		''' Read classification and apply to object'''
		inp, timestamp = self.inlets[stream_name].pull_sample(timeout=0.0)
		if inp:
			self.move_obj(self.pl, int(inp[0]))


	def wait_for_user(self):
		'''Draw waiting text prior to experiment
		TODO: Make text dynamic, e.g. read from config'''

		txtStim = visual.TextStim(self.win, text="Druk op spatiebalk om te beginnen", pos=(0.65,0))
		txtStim.draw()
		self.win.flip()
		while not 'space' in event.getKeys():
			core.wait(1)
		self.win.flip()

	def count_down(self, count_from=3):
		for i in reversed(range(count_from+1)):
			txt = 'Start over {}'.format(i)
			txtStim = visual.TextStim(self.win, text=txt, pos=(0.75,0))  # Recreating the object is actually faster than changing the text.
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
		''' Handle all key presses'''
		keys = event.getKeys()
		if 'escape' in keys:
			self.esc_pressed = True
		for k in ['left', 'right', 'up', 'down']:
			if k in keys:
				print(k)
				self.move_obj(self.pl, k)


	def place_target(self):
		'''places a target on a random position in the field that is within boundaries
		and not directly on the players position '''
		while self.player_reached_target():
			self.target.pos = (random.uniform(-(self.boundary-0.05), self.boundary-0.05),
							   random.uniform(-(self.boundary-0.05), self.boundary-0.05))
			self.send_target_marker()

	def player_reached_target(self):
		'''Returns true if player overlaps the target'''
		return self.pl.overlaps(self.target)

	def update_score(self):
		''' Updates the scoreObj and makes sure a new goal will be placed '''
		self.pl_score += 1
		txt = "goal {} reached".format(self.pl_score)
		self.send_flags('UiOutput', self.timer.getTime(), txt)
		self.place_target()


	def run(self):
		'''
		The main experiment loop.
		'''
		
		# Calculate some random classes
		self.wait_for_user()
		self.count_down()

		self.timer = core.Clock()

		self.draw_player()

		self.pl_score = 0
		self.esc_pressed = False
		self.total_score = 10  # TODO: Place in Config
		fnum = 0
		self.send_flags('UiOutput', self.timer.getTime(), 'experiment_start')
		while not self.esc_pressed and self.pl_score < self.total_score:
			t = time.time()
			self.check_keys()

			self.apply_commands('UiInput')

			if self.player_reached_target():
				self.update_score()

			# Draw everything
			for stim in self.stims:
				if fnum % stim[FREQ] == 0:
					stim[OBJ].draw()

			score_txt = 'Score: {} van {}'.format(self.pl_score, self.total_score)
			score_stim = visual.TextStim(self.win, text=score_txt, pos=(0,0.9), height=0.1)
			score_stim.draw()
			self.target.draw()

			self.win.flip()
			
			fnum += 1
			passed_time = time.time() - t
			if passed_time > 0.1:
				print('Time per loop: {0:.2f}s'.format(time.time() - t))
		

		self.outlets['UiOutput'].push_sample(['experiment_end'])

if __name__ == '__main__':
	ui = Ui()
	ui.setup()
	ui.run()

#TODO: Full screen changes shapes, (maybe port it to the next version anyway)