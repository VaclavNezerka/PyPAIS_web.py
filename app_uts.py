import decimal
import io
import json
import numpy as np
import pendulum as pdl
import imagehash
import db_api
from typing import Iterable


def get_masks_corrected(original: np.ndarray = None, corrections: np.ndarray = None) -> np.ndarray:
    """
    Applies manual corrections to the masks and returns the corrected masks.

    Parameters:
    -----------
        original (np.ndarray): The original mask.
        corrections (np.ndarray): The manual corrections to be applied.

    Returns:
    --------
        tuple: A tuple containing the corrected asphalt mask and aggregate mask.
    """
    if original is None and corrections is None:
        raise ValueError("At least one of 'original' or 'corrections' must be provided.")

    if original is None:
        original = np.zeros_like(corrections, dtype=bool)
    elif corrections is None:
        corrections = np.zeros_like(original, dtype=int)
    
    corrected_mask = original.copy()
    if corrections is not None:
        corrected_mask = np.clip(corrected_mask + corrections, 0, 1)
    return corrected_mask.astype(bool)
# def get_storage(conn, experiment_id):
#     if "user_id" not in session:
#         session["user_id"] = str(uuid.uuid4())

#     if not hasattr(g, "storage"):
#         g.storage = UserTemporaryStorage.load(conn, experiment_id)

#     return g.storage
        
