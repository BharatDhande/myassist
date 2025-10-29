# services/vision_service.py
"""
Computer vision analysis service using Google Gemini
"""
import io
import re
import json
import os
import time
import requests
from typing import List, Union, Dict
from PIL import Image
import google.generativeai as genai
from concurrent.futures import ThreadPoolExecutor

from core.config import settings
from core.logging_config import get_logger

logger = get_logger(__name__)


class VisionService:
    """Service for analyzing images using Gemini Vision API"""
    
    def __init__(self):
        # Configure Gemini
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model_name = settings.GEMINI_MODEL
        self.max_workers = settings.MAX_FRAME_WORKERS
        self.timeout = settings.FRAME_TIMEOUT
        self.max_image_size = settings.IMAGE_MAX_SIZE
    
    @staticmethod
    def _clean_json(raw_text: str) -> str:
        """Remove markdown code block formatting from JSON"""
        return re.sub(
            r"^```json\s*|\s*```$", 
            "", 
            raw_text.strip(), 
            flags=re.IGNORECASE
        )
    
    def load_image(self, source: Union[bytes, str]) -> bytes:
        """
        Load image from various sources
        
        Args:
            source: Image as bytes, local path, or URL
            
        Returns:
            Image data as bytes
        """
        try:
            # Clean string source
            if isinstance(source, str):
                source = source.strip()
            
            # Already bytes
            if isinstance(source, bytes):
                return source
            
            # Local file path
            if isinstance(source, str) and os.path.exists(source):
                with open(source, 'rb') as f:
                    return f.read()
            
            # URL
            if isinstance(source, str) and source.startswith(('http://', 'https://')):
                response = requests.get(source, timeout=10)
                response.raise_for_status()
                return response.content
            
            logger.warning(f"[VISION] Invalid image source: {source}")
            return None
            
        except Exception as e:
            logger.error(f"[VISION] Error loading image: {e}")
            return None
    
    def analyze_single_frame(self, source: Union[bytes, str], task: str) -> Dict:
        """
        Analyze a single image frame
        
        Args:
            source: Image source (bytes, path, or URL)
            task: Task description for context
            
        Returns:
            Analysis result dictionary
        """
        try:
            # Load image
            img_bytes = self.load_image(source)
            if img_bytes is None:
                return {
                    "status": "error", 
                    "observation": "Could not load image"
                }
            
            # Open and resize if needed
            img = Image.open(io.BytesIO(img_bytes))
            if img.width > self.max_image_size or img.height > self.max_image_size:
                img.thumbnail(
                    (self.max_image_size, self.max_image_size), 
                    Image.Resampling.LANCZOS
                )
            
            # Prepare prompt
            prompt = f"""
            Worker task: {task}.
            Analyze this frame. Respond ONLY in JSON format:
            {{
              "status": "ok|needs_adjustment|danger",
              "observation": "short natural suggestion and next step"
            }}
            """
            
            # Generate analysis
            model = genai.GenerativeModel(self.model_name)
            response = model.generate_content([prompt, img])
            
            # Parse JSON response
            cleaned = self._clean_json(response.text)
            return json.loads(cleaned)
            
        except Exception as e:
            logger.error(f"[VISION] Frame analysis error: {e}")
            return {
                "status": "error", 
                "observation": "Frame analysis failed"
            }
    
    def analyze_frame_batch(
        self, 
        batch_sources: List[Union[bytes, str]], 
        task: str
    ) -> str:
        """
        Analyze a batch of image frames (returns text message)
        
        Args:
            batch_sources: List of image sources
            task: Task description for context
            
        Returns:
            Natural language summary of analysis
        """
        analysis_data = self.analyze_frame_batch_detailed(batch_sources, task)
        return analysis_data.get("message", "Monitoring workspace")
    
    def analyze_frame_batch_detailed(
        self, 
        batch_sources: List[Union[bytes, str]], 
        task: str
    ) -> Dict:
        """
        Analyze a batch of image frames (returns detailed data)
        
        Args:
            batch_sources: List of image sources
            task: Task description for context
            
        Returns:
            Dictionary with status, message, and analysis details
        """
        logger.info(f"[VISION] Analyzing batch of {len(batch_sources)} frames")
        start_time = time.time()
        
        # Load all valid images
        valid_images = []
        for source in batch_sources:
            img_bytes = self.load_image(source)
            if img_bytes is not None:
                valid_images.append(img_bytes)
            else:
                logger.warning(f"[VISION] Skipping invalid source: {source}")
        
        if not valid_images:
            return {
                "status": "error",
                "message": "No valid images found to analyze.",
                "has_changes": False
            }
        
        # Process frames in parallel
        observations = []
        statuses = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [
                executor.submit(self.analyze_single_frame, img_bytes, task)
                for img_bytes in valid_images
            ]
            
            for i, future in enumerate(futures):
                try:
                    result = future.result(timeout=self.timeout)
                    if result.get("status") != "error":
                        observations.append(result.get("observation"))
                        statuses.append(result.get("status"))
                        logger.debug(
                            f"[VISION] Frame {i+1}: "
                            f"{result.get('status')} - {result.get('observation')}"
                        )
                except Exception as e:
                    logger.error(f"[VISION] Frame {i+1} failed: {e}")
                    continue
        
        processing_time = time.time() - start_time
        logger.info(f"[VISION] Batch processed in {processing_time:.2f}s")
        
        if not observations:
            return {
                "status": "ok",
                "message": "I'm monitoring the workspace. Keep working safely!",
                "has_changes": False
            }
        
        # Prioritize observations by status
        danger_count = statuses.count("danger")
        adjustment_count = statuses.count("needs_adjustment")
        ok_count = statuses.count("ok")
        
        # Determine overall status
        if danger_count > 0:
            overall_status = "danger"
        elif adjustment_count > 0:
            overall_status = "needs_adjustment"
        else:
            overall_status = "ok"
        
        priority_observations = []
        if danger_count > 0:
            priority_observations = [
                obs for i, obs in enumerate(observations) 
                if statuses[i] == "danger"
            ][:2]
        elif adjustment_count > 0:
            priority_observations = [
                obs for i, obs in enumerate(observations) 
                if statuses[i] == "needs_adjustment"
            ][:2]
        else:
            # For "ok" status, only include if there's actionable content
            priority_observations = observations[:1]
        
        # Generate status summary
        status_summary = ""
        if danger_count > 0:
            status_summary = "URGENT: Safety concerns detected. "
        elif adjustment_count > 0:
            status_summary = "Some adjustments recommended. "
        else:
            status_summary = "Work proceeding well. "
        
        # Create summary prompt
        prompt = f"""
        Act as a supportive assistant for a worker at a plant.
        Task: {task}
        Status: {status_summary}
        Key observations from {len(valid_images)} frames: {priority_observations}

        Provide ONE concise, supportive response (1 or max 2 sentences) that:
        1. Gives the most important guidance/suggestion and appropriate next step
        2. Sounds natural and human-like
        """
        
        try:
            model = genai.GenerativeModel(self.model_name)
            response = model.generate_content(prompt)
            final_message = response.text.strip()
            logger.info(f"[VISION] Final message: {final_message}")
            
            return {
                "status": overall_status,
                "message": final_message,
                "has_changes": True,
                "danger_count": danger_count,
                "adjustment_count": adjustment_count,
                "ok_count": ok_count
            }
        except Exception as e:
            logger.error(f"[VISION] Summary generation error: {e}")
            # Fallback messages
            fallback_message = ""
            if danger_count > 0:
                fallback_message = "⚠️ Safety alert! Please review your current actions."
            elif adjustment_count > 0:
                fallback_message = "Good progress! Consider making some adjustments."
            else:
                fallback_message = "Excellent work! Keep maintaining those safety standards."
            
            return {
                "status": overall_status,
                "message": fallback_message,
                "has_changes": True,
                "danger_count": danger_count,
                "adjustment_count": adjustment_count,
                "ok_count": ok_count
            }