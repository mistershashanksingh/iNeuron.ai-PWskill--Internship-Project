import streamlit as st
import numpy as np
import imutils
import cv2
import os
from PIL import Image, ImageEnhance
from keras.applications.mobilenet_v2 import preprocess_input
from keras.utils import img_to_array
from keras.models import load_model
from streamlit_webrtc import VideoTransformerBase, webrtc_streamer




# Setting custom Page Title and Icon with changed layout and sidebar state
st.set_page_config(page_title='Face Mask Detector', page_icon='😷', layout='centered', initial_sidebar_state='expanded')


def local_css(file_name):
    """ Method for reading styles.css and applying necessary changes to HTML"""
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)


def mask_image():
    global RGB_img
    # load our serialized face detector model from disk
    print("[INFO] loading face detector model...")
    prototxtPath = os.path.sep.join(["face_detector", "deploy.prototxt"])
    weightsPath = os.path.sep.join(["face_detector",
                                    "res10_300x300_ssd_iter_140000.caffemodel"])
    net = cv2.dnn.readNet(prototxtPath, weightsPath)

    # load the face mask detector model from disk
    print("[INFO] loading face mask detector model...")
    model = load_model("mask_detector.model")

    # load the input image from disk and grab the image spatial
    # dimensions
    image = cv2.imread("./dataset/img/img11.jpg")
    (h, w) = image.shape[:2]

    # construct a blob from the image
    blob = cv2.dnn.blobFromImage(image, 1.0, (300, 300),
                                 (104.0, 177.0, 123.0))

    # pass the blob through the network and obtain the face detections
    print("[INFO] computing face detections...")
    net.setInput(blob)
    detections = net.forward()

    # loop over the detections
    for i in range(0, detections.shape[2]):
        # extract the confidence (i.e., probability) associated with
        # the detection
        confidence = detections[0, 0, i, 2]

        # filter out weak detections by ensuring the confidence is
        # greater than the minimum confidence
        if confidence > 0.5:
            # compute the (x, y)-coordinates of the bounding box for
            # the object
            box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
            (startX, startY, endX, endY) = box.astype("int")

            # ensure the bounding boxes fall within the dimensions of
            # the frame
            (startX, startY) = (max(0, startX), max(0, startY))
            (endX, endY) = (min(w - 1, endX), min(h - 1, endY))

            # extract the face ROI, convert it from BGR to RGB channel
            # ordering, resize it to 224x224, and preprocess it
            face = image[startY:endY, startX:endX]
            face = cv2.cvtColor(face, cv2.COLOR_BGR2RGB)
            face = cv2.resize(face, (224, 224))
            face = img_to_array(face)
            face = preprocess_input(face)
            face = np.expand_dims(face, axis=0)

            # pass the face through the model to determine if the face
            # has a mask or not
            (mask, withoutMask) = model.predict(face)[0]

            # determine the class label and color we'll use to draw
            # the bounding box and text
            label = "Mask" if mask > withoutMask else "No Mask"
            color = (0, 255, 0) if label == "Mask" else (0, 0, 255)

            # include the probability in the label
            label = "{}: {:.2f}%".format(label, max(mask, withoutMask) * 100)

            # display the label and bounding box rectangle on the output
            # frame
            cv2.putText(image, label, (startX, startY - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 2)
            cv2.rectangle(image, (startX, startY), (endX, endY), color, 2)
            RGB_img = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
mask_image()


def get_video_faces(frame, faceNet, maskNet):
    (h, w) = frame.shape[:2]
    blob = cv2.dnn.blobFromImage(frame, 1.0, (300, 300),
                                 (104.0, 177.0, 123.0))
    faceNet.setInput(blob)
    detections = faceNet.forward()
    faces = []
    locs = []
    preds = []

    for i in range(0, detections.shape[2]):
        confidence = detections[0, 0, i, 2]
        # filter out weak detections by ensuring the confidence is
        # greater than the minimum confidence

        if confidence > 0.9:
            box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
            (startX, startY, endX, endY) = box.astype("int")

            (startX, startY) = (max(0, startX), max(0, startY))
            (endX, endY) = (min(w - 1, endX), min(h - 1, endY))

            face = frame[startY:endY, startX:endX]
            face = cv2.cvtColor(face, cv2.COLOR_BGR2RGB)
            face = cv2.resize(face, (224, 224))
            face = img_to_array(face)
            face = preprocess_input(face)

            faces.append(face)
            locs.append((startX, startY, endX, endY))

    if len(faces) > 0:
        faces = np.array(faces, dtype="float32")
        preds = maskNet.predict(faces, batch_size=32)

    return (locs, preds)


# load our serialized face detector model from disk
prototxtPath = os.path.sep.join(["./face_detector/", "deploy.prototxt"])
weightsPath = os.path.sep.join(["./face_detector/", "res10_300x300_ssd_iter_140000.caffemodel"])
faceNet = cv2.dnn.readNet(prototxtPath, weightsPath)

# load the face mask detector model from disk
maskNet = load_model("./mask_detector.model")


class VideoTransformer(VideoTransformerBase):
    def transform(self, frame):
        print('getting frame')
        frame = frame.to_ndarray(format="bgr24")
        frame = imutils.resize(frame, width=400)

        # detect faces in the frame and determine if they are wearing a
        # face mask or not
        (locs, preds) = get_video_faces(frame, faceNet, maskNet)
        print('predicting face mask')

        # loop over the detected face locations and their corresponding
        # locations
        for (box, pred) in zip(locs, preds):
            # unpack the bounding box and predictions
            (startX, startY, endX, endY) = box
            (mask, withoutMask) = pred
            print('loading predictions')

            # determine the class label and color we'll use to draw
            # the bounding box and text
            label = "Mask" if mask > withoutMask else "No Mask"
            color = (0, 255, 0) if label == "Mask" else (0, 0, 255)
            print('printing the mask detections')

            # display the label and bounding box rectangle on the output
            # frame
            cv2.putText(frame, label, (startX, startY - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 2)
            cv2.rectangle(frame, (startX, startY), (endX, endY), color, 2)
            print('finishing process')

        return frame

def mask_detection():
    local_css("css/style.css")
    st.markdown('<h1 align="center">😷 Face Mask Detection</h1>', unsafe_allow_html=True)
    activities = ["Image", "Webcam"]
    st.set_option('deprecation.showfileUploaderEncoding', False)
    st.sidebar.markdown("# Mask Detection on?")
    choice = st.sidebar.selectbox("Choose among the given options:", activities)

    if choice == 'Image':
        st.markdown('<h2 align="center">Detection on Image</h2>', unsafe_allow_html=True)
        st.markdown("### Upload your image here ⬇")
        image_file = st.file_uploader("", type=['jpg', 'jpeg'])  # upload image
        if image_file is not None:
            our_image = Image.open(image_file)  # making compatible to PIL
            im = our_image.save('./dataset/img/img11.jpg')
            saved_image = st.image(image_file, caption='', use_column_width=True)
            st.markdown('<h3 align="center">Image uploaded successfully!</h3>', unsafe_allow_html=True)
            if st.button('Click to start Processing'):
                st.image(RGB_img, use_column_width=True)
            else:
                st.markdown('<h3 align="center">Image limit is 200MB</h3>', unsafe_allow_html=True)

    if choice == 'Webcam':
        st.markdown('<h2 align="center">Detection on Webcam</h2>', unsafe_allow_html=True)
        st.markdown('<h3 align="center">Allow webcam Permission </h3>', unsafe_allow_html=True)
        webrtc_streamer(key="example", video_transformer_factory=VideoTransformer)
        
        
mask_detection()