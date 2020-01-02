#!/usr/bin/env python
'''
A module that uses an `eta.core.learning.ImageClassifier` to classify the
detected objects in images or videos.

Info:
    type: eta.core.types.Module
    version: 0.1.0

Copyright 2017-2019, Voxel51, Inc.
voxel51.com

Brian Moore, brian@voxel51.com
'''
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
import os
import sys

from eta.core.config import Config, ConfigError
import eta.core.image as etai
import eta.core.features as etaf
import eta.core.learning as etal
import eta.core.module as etam
import eta.core.utils as etau
import eta.core.video as etav


logger = logging.getLogger(__name__)


class ApplyClassifierToObjectsConfig(etam.BaseModuleConfig):
    '''Module configuration settings.

    Attributes:
        data (DataConfig)
        parameters (ParametersConfig)
    '''

    def __init__(self, d):
        super(ApplyClassifierToObjectsConfig, self).__init__(d)
        self.data = self.parse_object_array(d, "data", DataConfig)
        self.parameters = self.parse_object(d, "parameters", ParametersConfig)


class DataConfig(Config):
    '''Data configuration settings.

    Inputs:
        video_path (eta.core.types.Video): the input video
        input_labels_path (eta.core.types.VideoLabels): a VideoLabels file
            containing detected objects in the input video
        image_path (eta.core.types.Image): [None] the input image
        input_image_labels_path (eta.core.types.ImageLabels): [None] an
            ImageLabels file containing the detected objects in `image_path`
        images_dir (eta.core.types.ImageFileDirectory): [None] an input
            directory of images
        input_image_set_labels_path (eta.core.types.ImageSetLabels): [None] an
            ImageSetLabels file describing the detected objects in `images_dir`

    Outputs:
        output_labels_path (eta.core.types.VideoLabels): a VideoLabels file
            containing the predictions generated by processing `video_path`
        video_features_dir (eta.core.types.VideoObjectsFeaturesDirectory):
            [None] a directory in which to write features for the detected
            objects in each frame of `video_path`. If provided, the classifier
            used must support generating features
        output_image_labels_path (eta.core.types.ImageLabels): [None] an
            ImageLabels file containing the predictions generated by
            processing `image_path`
        image_features_dir (eta.core.types.ImageObjectsFeaturesDirectory):
            [None] a directory in which to write features for the objects in
            `image_path`. If provided, the classifier used must support
            generating features
        output_image_set_labels_path (eta.core.types.ImageSetLabels): [None] an
            ImageSetLabels file containing the predictions generated by
            processing `images_dir`
        image_set_features_dir (eta.core.types.ImageSetObjectsFeaturesDirectory):
            [None] a directory in which to write features for the objects in
            the images in `images_dir`.  If provided, the classifier used must
            support generating features
    '''

    def __init__(self, d):
        # Single video
        self.video_path = self.parse_string(d, "video_path", default=None)
        self.input_labels_path = self.parse_string(
            d, "input_labels_path", default=None)
        self.output_labels_path = self.parse_string(
            d, "output_labels_path", default=None)
        self.video_features_dir = self.parse_string(
            d, "video_features_dir", default=None)

        # Single image
        self.image_path = self.parse_string(d, "image_path", default=None)
        self.input_image_labels_path = self.parse_string(
            d, "input_image_labels_path", default=None)
        self.output_image_labels_path = self.parse_string(
            d, "output_image_labels_path", default=None)
        self.image_features_dir = self.parse_string(
            d, "image_features_dir", default=None)

        # Directory of images
        self.images_dir = self.parse_string(d, "images_dir", default=None)
        self.input_image_set_labels_path = self.parse_string(
            d, "input_image_set_labels_path", default=None)
        self.output_image_set_labels_path = self.parse_string(
            d, "output_image_set_labels_path", default=None)
        self.image_set_features_dir = self.parse_string(
            d, "image_set_features_dir", default=None)

        self._validate()

    def _validate(self):
        if self.video_path:
            if not self.input_labels_path:
                raise ConfigError(
                    "`input_labels_path` is required when `video_path` is "
                    "set")

            if not self.output_labels_path:
                raise ConfigError(
                    "`output_labels_path` is required when `video_path` is "
                    "set")

        if self.image_path:
            if not self.input_image_labels_path:
                raise ConfigError(
                    "`input_image_labels_path` is required when `image_path` "
                    "is set")

            if not self.output_image_labels_path:
                raise ConfigError(
                    "`output_image_labels_path` is required when `image_path` "
                    "is set")

        if self.images_dir:
            if not self.input_image_set_labels_path:
                raise ConfigError(
                    "`input_image_set_labels_path` is required when "
                    "`images_dir` is set")

            if not self.output_image_set_labels_path:
                raise ConfigError(
                    "`output_image_set_labels_path` is required when "
                    "`images_dir` is set")


