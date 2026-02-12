"""
Marine Monitor - Real-time Vessel Tracking

Connects to AISstream.io WebSocket API to receive real-time vessel data
and stores it in PostgreSQL marine schema.

Features:
- WebSocket connection with automatic reconnection
- Batch processing for efficient database inserts
- Handles multiple AIS message types
- Configurable filtering by MMSI and bounding box
- Graceful shutdown handling
"""

import asyncio
import websockets
import json
import logging
import os
import signal
import sys
from datetime import datetime
from typing import Dict, List, Optional, Set
from pathlib import Path

# Add root to path for imports
sys.path.append(str(Path(__file__).resolve().parent))

from core.marine_models import VesselPosition, VesselMetadata
from marine_pg_provider import (
    save_vessel_positions,
    save_vessel_metadata,
    increment_vessel_position_count,
    check_marine_schema_exists,
    init_connection_pool
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("marine_monitor.log", encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class MarineMonitor:
    """
    Real-time marine vessel monitoring using AISstream.io WebSocket API.
    """
    
    def __init__(
        self,
        api_key: str,
        bounding_boxes: Optional[List[List[List[float]]]] = None,
        filter_mmsi: Optional[List[str]] = None,
        batch_size: int = 100,
        schema: str = 'marine'
    ):
        """
        Initialize Marine Monitor.
        
        Args:
            api_key: AISstream.io API key
            bounding_boxes: List of bounding boxes [[south_lat, west_lon], [north_lat, east_lon]]
                           Default: Global coverage [[-90, -180], [90, 180]]
            filter_mmsi: Optional list of MMSI codes to filter
            batch_size: Number of positions to batch before inserting to DB
            schema: PostgreSQL schema name (default: 'marine')
        """
        self.api_key = api_key
        self.bounding_boxes = bounding_boxes or [[[-90, -180], [90, 180]]]
        self.filter_mmsi = filter_mmsi
        self.batch_size = batch_size
        self.schema = schema
        
        # WebSocket configuration
        self.ws_url = "wss://stream.aisstream.io/v0/stream"
        self.websocket = None
        
        # Batch processing
        self.position_batch: List[Dict] = []
        self.position_counts: Dict[str, int] = {}  # Track position counts per MMSI
        
        # Tracking
        self.messages_received = 0
        self.positions_saved = 0
        self.positions_filtered = 0  # Track positions filtered by bounding box
        self.metadata_saved = 0
        self.errors = 0
        self.start_time = datetime.utcnow()
        
        # Async task management for proper cleanup
        self.pending_tasks: Set[asyncio.Task] = set()
        
        # Shutdown flag
        self.should_stop = False
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.should_stop = True
    
    def _is_within_bounding_box(self, latitude: float, longitude: float) -> bool:
        """
        Check if a position is within any of the configured bounding boxes.
        
        Args:
            latitude: Latitude in degrees (-90 to 90)
            longitude: Longitude in degrees (-180 to 180)
        
        Returns:
            bool: True if position is within any bounding box, False otherwise
        """
        for bbox in self.bounding_boxes:
            # bbox format: [[south_lat, west_lon], [north_lat, east_lon]]
            south_lat, west_lon = bbox[0]
            north_lat, east_lon = bbox[1]
            
            # Check if position is within this bounding box
            if south_lat <= latitude <= north_lat and west_lon <= longitude <= east_lon:
                return True
        
        return False
    
    async def connect_and_subscribe(self) -> websockets.WebSocketClientProtocol:
        """
        Establish WebSocket connection and send subscription message.
        
        Returns:
            WebSocket connection
        """
        logger.info(f"Connecting to {self.ws_url}...")
        socket = await websockets.connect(self.ws_url)
        
        # Build subscription message
        subscription = {
            "Apikey": self.api_key,
            "BoundingBoxes": self.bounding_boxes
        }
        
        # Add optional filters
        if self.filter_mmsi:
            subscription["FiltersShipMMSI"] = self.filter_mmsi
        
        # Filter for position reports and static data
        subscription["FilterMessageTypes"] = [
            "PositionReport",
            "ShipStaticData"
        ]
        
        # Send subscription
        await socket.send(json.dumps(subscription))
        logger.info(f"Subscription sent. Monitoring vessels...")
        logger.info(f"Bounding boxes: {self.bounding_boxes}")
        if self.filter_mmsi:
            logger.info(f"Filtering {len(self.filter_mmsi)} MMSI codes")
        
        return socket
    
    def _process_position_report(self, message: dict) -> None:
        """
        Process position report message (AIS types 1, 2, 3, 18).
        
        Args:
            message: AIS message dictionary
        """
        try:
            position = VesselPosition.from_ais_message(message)
            if not position:
                return
            
            # CRITICAL: Validate position is within configured bounding box
            # This provides local filtering even if server-side filtering fails
            if not self._is_within_bounding_box(position.latitude, position.longitude):
                self.positions_filtered += 1
                if self.positions_filtered <= 5:  # Log first few filtered positions
                    logger.warning(
                        f"Filtered position outside bounding box: MMSI {position.mmsi} at "
                        f"({position.latitude:.4f}, {position.longitude:.4f})"
                    )
                return
            
            # Convert to dictionary for batch insert
            position_dict = {
                'mmsi': position.mmsi,
                'timestamp': position.timestamp,
                'latitude': position.latitude,
                'longitude': position.longitude,
                'speed_over_ground': position.speed_over_ground,
                'course_over_ground': position.course_over_ground,
                'heading': position.heading,
                'navigation_status': position.navigation_status,
                'rate_of_turn': position.rate_of_turn,
                'position_accuracy': position.position_accuracy,
                'message_type': position.message_type
            }
            
            # Add to batch
            self.position_batch.append(position_dict)
            
            # Track position count for this MMSI
            self.position_counts[position.mmsi] = self.position_counts.get(position.mmsi, 0) + 1
            
            # Log first position for each vessel
            if self.position_counts[position.mmsi] == 1:
                logger.info(
                    f"Tracking new vessel: MMSI {position.mmsi} at "
                    f"({position.latitude:.4f}, {position.longitude:.4f})"
                )
            
            # Flush batch if full - track the task for proper cleanup
            if len(self.position_batch) >= self.batch_size:
                task = asyncio.create_task(self._flush_position_batch())
                self.pending_tasks.add(task)
                task.add_done_callback(self.pending_tasks.discard)
                
        except Exception as e:
            logger.error(f"Error processing position report: {e}")
            self.errors += 1
    
    def _process_ship_static_data(self, message: dict) -> None:
        """
        Process ship static data message (AIS type 5).
        
        Args:
            message: AIS message dictionary
        """
        try:
            metadata = VesselMetadata.from_ais_message(message)
            if not metadata:
                return
            
            # Convert to dictionary for database insert
            metadata_dict = {
                'mmsi': metadata.mmsi,
                'vessel_name': metadata.vessel_name,
                'callsign': metadata.callsign,
                'imo_number': metadata.imo_number,
                'vessel_type': metadata.vessel_type,
                'vessel_type_description': metadata.vessel_type_description,
                'length': metadata.length,
                'width': metadata.width,
                'draught': metadata.draught,
                'destination': metadata.destination,
                'eta': metadata.eta,
                'cargo_type': metadata.cargo_type,
                'dimension_to_bow': metadata.dimension_to_bow,
                'dimension_to_stern': metadata.dimension_to_stern,
                'dimension_to_port': metadata.dimension_to_port,
                'dimension_to_starboard': metadata.dimension_to_starboard,
                'position_fixing_device': metadata.position_fixing_device
            }
            
            # Save immediately (metadata is infrequent, no need to batch) - track task for cleanup
            task = asyncio.create_task(self._save_metadata(metadata_dict))
            self.pending_tasks.add(task)
            task.add_done_callback(self.pending_tasks.discard)
            
            logger.info(
                f"Received metadata for {metadata.vessel_name or 'Unknown'} "
                f"(MMSI: {metadata.mmsi}, Type: {metadata.vessel_type_description})"
            )
            
        except Exception as e:
            logger.error(f"Error processing ship static data: {e}")
            self.errors += 1
    
    async def _flush_position_batch(self) -> None:
        """Flush position batch to database."""
        if not self.position_batch:
            return
        
        batch = self.position_batch.copy()
        self.position_batch.clear()
        
        try:
            # Save batch to database
            if save_vessel_positions(batch, schema=self.schema):
                self.positions_saved += len(batch)
                
                # Update position counts in metadata table
                for mmsi, count in self.position_counts.items():
                    increment_vessel_position_count(mmsi, count, schema=self.schema)
                self.position_counts.clear()
                
                logger.info(f"Saved batch of {len(batch)} positions to database")
            else:
                logger.error(f"Failed to save batch of {len(batch)} positions")
                
        except Exception as e:
            logger.error(f"Error flushing position batch: {e}")
            self.errors += 1
    
    async def _save_metadata(self, metadata_dict: dict) -> None:
        """Save vessel metadata to database."""
        try:
            if save_vessel_metadata(metadata_dict, schema=self.schema):
                self.metadata_saved += 1
            else:
                logger.error(f"Failed to save metadata for vessel {metadata_dict['mmsi']}")
        except Exception as e:
            logger.error(f"Error saving metadata: {e}")
            self.errors += 1
    
    def _process_message(self, message: dict) -> None:
        """
        Route message to appropriate handler based on message type.
        
        Args:
            message: AIS message dictionary
        """
        message_type = message.get("MessageType")
        
        if message_type == "PositionReport":
            self._process_position_report(message)
        elif message_type == "ShipStaticData":
            self._process_ship_static_data(message)
        else:
            # Ignore other message types for now
            logger.debug(f"Ignoring message type: {message_type}")
    
    def _log_statistics(self) -> None:
        """Log monitoring statistics."""
        elapsed = (datetime.utcnow() - self.start_time).total_seconds()
        rate = self.messages_received / elapsed if elapsed > 0 else 0
        
        logger.info("=" * 60)
        logger.info("Marine Monitor Statistics")
        logger.info("=" * 60)
        logger.info(f"Running time: {elapsed:.0f} seconds")
        logger.info(f"Messages received: {self.messages_received}")
        logger.info(f"Positions saved: {self.positions_saved}")
        logger.info(f"Positions filtered (outside bbox): {self.positions_filtered}")
        logger.info(f"Metadata records saved: {self.metadata_saved}")
        logger.info(f"Unique vessels tracked: {len(self.position_counts)}")
        logger.info(f"Pending tasks: {len(self.pending_tasks)}")
        logger.info(f"Message rate: {rate:.2f} msg/sec")
        logger.info(f"Errors: {self.errors}")
        logger.info("=" * 60)
    
    async def run(self) -> None:
        """
        Main monitoring loop with automatic reconnection.
        """
        logger.info("Starting Marine Monitor...")
        
        # Check database connectivity and schema
        logger.info("Checking database connection...")
        if not check_marine_schema_exists(self.schema):
            logger.error(f"Marine schema '{self.schema}' does not exist!")
            logger.error("Please run create_marine_schema.sql first")
            sys.exit(1)
        
        reconnect_delay = 1  # Start with 1 second delay
        max_reconnect_delay = 60  # Max 60 seconds between reconnects
        
        while not self.should_stop:
            try:
                # Connect and subscribe
                socket = await self.connect_and_subscribe()
                self.websocket = socket
                reconnect_delay = 1  # Reset delay on successful connection
                
                # Log statistics every 60 seconds
                last_stats_time = datetime.utcnow()
                stats_interval = 60  # seconds
                
                # Receive messages
                async for message_str in socket:
                    if self.should_stop:
                        break
                    
                    try:
                        message = json.loads(message_str)
                        self.messages_received += 1
                        self._process_message(message)
                        
                        # Log statistics periodically
                        now = datetime.utcnow()
                        if (now - last_stats_time).total_seconds() >= stats_interval:
                            self._log_statistics()
                            last_stats_time = now
                            
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse JSON message: {e}")
                        self.errors += 1
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                        self.errors += 1
                
            except websockets.ConnectionClosed as e:
                logger.warning(f"WebSocket connection closed: {e}")
                
                # Flush any remaining positions before reconnecting
                await self._flush_position_batch()
                
                if not self.should_stop:
                    logger.info(f"Reconnecting in {reconnect_delay} seconds...")
                    await asyncio.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)
                    
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                self.errors += 1
                
                if not self.should_stop:
                    logger.info(f"Retrying in {reconnect_delay} seconds...")
                    await asyncio.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)
        
        # Cleanup on shutdown
        logger.info("Shutting down...")
        
        # Flush remaining positions
        await self._flush_position_batch()
        
        # Wait for all pending tasks to complete (with timeout)
        if self.pending_tasks:
            logger.info(f"Waiting for {len(self.pending_tasks)} pending tasks to complete...")
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self.pending_tasks, return_exceptions=True),
                    timeout=10.0
                )
                logger.info("All pending tasks completed")
            except asyncio.TimeoutError:
                logger.warning("Timeout waiting for tasks, cancelling remaining tasks...")
                for task in self.pending_tasks:
                    if not task.done():
                        task.cancel()
                # Wait for cancellations to complete
                await asyncio.gather(*self.pending_tasks, return_exceptions=True)
        
        # Close WebSocket connection
        if self.websocket:
            try:
                await asyncio.wait_for(self.websocket.close(), timeout=5.0)
                logger.info("WebSocket connection closed")
            except asyncio.TimeoutError:
                logger.warning("Timeout closing WebSocket")
            except Exception as e:
                logger.warning(f"Error closing WebSocket: {e}")
        
        # Final statistics
        self._log_statistics()
        logger.info("Marine Monitor stopped gracefully")


