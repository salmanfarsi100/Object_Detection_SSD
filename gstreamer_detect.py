import gi
gi.require_version('Gst', '1.0')
from imutils.video import VideoStream
from imutils.video import FPS
import numpy as np
import argparse
import imutils
import time
from gi.repository import GObject, Gst, GLib
import sys
import numpy
import cv2
from datetime import datetime

vehicle_list = []		# vehicle bounding box metadata buffer
rgb_frames_list = []    # image metadata buffer
total_vehicles_detected = 0     # vehicles acccounted for in 'vehicle_list'

########## Vehicle Class ##########     # vehicle_list[] object class; described by the vehicle's tracking id, the number of frames it is tracked for and the coordinates of its bounding boxes

class Vehicle:
    def __init__(self, vehicle_id, frames_list=[], x1_list=[], y1_list=[], x2_list=[], y2_list=[]):
        self.vehicle_id = vehicle_id
        self.frames_list = frames_list
        self.x1_list = x1_list
        self.y1_list = y1_list
        self.x2_list = x2_list
        self.y2_list = y2_list

########## Vehicle Class ##########

########## RGB Frame Class ##########   # 'rgb_frames_list[]' object class; described by the frame number and the pixel matrix of the frame 

class RGB_Frame:
    def __init__(self, frame_iterator, rgb_image):
        self.frame_iterator = frame_iterator
        self.rgb_image = rgb_image

########## RGB Frame Class ##########

def IOU(x11, y11, x21, y21, x12, y12, x22, y22):		# intersection over union of two bounding boxes
    b1 = (x11, y11, x21, y21)
    b2 = (x12, y12, x22, y22)
    x1 = max(b1[0], b2[0])
    y1 = max(b1[1], b2[1])
    x2 = min(b1[2], b2[2])
    y2 = min(b1[3], b2[3])
    b1b2 = (x1, y1, x2, y2)
    area_b1b2 = (b1b2[2] - b1b2[0]) * (b1b2[3] - b1b2[1])
    area_b1 = (b1[2] - b1[0]) * (b1[3] - b1[1])
    area_b2 = (b2[2] - b2[0]) * (b2[3] - b2[1])
    iou = area_b1b2 / (area_b1+area_b2-area_b1b2)
    return iou

def check_overlap(x11, y11, x21, y21, x12, y12, x22, y22):		# is there an overlap?
    if (y12 > y21) or (y11 > y22):
        return False
    if (x12 > x21) or (x11 > x22):
        return False
    else:
        return True

def vehicles_detected():
    vehicle_count = 0
    for v in vehicle_list:
        if v.frames_list[-1] < (frame_number - 50):
            vehicle_count += 1
            print('\n vehicle id: ', v.vehicle_id, ' total frames = ', len(v.frames_list))
            for i, l in enumerate(v.frames_list):
                print('frame:', v.frames_list[i], 'x1:', v.x1_list[i], 'y1:',
                      v.y1_list[i], 'x2:', v.x2_list[i], 'y2:', v.y2_list[i])
    print(str(vehicle_count)+' vehicles detected')

# Constructing Argument Parse to input from Command Line
ap = argparse.ArgumentParser()
ap.add_argument("-p", "--prototxt", required=True, help='Path to prototxt')
ap.add_argument("-m", "--model", required=True, help='Path to model weights')
ap.add_argument("-c", "--confidence", type=float, default=0.7)
args = vars(ap.parse_args())

# Initialize Objects and corresponding colors which the model can detect
labels = ["background", "aeroplane", "bicycle", "bird",
          "boat", "bottle", "bus", "car", "cat", "chair", "cow",
          "diningtable", "dog", "horse", "motorbike", "person", "pottedplant",
          "sheep", "sofa", "train", "tvmonitor"]
colors = np.random.uniform(0, 255, size=(len(labels), 3))

# Loading Caffe Model
print('[Status] Loading Model...')
nn = cv2.dnn.readNetFromCaffe(args['prototxt'], args['model'])

time.sleep(2.0)
fps = FPS().start()
frame_number = 0
tracking_id = 0
y1 = 178
y2 = 477
midpoint = int((y1 + y2)/2)     # reference point of optimality

global stop
stop = 0

def bus_call(bus, message, loop):
    t = message.type
    if t == Gst.MessageType.EOS:
        sys.stdout.write("End of stream\n")
        print(total_vehicles_detected, ' vehicles detected')
        print("[Info] Elapsed time: {:.2f}".format(fps.elapsed()))
        print("[Info] FPS:  {:.2f}".format(fps.fps()))
        print("[Info] Total frames: ", frame_number)
        
        # vehicles_detected()
        
        quit()
        loop.quit()
    elif t == Gst.MessageType.WARNING:
        err, debug = message.parse_warning()
        sys.stderr.write("Warning: %s: %s\n" % (err, debug))
    elif t == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        sys.stderr.write("Error: %s: %s\n" % (err, debug))
        loop.quit()
    return True

