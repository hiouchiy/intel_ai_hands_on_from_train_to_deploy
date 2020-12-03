#
# Copyright 2020 Intel Corporation.
#
# This software and the related documents are Intel copyrighted materials,
# and your use of them is governed by the express license under which they
# were provided to you (End User License Agreement for the Intel(R) Software
# Development Products (Version October 2018)). Unless the License provides
# otherwise, you may not use, modify, copy, publish, distribute, disclose or
# transmit this software or the related documents without Intel's prior
# written permission.
#
# This software and the related documents are provided as is, with no
# express or implied warranties, other than those that are expressly
# stated in the License.

import os
import numpy as np
from addict import Dict
from cv2 import imread, resize as cv2_resize

from compression.api import Metric, DataLoader
from compression.graph import load_model, save_model
from compression.graph.model_utils import compress_model_weights
from compression.engines.ie_engine import IEEngine
from compression.pipeline.initializer import create_pipeline
from compression.utils.logger import init_logger
from sample.utils.argument_parser import get_common_argparser

from tensorflow.keras.applications.resnet import preprocess_input

# Initialize the logger to print the quantization process in the console.
init_logger(level='INFO')


# Custom DataLoader class implementation that is required for
# the proper reading of Imagenet images and annotations.
class ImageNetDataLoader(DataLoader):

    def __init__(self, config):
        if not isinstance(config, Dict):
            config = Dict(config)
        super().__init__(config)
        self._annotations, self._img_ids = self._read_img_ids_annotations(config)

    def __len__(self):
        return len(self._img_ids)

    def __getitem__(self, index):
        if index >= len(self):
            raise IndexError

        annotation = (index, self._annotations[self._img_ids[index]])\
            if self._annotations else (index, None)
        return annotation, self._read_image(self._img_ids[index])

    # Methods specific to the current implementation
    @staticmethod
    def _read_img_ids_annotations(dataset):
        """ Parses annotation file or directory with images to collect image names and annotations.
        :param dataset: dataset config
        :returns dictionary with annotations
                 list of image ids
        """
        annotations = {}
        img_ids = []
        if dataset.annotation_file:
            with open(dataset.annotation_file) as f:
                for line in f:
                    img_id, annotation = line.split(" ")
                    annotation = int(annotation.rstrip('\n'))
                    annotations[img_id] = annotation + 1 if dataset.has_background else annotation
                    img_ids.append(img_id)
        else:
            img_ids = sorted(os.listdir(dataset.data_source))

        return annotations, img_ids

    def _read_image(self, index):
        """ Reads images from directory.
        :param index: image index to read
        :return ndarray representation of image batch
        """
        image = imread(os.path.join(self.config.data_source, index))
        image = self._preprocess(image)
        
        image = preprocess_input(image)
        
        return image.transpose(2, 0, 1)

    def _preprocess(self, image):
        """ Does preprocessing of an image according to the preprocessing config.
        :param image: ndarray image
        :return processed image
        """
        for prep_params in self.config.preprocessing:
            image = PREPROC_FNS[prep_params.type](image, prep_params)
        return image


# Custom implementation of classification accuracy metric.
class Accuracy(Metric):

    # Required methods
    def __init__(self, top_k=1):
        super().__init__()
        self._top_k = top_k
        self._name = 'accuracy@top{}'.format(self._top_k)
        self._matches = []

    @property
    def value(self):
        """ Returns accuracy metric value for the last model output. """
        return {self._name: self._matches[-1]}

    @property
    def avg_value(self):
        """ Returns accuracy metric value for all model outputs. """
        return {self._name: np.ravel(self._matches).mean()}

    def update(self, output, target):
        """ Updates prediction matches.
        :param output: model output
        :param target: annotations
        """
        if len(output) > 1:
            raise Exception('The accuracy metric cannot be calculated '
                            'for a model with multiple outputs')
        if isinstance(target, dict):
            target = list(target.values())
        predictions = np.argsort(output[0], axis=1)[:, -self._top_k:]
        match = [float(t in predictions[i]) for i, t in enumerate(target)]

        self._matches.append(match)

    def reset(self):
        """ Resets collected matches """
        self._matches = []

    def get_attributes(self):
        """
        Returns a dictionary of metric attributes {metric_name: {attribute_name: value}}.
        Required attributes: 'direction': 'higher-better' or 'higher-worse'
                             'type': metric type
        """
        return {self._name: {'direction': 'higher-better',
                             'type': 'accuracy'}}


