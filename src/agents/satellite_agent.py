"""
Satellite Agent for collecting satellite imagery from NOAA, NASA, and other sources.
"""

import asyncio
from typing import List, Dict, Any, Optional
from pathlib import Path
import re
import logging
from datetime import datetime

from .base_agent import BaseAgent
from ..core.config import Config
from ..core.http_client import HTTPClient


class SatelliteAgent(BaseAgent):
    """
    Agent for collecting satellite imagery data.
    
    Features:
    - Collects data from GOES satellites
    - Supports imagery from NOAA/NESDIS, NASA, and other sources
    - Handles dynamic URLs with time-based parameters
    - Extracts metadata from image filenames and headers
    """
    
    def __init__(self, config: Config, http_client: Optional[HTTPClient] = None):
        """Initialize the SatelliteAgent."""
        super().__init__(config, http_client)
        self.logger = logging.getLogger('agent.satellite')
    
    async def collect(self, data_dir: Path) -> List[Dict[str, Any]]:
        """
        Collect satellite imagery from configured sources.
        
        Args:
            data_dir: Directory to store collected data
            
        Returns:
            List of metadata dictionaries
        """
        # Create satellite data directory
        satellite_dir = data_dir / "satellite"
        satellite_dir.mkdir(exist_ok=True)
        
        # Get satellite URLs from config
        satellite_urls = self.config.get_data_source_urls('satellite').get('satellite', [])
        
        if not satellite_urls:
            self.logger.warning("No satellite URLs configured")
            return []
        
        # Ensure HTTP client is available
        await self.ensure_http_client()
        
        # Create tasks for all satellite URLs
        tasks = []
        for url in satellite_urls:
            tasks.append(self.process_satellite_url(url, satellite_dir))
        
        # Execute all tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions
        metadata_list = []
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"Error processing satellite data: {result}")
            elif result:
                metadata_list.append(result)
        
        return metadata_list
    
    async def process_satellite_url(self, url: str, satellite_dir: Path) -> Dict[str, Any]:
        """
        Process a single satellite URL.
        
        Args:
            url: URL to the satellite data
            satellite_dir: Directory to store satellite data
            
        Returns:
            Metadata dictionary
        """
        try:
            # Determine satellite type and region from URL
            satellite_info = self._determine_satellite_info(url)
            
            self.logger.info(f"Processing {satellite_info['type']} satellite data for {satellite_info['region']}")
            
            # Handle different URL types
            if url.endswith(('.png', '.jpg', '.gif')):
                # Direct image URL
                return await self._process_satellite_image(url, satellite_dir, satellite_info)
            else:
                # Web page URL - need to find the image
                return await self._process_satellite_page(url, satellite_dir, satellite_info)
        
        except Exception as e:
            self.logger.error(f"Error processing satellite data from {url}: {e}")
            return self.create_metadata(
                name="satellite_unknown",
                description="Failed to process satellite data",
                data_type="unknown",
                source_url=url,
                error=str(e)
            )
    
    async def _process_satellite_image(self, url: str, satellite_dir: Path, satellite_info: Dict[str, str]) -> Dict[str, Any]:
        """Process a direct satellite image URL."""
        # Generate filename from satellite info
        base_filename = url.split('/')[-1]
        satellite_type = satellite_info['type']
        region = satellite_info['region']
        
        # Extract timestamp from URL or filename if possible
        timestamp = self._extract_timestamp(url, base_filename)
        
        filename = f"satellite_{satellite_type}_{region}_{timestamp}_{base_filename}"
        
        # Download the image
        result = await self.http_client.download(url, save_to_disk=True, custom_file_path=satellite_dir / filename)
        
        if result.success:
            return self.create_metadata(
                name=f"satellite_{satellite_type}_{region}",
                description=f"{satellite_type} satellite image for {region}",
                data_type="image",
                source_url=url,
                file_path=str(result.file_path),
                satellite_type=satellite_type,
                region=region,
                timestamp=timestamp,
                content_type=result.content_type,
                size_bytes=result.size_bytes
            )
        else:
            return self.create_metadata(
                name=f"satellite_{satellite_type}_{region}",
                description=f"Failed to download {satellite_type} satellite image for {region}",
                data_type="image",
                source_url=url,
                error=result.error
            )
    
    async def _process_satellite_page(self, url: str, satellite_dir: Path, satellite_info: Dict[str, str]) -> Dict[str, Any]:
        """Process a satellite web page URL to extract images."""
        # Download the page content
        result = await self.http_client.download(url)
        
        if not result.success:
            return self.create_metadata(
                name=f"satellite_{satellite_info['type']}_{satellite_info['region']}",
                description=f"Failed to download {satellite_info['type']} satellite page for {satellite_info['region']}",
                data_type="html",
                source_url=url,
                error=result.error
            )
        
        # Save the original page
        page_filename = f"satellite_{satellite_info['type']}_{satellite_info['region']}_page.html"
        page_path = satellite_dir / page_filename
        
        with open(page_path, 'wb') as f:
            f.write(result.content)
        
        # Extract image URLs from the page
        content = result.content.decode('utf-8', errors='ignore')
        image_urls = self._extract_image_urls(content, url)
        
        # Download images
        image_metadata = []
        for img_url in image_urls:
            try:
                # Generate a metadata entry for this specific image
                image_result = await self._process_satellite_image(
                    img_url, 
                    satellite_dir, 
                    satellite_info
                )
                
                if image_result.get('status') == 'success':
                    image_metadata.append({
                        "url": img_url,
                        "file_path": image_result.get('file_path'),
                        "content_type": image_result.get('content_type'),
                        "size_bytes": image_result.get('size_bytes'),
                        "timestamp": image_result.get('timestamp')
                    })
            except Exception as e:
                self.logger.warning(f"Failed to download image {img_url}: {e}")
        
        return self.create_metadata(
            name=f"satellite_{satellite_info['type']}_{satellite_info['region']}",
            description=f"{satellite_info['type']} satellite data for {satellite_info['region']}",
            data_type="html",
            source_url=url,
            file_path=str(page_path),
            satellite_type=satellite_info['type'],
            region=satellite_info['region'],
            image_count=len(image_metadata),
            images=image_metadata
        )
    
    def _determine_satellite_info(self, url: str) -> Dict[str, str]:
        """Determine the type of satellite and region from the URL."""
        url_lower = url.lower()
        info = {
            'type': 'unknown',
            'region': 'unknown'
        }
        
        # Determine satellite type
        if 'goes' in url_lower:
            if 'goes-west' in url_lower or 'goes-17' in url_lower or 'goes17' in url_lower:
                info['type'] = 'goes-west'
            elif 'goes-east' in url_lower or 'goes-16' in url_lower or 'goes16' in url_lower:
                info['type'] = 'goes-east'
            else:
                info['type'] = 'goes'
        elif 'modis' in url_lower:
            info['type'] = 'modis'
        elif 'noaa' in url_lower or 'nesdis' in url_lower:
            info['type'] = 'noaa'
        elif 'nasa' in url_lower:
            info['type'] = 'nasa'
        
        # Determine region
        region_keywords = {
            'hawaii': ['hawaii', 'hi', 'pacific', 'pac'],
            'north_pacific': ['north_pacific', 'npac', 'nopac'],
            'south_pacific': ['south_pacific', 'spac', 'sopac'],
            'pacific': ['pacific', 'pac'],
            'oahu': ['oahu', 'honolulu'],
            'maui': ['maui'],
            'kauai': ['kauai'],
            'big_island': ['big_island', 'hawaii_island'],
            'us': ['usa', 'us', 'conus'],
            'global': ['global', 'world']
        }
        
        # Check URL for region keywords
        for region, keywords in region_keywords.items():
            for keyword in keywords:
                if keyword in url_lower:
                    info['region'] = region
                    break
            if info['region'] != 'unknown':
                break
        
        return info
    
    def _extract_image_urls(self, html_content: str, base_url: str) -> List[str]:
        """Extract satellite image URLs from HTML content."""
        # Look for image URLs that are likely to be satellite images
        image_patterns = [
            # Standard image tags
            r'<img[^>]+src="([^"]+\.(jpg|jpeg|png|gif))"',
            # Links to images
            r'<a[^>]+href="([^"]+\.(jpg|jpeg|png|gif))"',
            # Special cases for satellite imagery
            r'data-url="([^"]+\.(jpg|jpeg|png|gif))"',
            r'data-image="([^"]+\.(jpg|jpeg|png|gif))"'
        ]
        
        # Prioritize satellite-specific filenames
        sat_keywords = ['satellite', 'goes', 'vis', 'ir', 'wv', 'geocolor', 'modis']
        
        image_urls = []
        for pattern in image_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            for match in matches:
                img_url = match[0]
                
                # Handle relative URLs
                if not img_url.startswith(('http://', 'https://')):
                    img_url = img_url.lstrip('/')
                    
                    # Add base URL
                    if base_url.endswith('/'):
                        img_url = base_url + img_url
                    else:
                        img_url = base_url + '/' + img_url
                
                # Check if this is likely a satellite image
                is_sat_image = any(keyword in img_url.lower() for keyword in sat_keywords)
                
                if is_sat_image:
                    # Prioritize these images
                    image_urls.insert(0, img_url)
                else:
                    image_urls.append(img_url)
        
        return image_urls
    
    def _extract_timestamp(self, url: str, filename: str) -> str:
        """
        Extract timestamp from URL or filename.
        
        Args:
            url: Source URL
            filename: Base filename
            
        Returns:
            Timestamp string or current date
        """
        # Common timestamp patterns in satellite filenames
        timestamp_patterns = [
            # YYYYMMDD_HHMMSS format
            r'(\d{8}_\d{6})',
            # YYYYMMDD format
            r'(\d{8})',
            # YYYYDDD (day-of-year) format
            r'(\d{4}\d{3})',
            # HHMMZ format (hour-minute UTC)
            r'(\d{4}Z)'
        ]
        
        # Check both URL and filename for timestamp patterns
        for pattern in timestamp_patterns:
            # Check filename first
            match = re.search(pattern, filename)
            if match:
                return match.group(1)
            
            # Then check URL
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        # Default to current date if no timestamp found
        return datetime.now().strftime("%Y%m%d")