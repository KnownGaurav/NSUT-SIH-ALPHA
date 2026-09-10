import React, { useState, useEffect, useRef } from 'react'

const STATIONS = [
  { code: 'NDLS', name: 'New Delhi', zone: 'NR' },
  { code: 'HWH',  name: 'Howrah Junction', zone: 'ER' },
  { code: 'CNB',  name: 'Kanpur Central', zone: 'NCR' },
  { code: 'PRYJ', name: 'Prayagraj Jn.', zone: 'NCR' },
  { code: 'BSB',  name: 'Varanasi Jn.', zone: 'NR' },
  { code: 'DBG',  name: 'Darbhanga Jn.', zone: 'ECR' },
  { code: 'TPTY', name: 'Tirupati', zone: 'SCR' },
]

const DELAY_STATUS = {
  on_time:  { label: 'ON TIME',   cls: 'pis-status-ontime' },
  moderate: { label: 'DELAYED',   cls: 'pis-status-delayed' },
  severe:   { label: 'LATE',      cls: 'pis-status-severe' },
}

function marqueeText(arr) {
  if (!arr || !arr.length) return ''
  const items = arr.map(a => `${a.train_number} ${a.train_name}  ·  PF ${a.assigned_platform}  ·  ${a.dynamic_predicted_eta || a.scheduled_arrival || '--'}`)
  return items.join('          |||          ')
}

