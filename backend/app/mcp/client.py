"""
MCP 客户端 - 支持 HTTP 和 Stdio 两种连接方式
"""
from typing import Any, Dict, List, Optional, Callable
import logging
import json
import subprocess
import threading
import os

logger = logging.getLogger(__name__)

try:
    import sseclient
    SSE_AVAILABLE = True
except ImportError:
    SSE_AVAILABLE = False
    logger.warning("sseclient not available, SSE notifications disabled")


class MCPClientBase:
    """MCP 客户端基类"""
    
    def __init__(self, name: str = ""):
        self.name = name
        self._connected = False
        self.tools: List[Dict] = []
        self.resources: List[Dict] = []
    
    def connect(self) -> bool:
        raise NotImplementedError
    
    def disconnect(self):
        raise NotImplementedError
    
    def list_tools(self) -> List[Dict]:
        raise NotImplementedError
    
    def call_tool(self, tool_name: str, arguments: Dict) -> Any:
        raise NotImplementedError
    
    def list_resources(self) -> List[Dict]:
        raise NotImplementedError
    
    def read_resource(self, uri: str) -> Any:
        raise NotImplementedError
    
    def get_info(self) -> Dict:
        raise NotImplementedError


class MCPClient(MCPClientBase):
    """HTTP 方式的 MCP 客户端"""
    
    def __init__(self, server_url: str, name: str = ""):
        super().__init__(name)
        self.server_url = server_url.rstrip("/")
        self.session = None
    
    def connect(self) -> bool:
        try:
            import requests
            self.session = requests.Session()
            self.session.headers.update({"Content-Type": "application/json"})
            
            response = self.session.post(
                f"{self.server_url}/mcp/initialize",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {}
                    }
                },
                timeout=30
            )
            if response.status_code == 200:
                self._connected = True
                logger.info(f"Connected to MCP server (HTTP): {self.name}")
                return True
        except Exception as e:
            logger.error(f"Failed to connect to MCP server {self.name}: {e}")
        
        return False
    
    def disconnect(self):
        self._connected = False
        if self.session:
            self.session.close()
    
    def list_tools(self) -> List[Dict]:
        if not self._connected or not self.session:
            return []
        
        try:
            response = self.session.post(
                f"{self.server_url}/mcp/tools/list",
                json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                timeout=10
            )
            if response.status_code == 200:
                result = response.json()
                self.tools = result.get("result", {}).get("tools", [])
                return self.tools
        except Exception as e:
            logger.error(f"Failed to list tools from MCP server: {e}")
        
        return []
    
    def call_tool(self, tool_name: str, arguments: Dict) -> Any:
        if not self._connected or not self.session:
            raise RuntimeError("Not connected to MCP server")
        
        try:
            response = self.session.post(
                f"{self.server_url}/mcp/tools/call",
                json={
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": arguments
                    }
                },
                timeout=60
            )
            if response.status_code == 200:
                result = response.json()
                return result.get("result", {})
        except Exception as e:
            logger.error(f"Failed to call tool {tool_name}: {e}")
            raise
        
        return None
    
    def list_resources(self) -> List[Dict]:
        if not self._connected or not self.session:
            return []
        
        try:
            response = self.session.post(
                f"{self.server_url}/mcp/resources/list",
                json={"jsonrpc": "2.0", "id": 4, "method": "resources/list"},
                timeout=10
            )
            if response.status_code == 200:
                result = response.json()
                self.resources = result.get("result", {}).get("resources", [])
                return self.resources
        except Exception as e:
            logger.error(f"Failed to list resources from MCP server: {e}")
        
        return []
    
    def read_resource(self, uri: str) -> Any:
        if not self._connected or not self.session:
            raise RuntimeError("Not connected to MCP server")
        
        try:
            response = self.session.post(
                f"{self.server_url}/mcp/resources/read",
                json={
                    "jsonrpc": "2.0",
                    "id": 5,
                    "method": "resources/read",
                    "params": {"uri": uri}
                },
                timeout=30
            )
            if response.status_code == 200:
                result = response.json()
                return result.get("result", {})
        except Exception as e:
            logger.error(f"Failed to read resource {uri}: {e}")
            raise
        
        return None
    
    def subscribe_to_notifications(self, callback: Callable):
        if not self._connected or not self.session:
            raise RuntimeError("Not connected to MCP server")
        
        if not SSE_AVAILABLE:
            logger.warning("SSE not available, notifications disabled")
            return
        
        def sse_listener():
            try:
                response = self.session.get(
                    f"{self.server_url}/mcp/notifications",
                    stream=True,
                    timeout=300
                )
                client = sseclient.SSEClient(response)
                for event in client.events():
                    if event.data:
                        callback(json.loads(event.data))
            except Exception as e:
                logger.error(f"SSE listener error: {e}")
        
        thread = threading.Thread(target=sse_listener, daemon=True)
        thread.start()
    
    def get_info(self) -> Dict:
        return {
            "name": self.name,
            "type": "http",
            "url": self.server_url,
            "connected": self._connected,
            "tools_count": len(self.tools),
            "resources_count": len(self.resources)
        }


