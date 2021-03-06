
"""

detectionserver

Contains routes for the RESTful API and for heavily templated pages.

Sorry for the crap comments, there is more description in the README.md

"""

from flask import request, jsonify, render_template
from point import Point
import config
import json
import localization as tri
import fingerprint
import plot
import db
import os


MAX_NODE_EVENTS = config.max_node_events
MIN_CONFIDENCE = config.min_confidence

CREATE_PLOTS = False
IMG_DIR = "imgs/"


def request_to_detection_event(req_dict, confidence):
    """

    Converts the request's post form to a detection event.

    @param req_dict The post form from the request

    @param confidence The confidence of the recognition

    @return A detection event created from the request's post form

    """

    return tri.DetectionEvent(
        float(req_dict["x"]),
        float(req_dict["y"]),
        float(confidence),
        float(req_dict["spl"]),
        float(req_dict["timestamp"])
    )


@config.app.route("/notify", methods=["POST"])
def post_notify():
    """

    This function is called when a node notifies the server of a new detection
    event.

    """

    req_print = json.loads(request.form["fingerprint"])

    sound_name, sound_class, confidence = db.get_best_matching_print(req_print)

    if confidence > MIN_CONFIDENCE:
        if not sound_name in config.detection_events.keys():
            config.detection_events[sound_name] = list()
            config.class_detection_events[sound_class] = list()

        config.new_data[sound_name] = True

        if len(config.detection_events[sound_name]) + 1 >= MAX_NODE_EVENTS:
            del config.detection_events[sound_name][0]

        d_event = request_to_detection_event(request.form, confidence)

        config.detection_events[sound_name].append(d_event)

        config.class_detection_events[sound_class].append(d_event)

    return jsonify(
        error=0,
        message="No error",
        name=sound_name,
        confidence=confidence,
        added=confidence > MIN_CONFIDENCE
    )


@config.app.route("/locations/<sound_name>", methods=["GET"])
def get_sound_locations(sound_name):
    """

    Gets the sound position given the sound name

    """

    if not sound_name in config.detection_events.keys():
        return json.dumps([])

    radius, spl, _ = db.get_reference_data(sound_name)

    location_list = tri.determine_sound_locations(
        radius, spl,
        config.detection_events[sound_name],
        disp=0
    )

    ret_list = list()

    for location in location_list:
        ret_list.append(location.to_dict())

    return json.dumps(ret_list)


@config.app.route("/class/locations/<class_name>", methods=["GET"])
def get_class_locations(class_name):
    """

    HIGHLY EXPERIMENTAL: DO NOT FUCK WITH!

    """

    if not class_name in config.class_detection_events.keys():
        return json.dumps([])

    # I can do the average like this because we are assuming we are trying
    # to track the same class of things, so the reference data must be
    # similar
    radius, spl = db.get_class_reference_data(class_name)

    location_list = tri.determine_sound_locations(
        radius, spl,
        config.class_detection_events[class_name],
        disp=0
    )

    ret_list = list()

    for location in location_list:
        ret_list.append(location.to_dict())

    return json.dumps(ret_list)



@config.app.route("/viewer/<sound_name>", methods=["GET"])
def get_position_viewer(sound_name):
    """

    Allows the user to view the tracking information for a given sound

    """

    if not sound_name in config.detection_events.keys():
        return render_template("graph.html", sound_name=sound_name)

    radius, spl, _ = db.get_reference_data(sound_name)

    location_list = tri.determine_sound_locations(
        radius, spl,
        config.detection_events[sound_name],
        disp=0
    )

    img_path = IMG_DIR + sound_name + ".png"
    img_web_path = "/" + img_path

    if config.new_data[sound_name] and CREATE_PLOTS:
        plot.plot_detection_events(
            location_list,
            radius, spl,
            config.detection_events[sound_name],
            img_path
        )

        config.new_data[sound_name] = False

    ret_list = list()

    for location in location_list:
        ret_list.append(
            {
                "confidence": round(location.confidence, 3),
                "position": location.position
            }
        )

    r_template = render_template(
        "graph.html",
        img_path=img_web_path,
        location_list=ret_list,
        sound_name=sound_name,
        detection_events=config.detection_events[sound_name],
        r_ref=radius,
        l_ref=spl
    )

    return r_template


@config.app.route("/upload", methods=["GET", "POST"])
def get_post_upload():
    """

    Function is called when a user wants to upload sound and meta-data
    to the database.

    """

    file_key = "sound_file"
    upload_folder = "sounds"
    if request.method == "POST" and file_key in request.files:
        sound_file = request.files[file_key]
        file_path = os.path.join(
            upload_folder,
            request.form["sound_name"] + ".wav"
        )

        sound_file.save(file_path)
        db.insert_reference(
            request.form["sound_name"],
            fingerprint.get_fingerprint(file_path),
            float(request.form["r_ref"]),
            float(request.form["l_ref"]),
            request.form["class"]
        )
    return render_template("upload.html")


@config.app.route("/names", methods=["GET"])
def get_sound_names():
    return jsonify(names=db.get_list_of_names())


