import { useEffect, useRef, useState } from "react";
import AppShell from "../components/AppShell";
import Card from "../components/ui/Card";
import Input from "../components/ui/Input";
import AppSelect from "../components/ui/Select";
import Button from "../components/ui/Button";
import Spinner from "../components/ui/Spinner";
import Skeleton from "../components/ui/Skeleton";
import TopProgress from "../components/TopProgress";

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

type TimelineEvent = { agent: string; message: string; payload?: any };
type AgentResult = {
  agent: string;
  status: "working" | "completed" | "pending";
  data?: any;
  count?: number;
  details?: string[];
  results?: any[];
};

enum Mode { WOW = "wow", REAL = "real" }

export default function Home() {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [results, setResults] = useState<any|null>(null);
  const [saved, setSaved] = useState<any[]>([]);
  const [searchLocation, setSearchLocation] = useState<string>("San Francisco, CA");
  const [busy, setBusy] = useState(false);
  const esRef = useRef<EventSource | null>(null);
  
  // Role and Resume state
  const ROLES = [
    "AI Engineer",
    "Full-Stack Developer", 
    "Java Developer",
    "Data Analyst",
    "Data Engineer",
    "Machine Learning Engineer",
    "DevOps Engineer",
    "Cloud Engineer",
    "Cybersecurity Engineer",
    "Product Manager",
    "Software Architect",
    "Backend Engineer",
    "Frontend Engineer",
    "Mobile Developer",
    "Blockchain Developer"
  ];
  const [role, setRole] = useState("AI Engineer");
  const [resumeToken, setResumeToken] = useState<string|null>(null);
  const [runId, setRunId] = useState<string|null>(null);
  const [minMatch, setMinMatch] = useState(60);
  const [depth, setDepth] = useState<"light"|"standard"|"deep">("standard");
  const [showRagTimeline, setShowRagTimeline] = useState(true);
  const [showWriterTimeline, setShowWriterTimeline] = useState(true);
  const [isTimelineExpanded, setIsTimelineExpanded] = useState(false);

  // Helper functions
  const onEnd = async (rid: string) => {
    const r = await fetch(`${BACKEND}/results/${rid}`); const j = await r.json(); setResults(j);
  };

  const star = async (kind: "event"|"housing"|"place", item: any) => {
    await fetch(`${BACKEND}/save/add`, {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({kind, item})});
    await refreshSaved();
  };

  const refreshSaved = async () => {
    const r = await fetch(`${BACKEND}/save/list`); const j = await r.json(); setSaved(j.items || []);
  };

  useEffect(()=>{ refreshSaved(); },[]);

  // Resume upload handler
  const onResume = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]; 
    if(!f) return;
    
    const fd = new FormData(); 
    fd.append("file", f);
    
    try {
      const r = await fetch(`${BACKEND}/upload/resume`, { method:"POST", body: fd });
      const j = await r.json(); 
      setResumeToken(j.token);
      console.log(`Resume uploaded: ${j.chars} characters`);
    } catch (error) {
      console.error("Resume upload failed:", error);
      alert("Resume upload failed. Please try again.");
    }
  };

  const startSSE = (url:string, ridSetter:(id:string)=>void) => {
    setBusy(true);
    const es = new EventSource(url);
    es.onmessage = (e)=> setEvents(p=>[...p, JSON.parse(e.data)]);
    es.addEventListener("end", ()=>{ es.close(); setBusy(false); });
    return es;
  };
  
  const runExplore = async () => {
    // This function is kept for potential future use but is not currently wired to a UI button.
    const params = {
      location: searchLocation,
      radius_km: 25, // Default radius for company search
      search_events: true, // Assuming events are always searched
      search_housing: true, // Assuming housing is always searched
      search_places: true, // Assuming places are always searched
      places_query: "coworking, coffee, gym", // Default places query
    };
    const body = { params, };
    const r = await fetch(`${BACKEND}/explore`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const j = await r.json();
    esRef.current = startSSE(`${BACKEND}/timeline/${j.run_id}`, setRunId);
  };
  const runRag = async () => {
    if (busy) return;
    
    console.log(`Running RAG for ${role} in ${searchLocation}`);
    setEvents([]);
    setResults(null);
    setRunId(null);
    
    if (esRef.current) { 
      esRef.current.close(); 
      esRef.current = null; 
    }
    
    try {
      const r = await fetch(`${BACKEND}/rag/companies`, {
      method: "POST", 
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ 
          city: searchLocation, 
          role, 
          resumeToken,
          depth
        })
      });
      
      if (!r.ok) {
        throw new Error(`RAG request failed: ${r.status}`);
      }
      
      const { run_id } = await r.json(); 
    setRunId(run_id);
      console.log(`RAG started with run_id: ${run_id}`);
    
      // Stream timeline events
    const es = new EventSource(`${BACKEND}/timeline/${run_id}`);
    es.onmessage = (e) => { 
        const event = JSON.parse(e.data);
        setEvents(p => [...p, event]);
      };
      
    es.addEventListener("end", async () => { 
      es.close(); 
        console.log("RAG workflow completed, fetching results...");
        try {
          const resultResponse = await fetch(`${BACKEND}/results/${run_id}`);
          const j = await resultResponse.json(); 
          setResults(j);
          console.log("RAG results:", j);
        } catch (error) {
          console.error("Failed to fetch RAG results:", error);
        }
      });
      
    esRef.current = es;
      
    } catch (error) {
      console.error("RAG workflow failed:", error);
      alert(`RAG workflow failed: ${error}`);
    }
  };

  // Writer workflow handler (triggered by Writer Agent "Test" button)
  const runWriter = async () => {
    if (!runId) {
      alert("Please run RAG workflow first to discover companies");
      return;
    }
    
    const filtered = (results?.ragdoc?.companies || []).filter((c:any)=> (c.score ?? 0) >= minMatch);
    console.log(`Generating emails for run_id: ${runId}, filtered companies: ${filtered.length}`);
    
    try {
      const r = await fetch(`${BACKEND}/writer/outreach`, {
        method: "POST", 
        headers: {"Content-Type": "application/json"}, 
        body: JSON.stringify({
          run_id: runId, 
          n: Math.min(5, filtered.length || 3)
        })
      });
      
      if (!r.ok) {
        throw new Error(`Writer request failed: ${r.status}`);
      }
      
      const j = await r.json();
      const writerRunId = j.run_id;
      console.log(`Writer timeline started with run_id: ${writerRunId}`);
      
      // Subscribe to Writer timeline
      const writerES = startSSE(`${BACKEND}/timeline/${writerRunId}`, () => {});
      
      writerES.addEventListener("end", async () => {
        console.log("Writer workflow completed, fetching results...");
        writerES.close();
        
        // Fetch final results which should now include emails
        try {
          const resultR = await fetch(`${BACKEND}/results/${runId}`);
          if (resultR.ok) {
            const resultData = await resultR.json();
            setResults(resultData);
            console.log("Updated results with emails:", resultData.emails?.length || 0);
          }
        } catch (err) {
          console.error("Failed to fetch writer results:", err);
        }
      });
      
    } catch (error) {
      console.error("Writer workflow failed:", error);
      alert(`Email generation failed: ${error}`);
    }
  };

  // Email actions
  const openInGmail = (to: string | undefined, subject: string, body: string) => {
    const toEnc = encodeURIComponent(to || "");
    const su = encodeURIComponent(subject);
    const bo = encodeURIComponent(body);
    const url = `https://mail.google.com/mail/?view=cm&fs=1&to=${toEnc}&su=${su}&body=${bo}`;
    window.open(url, "_blank", "noopener,noreferrer");
  };

  const openInOutlook = (to: string | undefined, subject: string, body: string) => {
    const toEnc = encodeURIComponent(to || "");
    const su = encodeURIComponent(subject);
    const bo = encodeURIComponent(body);
    const url = `https://outlook.office.com/mail/deeplink/compose?to=${toEnc}&subject=${su}&body=${bo}`;
    window.open(url, "_blank", "noopener,noreferrer");
  };

  const copyEmail = async (subject: string, body: string) => {
    const text = `Subject: ${subject}\n\n${body}`;
    try {
      await navigator.clipboard.writeText(text);
      alert("Copied email to clipboard ✓");
    } catch {
      const ta = document.createElement("textarea");
      ta.value = text; document.body.appendChild(ta);
      ta.select(); document.execCommand("copy"); document.body.removeChild(ta);
      alert("Copied email to clipboard ✓");
    }
  };


  // Update agent status based on timeline events (Simplified)
  useEffect(() => {
    if (events.length === 0) return;
    // Basic logic to show the last message, can be expanded if needed.
    console.log(events[events.length - 1]);
  }, [events]);





  const testIndividualAgent = async (agentName: string) => {
    if (busy) return;
    
    // Handle RAG agent - run the RAG workflow
    if (agentName === "RAG") {
      return runRag();
    }
    
    // Handle Writer agent - run the Writer workflow  
    if (agentName === "Writer") {
      return runWriter();
    }
    
    // Handle other agents (Scout, Planner) - original test functionality
    // This functionality is now handled by the main "Run RAG" button.
    // If you want to test individual agents, you'd need to implement their specific test logic here.
    // For now, we'll just log a message.
    console.log(`Testing individual agent: ${agentName}`);
  };

  const getAgentIcon = (agent: string) => {
    const icons: Record<string, string> = {
      Scout: "🔍",
      Filter: "⚡", 
      RAG: "🧠",
      Writer: "✍️",
      Planner: "📊",
    };
    return icons[agent] || "🤖";
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "working": return "#f59e0b";
      case "completed": return "#10b981"; 
      case "pending": return "#6b7280";
      default: return "#6b7280";
    }
  };

  return (
    <AppShell>
      <TopProgress active={busy} />
      <Card title="Search">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div className="md:col-span-1"><Input value={searchLocation} onChange={e=>setSearchLocation(e.target.value)} placeholder="City, ST or ZIP" /></div>
          <div><AppSelect value={role} onValueChange={setRole} options={ROLES} /></div>
          <div><AppSelect value={depth} onValueChange={(v) => setDepth(v as "light"|"standard"|"deep")} options={["light","standard","deep"]} /></div>
          <div className="flex items-center gap-2">
            <label className="text-sm text-sub">Resume</label>
            <input type="file" accept="application/pdf" onChange={onResume} className="text-sm" />
            <span className="text-xs text-sub">{resumeToken ? "loaded ✓" : "optional"}</span>
          </div>
          </div>
        <div className="mt-3 flex items-center gap-3">
          <span className="text-xs text-sub">Min match</span>
          <input type="range" min={0} max={100} value={minMatch} onChange={e=>setMinMatch(parseInt(e.target.value))} className="flex-1"/>
          <span className="text-xs">{minMatch}</span>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button onClick={runRag} disabled={busy}>{busy ? <Spinner label="Running..."/> : "Run RAG"}</Button>
          <Button onClick={runWriter} variant="ghost" disabled={busy || !runId}>Generate Emails</Button>
            </div>
      </Card>

      {/* Timeline */}
      <Card title="Timeline">
        <div className="mb-2 flex items-center gap-4 text-xs text-sub">
          <label className="flex items-center gap-1 cursor-pointer">
            <input type="checkbox" checked={showRagTimeline} onChange={e=>setShowRagTimeline(e.target.checked)} />
            RAG
          </label>
          <label className="flex items-center gap-1 cursor-pointer">
            <input type="checkbox" checked={showWriterTimeline} onChange={e=>setShowWriterTimeline(e.target.checked)} />
            Writer
          </label>
          <span className="ml-auto">{events.length} events</span>
          <button 
            onClick={() => setIsTimelineExpanded(!isTimelineExpanded)}
            className="text-xs text-blue-400 hover:text-blue-300 underline"
          >
            {isTimelineExpanded ? 'Hide Details' : 'Show Details'}
          </button>
        </div>
        {isTimelineExpanded && (
          <div className="max-h-[320px] overflow-auto space-y-2 pr-1">
            {events.length === 0 && !busy && <div className="text-sm text-sub">No activity yet. Click "Run RAG" to start.</div>}
            {events.length === 0 && busy && <Spinner className="h-10" />}
            {events
              .filter((ev:any)=> (ev.agent === "RAG" && !showRagTimeline) ? false : (ev.agent === "Writer" && !showWriterTimeline) ? false : true)
              .map((ev:any, i:number)=>(
              <div key={i} className="text-sm text-sub">
                <span className="text-ink">{ev.agent || "System"}:</span> {ev.message}
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Results */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4">
        {busy && !results && (
          <>
            <Skeleton className="h-24" />
            <Skeleton className="h-24" />
          </>
        )}
        {results?.ragdoc && (
          <Card title={`Company Research`}>
            <p className="mt-1 text-sub">Found {results.ragdoc.companies.length} companies for {results.ragdoc.role} in {results.ragdoc.city}</p>
            <div className="grid grid-cols-1 gap-3 mt-4">
              {results.ragdoc.companies
                .filter((c:any)=> (c.score ?? 0) >= minMatch && c.job_posting)
                .map((c:any, i:number) => (
                <div key={i} className="bg-bg border border-white/5 rounded-xl p-3">
                  <div className="flex items-center justify-between">
                    <div className="font-semibold text-ink">{results.ragdoc.role} at {c.name}</div>
                    <a 
                      href={c.job_posting?.url || c.homepage || c.source_url} 
                      target="_blank" 
                      rel="noopener noreferrer" 
                      className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                    >
                      Visit
                    </a>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}

        {results?.emails && (
          <Card title="Generated Emails">
            <p className="mt-1 text-sub">Created {results.emails.length} personalized emails</p>
            <div className="grid grid-cols-1 gap-3 mt-4">
              {results.emails.map((e:any, i:number) => (
                <div key={i} className="bg-bg border border-white/5 rounded-xl p-3">
                  <div className="font-semibold text-ink">{e.company}</div>
                  <div className="mt-1 text-sm text-sub font-semibold">{e.subject}</div>
                  <pre className="mt-2 text-sm text-ink whitespace-pre-wrap font-sans">{e.body}</pre>
                  <div className="mt-3 flex gap-2">
                    <Button onClick={()=>openInGmail(e.mailto, e.subject, e.body)}>Open in Gmail</Button>
                    <Button onClick={()=>openInOutlook(e.mailto, e.subject, e.body)} variant="ghost">Open in Outlook</Button>
                    <Button onClick={()=>copyEmail(e.subject, e.body)} variant="ghost">Copy Email</Button>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        )}

        {saved.length > 0 && (
          <Card title="Saved Items">
            <div className="grid grid-cols-1 gap-3">
              {saved.map((item, i) => (
                <div key={i} className="bg-bg border border-white/5 rounded-xl p-3">
                  <div className="font-semibold">{item.item.title || item.item.name}</div>
                  <p className="mt-1 text-sm text-sub">
                    {item.kind === 'event' && `Event - ${item.item.venue}`}
                    {item.kind === 'housing' && `Housing - ${item.item.neighborhood} - $${item.item.price}`}
                    {item.kind === 'place' && `Place - ${item.item.category}`}
                  </p>
                </div>
              ))}
        </div>
          </Card>
        )}
      </div>
    </AppShell>
  );
}