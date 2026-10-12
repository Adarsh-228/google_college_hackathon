import { initializeApp, getApps, getApp } from "firebase/app";
import { getFirestore, doc, onSnapshot, collection } from "firebase/firestore";

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY || "AIzaSyBg_GgW-J3aiPLO5shw8NFH8NPni-Qe2G4",
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN || "rbux-37584.firebaseapp.com",
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID || "rbux-37584",
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET || "rbux-37584.firebasestorage.app",
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID || "979308776301",
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID || "1:979308776301:web:97a5d3573be09fadc2a864",
};

let db: any = null;

try {
  const app = getApps().length > 0 ? getApp() : initializeApp(firebaseConfig);
  db = getFirestore(app);
} catch (e) {
  console.warn("Firestore client initialization skipped:", e);
}

export function subscribeToRun(runId: string, callback: (data: any) => void) {
  if (!db) return () => {};

  try {
    const runRef = doc(db, "runs", runId);
    return onSnapshot(runRef, (snapshot) => {
      if (snapshot.exists()) {
        callback(snapshot.data());
      }
    }, (err) => {
      console.warn("Firestore snapshot error:", err);
    });
  } catch (err) {
    console.warn("Could not subscribe to run:", err);
    return () => {};
  }
}

export function subscribeToRunEvents(runId: string, callback: (events: any[]) => void) {
  // Primary: Connect to backend SSE endpoint for instant streaming
  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const sseUrl = `${apiBase}/api/runs/${runId}/stream`;

  try {
    if (typeof window !== "undefined" && window.EventSource) {
      const eventSource = new EventSource(sseUrl);
      const eventsList: any[] = [];

      eventSource.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data);
          if (parsed.type === "STREAM_END") {
            eventSource.close();
            return;
          }
          eventsList.push(parsed);
          callback([...eventsList]);
        } catch {
          // Keepalive or unparsed message
        }
      };

      eventSource.onerror = () => {
        eventSource.close();
      };

      return () => {
        eventSource.close();
      };
    }
  } catch (err) {
    console.warn("SSE subscription error, falling back:", err);
  }

  // Fallback to Firestore subcollection if SSE is unavailable
  if (db) {
    try {
      const eventsRef = collection(db, "runs", runId, "events");
      return onSnapshot(eventsRef, (snapshot) => {
        const events = snapshot.docs.map((d) => d.data());
        callback(events);
      }, () => {});
    } catch {
      return () => {};
    }
  }

  return () => {};
}
