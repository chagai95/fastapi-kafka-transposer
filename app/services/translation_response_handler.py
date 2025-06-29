import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class TranslationResponseHandler:
    """Handles async responses for translation requests"""
    
    def __init__(self):
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._cleanup_task = None
        
    async def start(self):
        """Start the cleanup task"""
        self._cleanup_task = asyncio.create_task(self._cleanup_expired_futures())
        
    async def stop(self):
        """Stop the cleanup task"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
    
    def register_request(self, source_id: str) -> asyncio.Future:
        """Register a new request and return a future for its response"""
        future = asyncio.Future()
        self._pending_requests[source_id] = future
        logger.info(f"Registered future for {source_id}. Total pending: {len(self._pending_requests)}")
        logger.info(f"Current pending requests: {list(self._pending_requests.keys())}")
        return future
    
    async def handle_response(self, source_id: str, response_data: Dict[str, Any]):
        """Handle a response from Kafka and complete the future"""
        logger.info(f"Handling response for {source_id}: {response_data}")
        logger.info(f"Current pending requests: {list(self._pending_requests.keys())}")
        
        future = self._pending_requests.pop(source_id, None)
        if future and not future.done():
            future.set_result(response_data)
            logger.info(f"Successfully completed future for {source_id}")
        else:
            if future is None:
                logger.error(f"No pending future found for {source_id}. Available: {list(self._pending_requests.keys())}")
            elif future.done():
                logger.warning(f"Future for {source_id} was already completed")
    
    async def wait_for_response(self, source_id: str, timeout: float = 30.0) -> Optional[Dict[str, Any]]:
        """Wait for a response with timeout"""
        # This method shouldn't be used anymore - register_request should be called separately
        logger.warning(f"wait_for_response called for {source_id} - this method is deprecated")
        future = self.register_request(source_id)
        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for response for {source_id}")
            self._pending_requests.pop(source_id, None)
            return None
        except Exception as e:
            logger.error(f"Error waiting for response for {source_id}: {e}")
            self._pending_requests.pop(source_id, None)
            raise
    
    async def _cleanup_expired_futures(self):
        """Periodically clean up abandoned futures"""
        while True:
            try:
                await asyncio.sleep(60)  # Run every minute
                expired = []
                for source_id, future in self._pending_requests.items():
                    if future.done():
                        expired.append(source_id)
                        
                for source_id in expired:
                    self._pending_requests.pop(source_id, None)
                    
                if expired:
                    logger.info(f"Cleaned up {len(expired)} expired futures")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")

# Global instance
translation_response_handler = TranslationResponseHandler()