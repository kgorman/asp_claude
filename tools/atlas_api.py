#!/usr/bin/env python3
"""
Shared Atlas Stream Processing API library
Common functionality for connection and processor management
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import requests
from requests.auth import HTTPDigestAuth


def colorize_json(obj):
    """Add color codes to JSON output for terminal display"""
    import json
    
    def colorize_value(value, indent=0):
        spaces = "  " * indent
        if isinstance(value, dict):
            if not value:
                return "{}"
            items = []
            for k, v in value.items():
                colored_key = f'\033[94m"{k}"\033[0m'  # Blue for keys
                colored_value = colorize_value(v, indent + 1)
                items.append(f"{spaces}  {colored_key}: {colored_value}")
            return "{\n" + ",\n".join(items) + f"\n{spaces}}}"
        elif isinstance(value, list):
            if not value:
                return "[]"
            items = []
            for item in value:
                colored_item = colorize_value(item, indent + 1)
                items.append(f"{spaces}  {colored_item}")
            return "[\n" + ",\n".join(items) + f"\n{spaces}]"
        elif isinstance(value, str):
            return f'\033[92m"{value}"\033[0m'  # Green for strings
        elif isinstance(value, (int, float)):
            return f'\033[93m{value}\033[0m'  # Yellow for numbers
        elif isinstance(value, bool):
            return f'\033[95m{str(value).lower()}\033[0m'  # Magenta for booleans
        elif value is None:
            return f'\033[90mnull\033[0m'  # Gray for null
        else:
            return str(value)
    
    return colorize_value(obj)


class AtlasStreamProcessingAPI:
    """Atlas Stream Processing API client with common operations"""
    
    def __init__(self, config_file: str = "../config.txt"):
        self.config = self._load_config(config_file)
        self.auth = HTTPDigestAuth(
            self.config["PUBLIC_KEY"], 
            self.config["PRIVATE_KEY"]
        )
        self.project_url = f"https://cloud.mongodb.com/api/atlas/v2/groups/{self.config['PROJECT_ID']}"
        
        # Stream Processing Workspace configuration
        if self.config.get('SP_WORKSPACE_NAME'):
            # Primary workspace-based API
            self.base_url = f"{self.project_url}/streams/{self.config['SP_WORKSPACE_NAME']}"
            self.api_model = "workspace"
        elif self.config.get('SP_INSTANCE_NAME'):
            # Backward compatibility - treat instances as workspaces
            self.base_url = f"{self.project_url}/streams/{self.config['SP_INSTANCE_NAME']}"
            self.api_model = "workspace"
        else:
            self.base_url = None
            self.api_model = None
            
        self.headers = {"Accept": "application/vnd.atlas.2024-05-30+json"}
        # Use newer API version for tier support
        self.headers_v2025 = {"Accept": "application/vnd.atlas.2025-03-12+json"}
    
    def _load_config(self, config_file: str) -> Dict[str, str]:
        """Load configuration from api.txt file"""
        config = {}
        config_path = Path(config_file)
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file {config_file} not found")
        
        with open(config_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    config[key.strip()] = value.strip()
        
        required_keys = ["PUBLIC_KEY", "PRIVATE_KEY", "PROJECT_ID"]
        # SP_INSTANCE_NAME is now optional - required only for processor/connection operations
        missing_keys = [key for key in required_keys if key not in config]
        if missing_keys:
            raise ValueError(f"Missing required configuration keys: {missing_keys}")
        
        return config
    
    def analyze_processor_complexity(self, processor_name: str) -> str:
        """Analyze processor complexity and recommend optimal tier"""
        analysis = self.analyze_processor_complexity_detailed(processor_name)
        return analysis["recommended_tier"]
    
    def analyze_processor_complexity_detailed(self, processor_name: str) -> dict:
        """Analyze processor complexity and return detailed analysis"""
        try:
            # Get processor definition
            processors_dir = Path("../processors")
            processor_file = processors_dir / f"{processor_name}.json"
            
            if not processor_file.exists():
                return {
                    "recommended_tier": "SP10",
                    "analysis": {"error": "Processor file not found"},
                    "reasoning": "Default fallback for missing processor"
                }
            
            with open(processor_file, 'r') as f:
                processor_data = json.load(f)
            
            pipeline = processor_data.get("pipeline", [])
            complexity_score = 0
            connections_count = 0
            total_parallelism = 0
            complexity_factors = []
            parallelism_details = []
            
            # Analyze pipeline complexity
            for i, stage in enumerate(pipeline):
                stage_name = f"Stage {i+1}"
                
                # Complex operations
                if "$function" in str(stage):
                    complexity_score += 40
                    complexity_factors.append(f"{stage_name}: JavaScript function (+40 complexity)")
                if "$window" in str(stage):
                    complexity_score += 30
                    complexity_factors.append(f"{stage_name}: Window processing (+30 complexity)")
                if "$facet" in str(stage):
                    complexity_score += 25
                    complexity_factors.append(f"{stage_name}: Facet operation (+25 complexity)")
                if "$lookup" in str(stage):
                    complexity_score += 20
                    complexity_factors.append(f"{stage_name}: Lookup/join operation (+20 complexity)")
                if "$group" in str(stage):
                    complexity_score += 15
                    complexity_factors.append(f"{stage_name}: Grouping operation (+15 complexity)")
                if "$sort" in str(stage):
                    complexity_score += 10
                    complexity_factors.append(f"{stage_name}: Sort operation (+10 complexity)")
                
                # Count connections (sources and sinks)
                if "$source" in stage:
                    connections_count += 1
                if "$merge" in stage:
                    connections_count += 1
                
                # Extract parallelism settings - only count parallelism > 1
                if isinstance(stage, dict):
                    for key, value in stage.items():
                        if key == "parallelism" and isinstance(value, (int, float)):
                            parallelism_val = int(value)
                            if parallelism_val > 1:
                                contribution = parallelism_val - 1
                                total_parallelism += contribution
                                parallelism_details.append(f"{stage_name} ({list(stage.keys())[0]}): parallelism={parallelism_val} (contributes {contribution})")
                                complexity_score += parallelism_val * 5
                        elif isinstance(value, dict) and "parallelism" in value:
                            parallel_val = value.get("parallelism", 1)
                            if isinstance(parallel_val, (int, float)):
                                parallelism_val = int(parallel_val)
                                if parallelism_val > 1:
                                    contribution = parallelism_val - 1
                                    total_parallelism += contribution
                                    parallelism_details.append(f"{stage_name} ({key}): parallelism={parallelism_val} (contributes {contribution})")
                                    complexity_score += parallelism_val * 5
                
                # Check for Kafka partitions
                if "kafka" in str(stage).lower():
                    complexity_score += 15
                    complexity_factors.append(f"{stage_name}: Kafka integration (+15 complexity)")
            
            # Pipeline length factor
            pipeline_length = len(pipeline)
            if pipeline_length > 8:
                complexity_score += 20
                complexity_factors.append(f"Pipeline length: {pipeline_length} stages (+20 complexity)")
            elif pipeline_length > 5:
                complexity_score += 10
                complexity_factors.append(f"Pipeline length: {pipeline_length} stages (+10 complexity)")
            elif pipeline_length > 3:
                complexity_score += 5
                complexity_factors.append(f"Pipeline length: {pipeline_length} stages (+5 complexity)")
            
            # Connection count factor
            if connections_count > 4:
                complexity_score += 15
                complexity_factors.append(f"Connection count: {connections_count} (+15 complexity)")
            elif connections_count > 2:
                complexity_score += 10
                complexity_factors.append(f"Connection count: {connections_count} (+10 complexity)")
            
            # Apply parallelism-based tier minimums
            if total_parallelism > 48:
                min_tier_from_parallelism = "SP50"
            elif total_parallelism > 8:
                min_tier_from_parallelism = "SP30"
            elif total_parallelism > 1:
                min_tier_from_parallelism = "SP10"
            elif total_parallelism == 1:
                min_tier_from_parallelism = "SP5"
            else:
                min_tier_from_parallelism = "SP2"
            
            # Determine tier based on complexity score
            if complexity_score >= 80:
                recommended_tier = "SP50"
                complexity_reason = "Very complex pipeline (80+ complexity points)"
            elif complexity_score >= 50:
                recommended_tier = "SP30"
                complexity_reason = "Complex pipeline (50+ complexity points)"
            elif complexity_score >= 25:
                recommended_tier = "SP10"
                complexity_reason = "Moderate complexity (25+ complexity points)"
            elif complexity_score >= 10:
                recommended_tier = "SP5"
                complexity_reason = "Simple pipeline (10+ complexity points)"
            else:
                recommended_tier = "SP2"
                complexity_reason = "Very simple pipeline (<10 complexity points)"
            
            # Use the higher of complexity-based recommendation or parallelism minimum
            tier_hierarchy = ["SP2", "SP5", "SP10", "SP30", "SP50"]
            complexity_index = tier_hierarchy.index(recommended_tier)
            parallelism_index = tier_hierarchy.index(min_tier_from_parallelism)
            
            final_tier = tier_hierarchy[max(complexity_index, parallelism_index)]
            
            # Build reasoning
            if complexity_index >= parallelism_index:
                primary_reason = f"Complexity-driven: {complexity_reason}"
                secondary_reason = f"Parallelism requirement: {min_tier_from_parallelism} (total parallelism: {total_parallelism})"
            else:
                primary_reason = f"Parallelism-driven: {min_tier_from_parallelism} required for {total_parallelism} total parallelism"
                secondary_reason = f"Complexity score: {complexity_score} (suggests {recommended_tier})"
            
            return {
                "recommended_tier": final_tier,
                "analysis": {
                    "total_parallelism": total_parallelism,
                    "complexity_score": complexity_score,
                    "pipeline_stages": pipeline_length,
                    "connections_count": connections_count,
                    "complexity_tier": recommended_tier,
                    "parallelism_tier": min_tier_from_parallelism,
                    "parallelism_details": parallelism_details,
                    "complexity_factors": complexity_factors
                },
                "reasoning": {
                    "primary": primary_reason,
                    "secondary": secondary_reason,
                    "final_decision": f"Selected {final_tier} as the higher requirement"
                }
            }
                
        except Exception as e:
            return {
                "recommended_tier": "SP10",
                "analysis": {"error": str(e)},
                "reasoning": "Error occurred during analysis, using default tier"
            }
    
    def _parse_tier_validation_error(self, error_text: str) -> str:
        """Parse API validation errors to extract minimum tier requirement"""
        try:
            # Look for pattern: "Minimum tier for this workload: SP10 or larger"
            import re
            match = re.search(r'Minimum tier for this workload: (SP\d+)', error_text)
            if match:
                return match.group(1)
            
            # Look for parallelism limit patterns
            parallelism_match = re.search(r'Requested: (\d+)', error_text)
            if parallelism_match:
                requested_parallelism = int(parallelism_match.group(1))
                if requested_parallelism > 8:
                    return "SP50"
                elif requested_parallelism > 4:
                    return "SP30"
                elif requested_parallelism > 2:
                    return "SP10"
                else:
                    return "SP5"
        except:
            pass
        return None
    
    def _substitute_variables(self, text: str) -> str:
        """Substitute ${VAR} placeholders with config values"""
        def replace_var(match):
            var_name = match.group(1)
            return self.config.get(var_name, match.group(0))
        
        return re.sub(r'\$\{([^}]+)\}', replace_var, text)
    
    # Stream Processing Instance Operations
    def list_instances(self) -> List[Dict]:
        """Get list of all Stream Processing instances in the project"""
        try:
            response = requests.get(
                f"{self.project_url}/streams",
                auth=self.auth,
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            return {
                "operation": "list_instances",
                "status": "failed",
                "message": str(e),
                "http_code": getattr(e.response, 'status_code', None)
            }
    
    def create_instance(self, instance_name: str, cloud_provider: str = "AWS", region: str = "US_EAST_1") -> Dict:
        """Create a new Stream Processing instance"""
        try:
            payload = {
                "name": instance_name,
                "dataProcessRegion": {
                    "cloudProvider": cloud_provider,
                    "region": region
                }
            }
            response = requests.post(
                f"{self.project_url}/streams",
                auth=self.auth,
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            
            return {
                "name": instance_name,
                "operation": "create_instance",
                "status": "created",
                "message": "Stream Processing instance created successfully",
                "cloud_provider": cloud_provider,
                "region": region
            }
            
        except requests.RequestException as e:
            status_code = getattr(e.response, 'status_code', None)
            if status_code == 409:
                return {
                    "name": instance_name,
                    "operation": "create_instance",
                    "status": "already_exists", 
                    "message": "Stream Processing instance already exists"
                }
            return {
                "name": instance_name,
                "operation": "create_instance",
                "status": "failed",
                "message": str(e),
                "http_code": status_code
            }
    
    def delete_instance(self, instance_name: str) -> Dict:
        """Delete a Stream Processing instance"""
        try:
            response = requests.delete(
                f"{self.project_url}/streams/{instance_name}",
                auth=self.auth,
                headers=self.headers
            )
            response.raise_for_status()
            
            return {
                "name": instance_name,
                "operation": "delete_instance",
                "status": "deleted",
                "message": "Stream Processing instance deleted successfully"
            }
            
        except requests.RequestException as e:
            return {
                "name": instance_name,
                "operation": "delete_instance",
                "status": "failed",
                "message": str(e),
                "http_code": getattr(e.response, 'status_code', None)
            }
    
    def get_instance_details(self, instance_name: str) -> Dict:
        """Get details of a specific Stream Processing instance"""
        try:
            response = requests.get(
                f"{self.project_url}/streams/{instance_name}",
                auth=self.auth,
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            return {
                "name": instance_name,
                "operation": "get_instance_details",
                "status": "failed",
                "message": str(e),
                "http_code": getattr(e.response, 'status_code', None)
            }
    
    def _check_workspace_required(self):
        """Check if workspace name is configured and base_url is available"""
        if not self.base_url:
            raise ValueError("Stream Processing workspace not configured. Please set SP_WORKSPACE_NAME or SP_INSTANCE_NAME in config.txt.")
    
    def _get_detailed_error(self, e):
        """Get detailed error message from API response"""
        error_detail = str(e)
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_body = e.response.json()
                error_detail = f"{str(e)} - {error_body.get('detail', error_body)}"
            except:
                error_detail = f"{str(e)} - {e.response.text}"
        return error_detail
    
    # Processor Operations
    def list_processors(self, verbose: bool = False) -> List[Dict]:
        """Get list of all processors with tier information"""
        self._check_workspace_required()
        response = requests.get(
            f"{self.base_url}/processors",
            auth=self.auth,
            headers=self.headers
        )
        response.raise_for_status()
        processors = response.json().get("results", [])
        
        # Enhance each processor with tier information if available
        enhanced_processors = []
        for processor in processors:
            # Try to get detailed processor info including tier
            try:
                # Build URL with verbose parameter if needed
                detail_url = f"{self.base_url}/processor/{processor['name']}"
                params = {}
                if verbose:
                    # Try different parameter formats that Atlas API might expect
                    params = {
                        'includeCount': 'true',  # Common Atlas API pattern
                        'verbose': 'true',       # Direct verbose flag
                        'options.verbose': 'true'  # Nested options pattern
                    }
                
                detail_response = requests.get(
                    detail_url,
                    auth=self.auth,
                    headers=self.headers,
                    params=params if params else None
                )
                
                if detail_response.status_code == 200:
                    detail_data = detail_response.json()
                    processor["tier"] = detail_data.get("tier", "unknown")
                    processor["scaleFactor"] = detail_data.get("scaleFactor", "unknown")
                    # Add all available stats data when verbose
                    if verbose:
                        processor["full_response"] = detail_data  # Capture full response for verbose output
                    # Add verbose stats if available
                    if "stats" in detail_data:
                        processor["stats"] = detail_data["stats"]
                else:
                    processor["tier"] = "unknown"
                    processor["scaleFactor"] = "unknown"
            except:
                processor["tier"] = "unknown" 
                processor["scaleFactor"] = "unknown"
                
            enhanced_processors.append(processor)
        
        return enhanced_processors
    
    def get_processor_status(self) -> Dict:
        """Get status of all processors"""
        timestamp = datetime.now(timezone.utc).isoformat()
        result = {
            "timestamp": timestamp,
            "operation": "status",
            "summary": {"total": 0, "success": 0, "failed": 0},
            "processors": []
        }
        
        try:
            processors = self.list_processors()
            result["summary"]["total"] = len(processors)
            
            for processor in processors:
                proc_info = {
                    "name": processor["name"],
                    "operation": "status",
                    "status": processor.get("state", "UNKNOWN"),
                    "message": "Status retrieved successfully"
                }
                result["processors"].append(proc_info)
                result["summary"]["success"] += 1
                
        except requests.RequestException as e:
            result["summary"]["failed"] = 1
            result["processors"].append({
                "name": "API_ERROR",
                "operation": "status",
                "status": "ERROR",
                "message": str(e)
            })
        
        return result
    
    def get_processor_stats(self, verbose: bool = False) -> Dict:
        """Get detailed stats of all processors"""
        timestamp = datetime.now(timezone.utc).isoformat()
        result = {
            "timestamp": timestamp,
            "operation": "stats",
            "summary": {"total": 0, "success": 0, "failed": 0},
            "processors": []
        }
        
        try:
            processors = self.list_processors(verbose=verbose)
            result["summary"]["total"] = len(processors)
            
            for processor in processors:
                stats = processor.get("stats", {})
                proc_info = {
                    "name": processor["name"],
                    "operation": "stats",
                    "status": processor.get("state", "UNKNOWN"),
                    "message": "Stats retrieved successfully",
                }
                
                if verbose and "full_response" in processor:
                    # Use the complete stats from the API response
                    api_stats = processor["full_response"].get("stats", {})
                    proc_info["stats"] = api_stats
                    # Also include pipeline info if verbose
                    if "pipeline" in processor["full_response"]:
                        proc_info["pipeline"] = processor["full_response"]["pipeline"]
                else:
                    # Use the limited stats subset for regular output
                    proc_info["stats"] = {
                        "processor": processor["name"],
                        "state": processor.get("state", "UNKNOWN"),
                        "inputMessageCount": stats.get("inputMessageCount", 0),
                        "outputMessageCount": stats.get("outputMessageCount", 0),
                        "dlqMessageCount": stats.get("dlqMessageCount", 0),
                        "memoryUsageBytes": stats.get("memoryUsageBytes", 0),
                        "lastMessageIn": stats.get("lastMessageIn"),
                        "scaleFactor": stats.get("scaleFactor", 1)
                    }
                result["processors"].append(proc_info)
                result["summary"]["success"] += 1
                
        except requests.RequestException as e:
            result["summary"]["failed"] = 1
            result["processors"].append({
                "name": "API_ERROR",
                "operation": "stats",
                "status": "ERROR",
                "message": str(e)
            })
        
        return result
    
    def get_single_processor_status(self, processor_name: str) -> Dict:
        """Get status of a specific processor"""
        timestamp = datetime.now(timezone.utc).isoformat()
        result = {
            "timestamp": timestamp,
            "operation": "status",
            "summary": {"total": 1, "success": 0, "failed": 0},
            "processors": []
        }
        
        try:
            processors = self.list_processors()
            target_processor = None
            
            for processor in processors:
                if processor["name"] == processor_name:
                    target_processor = processor
                    break
            
            if target_processor:
                proc_info = {
                    "name": processor_name,
                    "operation": "status",
                    "status": target_processor.get("state", "UNKNOWN"),
                    "message": "Status retrieved successfully"
                }
                result["processors"].append(proc_info)
                result["summary"]["success"] = 1
            else:
                result["processors"].append({
                    "name": processor_name,
                    "operation": "status",
                    "status": "NOT_FOUND",
                    "message": f"Processor '{processor_name}' not found"
                })
                result["summary"]["failed"] = 1
                
        except requests.RequestException as e:
            result["summary"]["failed"] = 1
            result["processors"].append({
                "name": processor_name,
                "operation": "status",
                "status": "ERROR",
                "message": str(e)
            })
        
        return result
    
    def get_single_processor_stats(self, processor_name: str, verbose: bool = False) -> Dict:
        """Get detailed stats of a specific processor"""
        timestamp = datetime.now(timezone.utc).isoformat()
        result = {
            "timestamp": timestamp,
            "operation": "stats",
            "summary": {"total": 1, "success": 0, "failed": 0},
            "processors": []
        }
        
        try:
            processors = self.list_processors(verbose=verbose)
            target_processor = None
            
            for processor in processors:
                if processor["name"] == processor_name:
                    target_processor = processor
                    break
            
            if target_processor:
                stats = target_processor.get("stats", {})
                proc_info = {
                    "name": processor_name,
                    "operation": "stats",
                    "status": target_processor.get("state", "UNKNOWN"),
                    "message": "Stats retrieved successfully",
                }
                
                if verbose and "full_response" in target_processor:
                    # Use the complete stats from the API response
                    api_stats = target_processor["full_response"].get("stats", {})
                    proc_info["stats"] = api_stats
                    # Also include pipeline info if verbose
                    if "pipeline" in target_processor["full_response"]:
                        proc_info["pipeline"] = target_processor["full_response"]["pipeline"]
                else:
                    # Use the limited stats subset for regular output
                    proc_info["stats"] = {
                        "processor": processor_name,
                        "state": target_processor.get("state", "UNKNOWN"),
                        "inputMessageCount": stats.get("inputMessageCount", 0),
                        "outputMessageCount": stats.get("outputMessageCount", 0),
                        "dlqMessageCount": stats.get("dlqMessageCount", 0),
                        "memoryUsageBytes": stats.get("memoryUsageBytes", 0),
                        "lastMessageIn": stats.get("lastMessageIn"),
                        "scaleFactor": stats.get("scaleFactor", 1)
                    }
                result["processors"].append(proc_info)
                result["summary"]["success"] = 1
            else:
                result["processors"].append({
                    "name": processor_name,
                    "operation": "stats",
                    "status": "NOT_FOUND",
                    "message": f"Processor '{processor_name}' not found"
                })
                result["summary"]["failed"] = 1
                
        except requests.RequestException as e:
            result["summary"]["failed"] = 1
            result["processors"].append({
                "name": processor_name,
                "operation": "stats",
                "status": "ERROR",
                "message": str(e)
            })
        
        return result
    
    def start_processor(self, processor_name: str, tier: str = None) -> Dict:
        """Start a specific processor with optional tier specification"""
        self._check_workspace_required()
        try:
            if tier:
                # Use :startWith endpoint for tier specification (correct API)
                url = f"{self.base_url}/processor/{processor_name}:startWith"
                data = {"tier": tier}
                response = requests.post(
                    url,
                    auth=self.auth,
                    headers=self.headers_v2025,
                    json=data
                )
                
                if response.status_code == 200:
                    return {
                        "name": processor_name,
                        "operation": "start",
                        "status": "started",
                        "message": f"Started successfully on tier {tier}",
                        "tier": tier
                    }
                elif response.status_code == 400:
                    # Parse error for tier requirement and retry if needed
                    error_text = response.text
                    suggested_tier = self._parse_tier_validation_error(error_text)
                    
                    if suggested_tier and suggested_tier != tier:
                        print(f"Tier {tier} insufficient, API suggests {suggested_tier}. Retrying...")
                        # Retry with suggested tier
                        retry_data = {"tier": suggested_tier}
                        retry_response = requests.post(
                            url,
                            auth=self.auth,
                            headers=self.headers_v2025,
                            json=retry_data
                        )
                        
                        if retry_response.status_code == 200:
                            return {
                                "name": processor_name,
                                "operation": "start",
                                "status": "started",
                                "message": f"Started successfully on tier {suggested_tier} (upgraded from {tier})",
                                "tier": suggested_tier
                            }
                        else:
                            print(f"Retry with {suggested_tier} also failed: {retry_response.text}")
                    else:
                        print(f"Warning: Tier specification '{tier}' failed: {error_text}")
                    
                    # Fall through to regular start
                else:
                    response.raise_for_status()
                    
            # Regular start endpoint (fallback when no tier specified)
            response = requests.post(
                f"{self.base_url}/processor/{processor_name}:start",
                auth=self.auth,
                headers=self.headers
            )
            
            response.raise_for_status()
            
            message = "Started successfully"
            if tier:
                message += " (using default tier - tier specification failed)"
                
            return {
                "name": processor_name,
                "operation": "start",
                "status": "started",
                "message": message,
                "tier": "current"
            }
            
        except requests.RequestException as e:
            return {
                "name": processor_name,
                "operation": "start", 
                "status": "failed",
                "message": str(e),
                "http_code": getattr(e.response, 'status_code', None)
            }
    
    def stop_processor(self, processor_name: str) -> Dict:
        """Stop a specific processor"""
        self._check_workspace_required()
        try:
            response = requests.post(
                f"{self.base_url}/processor/{processor_name}:stop",
                auth=self.auth,
                headers=self.headers
            )
            response.raise_for_status()
            return {
                "name": processor_name,
                "operation": "stop",
                "status": "stopped",
                "message": "Stopped successfully"
            }
        except requests.RequestException as e:
            return {
                "name": processor_name,
                "operation": "stop",
                "status": "failed",
                "message": str(e),
                "http_code": getattr(e.response, 'status_code', None)
            }
    
    def create_processor(self, name: str, pipeline_file: str) -> Dict:
        """Create a processor from a JavaScript pipeline file"""
        try:
            # Read the pipeline from file
            pipeline_path = Path(pipeline_file)
            if not pipeline_path.exists():
                return {
                    "name": name,
                    "file": pipeline_file,
                    "operation": "create_processor",
                    "status": "failed",
                    "message": f"Pipeline file '{pipeline_file}' not found"
                }
            
            with open(pipeline_path, 'r') as f:
                pipeline_code = f.read()
            
            # First try to delete existing processor (idempotent)
            try:
                requests.delete(
                    f"{self.base_url}/processor/{name}",
                    auth=self.auth,
                    headers=self.headers
                )
            except requests.RequestException:
                pass  # Ignore delete errors
            
            # Create the processor
            payload = {
                "name": name,
                "pipeline": pipeline_code
            }
            response = requests.post(
                f"{self.base_url}/processor",
                auth=self.auth,
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            
            return {
                "name": name,
                "file": pipeline_file,
                "operation": "create_processor",
                "status": "created",
                "message": "Processor created successfully"
            }
            
        except requests.RequestException as e:
            return {
                "name": name,
                "file": pipeline_file,
                "operation": "create_processor",
                "status": "failed",
                "message": str(e),
                "http_code": getattr(e.response, 'status_code', None)
            }

    def create_processor_from_content(self, name: str, pipeline_content: str) -> Dict:
        """Create a processor from pipeline content string"""
        try:
            # First try to delete existing processor (idempotent)
            try:
                requests.delete(
                    f"{self.base_url}/processor/{name}",
                    auth=self.auth,
                    headers=self.headers
                )
            except requests.RequestException:
                pass  # Ignore delete errors
            
            # Parse the JavaScript content to extract pipeline and options
            parsed_content = self._parse_js_processor_content(pipeline_content)
            
            # Create the processor with the correct payload format
            payload = {
                "name": name,
                "pipeline": parsed_content["pipeline"]
            }
            
            # Add options if they exist (like dlq configuration)
            if "options" in parsed_content:
                payload["options"] = parsed_content["options"]
            
            response = requests.post(
                f"{self.base_url}/processor",
                auth=self.auth,
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            
            return {
                "name": name,
                "operation": "create_processor",
                "status": "created",
                "message": "Processor created successfully"
            }
            
        except requests.RequestException as e:
            return {
                "name": name,
                "operation": "create_processor",
                "status": "failed",
                "message": str(e),
                "http_code": getattr(e.response, 'status_code', None)
            }
        except Exception as e:
            return {
                "name": name,
                "operation": "create_processor",
                "status": "failed",
                "message": f"Parse error: {str(e)}"
            }

    def _parse_js_processor_content(self, content: str) -> Dict:
        """Parse JavaScript processor content and convert to JSON format"""
        import json
        import re
        
        # Remove comments
        content = re.sub(r'//.*$', '', content, flags=re.MULTILINE)
        
        # Find the main object - look for { ... } that contains name and pipeline
        # This is a simple approach that works for our Terraform-like format
        
        # Extract pipeline array - find pipeline: [...] 
        pipeline_match = re.search(r'pipeline:\s*(\[.*?\])', content, re.DOTALL)
        if not pipeline_match:
            raise ValueError("Could not find pipeline array in JavaScript content")
        
        pipeline_str = pipeline_match.group(1)
        
        # Convert JavaScript object syntax to JSON
        # Replace unquoted property names with quoted ones
        pipeline_str = re.sub(r'(\w+):', r'"\1":', pipeline_str)
        # Handle special MongoDB operators that start with $
        pipeline_str = re.sub(r'"(\$\w+)":', r'"\1":', pipeline_str)
        
        try:
            pipeline = json.loads(pipeline_str)
        except json.JSONDecodeError as e:
            # If direct JSON parsing fails, try a more sophisticated approach
            # For now, return the original error
            raise ValueError(f"Could not parse pipeline as JSON: {str(e)}")
        
        result = {"pipeline": pipeline}
        
        # Look for options like dlq configuration
        dlq_match = re.search(r'dlq:\s*(\{[^}]+\})', content)
        if dlq_match:
            dlq_str = dlq_match.group(1)
            # Convert to JSON format
            dlq_str = re.sub(r'(\w+):', r'"\1":', dlq_str)
            try:
                dlq_config = json.loads(dlq_str)
                result["options"] = {"dlq": dlq_config}
            except json.JSONDecodeError:
                pass  # Ignore DLQ parsing errors for now
        
        return result

    def create_processor_from_json(self, name: str, pipeline: List[Dict], options: Dict = None) -> Dict:
        """Create a processor from JSON pipeline data"""
        self._check_workspace_required()
        try:
            # First try to delete existing processor (idempotent)
            try:
                requests.delete(
                    f"{self.base_url}/processors/{name}",
                    auth=self.auth,
                    headers=self.headers
                )
            except requests.RequestException:
                pass  # Ignore delete errors
            
            # Create the processor with the correct payload format
            payload = {
                "name": name,
                "pipeline": pipeline
            }
            
            # Add options if they exist (like dlq configuration)
            if options:
                payload["options"] = options
            
            response = requests.post(
                f"{self.base_url}/processor",
                auth=self.auth,
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            
            return {
                "name": name,
                "operation": "create_processor",
                "status": "created",
                "message": "Processor created successfully"
            }
            
        except requests.RequestException as e:
            error_detail = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_body = e.response.json()
                    error_detail = f"{str(e)} - {error_body.get('detail', error_body)}"
                except:
                    error_detail = f"{str(e)} - {e.response.text}"
            
            return {
                "name": name,
                "operation": "create_processor",
                "status": "failed",
                "message": error_detail,
                "http_code": getattr(e.response, 'status_code', None)
            }

    def delete_processor(self, processor_name: str) -> Dict:
        """Delete a processor by name"""
        self._check_workspace_required()
        try:
            # Use the correct endpoint format from MongoDB documentation
            # DELETE /api/atlas/v2/groups/{groupId}/streams/{tenantName}/processor/{processorName}
            response = requests.delete(
                f"{self.base_url}/processor/{processor_name}",
                auth=self.auth,
                headers=self.headers
            )
            response.raise_for_status()
            
            return {
                "name": processor_name,
                "operation": "delete_processor",
                "status": "deleted",
                "message": "Processor deleted successfully"
            }
            
        except requests.RequestException as e:
            return {
                "name": processor_name,
                "operation": "delete_processor",
                "status": "failed",
                "message": str(e),
                "http_code": getattr(e.response, 'status_code', None)
            }
    
    # Connection Operations
    def list_connections(self) -> List[Dict]:
        """Get list of all connections"""
        self._check_workspace_required()
        response = requests.get(
            f"{self.base_url}/connections",
            auth=self.auth,
            headers=self.headers
        )
        response.raise_for_status()
        return response.json().get("results", [])
    
    def create_http_connection(self, name: str, url: str) -> Dict:
        """Create an HTTP connection"""
        self._check_workspace_required()
        try:
            payload = {
                "name": name,
                "type": "Https",
                "url": url
            }
            response = requests.post(
                f"{self.base_url}/connections",
                auth=self.auth,
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            return {
                "name": name,
                "type": "Https",
                "url": url,
                "operation": "create_connection",
                "status": "created",
                "message": "HTTP connection created successfully"
            }
        except requests.RequestException as e:
            status_code = getattr(e.response, 'status_code', None)
            if status_code == 409:
                return {
                    "name": name,
                    "type": "Https", 
                    "url": url,
                    "operation": "create_connection",
                    "status": "already_exists",
                    "message": "HTTP connection already exists"
                }
            return {
                "name": name,
                "type": "Https",
                "url": url,
                "operation": "create_connection",
                "status": "failed",
                "message": str(e),
                "http_code": status_code
            }
    
    def create_cluster_connection(self, name: str, cluster_name: str, db_role: Dict = None) -> Dict:
        """Create a MongoDB cluster connection"""
        self._check_workspace_required()
        try:
            payload = {
                "name": name,
                "type": "Cluster",
                "clusterName": cluster_name
            }
            
            # Add database role if provided
            if db_role:
                payload["dbRoleToExecute"] = db_role
            else:
                # Default role if none provided
                payload["dbRoleToExecute"] = {
                    "role": "atlasAdmin",
                    "type": "BUILT_IN"
                }
            response = requests.post(
                f"{self.base_url}/connections",
                auth=self.auth,
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            return {
                "name": name,
                "type": "Cluster",
                "clusterName": cluster_name,
                "operation": "create_connection",
                "status": "created",
                "message": "Cluster connection created successfully"
            }
        except requests.RequestException as e:
            status_code = getattr(e.response, 'status_code', None)
            if status_code == 409:
                return {
                    "name": name,
                    "type": "Cluster",
                    "clusterName": cluster_name,
                    "operation": "create_connection",
                    "status": "already_exists",
                    "message": "Cluster connection already exists"
                }
            return {
                "name": name,
                "type": "Cluster",
                "clusterName": cluster_name,
                "operation": "create_connection",
                "status": "failed",
                "message": self._get_detailed_error(e),
                "http_code": status_code
            }

    def delete_connection(self, connection_name: str) -> Dict:
        """Delete a connection"""
        self._check_workspace_required()
        try:
            response = requests.delete(
                f"{self.base_url}/connections/{connection_name}",
                auth=self.auth,
                headers=self.headers
            )
            response.raise_for_status()
            return {
                "name": connection_name,
                "operation": "delete_connection",
                "status": "deleted",
                "message": "Connection deleted successfully"
            }
        except requests.RequestException as e:
            status_code = getattr(e.response, 'status_code', None)
            if status_code == 404:
                return {
                    "name": connection_name,
                    "operation": "delete_connection",
                    "status": "not_found",
                    "message": "Connection not found"
                }
            return {
                "name": connection_name,
                "operation": "delete_connection",
                "status": "failed",
                "message": str(e),
                "http_code": status_code
            }

    # Profiling Methods
    def profile_processors(self, processor_names: List[str], duration: int, interval: int, 
                          metrics: List[str], thresholds: Dict = None) -> Dict:
        """Profile processors over a specified time period"""
        import time
        
        start_time = time.time()
        samples = []
        thresholds = thresholds or {}
        
        print(f"Collecting samples every {interval}s for {duration}s...")
        
        sample_count = 0
        while time.time() - start_time < duration:
            timestamp = datetime.now(timezone.utc).isoformat()
            sample = {"timestamp": timestamp, "processors": [], "alerts": []}
            
            for processor_name in processor_names:
                try:
                    stats_result = self.get_single_processor_stats(processor_name, verbose=True)
                    if stats_result["summary"]["success"] > 0:
                        stats = stats_result["processors"][0]["stats"]
                        
                        # Extract key metrics
                        proc_sample = {
                            "name": processor_name,
                            "memory_mb": stats.get("memoryUsageBytes", 0) / 1_048_576,
                            "input_count": stats.get("inputMessageCount", 0),
                            "output_count": stats.get("outputMessageCount", 0),
                            "dlq_count": stats.get("dlqMessageCount", 0),
                            "latency_p50_us": stats.get("latency", {}).get("p50", 0),
                            "latency_p99_us": stats.get("latency", {}).get("p99", 0),
                            "state_size_bytes": stats.get("stateSize", 0),
                            "scale_factor": stats.get("scaleFactor", 1)
                        }
                        
                        # Calculate throughput if we have previous sample
                        if len(samples) > 0:
                            prev_sample = next((p for p in samples[-1]["processors"] if p["name"] == processor_name), None)
                            if prev_sample:
                                input_diff = proc_sample["input_count"] - prev_sample["input_count"]
                                proc_sample["throughput_per_sec"] = max(0, input_diff / interval)
                            else:
                                proc_sample["throughput_per_sec"] = 0
                        else:
                            proc_sample["throughput_per_sec"] = 0
                        
                        sample["processors"].append(proc_sample)
                        
                        # Check thresholds
                        alerts = self._check_thresholds(proc_sample, thresholds)
                        sample["alerts"].extend(alerts)
                        
                except Exception as e:
                    sample["processors"].append({
                        "name": processor_name,
                        "error": str(e)
                    })
            
            samples.append(sample)
            sample_count += 1
            
            # Show progress
            elapsed = time.time() - start_time
            remaining = duration - elapsed
            print(f"Sample {sample_count}: {remaining:.0f}s remaining...")
            
            if remaining > interval:
                time.sleep(interval)
            elif remaining > 0:
                time.sleep(remaining)
        
        return self._analyze_profile_data(samples, duration, interval)

    def profile_processors_continuous(self, processor_names: List[str], interval: int, 
                                    metrics: List[str], thresholds: Dict = None) -> Dict:
        """Continuously profile processors until interrupted"""
        import time
        
        samples = []
        thresholds = thresholds or {}
        start_time = time.time()
        
        try:
            sample_count = 0
            while True:
                timestamp = datetime.now(timezone.utc).isoformat()
                sample = {"timestamp": timestamp, "processors": [], "alerts": []}
                
                for processor_name in processor_names:
                    try:
                        stats_result = self.get_single_processor_stats(processor_name, verbose=True)
                        if stats_result["summary"]["success"] > 0:
                            stats = stats_result["processors"][0]["stats"]
                            
                            proc_sample = {
                                "name": processor_name,
                                "memory_mb": stats.get("memoryUsageBytes", 0) / 1_048_576,
                                "input_count": stats.get("inputMessageCount", 0),
                                "output_count": stats.get("outputMessageCount", 0),
                                "latency_p50_us": stats.get("latency", {}).get("p50", 0),
                                "latency_p99_us": stats.get("latency", {}).get("p99", 0)
                            }
                            
                            # Calculate throughput
                            if len(samples) > 0:
                                prev_sample = next((p for p in samples[-1]["processors"] if p["name"] == processor_name), None)
                                if prev_sample:
                                    input_diff = proc_sample["input_count"] - prev_sample["input_count"]
                                    proc_sample["throughput_per_sec"] = max(0, input_diff / interval)
                                else:
                                    proc_sample["throughput_per_sec"] = 0
                            else:
                                proc_sample["throughput_per_sec"] = 0
                            
                            sample["processors"].append(proc_sample)
                            
                            # Check thresholds and print alerts immediately
                            alerts = self._check_thresholds(proc_sample, thresholds)
                            for alert in alerts:
                                print(f"🚨 ALERT: {alert}")
                            sample["alerts"].extend(alerts)
                            
                    except Exception as e:
                        sample["processors"].append({"name": processor_name, "error": str(e)})
                
                samples.append(sample)
                sample_count += 1
                
                # Print live stats
                elapsed = time.time() - start_time
                print(f"\n=== Sample {sample_count} ({elapsed:.0f}s elapsed) ===")
                for proc in sample["processors"]:
                    if "error" not in proc:
                        print(f"{proc['name']}: "
                              f"Memory: {proc['memory_mb']:.1f}MB, "
                              f"Latency: p50={proc['latency_p50_us']/1000:.1f}ms, "
                              f"Throughput: {proc['throughput_per_sec']:.1f}/sec")
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            elapsed = time.time() - start_time
            return self._analyze_profile_data(samples, elapsed, interval)

    def _check_thresholds(self, proc_sample: Dict, thresholds: Dict) -> List[str]:
        """Check if processor metrics exceed defined thresholds"""
        alerts = []
        proc_name = proc_sample["name"]
        
        if "memory_mb" in thresholds and proc_sample.get("memory_mb", 0) > thresholds["memory_mb"]:
            alerts.append(f"{proc_name}: High memory usage ({proc_sample['memory_mb']:.1f}MB > {thresholds['memory_mb']}MB)")
        
        if "latency_p99_ms" in thresholds:
            p99_ms = proc_sample.get("latency_p99_us", 0) / 1000
            if p99_ms > thresholds["latency_p99_ms"]:
                alerts.append(f"{proc_name}: High latency ({p99_ms:.1f}ms > {thresholds['latency_p99_ms']}ms)")
        
        if "throughput_min" in thresholds and proc_sample.get("throughput_per_sec", 0) < thresholds["throughput_min"]:
            alerts.append(f"{proc_name}: Low throughput ({proc_sample['throughput_per_sec']:.1f}/sec < {thresholds['throughput_min']}/sec)")
        
        return alerts

    def _analyze_profile_data(self, samples: List[Dict], duration: float, interval: int) -> Dict:
        """Analyze profiling data for trends and insights"""
        if not samples:
            return {"error": "No samples collected"}
        
        analysis = {
            "profile_summary": {
                "start_time": samples[0]["timestamp"],
                "end_time": samples[-1]["timestamp"],
                "duration_seconds": duration,
                "sample_count": len(samples),
                "interval_seconds": interval
            },
            "processors": {},
            "alerts": []
        }
        
        # Collect all alerts
        for sample in samples:
            analysis["alerts"].extend(sample.get("alerts", []))
        
        # Per-processor analysis
        if samples and samples[0]["processors"]:
            for processor_name in [p["name"] for p in samples[0]["processors"] if "error" not in p]:
                proc_data = []
                for sample in samples:
                    proc_sample = next((p for p in sample["processors"] if p["name"] == processor_name and "error" not in p), None)
                    if proc_sample:
                        proc_data.append(proc_sample)
                
                if proc_data:
                    analysis["processors"][processor_name] = self._calculate_processor_stats(proc_data)
        
        return analysis

    def _calculate_processor_stats(self, proc_data: List[Dict]) -> Dict:
        """Calculate statistics for a single processor's profile data"""
        memory_values = [p["memory_mb"] for p in proc_data]
        latency_p50_values = [p["latency_p50_us"]/1000 for p in proc_data]  # Convert to ms
        latency_p99_values = [p["latency_p99_us"]/1000 for p in proc_data]  # Convert to ms
        throughput_values = [p.get("throughput_per_sec", 0) for p in proc_data]
        
        def safe_stats(values):
            if not values or all(v == 0 for v in values):
                return {"min": 0, "max": 0, "avg": 0, "trend": "stable"}
            return {
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values),
                "trend": self._calculate_trend(values)
            }
        
        stats = {
            "memory_mb": safe_stats(memory_values),
            "latency_p50_ms": safe_stats(latency_p50_values),
            "latency_p99_ms": safe_stats(latency_p99_values),
            "throughput_per_sec": safe_stats(throughput_values),
            "samples": len(proc_data)
        }
        
        # Add recommendations
        stats["recommendations"] = self._generate_recommendations(stats)
        
        return stats

    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction for a series of values"""
        if len(values) < 2:
            return "insufficient_data"
        
        # Simple linear trend
        first_half = values[:len(values)//2]
        second_half = values[len(values)//2:]
        
        if not first_half or not second_half:
            return "stable"
        
        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)
        
        change_pct = ((second_avg - first_avg) / first_avg * 100) if first_avg > 0 else 0
        
        if abs(change_pct) < 5:
            return "stable"
        elif change_pct > 5:
            return "increasing"
        else:
            return "decreasing"

    def _generate_recommendations(self, stats: Dict) -> List[str]:
        """Generate performance recommendations based on profile statistics"""
        recommendations = []
        
        memory_stats = stats.get("memory_mb", {})
        latency_stats = stats.get("latency_p99_ms", {})
        throughput_stats = stats.get("throughput_per_sec", {})
        
        # Memory recommendations
        if memory_stats.get("trend") == "increasing":
            recommendations.append("Memory usage is increasing - monitor for potential memory leaks")
        elif memory_stats.get("max", 0) > 1000:
            recommendations.append("High memory usage detected - consider increasing tier or optimizing processor")
        elif memory_stats.get("avg", 0) < 100:
            recommendations.append("Low memory usage - processor may be over-provisioned")
        
        # Latency recommendations
        if latency_stats.get("trend") == "increasing":
            recommendations.append("Latency is increasing - check for performance degradation")
        elif latency_stats.get("avg", 0) > 50:
            recommendations.append("High average latency - consider tier upgrade or optimization")
        
        # Throughput recommendations
        if throughput_stats.get("trend") == "decreasing":
            recommendations.append("Throughput is decreasing - investigate potential bottlenecks")
        elif throughput_stats.get("avg", 0) < 1:
            recommendations.append("Low throughput detected - verify data source and processing logic")
        
        if not recommendations:
            recommendations.append("Processor performance appears healthy")
        
        return recommendations


def main():
    """Command line interface for Atlas API operations"""
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="Atlas Stream Processing API CLI")
    parser.add_argument("command", choices=["list", "stats", "delete", "start", "stop"], 
                       help="Command to execute")
    parser.add_argument("processor_name", nargs="?", help="Processor name for delete/start/stop commands")
    parser.add_argument("--config", default="../config.txt", help="API configuration file")
    
    args = parser.parse_args()
    
    try:
        api = AtlasStreamProcessingAPI(args.config)
        
        if args.command == "list":
            result = api.get_processor_status()
            print(colorize_json(result))
        elif args.command == "stats":
            result = api.get_processor_stats()
            print(colorize_json(result))
        elif args.command == "delete":
            if not args.processor_name:
                print(colorize_json({"error": "Processor name required for delete command"}))
                sys.exit(1)
            result = api.delete_processor(args.processor_name)
            print(colorize_json(result))
        elif args.command == "start":
            if not args.processor_name:
                print(colorize_json({"error": "Processor name required for start command"}))
                sys.exit(1)
            result = api.start_processor(args.processor_name)
            print(colorize_json(result))
        elif args.command == "stop":
            if not args.processor_name:
                print(colorize_json({"error": "Processor name required for stop command"}))
                sys.exit(1)
            result = api.stop_processor(args.processor_name)
            print(colorize_json(result))
            
    except Exception as e:
        error_result = {"error": str(e)}
        print(colorize_json(error_result))
        sys.exit(1)


if __name__ == "__main__":
    main()