class ParametersConfig(Config):
    '''Parameter configuration settings.

    Parameters:
        classifier (eta.core.types.ImageClassifier): an
            `eta.core.learning.ImageClassifierConfig` JSON describing the
            `eta.core.learning.ImageClassifier` to use
        labels (eta.core.types.Array): [None] an optional list of object
            labels to classify. By default, all objects are classified
        bb_padding (eta.core.types.Number): [None] the padding to apply to each
            dimension of the bounding box before classification
        force_square (eta.core.types.Boolean): [False] whether to minimally
            manipulate the object bounding boxes into squares before extraction
        min_height_pixels (eta.core.types.Number): [None] a minimum height,
            in pixels, for a bounding box to be classified
        confidence_threshold (eta.core.types.Number): [None] the minimum
            confidence required for a label to be saved
        record_top_k_probs (eta.core.types.Number): [None] top-k class
            probabilities to record for the predictions
    '''

    def __init__(self, d):
        self.classifier = self.parse_object(
            d, "classifier", etal.ImageClassifierConfig)
        self.labels = self.parse_array(d, "labels", default=None)
        self.bb_padding = self.parse_number(d, "bb_padding", default=None)
        self.force_square = self.parse_bool(d, "force_square", default=False)
        self.min_height_pixels = self.parse_number(
            d, "min_height_pixels", default=None)
        self.confidence_threshold = self.parse_number(
            d, "confidence_threshold", default=None)
        self.record_top_k_probs = self.parse_number(
            d, "record_top_k_probs", default=None)


def _build_object_filter(labels):
    if labels is None:
        logger.info("Classifying all objects")
        filter_fcn = lambda objs: objs
    else:
        logger.info("Classifying %s", labels)
        obj_filters = [lambda obj: obj.label in labels]
        filter_fcn = lambda objs: objs.get_matches(obj_filters)

    return filter_fcn


def _build_attribute_filter(threshold):
    if threshold is None:
        logger.info("Predicting all attributes")
        return lambda attrs: attrs

    logger.info("Returning predictions with confidence >= %f", threshold)
    attr_filters = [
        lambda attr: attr.confidence is None
        or attr.confidence > float(threshold)
    ]
    return lambda attrs: attrs.get_matches(attr_filters)


def _apply_classifier_to_objects(config):
    parameters = config.parameters

    # Build classifier
    classifier = parameters.classifier.build()
    logger.info("Loaded classifier %s", type(classifier))

    if parameters.record_top_k_probs:
        etal.ExposesProbabilities.ensure_exposes_probabilities(classifier)

    # Build filters
    object_filter = _build_object_filter(parameters.labels)
    attr_filter = _build_attribute_filter(parameters.confidence_threshold)

    # Process data
    with classifier:
        for data in config.data:
            if data.video_path:
                logger.info("Processing video '%s'", data.video_path)
                _process_video(
                    data, classifier, object_filter, attr_filter, parameters)
            if data.image_path:
                logger.info("Processing image '%s'", data.image_path)
                _process_image(
                    data, classifier, object_filter, attr_filter, parameters)
            if data.images_dir:
                logger.info("Processing image directory '%s'", data.images_dir)
                _process_images_dir(
                    data, classifier, object_filter, attr_filter, parameters)


def _process_video(data, classifier, object_filter, attr_filter, parameters):
    write_features = data.video_features_dir is not None

    if write_features:
        etal.ExposesFeatures.ensure_exposes_features(classifier)
        features_handler = etaf.VideoObjectsFeaturesHandler(
            data.video_features_dir)
    else:
        save_feature_fcn = None

    logger.info("Reading labels from '%s'", data.input_labels_path)
    labels = etav.VideoLabels.from_json(data.input_labels_path)

    logger.info("Processing video '%s'", data.video_path)
    with etav.FFmpegVideoReader(data.video_path) as vr:
        for img in vr:
            logger.debug("Processing frame %d", vr.frame_number)

            # Build function for writing features for this frame, if necessary
            if write_features:
                def save_feature_fcn(fvec, idx):
                    features_handler.write_feature(fvec, vr.frame_number, idx)

            # Classify objects in frame
            frame_labels = labels.get_frame(vr.frame_number)
            _classify_objects(
                classifier, img, frame_labels, object_filter, attr_filter,
                parameters, save_feature_fcn=save_feature_fcn)

    logger.info("Writing labels to '%s'", data.output_labels_path)
    labels.write_json(data.output_labels_path)


