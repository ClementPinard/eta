"""
ETA interface to the YOLOv4 object detection model.

This module assumes that the
`voxel51/darkflow <https://github.com/voxel51/darkflow>`_ repository has been
cloned and pip-installed on your machine.

Copyright 2017-2020, Voxel51, Inc.
voxel51.com

Brian Moore, brian@voxel51.com
"""
# pragma pylint: disable=redefined-builtin
# pragma pylint: disable=unused-wildcard-import
# pragma pylint: disable=wildcard-import
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from builtins import *

# pragma pylint: enable=redefined-builtin
# pragma pylint: enable=unused-wildcard-import
# pragma pylint: enable=wildcard-import

import logging
import warnings

import eta.constants as etac
from eta.core.config import Config, ConfigError
import eta.core.geometry as etag
import eta.core.learning as etal
import eta.core.models as etam
import eta.core.objects as etao
import eta.core.tfutils as etat
import eta.core.utils as etau


_ERROR_MSG = """

You must clone and install a repository in order to use a YOLO model:

mkdir -p '{0}'
git clone https://github.com/voxel51/darkflow '{0}'
pip install -e '{0}'

""".format(
    etac.DARKFLOW_DIR
)

dnb = etau.lazy_import("darkflow.net.build", error_msg=_ERROR_MSG)


logger = logging.getLogger(__name__)


class YOLODetectorConfig(Config, etal.HasDefaultDeploymentConfig):
    """YOLO object detector configuration settings.

    Note that `config_dir` and `config_path` are passed through
    `eta.core.utils.fill_config_patterns` at load time, so they can contain
    patterns to be resolved.

    Note that this class implements the `HasDefaultDeploymentConfig` mixin, so
    if a published model is provided via the `model_name` attribute, then any
    omitted fields present in the default deployment config for the published
    model will be automatically populated.

    Attributes:
        model_name: the name of the published model to load. If this value is
            provided, `model_path` does not need to be
        model_path: the path to a Darkflow model weights file in `.weights`
            format to load. If this value is provided, `model_name` does not
            need to be
        config_dir: path to the darkflow configuration directory
        config_path: path to the darkflow model architecture file
    """

    def __init__(self, d):
        self.model_name = self.parse_string(d, "model_name", default=None)
        self.model_path = self.parse_string(d, "model_path", default=None)

        # Loads any default deployment parameters, if possible
        if self.model_name:
            d = self.load_default_deployment_params(d, self.model_name)

        self.config_dir = etau.fill_config_patterns(
            self.parse_string(d, "config_dir")
        )
        self.config_path = etau.fill_config_patterns(
            self.parse_string(d, "config_path")
        )

        self._validate()

    def _validate(self):
        if not self.model_name and not self.model_path:
            raise ConfigError(
                "Either `model_name` or `model_path` must be provided"
            )


class YOLODetector(etal.ObjectDetector):
    """Interface to the Darkflow YOLO object detector."""

    def __init__(self, config):
        """Constructs a YOLODetector instance.

        Args:
            config: a YOLODetectorConfig instance
        """
        self.config = config

        # Get path to model
        if self.config.model_path:
            model_path = self.config.model_path
        else:
            # Downloads the published model, if necessary
            model_path = etam.download_model(self.config.model_name)

        try:
            # Get GPU usage from ETA
            tf_config = etat.make_tf_config()
            gpu = tf_config.gpu_options.per_process_gpu_memory_fraction
            logger.info("Sending gpu: %g (from ETA config) to TFNet", gpu)
        except AttributeError:
            # By default, try to use all GPU
            gpu = 1.0
            logger.info("Sending gpu: %g (default) to TFNet", gpu)

        # Blocks pesky warnings generated by darkflow that we don't care about
        with warnings.catch_warnings(record=True):
            self._tfnet = dnb.TFNet(
                {
                    "config": self.config.config_dir,
                    "model": self.config.config_path,
                    "load": model_path,
                    "json": True,
                    "summary": None,
                    "gpu": gpu,
                }
            )

    def detect(self, img):
        """Performs object detection on the input image.

        Args:
            img: an image

        Returns:
            objects: A DetectedObjectContainer describing the detected objects
                in the image
        """
        result = self._tfnet.return_predict(img)
        objects = [_to_detected_object(yd, img) for yd in result]
        return etao.DetectedObjectContainer(objects=objects)


def _to_detected_object(yd, img):
    """Converts a YOLO detection to a DetectedObject.

    Args:
        yd: a YOLO detection dictionary
        img: the image on which the prediction was made

    Returns:
        a DetectedObject
    """
    tl = yd["topleft"]
    br = yd["bottomright"]
    bbox = etag.BoundingBox.from_abs_coords(
        tl["x"], tl["y"], br["x"], br["y"], img=img
    )
    return etao.DetectedObject(yd["label"], bbox, confidence=yd["confidence"])