class UserTemporaryStorage:
    """
    A class for storing temporary data for the user.
    This ensures that the user can only access their own data.
    This class replaces the need for a previous solution which was current_images dictionary.
    """
    def __init__(self, **kwargs):
        self.user_id = None
        # values
        # self.info = None
        self.info_datetime = None
        self.info_place_of_experiment = None
        self.info_sample_collection_data = None
        self.info_wrapping_temperature = None
        self.info_exposing_water_temperature = None
        self.info_test_procedure = None
        self.info_comment = None
        self.info_aggregate = None
        self.info_binder = None
        self.expert_guess = None
        self.img_width = None
        self.img_height = None
        # info
        self.experiment_id = None
        # images
        self.color = None
        # masks
        self.aggregate_mask = None # [auto - rembg] all the pixels that are not background
        self.asphalt_mask = None # [auto - sliders] all the pixels that are asphalt and not background
        self.aggregate_mask_manual_corrections = None # [manual] all the pixels that are not background or are background (defined by the user)
        self.asphalt_mask_manual_corrections = None # [manual] all the pixels that are asphalt and not background (defined by the user)        
        self.inference_model = None # name of the model to be used for inference

        # image hashes for similarity checking
        self.phash = None
        self.ahash = None
        self.dhash = None
        self.colorhash = None
        
        self.from_dict(kwargs)
        self._dirty_fields = set()  # to track which fields have been modified

    @staticmethod
    def _to_bytes(arr):
        buf = io.BytesIO()
        np.save(buf, arr, allow_pickle=False)
        return buf.getvalue()

    @staticmethod
    def _from_bytes(blob):
        if blob is None:
            return None
        return np.load(io.BytesIO(blob), allow_pickle=False)


    @classmethod
    def load(cls, experiment_id):
        
        if experiment_id is None:
            print("No experiment_id provided, returning empty UserTemporaryStorage instance.")
            return cls()  # return an empty instance if no experiment_id is provided
        else:
            exp_dict = db_api.get_experiment_by_id(experiment_id)  # ensure the experiment exists in the database
            return cls(**exp_dict)  # initialize the UserTemporaryStorage instance with the data from the database
            # with conn.cursor() as cur:
            #     cur.execute("""
            #         SELECT * FROM user_experiments
            #         WHERE experiment_id = %s
            #     """, (experiment_id,))
            #     row = cur.fetchone()

            #     if not row:
            #         return None

            #     cols = [d[0] for d in cur.description]
            #     data = dict(zip(cols, row))

            # # convert masks
            # for k in ["aggregate_mask", "asphalt_mask",
            #         "aggregate_mask_manual", "asphalt_mask_manual"]:
            #     data[k] = cls._from_bytes(data.get(k))

            # return cls(data)

    @classmethod
    def save(self):
        
        print('Saving storage to database...')
        print(f'Current dirty fields: {self._dirty_fields}')
        data_dict = self.to_dict(for_save=True)
        experiment_id = data_dict.pop('experiment_id', None)
        if self.experiment_id is None:
             self.experiment_id = db_api.insert_experiment_to_db(values_dict=data_dict)
        
        db_api.update_experiment_in_db(values_dict=data_dict, experiment_id=experiment_id)
        self._dirty_fields.clear()  # reset dirty fields after saving
        print(f'Current dirty fields: {self._dirty_fields}')


    def __setattr__(self, name: str, value):
        if hasattr(self, '_dirty_fields'):
            self._dirty_fields.add(name)
        super().__setattr__(name, value)
        
            
    def from_dict(self, data_dict: dict) -> None:
        """
        Loads the attributes of the class from a dictionary.
        """
        try:
            self.img_height = data_dict['img_height']
            self.img_width = data_dict['img_width']
        except KeyError:
            pass

        for key, value in data_dict.items():
            if hasattr(self, key):
                if key in ['info_datetime'] and not isinstance(value, str):
                    # parse datetime string
                    if value is None:
                        value = pdl.now()
                    value = pdl.parse(str(value)).to_datetime_string()            
                if isinstance(value, decimal.Decimal):
                    value = float(value)
                if isinstance(value, bytes) or isinstance(value, memoryview):
                    # NP.SAVE APPROACH - Has the metadata like shape and dtype
                    buffer = io.BytesIO(value)
                    value = np.load(buffer, allow_pickle=True)
                setattr(self, key, value)

        # self._self_to_session()  # update the session after loading the data
   

    def to_dict(self, features: Iterable[str] = None, for_save: bool = False) -> dict:
        """
        Converts the attributes of the class to a dictionary.

        Parameters:
        -----------
            features (Iterable[str]): A list of attribute names to include in the dictionary. If None, all attributes are included.
            for_save (bool): If True, converts numpy arrays to bytes for database storage. If False, keeps numpy arrays as is.
        """
        if features is not None:
            dic = {key: value for key, value in self.__dict__.items() if key in features}
        else:
            dic = dict(self.__dict__)  # make a copy instead of using self.__dict__ (to avoid modifying the original)

        if for_save:
            dic['asphalt_ratio'] = self.get_asphalt_ratio() 
            # Convert numpy arrays to bytes for database storage
            for key, value in dic.items():
                if isinstance(value, np.ndarray):
                    # dic[key] = value.tobytes() 

                    # NP.SAVE APPROACH - KEEPS THE METADATA LIKE SHAPE AND DTYPE
                    buffer = io.BytesIO()
                    np.save(buffer, value)
                    dic[key] = buffer.getvalue()  # This is what you store in SQL (e.g., BLOB/BYTEA column)
                elif isinstance(value, imagehash.ImageHash):
                    dic[key] = str(value)  # store imagehash as string

            dic.pop('experiment_id', None)  # remove experiment_id from the dict when saving to db  
        dic.pop('_dirty_fields', None)  # remove _dirty_fields from the dict when saving to db

        return dic

    def to_json(self, features: Iterable[str] = None) -> str:
        """
        Converts the attributes of the class to a JSON string.
        """
        json_dict = self.to_dict(features=features)
        
        for key, value in json_dict.items():
            # convert images to base64 strings for JSON serialization
            if isinstance(value, np.ndarray):
                json_dict[key] = to_base64(value)

        return json.dumps(json_dict)

    def get_asphalt_mask(self) -> np.ndarray | None:
        """
        Applies manual corrections to the masks and returns the corrected masks.

        Returns:
        --------
            tuple: A tuple containing the corrected asphalt mask and aggregate mask.
        """
        asphalt_mask = get_masks_corrected(self.asphalt_mask, self.asphalt_mask_manual_corrections) 
        # if self.asphalt_mask_manual_corrections is not None:
        #     if asphalt_mask is None:
        #         asphalt_mask = np.zeros((self.image_height, self.image_width), dtype=bool)
        #     asphalt_mask += self.asphalt_mask_manual_corrections

        return asphalt_mask

    def get_aggregate_mask(self) -> np.ndarray | None:
        """
        Applies manual corrections to the masks and returns the corrected masks.

        Returns:
        --------
            tuple: A tuple containing the corrected asphalt mask and aggregate mask.
        """
        return get_masks_corrected(self.aggregate_mask, self.aggregate_mask_manual_corrections) 

    def get_bg_mask(self) -> np.ndarray | None:
        """
        Returns the background mask based on the aggregate mask and its manual corrections.

        Returns:
        --------
            np.ndarray | None: The background mask or None if the aggregate mask is not set.
        """
        aggregate_mask = self.get_aggregate_mask()
        asphalt_mask = self.get_asphalt_mask()
        bg_mask = np.logical_and(np.logical_not(aggregate_mask), np.logical_not(asphalt_mask))
        return bg_mask
    
    def get_masks_with_manual_corrections(self) -> tuple[np.ndarray | None, np.ndarray | None, np.ndarray | None]:
        """
        Returns the asphalt, aggregate, and background masks with manual corrections applied.

        Returns:
        --------
            tuple: A tuple containing the corrected asphalt mask, aggregate mask, and background mask.
        """
        asphalt_mask = self.get_asphalt_mask()
        aggregate_mask = self.get_aggregate_mask()
        bg_mask = self.get_bg_mask()
        return asphalt_mask, aggregate_mask, bg_mask

    def get_asphalt_ratio(self) -> float:
        """
        Returns the ratio of asphalt pixels to non-background pixels.

        Returns:
        --------
            float | None: The ratio of asphalt pixels to non-background pixels.
        """

        asphalt_mask = self.get_asphalt_mask()
        aggregate_mask = self.get_aggregate_mask()

        if asphalt_mask is None or aggregate_mask is None:
            return 0.0
        elif np.sum(aggregate_mask * asphalt_mask) > 0:
            raise ValueError("Aggregate mask and asphalt mask have overlapping areas.")

        non_bg_pixels = np.sum(aggregate_mask + asphalt_mask)
        asphalt_pixels = np.sum(asphalt_mask)
        return float(asphalt_pixels / non_bg_pixels) if non_bg_pixels > 0 else 0.0