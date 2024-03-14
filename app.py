from flask import Flask, render_template, request, send_from_directory, g, make_response, send_file
from PIL import Image
import numpy as np
import io
from skimage.filters.rank import entropy
from skimage.morphology import disk
from skimage import img_as_ubyte
import cv2
import time
from rembg import remove

app = Flask(__name__)

current_images = {'gray': [], 'entropy': {}, 'gray_original': {}, 
                  'entropy_original': {}, 'suggested_mask_threshold': {}, 'suggested_mask_blur': {},
                  'suggested_mask': [], 'manual_mask_adjustments': []}
# 'suggested_mask_blur'- an initial blur set by user for automatic mask suggestion 
# 'suggested_mask_threshold'- a threshold set by user for automatic mask suggestion 
# 'suggested_mask' - a mask suggested to a user by actual algorithm (based on the U-NET rembg model)
# 'manual_mask_adjustments' - changes manually made by the user (a sparse numpy boolean matrix), 
# ... so the final mask can expressed as 

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/grayscale-data', methods=['POST'])
def get_grayscale_data():
    file = request.files['file']
    if file:
        image = Image.open(file.stream)
        gray_image = image.convert('L')
        np_gray = np.array(gray_image)
        current_images['gray'] = np_gray
        current_images['gray_original'] = np_gray
        # cv2.imwrite('temp/gray_temp.jpg', np_gray)
        print('Image loaded.')

        img_byte_arr = io.BytesIO()
        gray_image.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)  # Rewind the buffer to the beginning

        img_byte_arr = io.BytesIO()
        Image.fromarray(np_gray).save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()
        return img_byte_arr, 200, {'Content-Type': 'image/png'}

@app.route('/suggest-mask',methods=['POST'])
def remove_picture_background():
    # this function returns a suggested mask, i.e. boolean matrix  
    # denoting wether a pixel should (T) or should not (F) be taken into
    # account during the other computations
    # adjust the mask by setting a manual threshold 
    
    # read the necessary properties
    image=np.array(request.form.get('image'),dtype=np.int8)
    blur_value=int(request.form.get('blurValue', 0))
    threshold=request.form.get('threshold')
    #
    blured_image=blur_image(blur_value,image=image)
    # suggest that the cropping is a vector of coordinates of the left bottom corner 
    # ... followed by the coordinates of the right upper corner 
    cr=request.form.get('cropping')
    tr_mask=remove(blured_image[cr[0]:cr[0]+cr[2],cr[1]:cr[1]+cr[3]])[:,:,1]
    tr_mask=np.array(tr_mask>=threshold)
    mask=np.zeros((image.shape[0],image.shape[1]),dtype=np.bool_)
    mask[cr[0]:cr[0]+cr[2],cr[1]:cr[1]+cr[3]]=tr_mask
    
    # save the requested variables (in future this should be different function, doing everything at once and more 
    # importantly, at the end, when the user is satisfied with the result so we won't be constantly overwriting the DB)
    current_images['suggested_mask']=mask
    current_images['suggested_mask_blur']=blur_value
    current_images['suggested_mask_threshold']=threshold
    print('Background removal suggested')
    return encode_to_png(mask), 200, {'Content-Type': 'image/png'}

@app.route('/entropy', methods=['POST'])
def calculate_entropy():
    # np_gray = cv2.imread('temp/gray_temp.jpg', cv2.IMREAD_GRAYSCALE)
    np_gray = current_images['gray']

    # Calculate local entropy
    entropy_image = entropy(img_as_ubyte(np_gray), disk(5))

    # Normalize the entropy image
    normalized_entropy = cv2.normalize(entropy_image, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX)
    np_entropy = np.uint8(normalized_entropy)
    # cv2.imwrite('temp/entropy_temp.jpg', np_entropy)
    current_images['entropy'] = np_entropy
    current_images['entropy_original'] = np_entropy
    print('Entropy calculated.')

    # Store entropy image for later use
    img_byte_arr = io.BytesIO()
    Image.fromarray(np_entropy).save(img_byte_arr, format='PNG')
    img_byte_arr = img_byte_arr.getvalue()
    return img_byte_arr, 200, {'Content-Type': 'image/png'}

