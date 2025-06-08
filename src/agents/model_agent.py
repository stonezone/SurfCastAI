"""
Model Agent for collecting wave model data from PacIOOS, NOAA, and other sources.
"""

import asyncio
import json
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import logging

from .base_agent import BaseAgent
from ..core.config import Config
from ..core.http_client import HTTPClient


class ModelAgent(BaseAgent):
    """
    Agent for collecting wave model data from various sources.
    
    Features:
    - Collects data from PacIOOS SWAN, WaveWatch III, and other wave models
    - Supports both direct data downloads and web scraping
    - Processes model imagery and data files
    - Extracts model run metadata
    """
    
    def __init__(self, config: Config, http_client: Optional[HTTPClient] = None):
        """Initialize the ModelAgent."""
        super().__init__(config, http_client)
        self.logger = logging.getLogger('agent.model')
    
    async def collect(self, data_dir: Path) -> List[Dict[str, Any]]:
        """
        Collect wave model data from configured sources.
        
        Args:
            data_dir: Directory to store collected data
            
        Returns:
            List of metadata dictionaries
        """
        # Create model data directory
        model_dir = data_dir / "models"
        model_dir.mkdir(exist_ok=True)
        
        # Get model URLs from config
        model_urls = self.config.get_data_source_urls('models').get('models', [])
        
        if not model_urls:
            self.logger.warning("No wave model URLs configured")
            return []
        
        # Ensure HTTP client is available
        await self.ensure_http_client()
        
        # Create tasks for all model URLs
        tasks = []
        for url in model_urls:
            tasks.append(self.process_model_url(url, model_dir))
        
        # Execute all tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions
        metadata_list = []
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"Error processing model data: {result}")
            elif result:
                metadata_list.append(result)
        
        return metadata_list
    
    async def process_model_url(self, url: str, model_dir: Path) -> Dict[str, Any]:
        """
        Process a single wave model URL.
        
        Args:
            url: URL to the model data
            model_dir: Directory to store model data
            
        Returns:
            Metadata dictionary
        """
        try:
            # Determine model type from URL
            model_type = self._determine_model_type(url)
            location = self._extract_location(url, model_type)
            
            self.logger.info(f"Processing {model_type} model data for {location}")
            
            # Different handling based on URL type
            if url.endswith(('.png', '.jpg', '.gif')):
                # Direct image URL
                return await self._process_model_image(url, model_dir, model_type, location)
            elif url.endswith(('.json', '.txt', '.csv')):
                # Direct data file URL
                return await self._process_model_data_file(url, model_dir, model_type, location)
            else:
                # Web page URL - need to scrape for data/images
                return await self._process_model_page(url, model_dir, model_type, location)
        
        except Exception as e:
            self.logger.error(f"Error processing model data from {url}: {e}")
            return self.create_metadata(
                name=f"model_{model_type if 'model_type' in locals() else 'unknown'}_{location if 'location' in locals() else 'unknown'}",
                description="Failed to process model data",
                data_type="unknown",
                source_url=url,
                error=str(e)
            )
    
    async def _process_model_image(self, url: str, model_dir: Path, model_type: str, location: str) -> Dict[str, Any]:
        """Process a direct model image URL."""
        # Generate filename from URL
        filename = f"model_{model_type}_{location}_{url.split('/')[-1]}"
        
        # Download the image
        result = await self.http_client.download(url, save_to_disk=True, custom_file_path=model_dir / filename)
        
        if result.success:
            return self.create_metadata(
                name=f"model_{model_type}_{location}",
                description=f"{model_type} wave model image for {location}",
                data_type="image",
                source_url=url,
                file_path=str(result.file_path),
                model_type=model_type,
                location=location,
                content_type=result.content_type,
                size_bytes=result.size_bytes
            )
        else:
            return self.create_metadata(
                name=f"model_{model_type}_{location}",
                description=f"Failed to download {model_type} wave model image for {location}",
                data_type="image",
                source_url=url,
                error=result.error
            )
    
    async def _process_model_data_file(self, url: str, model_dir: Path, model_type: str, location: str) -> Dict[str, Any]:
        """Process a direct model data file URL."""
        # Generate filename from URL
        filename = f"model_{model_type}_{location}_{url.split('/')[-1]}"
        
        # Download the data file
        result = await self.http_client.download(url, save_to_disk=True, custom_file_path=model_dir / filename)
        
        if result.success:
            # Determine data type from file extension
            data_type = "json" if url.endswith('.json') else "text"
            
            # Extract model run metadata if possible
            model_metadata = {}
            if data_type == "json":
                try:
                    content = result.content.decode('utf-8', errors='ignore')
                    data = json.loads(content)
                    model_metadata = self._extract_model_metadata(data, model_type)
                except (json.JSONDecodeError, Exception) as e:
                    self.logger.warning(f"Failed to extract model metadata: {e}")
            
            return self.create_metadata(
                name=f"model_{model_type}_{location}",
                description=f"{model_type} wave model data for {location}",
                data_type=data_type,
                source_url=url,
                file_path=str(result.file_path),
                model_type=model_type,
                location=location,
                content_type=result.content_type,
                size_bytes=result.size_bytes,
                model_metadata=model_metadata
            )
        else:
            return self.create_metadata(
                name=f"model_{model_type}_{location}",
                description=f"Failed to download {model_type} wave model data for {location}",
                data_type="unknown",
                source_url=url,
                error=result.error
            )
    
    async def _process_model_page(self, url: str, model_dir: Path, model_type: str, location: str) -> Dict[str, Any]:
        """Process a model web page URL to extract data and images."""
        # Download the page content
        result = await self.http_client.download(url)
        
        if not result.success:
            return self.create_metadata(
                name=f"model_{model_type}_{location}",
                description=f"Failed to download {model_type} wave model page for {location}",
                data_type="html",
                source_url=url,
                error=result.error
            )
        
        # Save the original page
        page_filename = f"model_{model_type}_{location}_page.html"
        page_path = model_dir / page_filename
        
        with open(page_path, 'wb') as f:
            f.write(result.content)
        
        # Extract image URLs from the page
        image_urls = self._extract_image_urls(result.content.decode('utf-8', errors='ignore'), url)
        
        # Download images
        image_metadata = []
        for img_url in image_urls:
            try:
                # Generate filename from URL
                img_filename = f"model_{model_type}_{location}_{img_url.split('/')[-1]}"
                
                # Download the image
                img_result = await self.http_client.download(
                    img_url, 
                    save_to_disk=True, 
                    custom_file_path=model_dir / img_filename
                )
                
                if img_result.success:
                    image_metadata.append({
                        "url": img_url,
                        "file_path": str(img_result.file_path),
                        "content_type": img_result.content_type,
                        "size_bytes": img_result.size_bytes
                    })
            except Exception as e:
                self.logger.warning(f"Failed to download image {img_url}: {e}")
        
        return self.create_metadata(
            name=f"model_{model_type}_{location}",
            description=f"{model_type} wave model data for {location}",
            data_type="html",
            source_url=url,
            file_path=str(page_path),
            model_type=model_type,
            location=location,
            image_count=len(image_metadata),
            images=image_metadata
        )
    
    def _determine_model_type(self, url: str) -> str:
        """Determine the type of wave model from the URL."""
        url_lower = url.lower()
        
        if 'swan' in url_lower:
            return 'swan'
        elif 'ww3' in url_lower or 'wavewatch' in url_lower:
            return 'ww3'
        elif 'cdip' in url_lower:
            return 'cdip'
        elif 'pacioos' in url_lower:
            return 'pacioos'
        elif 'surfline' in url_lower:
            return 'surfline'
        else:
            return 'unknown'
    
    def _extract_location(self, url: str, model_type: str) -> str:
        """Extract location information from the URL."""
        url_lower = url.lower()
        
        # Extract location based on model type and URL patterns
        if model_type == 'swan':
            if 'oahu' in url_lower:
                return 'oahu'
            elif 'hawaii' in url_lower:
                return 'hawaii'
            else:
                # Try to extract location from URL segments
                parts = url.split('/')
                for part in parts:
                    if part.lower() in ['oahu', 'hawaii', 'maui', 'kauai']:
                        return part.lower()
        
        elif model_type == 'ww3':
            if 'pacific' in url_lower:
                if 'north' in url_lower:
                    return 'north_pacific'
                elif 'south' in url_lower:
                    return 'south_pacific'
                else:
                    return 'pacific'
            elif 'hawaii' in url_lower:
                return 'hawaii'
        
        # Default fallback - extract location from any geographic terms
        geo_terms = ['oahu', 'hawaii', 'maui', 'kauai', 'pacific', 'atlantic']
        for term in geo_terms:
            if term in url_lower:
                return term
        
        return 'unknown'
    
    def _extract_image_urls(self, html_content: str, base_url: str) -> List[str]:
        """Extract image URLs from HTML content."""
        # Basic regex for image URLs
        img_patterns = [
            r'<img[^>]+src="([^"]+\.(jpg|jpeg|png|gif))"',
            r'<a[^>]+href="([^"]+\.(jpg|jpeg|png|gif))"'
        ]
        
        image_urls = []
        for pattern in img_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            for match in matches:
                img_url = match[0]
                
                # Handle relative URLs
                if not img_url.startswith(('http://', 'https://')):
                    # Remove any leading '/' from img_url
                    img_url = img_url.lstrip('/')
                    
                    # Add base URL
                    if base_url.endswith('/'):
                        img_url = base_url + img_url
                    else:
                        img_url = base_url + '/' + img_url
                
                image_urls.append(img_url)
        
        return image_urls
    
    def _extract_model_metadata(self, data: Dict[str, Any], model_type: str) -> Dict[str, Any]:
        """Extract metadata from model data."""
        metadata = {
            'model_type': model_type,
            'run_time': None,
            'forecast_hours': None,
            'parameters': []
        }
        
        try:
            # Different extraction logic based on model type
            if model_type == 'swan':
                # SWAN metadata extraction
                if 'metadata' in data:
                    meta = data['metadata']
                    metadata['run_time'] = meta.get('run_time')
                    metadata['forecast_hours'] = meta.get('forecast_hours')
                
                # Extract parameters
                if 'parameters' in data:
                    metadata['parameters'] = list(data['parameters'].keys())
            
            elif model_type == 'ww3':
                # WW3 metadata extraction
                if 'header' in data:
                    header = data['header']
                    metadata['run_time'] = header.get('refTime')
                    metadata['forecast_hours'] = header.get('forecastTime')
                
                # Extract parameters
                if 'parameters' in data:
                    metadata['parameters'] = [p.get('name') for p in data['parameters']]
        
        except Exception as e:
            self.logger.warning(f"Error extracting model metadata: {e}")
        
        return metadata