def gst_to_opencv(sample):
    buf = sample.get_buffer()
    caps = sample.get_caps()
    # ~ print(caps.get_structure(0).get_value('format'))
    # ~ print(caps.get_structure(0).get_value('height'))
    # ~ print(caps.get_structure(0).get_value('width'))

    # ~ print(buf.get_size())

    arr = numpy.ndarray((caps.get_structure(0).get_value('height'), caps.get_structure(
        0).get_value('width'), 3), buffer=buf.extract_dup(0, buf.get_size()), dtype=numpy.uint8)
    return arr

def new_buffer(sink, data):
    global image_arr
    sample = sink.emit("pull-sample")
    arr = gst_to_opencv(sample)
    image_arr = arr
    return Gst.FlowReturn.OK


Gst.init(None)
image_arr = None

print("Creating Pipeline \n")
pipeline = Gst.Pipeline()

if not pipeline:
    sys.stderr.write("Unable to create Pipeline \n")

print("Creating Source \n")
source = Gst.ElementFactory.make('filesrc', 'file-source')
if not source:
    sys.stderr.write("Unable to create Source \n")

print("Creating H264Parser \n")
h264parser = Gst.ElementFactory.make("h264parse", "h264-parser")
if not h264parser:
    sys.stderr.write("Unable to create h264 Parser \n")

print("Creating Decoder \n")
decoder = Gst.ElementFactory.make("avdec_h264", "vdecoder")
if not h264parser:
    sys.stderr.write("Unable to create Decoder \n")

print("Creating Video Converter \n")
converter = Gst.ElementFactory.make("videoconvert", "converter")
if not converter:
    sys.stderr.write("Unable to create Video Converter \n")

print("Creating Appsink \n")
sink = Gst.ElementFactory.make("appsink", "sink")
if not sink:
    sys.stderr.write("Unable to create Appsink \n")

print("Playing file video.h264")
source.set_property('location', 'video.h264')

sink.set_property('wait-on-eos', False)
sink.set_property('drop', True)
sink.set_property('max-buffers', 60)
sink.set_property('emit-signals', True)

caps = Gst.caps_from_string(
    "video/x-raw, format=(string){BGR, GRAY8}; video/x-bayer, format=(string){rggb,bggr,grbg,gbrg}")
sink.set_property('caps', caps)
sink.connect("new-sample", new_buffer, sink)

print("Adding elements to Pipeline \n")
pipeline.add(source)
pipeline.add(h264parser)
pipeline.add(decoder)
pipeline.add(converter)
pipeline.add(sink)

print("Linking elements in the Pipeline \n")
source.link(h264parser)
h264parser.link(decoder)
decoder.link(converter)
converter.link(sink)

loop = GLib.MainLoop()

bus = pipeline.get_bus()
bus.add_signal_watch()
bus.connect("message", bus_call, loop)

print("Starting pipeline \n")

pipeline.set_state(Gst.State.PLAYING)

frame_number = 0