class StdioMCPClient(MCPClientBase):
    """Stdio 方式的 MCP 客户端（通过子进程启动）"""
    
    def __init__(self, command: str, args: List[str], name: str = "", cwd: str = None):
        super().__init__(name or "stdio-mcp")
        self.command = command
        self.args = args
        self.cwd = cwd or os.getcwd()
        self.process: subprocess.Popen = None
        self._request_id = 0
        self._lock = threading.Lock()
    
    def connect(self) -> bool:
        try:
            self.process = subprocess.Popen(
                [self.command] + self.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.cwd,
                bufsize=1,
                text=True
            )
            
            initialize_request = {
                "jsonrpc": "2.0",
                "id": self._get_next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "email-assistant",
                        "version": "1.0.0"
                    }
                }
            }
            
            response = self._send_request(initialize_request)
            if response and "result" in response:
                self._connected = True
                logger.info(f"Connected to MCP server (Stdio): {self.name}")
                return True
            else:
                logger.error(f"Failed to initialize MCP server: {response}")
                self.process.terminate()
        except Exception as e:
            logger.error(f"Failed to connect to MCP server (Stdio) {self.name}: {e}")
        
        return False
    
    def disconnect(self):
        self._connected = False
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
    
    def _get_next_id(self) -> int:
        with self._lock:
            self._request_id += 1
            return self._request_id
    
    def _send_request(self, request: Dict) -> Optional[Dict]:
        if not self.process or not self.process.stdin or not self.process.stdout:
            return None
        
        try:
            request_str = json.dumps(request) + "\n"
            self.process.stdin.write(request_str)
            self.process.stdin.flush()
            
            response_line = self.process.stdout.readline()
            if response_line:
                return json.loads(response_line)
        except Exception as e:
            logger.error(f"Error sending request to MCP: {e}")
        
        return None
    
    def _send_request_sync(self, method: str, params: Dict = None) -> Optional[Dict]:
        request = {
            "jsonrpc": "2.0",
            "id": self._get_next_id(),
            "method": method,
            "params": params or {}
        }
        return self._send_request(request)
    
    def list_tools(self) -> List[Dict]:
        if not self._connected:
            return []
        
        try:
            response = self._send_request_sync("tools/list")
            if response and "result" in response:
                self.tools = response.get("result", {}).get("tools", [])
                return self.tools
        except Exception as e:
            logger.error(f"Failed to list tools from MCP server: {e}")
        
        return []
    
    def call_tool(self, tool_name: str, arguments: Dict) -> Any:
        if not self._connected:
            raise RuntimeError("Not connected to MCP server")
        
        request = {
            "jsonrpc": "2.0",
            "id": self._get_next_id(),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        
        response = self._send_request(request)
        if response and "result" in response:
            return response.get("result", {})
        elif response and "error" in response:
            error = response.get("error", {})
            raise RuntimeError(f"MCP error: {error.get('message', 'Unknown error')}")
        
        return None
    
    def list_resources(self) -> List[Dict]:
        if not self._connected:
            return []
        
        try:
            response = self._send_request_sync("resources/list")
            if response and "result" in response:
                self.resources = response.get("result", {}).get("resources", [])
                return self.resources
        except Exception as e:
            logger.error(f"Failed to list resources from MCP server: {e}")
        
        return []
    
    def read_resource(self, uri: str) -> Any:
        if not self._connected:
            raise RuntimeError("Not connected to MCP server")
        
        response = self._send_request_sync("resources/read", {"uri": uri})
        if response and "result" in response:
            return response.get("result", {})
        
        return None
    
    def subscribe_to_notifications(self, callback: Callable):
        logger.warning("SSE notifications not supported for stdio MCP client")
    
    def get_info(self) -> Dict:
        return {
            "name": self.name,
            "type": "stdio",
            "command": self.command,
            "args": self.args,
            "cwd": self.cwd,
            "connected": self._connected,
            "tools_count": len(self.tools),
            "resources_count": len(self.resources)
        }


class MCPClientManager:
    """MCP 客户端管理器 - 支持 HTTP 和 Stdio 两种客户端"""
    
    def __init__(self):
        self.clients: Dict[str, MCPClientBase] = {}
        self.logger = logging.getLogger("mcp.manager")
    
    def add_http_client(self, name: str, server_url: str) -> Optional[MCPClient]:
        """添加 HTTP MCP 客户端"""
        client = MCPClient(server_url, name)
        if client.connect():
            self.clients[name] = client
            self.logger.info(f"Added HTTP MCP client: {name} -> {server_url}")
            return client
        return None
    
    def add_stdio_client(self, name: str, command: str, args: List[str], cwd: str = None) -> Optional[StdioMCPClient]:
        """添加 Stdio MCP 客户端"""
        client = StdioMCPClient(command, args, name, cwd)
        if client.connect():
            self.clients[name] = client
            self.logger.info(f"Added Stdio MCP client: {name} -> {command} {' '.join(args)}")
            return client
        return None
    
    def add_client(self, name: str, server_url: str = None, command: str = None, args: List[str] = None, cwd: str = None) -> Optional[MCPClientBase]:
        """通用添加客户端（自动识别类型）"""
        if server_url:
            return self.add_http_client(name, server_url)
        elif command and args:
            return self.add_stdio_client(name, command, args, cwd)
        else:
            self.logger.error(f"Invalid MCP client config for {name}")
            return None
    
    def remove_client(self, name: str) -> bool:
        """移除 MCP 客户端"""
        if name in self.clients:
            self.clients[name].disconnect()
            del self.clients[name]
            self.logger.info(f"Removed MCP client: {name}")
            return True
        return False
    
    def get_client(self, name: str) -> Optional[MCPClientBase]:
        """获取 MCP 客户端"""
        return self.clients.get(name)
    
    def list_clients(self) -> List[Dict]:
        """列出所有客户端"""
        return [
            client.get_info() for client in self.clients.values()
        ]
    
    def get_all_tools(self) -> List[Dict]:
        """获取所有客户端的工具"""
        tools = []
        for name, client in self.clients.items():
            try:
                client_tools = client.list_tools()
                for tool in client_tools:
                    tool["source"] = name
                    tools.append(tool)
            except Exception as e:
                self.logger.error(f"Failed to get tools from {name}: {e}")
        return tools
    
    def call_tool(self, tool_name: str, arguments: Dict, source: str = None) -> Any:
        """调用工具（自动路由）"""
        if source:
            client = self.get_client(source)
            if client:
                return client.call_tool(tool_name, arguments)
            raise ValueError(f"MCP client '{source}' not found")
        
        # 遍历所有客户端查找工具
        for name, client in self.clients.items():
            try:
                return client.call_tool(tool_name, arguments)
            except:
                continue
        
        raise ValueError(f"Tool '{tool_name}' not found in any MCP client")


# 全局 MCP 客户端管理器
_mcp_manager = MCPClientManager()


def get_mcp_manager() -> MCPClientManager:
    """获取全局 MCP 管理器"""
    return _mcp_manager
