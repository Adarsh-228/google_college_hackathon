import os
import json
import time
import asyncio
from typing import Dict, Any, List, Optional, AsyncGenerator
from api.config import settings


class FirestoreSync:
    """
    Real-time synchronization engine for agent runs.
    Syncs documents to Google Cloud Firestore (runs/{run_id}) and subcollection (events).
    Includes an in-memory fallback store for local development.
    Supports SSE streaming via asyncio queues.
    """

    def __init__(self, project_id: Optional[str] = None):
        self.project_id = project_id or settings.google_cloud_project
        self._db = None
        self._local_runs: Dict[str, Dict[str, Any]] = {}
        self._local_events: Dict[str, List[Dict[str, Any]]] = {}
        # SSE subscriber queues: run_id -> list of asyncio.Queue
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}
        self._init_firestore()

    def _init_firestore(self):
        try:
            from google.cloud import firestore
            if self.project_id:
                self._db = firestore.Client(project=self.project_id)
                print(f"[Firestore] Connected to project: {self.project_id}")
        except Exception as e:
            self._db = None
            print(f"[Firestore] Using local fallback (no GCP credentials): {e}")

    # ── SSE Subscription ──────────────────────────────────────────────

    def subscribe(self, run_id: str) -> asyncio.Queue:
        """Returns an asyncio Queue that receives live events for a run."""
        q: asyncio.Queue = asyncio.Queue()
        if run_id not in self._subscribers:
            self._subscribers[run_id] = []
        self._subscribers[run_id].append(q)
        return q

    def unsubscribe(self, run_id: str, q: asyncio.Queue) -> None:
        """Removes a subscriber queue."""
        if run_id in self._subscribers:
            self._subscribers[run_id] = [
                sub for sub in self._subscribers[run_id] if sub is not q
            ]

    def _notify_subscribers(self, run_id: str, event_data: Dict[str, Any]) -> None:
        """Push event to all SSE subscribers of this run (fire-and-forget)."""
        for q in self._subscribers.get(run_id, []):
            try:
                q.put_nowait(event_data)
            except asyncio.QueueFull:
                pass  # Drop if subscriber is too slow

    # ── CRUD ──────────────────────────────────────────────────────────

    def create_run(self, run_id: str, initial_data: Dict[str, Any]) -> None:
        """Initializes run document state."""
        doc_data = {
            "runId": run_id,
            "status": "RUNNING",
            "currentTurn": 0,
            "createdAt": time.time(),
            **initial_data,
        }
        self._local_runs[run_id] = doc_data
        self._local_events[run_id] = []

        if self._db:
            try:
                self._db.collection(settings.firestore_collection).document(run_id).set(doc_data)
            except Exception as e:
                print(f"[Firestore Warning] Failed to create run document: {e}")

        # Notify SSE subscribers
        self._notify_subscribers(run_id, {
            "type": "RUN_CREATED",
            "data": doc_data,
        })

    def update_run_state(self, run_id: str, update_fields: Dict[str, Any]) -> None:
        """Updates root run document with current metrics, turn, or status."""
        if run_id in self._local_runs:
            self._local_runs[run_id].update(update_fields)

        if self._db:
            try:
                self._db.collection(settings.firestore_collection).document(run_id).update(update_fields)
            except Exception as e:
                print(f"[Firestore Warning] Failed to update run: {e}")

        # Notify SSE subscribers
        self._notify_subscribers(run_id, {
            "type": "RUN_UPDATE",
            "data": update_fields,
        })

    def append_event(self, run_id: str, event_data: Dict[str, Any]) -> None:
        """Appends turn event to local buffer and Firestore subcollection."""
        enriched_event = {
            "eventId": f"evt_{len(self._local_events.get(run_id, [])) + 1}",
            "timestamp": time.time(),
            **event_data,
        }
        if run_id in self._local_events:
            self._local_events[run_id].append(enriched_event)

        if self._db:
            try:
                self._db.collection(settings.firestore_collection).document(run_id).collection("events").add(enriched_event)
            except Exception as e:
                print(f"[Firestore Warning] Failed to append event: {e}")

        # Notify SSE subscribers with the enriched event
        self._notify_subscribers(run_id, enriched_event)

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves run state."""
        if self._db:
            try:
                doc = self._db.collection(settings.firestore_collection).document(run_id).get()
                if doc.exists:
                    return doc.to_dict()
            except Exception:
                pass
        return self._local_runs.get(run_id)

    def get_events(self, run_id: str) -> List[Dict[str, Any]]:
        """Retrieves all events for a run."""
        if self._db:
            try:
                docs = (
                    self._db.collection(settings.firestore_collection)
                    .document(run_id)
                    .collection("events")
                    .order_by("timestamp")
                    .stream()
                )
                return [d.to_dict() for d in docs]
            except Exception:
                pass
        return self._local_events.get(run_id, [])

    def list_runs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Lists all known runs."""
        if self._db:
            try:
                docs = (
                    self._db.collection(settings.firestore_collection)
                    .order_by("createdAt", direction="DESCENDING")
                    .limit(limit)
                    .stream()
                )
                return [d.to_dict() for d in docs]
            except Exception:
                pass
        return sorted(
            self._local_runs.values(),
            key=lambda r: r.get("createdAt", 0),
            reverse=True,
        )[:limit]
