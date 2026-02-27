"""
LSP (Language Server Protocol) module for OpenCode.

Handles language server integration including:
- LSP client implementation
- Server management
- Feature support (completion, diagnostics, etc.)
"""

import asyncio
import json
import subprocess
from typing import Any, Optional, Callable
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum


class MessageType(Enum):
    """LSP message type."""
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"


class SymbolKind(Enum):
    """LSP symbol kind."""
    FILE = 1
    MODULE = 2
    NAMESPACE = 3
    PACKAGE = 4
    CLASS = 5
    METHOD = 6
    PROPERTY = 7
    FIELD = 8
    CONSTRUCTOR = 9
    ENUM = 10
    INTERFACE = 11
    FUNCTION = 12
    VARIABLE = 13
    CONSTANT = 14
    STRING = 15
    NUMBER = 16
    BOOLEAN = 17
    ARRAY = 18
    OBJECT = 19
    KEY = 20
    NULL = 21
    ENUM_MEMBER = 22
    STRUCT = 23
    EVENT = 24
    OPERATOR = 25
    TYPE_PARAMETER = 26


class DiagnosticSeverity(Enum):
    """LSP diagnostic severity."""
    ERROR = 1
    WARNING = 2
    INFORMATION = 3
    HINT = 4


class CompletionItemKind(Enum):
    """LSP completion item kind."""
    TEXT = 1
    METHOD = 2
    FUNCTION = 3
    CONSTRUCTOR = 4
    FIELD = 5
    VARIABLE = 6
    CLASS = 7
    INTERFACE = 8
    MODULE = 9
    PROPERTY = 10
    UNIT = 11
    VALUE = 12
    ENUM = 13
    KEYWORD = 14
    SNIPPET = 15
    COLOR = 16
    FILE = 17
    REFERENCE = 18
    FOLDER = 19
    ENUM_MEMBER = 20
    CONSTANT = 21
    STRUCT = 22
    EVENT = 23
    OPERATOR = 24
    TYPE_PARAMETER = 25


@dataclass
class Position:
    """LSP position."""
    line: int
    character: int
    
    def to_dict(self) -> dict:
        return {"line": self.line, "character": self.character}


@dataclass
class Range:
    """LSP range."""
    start: Position
    end: Position
    
    def to_dict(self) -> dict:
        return {
            "start": self.start.to_dict(),
            "end": self.end.to_dict(),
        }


@dataclass
class TextDocumentIdentifier:
    """Text document identifier."""
    uri: str
    
    def to_dict(self) -> dict:
        return {"uri": self.uri}


@dataclass
class TextDocumentPosition:
    """Text document position params."""
    text_document: TextDocumentIdentifier
    position: Position
    
    def to_dict(self) -> dict:
        return {
            "textDocument": self.text_document.to_dict(),
            "position": self.position.to_dict(),
        }


@dataclass
class Diagnostic:
    """LSP diagnostic."""
    range: Range
    severity: DiagnosticSeverity
    code: Optional[str] = None
    source: Optional[str] = None
    message: str = ""
    
    def to_dict(self) -> dict:
        result = {
            "range": self.range.to_dict(),
            "message": self.message,
        }
        if self.severity:
            result["severity"] = self.severity.value
        if self.code:
            result["code"] = self.code
        if self.source:
            result["source"] = self.source
        return result


@dataclass
class CompletionItem:
    """LSP completion item."""
    label: str
    kind: Optional[CompletionItemKind] = None
    detail: Optional[str] = None
    documentation: Optional[str] = None
    sort_text: Optional[str] = None
    filter_text: Optional[str] = None
    text_edit: Optional[str] = None
    
    def to_dict(self) -> dict:
        result = {"label": self.label}
        if self.kind:
            result["kind"] = self.kind.value
        if self.detail:
            result["detail"] = self.detail
        if self.documentation:
            result["documentation"] = self.documentation
        if self.sort_text:
            result["sortText"] = self.sort_text
        if self.filter_text:
            result["filterText"] = self.filter_text
        if self.text_edit:
            result["textEdit"] = {"newText": self.text_edit}
        return result


@dataclass
class SymbolInformation:
    """LSP symbol information."""
    name: str
    kind: SymbolKind
    location: dict
    container_name: Optional[str] = None
    
    def to_dict(self) -> dict:
        result = {
            "name": self.name,
            "kind": self.kind.value,
            "location": self.location,
        }
        if self.container_name:
            result["containerName"] = self.container_name
        return result