export default function PassengerDisplayView({ onBackToDashboard, onOpenStationOps, onOpenAnalytics }) {
  const [selectedStation, setSelectedStation] = useState('NDLS')
  const [mobileView, setMobileView] = useState(false)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [tick, setTick] = useState(0)   // for blink animation sync
  const [lastUpdated, setLastUpdated] = useState(null)
  const tickRef = useRef(null)

  // Blink tick every 800 ms
  useEffect(() => {
    tickRef.current = setInterval(() => setTick(t => t + 1), 800)
    return () => clearInterval(tickRef.current)
  }, [])

  const fetchData = async (code) => {
    try {
      setLoading(true)
      setError(null)
      const res = await fetch(`/api/stations/${code}/arrivals?window_hours=6`)
      if (res.ok) {
        const json = await res.json()
        setData(json)
        setLastUpdated(new Date())
      } else {
        const j = await res.json().catch(() => ({}))
        setError(j.detail || `Failed to fetch arrivals for ${code}`)
        setData(null)
      }
    } catch (e) {
      setError(e.message || 'Network error')
      setData(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData(selectedStation)
    const id = setInterval(() => fetchData(selectedStation), 8000)
    return () => clearInterval(id)
  }, [selectedStation])

  const arrivals = data?.arrivals || []
  const now = new Date()
  const stnInfo = STATIONS.find(s => s.code === selectedStation)

  // Determine if a train is "arriving soon" (ETA within 10 min from now, approx)
  const isArrivingSoon = (arr) => {
    if (!arr.dynamic_predicted_eta) return false
    // ETA is formatted like "09:30 PM" — parse roughly
    try {
      const [time, period] = arr.dynamic_predicted_eta.split(' ')
      const [h, m] = time.split(':').map(Number)
      let hours = h + (period === 'PM' && h !== 12 ? 12 : period === 'AM' && h === 12 ? -12 : 0)
      const etaDate = new Date()
      etaDate.setHours(hours, m, 0, 0)
      const diffMin = (etaDate - now) / 60000
      return diffMin >= 0 && diffMin <= 10
    } catch { return false }
  }

  const isConflict = (arr) => arr.platform_conflict_flag

  const blinkOn = tick % 2 === 0

  return (
    <div className="pis-layout">
      {/* ── Top Control Bar ── */}
      <header className="pis-header">
        {/* Brand */}
        <div className="pis-brand">
          <div className="pis-ir-badge">IR</div>
          <div>
            <div className="pis-header-title">INDIAN RAILWAYS — PASSENGER INFORMATION SYSTEM</div>
            <div className="pis-header-sub">Real-Time Dynamic ETA Display Board · SIH 2026</div>
          </div>
        </div>

        {/* Nav buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
          <button
            className={`pis-view-toggle ${mobileView ? 'active' : ''}`}
            onClick={() => setMobileView(v => !v)}
          >
            {mobileView ? '🖥 Board View' : '📱 Mobile View'}
          </button>

          <button className="btn btn-primary" style={{ fontSize: '0.7rem', padding: '0.3rem 0.6rem' }}
            onClick={onBackToDashboard}>
            &#9638; Control Room
          </button>
          <button className="btn" style={{ fontSize: '0.7rem', padding: '0.3rem 0.6rem', borderColor: '#10b981', color: '#34d399' }}
            onClick={onOpenStationOps}>
            🚉 Station Ops
          </button>
          <button className="btn" style={{ fontSize: '0.7rem', padding: '0.3rem 0.6rem', borderColor: '#0284c7', color: '#38bdf8' }}
            onClick={onOpenAnalytics}>
            &#128202; Analytics
          </button>
        </div>
      </header>

      {/* ── Station Selector Row ── */}
      <div className="pis-station-bar">
        <span className="pis-station-label">SELECT STATION :</span>
        <div className="pis-station-chips">
          {STATIONS.map(s => (
            <button
              key={s.code}
              className={`pis-chip ${selectedStation === s.code ? 'active' : ''}`}
              onClick={() => setSelectedStation(s.code)}
            >
              {s.code}
              <span className="pis-chip-sub">{s.name}</span>
            </button>
          ))}
        </div>

        <div className="pis-liveband">
          <span className="pis-live-dot" style={{ color: blinkOn ? '#fbbf24' : '#713f12' }}>●</span>
          <span className="pis-live-text">LIVE</span>
          {lastUpdated && (
            <span className="pis-live-ts">Updated {lastUpdated.toLocaleTimeString()}</span>
          )}
        </div>
      </div>

      {/* ── Station Masthead / Board Header ── */}
      <div className={`pis-board-masthead ${mobileView ? 'mobile' : ''}`}>
        <div className="pis-board-stn">
          <span className="pis-board-stn-code">{selectedStation}</span>
          <span className="pis-board-stn-name">{stnInfo?.name?.toUpperCase() || selectedStation}</span>
          <span className="pis-board-stn-zone">Zone: {data?.zone || stnInfo?.zone || '--'}</span>
        </div>
        <div className="pis-board-stats">
          <div className="pis-stat">
            <span className="pis-stat-val">{arrivals.length}</span>
            <span className="pis-stat-lbl">TRAINS</span>
          </div>
          <div className="pis-stat">
            <span className="pis-stat-val" style={{ color: '#34d399' }}>
              {arrivals.filter(a => a.delay_minutes <= 5).length}
            </span>
            <span className="pis-stat-lbl">ON TIME</span>
          </div>
          <div className="pis-stat">
            <span className="pis-stat-val" style={{ color: '#fbbf24' }}>
              {arrivals.filter(a => a.delay_minutes > 5 && a.delay_minutes <= 30).length}
            </span>
            <span className="pis-stat-lbl">DELAYED</span>
          </div>
          <div className="pis-stat">
            <span className="pis-stat-val" style={{ color: '#f87171' }}>
              {arrivals.filter(a => a.delay_minutes > 30).length}
            </span>
            <span className="pis-stat-lbl">LATE</span>
          </div>
          <div className="pis-stat">
            <span className="pis-stat-val" style={{ color: data?.active_conflicts_count > 0 ? '#ef4444' : '#34d399' }}>
              {data?.active_conflicts_count || 0}
            </span>
            <span className="pis-stat-lbl">CONFLICTS</span>
          </div>
          <div className="pis-stat">
            <span className="pis-stat-val">{data?.total_platforms || '--'}</span>
            <span className="pis-stat-lbl">PLATFORMS</span>
          </div>
        </div>
      </div>

      {/* ── Loading / Error States ── */}
      {loading && !data && (
        <div className="pis-loading">
          <span className="pis-loading-text">
            {'▐' + ' FETCHING LIVE BOARD FOR ' + selectedStation + ' '}{'▌'.repeat((tick % 4) + 1)}
          </span>
        </div>
      )}
      {error && (
        <div className="pis-error">
          [ERROR] {error} — Check backend connection.
        </div>
      )}

      {/* ── BOARD VIEW (Desktop LED Display) ── */}
      {!mobileView && data && (
        <div className="pis-board-container">
          {/* Column headers */}
          <div className="pis-row pis-row-header">
            <div className="pis-col pis-col-trainno">TRAIN NO</div>
            <div className="pis-col pis-col-name">TRAIN NAME</div>
            <div className="pis-col pis-col-origin">ORIGIN</div>
            <div className="pis-col pis-col-dest">DESTINATION</div>
            <div className="pis-col pis-col-sched">SCHED TIME</div>
            <div className="pis-col pis-col-eta">EXPECTED (ETA)</div>
            <div className="pis-col pis-col-delay">DELAY</div>
            <div className="pis-col pis-col-pf">PLATFORM</div>
            <div className="pis-col pis-col-status">STATUS</div>
          </div>

          {arrivals.length === 0 ? (
            <div className="pis-no-trains">
              NO SCHEDULED TRAINS FOUND FOR THIS STATION IN THE NEXT 6 HOURS
            </div>
          ) : (
            arrivals.map((arr, idx) => {
              const soon = isArrivingSoon(arr)
              const conflict = isConflict(arr)
              const ds = DELAY_STATUS[arr.delay_status] || DELAY_STATUS.on_time
              const blinkRow = (soon || conflict) && blinkOn
              const rowClass = [
                'pis-row',
                'pis-row-data',
                soon && !conflict ? 'arriving-soon' : '',
                conflict ? 'has-conflict' : '',
                blinkRow ? 'blink-active' : '',
                idx % 2 === 0 ? 'pis-row-even' : 'pis-row-odd',
              ].filter(Boolean).join(' ')

              return (
                <div key={arr.train_number} className={rowClass}>
                  <div className="pis-col pis-col-trainno pis-amber">{arr.train_number}</div>
                  <div className="pis-col pis-col-name pis-white">{arr.train_name}</div>
                  <div className="pis-col pis-col-origin pis-dim">{arr.source_name || arr.source}</div>
                  <div className="pis-col pis-col-dest pis-dim">{arr.destination_name || arr.destination}</div>
                  <div className="pis-col pis-col-sched pis-slate">
                    {arr.scheduled_arrival || arr.scheduled_departure || '—'}
                  </div>
                  <div className="pis-col pis-col-eta pis-eta">
                    {arr.dynamic_predicted_eta || '—'}
                    {soon && <span className="pis-soon-badge" style={{ opacity: blinkOn ? 1 : 0.3 }}>● ARRIVING</span>}
                  </div>
                  <div className={`pis-col pis-col-delay ${arr.delay_minutes <= 5 ? 'pis-delay-ok' : arr.delay_minutes <= 30 ? 'pis-delay-warn' : 'pis-delay-crit'}`}>
                    {arr.delay_minutes <= 0 ? '0 min' : `+${Math.round(arr.delay_minutes)} min`}
                  </div>
                  <div className={`pis-col pis-col-pf ${conflict ? 'pis-pf-conflict' : 'pis-pf'}`}>
                    {arr.assigned_platform}
                    {conflict && <span style={{ opacity: blinkOn ? 1 : 0.2, marginLeft: '4px' }}>⚠</span>}
                  </div>
                  <div className={`pis-col pis-col-status ${ds.cls}`}>
                    {arr.current_status}
                  </div>
                </div>
              )
            })
          )}
        </div>
      )}

      {/* ── MOBILE VIEW (Commuter Phone Simulator) ── */}
      {mobileView && data && (
        <div className="pis-mobile-wrapper">
          <div className="pis-phone-frame">
            {/* Phone status bar */}
            <div className="pis-phone-statusbar">
              <span>9:41 AM</span>
              <span>●●●●◌ Wi-Fi ▲</span>
            </div>

            {/* App header */}
            <div className="pis-phone-appheader">
              <div className="pis-phone-app-logo">🚂</div>
              <div>
                <div className="pis-phone-app-title">IRCTC Rail ETA</div>
                <div className="pis-phone-app-sub">{stnInfo?.name}</div>
              </div>
              <div className="pis-phone-live-chip">LIVE</div>
            </div>

            {/* Scrollable card list */}
            <div className="pis-phone-scroll">
              {arrivals.length === 0 ? (
                <div className="pis-phone-empty">No upcoming trains found.</div>
              ) : (
                arrivals.map((arr) => {
                  const soon = isArrivingSoon(arr)
                  const conflict = isConflict(arr)
                  const ds = DELAY_STATUS[arr.delay_status] || DELAY_STATUS.on_time

                  return (
                    <div
                      key={arr.train_number}
                      className={`pis-phone-card ${soon ? 'phone-card-soon' : ''} ${conflict ? 'phone-card-conflict' : ''}`}
                    >
                      <div className="pis-phone-card-top">
                        <div>
                          <span className="pis-phone-tnum">{arr.train_number}</span>
                          <span className={`pis-phone-delay-pill ${arr.delay_minutes <= 5 ? 'green' : arr.delay_minutes <= 30 ? 'amber' : 'red'}`}>
                            {arr.delay_minutes <= 0 ? 'On Time' : `+${Math.round(arr.delay_minutes)}m`}
                          </span>
                        </div>
                        <span className={`pis-phone-status-badge ${arr.delay_status === 'on_time' ? 'status-ok' : arr.delay_status === 'moderate' ? 'status-mod' : 'status-severe'}`}>
                          {arr.current_status}
                        </span>
                      </div>

                      <div className="pis-phone-tname">{arr.train_name}</div>
                      <div className="pis-phone-route">
                        <span>{arr.source_name || arr.source}</span>
                        <span className="pis-phone-arrow"> → </span>
                        <span>{arr.destination_name || arr.destination}</span>
                      </div>

                      <div className="pis-phone-times">
                        <div className="pis-phone-time-box">
                          <div className="pis-phone-time-lbl">SCHEDULED</div>
                          <div className="pis-phone-time-val">{arr.scheduled_arrival || arr.scheduled_departure || '—'}</div>
                        </div>
                        <div className="pis-phone-time-arrow">→</div>
                        <div className="pis-phone-time-box eta-box">
                          <div className="pis-phone-time-lbl">DYNAMIC ETA</div>
                          <div className="pis-phone-time-val eta-val">
                            {arr.dynamic_predicted_eta || '—'}
                          </div>
                        </div>
                      </div>

                      <div className="pis-phone-footer">
                        <span className="pis-phone-pf">🚉 {arr.assigned_platform}</span>
                        {conflict && (
                          <span className="pis-phone-conflict-chip" style={{ opacity: blinkOn ? 1 : 0.4 }}>
                            ⚠ Platform Conflict
                          </span>
                        )}
                        {soon && !conflict && (
                          <span className="pis-phone-soon-chip" style={{ opacity: blinkOn ? 1 : 0.5 }}>
                            ● Arriving Soon
                          </span>
                        )}
                      </div>
                    </div>
                  )
                })
              )}
            </div>

            {/* Phone bottom bar */}
            <div className="pis-phone-navbar">
              <span>🏠</span><span>🔍</span><span>🎟️</span><span>⚙️</span>
            </div>
          </div>

          {/* Note beside phone */}
          <div className="pis-mobile-caption">
            <div className="pis-mobile-caption-title">📱 COMMUTER MOBILE VIEW</div>
            <p>This simulates how passengers view Dynamic ETA predictions through the IRCTC / UTS app or National Rail Connect.
              ETAs update every 8 seconds via the prediction engine.
            </p>
            <div className="pis-legend">
              <div><span className="pis-legend-dot green"></span> On Time (≤5 min)</div>
              <div><span className="pis-legend-dot amber"></span> Delayed (5–30 min)</div>
              <div><span className="pis-legend-dot red"></span> Late (&gt;30 min)</div>
              <div><span className="pis-legend-dot blink"></span> Arriving in &lt;10 min</div>
              <div><span className="pis-legend-dot conflict"></span> Platform Conflict</div>
            </div>
          </div>
        </div>
      )}

      {/* ── Marquee Ticker ── */}
      {data && arrivals.length > 0 && (
        <div className="pis-marquee-bar">
          <span className="pis-marquee-label">LIVE BOARD ►</span>
          <div className="pis-marquee-track">
            <span className="pis-marquee-text">{marqueeText(arrivals)}&nbsp;&nbsp;&nbsp;&nbsp;{marqueeText(arrivals)}</span>
          </div>
        </div>
      )}
    </div>
  )
}
