import json
import asyncio
import logging
from typing import Dict, Any, Callable, Coroutine, Optional, List
from confluent_kafka import Producer, Consumer, KafkaError
from concurrent.futures import ThreadPoolExecutor
from app.config import settings

logger = logging.getLogger(__name__)

class KafkaService:
    def __init__(self):
        self.producer = None
        self.consumers = {}
        self.handlers = {}
        self.consumer_tasks = {}
        self.executor = ThreadPoolExecutor(max_workers=10)
        self._running = True
        
    async def start_producer(self):
        self.producer = Producer({
            'bootstrap.servers': settings.KAFKA_BOOTSTRAP_SERVERS,
            'client.id': 'fastapi-producer',
            'linger.ms': 10,
            'batch.size': 16384
        })
        logger.info("Kafka producer started")
        
    async def stop_producer(self):
        if self.producer:
            # Flush any remaining messages
            self.producer.flush()
            self.producer = None
            logger.info("Kafka producer stopped")
            
    async def send_message(self, topic: str, message: Dict[str, Any], key: Optional[str] = None):
        if not self.producer:
            await self.start_producer()
        
        # Serialize message
        value = json.dumps(message).encode('utf-8')
        key_bytes = key.encode() if key else None
        
        # Create a future for async handling
        future = asyncio.Future()
        
        def delivery_callback(err, msg):
            if err:
                logger.error(f"Message delivery failed: {err}")
                future.set_exception(Exception(f"Message delivery failed: {err}"))
            else:
                logger.debug(f"Message delivered to {msg.topic()} [{msg.partition()}]")
                future.set_result(None)
        
        # Send message
        self.producer.produce(
            topic,
            value=value,
            key=key_bytes,
            callback=delivery_callback
        )
        
        # Trigger delivery callbacks
        self.producer.poll(0)
        
        # Wait for delivery
        await future
        logger.debug(f"Message sent to topic {topic}: {message}")
    
    async def register_consumer(self, topic: str, 
                               handler: Callable[[Dict[str, Any]], Coroutine[Any, Any, None]],
                               group_id: Optional[str] = None):
        """Register a handler for a Kafka topic"""
        self.handlers[topic] = handler
        
    async def start_consumer(self, topic: str, group_id: Optional[str] = None):
        """Start a consumer for a topic"""
        if topic in self.consumers:
            logger.warning(f"Consumer for topic {topic} already exists")
            return
            
        consumer_config = {
            'bootstrap.servers': settings.KAFKA_BOOTSTRAP_SERVERS,
            'group.id': group_id or f"fastapi-group-{topic}",
            'auto.offset.reset': 'latest',
            'enable.auto.commit': True,
            'auto.commit.interval.ms': 1000,
            'session.timeout.ms': 6000,
            'max.poll.interval.ms': 300000
        }
        
        consumer = Consumer(consumer_config)
        consumer.subscribe([topic])
        
        self.consumers[topic] = consumer
        logger.info(f"Started consumer for topic {topic}")
        
        # Start the consumption task
        task = asyncio.create_task(self._consume_messages(topic))
        self.consumer_tasks[topic] = task
        
    async def _consume_messages(self, topic: str):
        """Continuously consume messages from a topic"""
        consumer = self.consumers.get(topic)
        if not consumer:
            logger.error(f"No consumer found for topic {topic}")
            return
            
        handler = self.handlers.get(topic)
        if not handler:
            logger.error(f"No handler registered for topic {topic}")
            return
        
        loop = asyncio.get_event_loop()
        
        def poll_messages():
            return consumer.poll(timeout=1.0)
        
        try:
            while self._running:
                # Poll for messages in thread pool to avoid blocking
                msg = await loop.run_in_executor(self.executor, poll_messages)
                
                if msg is None:
                    continue
                    
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        logger.debug(f"Reached end of partition for topic {topic}")
                    else:
                        logger.error(f"Consumer error: {msg.error()}")
                    continue
                
                try:
                    # Deserialize message
                    value = json.loads(msg.value().decode('utf-8'))
                    logger.debug(f"Received message from {topic}: {value}")
                    
                    # Call handler
                    await handler(value)
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode message: {e}")
                except Exception as e:
                    logger.exception(f"Error processing message: {e}")
                    
        except Exception as e:
            logger.exception(f"Error in consumer loop: {e}")
        finally:
            consumer.close()
            logger.info(f"Consumer for topic {topic} closed")
            
    async def stop_all_consumers(self):
        """Stop all consumers"""
        self._running = False
        
        # Cancel all consumer tasks
        for topic, task in self.consumer_tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            logger.info(f"Stopped consumer task for topic {topic}")
        
        # Close all consumers
        for topic, consumer in self.consumers.items():
            consumer.close()
            logger.info(f"Closed consumer for topic {topic}")
            
        self.consumers = {}
        self.consumer_tasks = {}
        
        # Shutdown executor
        self.executor.shutdown(wait=True)

# Create a global instance
kafka_service = KafkaService()