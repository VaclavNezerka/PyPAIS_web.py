from collections.abc import Iterable
import io
import numpy as np
import cv2
from skimage.metrics import structural_similarity as ssim
from PIL import Image
import imagehash
import concurrent.futures as threading
import db_api
import heapq

"""
This module provides functions to compute similarity scores between images using different methods,

- The Image Similarity is evaluated in the following way:
    1. when an image is uploaded, its perceptual hash (phash), average hash (ahash), difference hash (dhash), and color hash (colorhash) are computed.
    2. These hashes are compared against a database of precomputed hashes for existing images 
     WITHIN THE SAME COMPANY using Hamming distance.
    3. AT MOST X= e.g. 50 images with the lowest Hamming distance for each hash type are selected as potential matches.
    4. For these selected images, two similarity scores are computed:
        a. Histogram Similarity Score using correlation method.
        b. Structural Similarity Index (SSIM).
    5. If any of these similarity scores exceed predefined thresholds (e.g., 0.9 for histogram similarity and 0.85 for SSIM), the images are flagged as similar.
    6. A list of n = e.g. 10 most similar images based on these scores is returned for further review.
    7. The most similar image is assumed the one with any metric the highest.
"""

def cv2_image_from_bytes(image_bytes: bytes) -> cv2.Mat:
    """
    Convert image bytes to cv2 Mat object.

    Args:
        image_bytes: Image in bytes format.
    Returns:
        cv2_image: Image as cv2 Mat object.
    """
    buffer = io.BytesIO(image_bytes)
    cv2_image = np.load(buffer, allow_pickle=True)
    return cv2_image


class ImageSimilarityController:
    """
    This class is responsible for controlling the image uniqueness in the background.
    """

    def __init__(self, max_workers: int = 8, checks_per_hash_type: int = 50, similarity_thresholds: dict = {"histogram": 0.9, "ssim": 0.85}, n_similar: int = 10) -> None:
        # self.executor = threading.ThreadPoolExecutor(max_workers=max_workers)
        self.executor = threading.ThreadPoolExecutor(max_workers=max_workers)
        self.checks_per_hash_type = checks_per_hash_type
        self.similarity_thresholds = similarity_thresholds
        self.n_similar = n_similar

    def _check_image_uniqness(self, user_id: int, experiment_id: int) -> None:
        """
        Check whether the image has been uploaded before by the user or someone in the same organization.
        """   
        experiment_ids, hashes = db_api.get_comparing_image_hashes(user_id, experiment_id)
        target_hashes = db_api.get_image_hashes_by_experiment_id(experiment_id)

        similar_image_indices = get_kNN_images(
            target_image_hashes=target_hashes,
            compare_images_hashes=hashes,
            n_max_per_hash_type=self.checks_per_hash_type
        )
        similar_experiment_ids = [experiment_ids[i] for i in similar_image_indices]

        # Compute the similarity score on kNN (suspicious) images
        # TODO: continue...
        # load target image from DB
        target_image = db_api.load_image_by_experiment_id(experiment_id)
        target_image = cv2_image_from_bytes(target_image)

        # heap to store the most similar images
        heap_hist = []
        heap_ssim = []

        for sim_exp_id in similar_experiment_ids:
            # Load images from DB
            compare_image = db_api.load_image_by_experiment_id(sim_exp_id)
            compare_image = cv2_image_from_bytes(compare_image)
            # Compute similarity scores
            scores = get_image_scores(target_image, compare_image)
            
            if scores['histogram_score'] >= self.similarity_thresholds['histogram']:
                heapq.heappush(heap_hist, (scores['histogram_score'], sim_exp_id))
                if len(heap_hist) > self.n_similar:
                    heapq.heappop(heap_hist)
            if scores['ssim_score'] >= self.similarity_thresholds['ssim']:
                heapq.heappush(heap_ssim, (scores['ssim_score'], sim_exp_id))
                if len(heap_ssim) > self.n_similar:
                    heapq.heappop(heap_ssim)
        ...
        # TODO: In future, consider combining both metrics to determine overall similarity.
        # TODO: Especially in cases where two images have the same score in one metric

        # Write the best matches to DB
        # print(f"Experiment ID: {experiment_id} - \n\t Similar by Histogram: {heap_hist}, \n\t Similar by SSIM: {heap_ssim}")
        db_api.store_similar_images(
            experiment_id=experiment_id,
            similar_by_histogram=heapq.nlargest(1, heap_hist)[0] if heap_hist else (None, None),
            similar_by_ssim=heapq.nlargest(1, heap_ssim)[0] if heap_ssim else (None, None)
        )


    def controll_experiment(self, user_id: str, experiment_id: int) -> None:
        """
        Add a new thread to check the image uniqness in the background.

        Parameters:
            user_id (str): The ID of the user.
            experiment_id (int): The ID of the experiment.
        """
        self.executor.submit(
            self._check_image_uniqness, 
            user_id, experiment_id
        )
        self._check_image_uniqness(user_id, experiment_id)