def resize(image, params):
    shape = params['height'], params['width']
    return cv2_resize(image, shape)


def crop(image, params):

    height, width = image.shape[:2]

    dst_height = int(height * params['central_fraction'])
    dst_width = int(width * params['central_fraction'])

    if height < dst_height or width < dst_width:
        resized = np.array([width, height])
        if width < dst_width:
            resized *= dst_width / width
        if height < dst_height:
            resized *= dst_height / height
        image = cv2_resize(image, tuple(np.ceil(resized).astype(int)))

    top_left_y = (height - dst_height) // 2
    top_left_x = (width - dst_width) // 2
    return image[top_left_y:top_left_y + dst_height, top_left_x:top_left_x + dst_width]


PREPROC_FNS = {'resize': resize, 'crop': crop}


def get_configs(args):
    if not args.weights:
        args.weights = '{}.bin'.format(os.path.splitext(args.model)[0])

    model_config = Dict({
        'model_name': 'resnet50_int8',
        'model': args.model,
        'weights': args.weights
    })
    engine_config = Dict({
        'device': 'CPU',
        'stat_requests_number': 4,
        'eval_requests_number': 4
    })
    dataset_config = {
        'data_source': args.dataset,
        'annotation_file': args.annotation_file,
        'has_background': True,
        'preprocessing': [
#            {
#                'type': 'crop',
#                'central_fraction': 0.875
#            },
            {
                'type': 'resize',
                'width': 224,
                'height': 224
            }
        ],
    }
    algorithms = [
        {
            'name': 'DefaultQuantization',
            'params': {
                'target_device': 'CPU',
                'preset': 'performance',
                'stat_subset_size': 300
            }
        }
    ]

    return model_config, engine_config, dataset_config, algorithms


def optimize_model(args):
    model_config, engine_config, dataset_config, algorithms = get_configs(args)

    # Step 1: Load the model.
    model = load_model(model_config)

    # Step 2: Initialize the data loader.
    data_loader = ImageNetDataLoader(dataset_config)

    # Step 3 (Optional. Required for AccuracyAwareQuantization): Initialize the metric.
    metric = Accuracy(top_k=1)

    # Step 4: Initialize the engine for metric calculation and statistics collection.
    engine = IEEngine(engine_config, data_loader, metric)

    # Step 5: Create a pipeline of compression algorithms.
    pipeline = create_pipeline(algorithms, engine)

    # Step 6: Execute the pipeline.
    compressed_model = pipeline.run(model)

    # Step 7 (Optional): Compress model weights quantized precision
    #                    in order to reduce the size of final .bin file.
    compress_model_weights(compressed_model)

    return compressed_model, pipeline


def main():
    argparser = get_common_argparser()
    argparser.add_argument(
        '-a',
        '--annotation-file',
        help='File with Imagenet annotations in .txt format',
        required=True
    )

    # Steps 1-7: Model optimization
    compressed_model, pipeline = optimize_model(argparser.parse_args())

    # Step 8: Save the compressed model to the desired path.
    save_model(compressed_model, os.path.join(os.path.curdir, 'optimized'))

    # Step 9 (Optional): Evaluate the compressed model. Print the results.
    metric_results = pipeline.evaluate(compressed_model)
    if metric_results:
        for name, value in metric_results.items():
            print('{: <27s}: {}'.format(name, value))


if __name__ == '__main__':
    main()