while True:
    message = bus.timed_pop_filtered(
        10000, Gst.MessageType.ANY)
    if image_arr is not None:  # where the magic happens

        frame = image_arr

        if type(frame) == type(None):
            break

        frame = imutils.resize(frame, width=1280)
        # frame = imutils.resize(frame, width=1920)
        (h, w) = frame.shape[:2]
        # print(h, w)
        
        rgb_frames_list.append(RGB_Frame(frame_number, frame))    # save current image to 'rgb_frames_list'
        if len(rgb_frames_list) > 250:      # drop expired frames; extend frame life by increasing this value (may affect performance)
            for x in range(50):
                del rgb_frames_list[x]
        
        cv2.line(frame, (0, int(0.2 * h)),
                 (w, int(0.2 * h)), (0, 255, 0), thickness=2)

        # Converting Frame to Blob
        blob = cv2.dnn.blobFromImage(cv2.resize(
            frame, (300, 300)), 0.007843, (300, 300), 127.5)

        # Passing Blob through network to detect and predict
        nn.setInput(blob)
        detections = nn.forward()

        # Loop over the detections
        for i in np.arange(0, detections.shape[2]):

            # Extracting the confidence of predictions
            confidence = detections[0, 0, i, 2]

            # Filtering out weak predictions
            if confidence > args["confidence"]:

                # Extracting the index of the labels from the detection
                # Computing the (x,y) - coordinates of the bounding box
                idx = int(detections[0, 0, i, 1])

                if idx == 7:

                    # Extracting bounding box coordinates
                    box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                    (startX, startY, endX, endY) = box.astype("int")

                    if startY >= (0.2 * h):		# neglecting boxes too far from the camera

                        if not vehicle_list:
                            temp_frames_list = []
                            temp_frames_list.append(frame_number)
                            temp_x1_list = []
                            temp_x1_list.append(startX)
                            temp_y1_list = []
                            temp_y1_list.append(startY)
                            temp_x2_list = []
                            temp_x2_list.append(endX)
                            temp_y2_list = []
                            temp_y2_list.append(endY)
                            vehicle_list.append(Vehicle(tracking_id, temp_frames_list,
                                                        temp_x1_list, temp_y1_list, temp_x2_list, temp_y2_list))
                            temp_track = 'id: ' + str(tracking_id)
                            tracking_id += 1

                        else:
                            iou_list = []
                            for v in vehicle_list:
                                frame_difference = frame_number - \
                                    v.frames_list[-1]
                                # ~ print('overlap? ', check_overlap(
                                # ~ v.x1_list[-1], v.y1_list[-1], v.x2_list[-1], v.y2_list[-1], startX, startY, endX, endY))
                                if check_overlap(v.x1_list[-1], v.y1_list[-1], v.x2_list[-1], v.y2_list[-1], startX, startY, endX, endY) and frame_difference < 5:
                                    intersection_over_union = IOU(
                                        v.x1_list[-1], v.y1_list[-1], v.x2_list[-1], v.y2_list[-1], startX, startY, endX, endY)
                                    # ~ print(
                                    # ~ 'operands: ', v.x1_list[-1], v.y1_list[-1], v.x2_list[-1], v.y2_list[-1], startX, startY, endX, endY)
                                    iou_list.append(intersection_over_union)
                                    # ~ print(intersection_over_union)
                                else:
                                    # ~ print(v.x1_list[-1], v.y1_list[-1], v.x2_list[-1],
                                    # ~ v.y2_list[-1], ' does not overlap with any bounding box')
                                    iou_list.append(0)

                            if not all([v == 0 for v in iou_list]):
                                max_value = max(iou_list)
                                max_index = iou_list.index(max_value)
                                # ~ print('iou list: ', iou_list)
                                # ~ print('frame number: ', frame_number, ' max iou: ', max_value, ' b_old: (', vehicle_list[max_index].x1_list[-1], ',', vehicle_list[
                                # ~ max_index].y1_list[-1], ',', vehicle_list[max_index].x2_list[-1], ',', vehicle_list[max_index].y2_list[-1], ') b: ', (startX, startY, endX, endY))
                                vehicle_list[max_index].frames_list.append(
                                    frame_number)
                                vehicle_list[max_index].x1_list.append(startX)
                                vehicle_list[max_index].y1_list.append(startY)
                                vehicle_list[max_index].x2_list.append(endX)
                                vehicle_list[max_index].y2_list.append(endY)
                                temp_track = 'id: ' + \
                                    str(vehicle_list[max_index].vehicle_id)
                            else:
                                temp_frames_list = []
                                temp_frames_list.append(frame_number)
                                temp_x1_list = []
                                temp_x1_list.append(startX)
                                temp_y1_list = []
                                temp_y1_list.append(startY)
                                temp_x2_list = []
                                temp_x2_list.append(endX)
                                temp_y2_list = []
                                temp_y2_list.append(endY)
                                vehicle_list.append(Vehicle(
                                    tracking_id, temp_frames_list, temp_x1_list, temp_y1_list, temp_x2_list, temp_y2_list))
                                temp_track = 'id: ' + str(tracking_id)
                                tracking_id += 1

                        cv2.rectangle(frame, (startX, startY),
                                      (endX, endY), colors[idx], 2)

                        y = startY - 15 if startY - 15 > 15 else startY + 15
                        label = "{} {}: {:.2f}%: {} {} {} {}".format(
                            temp_track, labels[idx], confidence * 100, startX, startY, endX, endY)
                        cv2.putText(frame, label, (startX, y),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, colors[idx], 2)

        # cv2.imshow("frame", frame)

        cv2.imwrite("/home/ee/Caffe-SSD-Object-Detection/Object Detection Caffe/stream/frame_number=" +
        str(frame_number)+".jpg", frame)    # save current frame to disk
        
        frame_number += 1

        if stop == 1:
            break
        
        for i, x in enumerate(vehicle_list):
            frame_lag = frame_number - x.frames_list[-1]    # how far behind the current frame is the last tracking frame of the vehicle
            l = len(x.frames_list)
            if (frame_lag > 50 and l < 9):      # eliminate false (without sufficient number of frames) tracking trains
                print('insufficient frames, vehicle '+str(vehicle_list[i].vehicle_id)+' deleted')
                del vehicle_list[i]
                break
            
            if (frame_lag > 100 and frame_lag < 200):    # optimal frame extractor
                total_vehicles_detected += 1
                # print('midpoint', midpoint)
                yc_list_temp = []   # temporary list of 'y' centres
                xc_list_temp = []   # temporary list of 'x' centres
                for j, c in enumerate(x.frames_list):   # populate a list of 'y' centres
                    yc = int((x.y1_list[j] + x.y2_list[j]) / 2)
                    yc_list_temp.append(yc)
                    xc = int((x.x1_list[j] + x.x2_list[j]) / 2)
                    xc_list_temp.append(xc)
                # print('yc_list_temp', yc_list_temp)
                # print('xc_list_temp', xc_list_temp)
                distance_from_center = [d - midpoint for d in yc_list_temp]
                # print('dis_from_c', distance_from_center)
                pos = (np.abs(distance_from_center)).argmin()
                # print('pos', pos)
                temp_frame_number = x.frames_list[pos]
                # print('temp_frame_number', temp_frame_number)
                temp_id = x.vehicle_id
                # print('temp_id', temp_id)
                temp_x1 = int(x.x1_list[pos])
                temp_x2 = int(x.x2_list[pos])
                temp_y1 = int(x.y1_list[pos])
                temp_y2 = int(x.y2_list[pos])
                # print('crop coordinates', (temp_x1, temp_y1, temp_x2, temp_y2))
                now = datetime.now()
                dt_string = now.strftime('%d-%m-%Y_%H-%M-%S')
                print('train expired, vehicle ' + str(vehicle_list[i].vehicle_id) + ' deleted')
                del vehicle_list[i]     # discard the vehicle saved to disk
                frame_finder = 0
                for f in rgb_frames_list:   # find the optimal frame in 'rgb_frames_list'
                    if f.frame_iterator == temp_frame_number:
                        break
                    else:
                        frame_finder += 1
                # print('frame_finder', frame_finder)
                # print('frame shape', rgb_frames_list[frame_finder].rgb_image.shape)
                crop = (rgb_frames_list[frame_finder].rgb_image)[temp_y1:temp_y2, temp_x1:temp_x2]      # crop the part of the frame bounding the vehicle
                # print(crop.shape)
                # print(dt_string)
                cv2.imwrite("/home/ee/Caffe-SSD-Object-Detection/Object Detection Caffe/optimal_frame/trid_frno_time=" + str(temp_id) + '_' + str(temp_frame_number) + "_" + str(dt_string[11:19])+ ".jpg", crop)    # save current frame to disk
                break
            
            if frame_lag > 200:     # 'vehicle_list' buffer cleaner; drops expired tracking trains
                print('train expired, vehicle ' + str(vehicle_list[i].vehicle_id) + ' deleted', '\n')
                del vehicle_list[i]
                break
        
        key = cv2.waitKey(1) & 0xFF

        if key == ord('q'):
            print("[Status] Video Stream Manually Terminated")
            break

        fps.update()

        fps.stop()
    
        if message:
            if message.type == Gst.MessageType.ERROR:
                err, debug = message.parse_error()
                print(("Error received from element %s: %s" %
                       (message.src.get_name(), err)))
                print(("Debugging information: %s" % debug))
                break
            elif message.type == Gst.MessageType.EOS:
                stop = 1
                print("End-Of-Stream reached.")
                print(str(total_vehicles_detected) + ' vehicles detected')
                fps.stop()
                cv2.destroyAllWindows()
                break
            elif message.type.STATE_CHANGED:
                if isinstance(message.src, Gst.Pipeline):
                    old_state, new_state, pending_state = message.parse_state_changed()
                    print(("Pipeline state changed from %s to %s." %
                           (old_state.value_nick, new_state.value_nick)))
            else:
                print("Unexpected message received.")

    if stop == 1:
        break

fps.stop()
cv2.destroyAllWindows()

print("[Info] Elapsed time: {:.2f}".format(fps.elapsed()))
print("[Info] FPS:  {:.2f}".format(fps.fps()))
print("[Info] Total frames: ", frame_number)

# vehicles_detected()

pipeline.set_state(Gst.State.NULL)