class LSPClient:
    """
    LSP client for communicating with language servers.
    """
    
    def __init__(
        self,
        server_command: list[str],
        root_uri: Optional[str] = None,
        language_id: str = "python",
    ):
        self.server_command = server_command
        self.root_uri = root_uri
        self.language_id = language_id
        self._process: Optional[subprocess.Popen] = None
        self._message_id = 0
        self._pending_requests: dict[int, asyncio.Future] = {}
        self._notification_handlers: dict[str, Callable] = {}
        self._initialized = False
        self._receive_task: Optional[asyncio.Task] = None
    
    async def start(self) -> bool:
        """Start the language server."""
        try:
            self._process = subprocess.Popen(
                self.server_command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
            )
            
            # Start receive loop
            self._receive_task = asyncio.create_task(self._receive_loop())
            
            # Initialize
            await self._initialize()
            
            self._initialized = True
            return True
            
        except Exception as e:
            print(f"Failed to start LSP server: {e}")
            return False
    
    async def stop(self) -> None:
        """Stop the language server."""
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        
        if self._process:
            await self._send_request("shutdown", {})
            self._send_notification("exit")
            self._process.terminate()
            self._process.wait(timeout=5)
        
        self._initialized = False
    
    async def _send_message(self, message: dict) -> None:
        """Send a message to the server."""
        if not self._process or not self._process.stdin:
            return
        
        content = json.dumps(message)
        header = f"Content-Length: {len(content)}\r\n\r\n"
        
        self._process.stdin.write(header.encode('utf-8'))
        self._process.stdin.write(content.encode('utf-8'))
        self._process.stdin.flush()
    
    async def _receive_loop(self) -> None:
        """Receive messages from the server."""
        import sys
        
        buffer = b""
        
        while self._process and self._process.poll() is None:
            try:
                # Read data
                data = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self._process.stdout.read(4096)
                )
                
                if not data:
                    break
                
                buffer += data
                
                # Process complete messages
                while b"\r\n\r\n" in buffer:
                    header, rest = buffer.split(b"\r\n\r\n", 1)
                    header_str = header.decode('utf-8')
                    
                    # Parse content length
                    content_length = 0
                    for line in header_str.split("\r\n"):
                        if line.startswith("Content-Length:"):
                            content_length = int(line.split(":")[1].strip())
                            break
                    
                    if len(rest) >= content_length:
                        body = rest[:content_length].decode('utf-8')
                        buffer = rest[content_length:]
                        
                        try:
                            message = json.loads(body)
                            await self._handle_message(message)
                        except json.JSONDecodeError:
                            pass
                            
            except Exception as e:
                print(f"LSP receive error: {e}")
                break
        
        self._initialized = False
    
    async def _handle_message(self, message: dict) -> None:
        """Handle incoming message."""
        if "id" in message and "result" in message or "error" in message:
            # Response
            message_id = message["id"]
            future = self._pending_requests.pop(message_id, None)
            if future:
                if "error" in message:
                    future.set_exception(Exception(message["error"]["message"]))
                else:
                    future.set_result(message.get("result"))
                    
        elif "method" in message:
            # Notification or request
            method = message["method"]
            params = message.get("params", {})
            
            handler = self._notification_handlers.get(method)
            if handler:
                if asyncio.iscoroutinefunction(handler):
                    await handler(params)
                else:
                    handler(params)
    
    async def _send_request(self, method: str, params: dict) -> Any:
        """Send a request and wait for response."""
        self._message_id += 1
        message_id = self._message_id
        
        message = {
            "jsonrpc": "2.0",
            "id": message_id,
            "method": method,
            "params": params,
        }
        
        future: asyncio.Future = asyncio.Future()
        self._pending_requests[message_id] = future
        
        await self._send_message(message)
        
        return await future
    
    async def _send_notification(self, method: str, params: Optional[dict] = None) -> None:
        """Send a notification."""
        message = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
        }
        await self._send_message(message)
    
    async def _initialize(self) -> None:
        """Initialize the language server."""
        result = await self._send_request("initialize", {
            "processId": None,
            "rootUri": self.root_uri,
            "capabilities": {
                "textDocument": {
                    "synchronization": {
                        "dynamicRegistration": True,
                        "willSave": False,
                        "didSave": True,
                        "willSaveWaitUntil": False,
                    },
                    "completion": {
                        "dynamicRegistration": True,
                        "completionItem": {
                            "snippetSupport": True,
                        },
                    },
                    "hover": {
                        "dynamicRegistration": True,
                    },
                    "diagnostics": {
                        "dynamicRegistration": True,
                    },
                },
                "workspace": {
                    "workspaceFolders": True,
                },
            },
        })
        
        await self._send_notification("initialized")
    
    async def open_document(self, uri: str, text: str, version: int = 1) -> None:
        """Notify server that a document was opened."""
        await self._send_notification("textDocument/didOpen", {
            "textDocument": {
                "uri": uri,
                "languageId": self.language_id,
                "version": version,
                "text": text,
            },
        })
    
    async def close_document(self, uri: str) -> None:
        """Notify server that a document was closed."""
        await self._send_notification("textDocument/didClose", {
            "textDocument": {"uri": uri},
        })
    
    async def change_document(
        self,
        uri: str,
        text: str,
        version: int,
        changes: Optional[list[dict]] = None,
    ) -> None:
        """Notify server of document changes."""
        params = {
            "textDocument": {
                "uri": uri,
                "version": version,
            },
        }
        
        if changes:
            params["contentChanges"] = changes
        else:
            params["contentChanges"] = [{"text": text}]
        
        await self._send_notification("textDocument/didChange", params)
    
    async def completion(
        self,
        uri: str,
        line: int,
        character: int,
    ) -> list[CompletionItem]:
        """Get completions at position."""
        result = await self._send_request("textDocument/completion", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character},
        })
        
        if not result:
            return []
        
        items = result.get("items", result) if isinstance(result, dict) else result
        
        completion_items = []
        for item in items:
            completion_items.append(CompletionItem(
                label=item.get("label", ""),
                kind=CompletionItemKind(item["kind"]) if "kind" in item else None,
                detail=item.get("detail"),
                documentation=item.get("documentation"),
                sort_text=item.get("sortText"),
                filter_text=item.get("filterText"),
                text_edit=item.get("textEdit", {}).get("newText") if isinstance(item.get("textEdit"), dict) else None,
            ))
        
        return completion_items
    
    async def hover(
        self,
        uri: str,
        line: int,
        character: int,
    ) -> Optional[str]:
        """Get hover information at position."""
        result = await self._send_request("textDocument/hover", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character},
        })
        
        if not result or not result.get("contents"):
            return None
        
        contents = result["contents"]
        if isinstance(contents, dict):
            return contents.get("value")
        elif isinstance(contents, list):
            return "\n".join(c.get("value", str(c)) for c in contents)
        return str(contents)
    
    async def diagnostics(self, uri: str) -> list[Diagnostic]:
        """Get diagnostics for document."""
        # Diagnostics come via notification, not request
        # This would need proper state management
        return []
    
    async def definition(
        self,
        uri: str,
        line: int,
        character: int,
    ) -> list[dict]:
        """Get definition at position."""
        result = await self._send_request("textDocument/definition", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character},
        })
        
        if not result:
            return []
        
        return result if isinstance(result, list) else [result]
    
    async def references(
        self,
        uri: str,
        line: int,
        character: int,
        include_declaration: bool = True,
    ) -> list[dict]:
        """Get references at position."""
        result = await self._send_request("textDocument/references", {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character},
            "context": {"includeDeclaration": include_declaration},
        })
        
        return result if result else []
    
    async def symbols(self, query: str = "") -> list[SymbolInformation]:
        """Get workspace symbols."""
        result = await self._send_request("workspace/symbol", {"query": query})
        
        if not result:
            return []
        
        symbols = []
        for item in result:
            symbols.append(SymbolInformation(
                name=item.get("name", ""),
                kind=SymbolKind(item.get("kind", 1)),
                location=item.get("location", {}),
                container_name=item.get("containerName"),
            ))
        
        return symbols
    
    def on_notification(self, method: str, handler: Callable) -> None:
        """Register a notification handler."""
        self._notification_handlers[method] = handler


class LSPManager:
    """Manager for multiple LSP servers."""
    
    def __init__(self):
        self._servers: dict[str, LSPClient] = {}
    
    def register_server(
        self,
        language_id: str,
        server_command: list[str],
        root_uri: Optional[str] = None,
    ) -> None:
        """Register a language server."""
        self._servers[language_id] = LSPClient(
            server_command=server_command,
            root_uri=root_uri,
            language_id=language_id,
        )
    
    async def start_server(self, language_id: str) -> bool:
        """Start a language server."""
        server = self._servers.get(language_id)
        if server:
            return await server.start()
        return False
    
    async def stop_server(self, language_id: str) -> None:
        """Stop a language server."""
        server = self._servers.get(language_id)
        if server:
            await server.stop()
    
    async def start_all(self) -> None:
        """Start all registered servers."""
        for server in self._servers.values():
            await server.start()
    
    async def stop_all(self) -> None:
        """Stop all servers."""
        for server in self._servers.values():
            await server.stop()
    
    def get_server(self, language_id: str) -> Optional[LSPClient]:
        """Get a language server."""
        return self._servers.get(language_id)
