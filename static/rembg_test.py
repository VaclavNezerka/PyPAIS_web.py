import PIL.Image
from rembg import remove
import PIL
import matplotlib.pyplot as plt
import numpy as np

input_path = 'Varinta A - na sucho, na světle, přes tmavý papír.HEIC'

image = PIL.Image.open(input_path)
image = np.array(image)
removed = remove(image)
removed= np.array(removed)
print(np.array(image).shape)
print(removed.shape)
print(np.unique(removed[:,:,1]))
# extract mask
mask = removed[:, :, 3]
removed [:,:,3][removed[:,:,3]>128] = 255
removed [:,:,3][removed[:,:,3]<=128] = 0
# Show the mask
# plt.imshow(mask>128)
# plt.show()

plt.imshow(removed.reshape((removed.shape[0],removed.shape[1],-1)))
plt.show()

# # save the image
# output_path = 'output_voda2.png'
# PIL.Image.fromarray(removed).save(output_path)
