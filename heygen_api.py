import requests
import json
from typing import Optional, Dict, Any
import logging

class HeyGenHandler:
    """
    A class to handle interactions with the HeyGen API for image-to-video conversion.
    """
    
    def __init__(self, api_key: str, api_url: str = "https://api.heygen.com/v1"):
        """
        Initialize the HeyGen API handler.
        
        Args:
            api_key: Your HeyGen API key
            api_url: Base URL for HeyGen API (defaults to v1)
        """
        self.api_key = api_key
        self.api_url = api_url
        self.headers = {
            "X-Api-Key": api_key,
            "Content-Type": "application/json",
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def create_video_from_image_and_text(
        self, 
        image_url: str, 
        text: str, 
        voice_id: str = "1bd001e7e50f421d891986aad5158bc8",  # Default voice ID
        video_config: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Create a video from an image and text using HeyGen API.
        
        Args:
            image_url: URL of the image to use
            text: Text to convert to speech
            voice_id: ID of the voice to use (default is English male)
            video_config: Additional video configuration options
            
        Returns:
            URL of the generated video or None if failed
        """
        if video_config is None:
            video_config = {
                "ratio": "16:9",
                "resolution": "720p",
                "background": "#FFFFFF"
            }

        payload = {
            "image_url": image_url,
            "script": {
                "type": "text",
                "input": text,
                "voice_id": voice_id
            },
            "video_config": video_config
        }

        try:
            response = self.session.post(
                f"{self.api_url}/video/generate",
                data=json.dumps(payload)
            
            response.raise_for_status()
            result = response.json()
            
            if result.get("status") == "success":
                video_url = result.get("data", {}).get("video_url")
                self.logger.info(f"Video created successfully: {video_url}")
                return video_url
            else:
                self.logger.error(f"HeyGen API error: {result.get('message')}")
                return None
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request failed: {str(e)}")
            return None
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse response: {str(e)}")
            return None