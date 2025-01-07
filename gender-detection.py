from inaSpeechSegmenter import Segmenter


def check_gender(segmentation):
    genders = [
        label for label, start, end in segmentation if label in ["male", "female"]
    ]
    if "male" in genders:
        return "male"
    elif "female" in genders:
        return "female"
    else:
        return "unknown"


def gender_detection(audio):
    media = "2.mp3"
    seg = Segmenter()
    segmentation = seg(media)

    gender = check_gender(segmentation)
    return gender
