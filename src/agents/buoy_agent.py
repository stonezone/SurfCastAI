"""
NDBC Buoy Agent for collecting data from NOAA NDBC buoys.
"""

import asyncio
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from bs4 import BeautifulSoup

from .base_agent import BaseAgent
from ..core.config import Config
from ..core.http_client import HTTPClient


class BuoyAgent(BaseAgent):
    """
    Agent for collecting buoy data from NOAA National Data Buoy Center (NDBC).
    
    Features:
    - Collects real-time buoy data
    - Parses tabular data into structured format
    - Extracts current conditions for quick access
    - Supports multiple buoy stations
    """
    
    def __init__(self, config: Config, http_client: Optional[HTTPClient] = None):
        """Initialize the BuoyAgent."""
        super().__init__(config, http_client)
        self.base_url = "https://www.ndbc.noaa.gov"
    
    async def collect(self, data_dir: Path) -> List[Dict[str, Any]]:
        """
        Collect buoy data from NDBC.
        
        Args:
            data_dir: Directory to store collected data
            
        Returns:
            List of metadata dictionaries
        """
        # Ensure data directory exists
        buoy_dir = data_dir / "buoys"
        buoy_dir.mkdir(exist_ok=True)
        
        # Get buoy URLs from config
        buoy_urls = self.config.get_data_source_urls('buoys').get('buoys', [])
        
        if not buoy_urls:
            self.logger.warning("No buoy URLs configured")
            return []
        
        # Ensure HTTP client is available
        await self.ensure_http_client()
        
        # Create tasks for all buoy URLs
        tasks = []
        for url in buoy_urls:
            tasks.append(self.process_buoy(url, buoy_dir))
        
        # Execute all tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions
        metadata_list = []
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"Error processing buoy: {result}")
            elif result:
                metadata_list.append(result)
        
        return metadata_list
    
    async def process_buoy(self, url: str, buoy_dir: Path) -> Dict[str, Any]:
        """
        Process a single buoy URL.
        
        Args:
            url: URL to the buoy data
            buoy_dir: Directory to store buoy data
            
        Returns:
            Metadata dictionary
        """
        try:
            # Extract station ID from URL
            station_id = url.split('station=')[-1] if 'station=' in url else url.split('/')[-1]
            station_id = station_id.split('&')[0] if '&' in station_id else station_id
            
            self.logger.info(f"Processing buoy station {station_id}")
            
            # Download the buoy data page
            result = await self.http_client.download(url)
            
            if not result.success:
                return self.create_metadata(
                    name=f"buoy_{station_id}",
                    description=f"Failed to fetch buoy data for station {station_id}",
                    data_type="html",
                    source_url=url,
                    error=result.error
                )
            
            # Parse the HTML content
            content = result.content.decode('utf-8', errors='ignore')
            
            # Try to find the data table
            soup = BeautifulSoup(content, 'html.parser')
            data_table = soup.find('table', {'class': 'dataTable'})
            
            if data_table:
                # Parse the table into structured data
                buoy_data = self._parse_buoy_table(data_table, station_id)
                
                # Save the parsed data
                filename = f"buoy_{station_id}.json"
                file_path = buoy_dir / filename
                
                with open(file_path, 'w') as f:
                    json.dump(buoy_data, f, indent=2)
                
                return self.create_metadata(
                    name=f"buoy_{station_id}",
                    description=f"Buoy data from station {station_id}",
                    data_type="json",
                    source_url=url,
                    file_path=str(file_path),
                    station_id=station_id,
                    data_points=len(buoy_data.get('observations', [])),
                    current_conditions=buoy_data.get('current_conditions')
                )
            else:
                # Save raw HTML if table not found
                filename = f"buoy_{station_id}_raw.html"
                file_path = buoy_dir / filename
                
                with open(file_path, 'w') as f:
                    f.write(content)
                
                return self.create_metadata(
                    name=f"buoy_{station_id}",
                    description=f"Raw HTML from buoy station {station_id}",
                    data_type="html",
                    source_url=url,
                    file_path=str(file_path),
                    station_id=station_id,
                    warning="Could not parse data table"
                )
        
        except Exception as e:
            self.logger.error(f"Error processing buoy {url}: {e}")
            return self.create_metadata(
                name=f"buoy_{station_id if 'station_id' in locals() else 'unknown'}",
                description="Failed to process buoy data",
                data_type="unknown",
                source_url=url,
                error=str(e)
            )
    
    def _parse_buoy_table(self, table, station_id: str) -> Dict[str, Any]:
        """
        Parse NDBC buoy data table into structured format.
        
        Args:
            table: BeautifulSoup table element
            station_id: Buoy station ID
            
        Returns:
            Structured buoy data dictionary
        """
        try:
            data = {
                'station_id': station_id,
                'observations': []
            }
            
            # Find all rows
            rows = table.find_all('tr')
            
            # Extract headers
            headers = []
            header_row = rows[0] if rows else None
            if header_row:
                headers = [th.text.strip() for th in header_row.find_all(['th', 'td'])]
            
            # Extract data rows
            for row in rows[1:]:
                cells = row.find_all('td')
                if cells:
                    observation = {}
                    for i, cell in enumerate(cells):
                        if i < len(headers):
                            observation[headers[i]] = cell.text.strip()
                    data['observations'].append(observation)
            
            # Extract current conditions if available
            if data['observations']:
                current = data['observations'][0]
                data['current_conditions'] = {
                    'wave_height': current.get('WVHT', 'N/A'),
                    'dominant_period': current.get('DPD', 'N/A'),
                    'wind_speed': current.get('WSPD', 'N/A'),
                    'wind_direction': current.get('WDIR', 'N/A'),
                    'timestamp': current.get('Date', 'N/A'),
                    'water_temp': current.get('WTMP', 'N/A'),
                    'air_temp': current.get('ATMP', 'N/A'),
                    'pressure': current.get('PRES', 'N/A')
                }
            
            return data
            
        except Exception as e:
            self.logger.error(f"Error parsing buoy table: {e}")
            return {
                'station_id': station_id,
                'error': str(e),
                'raw_html': str(table)
            }