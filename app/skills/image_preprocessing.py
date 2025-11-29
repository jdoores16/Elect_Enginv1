"""
Advanced image preprocessing for OCR optimization.
Includes noise reduction, contrast enhancement, deskewing, and adaptive thresholding.
"""

import cv2
import numpy as np
from PIL import Image
from pathlib import Path
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class ImagePreprocessor:
    """Advanced image preprocessing for panelboard OCR"""
    
    def __init__(self, 
                 enable_deskew: bool = True,
                 enable_denoise: bool = True,
                 enable_contrast: bool = True,
                 enable_binarization: bool = True):
        """
        Initialize preprocessor with feature flags.
        
        Args:
            enable_deskew: Enable automatic deskewing/rotation correction
            enable_denoise: Enable noise reduction
            enable_contrast: Enable contrast enhancement
            enable_binarization: Enable adaptive thresholding binarization
        """
        self.enable_deskew = enable_deskew
        self.enable_denoise = enable_denoise
        self.enable_contrast = enable_contrast
        self.enable_binarization = enable_binarization
    
    def preprocess(self, image_path: Path, save_debug: bool = False) -> Image.Image:
        """
        Apply full preprocessing pipeline to an image.
        
        Args:
            image_path: Path to input image
            save_debug: If True, save intermediate steps for debugging
            
        Returns:
            Preprocessed PIL Image ready for OCR
        """
        logger.info(f"Preprocessing {image_path.name} for OCR")
        
        img = cv2.imread(str(image_path))
        if img is None:
            raise ValueError(f"Failed to load image: {image_path}")
        
        original_img = img.copy()
        
        img = self._ensure_minimum_resolution(img)
        
        if self.enable_denoise:
            img = self._denoise(img)
        
        if self.enable_contrast:
            img = self._enhance_contrast(img)
        
        if self.enable_deskew:
            img = self._deskew(img)
        
        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        if self.enable_binarization:
            img_gray = self._binarize(img_gray)
        
        img_gray = self._remove_borders(img_gray)
        
        if save_debug:
            debug_dir = image_path.parent / "ocr_debug"
            debug_dir.mkdir(exist_ok=True)
            
            cv2.imwrite(str(debug_dir / f"{image_path.stem}_1_original.jpg"), original_img)
            cv2.imwrite(str(debug_dir / f"{image_path.stem}_2_denoised.jpg"), img)
            cv2.imwrite(str(debug_dir / f"{image_path.stem}_3_final.jpg"), img_gray)
            logger.info(f"Debug images saved to {debug_dir}")
        
        pil_image = Image.fromarray(img_gray)
        
        logger.info(f"Preprocessing complete: {image_path.name} ({pil_image.size[0]}x{pil_image.size[1]})")
        
        return pil_image
    
    def _ensure_minimum_resolution(self, img: np.ndarray, min_height: int = 1800) -> np.ndarray:
        """
        Upscale image if resolution is too low for good OCR.
        Tesseract works best with images around 300 DPI.
        """
        height, width = img.shape[:2]
        
        if height < min_height:
            scale_factor = min_height / height
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            
            img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
            logger.info(f"Upscaled image from {width}x{height} to {new_width}x{new_height}")
        
        return img
    
    def _denoise(self, img: np.ndarray) -> np.ndarray:
        """
        Remove noise while preserving edges using Non-Local Means Denoising.
        This is more effective than Gaussian blur for text images.
        """
        denoised = cv2.fastNlMeansDenoisingColored(img, None, h=10, hColor=10, 
                                                     templateWindowSize=7, searchWindowSize=21)
        logger.debug("Applied noise reduction")
        return denoised
    
    def _enhance_contrast(self, img: np.ndarray) -> np.ndarray:
        """
        Enhance contrast using CLAHE (Contrast Limited Adaptive Histogram Equalization).
        This improves text visibility in images with poor lighting or shadows.
        """
        img_lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        
        l_channel, a_channel, b_channel = cv2.split(img_lab)
        
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l_channel = clahe.apply(l_channel)
        
        img_lab = cv2.merge([l_channel, a_channel, b_channel])
        
        enhanced = cv2.cvtColor(img_lab, cv2.COLOR_LAB2BGR)
        logger.debug("Applied CLAHE contrast enhancement")
        return enhanced
    
    def _deskew(self, img: np.ndarray) -> np.ndarray:
        """
        Automatically detect and correct skew/rotation in the image.
        This is crucial for panelboard photos taken at an angle.
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        gray = cv2.bitwise_not(gray)
        
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
        
        coords = np.column_stack(np.where(thresh > 0))
        
        if len(coords) < 5:
            logger.debug("Not enough edge points for deskewing, skipping")
            return img
        
        angle = cv2.minAreaRect(coords)[-1]
        
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        
        if abs(angle) < 0.5:
            logger.debug(f"Skew angle {angle:.2f}° is negligible, skipping rotation")
            return img
        
        (h, w) = img.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        
        rotated = cv2.warpAffine(img, M, (w, h), 
                                 flags=cv2.INTER_CUBIC, 
                                 borderMode=cv2.BORDER_REPLICATE)
        
        logger.info(f"Deskewed image by {angle:.2f} degrees")
        return rotated
    
    def _binarize(self, img_gray: np.ndarray) -> np.ndarray:
        """
        Convert to binary (black/white) using adaptive thresholding.
        This produces cleaner text than simple grayscale.
        """
        binary = cv2.adaptiveThreshold(
            img_gray, 
            255, 
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 
            blockSize=15,
            C=10
        )
        
        logger.debug("Applied adaptive binarization")
        return binary
    
    def _remove_borders(self, img_gray: np.ndarray, border_percent: float = 0.02) -> np.ndarray:
        """
        Remove borders that might contain artifacts or shadows.
        """
        height, width = img_gray.shape[:2]
        
        border_h = int(height * border_percent)
        border_w = int(width * border_percent)
        
        if border_h > 0 and border_w > 0:
            cropped = img_gray[border_h:height-border_h, border_w:width-border_w]
            logger.debug(f"Removed {border_percent*100}% border")
            return cropped
        
        return img_gray


def preprocess_image(image_path, debug: bool = False) -> Tuple[Image.Image, dict]:
    """
    Backward-compatible wrapper for preprocess_for_ocr.
    
    Args:
        image_path: Path to image file (str or Path)
        debug: If True, save intermediate processing steps for debugging
        
    Returns:
        Tuple of (Preprocessed PIL Image, metadata dict)
    """
    if isinstance(image_path, str):
        image_path = Path(image_path)
    
    preprocessor = ImagePreprocessor(
        enable_deskew=True,
        enable_denoise=True,
        enable_contrast=True,
        enable_binarization=True
    )
    img = preprocessor.preprocess(image_path, save_debug=debug)
    metadata = {"preprocessing_applied": True}
    return img, metadata


def preprocess_for_ocr(image_path: Path, 
                       aggressive: bool = False, 
                       save_debug: bool = False) -> Image.Image:
    """
    Convenience function for preprocessing images for OCR.
    
    Args:
        image_path: Path to image file
        aggressive: If True, use more aggressive preprocessing (useful for poor quality images)
        save_debug: If True, save intermediate processing steps for debugging
        
    Returns:
        Preprocessed PIL Image ready for Tesseract OCR
    """
    if aggressive:
        preprocessor = ImagePreprocessor(
            enable_deskew=True,
            enable_denoise=True,
            enable_contrast=True,
            enable_binarization=True
        )
    else:
        preprocessor = ImagePreprocessor(
            enable_deskew=True,
            enable_denoise=True,
            enable_contrast=True,
            enable_binarization=False
        )
    
    return preprocessor.preprocess(image_path, save_debug=save_debug)