def main():
    """Entry point for running marine monitor directly."""
    # Load configuration from environment variables
    api_key = os.getenv("AIS_STREAM_API_KEY", "806cb56388d212f6d346775d69190649dc456907")
    if not api_key:
        logger.error("AIS_STREAM_API_KEY environment variable not set!")
        logger.error("Please set your AISstream.io API key")
        sys.exit(1)
    
    # Optional: Parse bounding box from environment
    # Default to Mediterranean if not specified (to avoid unnecessary global data collection)
    default_bbox = [[[30, -6], [46, 37]]]  # Mediterranean Sea
    
    bbox_str = os.getenv("AIS_BOUNDING_BOX")
    bounding_boxes = None
    if bbox_str:
        try:
            bounding_boxes = json.loads(bbox_str)
            logger.info(f"Using configured bounding box: {bounding_boxes}")
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse AIS_BOUNDING_BOX, using Mediterranean region")
            bounding_boxes = default_bbox
    else:
        bounding_boxes = default_bbox
        logger.info(f"No AIS_BOUNDING_BOX configured, using Mediterranean region: {bounding_boxes}")
    
    # Optional: Parse MMSI filter from environment
    mmsi_str = os.getenv("AIS_FILTER_MMSI")
    filter_mmsi = None
    if mmsi_str:
        filter_mmsi = [m.strip() for m in mmsi_str.split(',')]
    
    # Batch size
    batch_size = int(os.getenv("AIS_BATCH_SIZE", "100"))
    
    # Initialize database connection pool
    logger.info("Initializing database connection pool...")
    if not init_connection_pool():
        logger.error("Failed to initialize database connection pool")
        sys.exit(1)
    
    # Create and run monitor
    monitor = MarineMonitor(
        api_key=api_key,
        bounding_boxes=bounding_boxes,
        filter_mmsi=filter_mmsi,
        batch_size=batch_size
    )
    
    # Run async event loop
    asyncio.run(monitor.run())


if __name__ == "__main__":
    main()
