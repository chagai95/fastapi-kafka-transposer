import logging
from typing import Dict, List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database.models import WorkflowConfiguration, WorkflowStep, RouteConfiguration

logger = logging.getLogger(__name__)

class WorkflowDatabaseService:
    def __init__(self):
        self._workflow_cache = {}
        self._route_cache = {}
        
    async def get_workflow_config(self, session: AsyncSession, workflow_name: str) -> Optional[Dict]:
        """Get workflow configuration from database"""
        # Check cache first
        if workflow_name in self._workflow_cache:
            return self._workflow_cache[workflow_name]
            
        # Query database
        stmt = select(WorkflowConfiguration).options(
            selectinload(WorkflowConfiguration.steps)
        ).where(
            WorkflowConfiguration.name == workflow_name,
            WorkflowConfiguration.is_active == True
        )
        
        result = await session.execute(stmt)
        workflow = result.scalar_one_or_none()
        
        if not workflow:
            logger.error(f"No active workflow found with name: {workflow_name}")
            return None
            
        # Convert to the format expected by workflow_service
        workflow_config = {
            "steps": []
        }
        
        # Sort steps by step_order
        sorted_steps = sorted(workflow.steps, key=lambda s: s.step_order)
        
        for step in sorted_steps:
            workflow_config["steps"].append({
                "topic": step.topic,
                "response_topic": step.response_topic
            })
        
        # Cache the result
        self._workflow_cache[workflow_name] = workflow_config
        logger.info(f"Loaded workflow '{workflow_name}' with {len(workflow_config['steps'])} steps")
        
        return workflow_config
    
    async def get_route_config(self, session: AsyncSession, route_path: str) -> Optional[RouteConfiguration]:
        """Get route configuration from database"""
        # Check cache first
        cache_key = route_path
        if cache_key in self._route_cache:
            return self._route_cache[cache_key]
            
        # Query database
        stmt = select(RouteConfiguration).where(
            RouteConfiguration.route_path == route_path,
            RouteConfiguration.is_active == True
        )
        
        result = await session.execute(stmt)
        route_config = result.scalar_one_or_none()
        
        if route_config:
            # Cache the result
            self._route_cache[cache_key] = route_config
            logger.debug(f"Loaded route config for: {route_path}")
        else:
            logger.warning(f"No active route configuration found for: {route_path}")
            
        return route_config
    
    async def validate_route_parameters(self, session: AsyncSession, route_path: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate parameters against route configuration"""
        route_config = await self.get_route_config(session, route_path)
        
        if not route_config:
            return {
                "valid": False, 
                "error": f"No configuration found for route: {route_path}"
            }
        
        # Get parameter schemas
        required_params = route_config.required_parameters or {}
        optional_params = route_config.optional_parameters or {}
        
        # Check required parameters
        missing_params = []
        for param_name, param_config in required_params.items():
            if param_name not in parameters:
                missing_params.append(param_name)
            else:
                # Basic type validation
                expected_type = param_config.get("type")
                if expected_type and not self._validate_type(parameters[param_name], expected_type):
                    return {
                        "valid": False,
                        "error": f"Parameter '{param_name}' should be of type {expected_type}"
                    }
        
        if missing_params:
            return {
                "valid": False,
                "error": f"Missing required parameters: {', '.join(missing_params)}"
            }
        
        # Validate optional parameters if present
        for param_name, param_value in parameters.items():
            if param_name in optional_params:
                expected_type = optional_params[param_name].get("type")
                if expected_type and not self._validate_type(param_value, expected_type):
                    return {
                        "valid": False,
                        "error": f"Optional parameter '{param_name}' should be of type {expected_type}"
                    }
        
        return {
            "valid": True,
            "workflow_name": route_config.workflow_name
        }
    
    def _validate_type(self, value: Any, expected_type: str) -> bool:
        """Basic type validation"""
        type_map = {
            "string": str,
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict
        }
        
        if expected_type in type_map:
            return isinstance(value, type_map[expected_type])
        
        return True  # Unknown type, assume valid
    
    async def get_all_response_topics(self, session: AsyncSession) -> List[str]:
        """Get all response topics from active workflows"""
        stmt = select(WorkflowStep.response_topic).join(
            WorkflowConfiguration
        ).where(
            WorkflowConfiguration.is_active == True
        ).distinct()
        
        result = await session.execute(stmt)
        topics = [row[0] for row in result.fetchall()]
        
        logger.info(f"Found {len(topics)} unique response topics from active workflows")
        return topics
    
    def clear_cache(self):
        """Clear the internal cache - useful when workflows are updated"""
        self._workflow_cache.clear()
        self._route_cache.clear()
        logger.info("Workflow and route cache cleared")

# Create global instance
workflow_db_service = WorkflowDatabaseService()