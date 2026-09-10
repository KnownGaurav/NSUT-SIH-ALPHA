import React, { useState, useEffect, useMemo } from 'react'
import ControlRoomMap from './ControlRoomMap'

export default function ControlRoomView({ onSwitchToSingleTrainView, onOpenAnalytics, onOpenStationOps, onOpenPassengerLed }) {
  const [summaryData, setSummaryData] = useState(null)
  const [selectedTrainNumber, setSelectedTrainNumber] = useState(null)
  const [filterMode, setFilterMode] = useState('ALL') // 'ALL', 'ON_TIME', 'DELAYED', 'SEVERE_DELAY', 'DETERIORATING'
  const [searchQuery, setSearchQuery] = useState('')
  const [allRoutes, setAllRoutes] = useState({})
  const [loading, setLoading] = useState(true)
  const [lastRefreshed, setLastRefreshed] = useState(null)
  const [searching, setSearching] = useState(false)
  const [searchError, setSearchError] = useState('')

  // Live on-demand search handler for uningested trains
  const handleSearchSubmit = async (e) => {
    if (e) e.preventDefault()
    const q = searchQuery.trim()
    if (!q) return

    setSearching(true)
    setSearchError('')
    try {
      const res = await fetch(`/api/trains/search?q=${encodeURIComponent(q)}`)
      if (res.ok) {
        const results = await res.json()
        if (results && results.length > 0) {
          const matched = results[0]
          // Refresh summary to get the newly ingested train with live telemetry
          await fetchSummary()
          setSelectedTrainNumber(matched.train_number)
        } else {
          setSearchError(`No train found for "${q}"`)
        }
      } else {
        setSearchError('Search failed')
      }
    } catch (err) {
      console.error('Search error:', err)
      setSearchError('Search request error')
    } finally {
      setSearching(false)
    }
  }

  // 1. Fetch control-room summary data periodically
  const fetchSummary = async () => {
    try {
      const res = await fetch('/api/trains/control-room/summary')
      if (res.ok) {
        const data = await res.json()
        setSummaryData(data)
        setLastRefreshed(new Date())

        // Auto-select first train ONLY if no train has ever been selected yet
        setSelectedTrainNumber(prev => prev || (data.trains?.length > 0 ? data.trains[0].train_number : null))
      }
    } catch (err) {
      console.error('Control room summary fetch error:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchSummary()
    const interval = setInterval(fetchSummary, 8000)
    return () => clearInterval(interval)
  }, [])

  // 2. Pre-fetch routes for all active trains to draw network corridors
  useEffect(() => {
    if (!summaryData?.trains) return
    const routeMap = { ...allRoutes }
    let missingTrain = false

    summaryData.trains.forEach(async (t) => {
      if (!routeMap[t.train_number]) {
        missingTrain = true
        try {
          const rRes = await fetch(`/api/trains/${t.train_number}/route`)
          if (rRes.ok) {
            const rData = await rRes.json()
            setAllRoutes(prev => ({ ...prev, [t.train_number]: rData }))
          }
        } catch (e) {
          console.warn(`Could not load route for ${t.train_number}:`, e)
        }
      }
    })
  }, [summaryData])

  // 3. Filter and search trains
  const filteredTrains = useMemo(() => {
    if (!summaryData?.trains) return []

    return summaryData.trains.filter(train => {
      // Search query filter
      const matchesSearch = searchQuery === '' ||
        train.train_number.toLowerCase().includes(searchQuery.toLowerCase()) ||
        train.train_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (train.source && train.source.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (train.destination && train.destination.toLowerCase().includes(searchQuery.toLowerCase()))

      if (!matchesSearch) return false

      // Category filter
      if (filterMode === 'ON_TIME') return train.delay_status === 'on_time'
      if (filterMode === 'DELAYED') return train.delay_status === 'moderate'
      if (filterMode === 'SEVERE_DELAY') return train.delay_status === 'severe'
      if (filterMode === 'DETERIORATING') return train.has_deteriorating_eta

      return true
    })
  }, [summaryData, filterMode, searchQuery])

  // Keep selectedTrainNumber aligned when an active text search is typed
  useEffect(() => {
    if (searchQuery.trim()) {
      // Only force reselection if user has typed an active search query and current selection doesn't match it
      const matches = filteredTrains.some(t => t.train_number === selectedTrainNumber)
      if (!matches && filteredTrains.length > 0) {
        setSelectedTrainNumber(filteredTrains[0].train_number)
      }
    }
  }, [filteredTrains, searchQuery])

  const selectedTrain = useMemo(() => {
    if (!summaryData?.trains || !selectedTrainNumber) return null
    return summaryData.trains.find(t => t.train_number === selectedTrainNumber)
  }, [summaryData, selectedTrainNumber])

  const formatTime = (isoString) => {
    if (!isoString) return '--:--'
    try {
      return new Date(isoString).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    } catch {
      return '--:--'
    }
  }

  return (
    <div className="control-room-layout">
      {/* Control Room Top Operations Bar */}
      <header className="cr-header">
        <div className="cr-brand-group">
          <div className="cr-badge">IR-COA</div>
          <div>
            <div className="cr-title">CENTRAL RAILWAY TRAFFIC CONTROL ROOM</div>
            <div className="cr-subtitle">Sectional Supervision & Network-Wide Dynamic ETA Monitoring</div>
          </div>
        </div>

        {/* Operational Filter Strip */}
        <div className="cr-filter-strip">
          <button 
            className={`cr-filter-btn ${filterMode === 'ALL' ? 'active' : ''}`}
            onClick={() => setFilterMode('ALL')}
          >
            <span>ALL TRAINS</span>
            <span className="cr-count-pill">{summaryData?.total_active_trains ?? 0}</span>
          </button>

          <button 
            className={`cr-filter-btn on-time ${filterMode === 'ON_TIME' ? 'active' : ''}`}
            onClick={() => setFilterMode('ON_TIME')}
          >
            <span>ON TIME (&le;5M)</span>
            <span className="cr-count-pill green">{summaryData?.on_time_count ?? 0}</span>
          </button>

          <button 
            className={`cr-filter-btn delayed ${filterMode === 'DELAYED' ? 'active' : ''}`}
            onClick={() => setFilterMode('DELAYED')}
          >
            <span>MODERATE (5-30M)</span>
            <span className="cr-count-pill amber">{summaryData?.delayed_count ?? 0}</span>
          </button>

          <button 
            className={`cr-filter-btn severe ${filterMode === 'SEVERE_DELAY' ? 'active' : ''}`}
            onClick={() => setFilterMode('SEVERE_DELAY')}
          >
            <span>SEVERE (&gt;30M)</span>
            <span className="cr-count-pill red">{summaryData?.severe_delay_count ?? 0}</span>
          </button>

          <button 
            className={`cr-filter-btn deteriorating ${filterMode === 'DETERIORATING' ? 'active' : ''}`}
            onClick={() => setFilterMode('DETERIORATING')}
          >
            <span>DETERIORATING ETA</span>
            <span className="cr-count-pill pink">{summaryData?.deteriorating_count ?? 0}</span>
          </button>
        </div>

        {/* Global Provenance Badge, Analytics & Switcher */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <span 
            className="badge badge-ok"
            style={{ backgroundColor: '#064e3b', borderColor: '#059669', color: '#34d399' }}
          >
            <span className="dot"></span>
            DATA SOURCE: RAIL RADAR LIVE API
          </span>

          <button 
            className="btn" 
            style={{ fontSize: '0.72rem', padding: '0.35rem 0.6rem', borderColor: '#10b981', color: '#34d399' }}
            onClick={onOpenStationOps}
          >
            &#128649; Station Operations
          </button>

          <button 
            className="btn" 
            style={{ fontSize: '0.72rem', padding: '0.35rem 0.6rem', borderColor: '#d97706', color: '#fbbf24' }}
            onClick={onOpenPassengerLed}
          >
            &#128250; Passenger LED Display
          </button>

          <button 
            className="btn" 
            style={{ fontSize: '0.72rem', padding: '0.35rem 0.6rem', borderColor: '#0284c7', color: '#38bdf8' }}
            onClick={onOpenAnalytics}
          >
            &#128202; Model Analytics
          </button>

          <button 
            className="btn" 
            style={{ fontSize: '0.72rem', padding: '0.35rem 0.6rem' }}
            onClick={() => onSwitchToSingleTrainView(selectedTrainNumber)}
          >
            &larr; Single Train View
          </button>
        </div>
      </header>

      {/* Main Control Room Grid: Train List Sidebar | Large India Map | Selected Train Detail Sidebar */}
      <div className="cr-workspace-grid">
        {/* Left Secondary Area: Active Fleet Table & Search */}
        <section className="cr-panel cr-sidebar-left">
          <div className="cr-panel-header">
            <span>TRAIN SUPERVISION ROSTER ({filteredTrains.length})</span>
            {lastRefreshed && (
              <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                {lastRefreshed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </span>
            )}
          </div>

          {/* Search Box with Live Provider Ingestion */}
          <form className="cr-search-wrapper" onSubmit={handleSearchSubmit} style={{ display: 'flex', gap: '0.35rem', alignItems: 'center' }}>
            <div style={{ position: 'relative', flex: 1 }}>
              <input 
                type="text"
                className="cr-search-input"
                placeholder="Search train (e.g. 12565, NDLS)..."
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value)
                  if (searchError) setSearchError('')
                }}
              />
              {searchQuery && (
                <button 
                  type="button" 
                  className="cr-search-clear" 
                  onClick={() => {
                    setSearchQuery('')
                    setSearchError('')
                  }}
                >&times;</button>
              )}
            </div>
            <button 
              type="submit" 
              className="btn btn-primary"
              style={{ fontSize: '0.68rem', padding: '0.3rem 0.6rem', height: '27px', whiteSpace: 'nowrap' }}
              disabled={searching || !searchQuery.trim()}
            >
              {searching ? '...' : 'Track'}
            </button>
          </form>

          {searchError && (
            <div style={{ padding: '0.3rem 0.5rem', background: '#450a0a', color: '#fca5a5', fontSize: '0.65rem', borderBottom: '1px solid #991b1b', fontFamily: 'var(--font-mono)' }}>
              {searchError}
            </div>
          )}

          {/* Train List */}
          <div className="cr-train-list">
            {searching ? (
              <div style={{ padding: '1.5rem', textAlign: 'center', color: '#38bdf8', fontSize: '0.75rem', fontFamily: 'var(--font-mono)' }}>
                Querying Rail Radar live API for {searchQuery}...
              </div>
            ) : filteredTrains.length === 0 ? (
              <div style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                <p>No trains match &ldquo;{searchQuery}&rdquo;.</p>
                {searchQuery.trim().length === 5 && (
                  <button 
                    className="btn btn-primary" 
                    style={{ marginTop: '0.75rem', fontSize: '0.7rem', padding: '0.3rem 0.6rem' }}
                    onClick={handleSearchSubmit}
                  >
                    Fetch Train {searchQuery} from Live API
                  </button>
                )}
              </div>
            ) : (
              filteredTrains.map((train) => {
                const isSelected = train.train_number === selectedTrainNumber
                let statusClass = 'status-green'
                if (train.delay_status === 'moderate') statusClass = 'status-amber'
                if (train.delay_status === 'severe') statusClass = 'status-red'

                return (
                  <div 
                    key={train.train_number}
                    className={`cr-train-row ${isSelected ? 'selected' : ''}`}
                    onClick={() => setSelectedTrainNumber(train.train_number)}
                  >
                    <div className="cr-row-top">
                      <span className="cr-train-num">{train.train_number}</span>
                      <span className={`cr-delay-pill ${statusClass}`}>
                        {train.current_delay_minutes > 0 ? `+${train.current_delay_minutes}m` : '0m'}
                      </span>
                    </div>

                    <div className="cr-train-name" title={train.train_name}>
                      {train.train_name}
                    </div>

                    <div className="cr-row-bottom">
                      <span>{train.current_station || '--'} &rarr; {train.next_station || '--'}</span>
                      <span style={{ fontFamily: 'var(--font-mono)' }}>{train.speed_kmh} km/h</span>
                    </div>

                    {train.has_deteriorating_eta && (
                      <div className="cr-deteriorating-tag">
                        &bull; ETA Deteriorating
                      </div>
                    )}
                  </div>
                )
              })
            )}
          </div>
        </section>

        {/* Center Primary Area: Dominant Pan-India / Corridor Map */}
        <section className="cr-panel cr-map-area">
          <div className="cr-panel-header">
            <span>NETWORK OVERVIEW &bull; ACTIVE CORRIDORS</span>
            <span style={{ fontSize: '0.65rem', color: '#38bdf8' }}>
              {selectedTrain ? `FOCUSED: ${selectedTrain.train_number} (${selectedTrain.source} -> ${selectedTrain.destination})` : 'SELECT TRAIN'}
            </span>
          </div>

          <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
            <ControlRoomMap 
              trains={filteredTrains}
              selectedTrainNumber={selectedTrainNumber}
              onSelectTrain={(tNum) => setSelectedTrainNumber(tNum)}
              allRoutes={allRoutes}
            />
          </div>
        </section>

        {/* Right Secondary Area: Selected Train Operational Detail */}
        <section className="cr-panel cr-sidebar-right">
          <div className="cr-panel-header">
            <span>SELECTED TRAIN TELEMETRY</span>
            <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
              {selectedTrain ? selectedTrain.train_number : '--'}
            </span>
          </div>

          {selectedTrain ? (
            <div className="cr-detail-content">
              {/* Train Name & Route */}
              <div className="cr-card">
                <div className="cr-card-title">Train Identification</div>
                <div style={{ fontSize: '1rem', fontWeight: 700, color: '#f8fafc', fontFamily: 'var(--font-mono)' }}>
                  {selectedTrain.train_number}
                </div>
                <div style={{ fontSize: '0.8rem', color: '#cbd5e1', marginTop: '0.15rem' }}>
                  {selectedTrain.train_name}
                </div>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                  {selectedTrain.train_type} &bull; {selectedTrain.source_name || selectedTrain.source} &rarr; {selectedTrain.destination_name || selectedTrain.destination}
                </div>
              </div>

              {/* Current Speed & Delay */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                <div className="cr-card">
                  <div className="cr-card-title">Velocity</div>
                  <div className="cr-card-val">
                    {selectedTrain.speed_kmh} <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>KM/H</span>
                  </div>
                </div>

                <div className="cr-card">
                  <div className="cr-card-title">Current Delay</div>
                  <div className="cr-card-val" style={{
                    color: selectedTrain.delay_status === 'on_time' ? '#22c55e' : 
                           selectedTrain.delay_status === 'moderate' ? '#f59e0b' : '#ef4444'
                  }}>
                    +{selectedTrain.current_delay_minutes} <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>MIN</span>
                  </div>
                </div>
              </div>

              {/* Block Section & Next Station */}
              <div className="cr-card">
                <div className="cr-card-title">Block Section & Next Stop</div>
                <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#f8fafc', fontFamily: 'var(--font-mono)' }}>
                  {selectedTrain.current_station || '--'} &rarr; {selectedTrain.next_station || '--'}
                </div>
                <div style={{ fontSize: '0.75rem', color: '#38bdf8', marginTop: '0.2rem' }}>
                  Next Stop: <strong>{selectedTrain.next_station_name || selectedTrain.next_station || 'N/A'}</strong>
                </div>
              </div>

              {/* Dynamic ML ETA & Confidence */}
              <div className="cr-card">
                <div className="cr-card-title" style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Dynamic Predicted ETA</span>
                  <span style={{ color: '#38bdf8' }}>XGBOOST ML</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginTop: '0.25rem' }}>
                  <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#38bdf8', fontFamily: 'var(--font-mono)' }}>
                    {formatTime(selectedTrain.predicted_eta)}
                  </div>
                  {selectedTrain.baseline_eta && (
                    <div style={{ fontSize: '0.75rem', color: '#94a3b8', fontFamily: 'var(--font-mono)' }}>
                      Base: {formatTime(selectedTrain.baseline_eta)} ({selectedTrain.eta_difference_minutes > 0 ? `+${selectedTrain.eta_difference_minutes}m` : `${selectedTrain.eta_difference_minutes}m`})
                    </div>
                  )}
                </div>

                {/* Range & Statistical Confidence */}
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.68rem', color: '#cbd5e1', marginTop: '0.4rem', borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '0.35rem', fontFamily: 'var(--font-mono)' }}>
                  <span>
                    Range: {formatTime(selectedTrain.lower_bound)} - {formatTime(selectedTrain.upper_bound)}
                  </span>
                  <span>
                    Conf: {selectedTrain.eta_confidence ? `${(selectedTrain.eta_confidence * 100).toFixed(0)}%` : '88%'}
                  </span>
                </div>
              </div>

              {/* ETA Change & Deterministic Reason */}
              <div className="cr-card">
                <div className="cr-card-title">ETA Change & Attribution</div>
                <div style={{ fontSize: '0.74rem', color: '#f1f5f9', marginTop: '0.2rem', lineHeight: 1.35 }}>
                  {selectedTrain.explanation_summary || (
                    selectedTrain.eta_difference_minutes > 1.0 
                      ? `ETA deferred by +${selectedTrain.eta_difference_minutes}m compared to scheduled timetable baseline.`
                      : 'Sectional run on schedule within calibrated model tolerance.'
                  )}
                </div>

                {selectedTrain.contributing_factors?.length > 0 && (
                  <div style={{ marginTop: '0.4rem', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                    {selectedTrain.contributing_factors.map((f, i) => (
                      <div key={i} style={{ fontSize: '0.68rem', color: '#cbd5e1' }}>
                        <span className={`factor-tag ${f.category}`}>{f.category}</span>
                        {f.impact_description}
                        <div style={{ fontSize: '0.62rem', color: '#94a3b8', fontFamily: 'var(--font-mono)', paddingLeft: '0.2rem' }}>
                          &bull; {f.metric_evidence}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Geographic Coordinates Readout */}
              <div className="cr-card">
                <div className="cr-card-title">Telemetry Coordinate Stream</div>
                <div style={{ fontSize: '0.68rem', color: '#94a3b8', fontFamily: 'var(--font-mono)' }}>
                  <div>LAT: {selectedTrain.latitude.toFixed(4)}° N &bull; LON: {selectedTrain.longitude.toFixed(4)}° E</div>
                  <div>MODE: {selectedTrain.operational_event}</div>
                  <div style={{ color: selectedTrain.data_source === 'RAILRADAR_LIVE' ? '#34d399' : '#f59e0b', marginTop: '0.2rem', fontWeight: 600 }}>
                    DATA SOURCE: {selectedTrain.data_source === 'RAILRADAR_LIVE' ? 'RAIL RADAR LIVE API' : selectedTrain.data_source || 'SIMULATION'}
                  </div>
                </div>
              </div>

              {/* Jump to full single train telemetry view button */}
              <button 
                className="btn btn-primary" 
                style={{ width: '100%', padding: '0.5rem', justifyContent: 'center', fontSize: '0.74rem', marginTop: '0.25rem' }}
                onClick={() => onSwitchToSingleTrainView(selectedTrain.train_number)}
              >
                Inspect Detailed Timeline &amp; Simulator Controls &rarr;
              </button>
            </div>
          ) : (
            <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.75rem' }}>
              Select a train from the roster or map to inspect operational telemetry.
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
