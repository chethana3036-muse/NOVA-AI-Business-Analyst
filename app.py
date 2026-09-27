import io, re, json
from collections import Counter
import pandas as pd
import streamlit as st

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None
try:
    from docx import Document
except Exception:
    Document = None
try:
    from google import genai
except Exception:
    genai = None

st.set_page_config(page_title="NOVA | AI Business Analysis Copilot", page_icon="✦", layout="wide")

DEFAULTS = {
    "analysis": None, "stakeholders": [], "requirements": {}, "opportunities": [],
    "documents": [], "rag_results": [], "roadmap": [], "kpis": [], "risks": [],
    "activity": [], "gemini": None, "problem": "", "report": ""
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;600;700&display=swap');
html,body,[class*="css"]{font-family:Inter,sans-serif}
.stApp{background:radial-gradient(circle at 8% 8%,rgba(126,78,255,.22),transparent 28%),radial-gradient(circle at 92% 16%,rgba(0,210,255,.15),transparent 30%),radial-gradient(circle at 70% 90%,rgba(255,54,185,.12),transparent 25%),linear-gradient(135deg,#060914,#0b1020 48%,#06151d);color:#edf2ff}
.block-container{max-width:1450px;padding-top:1.1rem}
section[data-testid="stSidebar"]{background:linear-gradient(180deg,#080c1c,#06131d);border-right:1px solid rgba(255,255,255,.08)}
.hero{padding:34px 38px;border-radius:28px;background:linear-gradient(120deg,rgba(121,65,255,.2),rgba(0,201,255,.12),rgba(255,55,184,.1)),rgba(10,16,32,.8);border:1px solid rgba(255,255,255,.1);box-shadow:0 25px 80px rgba(0,0,0,.35);overflow:hidden}
.badge{display:inline-block;padding:7px 12px;border-radius:999px;background:rgba(120,64,255,.15);border:1px solid rgba(140,110,255,.35);color:#d7ceff;font-size:10px;font-weight:800;letter-spacing:1.5px}
.hero h1{font:700 58px "Space Grotesk";letter-spacing:-2px;margin:10px 0 2px}
.hero p{color:#aeb9d3;max-width:900px;line-height:1.7}
.section{margin-top:22px;padding:25px;border-radius:22px;background:rgba(13,20,38,.75);border:1px solid rgba(255,255,255,.075);box-shadow:0 16px 50px rgba(0,0,0,.18)}
.section h2{font-family:"Space Grotesk";margin:0 0 5px}.caption{color:#8997b5;font-size:13px}
.workflow{display:flex;gap:7px;overflow-x:auto;padding:10px 0}
.step{min-width:116px;padding:12px;border-radius:14px;text-align:center;background:rgba(255,255,255,.035);border:1px solid rgba(255,255,255,.07)}
.step strong{display:block;font-size:10px}.step span{color:#7f8da9;font-size:10px}
.card{padding:18px;border-radius:18px;background:rgba(255,255,255,.035);border:1px solid rgba(255,255,255,.065);height:100%}
.card h4{margin:0 0 8px}.card p,.card li{color:#a6b1c9;font-size:13px;line-height:1.6}
.agent{padding:12px;border-radius:14px;background:rgba(255,255,255,.035);border:1px solid rgba(255,255,255,.07);margin:7px 0}
.agent small{color:#8190ad}
.kpi{padding:13px;border-left:3px solid #6d4cff;background:rgba(255,255,255,.035);border-radius:9px;margin:7px 0;color:#b9c3d8;font-size:13px}
.stButton>button{border-radius:12px;border:1px solid rgba(255,255,255,.1);background:linear-gradient(90deg,rgba(112,55,255,.88),rgba(0,183,232,.78));color:white;font-weight:700}
</style>
""", unsafe_allow_html=True)

def log(msg):
    st.session_state.activity.insert(0, msg)
    st.session_state.activity = st.session_state.activity[:15]

def toks(s):
    return re.findall(r"[a-zA-Z0-9]{2,}", s.lower())

def make_chunks(text, size=180, overlap=30):
    words = text.split()
    out, start = [], 0
    while start < len(words):
        end = min(len(words), start + size)
        out.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = max(end - overlap, start + 1)
    return [x for x in out if x.strip()]

def overlap(q, t):
    a, b = Counter(toks(q)), Counter(toks(t))
    return round(sum(min(a[x], b[x]) for x in a) / max(1, sum(a.values())), 3)

def read_file(f):
    data, name = f.getvalue(), f.name.lower()
    if name.endswith(".txt"):
        return data.decode("utf-8", "ignore")
    if name.endswith(".csv"):
        return pd.read_csv(io.BytesIO(data)).astype(str).to_csv(index=False)
    if name.endswith(".pdf") and PdfReader:
        return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages)
    if name.endswith(".docx") and Document:
        return "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
    return ""

def live_ai(prompt):
    client = st.session_state.gemini
    if not client:
        return None
    try:
        return client.models.generate_content(model="gemini-2.5-flash", contents=prompt).text
    except Exception:
        st.warning("Live AI was unavailable, so NOVA continued in Demo Mode.")
        return None

def analyze(problem, objective, constraints, dept):
    p = problem.lower()
    if any(x in p for x in ["support","ticket","customer","service"]):
        typ="Customer Operations / Service Efficiency"
        roots=["Knowledge is fragmented across documents and systems.","Employees spend time searching instead of resolving requests.","Manual routing and repetitive triage create queue delays."]
        opp=["RAG Knowledge Assistant","AI Ticket Classification","Response Drafting Copilot","Agentic Escalation Workflow"]
    elif any(x in p for x in ["invoice","finance","payment","expense"]):
        typ="Finance Process Automation"
        roots=["Manual data entry creates delays.","Validation rules are distributed across teams.","Exception handling consumes specialist time."]
        opp=["Document Intelligence","Exception Handling Agent","Policy RAG","Automated Reconciliation"]
    elif any(x in p for x in ["hr","employee","recruit","hiring"]):
        typ="HR / Workforce Operations"
        roots=["Policy information is distributed across sources.","Employees repeat common policy questions.","Manual workflows increase response time."]
        opp=["HR Policy RAG","Employee Self-Service Agent","Workflow Automation","People Analytics"]
    else:
        typ="Business Process / Operational Efficiency"
        roots=["The current workflow contains manual handoffs.","Information is distributed across multiple sources.","Decision-making depends on repetitive analysis."]
        opp=["Knowledge Assistant","Process Copilot","Workflow Automation","Business Analytics"]
    return {
        "type": typ,
        "summary": f"The challenge appears to be an operational problem affecting {dept}. NOVA recommends validating the current process, identifying root causes, and selecting technology where it creates measurable value.",
        "objective": objective or "Improve process efficiency, visibility and user experience.",
        "roots": roots,
        "unknowns": ["What is the current baseline performance?","Which systems contain the required data?","Who owns and approves the process?","What privacy, security or compliance constraints apply?"],
        "assumptions": ["Authorized business data is available.","Human owners remain accountable for high-impact decisions.","The solution will be piloted before scale."],
        "constraints": [x for x in constraints.splitlines() if x.strip()] or ["Budget, timeline and implementation capacity require validation."],
        "opportunities": opp
    }

def stakeholders():
    return [
        {"Stakeholder":"Business Owner","Role":"Decision maker","Influence":"High","Interest":"High","Concern":"Value / ROI"},
        {"Stakeholder":"Process Owner","Role":"Operational owner","Influence":"High","Interest":"High","Concern":"Process performance"},
        {"Stakeholder":"End Users","Role":"Primary users","Influence":"Medium","Interest":"High","Concern":"Ease of use / workload"},
        {"Stakeholder":"IT / Architecture","Role":"Technical owner","Influence":"High","Interest":"Medium","Concern":"Integration / security"},
        {"Stakeholder":"Data / AI Team","Role":"AI enablement","Influence":"Medium","Interest":"Medium","Concern":"Data quality / evaluation"},
        {"Stakeholder":"Risk / Compliance","Role":"Governance","Influence":"High","Interest":"Medium","Concern":"Privacy / risk"}
    ]

def requirements():
    return {
        "functional":[
            "FR-001 — Users can submit a structured business request.",
            "FR-002 — Authorized users can retrieve relevant approved knowledge.",
            "FR-003 — Recommendations include rationale and supporting evidence where available.",
            "FR-004 — Important workflow actions are auditable.",
            "FR-005 — Human reviewers can approve, reject or revise AI outputs."
        ],
        "nonfunctional":[
            "NFR-001 — Access follows role-based authorization.",
            "NFR-002 — Sensitive data follows organizational policy.",
            "NFR-003 — AI outputs expose uncertainty and evidence where available.",
            "NFR-004 — The system supports logging and evaluation.",
            "NFR-005 — The system degrades gracefully if retrieval is unavailable."
        ],
        "stories":[
            "As a business analyst, I want ambiguous problems converted into structured requirements so stakeholders share a baseline.",
            "As an employee, I want grounded answers from approved documents so I can avoid searching multiple systems.",
            "As a manager, I want measurable KPIs so I can evaluate business value."
        ],
        "acceptance":[
            "Given an approved knowledge source, when a user asks a supported question, relevant content and its source are shown.",
            "Given a high-risk recommendation, human review is required before action.",
            "Given a business problem, analysis produces traceable requirements, assumptions and open questions."
        ]
    }

def opportunities(names):
    values=[92,84,78,69]; efforts=["Medium","Medium","Low-Medium","High"]; risks=["Medium","Medium","Low","High"]
    tech=["LLM + RAG","LLM / classification","LLM + workflow","Agentic AI"]
    return [{"Opportunity":n,"Business Value":values[i],"Effort":efforts[i],"Risk":risks[i],"Technology":tech[i],"Priority":"P1" if values[i]>=84 else "P2"} for i,n in enumerate(names)]

def roadmap():
    return [
        {"Phase":"1 — Discover","Timeline":"Weeks 1–2","Outputs":"Stakeholders, current-state map, baseline KPIs, requirements"},
        {"Phase":"2 — Prototype","Timeline":"Weeks 3–5","Outputs":"AI/RAG prototype, workflow, evaluation set"},
        {"Phase":"3 — Pilot","Timeline":"Weeks 6–8","Outputs":"Limited users, feedback, quality and risk evaluation"},
        {"Phase":"4 — Scale","Timeline":"Week 9+","Outputs":"Integrations, monitoring, governance, rollout"}
    ]

def kpis():
    return [
        {"Category":"Operational","KPI":"Average resolution time","Direction":"Decrease"},
        {"Category":"Operational","KPI":"Backlog volume","Direction":"Decrease"},
        {"Category":"User","KPI":"Employee satisfaction","Direction":"Increase"},
        {"Category":"AI","KPI":"Answer relevance","Direction":"Increase"},
        {"Category":"AI","KPI":"Citation coverage","Direction":"Increase"},
        {"Category":"AI","KPI":"Human override rate","Direction":"Monitor"},
        {"Category":"Risk","KPI":"Ungrounded answer rate","Direction":"Decrease"},
        {"Category":"Business","KPI":"Cost per case","Direction":"Decrease"}
    ]

def risks():
    return [
        {"Risk":"Hallucination","Severity":"High","Control":"RAG grounding, citations, evaluation and human review"},
        {"Risk":"Privacy","Severity":"High","Control":"RBAC, data minimization and approved sources"},
        {"Risk":"Bias","Severity":"Medium","Control":"Representative evaluation and review"},
        {"Risk":"Security","Severity":"High","Control":"Least privilege, secrets management and audit logs"},
        {"Risk":"Adoption","Severity":"Medium","Control":"Pilot, training and feedback loop"}
    ]

def build_report():
    a=st.session_state.analysis or {}
    lines=["# NOVA — Executive Business Analysis Report","","## Executive Summary",a.get("summary","Not available."),"","## Business Objective",a.get("objective","Not specified."),"","## Root Causes"]
    lines += [f"- {x}" for x in a.get("roots",[])]
    lines += ["","## Functional Requirements"]+[f"- {x}" for x in st.session_state.requirements.get("functional",[])]
    lines += ["","## AI Opportunities"]+[f"- {x['Opportunity']} — Value {x['Business Value']}/100 | Effort {x['Effort']} | Risk {x['Risk']}" for x in st.session_state.opportunities]
    lines += ["","## Implementation Roadmap"]+[f"- {x['Phase']} ({x['Timeline']}): {x['Outputs']}" for x in st.session_state.roadmap]
    lines += ["","## Responsible AI"]+[f"- {x['Risk']} ({x['Severity']}): {x['Control']}" for x in st.session_state.risks]
    lines += ["","## Important note","Scores, targets and recommendations are illustrative until validated against real organizational data."]
    return "\n".join(lines)

# Sidebar
with st.sidebar:
    st.markdown("## ✦ NOVA")
    st.caption("AI BUSINESS ANALYSIS & SOLUTION DESIGN COPILOT")
    st.divider()
    key=st.text_input("Gemini API key (optional)", type="password")
    if key and genai:
        try:
            st.session_state.gemini=genai.Client(api_key=key)
            st.success("Live Gemini connected")
        except Exception:
            st.session_state.gemini=None
            st.error("Could not connect.")
    else:
        st.session_state.gemini=None
        st.info("Demo Engine Active")
    st.divider()
    st.markdown("### Workflow")
    for x in ["01 Discover","02 Stakeholders","03 Root Cause","04 Requirements","05 AI Opportunities","06 RAG","07 Architecture","08 Prioritize","09 Roadmap","10 KPIs & Risk","11 Executive Report"]:
        st.caption(x)
    st.divider()
    st.markdown("### Agent Network")
    for x in ["🔎 Discovery Agent","👥 Stakeholder Agent","🧠 BA / Requirements Agent","📚 RAG Knowledge Agent","🏗️ Solution Agent","📊 Analytics Agent","🛡️ Risk Agent","🗺️ Roadmap Agent"]:
        st.markdown(f"<div class='agent'><b>{x}</b><br><small>Ready</small></div>",unsafe_allow_html=True)
    if st.button("Reset Workspace",use_container_width=True):
        for k,v in DEFAULTS.items(): st.session_state[k]=v
        st.rerun()

# Header
st.markdown("""<div class="hero"><span class="badge">AI • GENAI • RAG • AGENTIC WORKFLOWS • BUSINESS ANALYSIS</span>
<h1>NOVA</h1><p><b>AI Business Analysis & Solution Design Copilot</b><br>
Transform ambiguous business problems into structured requirements, grounded knowledge,
AI opportunities, solution architecture, prioritized roadmaps and measurable business outcomes.</p></div>""",unsafe_allow_html=True)

steps=["DISCOVER","STAKEHOLDERS","ROOT CAUSE","REQUIREMENTS","AI OPPORTUNITIES","RAG","ARCHITECTURE","PRIORITIZE","ROADMAP","MEASURE"]
st.markdown('<div class="workflow">'+''.join(f"<div class='step'><strong>{i+1:02d} {x}</strong><span>NOVA stage</span></div>" for i,x in enumerate(steps))+'</div>',unsafe_allow_html=True)

# Dashboard
st.markdown('<div class="section"><h2>◈ Command Center</h2><div class="caption">Live overview of the current business-analysis workspace.</div></div>',unsafe_allow_html=True)
a1,a2,a3,a4,a5=st.columns(5)
a1.metric("Analysis","READY" if st.session_state.analysis else "NOT STARTED")
a2.metric("Requirements",len(st.session_state.requirements.get("functional",[])))
a3.metric("AI Opportunities",len(st.session_state.opportunities))
a4.metric("Knowledge Sources",len(st.session_state.documents))
a5.metric("Risks",len(st.session_state.risks))

# Discovery
st.markdown('<div class="section"><h2>01 · Business Discovery</h2><div class="caption">Capture context before selecting a technology solution.</div></div>',unsafe_allow_html=True)
c1,c2=st.columns([1.6,1])
with c1:
    problem=st.text_area("Business problem",value=st.session_state.problem,height=145,placeholder="Example: Our customer support team takes too long to resolve tickets because employees spend too much time searching for information.")
    st.session_state.problem=problem
with c2:
    dept=st.selectbox("Business function",["Customer Support","Finance","HR","Sales","Operations","IT","Supply Chain","Other"])
    objective=st.text_area("Business objective",height=75,placeholder="What should improve?")
    constraints=st.text_area("Constraints",height=75,placeholder="Budget, security, compliance, timeline, data...")

if st.button("✨ Run Full Business Analysis",use_container_width=True):
    if not problem.strip():
        st.error("Enter a business problem first.")
    else:
        with st.spinner("NOVA is orchestrating the analysis..."):
            result=analyze(problem,objective,constraints,dept)
            live=live_ai(f"""You are a senior enterprise business analyst. Analyze this problem: {problem}
Function: {dept}. Objective: {objective}. Constraints: {constraints}.
Return concise JSON with keys summary,type,roots,unknowns,assumptions. Do not invent metrics.""")
            if live:
                try:
                    parsed=json.loads(re.sub(r"```json|```","",live).strip())
                    for k in ["summary","type","roots","unknowns","assumptions"]:
                        if k in parsed: result[k]=parsed[k]
                except Exception:
                    pass
            st.session_state.analysis=result
            st.session_state.stakeholders=stakeholders()
            st.session_state.requirements=requirements()
            st.session_state.opportunities=opportunities(result["opportunities"])
            st.session_state.roadmap=roadmap()
            st.session_state.kpis=kpis()
            st.session_state.risks=risks()
            log("Discovery Agent completed analysis")
            log("Stakeholder Agent mapped key roles")
            log("Requirements Agent generated requirements")
            log("Solution Agent identified AI opportunities")
        st.success("Initial analysis pipeline completed.")

if st.session_state.analysis:
    a=st.session_state.analysis

    st.markdown('<div class="section"><h2>Business Intelligence Brief</h2><div class="caption">Structured interpretation and validation questions.</div></div>',unsafe_allow_html=True)
    q1,q2,q3=st.columns(3)
    q1.markdown(f"<div class='card'><h4>Problem Type</h4><p>{a['type']}</p></div>",unsafe_allow_html=True)
    q2.markdown(f"<div class='card'><h4>Objective</h4><p>{a['objective']}</p></div>",unsafe_allow_html=True)
    q3.markdown(f"<div class='card'><h4>Summary</h4><p>{a['summary']}</p></div>",unsafe_allow_html=True)

    b1,b2,b3=st.columns(3)
    with b1:
        st.markdown("#### 🧠 Root Causes")
        for x in a["roots"]: st.write("•",x)
    with b2:
        st.markdown("#### ❓ Discovery Questions")
        for x in a["unknowns"]: st.write("•",x)
    with b3:
        st.markdown("#### ⚠️ Assumptions / Constraints")
        for x in a["assumptions"]+a["constraints"]: st.write("•",x)

    st.markdown('<div class="section"><h2>02 · Stakeholder Intelligence</h2><div class="caption">Who is affected, who decides, and what each stakeholder cares about.</div></div>',unsafe_allow_html=True)
    st.dataframe(pd.DataFrame(st.session_state.stakeholders),use_container_width=True,hide_index=True)
    st.info("BA action: validate influence, decision rights, pain points and success criteria through interviews or workshops.")

    st.markdown('<div class="section"><h2>03 · Root Cause Analysis</h2><div class="caption">A simple causal chain to validate with a 5 Whys session.</div></div>',unsafe_allow_html=True)
    st.code("BUSINESS SYMPTOM\n      ↓\n"+a["roots"][0]+"\n      ↓\n"+a["roots"][1]+"\n      ↓\n"+a["roots"][2]+"\n      ↓\nINTERVENTION OPPORTUNITY\n      ↓\nPILOT → MEASURE → VALIDATE → SCALE")

    st.markdown('<div class="section"><h2>04 · Requirements Studio</h2><div class="caption">Functional requirements, NFRs, user stories and acceptance criteria.</div></div>',unsafe_allow_html=True)
    r1,r2=st.columns(2)
    with r1:
        st.markdown("#### Functional Requirements")
        for x in st.session_state.requirements["functional"]: st.markdown(f"<div class='kpi'>{x}</div>",unsafe_allow_html=True)
    with r2:
        st.markdown("#### Non-Functional Requirements")
        for x in st.session_state.requirements["nonfunctional"]: st.markdown(f"<div class='kpi'>{x}</div>",unsafe_allow_html=True)
    r3,r4=st.columns(2)
    with r3:
        st.markdown("#### User Stories")
        for x in st.session_state.requirements["stories"]: st.write("•",x)
    with r4:
        st.markdown("#### Acceptance Criteria")
        for x in st.session_state.requirements["acceptance"]: st.write("•",x)

    st.markdown('<div class="section"><h2>05 · AI Opportunity Discovery</h2><div class="caption">Identify where AI creates value instead of forcing AI into every step.</div></div>',unsafe_allow_html=True)
    oppdf=pd.DataFrame(st.session_state.opportunities)
    st.dataframe(oppdf,use_container_width=True,hide_index=True)
    if not oppdf.empty: st.bar_chart(oppdf.set_index("Opportunity")["Business Value"])

    st.markdown('<div class="section"><h2>06 · Enterprise RAG Knowledge Center</h2><div class="caption">Upload approved business knowledge and retrieve relevant evidence.</div></div>',unsafe_allow_html=True)
    files=st.file_uploader("Upload knowledge sources",type=["pdf","txt","csv","docx"],accept_multiple_files=True)
    if files:
        st.session_state.documents=[{"name":f.name,"chunks":make_chunks(read_file(f))} for f in files]
        log(f"RAG Agent indexed {len(files)} source(s)")
    if st.session_state.documents:
        st.write("Indexed sources:",", ".join(d["name"] for d in st.session_state.documents))
        question=st.text_input("Ask the knowledge base",placeholder="Example: What is the escalation policy?")
        if st.button("🔎 Retrieve Grounded Evidence"):
            results=[]
            for d in st.session_state.documents:
                for i,ch in enumerate(d["chunks"]):
                    score=overlap(question,ch)
                    if score>0: results.append({"Source":d["name"],"Chunk":i+1,"Relevance":score,"Evidence":ch[:1000]})
            results.sort(key=lambda x:x["Relevance"],reverse=True)
            st.session_state.rag_results=results[:6]
            log("RAG Agent retrieved top evidence")
        for r in st.session_state.rag_results:
            st.markdown(f"<div class='card'><h4>📌 {r['Source']} · Chunk {r['Chunk']} · Relevance {r['Relevance']}</h4><p>{r['Evidence']}</p></div>",unsafe_allow_html=True)
    else:
        st.info("Upload PDF, DOCX, TXT or CSV files to activate the knowledge center.")

    st.markdown('<div class="section"><h2>07 · Solution Architecture</h2><div class="caption">A high-level enterprise pattern connecting business analysis, agents and grounded knowledge.</div></div>',unsafe_allow_html=True)
    st.code("""
BUSINESS USERS
  BA • Manager • Employee • Process Owner
                 │
                 ▼
        ┌───────────────────┐
        │  NOVA EXPERIENCE   │
        │ BA + RAG + Reports │
        └─────────┬─────────┘
                  ▼
          AI ORCHESTRATOR
       ┌──────────┼──────────┐
       ▼          ▼          ▼
    BA AGENT   RAG AGENT  ANALYTICS
       │          │          │
       └──────────┼──────────┘
                  ▼
            SOLUTION AGENT
                  ▼
             RISK AGENT
                  ▼
            ROADMAP AGENT
                  ▼
           HUMAN APPROVAL
                  ▼
             IMPLEMENTATION
""",language="text")

    z1,z2,z3=st.columns(3)
    z1.markdown("<div class='card'><h4>🔐 Security</h4><p>RBAC, least privilege, approved sources, secrets management and audit logs.</p></div>",unsafe_allow_html=True)
    z2.markdown("<div class='card'><h4>📚 Grounding</h4><p>Retrieval and citations support enterprise answers; generated text is not automatically authoritative.</p></div>",unsafe_allow_html=True)
    z3.markdown("<div class='card'><h4>👤 Human Oversight</h4><p>High-impact decisions remain subject to business ownership and human approval.</p></div>",unsafe_allow_html=True)

    st.markdown('<div class="section"><h2>08 · Prioritization Matrix</h2><div class="caption">Compare business value, effort and risk to decide what to pilot first.</div></div>',unsafe_allow_html=True)
    st.dataframe(oppdf[["Opportunity","Business Value","Effort","Risk","Priority"]],use_container_width=True,hide_index=True)
    st.caption("Priority is an illustrative portfolio score, not a real enterprise investment decision.")

    st.markdown('<div class="section"><h2>09 · Implementation Roadmap</h2><div class="caption">Move from discovery to controlled enterprise rollout.</div></div>',unsafe_allow_html=True)
    st.dataframe(pd.DataFrame(st.session_state.roadmap),use_container_width=True,hide_index=True)

    st.markdown('<div class="section"><h2>10 · KPI & Business Impact Center</h2><div class="caption">Suggested measures — not claimed project results.</div></div>',unsafe_allow_html=True)
    st.dataframe(pd.DataFrame(st.session_state.kpis),use_container_width=True,hide_index=True)
    st.warning("NOVA does not invent achieved impact. KPI targets should use real organizational baselines.")

    st.markdown('<div class="section"><h2>11 · Responsible AI & Risk</h2><div class="caption">Governance checks for enterprise AI adoption.</div></div>',unsafe_allow_html=True)
    st.dataframe(pd.DataFrame(st.session_state.risks),use_container_width=True,hide_index=True)

    st.markdown('<div class="section"><h2>12 · Agent Activity</h2><div class="caption">Transparent view of the agentic workflow.</div></div>',unsafe_allow_html=True)
    if st.session_state.activity:
        for x in st.session_state.activity: st.markdown("• "+x)
    else: st.caption("Run the analysis to populate agent activity.")

    st.markdown('<div class="section"><h2>13 · Executive Report</h2><div class="caption">Create a concise handoff document for a manager or project sponsor.</div></div>',unsafe_allow_html=True)
    if st.button("📄 Generate Executive Report",use_container_width=True):
        st.session_state.report=build_report()
        log("Roadmap Agent generated executive report")
    if st.session_state.report:
        st.download_button("⬇️ Download Report (.md)",st.session_state.report,file_name="NOVA_Executive_Report.md",mime="text/markdown",use_container_width=True)
        with st.expander("Preview report"):
            st.markdown(st.session_state.report)
st.markdown("""
<div class="section"><h2>14 · Executive Operating Model</h2><div class="caption">How NOVA fits into a real enterprise transformation lifecycle — from business signal to measurable outcome.</div></div>
""", unsafe_allow_html=True)

eo1,eo2,eo3,eo4=st.columns(4)
for col,title,body in [
(eo1,"01 · Sense","Capture business pain, customer friction, operational signals and strategic objectives.<br><br>• Problem framing<br>• Stakeholder interviews<br>• Evidence collection"),
(eo2,"02 · Understand","Convert ambiguity into process maps, requirements, root causes and measurable success criteria.<br><br>• 5 Whys<br>• SIPOC<br>• User stories"),
(eo3,"03 · Design","Evaluate automation, analytics, GenAI, RAG and agentic opportunities against business value.<br><br>• Use-case scoring<br>• Architecture<br>• Risk assessment"),
(eo4,"04 · Deliver","Pilot, evaluate, govern and scale with human ownership and outcome measurement.<br><br>• Roadmap<br>• UAT<br>• KPI monitoring")]:
    col.markdown(f"<div class='card'><h4>{title}</h4><p>{body}</p></div>",unsafe_allow_html=True)

st.markdown("""<div class="section"><h2>15 · Current-State Process Intelligence</h2><div class="caption">A BA-style view of the process before technology is introduced.</div></div>""",unsafe_allow_html=True)
process_steps=[("01","REQUEST","Customer / employee submits request","Input"),("02","TRIAGE","Agent reads and categorizes request","Manual"),("03","SEARCH","Employee searches policies / systems","High friction"),("04","DECIDE","Employee determines response or escalation","Judgement"),("05","RESPOND","Response is prepared and sent","Manual"),("06","ESCALATE","Complex cases move to another team","Handoff"),("07","CLOSE","Case is resolved and logged","Output")]
for i in range(0,len(process_steps),4):
    cols=st.columns(4)
    for col,(n,title,desc,tag) in zip(cols,process_steps[i:i+4]):
        col.markdown(f"<div class='card'><div style='font-size:11px;color:#8795b2'>{n} · {tag.upper()}</div><h4>{title}</h4><p>{desc}</p></div>",unsafe_allow_html=True)
st.markdown("<div class='card' style='margin-top:12px'><h4>⚡ Opportunity hotspots</h4><p>Search-heavy steps are candidates for RAG. Repetitive triage is a candidate for classification. Repetitive drafting is a candidate for GenAI assistance. Multi-step routing can become an agentic workflow only after permissions, controls and evaluation are defined.</p></div>",unsafe_allow_html=True)

st.markdown("""<div class="section"><h2>16 · SIPOC / Business Process Scope</h2><div class="caption">A compact process-scoping artifact for a discovery workshop.</div></div>""",unsafe_allow_html=True)
sipoc=pd.DataFrame([["Suppliers","Customer, employee, process owner, policy team"],["Inputs","Request, customer context, policies, product data, case history"],["Process","Receive → classify → retrieve → decide → respond → escalate → close"],["Outputs","Resolved request, response, case record, escalation"],["Customers","End customer, employee, manager, business owner"]],columns=["SIPOC Element","Working Definition"])
st.dataframe(sipoc,use_container_width=True,hide_index=True)

st.markdown("""<div class="section"><h2>17 · Customer / Employee Journey Map</h2><div class="caption">Where users experience friction — and where a solution should create value.</div></div>""",unsafe_allow_html=True)
journey=pd.DataFrame([["Discover","User needs help","Finds support channel","Medium","Clear entry point"],["Submit","Provides details","Repeats information","High","Structured intake"],["Wait","Expects resolution","Waits for response","High","Status visibility"],["Resolve","Receives answer","May receive inconsistent answer","High","Grounded response"],["Escalate","Complex issue","Multiple handoffs","Medium","Controlled routing"],["Close","Issue resolved","Little feedback loop","Low","Outcome + feedback"]],columns=["Stage","User Goal","Observed Friction","Friction","Design Opportunity"])
st.dataframe(journey,use_container_width=True,hide_index=True)

st.markdown("""<div class="section"><h2>18 · AI / Automation Opportunity Catalog</h2><div class="caption">A portfolio catalogue showing when to use automation, analytics, GenAI, RAG or agents.</div></div>""",unsafe_allow_html=True)
catalog=pd.DataFrame([["Rule Automation","Deterministic repetitive tasks","Low","Workflow / RPA","Start here when rules are stable"],["Predictive Analytics","Forecasting / prioritization","Medium","ML / statistics","Needs historical data"],["GenAI Copilot","Drafting / summarization / ideation","Medium","LLM","Human review recommended"],["RAG Assistant","Answers over approved enterprise knowledge","Medium","LLM + retrieval","Needs source governance"],["AI Classification","Categorize requests / documents","Medium","LLM / ML","Evaluate accuracy by class"],["Agentic Workflow","Multi-step tasks using tools","High","LLM + tools + orchestration","Needs permissions and guardrails"]],columns=["Pattern","Best Fit","Complexity","Typical Stack","BA Decision Rule"])
st.dataframe(catalog,use_container_width=True,hide_index=True)

st.markdown("""<div class="section"><h2>19 · Agentic AI Control Plane</h2><div class="caption">Agents act as role-based collaborators rather than one unrestricted autonomous model.</div></div>""",unsafe_allow_html=True)
agents=[("Discovery Agent","Turns a vague problem into structured context","problem + objectives","problem brief"),("Requirements Agent","Drafts requirements and acceptance criteria","process + stakeholder needs","requirements backlog"),("Knowledge Agent","Retrieves approved evidence","question + indexed sources","ranked evidence"),("Solution Agent","Maps pain points to technology patterns","requirements + constraints","solution options"),("Analytics Agent","Defines KPIs and measurement logic","process + outcomes","KPI framework"),("Risk Agent","Identifies AI, privacy and operational risks","proposed solution","controls"),("Roadmap Agent","Sequences pilot and scale activities","priorities + dependencies","delivery roadmap")]
for name,purpose,inputs,output in agents:
    st.markdown(f"<div class='agent'><b>✦ {name}</b><br><small>{purpose}</small><br><span style='color:#6f7d99'>↳ {inputs} → {output}</span></div>",unsafe_allow_html=True)
st.markdown("<div class='card'><h4>🔒 Agent boundary principle</h4><p>Agents recommend, retrieve, draft and orchestrate. Business owners authorize high-impact actions. Tool access should be limited by role, action and data sensitivity. Consequential actions should be observable and auditable.</p></div>",unsafe_allow_html=True)

st.markdown("""<div class="section"><h2>20 · RAG Pipeline Blueprint</h2><div class="caption">The enterprise knowledge lifecycle behind NOVA's retrieval layer.</div></div>""",unsafe_allow_html=True)
st.code("""APPROVED DOCUMENTS\n       │\n       ▼\nINGESTION → PARSING → CHUNKING → METADATA\n       │\n       ▼\nEMBEDDING / INDEX\n       │\n       ▼\nUSER QUESTION\n       │\n       ▼\nQUERY UNDERSTANDING\n       │\n       ▼\nTOP-K RETRIEVAL\n       │\n       ├── relevance check\n       ├── source permission check\n       └── freshness check\n       │\n       ▼\nLLM GENERATION\n       │\n       ▼\nANSWER + EVIDENCE + UNCERTAINTY\n       │\n       ▼\nHUMAN / USER FEEDBACK""",language="text")
r1,r2,r3=st.columns(3)
r1.markdown("<div class='card'><h4>Retrieval quality</h4><p>Precision, recall, relevance, source coverage and failed-query analysis.</p></div>",unsafe_allow_html=True)
r2.markdown("<div class='card'><h4>Generation quality</h4><p>Faithfulness, completeness, clarity, citation coverage and groundedness.</p></div>",unsafe_allow_html=True)
r3.markdown("<div class='card'><h4>Knowledge governance</h4><p>Ownership, freshness, access control, versioning and document approval status.</p></div>",unsafe_allow_html=True)

st.markdown("""<div class="section"><h2>21 · Data & AI Lifecycle</h2><div class="caption">From business data to monitored AI capability.</div></div>""",unsafe_allow_html=True)
lifecycle=pd.DataFrame([["1. Discover","Identify data owners and business purpose","Business Analyst"],["2. Assess","Check quality, sensitivity and availability","Data / Risk"],["3. Prepare","Clean, transform, classify and govern","Data Team"],["4. Build","Create retrieval, prompts, models or workflows","AI / Engineering"],["5. Evaluate","Test quality, safety, bias and failure modes","AI / QA"],["6. Pilot","Release to a controlled user group","Product Owner"],["7. Monitor","Track outcomes, drift, incidents and feedback","Operations"],["8. Improve","Iterate requirements and solution","Cross-functional team"]],columns=["Stage","Key Activity","Primary Owner"])
st.dataframe(lifecycle,use_container_width=True,hide_index=True)

st.markdown("""<div class="section"><h2>22 · Requirements Backlog & Prioritization</h2><div class="caption">A realistic product backlog for an enterprise AI initiative.</div></div>""",unsafe_allow_html=True)
backlog=pd.DataFrame([["REQ-001","Structured intake","User can describe a business issue","Must","P1","Discovery"],["REQ-002","Source-aware answers","Assistant shows supporting evidence","Must","P1","RAG"],["REQ-003","Role-based access","Users see only permitted content","Must","P1","Security"],["REQ-004","Human approval","High-impact actions require approval","Must","P1","Governance"],["REQ-005","Feedback loop","Users can rate or correct answers","Should","P2","Analytics"],["REQ-006","Conversation memory","Retain useful session context","Should","P2","Experience"],["REQ-007","Workflow integration","Create/update cases through approved tools","Could","P3","Agents"],["REQ-008","Executive analytics","Monitor adoption and business outcomes","Should","P2","Analytics"]],columns=["ID","Capability","Requirement","MoSCoW","Priority","Workstream"])
st.dataframe(backlog,use_container_width=True,hide_index=True)

st.markdown("""<div class="section"><h2>23 · UAT & AI Evaluation Lab</h2><div class="caption">A professional BA/AI project needs tests, not just a demo.</div></div>""",unsafe_allow_html=True)
tests=pd.DataFrame([["UAT-01","Valid support question","Approved policy exists","Correct grounded answer","Functional"],["UAT-02","Unknown question","No source supports answer","System states uncertainty","Safety"],["UAT-03","Restricted document","User lacks permission","Document is not revealed","Security"],["UAT-04","Ambiguous request","Multiple interpretations","System asks clarification","UX"],["UAT-05","Conflicting documents","Two source versions","System flags conflict","RAG"],["UAT-06","High-impact recommendation","Decision affects customer","Human approval is required","Governance"]],columns=["Test ID","Scenario","Condition","Expected Result","Type"])
st.dataframe(tests,use_container_width=True,hide_index=True)
e1,e2,e3,e4=st.columns(4)
e1.metric("Evaluation Set","6+ scenarios");e2.metric("Grounding","Evidence required");e3.metric("Safety","Human review");e4.metric("Security","RBAC check")

st.markdown("""<div class="section"><h2>24 · Business Value Case</h2><div class="caption">A decision framework for a sponsor — without inventing financial results.</div></div>""",unsafe_allow_html=True)
value=pd.DataFrame([["Efficiency","Time spent searching","Reduce","Baseline required"],["Quality","Response consistency","Increase","Quality sampling required"],["Experience","Employee effort","Reduce","Survey / task study"],["Customer","Resolution experience","Improve","CSAT / case metrics"],["Risk","Unsupported AI outputs","Reduce","Evaluation dataset"],["Adoption","Active users / repeat use","Increase","Product analytics"]],columns=["Value Dimension","Measure","Desired Direction","Validation Method"])
st.dataframe(value,use_container_width=True,hide_index=True)

st.markdown("""<div class="section"><h2>25 · Responsible AI Scorecard</h2><div class="caption">Questions to answer before moving from prototype to production.</div></div>""",unsafe_allow_html=True)
rai=[("Fairness","Could the system perform differently for different user groups?","Test representative cases; monitor disparities."),("Transparency","Can users understand why an answer or recommendation was produced?","Expose sources, rationale and limitations."),("Privacy","Does the workflow process personal or sensitive data?","Minimize data; enforce access controls."),("Security","Can a prompt or tool call expose unauthorized information?","RBAC, validation, logging and least privilege."),("Reliability","What happens when the model is wrong or unavailable?","Fallback path, uncertainty handling and monitoring."),("Accountability","Who owns the final business decision?","Named business owner and approval workflow.")]
for title,q,control in rai:
    st.markdown(f"<div class='card' style='margin:8px 0'><h4>🛡️ {title}</h4><p><b>Question:</b> {q}</p><p><b>Control:</b> {control}</p></div>",unsafe_allow_html=True)

st.markdown("""<div class="section"><h2>26 · Business Analyst Toolkit</h2><div class="caption">Practical artifacts NOVA can support across a project lifecycle.</div></div>""",unsafe_allow_html=True)
toolkit=pd.DataFrame([["Discovery","Problem statement","Define the problem and desired outcome"],["Discovery","Stakeholder map","Identify influence, interest and concerns"],["Analysis","SIPOC","Set process boundaries"],["Analysis","5 Whys","Explore root causes"],["Analysis","As-is / To-be","Compare current and future workflows"],["Requirements","User stories","Capture user needs"],["Requirements","Acceptance criteria","Make requirements testable"],["Solution","Use-case matrix","Compare AI/automation options"],["Solution","Architecture","Connect business needs to technology"],["Delivery","Roadmap","Sequence implementation"],["Testing","UAT plan","Validate business behavior"],["Governance","Risk register","Track AI and operational risks"],["Measurement","KPI tree","Connect features to outcomes"]],columns=["Phase","Artifact","Purpose"])
st.dataframe(toolkit,use_container_width=True,hide_index=True)

st.markdown("""<div class="section"><h2>27 · What a Production Version Would Add</h2><div class="caption">Clear separation between this portfolio prototype and an enterprise deployment.</div></div>""",unsafe_allow_html=True)
p1,p2,p3=st.columns(3)
p1.markdown("<div class='card'><h4>Enterprise integrations</h4><p>ServiceNow / Jira, Microsoft 365, SharePoint, CRM, ERP and identity providers.</p></div>",unsafe_allow_html=True)
p2.markdown("<div class='card'><h4>Observability</h4><p>Tracing, latency, token usage, retrieval failures, model quality and incident monitoring.</p></div>",unsafe_allow_html=True)
p3.markdown("<div class='card'><h4>Governance</h4><p>Approval workflows, audit trails, data retention, model/version management and access policies.</p></div>",unsafe_allow_html=True)

st.markdown("""<div class="section"><h2>28 · Portfolio Evidence Panel</h2><div class="caption">The parts of NOVA you can demonstrate in interviews and on your resume.</div></div>""",unsafe_allow_html=True)
evidence=pd.DataFrame([["Business Analysis","Problem framing → requirements","Shows structured thinking"],["Product Thinking","Prioritization → roadmap → KPIs","Shows outcome orientation"],["GenAI","Prompting / LLM layer","Shows modern AI literacy"],["RAG","Document ingestion → retrieval → evidence","Shows grounded AI understanding"],["Agentic AI","Role-based multi-agent workflow","Shows orchestration concepts"],["Data","KPI + evaluation framework","Shows analytical thinking"],["Responsible AI","Risk, privacy, fairness, oversight","Shows enterprise awareness"],["UX","Command-center workflow","Shows communication / product sense"]],columns=["Skill","Evidence in NOVA","Why It Matters"])
st.dataframe(evidence,use_container_width=True,hide_index=True)

st.markdown("""<div class="section"><h2>29 · NOVA Demo Scenario</h2><div class="caption">Use this storyline when showing the project to a recruiter, interviewer or mentor.</div></div>""",unsafe_allow_html=True)
demo_steps=[("01","Problem","A support organization has slow, inconsistent ticket resolution."),("02","Diagnose","NOVA identifies search friction, manual triage and fragmented knowledge."),("03","Define","Requirements and acceptance criteria are generated for validation."),("04","Discover AI","NOVA compares RAG, GenAI, classification and agentic workflow patterns."),("05","Ground","Approved policy documents are uploaded and queried through the RAG layer."),("06","Design","The architecture separates users, orchestrator, agents, knowledge and governance."),("07","Prioritize","The portfolio compares value, effort and risk before recommending a pilot."),("08","Measure","KPIs and evaluation scenarios define how success will be validated."),("09","Govern","Responsible AI controls define privacy, security, transparency and human oversight."),("10","Deliver","A phased roadmap moves from discovery to pilot and controlled scale.")]
for n,title,desc in demo_steps:
    st.markdown(f"<div class='agent'><b>{n} · {title}</b><br><small>{desc}</small></div>",unsafe_allow_html=True)

st.markdown("""<div class="section"><h2>30 · Final Solution Blueprint</h2><div class="caption">The complete NOVA operating model.</div></div>""",unsafe_allow_html=True)
st.code("""                         ┌─────────────────────────────┐\n                         │        BUSINESS USERS        │\n                         │ BA • Manager • Employee      │\n                         └──────────────┬──────────────┘\n                                        │\n                                        ▼\n                     ┌──────────────────────────────────┐\n                     │        NOVA EXPERIENCE            │\n                     │ Discovery • Requirements • RAG    │\n                     │ Prioritization • Reports          │\n                     └────────────────┬─────────────────┘\n                                      │\n                                      ▼\n                     ┌──────────────────────────────────┐\n                     │       AGENT ORCHESTRATOR          │\n                     └───────┬─────────┬─────────┬──────┘\n                             │         │         │\n                     ┌───────▼───┐ ┌──▼──────┐ ┌▼──────────┐\n                     │ BA AGENTS │ │ RAG     │ │ ANALYTICS │\n                     │ Req/Road  │ │ AGENT   │ │ / KPI     │\n                     └───────┬───┘ └──┬──────┘ └────┬──────┘\n                             │        │              │\n                             └────────┼──────────────┘\n                                      ▼\n                              ┌───────────────┐\n                              │ SOLUTION +    │\n                              │ RISK AGENTS   │\n                              └───────┬───────┘\n                                      ▼\n                              ┌───────────────┐\n                              │ HUMAN REVIEW  │\n                              └───────┬───────┘\n                                      ▼\n                              PILOT → MEASURE\n                                      │\n                                      ▼\n                                   SCALE\n""",language="text")

st.markdown("""<div class="section"><h2>31 · NOVA Capability Summary</h2><div class="caption">A single-page view of the portfolio scope.</div></div>""",unsafe_allow_html=True)
caps=["Business problem discovery and structured framing","Stakeholder analysis and process scoping","Root-cause and current-state analysis","Functional + non-functional requirements","User stories and acceptance criteria","AI / automation use-case discovery","RAG document ingestion and evidence retrieval","Agentic AI role orchestration","Enterprise solution architecture","Prioritization and roadmap planning","KPI and business-value framework","UAT and AI evaluation scenarios","Responsible AI and risk governance","Executive report generation"]
cc=st.columns(2)
for i,cap in enumerate(caps): cc[i%2].markdown(f"<div class='kpi'>✓ {cap}</div>",unsafe_allow_html=True)
st.markdown("<div style='height:60px'></div>",unsafe_allow_html=True)

st.markdown("<br><div style='text-align:center;color:#65718c;font-size:11px'>NOVA is a portfolio-grade decision-support prototype. Validate recommendations, scores and business outcomes against real organizational data before operational use.</div>",unsafe_allow_html=True)
