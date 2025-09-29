# vision.py
import io, re, json
from typing import List, Union
from PIL import Image
import google.generativeai as genai
from concurrent.futures import ThreadPoolExecutor
import time
import requests
import os

API_KEY = "AIzaSyCkO5Qlb2tqmDaN1xnGzILSKTNM8kNCizA"
MODEL = "gemini-2.5-flash-lite"
genai.configure(api_key=API_KEY)

TASK = "assisting worker working at a plant"
vision_paused = False

def clean_json(raw_text: str) -> str:
    return re.sub(r"^```json\s*|\s*```$", "", raw_text.strip(), flags=re.IGNORECASE)

def load_image_from_source(image_source: Union[bytes, str]) -> bytes:
    """Load image from various sources: bytes, local path, or URL"""
    try:
        # Clean the source string (remove leading/trailing whitespace)
        if isinstance(image_source, str):
            image_source = image_source.strip()
        
        # If already bytes, return as is
        if isinstance(image_source, bytes):
            return image_source
        
        # If it's a local file path
        if isinstance(image_source, str) and os.path.exists(image_source):
            with open(image_source, 'rb') as f:
                return f.read()
        
        # If it's a URL
        if isinstance(image_source, str) and image_source.startswith(('http://', 'https://')):
            response = requests.get(image_source, timeout=10)
            response.raise_for_status()
            return response.content
        
        # If none of the above, return None
        return None
        
    except Exception as e:
        print(f"[VISION] Error loading image from source {image_source}: {e}")
        return None

def analyze_single_frame(image_source: Union[bytes, str], task: str) -> dict:
    """Analyze one frame from bytes, local path, or URL"""
    try:
        # Load the image from the source
        img_bytes = load_image_from_source(image_source)
        if img_bytes is None:
            return {"status": "error", "observation": "Could not load image"}
        
        img = Image.open(io.BytesIO(img_bytes))
        # Resize large images to improve processing speed
        if img.width > 1024 or img.height > 1024:
            img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
        
        prompt = f"""
        Worker task: {task}.
        Analyze this frame. Respond ONLY in JSON format:
        {{
          "status": "ok|needs_adjustment|danger",
          "observation": "short natural suggestion and next step"
        }}
        """
        model = genai.GenerativeModel(MODEL)
        response = model.generate_content([prompt, img])
        cleaned = clean_json(response.text)
        return json.loads(cleaned)
    except Exception as e:
        print(f"[VISION] Error analyzing single frame: {e}")
        return {"status": "error", "observation": "Frame analysis failed"}

def analyze_frame_batch(batch_sources: List[Union[bytes, str]], task: str) -> str:
    """Analyze a batch of frames from bytes, local paths, or URLs"""
    print(f"[VISION] Analyzing batch of {len(batch_sources)} frames...")
    start_time = time.time()
    
    # First, load all images from their sources
    valid_images = []
    for source in batch_sources:
        img_bytes = load_image_from_source(source)
        if img_bytes is not None:
            valid_images.append(img_bytes)
        else:
            print(f"[VISION] Skipping invalid image source: {source}")
    
    if not valid_images:
        return "No valid images found to analyze. Please check the image sources."
    
    observations = []
    statuses = []
    
    # Process frames in parallel for better performance
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(analyze_single_frame, img_bytes, task) 
                  for img_bytes in valid_images]
        
        for i, future in enumerate(futures):
            try:
                result = future.result(timeout=10)  # 10 second timeout per frame
                if result.get("status") != "error":
                    observations.append(result.get("observation"))
                    statuses.append(result.get("status"))
                    print(f"[VISION] Frame {i+1}: {result.get('status')} - {result.get('observation')}")
            except Exception as e:
                print(f"[VISION] Frame {i+1} failed: {e}")
                continue

    processing_time = time.time() - start_time
    print(f"[VISION] Batch processing took {processing_time:.2f} seconds")

    if not observations:
        return "I'm monitoring the workspace. Keep working safely!"

    # Count status types for priority
    danger_count = statuses.count("danger")
    adjustment_count = statuses.count("needs_adjustment")
    ok_count = statuses.count("ok")
    
    # Prioritize danger alerts
    priority_observations = []
    if danger_count > 0:
        priority_observations = [obs for i, obs in enumerate(observations) 
                               if statuses[i] == "danger"][:2]  # Max 2 danger alerts
    elif adjustment_count > 0:
        priority_observations = [obs for i, obs in enumerate(observations) 
                               if statuses[i] == "needs_adjustment"][:2]
    else:
        priority_observations = observations[:2]  # Take first 2 observations

    # Create summary prompt
    status_summary = ""
    if danger_count > 0:
        status_summary = "URGENT: Safety concerns detected. "
    elif adjustment_count > 0:
        status_summary = "Some adjustments recommended. "
    else:
        status_summary = "Work proceeding well. "

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
        model = genai.GenerativeModel(MODEL)
        response = model.generate_content(prompt)
        final_message = response.text.strip()
        print(f"[VISION] Final message: {final_message}")
        return final_message
    except Exception as e:
        print(f"[VISION] Error generating summary: {e}")
        if danger_count > 0:
            return "⚠️ Safety alert! Please review your current actions and ensure all safety protocols are followed."
        elif adjustment_count > 0:
            return "Good progress! Consider making some adjustments for optimal results."
        else:
            return "Excellent work! Keep maintaining those safety standards."