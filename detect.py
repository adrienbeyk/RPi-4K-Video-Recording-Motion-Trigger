from imutils.video import VideoStream
import datetime
import argparse
import imutils
import cv2
import shlex
import subprocess
import time

SKIP_RECORDING = False

def do_ffmpeg_capture():
	'''
	We want to run this in shell:
	$ ffmpeg -f v4l2 -video_size 4096x2160 -input_format mjpeg -i /dev/video0 -c:v copy output.mkv -y -hide_banner
	'''
	wait_device_available()

	seconds_to_capture = 5
	timeout = seconds_to_capture + 10
	duration = f"00:00:{seconds_to_capture}" # hh:mm:ss[.xxx] syntax
	cmd = f"ffmpeg -f v4l2 -video_size 4096x2160 -input_format mjpeg -i /dev/video0 -t {duration} -c:v copy {int(time.time())}.mkv" \
		" -y -hide_banner"
	while True:
		try:
			print("recording...")
			ret = subprocess.run(shlex.split(cmd), timeout=timeout).returncode
			print(f"ffmpeg finished capture with exit code {ret}")
			return
		except subprocess.TimeoutExpired:
			print("ffmpeg hanged, retrying...")
			continue

def main():
	'''
	Main program loop
	'''
	vs = create_cv2()

	force_capture = False

	# initialize the first frame in the video stream
	firstFrame = None

	last_motion_timestamp = None
	last_capture_timestamp = datetime.datetime.now()
	# Since we restart the webcam between ffmpeg and opencv2 invocations,
	# it needs time to adjust to its surroundings (exposure adjustments, etc).
	# Otherwise it's easy to enter capture loops due to unstable exposure.
	ghosting_interval = datetime.timedelta(seconds=2)

	# loop over the frames of the video
	while True:
		# grab the current frame and initialize the occupied/unoccupied
		# text
		frame = vs.read()
		text = "Unoccupied"

		# if the frame could not be grabbed, then we have reached the end
		# of the video
		if frame is None:
			break

		# resize the frame, convert it to grayscale, and blur it
		frame = imutils.resize(frame, width=500)
		gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
		gray = cv2.GaussianBlur(gray, (21, 21), 0)

		# if the first frame is None, initialize it
		if firstFrame is None:
			firstFrame = gray
			continue

		# compute the absolute difference between the current frame and
		# first frame
		frameDelta = cv2.absdiff(firstFrame, gray)
		# import pdb; pdb.set_trace()
		thresh = cv2.threshold(frameDelta, 25, 255, cv2.THRESH_BINARY)[1]
	 
		# dilate the thresholded image to fill in holes, then find contours
		# on thresholded image
		thresh = cv2.dilate(thresh, None, iterations=2)
		cnts = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL,
			cv2.CHAIN_APPROX_SIMPLE)
		cnts = imutils.grab_contours(cnts)
	 
		curr_timestamp = datetime.datetime.now()
		motion_detected = False
		# loop over the contours
		for c in cnts:
			# if the contour is too small, ignore it
			if cv2.contourArea(c) < args.min_area:
				continue
			
			motion_detected = True
			firstFrame = None
			last_motion_timestamp = datetime.datetime.now()

			# compute the bounding box for the contour, draw it on the frame,
			# and update the text
			(x, y, w, h) = cv2.boundingRect(c)
			cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
			text = "Occupied"
			break

		timestamp_str = curr_timestamp.strftime("%A %d %B %Y %I:%M:%S%p")
		not_too_fast = curr_timestamp > (last_capture_timestamp + ghosting_interval)
		if (motion_detected and not_too_fast) or force_capture:
			force_capture = False
			print(f"MOTION DETECTED {timestamp_str}")
			stop_cv2_and_begin_capture(vs)
			vs = restart_cv2(vs)
			last_capture_timestamp = datetime.datetime.now()

		# draw the text and timestamp_str on the frame
		cv2.putText(frame, "Room Status: {}".format(text), (10, 20),
			cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
		cv2.putText(frame, timestamp_str,
			(10, frame.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)
	 
		# show the frame and record if the user presses a key
		cv2.imshow("Security Feed", frame)
		cv2.imshow("Thresh", thresh)
		cv2.imshow("Frame Delta", frameDelta)

		key = chr(cv2.waitKey(1) & 0xFF)
		if key == "f":
			force_capture = True
		elif key == "q":
			break
 
	shutdown_cv2(vs)
	cv2.destroyAllWindows()


'''
Begin utility functions
'''

def device_busy():
	'''
	Returns true when device is still busy (just in case cv2 didn't close it in time).
	But this is likely not needed anymore due to call to vs.stream.release().
	'''
	cmd = "lsof /dev/video0"
	ret = subprocess.run(shlex.split(cmd)).returncode
	return ret == 0


def wait_device_available():
	'''
	Spins forever until the device is free.
	'''
	while device_busy():
		print("waiting...")
		time.sleep(0.5)

def stop_cv2_and_begin_capture(vs):
	'''
	Do nothing if SKIP_RECORDING is set
	'''
	if SKIP_RECORDING:
		print("skipping recording as instructed")
		return
	shutdown_cv2(vs)
	do_ffmpeg_capture()

def create_cv2():
	# TODO: submit pull request to imutils to pass CAP_FFMPEG to cv2
	vs = VideoStream(src=0).start()
	time.sleep(2.0)
	return vs

def shutdown_cv2(vs):
	# cleanup the camera and close any open windows
	vs.stop()
	vs.stream.release()

def restart_cv2(vs):
	'''
	Return our passed-in VideoStream if SKIP_RECORDING is set.
	Otherwise create and return a new VideoStream instance.
	'''
	if SKIP_RECORDING:
		return vs
	# Sometimes ffmpeg fails to vmalloc (we run out of memory):
	# <4>[12331.355688] ffmpeg: vmalloc: allocation failure: 17694720 bytes, mode:0x6080c0(GFP_KERNEL|__GFP_ZERO), nodemask=(null)
	# which causes lots of this printed to console:
	# 	VIDIOC_QBUF: Invalid argument
	# and we will get terminated
	return create_cv2()

if __name__ == '__main__':
	ap = argparse.ArgumentParser()
	ap.add_argument("-n", "--no-rec", dest="no_rec", action="store_true", default=False, help="disable recording")
	ap.add_argument("-a", "--min-area", type=int, default=500, help="minimum area size")
	args = ap.parse_args()

	SKIP_RECORDING = args.no_rec
	 
	main()

