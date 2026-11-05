/* ═══════════════════════════════════════════════════════════
   Project CogniGap — Dashboard JavaScript v2.0
   Dual-score display + plagiarism sources + API-based search
   ═══════════════════════════════════════════════════════════ */

let localScoreChart = null;
let globalScoreChart = null;
let overlapChart = null;
let timelineChart = null;

Chart.defaults.color = '#777777';
Chart.defaults.borderColor = '#252525';
Chart.defaults.font.family = "'Inter', sans-serif";

// ── Toast ────────────────────────────────────────────────────
function showToast(message, type = 'info') {
    const c = document.getElementById('toastContainer');
    const t = document.createElement('div');
    t.className = `toast ${type}`;
    t.textContent = message;
    c.appendChild(t);
    setTimeout(() => {
        t.style.animation = 'toastOut 0.3s ease forwards';
        setTimeout(() => t.remove(), 300);
    }, 4000);
}

function setStatus(text) {
    const label = document.querySelector('.status-text');
    if (label) label.textContent = text;
}

function setProgress(step, status, done) {
    const el = document.getElementById(`pStep${step}`);
    const st = document.getElementById(`pStatus${step}`);
    if (done) {
        el.classList.remove('active');
        el.classList.add('done');
        st.textContent = '✓';
    } else {
        el.classList.add('active');
        el.classList.remove('done');
        st.textContent = status;
    }
}

// ── Full Pipeline (user-driven) ─────────────────────────────
async function runFullPipeline() {
    const idea = document.getElementById('ideaInput').value.trim();
    const keywords = document.getElementById('keywordsInput').value.trim();
    const tags = document.getElementById('tagsInput').value.trim();
    const topics = document.getElementById('topicsInput').value.trim();

    if (!idea && !keywords && !tags) {
        showToast('Please describe your idea or enter some keywords/tags.', 'error');
        return;
    }

    const btn = document.getElementById('btnRunAll');
    btn.disabled = true;
    btn.textContent = 'Running...';

    const prog = document.getElementById('progressSection');
    prog.style.display = 'block';

    const topicList = topics ? topics.split(',').map(t => t.trim()).filter(Boolean) : undefined;

    const userContext = {
        idea: idea,
        keywords: keywords,
        tags: tags,
        topics: topicList
    };

    try {
        // Step A: Scan local files
        setProgress(1, 'running...', false);
        setStatus('Scanning files...');
        const scanResp = await fetch('/api/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(userContext)
        });
        const scanData = await scanResp.json();
        if (scanData.success) {
            setProgress(1, '', true);
            showToast(`Scanned ${scanData.total_files} local files`, 'success');
        } else {
            setProgress(1, 'failed', false);
            showToast('Scan failed: ' + (scanData.error || ''), 'error');
        }

        // Step B: Search databases
        setProgress(2, 'running...', false);
        setStatus('Searching research databases...');
        const scrapeResp = await fetch('/api/scrape', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(userContext)
        });
        const scrapeData = await scrapeResp.json();
        if (scrapeData.success) {
            setProgress(2, '', true);
            showToast(`Found ${scrapeData.total_results} results from databases`, 'success');
        } else {
            setProgress(2, 'failed', false);
            showToast('Search failed: ' + (scrapeData.error || ''), 'error');
        }

        // Step C: Analyze
        setProgress(3, 'running...', false);
        setStatus('Analyzing originality...');
        const analyzeResp = await fetch('/api/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(userContext)
        });
        const analyzeData = await analyzeResp.json();
        if (analyzeData.success && analyzeData.results) {
            setProgress(3, '', true);
            setStatus('Complete');
            showToast(`Local: ${analyzeData.results.local_originality_score}% | Global: ${analyzeData.results.global_originality_score}%`, 'success');
            renderResults(analyzeData.results);

            const rs = document.getElementById('resultsSection');
            rs.style.display = 'flex';
            rs.scrollIntoView({ behavior: 'smooth', block: 'start' });
        } else {
            setProgress(3, 'failed', false);
            showToast('Analysis failed: ' + (analyzeData.error || analyzeData.message || ''), 'error');
        }

    } catch (err) {
        showToast('Error: ' + err.message, 'error');
        setStatus('Error');
    }

    btn.disabled = false;
    btn.innerHTML = '<span class="btn-dot"></span> Run Originality Check';
}

