# -*- coding: utf-8 -*-
"""
Created on Thu Oct  3 12:52:19 2019

@author: Maarten
"""
from random import shuffle

classes = [0, 1, 2, 3]
reps = 5

labels = [str(i) for i in classes]
labels = labels*reps
shuffle(labels)
labels = ''.join(labels)

f = open('labels.txt', 'w+')
f.write(labels)
f.close()


#f = open("labels.txt", "r").read()