def encode_to_png(image):
    # creates a byte stream ('buffer') for binary operations
    image_io=io.BytesIO()
    image.save(image_io,'PNG') #saves the img as PNG to the byte stream ('buffer')
    image_io.seek(0)
    return image_io.getvalue()

@app.route('/blur', methods=['POST'])
def blur_caller():
    blur_value = int(request.form.get('blurValue', 0))
    # calls twice the function for the blur_image for the gray image and image entropy
    current_images['gray']=blur_image(blur_value,image=current_images['gray'])
    current_images['entropy']=blur_image(blur_value,image=current_images['entropy'])

    new_blur_image = Image.fromarray(current_images['gray'])
    img_byte_arr = io.BytesIO()
    new_blur_image.save(img_byte_arr, format='PNG')
    img_byte_arr = img_byte_arr.getvalue()
    return img_byte_arr, 200, {'Content-Type': 'image/png'}

def blur_image(blur_value,image):
    if blur_value <= 0:
        blur_value = 0
        pass
    elif blur_value % 2 == 0:
        blur_value -= 1  # Make it odd by adding 1 if it's even
        image = cv2.GaussianBlur(image, (blur_value, blur_value), 0)
    else:
        image = cv2.GaussianBlur(image, (blur_value, blur_value), 0)
    print('Image blurred, blur kernel size %d.' % blur_value)
    return image


@app.route('/apply-mask', methods=['POST'])
def apply_mask():
    # Assuming the image's ID or a unique identifier is sent as part of the form data for key lookup
    image_id = request.form.get('imageId')
    min_threshold = int(request.form.get('minThreshold', 0))
    max_threshold = int(request.form.get('maxThreshold', 255))
    entropy_min_threshold = int(request.form.get('entropyMinThreshold', 0))
    entropy_max_threshold = int(request.form.get('entropyMaxThreshold', 255))

    print('Mask applied')
    # np_gray = cv2.imread('temp/gray_temp.jpg', cv2.IMREAD_GRAYSCALE)
    # np_entropy = cv2.imread('temp/entropy_temp.jpg', cv2.IMREAD_GRAYSCALE)
    np_gray = current_images['gray']
    np_entropy = current_images['entropy']
    if image_id == 'gray':
        overlay_image = apply_red_overlay(np_gray, np_gray, np_entropy, min_threshold, max_threshold,
                                          entropy_min_threshold, entropy_max_threshold)
    else:
        overlay_image = apply_red_overlay(np_entropy, np_gray, np_entropy, min_threshold, max_threshold,
                                          entropy_min_threshold, entropy_max_threshold)

    img_byte_arr=encode_to_png(overlay_image) #should be equivalent to the 3 rows bellow
    # img_byte_arr = io.BytesIO()
    # overlay_image.save(img_byte_arr, format='PNG')
    # img_byte_arr = img_byte_arr.getvalue()
    return img_byte_arr, 200, {'Content-Type': 'image/png'}


def apply_red_overlay(masked_img, intensity_img, entropy_img, min_threshold, max_threshold, entropy_min_threshold,
                      entropy_max_threshold):
    intensity_mask = (intensity_img >= min_threshold) & (intensity_img <= max_threshold)
    entropy_mask = (entropy_img >= entropy_min_threshold) & (entropy_img <= entropy_max_threshold)
    combined_mask = intensity_mask & entropy_mask

    # Create an RGBA version of the processed data
    rgba_image = np.dstack([masked_img] * 3 + [np.full(masked_img.shape, 255, dtype=np.uint8)])

    # Prepare the red overlay
    red_overlay = np.zeros_like(rgba_image, dtype=np.uint8)
    red_overlay[..., 0] = 255  # Red channel full intensity
    red_overlay[combined_mask] = [255, 0, 0, 128]  # Semi-transparent red overlay where mask is True

    # Combine the original image with the overlay
    overlay_image = Image.alpha_composite(Image.fromarray(rgba_image), Image.fromarray(red_overlay))

    return overlay_image


@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)



if __name__ == "__main__":
    app.run(debug=True)