// ── Render Results ──────────────────────────────────────────
function renderResults(r) {
    // Dual scores
    updateDoughnut('localScoreChart', r.local_originality_score, '#6aaa78', '#1a1a1a');
    updateDoughnut('globalScoreChart', r.global_originality_score, '#7a9abb', '#1a1a1a');
    document.getElementById('localScoreValue').textContent = r.local_originality_score + '%';
    document.getElementById('globalScoreValue').textContent = r.global_originality_score + '%';
    document.getElementById('localPlagPct').textContent = r.local_plagiarism_pct + '%';
    document.getElementById('globalPlagPct').textContent = r.global_plagiarism_pct + '%';
    document.getElementById('localFileCount').textContent = r.local_file_count;
    document.getElementById('globalResultCount').textContent = r.global_result_count;

    // Status counts
    document.getElementById('statExists').textContent = r.status_counts.already_exists;
    document.getElementById('statSimilar').textContent = r.status_counts.similar_work;
    document.getElementById('statOriginal').textContent = r.status_counts.original;

    // Plagiarism sources
    renderPlagiarismSources(r.plagiarism_sources);
    if (r.concepts) { renderBlindspotMatrix(r.concepts); }

    // Local file matches
    renderLocalFiles(r.local_similar_files);

    // Insights & References
    renderInsights(r.insights);
    renderReferences(r.references);

    // Overlap chart
    updateOverlapChart(r);

    // Gaps, similar items, map
    renderGaps(r.gaps);
    renderSimilarItems(r.global_similar_items);
    renderMap(r.connection_map);
}

// ── Doughnut Chart ──────────────────────────────────────────
function updateDoughnut(canvasId, score, color, bgColor) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    // Destroy existing
    const existing = Chart.getChart(canvasId);
    if (existing) existing.destroy();

    new Chart(ctx, {
        type: 'doughnut',
        data: {
            datasets: [{
                data: [score, 100 - score],
                backgroundColor: [color, bgColor],
                borderWidth: 0,
                cutout: '78%',
                borderRadius: 6,
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: true,
            plugins: { legend: { display: false }, tooltip: { enabled: false } },
            animation: { animateRotate: true, duration: 1200 }
        }
    });
}

// ── Plagiarism Sources ──────────────────────────────────────
function renderPlagiarismSources(sources) {
    const el = document.getElementById('plagiarismList');
    if (!sources || !sources.length) {
        el.innerHTML = '<div class="empty-state">No plagiarism sources detected — your idea appears original!</div>';
        return;
    }
    el.innerHTML = sources.map(s => {
        const pct = s.similarity_pct;
        let badgeCls = 'badge-green';
        if (pct >= 50) badgeCls = 'badge-red';
        else if (pct >= 20) badgeCls = 'badge-amber';

        const sourceIcon = getSourceIcon(s.source_type);
        const yearStr = s.year ? ` · ${s.year}` : '';
        const citStr = s.citations ? ` · ${s.citations} citations` : '';

        return `
            <div class="plag-item">
                <div class="plag-score ${badgeCls}">${pct}%</div>
                <div class="plag-info">
                    <div class="plag-title">${s.url ? `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.title)}</a>` : esc(s.title)}</div>
                    <div class="plag-meta">
                        <span class="plag-source-badge ${s.source_type}">${sourceIcon} ${esc(s.source_label)}</span>
                        ${yearStr}${citStr}
                    </div>
                    ${s.snippet ? `<div class="plag-snippet">${esc(s.snippet)}</div>` : ''}
                </div>
            </div>
        `;
    }).join('');
}

function getSourceIcon(sourceType) {
    switch(sourceType) {
        case 'semantic_scholar': return '📄';
        case 'crossref': return '📚';
        case 'openalex': return '🔬';
        case 'github': return '💻';
        case 'web': return '🌐';
        default: return '🔗';
    }
}