def similarity_score_histogram(image1, image2):
    """
    Compute the histogram similarity score between two images using correlation method.
    The score ranges from 0 to 1, where 1 indicates perfect similarity, and 0 indicates no similarity.

    Args:
        image1: First input image.
        image2: Second input image.
    Returns:
        metric_val: Similarity score based on histogram correlation.
    """

    hist_img1 = cv2.calcHist([image1], [0, 1, 2], None, [256, 256, 256], [0, 256, 0, 256, 0, 256])
    hist_img1[255, 255, 255] = 0 #ignore all white pixels
    cv2.normalize(hist_img1, hist_img1, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)

    hist_img2 = cv2.calcHist([image2], [0, 1, 2], None, [256, 256, 256], [0, 256, 0, 256, 0, 256])
    hist_img2[255, 255, 255] = 0  #ignore all white pixels
    cv2.normalize(hist_img2, hist_img2, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
    # Find the metric value
    metric_val = cv2.compareHist(hist_img1, hist_img2, cv2.HISTCMP_CORREL)
    return metric_val

def similarity_score_ssim(image1, image2, in_0_1_range=True):
    """
    Compute the Structural Similarity Index (SSIM) between two images.
    The SSIM index can range from 0 to 1, where 1 indicates perfect similarity, and 0 indicates no similarity.

    The images are first converted to grayscale. If the images have different sizes,
    the second image is resized to match the first image's dimensions.
    
    Args:
        image1: First input image.
        image2: Second input image.
        in_0_1_range: If True, the score is normalized to the range [0, 1]. (default is True) If False, the score is returned in  the range [-1, 1 ].
    Returns:
        score: Structural Similarity Index (SSIM) between the two images.
            
    """ 
    gray_img1 = cv2.cvtColor(image1, cv2.COLOR_BGR2GRAY)
    gray_img2 = cv2.cvtColor(image2, cv2.COLOR_BGR2GRAY)
    if gray_img1.shape != gray_img2.shape:
        gray_img2 = cv2.resize(gray_img2, (gray_img1.shape[1], gray_img1.shape[0]))

    score = ssim(gray_img1, gray_img2, full=False)
    if in_0_1_range:
        score = (score + 1) / 2  # Convert to range [0, 1]
    return score

def get_image_scores(image1: cv2.Mat, image2: cv2.Mat) -> dict[str, float]:
    """
    Compute similarity scores between two images using histogram correlation and SSIM.

    Args:
        image1: First input image (cv2 Mat object).
        image2: Second input image (cv2 Mat object).
    Returns:
        scores: Dictionary containing histogram similarity score and SSIM score.
    """
    hist_score = similarity_score_histogram(image1, image2)
    ssim_score = similarity_score_ssim(image1, image2, in_0_1_range=True)
    return {'histogram_score': hist_score, 'ssim_score': ssim_score}


def return_hashes(image: Image.Image) -> dict[str, imagehash.ImageHash]:
    """
    Compute perceptual hash (phash), average hash (ahash), and difference hash (dhash) for the given image.

    Args:
        image: Input image (PIL Image object).
    Returns:
        phash: Perceptual hash of the image.
        ahash: Average hash of the image.
        dhash: Difference hash of the image.
        colorhash: Color hash of the image.
    """
    phash = imagehash.phash(image)
    ahash = imagehash.average_hash(image)
    dhash = imagehash.dhash(image)
    colorhash = imagehash.colorhash(image)
    return {'phash': phash, 'ahash': ahash, 'dhash': dhash, 'colorhash': colorhash}



def hamming_distances_between_hashes(target_image_hash: imagehash.ImageHash, compare_images_hashes: Iterable[imagehash.ImageHash]) -> np.ndarray:
    """
    Compute the Hamming distances between various types hashes of .

    Args:
        target_image_hash: Target image hash.
        compare_images_hashes: Iterable of image hashes to compare against the target hash.
    Returns:
        distances: np.ndarray containing Hamming distances for each hash type.
    """
    distances = np.zeros(len(compare_images_hashes), dtype=int)
    for i, image_hash in enumerate(compare_images_hashes):
        distance = target_image_hash - image_hash
        distances[i] = distance
    return distances


# complete procedure
def get_kNN_images(target_image_hashes: dict[imagehash.ImageHash], compare_images_hashes: dict[Iterable[imagehash.ImageHash]], n_max_per_hash_type: int = 50) -> list:
    """
    Identify similar images based on Hamming distance threshold.

    Args:
        target_image_hashes: Target image hashes.
        compare_images_hashes: Iterable of image hashes to compare against the target hashes.
        threshold: Similarity threshold (default is 0.85).
    Returns:
        similar_images_indices: List of indices of similar images.
    """
    similar_images_indices = set()

    for i, hash_type in enumerate(target_image_hashes.keys()):

        distances = hamming_distances_between_hashes(
            target_image_hashes[hash_type],
            compare_images_hashes[hash_type]
        )

        sorted_indices = np.argsort(distances)
        selected_indices = sorted_indices[:n_max_per_hash_type]

        similar_images_indices.update(selected_indices.tolist())
        k = 0
        while len(similar_images_indices) < n_max_per_hash_type * i:
            try:
                similar_images_indices.add(sorted_indices[n_max_per_hash_type + k])
            except IndexError:
                break
            k += 1

    return list(similar_images_indices)


# isc.controll_experiment(user_id=2, experiment_id=190)
