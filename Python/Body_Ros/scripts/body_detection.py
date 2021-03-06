#!/usr/bin/env python

#################################################################################################################################
"""
Body Detection Module - Acts as Frost's Eyes

Establishes a connection to a USB Camera with ROS, in this case a XBox Kinect's RGB Camera
Receives frames from Kinect and utilizes machine learning classifiers and smoothing algorithms to find and track people
Displays a live feed of the camera with people bounded in green boxes

Written by Kevin Zhang
"""
################################################################################################################################


import numpy as np
import cv2
import freenect
import rospy
from frost_body.msg import Rect, Rect_Array
import time


class BodyDetector(object):
	"""
	main class for Kinect's computer vision, finds and tracks bodies within field of vision
	"""
	def __init__(self, init = False):

		if not init:
			rospy.init_node('frost_body', anonymous = True)

		#setting up ROS publishers to Edwin commands
		self.body_pub = rospy.Publisher('tracked_people', Rect_Array, queue_size=10)

		#image from Kinect
		self.frame = []

		#parameters for tuning speed vs performance
		self.winStride = (4,4)
		self.padding = (16,16)
		self.scale = 1.03
		self.meanShift = False

		#ML library from OpenCV
		self.hog = cv2.HOGDescriptor()
		self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())


		#variables for tracking people
		self.history = [] #maintains a rectangle in occasional dropped frames

		#data to publish
		self.people_rects = []
		self.people = Rect_Array()
		self.people_ranges = None


	def get_video(self):
		"""
		gets video frame if video capture is currently from Kinect
		"""
		array,_ = freenect.sync_get_video()
		array = cv2.cvtColor(array,cv2.COLOR_RGB2BGR)
		return array


	def find_bodies(self):
		"""
		uses HOG and non-max supression to calculate where people are in the frame, if any
		"""

		self.frame = self.get_video()

		self.frame = cv2.resize(self.frame, (320, 240))

		#finds people
		(rects, weights) = self.hog.detectMultiScale(self.frame, winStride=self.winStride,
		padding=self.padding, scale=self.scale, useMeanshiftGrouping=self.meanShift)

		#return a list of rectangles that tell where people are
		reality, self.people_rects = self.draw_rectangles(rects,self.frame)

		#updates history to help smooth over drops in frames
		if len(self.history) < 50:
			if reality:
				self.history.append(self.people_rects)
			else:
				self.history.pop(0)
		else:
			self.history.pop(0)
			if reality:
				self.history.append(self.people_rects)

		#draws frame
		cv2.namedWindow('frame', 0)
		cv2.resizeWindow('frame', 320, 240)

		cv2.imshow('frame',self.frame)
		cv2.waitKey(1)

		self.people = Rect_Array()
		if self.people_rects is not None:
			for (x, y, w, h) in self.people_rects:
				self.people_ranges = Rect()
				self.people_ranges.x = x
				self.people_ranges.y = y
				self.people_ranges.w = w
				self.people_ranges.h = h
				self.people.Rect_Array.append(self.people_ranges)

			self.body_pub.publish(self.people)
			#return self.people_ranges


	def draw_rectangles(self,rects, frame):
		"""
		draws rectangles in frame where people are, can use history or new rectangles depending on dropped frames
		"""
		#if current rects has no rects, then look through history, and if there was a very recent rectangle, then use that rectangle
		if len(rects) == 0 and len(self.history) > 0 and any(len(item) > 0 for item in self.history):
			for i in range(len(self.history)-1, -1, -1):
				if len(self.history[i]) > 0:
					hist = self.non_max_suppression_fast(self.history[i], .3)
					for (x, y, w, h) in hist:
						cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
					return (0, hist)
				return (0, [])

		else:
			rects = self.non_max_suppression_fast(rects, .3)
			for (x, y, w, h) in rects:
				cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
			return (1, rects)


	# Malisiewicz et al.
	def non_max_suppression_fast(self,boxes, overlapThresh):
		"""
		smooths out tracking by removing extraneous rectangles
		"""
		# if there are no boxes, return an empty list
		if len(boxes) == 0:
			return []

		# if the bounding boxes integers, convert them to floats --
		# this is important since we'll be doing a bunch of divisions
		boxes = boxes.astype("float")

		# initialize the list of picked indexes
		pick = []

		# grab the coordinates of the bounding boxes
		x1 = boxes[:,0]
		y1 = boxes[:,1]
		x2 = boxes[:,0] + boxes[:,2]
		y2 = boxes[:,1] + boxes[:,3]

		# compute the area of the bounding boxes and sort the bounding
		# boxes by the bottom-right y-coordinate of the bounding box
		area = (x2 - x1 + 1) * (y2 - y1 + 1)
		idxs = np.argsort(y2)

		# keep looping while some indexes still remain in the indexes
		# list
		while len(idxs) > 0:
			# grab the last index in the indexes list and add the
			# index value to the list of picked indexes
			last = len(idxs) - 1
			i = idxs[last]
			pick.append(i)

			# find the largest (x, y) coordinates for the start of
			# the bounding box and the smallest (x, y) coordinates
			# for the end of the bounding box
			xx1 = np.maximum(x1[i], x1[idxs[:last]])
			yy1 = np.maximum(y1[i], y1[idxs[:last]])
			xx2 = np.minimum(x2[i], x2[idxs[:last]])
			yy2 = np.minimum(y2[i], y2[idxs[:last]])

			# compute the width and height of the bounding box
			w = np.maximum(0, xx2 - xx1 + 1)
			h = np.maximum(0, yy2 - yy1 + 1)

			# compute the ratio of overlap
			overlap = (w * h) / area[idxs[:last]]

			# delete all indexes from the index list that have
			idxs = np.delete(idxs, np.concatenate(([last],
				np.where(overlap > overlapThresh)[0])))

		# return only the bounding boxes that were picked using the
		# integer data type
		return boxes[pick].astype("int")


	def run(self):
		"""
        main run function for body_detection
        """
		r = rospy.Rate(10)
		time.sleep(1)

		while not rospy.is_shutdown():
			self.find_bodies()
			r.sleep()


if __name__ == "__main__":
	Bodies = BodyDetector()
	Bodies.run()