// ── Local File Matches ──────────────────────────────────────
function renderLocalFiles(files) {
    const el = document.getElementById('localFilesList');
    if (!files || !files.length) {
        el.innerHTML = '<div class="empty-state">No local files to compare against.</div>';
        return;
    }
    el.innerHTML = files.map(f => {
        const pct = Math.round(f.similarity * 100);
        let cls = 'low';
        if (f.status === 'Heavily Overlapping') cls = 'high';
        else if (f.status === 'Some Overlap') cls = 'medium';
        return `
            <div class="similar-item">
                <div class="sim-score ${cls}">${pct}%</div>
                <div class="sim-info">
                    <div class="sim-title">${esc(f.filename)}</div>
                    <div class="sim-meta">${esc(f.snippet || '')}</div>
                </div>
                <div class="sim-tag">${f.status}</div>
            </div>
        `;
    }).join('');
}

// ── Overlap Radar ───────────────────────────────────────────
function updateOverlapChart(r) {
    const ctx = document.getElementById('overlapChart').getContext('2d');
    if (overlapChart) overlapChart.destroy();

    overlapChart = new Chart(ctx, {
        type: 'radar',
        data: {
            labels: ['Your Keywords', 'Global Keywords', 'Overlap Match', 'Local Score', 'Global Score'],
            datasets: [{
                label: 'Profile',
                data: [
                    Math.min(r.total_user_keywords * 5, 100), // Scale for visual balance
                    Math.min(r.total_global_keywords, 100),
                    Math.min(r.overlap_count * 10, 100), // Scale for visual balance
                    r.local_originality_score,
                    r.global_originality_score
                ],
                backgroundColor: 'rgba(74, 139, 90, 0.2)', // Vibrant green with opacity
                borderColor: '#4a8b5a', // Solid green
                borderWidth: 2,
                pointBackgroundColor: '#7a9abb', // Blue points
                pointBorderColor: '#111111',
                pointBorderWidth: 2,
                pointRadius: 5,
                pointHoverRadius: 7
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            scales: {
                r: {
                    beginAtZero: true,
                    grid: { color: '#1f1f1f' },
                    angleLines: { color: '#1f1f1f' },
                    pointLabels: { color: '#777', font: { size: 11 } },
                    ticks: { display: false }
                }
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#1a1a1a',
                    borderColor: '#333', borderWidth: 1,
                    titleFont: { weight: '500' },
                    bodyFont: { family: "'JetBrains Mono', monospace" },
                    padding: 10, cornerRadius: 12,
                }
            },
            animation: { duration: 1000 }
        }
    });
}


// ── Gaps ─────────────────────────────────────────────────────
function renderGaps(gaps) {
    const el = document.getElementById('gapsList');
    if (!gaps || !gaps.length) {
        el.innerHTML = '<div class="empty-state">No gaps found — your work covers current trends.</div>';
        return;
    }
    el.innerHTML = gaps.map(g => `
        <div class="gap-item">
            <div class="gap-keyword">${esc(g.keyword)}</div>
            <div class="gap-bar"><div class="gap-bar-fill" style="width:${g.trending_score}%"></div></div>
            <div class="gap-suggestion">${esc(g.suggestion)}</div>
        </div>
    `).join('');
}

// ── Similar Items (Global) ──────────────────────────────────
function renderSimilarItems(items) {
    const el = document.getElementById('similarList');
    if (!items || !items.length) {
        el.innerHTML = '<div class="empty-state">No similar work found.</div>';
        return;
    }
    el.innerHTML = items.slice(0, 15).map(item => {
        const pct = Math.round(item.similarity * 100);
        let cls = 'low';
        if (item.status === 'Already Exists') cls = 'high';
        else if (item.status === 'Similar Work Found') cls = 'medium';
        const sourceIcon = getSourceIcon(item.source);
        return `
            <div class="similar-item">
                <div class="sim-score ${cls}">${pct}%</div>
                <div class="sim-info">
                    <div class="sim-title">${item.url ? `<a href="${esc(item.url)}" target="_blank" rel="noopener">${esc(item.title || 'Untitled')}</a>` : esc(item.title || 'Untitled')}</div>
                    <div class="sim-meta">${sourceIcon} ${esc(item.source_label || item.source || '')} ${item.year ? '· ' + item.year : ''}</div>
                </div>
                <div class="sim-tag">${item.status}</div>
            </div>
        `;
    }).join('');
}

// ── Connection Map ──────────────────────────────────────────
function renderMap(path) {
    const el = document.getElementById('mapContainer');
    if (!path) {
        el.innerHTML = '<div class="empty-state">No map available</div>';
        return;
    }
    el.innerHTML = `<div style="width: 100%; max-height: 500px; overflow: hidden; display: flex; justify-content: center;"><img src="/static/${path}?t=${Date.now()}" alt="Connection Map" style="max-width: 100%; max-height: 100%; object-fit: contain;"></div>`;
}

// ── Project Insights ────────────────────────────────────────
function renderInsights(insights) {
    const el = document.getElementById('insightsContent');
    if (!insights || !insights.verdict) {
        el.innerHTML = '<div class="empty-state">No insights available</div>';
        return;
    }

    // Verdict banner
    const verdictClass = insights.should_build ? 'verdict-go' : 'verdict-stop';
    let html = `
        <div class="insight-verdict ${verdictClass}">
            <div class="verdict-title">${esc(insights.recommendation)}</div>
            <div class="verdict-detail">${esc(insights.recommendation_detail)}</div>
        </div>
    `;

    // Pros & Cons side by side
    html += '<div class="pros-cons-grid">';

    // Pros
    html += '<div class="pros-section"><h3 class="pros-title">✅ Pros</h3>';
    if (insights.pros && insights.pros.length) {
        html += insights.pros.map(p => `
            <div class="insight-item pro-item">
                <span class="insight-icon">${p.icon || '✅'}</span>
                <div>
                    <div class="insight-item-title">${esc(p.title)}</div>
                    <div class="insight-item-detail">${esc(p.detail)}</div>
                </div>
            </div>
        `).join('');
    } else {
        html += '<div class="empty-state" style="padding:1rem;">No notable pros found.</div>';
    }
    html += '</div>';

    // Cons
    html += '<div class="cons-section"><h3 class="cons-title">⚠️ Cons</h3>';
    if (insights.cons && insights.cons.length) {
        html += insights.cons.map(c => `
            <div class="insight-item con-item">
                <span class="insight-icon">${c.icon || '⚠️'}</span>
                <div>
                    <div class="insight-item-title">${esc(c.title)}</div>
                    <div class="insight-item-detail">${esc(c.detail)}</div>
                </div>
            </div>
        `).join('');
    } else {
        html += '<div class="empty-state" style="padding:1rem;">No notable cons found.</div>';
    }
    html += '</div></div>';

    // Usefulness table
    if (insights.usefulness) {
        const u = insights.usefulness;
        html += `
            <div class="usefulness-section">
                <h3 class="usefulness-title">📊 Real-World Usefulness Assessment</h3>
                <table class="usefulness-table">
                    <thead>
                        <tr><th>Metric</th><th>Score</th><th>Rating</th></tr>
                    </thead>
                    <tbody>
                        ${renderUsefulnessRow('Real-World Impact', u.real_world_impact)}
                        ${renderUsefulnessRow('Technical Innovation', u.technical_innovation)}
                        ${renderUsefulnessRow('Market Potential', u.market_potential)}
                        ${renderUsefulnessRow('Learning Value', u.learning_value)}
                        ${renderUsefulnessRow('Community Interest', u.community_interest)}
                    </tbody>
                    <tfoot>
                        <tr class="usefulness-total">
                            <td><strong>Overall Score</strong></td>
                            <td><strong>${u.overall}/10</strong></td>
                            <td><strong>${getScoreLabel(u.overall)}</strong></td>
                        </tr>
                    </tfoot>
                </table>
            </div>
        `;
    }

    el.innerHTML = html;
}

function renderUsefulnessRow(label, score) {
    const pct = (score || 0) * 10;
    const lbl = getScoreLabel(score);
    return `
        <tr>
            <td>${label}</td>
            <td>
                <div class="score-bar-wrap">
                    <div class="score-bar-fill" style="width:${pct}%;background:${getScoreColor(score)}"></div>
                </div>
                <span class="score-num">${score}/10</span>
            </td>
            <td class="score-label-td" style="color:${getScoreColor(score)}">${lbl}</td>
        </tr>
    `;
}

function getScoreLabel(score) {
    if (score >= 8) return 'Excellent';
    if (score >= 6) return 'Good';
    if (score >= 4) return 'Fair';
    return 'Low';
}

function getScoreColor(score) {
    if (score >= 8) return '#6aaa78';
    if (score >= 6) return '#7a9abb';
    if (score >= 4) return '#bbaa77';
    return '#bb7777';
}

// ── Reference Materials ─────────────────────────────────────
function renderReferences(refs) {
    const el = document.getElementById('referencesContent');
    if (!refs) {
        el.innerHTML = '<div class="empty-state">No references found</div>';
        return;
    }

    let html = '<div class="ref-tabs">';

    // Papers tab
    if (refs.papers && refs.papers.length) {
        html += '<div class="ref-section"><h3 class="ref-section-title">📄 Research Papers</h3><div class="ref-list">';
        html += refs.papers.map(p => `
            <div class="ref-item">
                <div class="ref-item-title"><a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.title)}</a></div>
                <div class="ref-item-meta">${p.source || 'Paper'} ${p.year ? '· ' + p.year : ''} ${p.citations ? '· ' + p.citations + ' citations' : ''}</div>
            </div>
        `).join('');
        html += '</div></div>';
    }

    // GitHub repos
    if (refs.repos && refs.repos.length) {
        html += '<div class="ref-section"><h3 class="ref-section-title">💻 GitHub Repositories</h3><div class="ref-list">';
        html += refs.repos.map(r => `
            <div class="ref-item">
                <div class="ref-item-title"><a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.title)}</a></div>
                <div class="ref-item-meta">${r.language || ''} ${r.stars ? '· ⭐ ' + r.stars : ''}</div>
                ${r.snippet ? `<div class="ref-item-snippet">${esc(r.snippet)}</div>` : ''}
            </div>
        `).join('');
        html += '</div></div>';
    }

    // Web results
    if (refs.web && refs.web.length) {
        html += '<div class="ref-section"><h3 class="ref-section-title">🌐 Web Resources</h3><div class="ref-list">';
        html += refs.web.map(w => `
            <div class="ref-item">
                <div class="ref-item-title"><a href="${esc(w.url)}" target="_blank" rel="noopener">${esc(w.title)}</a></div>
                ${w.snippet ? `<div class="ref-item-snippet">${esc(w.snippet)}</div>` : ''}
            </div>
        `).join('');
        html += '</div></div>';
    }

    if (!html.includes('ref-section')) {
        html = '<div class="empty-state">No reference materials found</div>';
    }

    html += '</div>';
    el.innerHTML = html;
}

// ── Utility ─────────────────────────────────────────────────
function esc(s) {
    if (!s) return '';
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

// ── Blindspot Matrix ────────────────────────────────────────
function renderBlindspotMatrix(concepts) {
    const c = document.getElementById('blindspotContent');
    if (!c) return;
    if (!concepts || concepts.length === 0) {
        c.innerHTML = '<div class="empty-state">No concept data available</div>';
        return;
    }
    let html = 
    <table style="width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 10px;">
        <thead>
            <tr style="border-bottom: 1px solid #333; color: #888;">
                <th style="text-align: left; padding: 10px;">Architectural Concept</th>
                <th style="text-align: center; padding: 10px;">Papers</th>
                <th style="text-align: center; padding: 10px;">Patents</th>
                <th style="text-align: center; padding: 10px;">Code</th>
            </tr>
        </thead>
        <tbody>
    ;
    concepts.forEach(row => {
        const pPct = Math.round((row.papers || 0) * 100);
        const patPct = Math.round((row.patents || 0) * 100);
        const cPct = Math.round((row.code || 0) * 100);
        const getBg = v => hsla(, 70%, 45%, 0.25);
        const getClr = v => hsl(, 80%, 65%);

        html += 
        <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
            <td style="padding: 12px 10px; font-weight: 500;"> + row.name + </td>
            <td style="text-align: center; padding: 10px;">
                <span style="background:  + getBg(pPct) + ; color:  + getClr(pPct) + ; padding: 4px 10px; border-radius: 6px; font-weight: 600;"> + pPct + %</span>
            </td>
            <td style="text-align: center; padding: 10px;">
                <span style="background:  + getBg(patPct) + ; color:  + getClr(patPct) + ; padding: 4px 10px; border-radius: 6px; font-weight: 600;"> + patPct + %</span>
            </td>
            <td style="text-align: center; padding: 10px;">
                <span style="background:  + getBg(cPct) + ; color:  + getClr(cPct) + ; padding: 4px 10px; border-radius: 6px; font-weight: 600;"> + cPct + %</span>
            </td>
        </tr>
        ;
    });
    html += </tbody></table>;
    c.innerHTML = html;
}