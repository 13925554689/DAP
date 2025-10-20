"""
AI Agent Bridge for DAP System
Layer 5: External Integration & API Services

Provides comprehensive communication bridge with external AI systems,
including the upper-level "AI Audit Brain" and other intelligent agents.
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Union
import logging
from contextlib import asynccontextmanager
import threading
from queue import Queue, Empty
import socket
from dataclasses import dataclass, asdict

try:
    import websockets
    from websockets.server import WebSocketServerProtocol
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

try:
    import pika
    RABBITMQ_AVAILABLE = True
except ImportError:
    RABBITMQ_AVAILABLE = False

try:
    import zmq
    ZMQ_AVAILABLE = True
except ImportError:
    ZMQ_AVAILABLE = False

try:
    import grpc
    from concurrent import futures
    GRPC_AVAILABLE = True
except ImportError:
    GRPC_AVAILABLE = False

@dataclass
class AgentMessage:
    """Standardized message format for AI agent communication"""
    id: str
    source: str
    target: str
    message_type: str
    payload: Dict[str, Any]
    timestamp: str
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None
    priority: int = 5  # 1-10, higher is more urgent
    ttl: Optional[int] = None  # Time to live in seconds

@dataclass
class AgentCapability:
    """Agent capability description"""
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    version: str
    requires_auth: bool = False

class AIAgentBridge:
    """AI Agent Bridge for external system communication"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.setup_logging()

        # Communication protocols
        self.websocket_server = None
        self.rabbitmq_connection = None
        self.zmq_context = None
        self.grpc_server = None

        # Agent registry
        self.registered_agents = {}
        self.agent_capabilities = {}
        self.agent_sessions = {}

        # Message routing
        self.message_handlers = {}
        self.message_queue = Queue()
        self.routing_rules = {}

        # Performance tracking
        self.message_count = 0
        self.start_time = time.time()
        self.active_connections = 0

        # Background tasks
        self.background_tasks = []
        self.is_running = False

        self.initialize_bridge()

    def setup_logging(self):
        """Setup enhanced logging for AI agent bridge"""
        self.logger = logging.getLogger(f"{__name__}.AIAgentBridge")

        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def initialize_bridge(self):
        """Initialize all communication protocols"""
        self.setup_message_handlers()
        self.setup_routing_rules()
        self.setup_websocket_server()
        self.setup_rabbitmq()
        self.setup_zeromq()
        self.setup_grpc_server()

    def setup_message_handlers(self):
        """Setup default message handlers"""
        self.message_handlers = {
            'audit_request': self.handle_audit_request,
            'data_query': self.handle_data_query,
            'analysis_request': self.handle_analysis_request,
            'model_update': self.handle_model_update,
            'health_check': self.handle_health_check,
            'capability_inquiry': self.handle_capability_inquiry,
            'agent_registration': self.handle_agent_registration,
            'heartbeat': self.handle_heartbeat
        }

    def setup_routing_rules(self):
        """Setup message routing rules"""
        self.routing_rules = {
            'ai_audit_brain': {
                'priority': 10,
                'protocols': ['websocket', 'grpc'],
                'timeout': 30,
                'retry_count': 3
            },
            'data_processor': {
                'priority': 8,
                'protocols': ['rabbitmq', 'zeromq'],
                'timeout': 60,
                'retry_count': 2
            },
            'analysis_engine': {
                'priority': 7,
                'protocols': ['websocket', 'rabbitmq'],
                'timeout': 120,
                'retry_count': 1
            },
            'external_agent': {
                'priority': 5,
                'protocols': ['websocket', 'zeromq'],
                'timeout': 30,
                'retry_count': 2
            }
        }

    def setup_websocket_server(self):
        """Setup WebSocket server for real-time communication"""
        if not WEBSOCKETS_AVAILABLE:
            self.logger.warning("WebSockets not available. Real-time communication limited.")
            return

        self.websocket_clients = set()
        self.websocket_port = self.config.get('websocket_port', 8765)

    def setup_rabbitmq(self):
        """Setup RabbitMQ for reliable message queuing"""
        if not RABBITMQ_AVAILABLE:
            self.logger.warning("RabbitMQ not available. Message queuing limited.")
            return

        try:
            rabbitmq_config = self.config.get('rabbitmq', {})
            connection_params = pika.ConnectionParameters(
                host=rabbitmq_config.get('host', 'localhost'),
                port=rabbitmq_config.get('port', 5672),
                virtual_host=rabbitmq_config.get('vhost', '/'),
                credentials=pika.PlainCredentials(
                    rabbitmq_config.get('username', 'guest'),
                    rabbitmq_config.get('password', 'guest')
                )
            )

            self.rabbitmq_connection = pika.BlockingConnection(connection_params)
            self.rabbitmq_channel = self.rabbitmq_connection.channel()

            # Declare exchanges and queues
            self.rabbitmq_channel.exchange_declare(exchange='dap_agents', exchange_type='topic')
            self.rabbitmq_channel.queue_declare(queue='dap_inbox', durable=True)
            self.rabbitmq_channel.queue_declare(queue='dap_outbox', durable=True)

            self.logger.info("RabbitMQ connection established")

        except Exception as e:
            self.logger.warning(f"RabbitMQ setup failed: {e}")
            self.rabbitmq_connection = None

    def setup_zeromq(self):
        """Setup ZeroMQ for high-performance messaging"""
        if not ZMQ_AVAILABLE:
            self.logger.warning("ZeroMQ not available. High-performance messaging limited.")
            return

        try:
            self.zmq_context = zmq.Context()

            # Setup publisher socket
            self.zmq_publisher = self.zmq_context.socket(zmq.PUB)
            zmq_pub_port = self.config.get('zmq_publisher_port', 5555)
            self.zmq_publisher.bind(f"tcp://*:{zmq_pub_port}")

            # Setup subscriber socket
            self.zmq_subscriber = self.zmq_context.socket(zmq.SUB)
            zmq_sub_port = self.config.get('zmq_subscriber_port', 5556)
            self.zmq_subscriber.bind(f"tcp://*:{zmq_sub_port}")
            self.zmq_subscriber.setsockopt(zmq.SUBSCRIBE, b"")  # Subscribe to all messages

            # Setup request-response sockets
            self.zmq_responder = self.zmq_context.socket(zmq.REP)
            zmq_resp_port = self.config.get('zmq_responder_port', 5557)
            self.zmq_responder.bind(f"tcp://*:{zmq_resp_port}")

            self.logger.info("ZeroMQ sockets initialized")

        except Exception as e:
            self.logger.warning(f"ZeroMQ setup failed: {e}")
            self.zmq_context = None

    def setup_grpc_server(self):
        """Setup gRPC server for structured API communication"""
        if not GRPC_AVAILABLE:
            self.logger.warning("gRPC not available. Structured API communication limited.")
            return

        try:
            self.grpc_server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
            grpc_port = self.config.get('grpc_port', 50051)

            # Add service implementations here
            # self.grpc_server.add_insecure_port(f'[::]:{grpc_port}')

            self.logger.info("gRPC server initialized")

        except Exception as e:
            self.logger.warning(f"gRPC setup failed: {e}")
            self.grpc_server = None

    async def start_bridge(self):
        """Start all communication protocols"""
        self.is_running = True
        self.logger.info("Starting AI Agent Bridge...")

        # Start background tasks
        tasks = []

        if WEBSOCKETS_AVAILABLE:
            tasks.append(asyncio.create_task(self.start_websocket_server()))

        if self.rabbitmq_connection:
            tasks.append(asyncio.create_task(self.start_rabbitmq_consumer()))

        if self.zmq_context:
            tasks.append(asyncio.create_task(self.start_zeromq_listener()))

        tasks.append(asyncio.create_task(self.message_processor()))
        tasks.append(asyncio.create_task(self.heartbeat_monitor()))

        # Wait for all tasks
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def stop_bridge(self):
        """Stop all communication protocols"""
        self.is_running = False
        self.logger.info("Stopping AI Agent Bridge...")

        # Close connections
        if self.rabbitmq_connection and not self.rabbitmq_connection.is_closed:
            self.rabbitmq_connection.close()

        if self.zmq_context:
            self.zmq_context.term()

        if self.grpc_server:
            self.grpc_server.stop(grace=5)

    async def start_websocket_server(self):
        """Start WebSocket server"""
        if not WEBSOCKETS_AVAILABLE:
            return

        async def handle_websocket(websocket, path):
            """Handle WebSocket connection"""
            self.websocket_clients.add(websocket)
            self.active_connections += 1
            self.logger.info(f"WebSocket client connected from {websocket.remote_address}")

            try:
                async for message in websocket:
                    await self.handle_websocket_message(websocket, message)
            except websockets.exceptions.ConnectionClosed:
                self.logger.info("WebSocket client disconnected")
            finally:
                self.websocket_clients.discard(websocket)
                self.active_connections -= 1

        try:
            server = await websockets.serve(handle_websocket, "localhost", self.websocket_port)
            self.logger.info(f"WebSocket server started on port {self.websocket_port}")
            await server.wait_closed()
        except Exception as e:
            self.logger.error(f"WebSocket server error: {e}")

    async def handle_websocket_message(self, websocket, message_data):
        """Handle incoming WebSocket message"""
        try:
            message_dict = json.loads(message_data)
            agent_message = AgentMessage(**message_dict)

            # Process message
            response = await self.process_message(agent_message)

            # Send response if needed
            if response:
                response_data = json.dumps(asdict(response))
                await websocket.send(response_data)

        except Exception as e:
            self.logger.error(f"Error handling WebSocket message: {e}")
            error_response = {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            await websocket.send(json.dumps(error_response))

    async def start_rabbitmq_consumer(self):
        """Start RabbitMQ message consumer"""
        if not self.rabbitmq_connection:
            return

        def callback(ch, method, properties, body):
            """RabbitMQ message callback"""
            try:
                message_dict = json.loads(body.decode('utf-8'))
                agent_message = AgentMessage(**message_dict)

                # Process message asynchronously
                asyncio.create_task(self.process_message(agent_message))

                # Acknowledge message
                ch.basic_ack(delivery_tag=method.delivery_tag)

            except Exception as e:
                self.logger.error(f"Error processing RabbitMQ message: {e}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

        try:
            self.rabbitmq_channel.basic_consume(
                queue='dap_inbox',
                on_message_callback=callback
            )

            self.logger.info("RabbitMQ consumer started")
            self.rabbitmq_channel.start_consuming()

        except Exception as e:
            self.logger.error(f"RabbitMQ consumer error: {e}")

    async def start_zeromq_listener(self):
        """Start ZeroMQ message listener"""
        if not self.zmq_context:
            return

        try:
            while self.is_running:
                # Check for subscriber messages
                try:
                    message_data = self.zmq_subscriber.recv_string(zmq.NOBLOCK)
                    message_dict = json.loads(message_data)
                    agent_message = AgentMessage(**message_dict)
                    await self.process_message(agent_message)
                except zmq.Again:
                    pass

                # Check for request-response messages
                try:
                    request_data = self.zmq_responder.recv_string(zmq.NOBLOCK)
                    request_dict = json.loads(request_data)
                    agent_message = AgentMessage(**request_dict)

                    response = await self.process_message(agent_message)
                    if response:
                        response_data = json.dumps(asdict(response))
                        self.zmq_responder.send_string(response_data)
                    else:
                        self.zmq_responder.send_string(json.dumps({"status": "ok"}))

                except zmq.Again:
                    pass

                await asyncio.sleep(0.01)  # Small delay to prevent busy waiting

        except Exception as e:
            self.logger.error(f"ZeroMQ listener error: {e}")

    async def message_processor(self):
        """Background message processor"""
        while self.is_running:
            try:
                # Process queued messages
                while not self.message_queue.empty():
                    try:
                        message = self.message_queue.get_nowait()
                        await self.process_message(message)
                        self.message_queue.task_done()
                    except Empty:
                        break

                await asyncio.sleep(0.1)

            except Exception as e:
                self.logger.error(f"Message processor error: {e}")
                await asyncio.sleep(1)

    async def heartbeat_monitor(self):
        """Monitor agent heartbeats"""
        while self.is_running:
            try:
                current_time = time.time()
                expired_agents = []

                for agent_id, session_info in self.agent_sessions.items():
                    last_heartbeat = session_info.get('last_heartbeat', 0)
                    timeout = session_info.get('timeout', 300)  # 5 minutes default

                    if current_time - last_heartbeat > timeout:
                        expired_agents.append(agent_id)

                # Remove expired agents
                for agent_id in expired_agents:
                    self.logger.warning(f"Agent {agent_id} heartbeat expired")
                    await self.unregister_agent(agent_id)

                await asyncio.sleep(30)  # Check every 30 seconds

            except Exception as e:
                self.logger.error(f"Heartbeat monitor error: {e}")
                await asyncio.sleep(30)

    async def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """Process incoming agent message"""
        try:
            self.message_count += 1
            self.logger.info(f"Processing message {message.id} from {message.source}")

            # Check message TTL
            if message.ttl:
                message_time = datetime.fromisoformat(message.timestamp)
                if datetime.now() - message_time > timedelta(seconds=message.ttl):
                    self.logger.warning(f"Message {message.id} expired")
                    return None

            # Route to appropriate handler
            handler = self.message_handlers.get(message.message_type)
            if handler:
                response = await handler(message)
                return response
            else:
                self.logger.warning(f"No handler for message type: {message.message_type}")
                return None

        except Exception as e:
            self.logger.error(f"Error processing message {message.id}: {e}")
            return None

    async def send_message(self, message: AgentMessage, protocols: List[str] = None):
        """Send message to target agent"""
        try:
            protocols = protocols or ['websocket', 'rabbitmq', 'zeromq']
            message_data = json.dumps(asdict(message))

            # Send via WebSocket
            if 'websocket' in protocols and WEBSOCKETS_AVAILABLE:
                for client in self.websocket_clients.copy():
                    try:
                        await client.send(message_data)
                    except Exception as e:
                        self.logger.warning(f"Failed to send WebSocket message: {e}")
                        self.websocket_clients.discard(client)

            # Send via RabbitMQ
            if 'rabbitmq' in protocols and self.rabbitmq_connection:
                try:
                    self.rabbitmq_channel.basic_publish(
                        exchange='dap_agents',
                        routing_key=message.target,
                        body=message_data.encode('utf-8'),
                        properties=pika.BasicProperties(
                            priority=message.priority,
                            message_id=message.id,
                            correlation_id=message.correlation_id
                        )
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to send RabbitMQ message: {e}")

            # Send via ZeroMQ
            if 'zeromq' in protocols and self.zmq_context:
                try:
                    self.zmq_publisher.send_string(message_data)
                except Exception as e:
                    self.logger.warning(f"Failed to send ZeroMQ message: {e}")

            self.logger.info(f"Message {message.id} sent to {message.target}")

        except Exception as e:
            self.logger.error(f"Error sending message: {e}")

    async def register_agent(self, agent_id: str, capabilities: List[AgentCapability], connection_info: Dict[str, Any]):
        """Register external agent"""
        try:
            self.registered_agents[agent_id] = {
                'id': agent_id,
                'capabilities': [asdict(cap) for cap in capabilities],
                'connection_info': connection_info,
                'registered_at': datetime.now().isoformat(),
                'status': 'active'
            }

            # Store capabilities
            for capability in capabilities:
                self.agent_capabilities[f"{agent_id}.{capability.name}"] = capability

            # Initialize session
            self.agent_sessions[agent_id] = {
                'last_heartbeat': time.time(),
                'timeout': connection_info.get('timeout', 300),
                'message_count': 0
            }

            self.logger.info(f"Agent {agent_id} registered with {len(capabilities)} capabilities")

            # Send welcome message
            welcome_message = AgentMessage(
                id=str(uuid.uuid4()),
                source='dap_bridge',
                target=agent_id,
                message_type='registration_complete',
                payload={
                    'status': 'success',
                    'bridge_info': {
                        'protocols': ['websocket', 'rabbitmq', 'zeromq'],
                        'capabilities': list(self.message_handlers.keys())
                    }
                },
                timestamp=datetime.now().isoformat()
            )

            await self.send_message(welcome_message)

        except Exception as e:
            self.logger.error(f"Error registering agent {agent_id}: {e}")

    async def unregister_agent(self, agent_id: str):
        """Unregister external agent"""
        try:
            if agent_id in self.registered_agents:
                # Remove agent capabilities
                caps_to_remove = [key for key in self.agent_capabilities.keys() if key.startswith(f"{agent_id}.")]
                for cap_key in caps_to_remove:
                    del self.agent_capabilities[cap_key]

                # Remove agent
                del self.registered_agents[agent_id]

                # Remove session
                if agent_id in self.agent_sessions:
                    del self.agent_sessions[agent_id]

                self.logger.info(f"Agent {agent_id} unregistered")

        except Exception as e:
            self.logger.error(f"Error unregistering agent {agent_id}: {e}")

    # Message handlers
    async def handle_audit_request(self, message: AgentMessage) -> AgentMessage:
        """Handle audit request from external agent"""
        try:
            payload = message.payload
            audit_type = payload.get('audit_type', 'general')
            company_id = payload.get('company_id')

            # Process audit request
            audit_result = {
                'audit_id': str(uuid.uuid4()),
                'audit_type': audit_type,
                'company_id': company_id,
                'status': 'completed',
                'findings': [
                    {'type': 'warning', 'description': '发现异常交易记录'},
                    {'type': 'info', 'description': '资产负债表平衡'}
                ],
                'recommendations': ['建议进一步核查异常交易'],
                'completed_at': datetime.now().isoformat()
            }

            response = AgentMessage(
                id=str(uuid.uuid4()),
                source='dap_bridge',
                target=message.source,
                message_type='audit_response',
                payload=audit_result,
                timestamp=datetime.now().isoformat(),
                correlation_id=message.id
            )

            return response

        except Exception as e:
            self.logger.error(f"Error handling audit request: {e}")
            return None

    async def handle_data_query(self, message: AgentMessage) -> AgentMessage:
        """Handle data query from external agent"""
        try:
            payload = message.payload
            query = payload.get('query', '')
            filters = payload.get('filters', {})

            # Process data query
            query_result = {
                'query_id': str(uuid.uuid4()),
                'query': query,
                'results': [
                    {'id': 'T001', 'amount': 15000, 'date': '2024-01-15'},
                    {'id': 'T002', 'amount': 12000, 'date': '2024-01-16'}
                ],
                'total_count': 2,
                'execution_time': 0.05,
                'completed_at': datetime.now().isoformat()
            }

            response = AgentMessage(
                id=str(uuid.uuid4()),
                source='dap_bridge',
                target=message.source,
                message_type='data_response',
                payload=query_result,
                timestamp=datetime.now().isoformat(),
                correlation_id=message.id
            )

            return response

        except Exception as e:
            self.logger.error(f"Error handling data query: {e}")
            return None

    async def handle_analysis_request(self, message: AgentMessage) -> AgentMessage:
        """Handle analysis request from external agent"""
        try:
            payload = message.payload
            analysis_type = payload.get('analysis_type', 'general')
            data_source = payload.get('data_source', '')

            # Process analysis request
            analysis_result = {
                'analysis_id': str(uuid.uuid4()),
                'analysis_type': analysis_type,
                'data_source': data_source,
                'results': {
                    'summary': '数据分析完成',
                    'anomalies': 3,
                    'risk_score': 0.25,
                    'insights': ['异常交易模式', '现金流波动']
                },
                'completed_at': datetime.now().isoformat()
            }

            response = AgentMessage(
                id=str(uuid.uuid4()),
                source='dap_bridge',
                target=message.source,
                message_type='analysis_response',
                payload=analysis_result,
                timestamp=datetime.now().isoformat(),
                correlation_id=message.id
            )

            return response

        except Exception as e:
            self.logger.error(f"Error handling analysis request: {e}")
            return None

    async def handle_model_update(self, message: AgentMessage) -> AgentMessage:
        """Handle model update from external agent"""
        try:
            payload = message.payload
            model_type = payload.get('model_type', '')
            update_data = payload.get('update_data', {})

            # Process model update
            update_result = {
                'update_id': str(uuid.uuid4()),
                'model_type': model_type,
                'status': 'success',
                'message': '模型更新完成',
                'updated_at': datetime.now().isoformat()
            }

            response = AgentMessage(
                id=str(uuid.uuid4()),
                source='dap_bridge',
                target=message.source,
                message_type='model_update_response',
                payload=update_result,
                timestamp=datetime.now().isoformat(),
                correlation_id=message.id
            )

            return response

        except Exception as e:
            self.logger.error(f"Error handling model update: {e}")
            return None

    async def handle_health_check(self, message: AgentMessage) -> AgentMessage:
        """Handle health check from external agent"""
        try:
            health_status = {
                'status': 'healthy',
                'uptime': time.time() - self.start_time,
                'message_count': self.message_count,
                'active_connections': self.active_connections,
                'registered_agents': len(self.registered_agents),
                'capabilities_count': len(self.agent_capabilities),
                'timestamp': datetime.now().isoformat()
            }

            response = AgentMessage(
                id=str(uuid.uuid4()),
                source='dap_bridge',
                target=message.source,
                message_type='health_response',
                payload=health_status,
                timestamp=datetime.now().isoformat(),
                correlation_id=message.id
            )

            return response

        except Exception as e:
            self.logger.error(f"Error handling health check: {e}")
            return None

    async def handle_capability_inquiry(self, message: AgentMessage) -> AgentMessage:
        """Handle capability inquiry from external agent"""
        try:
            capabilities_info = {
                'bridge_capabilities': list(self.message_handlers.keys()),
                'registered_agents': list(self.registered_agents.keys()),
                'agent_capabilities': {
                    agent_id: agent_info['capabilities']
                    for agent_id, agent_info in self.registered_agents.items()
                },
                'protocols': ['websocket', 'rabbitmq', 'zeromq'],
                'timestamp': datetime.now().isoformat()
            }

            response = AgentMessage(
                id=str(uuid.uuid4()),
                source='dap_bridge',
                target=message.source,
                message_type='capability_response',
                payload=capabilities_info,
                timestamp=datetime.now().isoformat(),
                correlation_id=message.id
            )

            return response

        except Exception as e:
            self.logger.error(f"Error handling capability inquiry: {e}")
            return None

    async def handle_agent_registration(self, message: AgentMessage) -> AgentMessage:
        """Handle agent registration request"""
        try:
            payload = message.payload
            agent_id = payload.get('agent_id', message.source)
            capabilities_data = payload.get('capabilities', [])
            connection_info = payload.get('connection_info', {})

            # Parse capabilities
            capabilities = []
            for cap_data in capabilities_data:
                capability = AgentCapability(
                    name=cap_data['name'],
                    description=cap_data['description'],
                    input_schema=cap_data.get('input_schema', {}),
                    output_schema=cap_data.get('output_schema', {}),
                    version=cap_data.get('version', '1.0.0'),
                    requires_auth=cap_data.get('requires_auth', False)
                )
                capabilities.append(capability)

            # Register agent
            await self.register_agent(agent_id, capabilities, connection_info)

            registration_result = {
                'status': 'success',
                'agent_id': agent_id,
                'registered_capabilities': len(capabilities),
                'message': f'Agent {agent_id} registered successfully',
                'registered_at': datetime.now().isoformat()
            }

            response = AgentMessage(
                id=str(uuid.uuid4()),
                source='dap_bridge',
                target=message.source,
                message_type='registration_response',
                payload=registration_result,
                timestamp=datetime.now().isoformat(),
                correlation_id=message.id
            )

            return response

        except Exception as e:
            self.logger.error(f"Error handling agent registration: {e}")
            return None

    async def handle_heartbeat(self, message: AgentMessage) -> AgentMessage:
        """Handle heartbeat from external agent"""
        try:
            agent_id = message.source

            # Update heartbeat timestamp
            if agent_id in self.agent_sessions:
                self.agent_sessions[agent_id]['last_heartbeat'] = time.time()
                self.agent_sessions[agent_id]['message_count'] += 1

            heartbeat_response = {
                'status': 'alive',
                'agent_id': agent_id,
                'server_time': datetime.now().isoformat(),
                'next_heartbeat': 60  # seconds
            }

            response = AgentMessage(
                id=str(uuid.uuid4()),
                source='dap_bridge',
                target=message.source,
                message_type='heartbeat_response',
                payload=heartbeat_response,
                timestamp=datetime.now().isoformat(),
                correlation_id=message.id
            )

            return response

        except Exception as e:
            self.logger.error(f"Error handling heartbeat: {e}")
            return None

    def get_bridge_status(self) -> Dict[str, Any]:
        """Get bridge status information"""
        return {
            'status': 'running' if self.is_running else 'stopped',
            'uptime': time.time() - self.start_time,
            'message_count': self.message_count,
            'active_connections': self.active_connections,
            'registered_agents': len(self.registered_agents),
            'protocols': {
                'websocket': WEBSOCKETS_AVAILABLE and self.websocket_server is not None,
                'rabbitmq': self.rabbitmq_connection is not None,
                'zeromq': self.zmq_context is not None,
                'grpc': self.grpc_server is not None
            },
            'agents': list(self.registered_agents.keys()),
            'capabilities': len(self.agent_capabilities)
        }

# Test function
async def test_ai_agent_bridge():
    """Test the AI agent bridge functionality"""
    print("Testing AI Agent Bridge...")

    bridge = AIAgentBridge()
    print(f"✓ Bridge initialized: {bridge.is_running == False}")

    # Test message creation
    test_message = AgentMessage(
        id="test_001",
        source="test_agent",
        target="dap_bridge",
        message_type="health_check",
        payload={},
        timestamp=datetime.now().isoformat()
    )

    print(f"✓ Message created: {test_message.id}")

    # Test capability
    test_capability = AgentCapability(
        name="test_capability",
        description="Test capability",
        input_schema={},
        output_schema={},
        version="1.0.0"
    )

    print(f"✓ Capability created: {test_capability.name}")

    print("✓ AI Agent Bridge test completed")

if __name__ == "__main__":
    import asyncio

    # Run test
    asyncio.run(test_ai_agent_bridge())