def _process_image(data, classifier, object_filter, attr_filter, parameters):
    write_features = data.image_features_dir is not None

    if write_features:
        etal.ExposesFeatures.ensure_exposes_features(classifier)
        features_handler = etaf.ImageObjectsFeaturesHandler(
            data.image_features_dir)

        def save_feature_fcn(fvec, idx):
            features_handler.write_feature(fvec, idx)
    else:
        save_feature_fcn = None

    logger.info("Reading labels from '%s'", data.input_image_labels_path)
    image_labels = etai.ImageLabels.from_json(data.input_image_labels_path)

    # Classify objects in image
    img = etai.read(data.image_path)
    _classify_objects(
        classifier, img, image_labels, object_filter, attr_filter, parameters,
        save_feature_fcn=save_feature_fcn)

    logger.info("Writing labels to '%s'", data.output_image_labels_path)
    image_labels.write_json(data.output_image_labels_path)


def _process_images_dir(
        data, classifier, object_filter, attr_filter, parameters):
    write_features = data.image_set_features_dir is not None

    if write_features:
        etal.ExposesFeatures.ensure_exposes_features(classifier)
        features_handler = etaf.ImageSetObjectsFeaturesHandler(
            data.image_set_features_dir)
    else:
        save_feature_fcn = None

    # Load labels
    logger.info("Reading labels from '%s'", data.input_image_set_labels_path)
    image_set_labels = etai.ImageSetLabels.from_json(
        data.input_image_set_labels_path)

    # Classify objects in each image in directory
    for filename in etau.list_files(data.images_dir):
        inpath = os.path.join(data.images_dir, filename)
        logger.info("Processing image '%s'", inpath)

        # Build function for writing features for this image, if necessary
        if write_features:
            def save_feature_fcn(fvec, idx):
                features_handler.write_feature(fvec, filename, idx)

        # Classify objects in image
        img = etai.read(inpath)
        image_labels = image_set_labels[filename]
        _classify_objects(
            classifier, img, image_labels, object_filter, attr_filter,
            parameters, save_feature_fcn=save_feature_fcn)

    logger.info("Writing labels to '%s'", data.output_image_set_labels_path)
    image_set_labels.write_json(data.output_image_set_labels_path)


def _classify_objects(
        classifier, img, image_or_frame_labels, object_filter, attr_filter,
        parameters, save_feature_fcn=None):
    # Parse parameters
    bb_padding = parameters.bb_padding
    force_square = parameters.force_square
    min_height = parameters.min_height_pixels
    record_top_k_probs = parameters.record_top_k_probs

    # Get objects
    objects = object_filter(image_or_frame_labels.objects)

    # Classify objects
    for idx, obj in enumerate(objects, 1):
        # Extract object chip
        bbox = obj.bounding_box
        if bb_padding:
            bbox = bbox.pad_relative(bb_padding)
        obj_img = bbox.extract_from(img, force_square=force_square)

        # Skip small objects, if requested
        obj_height = obj_img.shape[0]
        if min_height is not None and obj_height < min_height:
            logger.debug(
                "Skipping object with height %d < %d", obj_height, min_height)
            continue

        # Classify object
        attrs = _classify_image(
            obj_img, classifier, attr_filter, record_top_k_probs)

        # Write features, if requested
        if save_feature_fcn is not None:
            fvec = classifier.get_features()
            save_feature_fcn(fvec, idx)

        # Record predictions
        obj.add_attributes(attrs)


def _classify_image(img, classifier, attr_filter, record_top_k_probs):
    # Perform prediction
    attrs = classifier.predict(img)

    # Record top-k classes, if necessary
    if record_top_k_probs:
        all_top_k_probs = classifier.get_top_k_classes(record_top_k_probs)
        for attr, top_k_probs in zip(attrs, all_top_k_probs.flatten()):
            attr.top_k_probs = top_k_probs

    # Filter predictions
    attrs = attr_filter(attrs)

    return attrs


def run(config_path, pipeline_config_path=None):
    '''Run the apply_classifier_to_objects module.

    Args:
        config_path: path to a ApplyClassifierToObjectsConfig file
        pipeline_config_path: optional path to a PipelineConfig file
    '''
    config = ApplyClassifierToObjectsConfig.from_json(config_path)
    etam.setup(config, pipeline_config_path=pipeline_config_path)
    _apply_classifier_to_objects(config)


if __name__ == "__main__":
    run(*sys.argv[1:])
