// app.js — reads AI_POLICY_RECORDS (from data.js) and renders the dashboard.
// No frameworks, no build step — plain DOM so this runs anywhere, including file://.


(function () {
    const records = (window.AI_POLICY_RECORDS || []).slice();


    const state = {
        states: new Set(),   // active state filters (empty = all)
        cats: new Set(),     // active category filters (empty = all)
        q: "",
        view: "timeline",
    };


    const STATE_ORDER = [...new Set(records.map(r => r.state))].sort();
    const CAT_ORDER = [
        "Policy / Strategy", "Institutional Setup", "Industry / Academia MoU",
        "Governance Deployment", "Budget & Funding", "Regulatory / Ethics", "Skilling / Workforce",
    ].filter(c => records.some(r => r.category === c));


    // ---------- header stats ----------
    function renderStats() {
        const dates = records.map(r => r.date).sort();
        const strip = document.getElementById("statStrip");
        const stats = [
            { n: records.length, l: "Records" },
            { n: STATE_ORDER.length, l: "States" },
            { n: CAT_ORDER.length, l: "Categories" },
            { n: `${dates[0].slice(0, 7)} \u2192 ${dates[dates.length - 1].slice(0, 7)}`, l: "Date span" },
        ];
        strip.innerHTML = stats.map(s => `<div class="stat"><div class="n">${s.n}</div><div class="l">${s.l}</div></div>`).join("");
        document.getElementById("today").textContent = new Date().toLocaleDateString("en-IN", { year: "numeric", month: "long", day: "numeric" });
    }


    // ---------- bar chart: records per state ----------
    function renderBars() {
        const counts = {};
        STATE_ORDER.forEach(s => counts[s] = 0);
        records.forEach(r => counts[r.state]++);
        const max = Math.max(...Object.values(counts));
        const el = document.getElementById("stateBars");
        el.innerHTML = STATE_ORDER
            .sort((a, b) => counts[b] - counts[a])
            .map(s => `
       <div class="bar-row">
         <div class="bar-label">${s}</div>
         <div class="bar-track"><div class="bar-fill" style="width:${(counts[s] / max * 100).toFixed(0)}%"></div></div>
         <div class="bar-count">${counts[s]}</div>
       </div>`).join("");
    }


    // ---------- filter chips ----------
    function renderChips() {
        const stateEl = document.getElementById("stateChips");
        stateEl.innerHTML = STATE_ORDER.map(s => `<span class="chip" data-state="${s}">${s}</span>`).join("");
        stateEl.querySelectorAll(".chip").forEach(chip => {
            chip.addEventListener("click", () => {
                const s = chip.dataset.state;
                state.states.has(s) ? state.states.delete(s) : state.states.add(s);
                chip.classList.toggle("active");
                render();
            });
        });


        const catEl = document.getElementById("catChips");
        catEl.innerHTML = CAT_ORDER.map(c => `<span class="chip" data-cat="${c}">${c}</span>`).join("");
        catEl.querySelectorAll(".chip").forEach(chip => {
            chip.addEventListener("click", () => {
                const c = chip.dataset.cat;
                state.cats.has(c) ? state.cats.delete(c) : state.cats.add(c);
                chip.classList.toggle("active");
                render();
            });
        });
    }


    function fmtDate(r) {
        const d = new Date(r.date + "T00:00:00");
        if (r.date_precision === "day") {
            return d.toLocaleDateString("en-IN", { year: "numeric", month: "short", day: "numeric" });
        }
        if (r.date_precision === "month") {
            return "~" + d.toLocaleDateString("en-IN", { year: "numeric", month: "short" });
        }
        return "~" + d.getFullYear();
    }


    function filtered() {
        const q = state.q.trim().toLowerCase();
        return records.filter(r => {
            if (state.states.size && !state.states.has(r.state)) return false;
            if (state.cats.size && !state.cats.has(r.category)) return false;
            if (q) {
                const hay = [r.headline, r.summary, r.entities, r.state, r.category].join(" ").toLowerCase();
                if (!hay.includes(q)) return false;
            }
            return true;
        }).sort((a, b) => b.date.localeCompare(a.date));
    }


    function renderTimeline(rows) {
        const el = document.getElementById("results");
        if (!rows.length) {
            el.innerHTML = `<div class="empty-state">No records match these filters. Try clearing a filter or the search box.</div>`;
            return;
        }
        el.innerHTML = rows.map(r => `
     <article class="card" data-cat="${r.category}">
       <div class="card-top">
         <div class="card-meta">
           <span class="state-badge">${r.state_code}</span>
           <span>${r.state}</span>
           <span>&middot;</span>
           <span>${fmtDate(r)}</span>
         </div>
         <span class="cat-tag">${r.category}</span>
       </div>
       <h2>${r.headline}</h2>
       <p class="summary">${r.summary}</p>
       <div class="card-foot">
         <span class="entities">${r.entities || ""}</span>
         <a href="${r.source_url}" target="_blank" rel="noopener">${r.source_name} &rarr;</a>
       </div>
       ${(r.also_reported_by || r.notes) ? `
       <details class="notes">
         <summary>Sourcing notes</summary>
         ${r.also_reported_by ? `<p><strong>Also reported by:</strong> ${r.also_reported_by}</p>` : ""}
         ${r.notes ? `<p><strong>Note:</strong> ${r.notes}</p>` : ""}
       </details>` : ""}
     </article>
   `).join("");
    }


    function renderTable(rows) {
        const el = document.getElementById("tableWrap");
        if (!rows.length) {
            el.innerHTML = `<div class="empty-state">No records match these filters.</div>`;
            return;
        }
        el.innerHTML = `
     <table>
       <thead><tr>
         <th>State</th><th>Date</th><th>Category</th><th>Headline</th><th>Source</th>
       </tr></thead>
       <tbody>
         ${rows.map(r => `
           <tr>
             <td>${r.state_code}</td>
             <td class="mono">${fmtDate(r)}</td>
             <td>${r.category}</td>
             <td>${r.headline}</td>
             <td><a href="${r.source_url}" target="_blank" rel="noopener">${r.source_name}</a></td>
           </tr>`).join("")}
       </tbody>
     </table>`;
    }


    function render() {
        const rows = filtered();
        document.getElementById("resultCount").textContent = `${rows.length} of ${records.length} records`;
        if (state.view === "timeline") {
            document.getElementById("results").style.display = "flex";
            document.getElementById("tableWrap").style.display = "none";
            renderTimeline(rows);
        } else {
            document.getElementById("results").style.display = "none";
            document.getElementById("tableWrap").style.display = "block";
            renderTable(rows);
        }
    }


    document.getElementById("searchBox").addEventListener("input", e => {
        state.q = e.target.value;
        render();
    });
    document.getElementById("btnTimeline").addEventListener("click", () => {
        state.view = "timeline";
        document.getElementById("btnTimeline").classList.add("active");
        document.getElementById("btnTable").classList.remove("active");
        render();
    });
    document.getElementById("btnTable").addEventListener("click", () => {
        state.view = "table";
        document.getElementById("btnTable").classList.add("active");
        document.getElementById("btnTimeline").classList.remove("active");
        render();
    });


    renderStats();
    renderBars();
    renderChips();
    render();
})();
