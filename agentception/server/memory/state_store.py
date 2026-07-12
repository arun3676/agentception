from __future__ import annotations
import asyncio
from typing import Dict, Any, Set
from datetime import datetime, timedelta

class Memory:
    def __init__(self):
        self.kv: Dict[str, Any] = {}
    def set(self, key: str, value: Any): self.kv[key] = value
    def get(self, key: str, default=None): return self.kv.get(key, default)

class TimelineBus:
    def __init__(self): 
        self.queues: Dict[str, asyncio.Queue] = {}
        self.active_connections: Dict[str, Set[asyncio.Task]] = {}  # Track active SSE connections
        self.connection_times: Dict[str, datetime] = {}  # Track when connections were created
        self.max_connections_per_run = 5  # Limit concurrent connections per run_id
        self.max_connection_age_minutes = 30  # Close connections older than 30 minutes
    
    def ensure(self, run_id: str):
        q = self.queues.get(run_id)
        if not q:
            q = asyncio.Queue(); self.queues[run_id] = q
        return q
    
    def get(self, run_id: str): 
        return self.queues.get(run_id)
    
    def register_connection(self, run_id: str, task: asyncio.Task):
        """Register an active SSE connection"""
        if run_id not in self.active_connections:
            self.active_connections[run_id] = set()
        
        # Check connection limit
        if len(self.active_connections[run_id]) >= self.max_connections_per_run:
            # Close oldest connection
            oldest_task = min(self.active_connections[run_id], key=lambda t: self.connection_times.get(str(id(t)), datetime.now()))
            if not oldest_task.done():
                oldest_task.cancel()
            self.active_connections[run_id].discard(oldest_task)
        
        self.active_connections[run_id].add(task)
        self.connection_times[str(id(task))] = datetime.now()
    
    def unregister_connection(self, run_id: str, task: asyncio.Task):
        """Unregister a closed SSE connection"""
        if run_id in self.active_connections:
            self.active_connections[run_id].discard(task)
            if str(id(task)) in self.connection_times:
                del self.connection_times[str(id(task))]
            # Clean up empty sets
            if not self.active_connections[run_id]:
                del self.active_connections[run_id]
    
    def cleanup_stale_connections(self):
        """Clean up stale connections older than max_connection_age_minutes"""
        now = datetime.now()
        stale_tasks = []
        
        for run_id, tasks in list(self.active_connections.items()):
            for task in list(tasks):
                task_id = str(id(task))
                if task_id in self.connection_times:
                    age = now - self.connection_times[task_id]
                    if age > timedelta(minutes=self.max_connection_age_minutes):
                        stale_tasks.append((run_id, task))
        
        for run_id, task in stale_tasks:
            if not task.done():
                task.cancel()
            self.unregister_connection(run_id, task)
        
        return len(stale_tasks)
